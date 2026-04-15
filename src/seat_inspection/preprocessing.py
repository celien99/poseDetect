"""关键点时序处理层。

职责：
- 对 YOLO Pose 输出的关键点做轻量平滑
- 对短时间缺失的关键点做补帧
- 为后续动作规则提供更稳定的观测输入
"""

from __future__ import annotations

from collections import deque

from .config import KeypointProcessingConfig
from .schemas import Point, PoseSample

POSE_POINT_NAMES = (
    "left_shoulder",
    "right_shoulder",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
)


class KeypointSequenceProcessor:
    """对关键点序列做平滑和短时补帧。"""

    def __init__(self, config: KeypointProcessingConfig | None = None) -> None:
        self.config = config or KeypointProcessingConfig()
        self._history: deque[PoseSample] = deque(maxlen=max(1, self.config.smoothing_window))
        self._last_valid_points: dict[str, Point] = {}
        self._missing_counts: dict[str, int] = {name: 0 for name in POSE_POINT_NAMES}

    def reset(self) -> None:
        """清空时序状态。"""
        self._history.clear()
        self._last_valid_points.clear()
        self._missing_counts = {name: 0 for name in POSE_POINT_NAMES}

    def process(self, pose: PoseSample) -> PoseSample:
        """处理当前帧关键点并返回平滑后的姿态结果。"""
        if not self.config.enabled:
            return pose

        repaired = {
            name: self._repair_point(name, getattr(pose, name))
            for name in POSE_POINT_NAMES
        }
        repaired_pose = PoseSample(**repaired)
        self._history.append(repaired_pose)
        return PoseSample(
            **{
                name: self._smooth_point(name)
                for name in POSE_POINT_NAMES
            },
        )

    def _repair_point(self, name: str, point: Point) -> Point:
        if point.confidence >= self.config.min_confidence:
            self._last_valid_points[name] = point
            self._missing_counts[name] = 0
            return point

        self._missing_counts[name] += 1
        if (
            self.config.interpolate_missing
            and name in self._last_valid_points
            and self._missing_counts[name] <= self.config.max_missing_frames
        ):
            previous = self._last_valid_points[name]
            return Point(previous.x, previous.y, previous.confidence)
        return point

    def _smooth_point(self, name: str) -> Point:
        points = [getattr(pose, name) for pose in self._history]
        valid_points = [point for point in points if point.confidence > 0]
        if not valid_points:
            return getattr(self._history[-1], name)
        return Point(
            x=sum(point.x for point in valid_points) / len(valid_points),
            y=sum(point.y for point in valid_points) / len(valid_points),
            confidence=sum(point.confidence for point in valid_points) / len(valid_points),
        )
