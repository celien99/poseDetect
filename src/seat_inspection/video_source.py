from __future__ import annotations

from typing import Any, Protocol

import cv2

from mvsCamera import is_mvs_source, open_mvs_capture


class FrameCapture(Protocol):
    def isOpened(self) -> bool:
        ...

    def read(self) -> tuple[bool, Any]:
        ...

    def release(self) -> None:
        ...

    def get(self, prop_id: int) -> float:
        ...


def resolve_source(source: str) -> int | str:
    if source.isdigit():
        return int(source)
    return source


def open_capture(source: str) -> FrameCapture:
    if is_mvs_source(source):
        return open_mvs_capture(source)
    return cv2.VideoCapture(resolve_source(source))
