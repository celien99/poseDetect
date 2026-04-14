from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import cv2
from ultralytics import YOLO

from .config import InferenceConfig, RuleConfig
from .engine import ActionRecognitionEngine
from .reporting import export_action_report
from .schemas import ActionDecision, BoundingBox, FrameObservation, Point, PoseSample, SeatRegions

COCO_KEYPOINT_INDEX = {
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_wrist": 9,
    "right_wrist": 10,
    "left_hip": 11,
    "right_hip": 12,
}


def run_rule_based_inference(
    observations: Iterable[FrameObservation],
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    engine = ActionRecognitionEngine(rule_config)
    return engine.process_stream(observations)


def run_video_inference(
    config: InferenceConfig,
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    model = YOLO(config.pose_model_path)
    engine = ActionRecognitionEngine(rule_config)
    capture = cv2.VideoCapture(_resolve_source(config.source))

    if not capture.isOpened():
        raise ValueError(f"Unable to open inference source: {config.source}")

    writer = _build_writer(capture, config)
    decisions: list[ActionDecision] = []
    frame_index = 0

    try:
        while True:
            success, frame = capture.read()
            if not success:
                break

            frame_index += 1
            result = model.predict(
                frame,
                conf=config.confidence,
                iou=config.iou,
                device=config.device,
                verbose=False,
            )[0]
            observation = _build_observation(frame_index, result, config.seat_regions)

            if observation is None:
                engine.reset()
                decision = ActionDecision(
                    frame_index=frame_index,
                    touch_side_surface=False,
                    lift_seat_bottom=False,
                    scores={
                        "touch_side_surface": 0.0,
                        "lift_seat_bottom": 0.0,
                    },
                )
            else:
                decision = engine.process_frame(observation)

            decisions.append(decision)

            if writer is not None:
                annotated = _annotate_frame(frame, config.seat_regions, decision)
                writer.write(annotated)
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    export_action_report(
        config.output_json_path,
        decisions,
        metadata={
            "source": config.source,
            "pose_model_path": config.pose_model_path,
            "save_visualization": config.save_visualization,
        },
    )
    return decisions


def _resolve_source(source: str) -> int | str:
    if source.isdigit():
        return int(source)
    return source


def _build_writer(
    capture: cv2.VideoCapture,
    config: InferenceConfig,
) -> cv2.VideoWriter | None:
    if not config.save_visualization:
        return None

    output_path = config.output_video_path or "outputs/action_preview.mp4"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(output_path, fourcc, fps, (width, height))


def _build_observation(
    frame_index: int,
    result: Any,
    seat_regions: SeatRegions,
) -> FrameObservation | None:
    pose = _extract_primary_pose(result)
    if pose is None:
        return None

    return FrameObservation(
        frame_index=frame_index,
        seat_regions=seat_regions,
        pose=pose,
    )


def _extract_primary_pose(result: Any) -> PoseSample | None:
    keypoints = getattr(result, "keypoints", None)
    if keypoints is None or keypoints.data is None:
        return None

    keypoint_data = keypoints.data.cpu().numpy()
    if len(keypoint_data) == 0:
        return None

    boxes = getattr(result, "boxes", None)
    selected_index = 0
    if boxes is not None and boxes.conf is not None:
        confidences = boxes.conf.cpu().numpy()
        selected_index = int(confidences.argmax())

    pose_data = keypoint_data[selected_index]
    return PoseSample(
        left_shoulder=_point_from_pose(pose_data, COCO_KEYPOINT_INDEX["left_shoulder"]),
        right_shoulder=_point_from_pose(pose_data, COCO_KEYPOINT_INDEX["right_shoulder"]),
        left_wrist=_point_from_pose(pose_data, COCO_KEYPOINT_INDEX["left_wrist"]),
        right_wrist=_point_from_pose(pose_data, COCO_KEYPOINT_INDEX["right_wrist"]),
        left_hip=_point_from_pose(pose_data, COCO_KEYPOINT_INDEX["left_hip"]),
        right_hip=_point_from_pose(pose_data, COCO_KEYPOINT_INDEX["right_hip"]),
    )


def _point_from_pose(pose_data: Any, index: int) -> Point:
    x, y, confidence = pose_data[index]
    return Point(float(x), float(y), float(confidence))


def _annotate_frame(
    frame: Any,
    seat_regions: SeatRegions,
    decision: ActionDecision,
) -> Any:
    annotated = frame.copy()
    _draw_box(annotated, seat_regions.overall, (0, 255, 0), "seat")
    _draw_box(annotated, seat_regions.side_surface, (255, 255, 0), "side")
    _draw_box(annotated, seat_regions.bottom_surface, (255, 0, 255), "bottom")

    status = (
        f"touch={int(decision.touch_side_surface)} "
        f"lift={int(decision.lift_seat_bottom)}"
    )
    cv2.putText(
        annotated,
        status,
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return annotated


def _draw_box(frame: Any, box: BoundingBox, color: tuple[int, int, int], label: str) -> None:
    cv2.rectangle(
        frame,
        (int(box.x1), int(box.y1)),
        (int(box.x2), int(box.y2)),
        color,
        2,
    )
    cv2.putText(
        frame,
        label,
        (int(box.x1), max(20, int(box.y1) - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
        cv2.LINE_AA,
    )
