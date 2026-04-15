"""旧版输入层兼容模块。

新代码应优先改用独立的 `media_inputs` 包。
"""

from __future__ import annotations

from typing import Any, Protocol

from media_inputs import FrameStream, open_frame_stream, resolve_capture_source


class FrameCapture(Protocol):
    """兼容旧接口的最小协议。"""

    def isOpened(self) -> bool:
        ...

    def read(self) -> tuple[bool, Any]:
        ...

    def release(self) -> None:
        ...

    def get(self, prop_id: int) -> float:
        ...


class _LegacyCaptureAdapter:
    """把新的标准帧流接口适配为旧版 OpenCV 风格接口。"""

    def __init__(self, stream: FrameStream) -> None:
        self._stream = stream

    def isOpened(self) -> bool:
        return self._stream.is_opened()

    def read(self) -> tuple[bool, Any]:
        media_frame = self._stream.read_frame()
        if media_frame is None:
            return False, None
        return True, media_frame.image

    def release(self) -> None:
        self._stream.release()

    def get(self, prop_id: int) -> float:
        return self._stream.get(prop_id)

def resolve_source(source: str) -> int | str:
    """兼容旧接口，内部委托到新输入层。"""
    return resolve_capture_source(source)


def open_capture(source: str) -> FrameCapture:
    """兼容旧接口，内部委托到新输入层。"""
    return _LegacyCaptureAdapter(open_frame_stream(source))
