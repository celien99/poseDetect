"""主操作者跟踪与跨机位关联。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import BoundingBox, PersonDetection


@dataclass(slots=True)
class OperatorTrackAssignment:
    """单路相机上的主操作者轨迹分配结果。"""

    camera_name: str
    track_id: str
    bounding_box: BoundingBox
    confidence: float
    frame_index: int


@dataclass(slots=True)
class OperatorAssociation:
    """跨机位主操作者关联结果。"""

    association_id: str | None
    camera_track_ids: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class _TrackedOperator:
    track_id: str
    bounding_box: BoundingBox
    last_frame_index: int
    missing_frames: int = 0


class PrimaryOperatorTracker:
    """单路相机上的轻量主操作者跟踪器。"""

    def __init__(
        self,
        camera_name: str,
        max_missing_frames: int = 5,
        min_iou_for_same_track: float = 0.1,
    ) -> None:
        self.camera_name = camera_name
        self.max_missing_frames = max(0, max_missing_frames)
        self.min_iou_for_same_track = max(0.0, min_iou_for_same_track)
        self._next_track_index = 1
        self._current_track: _TrackedOperator | None = None

    def update(
        self,
        frame_index: int,
        detection: PersonDetection | None,
    ) -> OperatorTrackAssignment | None:
        """更新单路主操作者轨迹。"""
        if detection is None:
            self._handle_missing()
            return None

        if self._current_track is None or not self._is_same_track(detection.bounding_box):
            self._current_track = _TrackedOperator(
                track_id=f"{self.camera_name}-{self._next_track_index}",
                bounding_box=detection.bounding_box,
                last_frame_index=frame_index,
                missing_frames=0,
            )
            self._next_track_index += 1
        else:
            self._current_track.bounding_box = detection.bounding_box
            self._current_track.last_frame_index = frame_index
            self._current_track.missing_frames = 0

        detection.track_id = self._current_track.track_id
        return OperatorTrackAssignment(
            camera_name=self.camera_name,
            track_id=self._current_track.track_id,
            bounding_box=detection.bounding_box,
            confidence=detection.confidence,
            frame_index=frame_index,
        )

    def _handle_missing(self) -> None:
        if self._current_track is None:
            return
        self._current_track.missing_frames += 1
        if self._current_track.missing_frames > self.max_missing_frames:
            self._current_track = None

    def _is_same_track(self, candidate_box: BoundingBox) -> bool:
        if self._current_track is None:
            return False
        return intersection_over_union(
            self._current_track.bounding_box,
            candidate_box,
        ) >= self.min_iou_for_same_track


class MultiCameraOperatorAssociator:
    """把多路主操作者轨迹关联为统一的跨机位主操作者。"""

    def __init__(self, max_idle_cycles: int = 10) -> None:
        self.max_idle_cycles = max(0, max_idle_cycles)
        self._next_association_index = 1
        self._current_association_id: str | None = None
        self._idle_cycles = 0

    def update(
        self,
        assignments: list[OperatorTrackAssignment],
    ) -> OperatorAssociation:
        """更新跨机位主操作者关联状态。"""
        if not assignments:
            self._idle_cycles += 1
            if self._idle_cycles > self.max_idle_cycles:
                self._current_association_id = None
            return OperatorAssociation(association_id=self._current_association_id)

        if self._current_association_id is None:
            self._current_association_id = f"operator-{self._next_association_index}"
            self._next_association_index += 1

        self._idle_cycles = 0
        return OperatorAssociation(
            association_id=self._current_association_id,
            camera_track_ids={
                assignment.camera_name: assignment.track_id
                for assignment in assignments
            },
        )


def intersection_over_union(first: BoundingBox, second: BoundingBox) -> float:
    """计算两个框的 IoU。"""
    intersection_width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    intersection_height = max(0.0, min(first.y2, second.y2) - max(first.y1, second.y1))
    intersection_area = intersection_width * intersection_height
    if intersection_area <= 0:
        return 0.0

    first_area = max(1.0, first.width * first.height)
    second_area = max(1.0, second.width * second.height)
    union = first_area + second_area - intersection_area
    return intersection_area / max(1.0, union)
