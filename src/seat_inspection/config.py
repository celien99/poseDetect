from __future__ import annotations

from dataclasses import dataclass

from .schemas import SeatRegions


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


@dataclass(slots=True)
class InferenceConfig:
    """推理配置。

    备注：
    - `pose_model_path` 为姿态模型路径。
    - `source` 可为视频文件、摄像头编号或流媒体地址。
    - `seat_regions` 用于固定机位下的区域标定，是工业场景的核心输入。
    - `output_json_path` 用于输出动作结果，便于 MES/质检系统集成。
    - `output_video_path` 可用于导出带标注视频，辅助现场联调和问题复盘。
    - `seat_model_path` 预留给座椅区域检测模型，当前可为空。
    - `save_visualization` 为 `True` 时才会尝试生成可视化视频。
    """

    pose_model_path: str
    source: str
    seat_regions: SeatRegions
    output_json_path: str = "outputs/action_results.json"
    output_video_path: str | None = None
    seat_model_path: str | None = None
    confidence: float = 0.25
    iou: float = 0.45
    device: str = "cpu"
    save_visualization: bool = False
