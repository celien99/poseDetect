from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cv2

from mvsCamera import CameraLocator, CameraPropertyConfig, HikCamera, MvsCameraError

DEFAULT_TIMEOUT_MS = 1000
DEFAULT_OUTPUT_DIR = "outputs/mvs_camera_demo"
DEFAULT_WINDOW_NAME = "mvs-camera-demo"


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

    selector_group = parser.add_argument_group("camera selector")
    selector_mutex = selector_group.add_mutually_exclusive_group()
    selector_mutex.add_argument(
        "--index",
        type=int,
        help="Select camera by enumeration index. Defaults to 0 when no selector is given.",
    )
    selector_mutex.add_argument(
        "--serial-number",
        help="Select camera by serial number",
    )
    selector_mutex.add_argument(
        "--ip-address",
        help="Select camera by IP address",
    )
    selector_mutex.add_argument(
        "--mac-address",
        help="Select camera by MAC address",
    )

    parser.add_argument(
        "--trigger",
        choices=["continuous", "software"],
        default="continuous",
        help="Trigger mode to use when grabbing frames",
    )
    parser.add_argument(
        "--pixel-format",
        choices=["bgr8", "rgb8", "mono8"],
        default="bgr8",
        help="Preferred pixel format",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
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
        default=DEFAULT_OUTPUT_DIR,
        help="Directory used by preview mode when pressing 's' to save a photo",
    )
    parser.add_argument(
        "--save-prefix",
        default="capture",
        help="Filename prefix used for preview photo capture",
    )
    parser.add_argument(
        "--window-name",
        default=DEFAULT_WINDOW_NAME,
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
    parser.set_defaults(frame_rate_enable=None)

    parser.add_argument(
        "--width",
        type=int,
        help="ROI width",
    )
    parser.add_argument(
        "--height",
        type=int,
        help="ROI height",
    )
    parser.add_argument(
        "--offset-x",
        type=int,
        help="ROI X offset",
    )
    parser.add_argument(
        "--offset-y",
        type=int,
        help="ROI Y offset",
    )

    parser.add_argument(
        "--reverse-x",
        dest="reverse_x",
        action="store_true",
        help="Enable horizontal image reversal",
    )
    parser.add_argument(
        "--no-reverse-x",
        dest="reverse_x",
        action="store_false",
        help="Disable horizontal image reversal",
    )
    parser.add_argument(
        "--reverse-y",
        dest="reverse_y",
        action="store_true",
        help="Enable vertical image reversal",
    )
    parser.add_argument(
        "--no-reverse-y",
        dest="reverse_y",
        action="store_false",
        help="Disable vertical image reversal",
    )
    parser.set_defaults(reverse_x=None, reverse_y=None)
    return parser


def build_locator(args: argparse.Namespace) -> CameraLocator:
    """Build camera selector config from parsed args."""
    if args.serial_number:
        return CameraLocator(
            device_index=None,
            serial_number=args.serial_number,
        )
    if args.ip_address:
        return CameraLocator(
            device_index=None,
            ip_address=args.ip_address,
        )
    if args.mac_address:
        return CameraLocator(
            device_index=None,
            mac_address=args.mac_address,
        )
    return CameraLocator(device_index=0 if args.index is None else args.index)


def build_property_config(args: argparse.Namespace) -> CameraPropertyConfig:
    """Build camera property config from parsed args."""
    return CameraPropertyConfig(
        exposure_auto=args.exposure_auto,
        exposure_time_us=args.exposure_time_us,
        gain_auto=args.gain_auto,
        gain=args.gain,
        gamma=args.gamma,
        acquisition_frame_rate_enable=args.frame_rate_enable,
        acquisition_frame_rate=args.fps,
        width=args.width,
        height=args.height,
        offset_x=args.offset_x,
        offset_y=args.offset_y,
        reverse_x=args.reverse_x,
        reverse_y=args.reverse_y,
    )


def resolve_actions(args: argparse.Namespace) -> SimpleNamespace:
    """Normalize top-level actions so the demo has friendly defaults."""
    preview = bool(args.preview)
    if not args.list_devices and not args.capture and not preview:
        preview = True
    return SimpleNamespace(
        list_devices=bool(args.list_devices),
        capture_path=args.capture,
        preview=preview,
    )


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


def run_capture(args: argparse.Namespace, actions: SimpleNamespace) -> int:
    """Open one camera and run capture or preview actions."""
    camera = HikCamera(
        locator=build_locator(args),
        trigger_mode=args.trigger,
        pixel_format=args.pixel_format,
        property_config=build_property_config(args),
    )
    try:
        device_info = camera.open()
        camera.start_grabbing()
        print(f"Opened camera: {format_device_info(device_info)}")

        if args.show_nodes:
            print_camera_nodes(camera)

        if actions.capture_path:
            frame = capture_frame(camera, args.timeout_ms)
            output_path = save_frame(frame, actions.capture_path)
            print(f"Captured photo saved to: {output_path}")
            return 0

        if actions.preview:
            run_preview_loop(
                camera=camera,
                timeout_ms=args.timeout_ms,
                output_dir=args.output_dir,
                save_prefix=args.save_prefix,
                window_name=args.window_name,
            )
            return 0

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


def main() -> int:
    """CLI entry point for the standalone MVS demo."""
    parser = build_parser()
    args = parser.parse_args()
    actions = resolve_actions(args)

    if actions.list_devices:
        return list_devices()
    return run_capture(args, actions)


if __name__ == "__main__":
    raise SystemExit(main())
