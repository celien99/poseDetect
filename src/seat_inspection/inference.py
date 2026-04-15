from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import cv2
from media_inputs import FrameStream, load_image_frame, open_frame_stream

from .config import (
    ImageInferenceConfig,
    InferenceConfig,
    MultiCameraInferenceConfig,
    RuleConfig,
    StateMachineConfig,
)
from .engine import ActionRecognitionEngine
from .multi_camera import CameraDecisionSample, fuse_camera_decisions
from .person_detection import PersonDetector
from .pipeline import InspectionPipeline
from .pose_estimation import PoseEstimator
from .region_provider import build_seat_region_provider
from .reporting import export_action_report
from .schemas import ActionDecision, FrameObservation
from .state_machine import InspectionStateMachine
from .visualization import annotate_frame


def run_rule_based_inference(
    observations: Iterable[FrameObservation],
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    """直接对结构化观测序列运行规则，不依赖 YOLO 模型。"""
    engine = ActionRecognitionEngine(rule_config)
    return engine.process_stream(observations)


def run_video_inference(
    config: InferenceConfig,
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    """对视频流或 MVS 相机流执行姿态推理与动作识别。"""
    pipeline = _build_pipeline(config, rule_config)
    stream = open_frame_stream(config.source)

    if not stream.is_opened():
        raise ValueError(f"Unable to open inference source: {config.source}")

    writer = _build_writer(stream, config)
    decisions: list[ActionDecision] = []
    show_window = config.show_window

    try:
        while True:
            media_frame = stream.read_frame()
            if media_frame is None:
                break

            frame_result = pipeline.process_frame(
                frame=media_frame.image,
                frame_index=media_frame.frame_index,
                snapshot=False,
            )
            decisions.append(frame_result.decision)

            if writer is not None or show_window:
                annotated = annotate_frame(
                    media_frame.image,
                    frame_result.seat_regions,
                    frame_result.decision,
                    frame_result.inspection_result,
                    frame_result.person_detection,
                )
                if writer is not None:
                    writer.write(annotated)
                if show_window and _show_window(
                    config.window_name,
                    annotated,
                    config.window_wait_ms,
                    config.exit_key,
                ):
                    break
    finally:
        stream.release()
        if writer is not None:
            writer.release()
        if show_window:
            _destroy_window(config.window_name)

    inspection_result = pipeline.finalize()

    export_action_report(
        config.output_json_path,
        decisions,
        metadata={
            "source": config.source,
            "pose_model_path": config.pose_model_path,
            "person_model_path": config.person_model_path,
            "seat_region_mode": pipeline.seat_region_provider.mode,
            "seat_model_path": config.seat_model_path,
            "save_visualization": config.save_visualization,
            "show_window": config.show_window,
            "mode": "video",
        },
        inspection_result=inspection_result,
    )
    return decisions


def run_multi_camera_inference(
    config: MultiCameraInferenceConfig,
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    """对多路视频流或工业相机流执行融合推理。"""
    if not config.cameras:
        raise ValueError("Multi-camera inference requires at least one camera config")

    camera_contexts = [_build_multi_camera_context(config, camera_config, rule_config) for camera_config in config.cameras]
    fused_state_machine = InspectionStateMachine(config.state_machine)
    decisions: list[ActionDecision] = []
    writer: cv2.VideoWriter | None = None
    show_window = config.show_window
    frame_cycle_index = 0

    try:
        while True:
            frame_cycle_index += 1
            cycle_data: list[dict[str, Any]] = []
            for context in camera_contexts:
                media_frame = context["stream"].read_frame()
                if media_frame is None:
                    inspection_result = fused_state_machine.finalize()
                    export_action_report(
                        config.output_json_path,
                        decisions,
                        metadata=_build_multi_camera_metadata(config, camera_contexts),
                        inspection_result=inspection_result,
                    )
                    return decisions

                frame_result = context["pipeline"].process_frame(
                    frame=media_frame.image,
                    frame_index=media_frame.frame_index,
                    snapshot=False,
                )
                cycle_data.append(
                    {
                        "context": context,
                        "media_frame": media_frame,
                        "frame_result": frame_result,
                    },
                )

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
            decisions.append(fused_decision)
            fused_inspection_result = fused_state_machine.update(fused_decision)

            if writer is not None or show_window or config.save_visualization:
                canvas = _render_multi_camera_canvas(
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


def run_image_inference(
    config: ImageInferenceConfig,
    rule_config: RuleConfig | None = None,
) -> ActionDecision:
    """对单张图片执行姿态推理与动作判断。"""
    media_frame = load_image_frame(config.source)

    pipeline = _build_pipeline(
        InferenceConfig(
            pose_model_path=config.pose_model_path,
            source=config.source,
            seat_regions=config.seat_regions,
            output_json_path=config.output_json_path,
            person_model_path=config.person_model_path,
            seat_model_path=config.seat_model_path,
            confidence=config.confidence,
            iou=config.iou,
            device=config.device,
            save_visualization=config.save_visualization,
            keypoint_processing=config.keypoint_processing,
            state_machine=config.state_machine,
        ),
        rule_config,
    )
    frame_result = pipeline.process_frame(
        frame=media_frame.image,
        frame_index=media_frame.frame_index,
        snapshot=True,
    )
    inspection_result = pipeline.finalize()

    annotated_image_path = config.output_image_path
    if config.save_visualization:
        annotated_image_path = annotated_image_path or "outputs/action_image_preview.jpg"
        annotated = annotate_frame(
            media_frame.image,
            frame_result.seat_regions,
            frame_result.decision,
            inspection_result,
            frame_result.person_detection,
        )
        output_path = Path(annotated_image_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), annotated)

    export_action_report(
        config.output_json_path,
        [frame_result.decision],
        metadata={
            "source": config.source,
            "pose_model_path": config.pose_model_path,
            "person_model_path": config.person_model_path,
            "seat_region_mode": pipeline.seat_region_provider.mode,
            "seat_model_path": config.seat_model_path,
            "save_visualization": config.save_visualization,
            "output_image_path": annotated_image_path,
            "mode": "image",
        },
        inspection_result=inspection_result,
    )
    return frame_result.decision


def _build_pipeline(
    config: InferenceConfig,
    rule_config: RuleConfig | None = None,
) -> InspectionPipeline:
    engine = ActionRecognitionEngine(
        rule_config,
        config.keypoint_processing,
        config.state_machine,
    )
    return InspectionPipeline(
        pose_estimator=PoseEstimator(config.pose_model_path),
        seat_region_provider=build_seat_region_provider(
            config.seat_regions,
            config.seat_model_path,
            confidence=config.confidence,
            iou=config.iou,
            device=config.device,
        ),
        engine=engine,
        confidence=config.confidence,
        iou=config.iou,
        device=config.device,
        person_detector=PersonDetector(config.person_model_path),
    )


def _build_multi_camera_context(
    config: MultiCameraInferenceConfig,
    camera_config,
    rule_config: RuleConfig | None,
) -> dict[str, Any]:
    per_camera_inference = InferenceConfig(
        pose_model_path=camera_config.pose_model_path or config.pose_model_path,
        source=camera_config.source,
        seat_regions=camera_config.seat_regions,
        output_json_path=config.output_json_path,
        output_video_path=None,
        person_model_path=camera_config.person_model_path or config.person_model_path,
        seat_model_path=camera_config.seat_model_path or config.seat_model_path,
        confidence=camera_config.confidence if camera_config.confidence is not None else config.confidence,
        iou=camera_config.iou if camera_config.iou is not None else config.iou,
        device=camera_config.device or config.device,
        save_visualization=False,
        show_window=False,
        keypoint_processing=config.keypoint_processing,
        state_machine=StateMachineConfig(enabled=False),
    )
    stream = open_frame_stream(camera_config.source)
    if not stream.is_opened():
        raise ValueError(f"Unable to open inference source: {camera_config.source}")
    return {
        "name": camera_config.name,
        "source": camera_config.source,
        "stream": stream,
        "pipeline": _build_pipeline(per_camera_inference, rule_config),
    }


def _build_writer(
    stream: FrameStream,
    config: InferenceConfig,
) -> cv2.VideoWriter | None:
    """按输入视频尺寸创建可视化输出视频写入器。"""
    if not config.save_visualization:
        return None

    output_path = config.output_video_path or "outputs/action_preview.mp4"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    width = int(stream.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = stream.get(cv2.CAP_PROP_FPS) or 25.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(output_path, fourcc, fps, (width, height))


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
            }
            for context in camera_contexts
        ],
    }


def _render_multi_camera_canvas(
    cycle_data: list[dict[str, Any]],
    fused_decision: ActionDecision,
    fused_inspection_result,
) -> Any:
    annotated_frames: list[Any] = []
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
