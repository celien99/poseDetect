from __future__ import annotations

import argparse

from seat_inspection.runtime_config import load_runtime_config


def build_parser() -> argparse.ArgumentParser:
    """构建仅保留多机位协同推理的 CLI。"""
    parser = argparse.ArgumentParser(
        description="Enterprise multi-camera seat inspection entry",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    infer_parser = subparsers.add_parser(
        "infer",
        help="Run collaborative multi-camera inference and export fused JSON",
    )
    infer_parser.add_argument(
        "--config",
        default="configs/runtime.multi_camera.example.json",
        help="Runtime config JSON path",
    )

    return parser



def main() -> None:
    """CLI 主入口。"""
    parser = build_parser()
    args = parser.parse_args()

    runtime_config = load_runtime_config(args.config)

    if args.command == "infer":
        from seat_inspection.inference import run_multi_camera_inference

        if runtime_config.multi_camera_inference is None:
            raise ValueError("Multi-camera inference config is missing in runtime config file")
        decisions = run_multi_camera_inference(
            runtime_config.multi_camera_inference,
            runtime_config.rules,
        )
        print(
            f"Inference completed: {len(decisions)} fused frames processed, "
            f"report saved to {runtime_config.multi_camera_inference.output_json_path}",
        )
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
