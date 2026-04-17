from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
from media_inputs import FrameStream, open_frame_stream

from .config import (
    CameraInferenceConfig,
    KeypointProcessingConfig,
    MultiCameraInferenceConfig,
    RuleConfig,
    StateMachineConfig,
)
from .engine import ActionRecognitionEngine
from .multi_camera import CameraDecisionSample, fuse_camera_decisions
from .person_detection import PersonDetector
from .pipeline import InspectionPipeline
from .pose_estimation import PoseEstimator
from .region_provider import DetectedSeatRegionProvider, FixedSeatRegionProvider
from .reporting import export_action_report
from .schemas import ActionDecision, FrameObservation
from .seat_detection import SeatDetector
from .state_machine import InspectionStateMachine
from .tracking import (
    MultiCameraOperatorAssociator,
    OperatorTrackAssignment,
    PrimaryOperatorTracker,
)
from .visualization import annotate_frame


@dataclass(slots=True)
class CameraRuntimeStats:
    """单路相机在多机位推理过程中的运行统计。"""

    name: str
    source: str
    active: bool = True
    frames_processed: int = 0
    dropped_frames: int = 0
    consecutive_failures: int = 0
    last_timestamp_ms: float | None = None
    last_status: str = "idle"


def run_rule_based_inference(
    observations: Iterable[FrameObservation],
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    """直接对结构化观测序列运行规则，不依赖 YOLO 模型。"""
    engine = ActionRecognitionEngine(rule_config)
    return engine.process_stream(observations)


def run_multi_camera_inference(
    config: MultiCameraInferenceConfig,
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    """对多路视频流或工业相机流执行融合推理。"""
    if not config.cameras:
        raise ValueError("Multi-camera inference requires at least one camera config")

    camera_contexts = [_build_multi_camera_context(config, camera_config, rule_config) for camera_config in config.cameras]
    fused_state_machine = InspectionStateMachine(config.state_machine)
    operator_associator = MultiCameraOperatorAssociator()
    decisions: list[ActionDecision] = []
    writer: cv2.VideoWriter | None = None
    show_window = config.show_window
    frame_cycle_index = 0

    try:
        while True:
            frame_cycle_index += 1
            cycle_data: list[dict[str, Any]] = []
            for context in [item for item in camera_contexts if item["stats"].active]:
                media_frame = context["stream"].read_frame()
                if media_frame is None:
                    stats = context["stats"]
                    stats.dropped_frames += 1
                    stats.consecutive_failures += 1
                    stats.last_status = "missing"
                    if stats.consecutive_failures > max(0, config.max_consecutive_read_failures):
                        stats.active = False
                        stats.last_status = "offline"
                    continue

                stats = context["stats"]
                stats.frames_processed += 1
                stats.consecutive_failures = 0
                stats.last_timestamp_ms = media_frame.timestamp_ms
                stats.last_status = "ok"

                frame_result = context["pipeline"].process_frame(
                    frame=media_frame.image,
                    frame_index=media_frame.frame_index,
                    snapshot=False,
                )
                operator_assignment = context["tracker"].update(
                    media_frame.frame_index,
                    frame_result.person_detection,
                )
                cycle_data.append(
                    {
                        "context": context,
                        "media_frame": media_frame,
                        "frame_result": frame_result,
                        "operator_assignment": operator_assignment,
                    },
                )

            if len(cycle_data) < max(1, config.min_active_cameras):
                if _count_active_cameras(camera_contexts) < max(1, config.min_active_cameras):
                    inspection_result = fused_state_machine.finalize()
                    export_action_report(
                        config.output_json_path,
                        decisions,
                        metadata=_build_multi_camera_metadata(config, camera_contexts),
                        inspection_result=inspection_result,
                    )
                    return decisions
                continue

            fused_decision = fuse_camera_decisions(
                [
                    CameraDecisionSample(
                        camera_name=item["context"]["name"],
                        frame_index=item["media_frame"].frame_index,
                        timestamp_ms=item["media_frame"].timestamp_ms,
                        decision=item["frame_result"].decision,
                    )
                    for item in cycle_data
                ],
                frame_index=frame_cycle_index,
                fusion_config=config.fusion,
            )
            operator_association = operator_associator.update(
                [
                    assignment
                    for assignment in (
                        item["operator_assignment"]
                        for item in cycle_data
                    )
                    if assignment is not None
                ],
            )
            fused_decision.operator_track_ids = dict(operator_association.camera_track_ids)
            fused_decision.operator_association_id = operator_association.association_id
            fused_decision.active_cameras = [
                item["context"]["name"]
                for item in cycle_data
            ]
            decisions.append(fused_decision)
            fused_inspection_result = fused_state_machine.update(fused_decision)

            if writer is not None or show_window or config.save_visualization:
                canvas = _render_multi_camera_canvas(
                    camera_contexts,
                    cycle_data,
                    fused_decision,
                    fused_inspection_result,
                )
                if config.save_visualization:
                    if writer is None:
                        writer = _build_canvas_writer(
                            config.output_video_path or "outputs/multi_camera_action_preview.mp4",
                            canvas,
                            _resolve_writer_fps([context["stream"] for context in camera_contexts]),
                        )
                    writer.write(canvas)
                if show_window and _show_window(
                    config.window_name,
                    canvas,
                    config.window_wait_ms,
                    config.exit_key,
                ):
                    break
    finally:
        for context in camera_contexts:
            context["stream"].release()
        if writer is not None:
            writer.release()
        if show_window:
            _destroy_window(config.window_name)

    inspection_result = fused_state_machine.finalize()
    export_action_report(
        config.output_json_path,
        decisions,
        metadata=_build_multi_camera_metadata(config, camera_contexts),
        inspection_result=inspection_result,
    )
    return decisions


def _build_pipeline(
    pose_model_path: str,
    seat_regions,
    person_model_path: str | None,
    seat_model_path: str | None,
    confidence: float,
    iou: float,
    device: str,
    keypoint_processing: KeypointProcessingConfig,
    state_machine: StateMachineConfig,
    rule_config: RuleConfig | None = None,
) -> InspectionPipeline:
    engine = ActionRecognitionEngine(
        rule_config,
        keypoint_processing,
        state_machine,
    )
    if seat_model_path:
        seat_region_provider = DetectedSeatRegionProvider(
            template_regions=seat_regions,
            detector=SeatDetector(seat_model_path),
            confidence=confidence,
            iou=iou,
            device=device,
        )
    else:
        seat_region_provider = FixedSeatRegionProvider(seat_regions=seat_regions)
    return InspectionPipeline(
        pose_estimator=PoseEstimator(pose_model_path),
        seat_region_provider=seat_region_provider,
        engine=engine,
        confidence=confidence,
        iou=iou,
        device=device,
        person_detector=PersonDetector(person_model_path),
    )


def _build_multi_camera_context(
    config: MultiCameraInferenceConfig,
    camera_config: CameraInferenceConfig,
    rule_config: RuleConfig | None,
) -> dict[str, Any]:
    stream = open_frame_stream(camera_config.source)
    if not stream.is_opened():
        raise ValueError(f"Unable to open inference source: {camera_config.source}")
    return {
        "name": camera_config.name,
        "source": camera_config.source,
        "stream": stream,
        "stats": CameraRuntimeStats(
            name=camera_config.name,
            source=camera_config.source,
        ),
        "tracker": PrimaryOperatorTracker(camera_config.name),
        "pipeline": _build_pipeline(
            pose_model_path=camera_config.pose_model_path or config.pose_model_path,
            seat_regions=camera_config.seat_regions,
            person_model_path=camera_config.person_model_path or config.person_model_path,
            seat_model_path=camera_config.seat_model_path or config.seat_model_path,
            confidence=(
                camera_config.confidence
                if camera_config.confidence is not None
                else config.confidence
            ),
            iou=camera_config.iou if camera_config.iou is not None else config.iou,
            device=camera_config.device or config.device,
            keypoint_processing=config.keypoint_processing,
            state_machine=StateMachineConfig(enabled=False),
            rule_config=rule_config,
        ),
    }


def _build_canvas_writer(
    output_path: str,
    frame: Any,
    fps: float,
) -> cv2.VideoWriter:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    height, width = frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(output_path, fourcc, fps or 25.0, (width, height))


def _show_window(
    window_name: str,
    frame: Any,
    wait_ms: int,
    exit_key: str,
) -> bool:
    try:
        cv2.imshow(window_name, frame)
    except cv2.error as exc:
        raise RuntimeError(
            "OpenCV window display is unavailable in the current environment. "
            "Disable `show_window` or run with GUI support.",
        ) from exc

    key = cv2.waitKey(max(1, wait_ms)) & 0xFF
    return key == ord(exit_key[:1])


def _destroy_window(window_name: str) -> None:
    try:
        cv2.destroyWindow(window_name)
    except cv2.error:
        pass


def _build_multi_camera_metadata(
    config: MultiCameraInferenceConfig,
    camera_contexts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "mode": "multi_camera",
        "pose_model_path": config.pose_model_path,
        "person_model_path": config.person_model_path,
        "seat_model_path": config.seat_model_path,
        "min_active_cameras": config.min_active_cameras,
        "max_consecutive_read_failures": config.max_consecutive_read_failures,
        "target_selection_strategy": "seat_proximity",
        "operator_association_strategy": "persistent_primary_operator",
        "save_visualization": config.save_visualization,
        "show_window": config.show_window,
        "fusion": {
            "default_action_strategy": config.fusion.default_action_strategy,
            "touch_action_strategy": config.fusion.touch_action_strategy,
            "lift_action_strategy": config.fusion.lift_action_strategy,
            "time_tolerance_ms": config.fusion.time_tolerance_ms,
        },
        "cameras": [
            {
                "name": context["name"],
                "source": context["source"],
                "active": context["stats"].active,
                "frames_processed": context["stats"].frames_processed,
                "dropped_frames": context["stats"].dropped_frames,
                "consecutive_failures": context["stats"].consecutive_failures,
                "last_timestamp_ms": context["stats"].last_timestamp_ms,
                "last_status": context["stats"].last_status,
            }
            for context in camera_contexts
        ],
    }


def _render_multi_camera_canvas(
    camera_contexts: list[dict[str, Any]],
    cycle_data: list[dict[str, Any]],
    fused_decision: ActionDecision,
    fused_inspection_result,
) -> Any:
    annotated_frames_by_name: dict[str, Any] = {}
    for item in cycle_data:
        annotated = annotate_frame(
            item["media_frame"].image,
            item["frame_result"].seat_regions,
            item["frame_result"].decision,
            None,
            item["frame_result"].person_detection,
        )
        cv2.putText(
            annotated,
            item["context"]["name"],
            (20, max(90, annotated.shape[0] - 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        annotated_frames_by_name[item["context"]["name"]] = annotated

    reference_frame = next(iter(annotated_frames_by_name.values()))
    annotated_frames: list[Any] = []
    for context in camera_contexts:
        annotated = annotated_frames_by_name.get(context["name"])
        if annotated is None:
            annotated = _build_camera_placeholder(context, reference_frame.shape)
        annotated_frames.append(annotated)

    canvas = _compose_frame_grid(annotated_frames)
    status_items = [f"{name}={int(state)}" for name, state in fused_decision.actions.items()]
    status_text = "fused " + " ".join(status_items[:4]) if status_items else "fused no_action"
    cv2.putText(
        canvas,
        status_text,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    summary = f"workflow={fused_inspection_result.current_state} result={fused_inspection_result.status}"
    cv2.putText(
        canvas,
        summary,
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 200, 0) if fused_inspection_result.status == "OK" else (0, 0, 255),
        2,
        cv2.LINE_AA,
    )
    return canvas


def _build_camera_placeholder(context: dict[str, Any], reference_shape: tuple[int, ...]) -> Any:
    height, width = reference_shape[:2]
    placeholder = np.zeros((height, width, 3), dtype="uint8")
    stats = context["stats"]
    status_text = f"{context['name']} {stats.last_status}"
    cv2.putText(
        placeholder,
        status_text,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        placeholder,
        f"dropped={stats.dropped_frames} failures={stats.consecutive_failures}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (180, 180, 180),
        2,
        cv2.LINE_AA,
    )
    return placeholder


def _compose_frame_grid(frames: list[Any]) -> Any:
    if not frames:
        raise ValueError("No frames available to compose")

    tile_width = min(frame.shape[1] for frame in frames)
    tile_height = min(frame.shape[0] for frame in frames)
    resized = [
        cv2.resize(frame, (tile_width, tile_height))
        for frame in frames
    ]
    if len(resized) == 1:
        return resized[0]

    rows: list[Any] = []
    for index in range(0, len(resized), 2):
        row_frames = resized[index:index + 2]
        if len(row_frames) == 1:
            blank = 255 * (row_frames[0] * 0)
            row_frames = [row_frames[0], blank.astype(row_frames[0].dtype)]
        rows.append(cv2.hconcat(row_frames))
    return rows[0] if len(rows) == 1 else cv2.vconcat(rows)


def _resolve_writer_fps(streams: list[FrameStream]) -> float:
    for stream in streams:
        fps = stream.get(cv2.CAP_PROP_FPS)
        if fps:
            return fps
    return 25.0


def _count_active_cameras(camera_contexts: list[dict[str, Any]]) -> int:
    return sum(1 for context in camera_contexts if context["stats"].active)
