from media_inputs import infer_source_kind, resolve_capture_source
from media_inputs.core import _CaptureFrameStream


class FakeCapture:
    def __init__(self) -> None:
        self._calls = 0

    def isOpened(self) -> bool:
        return True

    def read(self):
        import numpy as np

        self._calls += 1
        return True, np.zeros((4, 6, 3), dtype="uint8")

    def release(self) -> None:
        return None

    def get(self, prop_id: int) -> float:
        if prop_id == 0:
            return 0.0
        if prop_id == 5:
            return 25.0
        return 0.0


def test_infer_source_kind_supports_multiple_inputs() -> None:
    assert infer_source_kind("mvs://0") == "mvs_camera"
    assert infer_source_kind("0") == "camera_index"
    assert infer_source_kind("demo.jpg") == "image"
    assert infer_source_kind("demo.mp4") == "video_file"


def test_resolve_capture_source_converts_digit_string_to_int() -> None:
    assert resolve_capture_source("1") == 1
    assert resolve_capture_source("demo.mp4") == "demo.mp4"


def test_capture_frame_stream_builds_synthetic_timestamp_when_missing() -> None:
    stream = _CaptureFrameStream(FakeCapture(), "demo.mp4", "video_file")

    frame = stream.read_frame()

    assert frame is not None
    assert frame.timestamp_ms == 0.0
