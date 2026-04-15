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


def test_is_mvs_source_detects_scheme() -> None:
    assert is_mvs_source("mvs://0")
    assert not is_mvs_source("demo.mp4")
