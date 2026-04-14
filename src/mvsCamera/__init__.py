"""Reusable MVS camera frame-source adapter for seat inspection."""

from .frame_source import (
    MvsCameraCapture,
    MvsCameraError,
    MvsCameraSourceConfig,
    is_mvs_source,
    open_mvs_capture,
    parse_mvs_source,
)
from .sdk_loader import MvsSdkLoadError, describe_mvs_sdk_candidates

__all__ = [
    "MvsCameraCapture",
    "MvsCameraError",
    "MvsSdkLoadError",
    "MvsCameraSourceConfig",
    "describe_mvs_sdk_candidates",
    "is_mvs_source",
    "open_mvs_capture",
    "parse_mvs_source",
]
