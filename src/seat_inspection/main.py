from __future__ import annotations

import argparse

from seat_inspection.runtime_config import load_runtime_config


def build_parser() -> argparse.ArgumentParser:
    """构建仅保留多机位协同推理的 CLI。"""
    parser = argparse.ArgumentParser(
        description="Enterprise multi-camera seat inspection entry",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_setup_parser = subparsers.add_parser(
        "capture-setup",
        help="Capture one setup image from every configured camera",
    )
    capture_setup_parser.add_argument(
        "--config",
        default="configs/multi_camera_setup.example.json",
        help="Setup config JSON path",
    )
    capture_setup_parser.add_argument(
        "--output-dir",
        default="outputs/setup_capture",
        help="Directory to save captured setup images",
    )

    annotate_setup_parser = subparsers.add_parser(
        "annotate-setup",
        help="Annotate seat regions on captured setup images",
    )
    annotate_setup_parser.add_argument(
        "--capture-dir",
        default="outputs/setup_capture",
        help="Directory containing capture_manifest.json and captured images",
    )
    annotate_setup_parser.add_argument(
        "--output",
        default="outputs/setup_capture/seat_regions.annotations.json",
        help="Output JSON path for annotated seat regions",
    )

    apply_setup_parser = subparsers.add_parser(
        "apply-setup",
        help="Apply annotated seat regions back into a runtime config",
    )
    apply_setup_parser.add_argument(
        "--annotations",
        default="outputs/setup_capture/seat_regions.annotations.json",
        help="Annotation JSON path produced by annotate-setup",
    )
    apply_setup_parser.add_argument(
        "--runtime-config",
        default="configs/runtime.multi_camera.example.json",
        help="Runtime config JSON path to update",
    )
    apply_setup_parser.add_argument(
        "--output",
        help="Optional output config path. Defaults to in-place update.",
    )

    setup_seat_regions_parser = subparsers.add_parser(
        "setup-seat-regions",
        help="Capture, annotate, and write back seat regions in one guided flow",
    )
    setup_seat_regions_parser.add_argument(
        "--setup-config",
        default="configs/multi_camera_setup.example.json",
        help="Setup config JSON path",
    )
    setup_seat_regions_parser.add_argument(
        "--runtime-config",
        default="configs/runtime.multi_camera.example.json",
        help="Runtime config JSON path to update",
    )
    setup_seat_regions_parser.add_argument(
        "--capture-dir",
        default="outputs/setup_capture",
        help="Directory to save captured setup images",
    )
    setup_seat_regions_parser.add_argument(
        "--annotation-output",
        default="outputs/setup_capture/seat_regions.annotations.json",
        help="Output JSON path for annotated seat regions",
    )
    setup_seat_regions_parser.add_argument(
        "--output-runtime-config",
        help="Optional output config path. Defaults to in-place update.",
    )

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

    if args.command == "capture-setup":
        from seat_inspection.camera_setup import capture_multi_camera_snapshots

        summary = capture_multi_camera_snapshots(
            config_path=args.config,
            output_dir=args.output_dir,
        )
        print(
            f"Setup capture completed: {summary.success_count}/{len(summary.results)} cameras captured, "
            f"manifest saved to {summary.manifest_path}",
        )
        return

    if args.command == "annotate-setup":
        from seat_inspection.camera_setup import annotate_multi_camera_snapshots

        output_path = annotate_multi_camera_snapshots(
            capture_dir=args.capture_dir,
            output_path=args.output,
        )
        print(f"Seat region annotation completed: output saved to {output_path}")
        return

    if args.command == "apply-setup":
        from seat_inspection.camera_setup import apply_annotations_to_runtime_config

        output_path = apply_annotations_to_runtime_config(
            annotation_path=args.annotations,
            runtime_config_path=args.runtime_config,
            output_path=args.output,
        )
        print(f"Runtime config updated with seat regions: output saved to {output_path}")
        return

    if args.command == "setup-seat-regions":
        from seat_inspection.camera_setup import setup_seat_regions

        summary = setup_seat_regions(
            setup_config_path=args.setup_config,
            runtime_config_path=args.runtime_config,
            capture_dir=args.capture_dir,
            annotation_output_path=args.annotation_output,
            output_runtime_config_path=args.output_runtime_config,
        )
        print(
            "Seat region setup completed: "
            f"{summary.capture_summary.success_count}/{len(summary.capture_summary.results)} cameras captured, "
            f"annotations saved to {summary.annotation_path}, "
            f"runtime config saved to {summary.runtime_config_output_path}",
        )
        return

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
