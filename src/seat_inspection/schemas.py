from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Point:
    """单个姿态关键点坐标与置信度。"""

    x: float
    y: float
    confidence: float = 1.0


@dataclass(slots=True)
class BoundingBox:
    """矩形区域定义，通常用于座椅标定框。"""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        """返回矩形宽度，保证不会出现负值。"""
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        """返回矩形高度，保证不会出现负值。"""
        return max(0.0, self.y2 - self.y1)

    @property
    def center_x(self) -> float:
        """返回矩形中心点横坐标。"""
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        """返回矩形中心点纵坐标。"""
        return (self.y1 + self.y2) / 2.0


@dataclass(slots=True)
class SeatRegions:
    """固定机位下的座椅区域标定结果。"""

    overall: BoundingBox
    side_surface: BoundingBox
    bottom_surface: BoundingBox


@dataclass(slots=True)
class PoseSample:
    """动作判断当前依赖的人体关键点集合。"""

    left_shoulder: Point
    right_shoulder: Point
    left_wrist: Point
    right_wrist: Point
    left_hip: Point
    right_hip: Point


@dataclass(slots=True)
class FrameObservation:
    """单帧输入在规则引擎中的标准表示。"""

    frame_index: int
    seat_regions: SeatRegions
    pose: PoseSample


@dataclass(slots=True)
class PersonDetection:
    """单人目标检测结果。"""

    bounding_box: BoundingBox
    confidence: float
    track_id: str | None = None


@dataclass(slots=True)
class ActionDecision:
    """单帧动作判定结果。"""

    frame_index: int
    actions: dict[str, bool] = field(default_factory=dict)  # 通用动作名到判定状态的映射
    scores: dict[str, float] = field(default_factory=dict)  # 通用动作名到置信分数的映射
    reasons: dict[str, str] = field(default_factory=dict)  # 通用动作名到当前判定原因的映射
    diagnostics: dict[str, dict[str, float | int | bool | str]] = field(default_factory=dict)
    # 通用动作名到诊断特征的映射
    operator_track_ids: dict[str, str] = field(default_factory=dict)
    operator_association_id: str | None = None
    active_cameras: list[str] = field(default_factory=list)

    @property
    def touch_side_surface(self) -> bool:
        """兼容旧访问方式，内部统一委托到通用动作字典。"""
        return self.actions.get("touch_side_surface", False)

    @property
    def lift_seat_bottom(self) -> bool:
        """兼容旧访问方式，内部统一委托到通用动作字典。"""
        return self.actions.get("lift_seat_bottom", False)


@dataclass(slots=True)
class WorkflowEvent:
    """流程状态机输出的事件日志。"""

    frame_index: int
    event_type: str
    message: str


@dataclass(slots=True)
class WorkflowStepState:
    """流程中的单个步骤执行状态。"""

    name: str
    action: str
    completed: bool = False
    completed_frame: int | None = None


@dataclass(slots=True)
class InspectionResult:
    """整段视频或一次图片判断的最终检测结果。"""

    status: str
    current_state: str
    current_step: str | None = None
    completed_steps: list[str] = field(default_factory=list)
    step_states: list[WorkflowStepState] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)
