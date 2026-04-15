"""兼容早期训练脚本的轻量 CLI。"""

from __future__ import annotations

import argparse

from .config import TrainingConfig
from .training import train_pose_model


def build_parser() -> argparse.ArgumentParser:
    """构建仅包含训练能力的简化命令行入口。"""
    parser = argparse.ArgumentParser(description="Seat inspection pose training CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Train YOLO pose model")
    train_parser.add_argument("--model", required=True, help="YOLO model or weights path")
    train_parser.add_argument("--data", required=True, help="Dataset YAML path")
    train_parser.add_argument("--epochs", type=int, default=100)
    train_parser.add_argument("--imgsz", type=int, default=640)
    train_parser.add_argument("--batch", type=int, default=16)
    train_parser.add_argument("--device", default="cpu")
    train_parser.add_argument("--project", default="runs/seat_pose")
    train_parser.add_argument("--name", default="train")
    return parser


def main() -> None:
    """简化 CLI 主入口。"""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "train":
        config = TrainingConfig(
            model_path=args.model,
            data_config=args.data,
            epochs=args.epochs,
            image_size=args.imgsz,
            batch=args.batch,
            device=args.device,
            project=args.project,
            name=args.name,
        )
        train_pose_model(config)


if __name__ == "__main__":
    main()
