"""座椅动作检测包导出入口。"""

from .config import (
    ActionConfig,
    CameraInferenceConfig,
    KeypointProcessingConfig,
    MultiCameraFusionConfig,
    MultiCameraInferenceConfig,
    RuleConfig,
    StateMachineConfig,
    WorkflowStepConfig,
)
from .camera_setup import (
    annotate_multi_camera_snapshots,
    apply_annotations_to_runtime_config,
    capture_multi_camera_snapshots,
    setup_seat_regions,
)
from .engine import ActionRecognitionEngine
from .pipeline import InspectionPipeline
from .pose_estimation import PoseEstimator
from .runtime_config import RuntimeConfigBundle, load_runtime_config

__all__ = [
    "ActionRecognitionEngine",
    "ActionConfig",
    "annotate_multi_camera_snapshots",
    "apply_annotations_to_runtime_config",
    "CameraInferenceConfig",
    "capture_multi_camera_snapshots",
    "InspectionPipeline",
    "KeypointProcessingConfig",
    "MultiCameraFusionConfig",
    "MultiCameraInferenceConfig",
    "PoseEstimator",
    "RuleConfig",
    "RuntimeConfigBundle",
    "setup_seat_regions",
    "StateMachineConfig",
    "WorkflowStepConfig",
    "load_runtime_config",
]
