from __future__ import annotations

from ctypes import POINTER, byref, c_ubyte, cast, memset, sizeof
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    import numpy as np

if __package__ in (None, ""):
    from mvsCamera.pixel_utils import is_color_pixel_type, is_mono_pixel_type
else:
    from .pixel_utils import is_color_pixel_type, is_mono_pixel_type

MVS_SOURCE_SCHEME = "mvs"
DEFAULT_GRAB_TIMEOUT_MS = 1000  # 单帧主动取流超时时间，单位毫秒


class MvsCameraError(RuntimeError):
    """MVS SDK 相机访问异常。"""


@dataclass
class MvsCameraSourceConfig:
    """工业相机源配置。"""

    device_index: int = 0
    grab_timeout_ms: int = DEFAULT_GRAB_TIMEOUT_MS


def is_mvs_source(source: str) -> bool:
    """判断给定源是否为 `mvs://` 工业相机地址。"""
    return source.lower().startswith(f"{MVS_SOURCE_SCHEME}://")


def parse_mvs_source(source: str) -> MvsCameraSourceConfig:
    """解析 `mvs://` 源字符串为结构化配置。"""
    if not is_mvs_source(source):
        raise ValueError(f"Unsupported MVS source: {source}")

    parsed = urlparse(source)
    device_index = _parse_device_index(parsed)
    query = parse_qs(parsed.query)
    timeout_ms = int(query.get("timeout_ms", [DEFAULT_GRAB_TIMEOUT_MS])[0])
    return MvsCameraSourceConfig(
        device_index=device_index,
        grab_timeout_ms=timeout_ms,
    )


def open_mvs_capture(source: str) -> "MvsCameraCapture":
    """根据字符串源创建工业相机取流对象。"""
    return MvsCameraCapture(parse_mvs_source(source))


class MvsCameraCapture:
    """对海康 MVS SDK 的轻量封装，接口尽量兼容 `cv2.VideoCapture`。"""

    def __init__(self, config: MvsCameraSourceConfig) -> None:
        self._config = config
        self._sdk = _load_sdk()
        self._camera = self._sdk["MvCamera"]()
        self._device_list = self._sdk["MV_CC_DEVICE_INFO_LIST"]()
        self._frame_buffer: Any | None = None  # SDK 原始帧缓存
        self._payload_size = 0  # 当前设备单帧最大字节数
        self._width = 0
        self._height = 0
        self._fps = 0.0
        self._opened = False
        self._start()

    def isOpened(self) -> bool:
        """返回当前相机是否成功打开。"""
        return self._opened

    def read(self) -> tuple[bool, Any]:
        """读取一帧图像，返回值风格与 OpenCV 保持一致。"""
        if not self._opened:
            return False, None

        frame_info = self._sdk["MV_FRAME_OUT_INFO_EX"]()
        memset(byref(frame_info), 0, sizeof(frame_info))
        ret = self._camera.MV_CC_GetOneFrameTimeout(
            self._frame_buffer,
            self._payload_size,
            frame_info,
            self._config.grab_timeout_ms,
        )
        if ret != 0:
            return False, None

        self._width = int(frame_info.nWidth)
        self._height = int(frame_info.nHeight)
        return True, self._decode_frame(self._frame_buffer, frame_info)

    def release(self) -> None:
        """停止取流并释放设备句柄。"""
        if not self._opened:
            return

        try:
            self._camera.MV_CC_StopGrabbing()
        finally:
            try:
                self._camera.MV_CC_CloseDevice()
            finally:
                self._camera.MV_CC_DestroyHandle()
                self._opened = False

    def get(self, prop_id: int) -> float:
        """兼容 OpenCV 的少量属性查询。"""
        if prop_id == 3:
            return float(self._width)
        if prop_id == 4:
            return float(self._height)
        if prop_id == 5:
            return float(self._fps)
        return 0.0

    def _start(self) -> None:
        """枚举设备、打开目标相机并开始取流。"""
        transport_layer = self._sdk["MV_GIGE_DEVICE"] | self._sdk["MV_USB_DEVICE"]
        ret = self._sdk["MvCamera"].MV_CC_EnumDevices(transport_layer, self._device_list)
        _check_ret(ret, "enumerate devices")

        if self._device_list.nDeviceNum == 0:
            raise MvsCameraError("No MVS camera devices were found")
        if self._config.device_index >= self._device_list.nDeviceNum:
            raise MvsCameraError(
                f"Device index {self._config.device_index} is out of range for "
                f"{self._device_list.nDeviceNum} detected camera(s)",
            )

        device_info = cast(
            self._device_list.pDeviceInfo[self._config.device_index],
            POINTER(self._sdk["MV_CC_DEVICE_INFO"]),
        ).contents

        ret = self._camera.MV_CC_CreateHandle(device_info)
        _check_ret(ret, "create device handle")
        try:
            ret = self._camera.MV_CC_OpenDevice(self._sdk["MV_ACCESS_Exclusive"], 0)
            _check_ret(ret, "open device")

            if device_info.nTLayerType == self._sdk["MV_GIGE_DEVICE"]:
                # GigE 相机需要优先设置最佳包长，避免丢包或吞吐下降。
                packet_size = self._camera.MV_CC_GetOptimalPacketSize()
                if int(packet_size) > 0:
                    self._camera.MV_CC_SetIntValue("GevSCPSPacketSize", int(packet_size))

            ret = self._camera.MV_CC_SetEnumValue("TriggerMode", self._sdk["MV_TRIGGER_MODE_OFF"])
            _check_ret(ret, "disable trigger mode")

            self._payload_size = self._get_int_value("PayloadSize")
            self._width = self._get_int_value("Width")
            self._height = self._get_int_value("Height")
            self._fps = self._get_float_value("AcquisitionFrameRate")
            self._frame_buffer = (c_ubyte * self._payload_size)()

            ret = self._camera.MV_CC_StartGrabbing()
            _check_ret(ret, "start grabbing")
        except Exception:
            self._camera.MV_CC_CloseDevice()
            self._camera.MV_CC_DestroyHandle()
            raise

        self._opened = True

    def _get_int_value(self, node_name: str) -> int:
        """读取整型节点值。"""
        param = self._sdk["MVCC_INTVALUE"]()
        memset(byref(param), 0, sizeof(param))
        ret = self._camera.MV_CC_GetIntValue(node_name, param)
        _check_ret(ret, f"read int node {node_name}")
        return int(param.nCurValue)

    def _get_float_value(self, node_name: str) -> float:
        """读取浮点型节点值，若节点不可读则返回 0。"""
        param = self._sdk["MVCC_FLOATVALUE"]()
        memset(byref(param), 0, sizeof(param))
        ret = self._camera.MV_CC_GetFloatValue(node_name, param)
        if ret != 0:
            return 0.0
        return float(param.fCurValue)

    def _decode_frame(self, frame_buffer: Any, frame_info: Any) -> Any:
        """把 SDK 原始帧转换成 OpenCV 可直接使用的 BGR 图像。"""
        cv2, np = _load_runtime_dependencies()
        width = int(frame_info.nWidth)
        height = int(frame_info.nHeight)
        pixel_type = int(frame_info.enPixelType)

        if pixel_type == self._sdk["PixelType_Gvsp_BGR8_Packed"]:
            frame = np.frombuffer(
                frame_buffer,
                count=width * height * 3,
                dtype=np.uint8,
            ).reshape(height, width, 3)
            return frame.copy()

        if pixel_type == self._sdk["PixelType_Gvsp_RGB8_Packed"]:
            rgb = np.frombuffer(
                frame_buffer,
                count=width * height * 3,
                dtype=np.uint8,
            ).reshape(height, width, 3)
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if pixel_type == self._sdk["PixelType_Gvsp_Mono8"]:
            mono = np.frombuffer(
                frame_buffer,
                count=width * height,
                dtype=np.uint8,
            ).reshape(height, width)
            return cv2.cvtColor(mono, cv2.COLOR_GRAY2BGR)

        if is_color_pixel_type(pixel_type):
            # 统一转换到 BGR，便于直接喂给 OpenCV / YOLO。
            converted = self._convert_pixel_type(
                frame_buffer,
                frame_info,
                self._sdk["PixelType_Gvsp_BGR8_Packed"],
                width * height * 3,
            )
            return np.frombuffer(
                converted,
                count=width * height * 3,
                dtype=np.uint8,
            ).reshape(height, width, 3).copy()

        if is_mono_pixel_type(pixel_type):
            # 单通道图像也转换成 3 通道 BGR，避免上游推理逻辑分支处理。
            converted = self._convert_pixel_type(
                frame_buffer,
                frame_info,
                self._sdk["PixelType_Gvsp_Mono8"],
                width * height,
            )
            mono = np.frombuffer(
                converted,
                count=width * height,
                dtype=np.uint8,
            ).reshape(height, width)
            return cv2.cvtColor(mono, cv2.COLOR_GRAY2BGR)

        raise MvsCameraError(f"Unsupported pixel type: {pixel_type}")

    def _convert_pixel_type(
        self,
        frame_buffer: Any,
        frame_info: Any,
        destination_pixel_type: int,
        destination_size: int,
    ) -> Any:
        """调用 SDK 内置像素格式转换能力。"""
        convert_param = self._sdk["MV_CC_PIXEL_CONVERT_PARAM"]()
        memset(byref(convert_param), 0, sizeof(convert_param))
        convert_param.nWidth = frame_info.nWidth
        convert_param.nHeight = frame_info.nHeight
        convert_param.enSrcPixelType = frame_info.enPixelType
        convert_param.pSrcData = cast(frame_buffer, POINTER(c_ubyte))
        convert_param.nSrcDataLen = frame_info.nFrameLen
        convert_param.enDstPixelType = destination_pixel_type

        destination_buffer = (c_ubyte * destination_size)()
        convert_param.pDstBuffer = cast(destination_buffer, POINTER(c_ubyte))
        convert_param.nDstBufferSize = destination_size

        ret = self._camera.MV_CC_ConvertPixelType(convert_param)
        _check_ret(ret, "convert frame pixel type")
        return destination_buffer


def _parse_device_index(parsed: Any) -> int:
    """从 `mvs://<index>` 或 `mvs://index/<index>` 中解析设备号。"""
    candidate = parsed.netloc or parsed.path.strip("/")
    if not candidate:
        return 0
    if candidate.startswith("index/"):
        candidate = candidate.split("/", 1)[1]
    return int(candidate)


def _check_ret(ret: int, action: str) -> None:
    """统一检查 SDK 返回码。"""
    if ret != 0:
        raise MvsCameraError(f"Failed to {action}: 0x{ret:x}")


def _load_sdk() -> dict[str, Any]:
    """延迟导入 MVS SDK 相关结构体与常量，降低普通环境启动成本。"""
    from .CameraParams_const import MV_ACCESS_Exclusive, MV_GIGE_DEVICE, MV_TRIGGER_MODE_OFF, MV_USB_DEVICE
    from .MvCameraControl_class import MvCamera
    from .MvCameraControl_header import (
        MV_CC_DEVICE_INFO,
        MV_CC_DEVICE_INFO_LIST,
        MV_CC_PIXEL_CONVERT_PARAM,
        MV_FRAME_OUT_INFO_EX,
        MVCC_FLOATVALUE,
        MVCC_INTVALUE,
        PixelType_Gvsp_BGR8_Packed,
        PixelType_Gvsp_Mono8,
        PixelType_Gvsp_RGB8_Packed,
    )

    return {
        "MV_ACCESS_Exclusive": MV_ACCESS_Exclusive,
        "MV_CC_DEVICE_INFO": MV_CC_DEVICE_INFO,
        "MV_CC_DEVICE_INFO_LIST": MV_CC_DEVICE_INFO_LIST,
        "MV_CC_PIXEL_CONVERT_PARAM": MV_CC_PIXEL_CONVERT_PARAM,
        "MV_FRAME_OUT_INFO_EX": MV_FRAME_OUT_INFO_EX,
        "MV_GIGE_DEVICE": MV_GIGE_DEVICE,
        "MV_TRIGGER_MODE_OFF": MV_TRIGGER_MODE_OFF,
        "MV_USB_DEVICE": MV_USB_DEVICE,
        "MVCC_FLOATVALUE": MVCC_FLOATVALUE,
        "MVCC_INTVALUE": MVCC_INTVALUE,
        "MvCamera": MvCamera,
        "PixelType_Gvsp_BGR8_Packed": PixelType_Gvsp_BGR8_Packed,
        "PixelType_Gvsp_Mono8": PixelType_Gvsp_Mono8,
        "PixelType_Gvsp_RGB8_Packed": PixelType_Gvsp_RGB8_Packed,
    }


def _load_runtime_dependencies() -> tuple[Any, Any]:
    """延迟导入 OpenCV / numpy，避免无相机环境下不必要的导入失败。"""
    try:
        import cv2
        import numpy as np
    except ModuleNotFoundError as exc:
        raise MvsCameraError(
            "OpenCV and numpy are required when reading frames from an MVS camera",
        ) from exc
    return cv2, np
