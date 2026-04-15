"""项目核心配置对象定义。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import SeatRegions

DEFAULT_TOUCH_ACTION_NAME = "touch_side_surface"
DEFAULT_LIFT_ACTION_NAME = "lift_seat_bottom"
DEFAULT_TOUCH_HOLD_FRAMES = 3
DEFAULT_LIFT_HOLD_FRAMES = 4
DEFAULT_TOUCH_WRIST_MARGIN = 30.0
DEFAULT_LIFT_WRIST_MARGIN = 40.0
DEFAULT_LIFT_RATIO_THRESHOLD = 0.10


@dataclass(slots=True)
class ActionConfig:
    """单个动作规则定义。"""

    name: str
    kind: str
    region: str
    hold_frames: int = 1
    wrist_margin: float | None = None
    min_wrist_count: int = 1
    lift_ratio_threshold: float | None = None
    enabled: bool = True


def build_default_rule_actions(
    touch_hold_frames: int = DEFAULT_TOUCH_HOLD_FRAMES,
    lift_hold_frames: int = DEFAULT_LIFT_HOLD_FRAMES,
    touch_wrist_margin: float = DEFAULT_TOUCH_WRIST_MARGIN,
    lift_wrist_margin: float = DEFAULT_LIFT_WRIST_MARGIN,
    lift_ratio_threshold: float = DEFAULT_LIFT_RATIO_THRESHOLD,
) -> list[ActionConfig]:
    """构建默认启用的两类基础动作。"""
    return [
        ActionConfig(
            name=DEFAULT_TOUCH_ACTION_NAME,
            kind="touch_region",
            region="side_surface",
            hold_frames=touch_hold_frames,
            wrist_margin=touch_wrist_margin,
            min_wrist_count=1,
        ),
        ActionConfig(
            name=DEFAULT_LIFT_ACTION_NAME,
            kind="lift_region",
            region="bottom_surface",
            hold_frames=lift_hold_frames,
            wrist_margin=lift_wrist_margin,
            min_wrist_count=2,
            lift_ratio_threshold=lift_ratio_threshold,
        ),
    ]


@dataclass(slots=True)
class KeypointProcessingConfig:
    """关键点时序处理配置。"""

    enabled: bool = True
    smoothing_window: int = 3
    interpolate_missing: bool = True
    max_missing_frames: int = 2
    min_confidence: float = 0.15


@dataclass(slots=True)
class WorkflowStepConfig:
    """状态机中的单个流程步骤配置。"""

    name: str
    action: str
    min_frames: int = 1


@dataclass(slots=True)
class StateMachineConfig:
    """动作流程状态机配置。"""

    enabled: bool = True
    steps: list[WorkflowStepConfig] = field(default_factory=list)
    require_all_steps: bool = True
    ok_label: str = "OK"
    ng_label: str = "NG"


@dataclass(slots=True)
class MultiCameraFusionConfig:
    """多相机动作融合配置。"""

    default_action_strategy: str = "any"
    touch_action_strategy: str = "any"
    lift_action_strategy: str = "any"
    time_tolerance_ms: float = 120.0


@dataclass(slots=True)
class RuleConfig:
    """动作规则配置。"""

    min_wrist_confidence: float = 0.3
    min_shoulder_confidence: float = 0.3
    min_hip_confidence: float = 0.3
    reach_ratio_threshold: float = 0.12
    max_action_gap_frames: int = 2
    actions: list[ActionConfig] = field(default_factory=build_default_rule_actions)


@dataclass(slots=True)
class CameraInferenceConfig:
    """多相机模式下的单路相机配置。"""

    name: str
    source: str
    seat_regions: SeatRegions
    pose_model_path: str | None = None
    person_model_path: str | None = None
    seat_model_path: str | None = None
    confidence: float | None = None
    iou: float | None = None
    device: str | None = None


@dataclass(slots=True)
class MultiCameraInferenceConfig:
    """多相机推理配置。"""

    pose_model_path: str
    cameras: list[CameraInferenceConfig]
    output_json_path: str = "outputs/multi_camera_action_results.json"
    output_video_path: str | None = None
    person_model_path: str | None = None
    seat_model_path: str | None = None
    confidence: float = 0.25
    iou: float = 0.45
    device: str = "cpu"
    save_visualization: bool = False
    show_window: bool = False
    window_name: str = "seat-inspection-multi"
    window_wait_ms: int = 1
    exit_key: str = "q"
    fusion: MultiCameraFusionConfig = field(default_factory=MultiCameraFusionConfig)
    keypoint_processing: KeypointProcessingConfig = field(default_factory=KeypointProcessingConfig)
    state_machine: StateMachineConfig = field(default_factory=StateMachineConfig)
