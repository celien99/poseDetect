from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from mvsCamera import (
    CameraLocator,
    CameraPropertyConfig,
    HikCamera,
    MvsCameraError,
    parse_mvs_source,
)

DEFAULT_TIMEOUT_MS = 1000
DEFAULT_OUTPUT_DIR = "outputs/mvs_camera_demo"
DEFAULT_WINDOW_NAME = "mvs-camera-demo"
DEFAULT_SAVE_PREFIX = "capture"
CLI_PROPERTY_FIELDS = {
    "exposure_auto": "exposure_auto",
    "exposure_time_us": "exposure_time_us",
    "gain_auto": "gain_auto",
    "gain": "gain",
    "gamma": "gamma",
    "frame_rate_enable": "acquisition_frame_rate_enable",
    "fps": "acquisition_frame_rate",
    "width": "width",
    "height": "height",
    "offset_x": "offset_x",
    "offset_y": "offset_y",
    "reverse_x": "reverse_x",
    "reverse_y": "reverse_y",
}


@dataclass(slots=True)
class DemoRunSettings:
    """Resolved settings used by the standalone MVS demo."""

    locator: CameraLocator
    property_config: CameraPropertyConfig
    trigger_mode: str = "continuous"
    pixel_format: str = "bgr8"
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    output_dir: str = DEFAULT_OUTPUT_DIR
    save_prefix: str = DEFAULT_SAVE_PREFIX
    window_name: str = DEFAULT_WINDOW_NAME
    show_nodes: bool = False
    preview: bool = False
    capture_path: str | None = None


def build_parser() -> argparse.ArgumentParser:
    """Build a standalone CLI for MVS camera control only."""
    parser = argparse.ArgumentParser(
        description="Standalone MVS camera demo for parameter control and photo capture",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List visible MVS cameras and exit",
    )
    parser.add_argument(
        "--config",
        help=(
            "Load camera settings from a JSON file. Supports existing runtime config files "
            "with multi_camera_inference.cameras, or a lightweight demo config with mvs_camera_demo.source."
        ),
    )
    parser.add_argument(
        "--camera-name",
        help="When --config points to a multi-camera runtime config, select one camera by name",
    )

    selector_group = parser.add_argument_group("camera selector")
    selector_mutex = selector_group.add_mutually_exclusive_group()
    for option, kwargs in (
        (
            "--index",
            {
                "type": int,
                "help": "Select camera by enumeration index. Defaults to 0 when no selector is given.",
            },
        ),
        ("--serial-number", {"help": "Select camera by serial number"}),
        ("--ip-address", {"help": "Select camera by IP address"}),
        ("--mac-address", {"help": "Select camera by MAC address"}),
    ):
        selector_mutex.add_argument(option, **kwargs)

    parser.add_argument(
        "--trigger",
        choices=["continuous", "software"],
        help="Trigger mode to use when grabbing frames",
    )
    parser.add_argument(
        "--pixel-format",
        choices=["bgr8", "rgb8", "mono8"],
        help="Preferred pixel format",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        help="Frame grab timeout in milliseconds",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Open a live preview window. If no action is provided, preview is enabled by default.",
    )
    parser.add_argument(
        "--capture",
        help="Capture one frame to the given image path and exit",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory used by preview mode when pressing 's' to save a photo",
    )
    parser.add_argument(
        "--save-prefix",
        help="Filename prefix used for preview photo capture",
    )
    parser.add_argument(
        "--window-name",
        help="Preview window title",
    )
    parser.add_argument(
        "--show-nodes",
        action="store_true",
        help="Print common camera node values after opening the camera",
    )

    parser.add_argument(
        "--exposure-auto",
        choices=["off", "once", "continuous"],
        help="Exposure auto mode",
    )
    parser.add_argument(
        "--exposure-time-us",
        type=float,
        help="Exposure time in microseconds",
    )
    parser.add_argument(
        "--gain-auto",
        choices=["off", "once", "continuous"],
        help="Gain auto mode",
    )
    parser.add_argument(
        "--gain",
        type=float,
        help="Analog gain value",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        help="Gamma value",
    )
    parser.add_argument(
        "--fps",
        type=float,
        help="Acquisition frame rate",
    )
    parser.add_argument(
        "--frame-rate-enable",
        dest="frame_rate_enable",
        action="store_true",
        help="Enable manual frame rate control",
    )
    parser.add_argument(
        "--disable-frame-rate",
        dest="frame_rate_enable",
        action="store_false",
        help="Disable manual frame rate control",
    )

    for option, help_text in (
        ("--width", "ROI width"),
        ("--height", "ROI height"),
        ("--offset-x", "ROI X offset"),
        ("--offset-y", "ROI Y offset"),
    ):
        parser.add_argument(option, type=int, help=help_text)

    for axis, label in (("x", "horizontal"), ("y", "vertical")):
        parser.add_argument(
            f"--reverse-{axis}",
            dest=f"reverse_{axis}",
            action="store_true",
            help=f"Enable {label} image reversal",
        )
        parser.add_argument(
            f"--no-reverse-{axis}",
            dest=f"reverse_{axis}",
            action="store_false",
            help=f"Disable {label} image reversal",
        )

    parser.set_defaults(frame_rate_enable=None, reverse_x=None, reverse_y=None)
    return parser


def format_device_info(device: Any) -> str:
    """Format one enumerated camera into a single readable line."""
    parts = [
        f"index={device.index}",
        f"model={device.model_name or '-'}",
        f"sn={device.serial_number or '-'}",
        f"ip={device.ip_address or '-'}",
        f"mac={device.mac_address or '-'}",
    ]
    if device.user_defined_name:
        parts.append(f"name={device.user_defined_name}")
    return ", ".join(parts)


def print_camera_nodes(camera: HikCamera) -> None:
    """Print commonly used node values and ranges when supported."""
    print("Camera node summary:")
    for node_name in ("ExposureTime", "Gain", "AcquisitionFrameRate"):
        print(f"  {node_name}: {describe_node(camera, node_name, is_float=True)}")
    for node_name in ("Width", "Height", "OffsetX", "OffsetY"):
        print(f"  {node_name}: {describe_node(camera, node_name, is_float=False)}")


def describe_node(camera: HikCamera, node_name: str, *, is_float: bool) -> str:
    """Describe one node safely, even when a model does not support it."""
    try:
        if is_float:
            value = camera.get_float_node(node_name)
        else:
            value = camera.get_int_node(node_name)
    except MvsCameraError as exc:
        return f"unsupported ({exc})"
    return ", ".join(f"{key}={val}" for key, val in value.items())


def capture_frame(camera: HikCamera, timeout_ms: int) -> Any:
    """Grab one frame or raise an error if no frame is returned."""
    frame = camera.get_frame(timeout_ms=timeout_ms)
    if frame is None:
        raise RuntimeError(f"Timed out waiting for a frame within {timeout_ms} ms")
    return frame


def save_frame(frame: Any, output_path: str | Path) -> Path:
    """Save one BGR frame to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(path), frame)
    if not success:
        raise RuntimeError(f"Failed to save image to {path}")
    return path


def load_settings_from_config(config_path: str, camera_name: str | None = None) -> DemoRunSettings:
    """Load demo settings from a JSON file."""
    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
    demo_payload = payload.get("mvs_camera_demo")
    if not isinstance(demo_payload, dict):
        demo_payload = payload if _looks_like_demo_payload(payload) else {}

    source = demo_payload.get("source")
    if source is None:
        source = _resolve_source_from_payload(
            payload,
            camera_name or demo_payload.get("camera_name"),
        )

    source_config = parse_mvs_source(source)
    return DemoRunSettings(
        locator=source_config.to_locator(),
        property_config=source_config.to_property_config(),
        trigger_mode=demo_payload.get("trigger", source_config.trigger_mode),
        pixel_format=demo_payload.get("pixel_format", source_config.pixel_format),
        timeout_ms=int(demo_payload.get("timeout_ms", source_config.grab_timeout_ms)),
        output_dir=demo_payload.get("output_dir", DEFAULT_OUTPUT_DIR),
        save_prefix=demo_payload.get("save_prefix", DEFAULT_SAVE_PREFIX),
        window_name=demo_payload.get("window_name", DEFAULT_WINDOW_NAME),
        show_nodes=bool(demo_payload.get("show_nodes", False)),
        preview=bool(demo_payload.get("preview", False)),
        capture_path=demo_payload.get("capture"),
    )


def merge_settings(args: argparse.Namespace, file_settings: DemoRunSettings | None) -> DemoRunSettings:
    """Merge CLI options on top of configuration-file settings."""
    base = file_settings or DemoRunSettings(
        locator=CameraLocator(),
        property_config=CameraPropertyConfig(),
    )
    capture_path = args.capture if args.capture is not None else base.capture_path
    preview = bool(args.preview or base.preview)
    if capture_path is None and not preview:
        preview = True

    locator_overrides = _selector_overrides_from_args(args)
    property_overrides = {
        target_name: value
        for arg_name, target_name in CLI_PROPERTY_FIELDS.items()
        if (value := getattr(args, arg_name)) is not None
    }
    return DemoRunSettings(
        locator=replace(base.locator, **locator_overrides) if locator_overrides else base.locator,
        property_config=(
            replace(base.property_config, **property_overrides)
            if property_overrides
            else base.property_config
        ),
        trigger_mode=args.trigger or base.trigger_mode,
        pixel_format=args.pixel_format or base.pixel_format,
        timeout_ms=base.timeout_ms if args.timeout_ms is None else args.timeout_ms,
        output_dir=args.output_dir or base.output_dir,
        save_prefix=args.save_prefix or base.save_prefix,
        window_name=args.window_name or base.window_name,
        show_nodes=bool(args.show_nodes or base.show_nodes),
        preview=preview,
        capture_path=capture_path,
    )


def _selector_overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Return locator overrides from CLI, clearing other selectors when needed."""
    if args.serial_number:
        return {
            "device_index": None,
            "serial_number": args.serial_number,
            "ip_address": None,
            "mac_address": None,
        }
    if args.ip_address:
        return {
            "device_index": None,
            "serial_number": None,
            "ip_address": args.ip_address,
            "mac_address": None,
        }
    if args.mac_address:
        return {
            "device_index": None,
            "serial_number": None,
            "ip_address": None,
            "mac_address": args.mac_address,
        }
    if args.index is not None:
        return {
            "device_index": args.index,
            "serial_number": None,
            "ip_address": None,
            "mac_address": None,
        }
    return {}


def _looks_like_demo_payload(payload: dict[str, Any]) -> bool:
    """Return whether a top-level JSON object already looks like a demo config."""
    return any(
        key in payload
        for key in (
            "source",
            "camera_name",
            "capture",
            "preview",
            "output_dir",
            "window_name",
        )
    )


def _resolve_source_from_payload(payload: dict[str, Any], camera_name: str | None) -> str:
    """Resolve one camera source string from a JSON payload."""
    if isinstance(payload.get("source"), str):
        return str(payload["source"])

    inference_payload = payload.get("multi_camera_inference")
    if isinstance(inference_payload, dict):
        cameras = inference_payload.get("cameras", [])
        if not isinstance(cameras, list) or not cameras:
            raise ValueError("No cameras were found under multi_camera_inference.cameras")

        if camera_name:
            for camera_payload in cameras:
                if isinstance(camera_payload, dict) and camera_payload.get("name") == camera_name:
                    source = camera_payload.get("source")
                    if not isinstance(source, str):
                        raise ValueError(f"Camera '{camera_name}' is missing a valid source string")
                    return source
            raise ValueError(f"Camera named '{camera_name}' was not found in the config file")

        first_camera = cameras[0]
        if not isinstance(first_camera, dict) or not isinstance(first_camera.get("source"), str):
            raise ValueError("The first camera entry is missing a valid source string")
        return str(first_camera["source"])

    raise ValueError("Unable to resolve a camera source from the config file")


def list_devices() -> int:
    """List visible MVS devices."""
    camera = HikCamera()
    try:
        devices = camera.enumerate_devices()
        if not devices:
            print("No MVS cameras were found.")
            return 0
        print("Visible MVS cameras:")
        for device in devices:
            print(f"  - {format_device_info(device)}")
        return 0
    finally:
        camera.close()


def run_capture(settings: DemoRunSettings) -> int:
    """Open one camera and run capture or preview actions."""
    camera = HikCamera(
        locator=settings.locator,
        trigger_mode=settings.trigger_mode,
        pixel_format=settings.pixel_format,
        property_config=settings.property_config,
    )
    try:
        device_info = camera.open()
        camera.start_grabbing()
        print(f"Opened camera: {format_device_info(device_info)}")

        if settings.show_nodes:
            print_camera_nodes(camera)

        if settings.capture_path:
            frame = capture_frame(camera, settings.timeout_ms)
            output_path = save_frame(frame, settings.capture_path)
            print(f"Captured photo saved to: {output_path}")
            return 0

        if settings.preview:
            run_preview_loop(
                camera=camera,
                timeout_ms=settings.timeout_ms,
                output_dir=settings.output_dir,
                save_prefix=settings.save_prefix,
                window_name=settings.window_name,
            )
        return 0
    finally:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
        camera.close()


def run_preview_loop(
    *,
    camera: HikCamera,
    timeout_ms: int,
    output_dir: str,
    save_prefix: str,
    window_name: str,
) -> None:
    """Show raw frames in a preview window and allow manual saving."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    print("Preview controls: press 's' to save a photo, 'q' or ESC to quit.")

    while True:
        frame = camera.get_frame(timeout_ms=timeout_ms)
        if frame is None:
            print(f"Frame timeout after {timeout_ms} ms, retrying...")
            continue

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break
        if key == ord("s"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = output_root / f"{save_prefix}_{timestamp}.png"
            save_frame(frame, output_path)
            print(f"Saved photo to: {output_path}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the standalone MVS demo."""
    parser = build_parser()
    args = parser.parse_args() if argv is None else parser.parse_args(list(argv))
    if args.list_devices:
        return list_devices()

    file_settings = load_settings_from_config(args.config, args.camera_name) if args.config else None
    settings = merge_settings(args, file_settings)
    return run_capture(settings)


if __name__ == "__main__":
    raise SystemExit(main())
