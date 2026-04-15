"""YOLO pose 训练入口封装。"""

from __future__ import annotations

from ultralytics import YOLO

from .config import TrainingConfig

def train_pose_model(config: TrainingConfig) -> None:
    """按配置启动姿态模型训练。"""
    model = YOLO(config.model_path)
    model.train(
        data=config.data_config,
        epochs=config.epochs,
        imgsz=config.image_size,
        batch=config.batch,
        device=config.device,
        project=config.project,
        name=config.name,
    )
