from __future__ import annotations

import argparse

import numpy as np

from seat_inspection.mvs_camera_demo import (
    build_locator,
    build_property_config,
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
