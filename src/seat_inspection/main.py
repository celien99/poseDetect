from __future__ import annotations

import argparse

from seat_inspection.runtime_config import load_runtime_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enterprise seat inspection training and inference entry",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Train YOLO pose model")
    train_parser.add_argument(
        "--config",
        default="configs/runtime.example.json",
        help="Runtime config JSON path",
    )

    collect_parser = subparsers.add_parser(
        "collect",
        help="Capture frames and auto-build a YOLO pose dataset",
    )
    collect_parser.add_argument(
        "--config",
        default="configs/runtime.example.json",
        help="Runtime config JSON path",
    )

    infer_parser = subparsers.add_parser("infer", help="Run video inference and export JSON")
    infer_parser.add_argument(
        "--config",
        default="configs/runtime.example.json",
        help="Runtime config JSON path",
    )
    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    runtime_config = load_runtime_config(args.config)

    if args.command == "train":
        from seat_inspection.training import train_pose_model

        if runtime_config.training is None:
            raise ValueError("Training config is missing in runtime config file")
        train_pose_model(runtime_config.training)
        return

    if args.command == "collect":
        from seat_inspection.dataset_capture import capture_pose_dataset

        if runtime_config.collection is None:
            raise ValueError("Collection config is missing in runtime config file")
        summary = capture_pose_dataset(runtime_config.collection)
        print(
            f"Dataset capture completed: {summary.saved_images} images saved "
            f"({summary.train_images} train / {summary.val_images} val), "
            f"dataset yaml: {summary.dataset_yaml_path}",
        )
        return

    if args.command == "infer":
        from seat_inspection.inference import run_video_inference

        if runtime_config.inference is None:
            raise ValueError("Inference config is missing in runtime config file")
        decisions = run_video_inference(runtime_config.inference, runtime_config.rules)
        print(
            f"Inference completed: {len(decisions)} frames processed, "
            f"report saved to {runtime_config.inference.output_json_path}",
        )
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
