from media_inputs import infer_source_kind, resolve_capture_source


def test_infer_source_kind_supports_multiple_inputs() -> None:
    assert infer_source_kind("mvs://0") == "mvs_camera"
    assert infer_source_kind("0") == "camera_index"
    assert infer_source_kind("demo.jpg") == "image"
    assert infer_source_kind("demo.mp4") == "video_file"


def test_resolve_capture_source_converts_digit_string_to_int() -> None:
    assert resolve_capture_source("1") == 1
    assert resolve_capture_source("demo.mp4") == "demo.mp4"
