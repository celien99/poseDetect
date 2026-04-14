from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Point:
    """关键点坐标。"""
    x: float
    y: float
    confidence: float = 1.0


@dataclass(slots=True)
class BoundingBox:
    """边界框。"""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0


@dataclass(slots=True)
class SeatRegions:
    """座椅区域。"""
    overall: BoundingBox
    side_surface: BoundingBox
    bottom_surface: BoundingBox


@dataclass(slots=True)
class PoseSample:
    """人体关键点。"""
    left_shoulder: Point
    right_shoulder: Point
    left_wrist: Point
    right_wrist: Point
    left_hip: Point
    right_hip: Point


@dataclass(slots=True)
class FrameObservation:
    """单帧观测。"""
    frame_index: int
    seat_regions: SeatRegions
    pose: PoseSample


@dataclass(slots=True)
class ActionDecision:
    """动作决策。"""
    frame_index: int
    touch_side_surface: bool
    lift_seat_bottom: bool
    scores: dict[str, float] = field(default_factory=dict)
