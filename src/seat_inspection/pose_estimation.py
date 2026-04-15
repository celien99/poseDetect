"""姿态检测层。"""

from __future__ import annotations

from typing import Any

from .schemas import BoundingBox, FrameObservation, Point, PoseSample, SeatRegions
from .selection import select_primary_box_index

COCO_KEYPOINT_INDEX = {
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_wrist": 9,
    "right_wrist": 10,
    "left_hip": 11,
    "right_hip": 12,
}


class PoseEstimator:
    """YOLO Pose 估计器。"""

    def __init__(self, model_path: str) -> None:
        from ultralytics import YOLO

        self.model_path = model_path
        self._model = YOLO(model_path)

    def predict(
        self,
        frame: Any,
        confidence: float,
        iou: float,
        device: str,
    ) -> Any:
        """返回 YOLO Pose 原始结果。"""
        return self._model.predict(
            frame,
            conf=confidence,
            iou=iou,
            device=device,
            verbose=False,
        )[0]


def build_observation_from_pose_result(
    frame_index: int,
    result: Any,
    seat_regions: SeatRegions,
) -> FrameObservation | None:
    """从姿态模型结果构建动作引擎所需观测对象。"""
    pose = extract_primary_pose(result, reference_box=seat_regions.overall)
    if pose is None:
        return None

    return FrameObservation(
        frame_index=frame_index,
        seat_regions=seat_regions,
        pose=pose,
    )


def extract_primary_pose(
    result: Any,
    reference_box: BoundingBox | None = None,
) -> PoseSample | None:
    """选取置信度最高的人体姿态结果。"""
    keypoints = getattr(result, "keypoints", None)
    if keypoints is None or keypoints.data is None:
        return None

    keypoint_data = keypoints.data.cpu().numpy()
    if len(keypoint_data) == 0:
        return None

    boxes = getattr(result, "boxes", None)
    selected_index = 0
    if boxes is not None and getattr(boxes, "xyxy", None) is not None:
        confidences = boxes.conf.cpu().numpy() if boxes.conf is not None else None
        selected_index = select_primary_box_index(
            boxes.xyxy.cpu().numpy(),
            confidences,
            reference_box=reference_box,
        )

    pose_data = keypoint_data[selected_index]
    return PoseSample(
        left_shoulder=point_from_pose(pose_data, COCO_KEYPOINT_INDEX["left_shoulder"]),
        right_shoulder=point_from_pose(pose_data, COCO_KEYPOINT_INDEX["right_shoulder"]),
        left_wrist=point_from_pose(pose_data, COCO_KEYPOINT_INDEX["left_wrist"]),
        right_wrist=point_from_pose(pose_data, COCO_KEYPOINT_INDEX["right_wrist"]),
        left_hip=point_from_pose(pose_data, COCO_KEYPOINT_INDEX["left_hip"]),
        right_hip=point_from_pose(pose_data, COCO_KEYPOINT_INDEX["right_hip"]),
    )


def point_from_pose(pose_data: Any, index: int) -> Point:
    """从关键点数组中提取单个关键点。"""
    x, y, confidence = pose_data[index]
    return Point(float(x), float(y), float(confidence))
