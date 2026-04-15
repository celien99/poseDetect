"""项目核心配置对象定义。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import SeatRegions


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
class TrainingConfig:
    """训练配置。

    备注：
    - `model_path` 指向 YOLO pose 权重或模型配置文件。
    - `data_config` 指向数据集 YAML，建议使用企业内部版本化配置。
    - `project` 与 `name` 共同决定训练输出目录，便于区分实验批次。
    - `device` 在生产训练环境中可配置为 `cuda:0` 等 GPU 设备。
    """

    model_path: str
    data_config: str
    epochs: int = 100
    image_size: int = 640
    batch: int = 16
    device: str = "cpu"
    project: str = "runs/seat_pose"
    name: str = "train"


@dataclass(slots=True)
class RuleConfig:
    """动作规则配置。

    备注：
    - `touch_hold_frames` 表示“触摸侧面”动作需要连续满足的帧数。
    - `lift_hold_frames` 表示“抬起底部”动作需要连续满足的帧数。
    - `wrist_to_surface_margin` 与 `wrist_to_bottom_margin` 用于容忍关键点抖动。
    - 各类 `min_*_confidence` 用于过滤低质量姿态点。
    - `lift_ratio_threshold` 建议结合真实产线视频反复标定。
    """

    touch_hold_frames: int = 3
    lift_hold_frames: int = 4
    wrist_to_surface_margin: float = 30.0
    wrist_to_bottom_margin: float = 40.0
    min_wrist_confidence: float = 0.3
    min_shoulder_confidence: float = 0.3
    min_hip_confidence: float = 0.3
    reach_ratio_threshold: float = 0.12
    lift_ratio_threshold: float = 0.10
    max_action_gap_frames: int = 2
    actions: list[ActionConfig] = field(default_factory=list)


@dataclass(slots=True)
class InferenceConfig:
    """推理配置。

    备注：
    - `pose_model_path` 为姿态模型路径。
    - `person_model_path` 可选，用于独立人体检测；为空时复用姿态结果中的人体框。
    - `source` 可为视频文件、摄像头编号或流媒体地址。
    - `seat_regions` 用于固定机位下的区域标定，是工业场景的核心输入。
    - `output_json_path` 用于输出动作结果，便于 MES/质检系统集成。
    - `output_video_path` 可用于导出带标注视频，辅助现场联调和问题复盘。
    - `seat_model_path` 预留给座椅区域检测模型，当前默认仍走固定 ROI。
    - `save_visualization` 为 `True` 时才会尝试生成可视化视频。
    """

    pose_model_path: str
    source: str
    seat_regions: SeatRegions
    output_json_path: str = "outputs/action_results.json"
    output_video_path: str | None = None
    person_model_path: str | None = None
    seat_model_path: str | None = None
    confidence: float = 0.25
    iou: float = 0.45
    device: str = "cpu"
    save_visualization: bool = False
    keypoint_processing: KeypointProcessingConfig = field(default_factory=KeypointProcessingConfig)
    state_machine: StateMachineConfig = field(default_factory=StateMachineConfig)


@dataclass(slots=True)
class ImageInferenceConfig:
    """单张图片推理配置。"""

    pose_model_path: str
    source: str
    seat_regions: SeatRegions
    output_json_path: str = "outputs/image_action_result.json"
    output_image_path: str | None = None
    person_model_path: str | None = None
    seat_model_path: str | None = None
    confidence: float = 0.25
    iou: float = 0.45
    device: str = "cpu"
    save_visualization: bool = True
    keypoint_processing: KeypointProcessingConfig = field(default_factory=KeypointProcessingConfig)
    state_machine: StateMachineConfig = field(default_factory=StateMachineConfig)


@dataclass(slots=True)
class CollectionConfig:
    """数据采集配置。

    备注：
    - `pose_model_path` 用于对采集帧做自动姿态伪标注，生成可直接训练的 YOLO pose 标签。
    - `source` 支持视频文件、普通摄像头编号以及 `mvs://0` 这类海康工业相机源。
    - `output_dir` 会生成 `images/train|val`、`labels/train|val` 和 `dataset.yaml`。
    - `save_every_n_frames` 用于抽帧，避免连续帧过于相似。
    - `max_images` 控制本次采集的最大图片数量，便于先跑通闭环。
    - `overwrite` 为 `True` 时允许覆盖已存在的数据集目录。
    """

    pose_model_path: str
    source: str
    output_dir: str = "datasets/seat_pose"
    dataset_yaml_path: str | None = None
    confidence: float = 0.25
    iou: float = 0.45
    device: str = "cpu"
    save_every_n_frames: int = 15
    max_images: int = 200
    train_split: float = 0.8
    random_seed: int = 42
    overwrite: bool = False
