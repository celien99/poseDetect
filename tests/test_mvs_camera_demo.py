from __future__ import annotations

import json

import numpy as np

from seat_inspection.mvs_camera_demo import build_parser, load_settings_from_config, main, merge_settings, save_frame


def parse_args(*argv: str):
    return build_parser().parse_args(list(argv))


def test_merge_settings_builds_locator_from_serial_number() -> None:
    settings = merge_settings(
        parse_args("--serial-number", "DA9184658"),
        None,
    )

    assert settings.locator.device_index is None
    assert settings.locator.serial_number == "DA9184658"


def test_merge_settings_defaults_to_index_zero_and_preview() -> None:
    settings = merge_settings(parse_args(), None)

    assert settings.locator.device_index == 0
    assert settings.preview is True
    assert settings.capture_path is None


def test_merge_settings_maps_optional_property_values() -> None:
    settings = merge_settings(
        parse_args(
            "--exposure-auto",
            "off",
            "--exposure-time-us",
            "6000",
            "--gain-auto",
            "continuous",
            "--gain",
            "8.5",
            "--gamma",
            "0.7",
            "--frame-rate-enable",
            "--fps",
            "12.5",
            "--width",
            "1920",
            "--height",
            "1080",
            "--offset-x",
            "16",
            "--offset-y",
            "24",
            "--no-reverse-x",
            "--reverse-y",
        ),
        None,
    )
    config = settings.property_config

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
    file_settings = load_settings_from_config_payload(
        {
            "mvs_camera_demo": {
                "source": "mvs://sn/DA9184658?timeout_ms=1000&exposure_auto=off&exposure_time=5000&gain_auto=off&gain=6",
            },
        },
    )

    merged = merge_settings(
        parse_args("--exposure-time-us", "9000", "--gain", "10"),
        file_settings,
    )

    assert merged.property_config.exposure_time_us == 9000.0
    assert merged.property_config.gain == 10.0
    assert merged.locator.serial_number == "DA9184658"


def test_main_list_devices_short_circuits_before_loading_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_list_devices() -> int:
        captured["listed"] = True
        return 0

    monkeypatch.setattr(
        "seat_inspection.mvs_camera_demo.list_devices",
        fake_list_devices,
    )
    monkeypatch.setattr(
        "seat_inspection.mvs_camera_demo.load_settings_from_config",
        lambda *_args, **_kwargs: captured.setdefault("loaded", True),
    )

    exit_code = main(["--list-devices", "--config", "demo.json"])

    assert exit_code == 0
    assert captured == {"listed": True}


def load_settings_from_config_payload(payload: dict):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        return load_settings_from_config(str(config_path))
