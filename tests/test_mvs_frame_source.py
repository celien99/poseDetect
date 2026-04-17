from mvsCamera import MvsCameraSourceConfig, is_mvs_source, parse_mvs_source


def test_parse_mvs_source_supports_shorthand_device_index() -> None:
    config = parse_mvs_source("mvs://2")

    assert config == MvsCameraSourceConfig(device_index=2, grab_timeout_ms=1000)


def test_parse_mvs_source_supports_query_timeout() -> None:
    config = parse_mvs_source("mvs://0?timeout_ms=250")

    assert config.device_index == 0
    assert config.grab_timeout_ms == 250


def test_parse_mvs_source_supports_serial_selector() -> None:
    config = parse_mvs_source("mvs://sn/ABC123")

    assert config.device_index is None
    assert config.serial_number == "ABC123"


def test_parse_mvs_source_supports_ip_selector_with_query_options() -> None:
    config = parse_mvs_source("mvs://ip/192.168.1.10?trigger=software&pixel_format=mono8")

    assert config.ip_address == "192.168.1.10"
    assert config.trigger_mode == "software"
    assert config.pixel_format == "mono8"


def test_parse_mvs_source_supports_camera_property_queries() -> None:
    config = parse_mvs_source(
        "mvs://sn/ABC123"
        "?exposure_auto=off"
        "&exposure_time=6000"
        "&gain_auto=continuous"
        "&gain=8.5"
        "&gamma=0.7"
        "&frame_rate_enable=true"
        "&fps=12.5"
        "&width=1920"
        "&height=1080"
        "&offset_x=16"
        "&offset_y=24"
        "&reverse_x=false"
        "&reverse_y=true",
    )

    assert config.serial_number == "ABC123"
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


def test_mvs_camera_source_config_can_build_locator_and_property_config() -> None:
    config = parse_mvs_source(
        "mvs://sn/ABC123"
        "?exposure_auto=off"
        "&gain=8.5"
        "&width=1920"
        "&reverse_y=true",
    )

    locator = config.to_locator()
    property_config = config.to_property_config()

    assert locator.serial_number == "ABC123"
    assert locator.device_index is None
    assert property_config.exposure_auto == "off"
    assert property_config.gain == 8.5
    assert property_config.width == 1920
    assert property_config.reverse_y is True


def test_parse_mvs_source_rejects_invalid_boolean_query() -> None:
    try:
        parse_mvs_source("mvs://0?frame_rate_enable=maybe")
    except ValueError as exc:
        assert "Unsupported boolean value" in str(exc)
    else:
        raise AssertionError("expected invalid boolean query to raise ValueError")


def test_is_mvs_source_detects_scheme() -> None:
    assert is_mvs_source("mvs://0")
    assert not is_mvs_source("demo.mp4")
