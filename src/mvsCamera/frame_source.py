"""MVS 相机源适配层。

上层只需要把海康相机当作一个 `cv2.VideoCapture` 风格输入源使用；
具体的设备选择、SDK 初始化和取流细节，都下沉到 `camera_controller.py`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from .camera_controller import CameraLocator, HikCamera, MvsCameraError

MVS_SOURCE_SCHEME = "mvs"
DEFAULT_GRAB_TIMEOUT_MS = 1000


@dataclass(slots=True)
class MvsCameraSourceConfig:
    """工业相机源配置。"""

    device_index: int | None = 0
    serial_number: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    grab_timeout_ms: int = DEFAULT_GRAB_TIMEOUT_MS
    trigger_mode: str = "continuous"
    pixel_format: str = "bgr8"


def is_mvs_source(source: str) -> bool:
    """判断给定源是否为 `mvs://` 工业相机地址。"""
    return source.lower().startswith(f"{MVS_SOURCE_SCHEME}://")


def parse_mvs_source(source: str) -> MvsCameraSourceConfig:
    """解析 `mvs://` 源字符串为结构化配置。

    支持示例：
    - `mvs://0`
    - `mvs://index/1`
    - `mvs://sn/ABC123`
    - `mvs://ip/192.168.1.10`
    - `mvs://mac/AA:BB:CC:DD:EE:FF`
    - `mvs://0?timeout_ms=2000&trigger=software&pixel_format=bgr8`
    """
    if not is_mvs_source(source):
        raise ValueError(f"Unsupported MVS source: {source}")

    parsed = urlparse(source)
    query = parse_qs(parsed.query)

    config = MvsCameraSourceConfig(
        grab_timeout_ms=int(query.get("timeout_ms", [DEFAULT_GRAB_TIMEOUT_MS])[0]),
        trigger_mode=query.get("trigger", ["continuous"])[0].lower(),
        pixel_format=query.get("pixel_format", ["bgr8"])[0].lower(),
    )

    _apply_selector_from_url(config, parsed)
    _apply_selector_from_query(config, query)
    _validate_selector(config)
    return config


def open_mvs_capture(source: str) -> "MvsCameraCapture":
    """根据字符串源创建工业相机取流对象。"""
    return MvsCameraCapture(parse_mvs_source(source))


class MvsCameraCapture:
    """对外暴露的相机取流适配器。"""

    def __init__(self, config: MvsCameraSourceConfig) -> None:
        self._config = config
        self._camera = HikCamera(
            locator=CameraLocator(
                device_index=config.device_index,
                serial_number=config.serial_number,
                ip_address=config.ip_address,
                mac_address=config.mac_address,
            ),
            trigger_mode=config.trigger_mode,
            pixel_format=config.pixel_format,
        )
        self._device_info = self._camera.open()
        self._camera.start_grabbing()

    def isOpened(self) -> bool:
        """返回相机是否已成功打开。"""
        return self._camera.opened

    def read(self) -> tuple[bool, Any]:
        """读取一帧 BGR 图像。"""
        frame = self._camera.get_frame(timeout_ms=self._config.grab_timeout_ms)
        if frame is None:
            return False, None
        return True, frame

    def release(self) -> None:
        """关闭相机。"""
        self._camera.close()

    def get(self, prop_id: int) -> float:
        """兼容 OpenCV 的属性查询。"""
        if prop_id == 3:
            return float(self._camera.width)
        if prop_id == 4:
            return float(self._camera.height)
        if prop_id == 5:
            return float(self._camera.fps)
        return 0.0

    @property
    def device_info(self):
        """返回当前连接设备的标准化信息。"""
        return self._device_info


def _apply_selector_from_url(config: MvsCameraSourceConfig, parsed) -> None:
    selector = (parsed.netloc or "").strip()
    remainder = parsed.path.strip("/")

    if selector in {"index", "sn", "serial", "ip", "mac"} and remainder:
        _set_selector(config, selector, remainder)
        return

    candidate = selector or remainder
    if not candidate:
        return
    if candidate.isdigit():
        config.device_index = int(candidate)


def _apply_selector_from_query(config: MvsCameraSourceConfig, query: dict[str, list[str]]) -> None:
    if "index" in query:
        config.device_index = int(query["index"][0])
    if "sn" in query:
        config.serial_number = query["sn"][0]
        config.device_index = None
    if "serial" in query:
        config.serial_number = query["serial"][0]
        config.device_index = None
    if "ip" in query:
        config.ip_address = query["ip"][0]
        config.device_index = None
    if "mac" in query:
        config.mac_address = query["mac"][0]
        config.device_index = None


def _set_selector(config: MvsCameraSourceConfig, selector: str, value: str) -> None:
    if selector == "index":
        config.device_index = int(value)
        return
    config.device_index = None
    if selector in {"sn", "serial"}:
        config.serial_number = value
    elif selector == "ip":
        config.ip_address = value
    elif selector == "mac":
        config.mac_address = value


def _validate_selector(config: MvsCameraSourceConfig) -> None:
    selected = [
        config.device_index is not None,
        bool(config.serial_number),
        bool(config.ip_address),
        bool(config.mac_address),
    ]
    if sum(selected) > 1:
        raise ValueError("Only one camera selector can be set among index / serial / ip / mac")
