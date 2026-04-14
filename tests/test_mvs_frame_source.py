from mvsCamera import MvsCameraSourceConfig, is_mvs_source, parse_mvs_source


def test_parse_mvs_source_supports_shorthand_device_index() -> None:
    config = parse_mvs_source("mvs://2")

    assert config == MvsCameraSourceConfig(device_index=2, grab_timeout_ms=1000)


def test_parse_mvs_source_supports_query_timeout() -> None:
    config = parse_mvs_source("mvs://0?timeout_ms=250")

    assert config.device_index == 0
    assert config.grab_timeout_ms == 250


def test_is_mvs_source_detects_scheme() -> None:
    assert is_mvs_source("mvs://0")
    assert not is_mvs_source("demo.mp4")
