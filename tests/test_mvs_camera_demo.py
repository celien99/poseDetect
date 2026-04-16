from __future__ import annotations

import argparse
import json

import numpy as np

from seat_inspection.mvs_camera_demo import (
    build_locator,
    build_property_config,
    load_settings_from_config,
    merge_settings,
    resolve_actions,
    save_frame,
)


def test_build_locator_prefers_serial_number() -> None:
    locator = build_locator(
        argparse.Namespace(
            index=3,
            serial_number="DA9184658",
            ip_address=None,
            mac_address=None,
        ),
    )

    assert locator.device_index is None
    assert locator.serial_number == "DA9184658"


def test_build_locator_defaults_to_index_zero() -> None:
    locator = build_locator(
        argparse.Namespace(
            index=None,
            serial_number=None,
            ip_address=None,
            mac_address=None,
        ),
    )

    assert locator.device_index == 0


def test_build_property_config_maps_optional_values() -> None:
    config = build_property_config(
        argparse.Namespace(
            exposure_auto="off",
            exposure_time_us=6000.0,
            gain_auto="continuous",
            gain=8.5,
            gamma=0.7,
            frame_rate_enable=True,
            fps=12.5,
            width=1920,
            height=1080,
            offset_x=16,
            offset_y=24,
            reverse_x=False,
            reverse_y=True,
        ),
    )

    assert config.exposure_auto == "off"
    assert config.exposure_time_us == 6000.0
    assert config.gain_auto == "continuous"
    assert config.gain == 8.5
    assert config.gamma == 0.7
    assert config.acquisition_frame_rate_enable is True
    assert config.acquisition_frame_rate == 12.5
    assert config.width == 1920
    assert config.height == 1080
    assert config.offset_x == 16
    assert config.offset_y == 24
    assert config.reverse_x is False
    assert config.reverse_y is True


def test_resolve_actions_defaults_to_preview() -> None:
    actions = resolve_actions(
        argparse.Namespace(
            list_devices=False,
            capture=None,
            preview=False,
        ),
    )

    assert actions.list_devices is False
    assert actions.capture_path is None
    assert actions.preview is True


def test_save_frame_creates_output_file(tmp_path) -> None:
    frame = np.zeros((10, 12, 3), dtype=np.uint8)

    output_path = save_frame(frame, tmp_path / "captures" / "frame.png")

    assert output_path.exists()


def test_load_settings_from_runtime_config_payload(tmp_path) -> None:
    config_path = tmp_path / "runtime.json"
    config_path.write_text(
        json.dumps(
            {
                "multi_camera_inference": {
                    "cameras": [
                        {
                            "name": "cam_0",
                            "source": "mvs://sn/DA9184658?timeout_ms=1500&trigger=software&pixel_format=mono8&exposure_auto=off&exposure_time=7000&gain=4",
                        },
                        {
                            "name": "cam_1",
                            "source": "mvs://sn/DA9184675?timeout_ms=1000",
                        },
                    ],
                },
                "mvs_camera_demo": {
                    "camera_name": "cam_0",
                    "preview": True,
                    "show_nodes": True,
                    "output_dir": "outputs/custom_demo",
                },
            },
        ),
        encoding="utf-8",
    )

    settings = load_settings_from_config(str(config_path))

    assert settings.locator.serial_number == "DA9184658"
    assert settings.trigger_mode == "software"
    assert settings.pixel_format == "mono8"
    assert settings.timeout_ms == 1500
    assert settings.property_config.exposure_auto == "off"
    assert settings.property_config.exposure_time_us == 7000.0
    assert settings.property_config.gain == 4.0
    assert settings.preview is True
    assert settings.show_nodes is True
    assert settings.output_dir == "outputs/custom_demo"


def test_load_settings_from_direct_demo_source(tmp_path) -> None:
    config_path = tmp_path / "demo.json"
    config_path.write_text(
        json.dumps(
            {
                "mvs_camera_demo": {
                    "source": "mvs://ip/192.168.1.10?timeout_ms=800&trigger=continuous&pixel_format=bgr8&gain_auto=off&gain=8",
                    "capture": "outputs/demo/frame.png",
                },
            },
        ),
        encoding="utf-8",
    )

    settings = load_settings_from_config(str(config_path))

    assert settings.locator.ip_address == "192.168.1.10"
    assert settings.timeout_ms == 800
    assert settings.capture_path == "outputs/demo/frame.png"
    assert settings.property_config.gain_auto == "off"
    assert settings.property_config.gain == 8.0


def test_merge_settings_lets_cli_override_config_values() -> None:
    file_settings = load_settings_from_config_payload_for_merge()

    merged = merge_settings(
        argparse.Namespace(
            index=None,
            serial_number=None,
            ip_address=None,
            mac_address=None,
            exposure_auto=None,
            exposure_time_us=9000.0,
            gain_auto=None,
            gain=10.0,
            gamma=None,
            frame_rate_enable=None,
            fps=None,
            width=None,
            height=None,
            offset_x=None,
            offset_y=None,
            reverse_x=None,
            reverse_y=None,
            trigger=None,
            pixel_format=None,
            timeout_ms=None,
            output_dir=None,
            save_prefix=None,
            window_name=None,
            show_nodes=False,
            preview=False,
            capture=None,
        ),
        file_settings,
    )

    assert merged.property_config.exposure_time_us == 9000.0
    assert merged.property_config.gain == 10.0
    assert merged.locator.serial_number == "DA9184658"


def load_settings_from_config_payload_for_merge():
    return load_settings_from_config_payload(
        {
            "mvs_camera_demo": {
                "source": "mvs://sn/DA9184658?timeout_ms=1000&exposure_auto=off&exposure_time=5000&gain_auto=off&gain=6",
            },
        },
    )


def load_settings_from_config_payload(payload: dict):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        return load_settings_from_config(str(config_path))
