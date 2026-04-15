from __future__ import annotations

import argparse

from seat_inspection.runtime_config import load_runtime_config


def build_parser() -> argparse.ArgumentParser:
    """构建项目统一 CLI，覆盖训练、采集、视频推理和图片推理。"""
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

    calibrate_parser = subparsers.add_parser(
        "calibrate-regions",
        help="Interactively calibrate seat regions from one image/video/camera source",
    )
    calibrate_parser.add_argument(
        "--source",
        required=True,
        help="Calibration source: image path, video path, camera index, or mvs:// source",
    )
    calibrate_parser.add_argument(
        "--output",
        help="Optional JSON output path. Prints JSON to stdout when omitted.",
    )
    calibrate_parser.add_argument(
        "--window-name",
        default="seat-region-calibration",
        help="OpenCV calibration window name",
    )

    infer_parser = subparsers.add_parser("infer", help="Run video inference and export JSON")
    infer_parser.add_argument(
        "--config",
        default="configs/runtime.example.json",
        help="Runtime config JSON path",
    )

    infer_multi_parser = subparsers.add_parser(
        "infer-multi",
        help="Run multi-camera inference and export fused JSON",
    )
    infer_multi_parser.add_argument(
        "--config",
        default="configs/runtime.multi_camera.example.json",
        help="Runtime config JSON path",
    )

    infer_image_parser = subparsers.add_parser(
        "infer-image",
        help="Run single-image inference and export JSON",
    )
    infer_image_parser.add_argument(
        "--config",
        default="configs/runtime.example.json",
        help="Runtime config JSON path",
    )
    return parser



def main() -> None:
    """CLI 主入口。"""
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

    if args.command == "calibrate-regions":
        from seat_inspection.calibration import calibrate_seat_regions

        calibrate_seat_regions(
            source=args.source,
            output_path=args.output,
            window_name=args.window_name,
        )
        if args.output:
            print(f"Seat regions calibration saved to {args.output}")
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

    if args.command == "infer-multi":
        from seat_inspection.inference import run_multi_camera_inference

        if runtime_config.multi_camera_inference is None:
            raise ValueError("Multi-camera inference config is missing in runtime config file")
        decisions = run_multi_camera_inference(
            runtime_config.multi_camera_inference,
            runtime_config.rules,
        )
        print(
            f"Multi-camera inference completed: {len(decisions)} fused frames processed, "
            f"report saved to {runtime_config.multi_camera_inference.output_json_path}",
        )
        return

    if args.command == "infer-image":
        from seat_inspection.inference import run_image_inference

        if runtime_config.image_inference is None:
            raise ValueError("Image inference config is missing in runtime config file")
        decision = run_image_inference(runtime_config.image_inference, runtime_config.rules)
        print(
            f"Image inference completed: actions={decision.actions}, "
            f"report saved to {runtime_config.image_inference.output_json_path}",
        )
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
