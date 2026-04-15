# `src/mvsCamera` 使用说明

本文档说明当前项目中 `src/mvsCamera` 模块的职责、可实现的功能、如何单独使用，以及它在当前项目中的接入方式。

## 1. 模块定位

`src/mvsCamera` 现在的定位已经很明确：

- 它是海康 MVS SDK 的 Python 接入层
- 它负责相机发现、打开、取流、像素转换
- 它不直接负责动作识别
- 它的主要输出是“可供上层消费的图像帧”

也就是说：

- `mvsCamera` 负责“把工业相机数据拿进来”
- `media_inputs` 负责“把各种媒体资源统一成标准帧数据”
- `seat_inspection` 负责“拿标准帧数据做检测、规则判断、流程状态机和 OK/NG 输出”

## 2. 当前目录结构

当前 `src/mvsCamera` 主要分为两层。

### 对外接口层

- [src/mvsCamera/__init__.py](/Users/yyh/code/poseDetect/src/mvsCamera/__init__.py)
- [src/mvsCamera/camera_controller.py](/Users/yyh/code/poseDetect/src/mvsCamera/camera_controller.py)
- [src/mvsCamera/frame_source.py](/Users/yyh/code/poseDetect/src/mvsCamera/frame_source.py)
- [src/mvsCamera/pixel_utils.py](/Users/yyh/code/poseDetect/src/mvsCamera/pixel_utils.py)
- [src/mvsCamera/MvCameraControl_class.py](/Users/yyh/code/poseDetect/src/mvsCamera/MvCameraControl_class.py)
- [src/mvsCamera/sdk_loader.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk_loader.py)

### SDK 底层映射层

- [src/mvsCamera/sdk/__init__.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/__init__.py)
- [src/mvsCamera/sdk/MvCameraControl_class.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/MvCameraControl_class.py)
- [src/mvsCamera/sdk/sdk_loader.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/sdk_loader.py)
- [src/mvsCamera/sdk/CameraParams_const.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/CameraParams_const.py)
- [src/mvsCamera/sdk/CameraParams_header.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/CameraParams_header.py)
- [src/mvsCamera/sdk/MvCameraControl_header.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/MvCameraControl_header.py)
- [src/mvsCamera/sdk/MvErrorDefine_const.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/MvErrorDefine_const.py)
- [src/mvsCamera/sdk/PixelType_header.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/PixelType_header.py)

说明：

- 对外接口层适合业务代码直接调用
- `sdk/` 子包主要是底层 ctypes 映射，不建议业务代码直接改

## 3. 当前能实现什么功能

当前 `src/mvsCamera` 可以实现：

- 初始化和反初始化海康 MVS SDK
- 枚举当前机器可见的工业相机
- 按设备索引选择相机
- 按 SN 选择相机
- 按 IP 选择相机
- 按 MAC 选择相机
- 打开设备
- 设置连续模式或软件触发模式
- 开始取流
- 读取一帧图像
- 把相机输出统一转换为 OpenCV 可直接使用的 BGR 图像
- 给上层提供类似 `cv2.VideoCapture` 的调用方式
- 在 Windows 上自动尝试发现 MVS SDK DLL 路径

## 4. 核心对外接口

最常用的接口在 [src/mvsCamera/__init__.py](/Users/yyh/code/poseDetect/src/mvsCamera/__init__.py) 中已经统一导出。

主要包括：

- `HikCamera`
- `CameraLocator`
- `MvsDeviceInfo`
- `MvsCameraCapture`
- `parse_mvs_source`
- `open_mvs_capture`
- `is_mvs_source`
- `describe_mvs_sdk_candidates`

## 5. 两种推荐使用方式

### 方式 A：直接使用 `HikCamera`

适合：

- 调试相机本身
- 枚举设备
- 手动控制触发
- 单独验证 MVS SDK 是否正常

示例：

```python
from mvsCamera import HikCamera, CameraLocator

camera = HikCamera(
    locator=CameraLocator(device_index=0),
    trigger_mode="continuous",
    pixel_format="bgr8",
)

device_info = camera.open()
print(device_info)

camera.start_grabbing()
frame = camera.get_frame(timeout_ms=1000)

if frame is not None:
    print(frame.shape)

camera.close()
```

### 方式 B：直接使用 `open_mvs_capture`

适合：

- 把工业相机当作 `cv2.VideoCapture` 风格源接入
- 给上层 `media_inputs` 或其他通用媒体层调用

示例：

```python
from mvsCamera import open_mvs_capture

capture = open_mvs_capture("mvs://0?timeout_ms=1000")

ok, frame = capture.read()
if ok:
    print(frame.shape)

capture.release()
```

## 6. `mvs://` 资源地址格式

当前 `frame_source.py` 支持这些写法。

### 按设备索引

```text
mvs://0
mvs://1
mvs://index/0
```

### 按序列号

```text
mvs://sn/ABC123456
```

### 按 IP

```text
mvs://ip/192.168.1.10
```

### 按 MAC

```text
mvs://mac/AA:BB:CC:DD:EE:FF
```

### 带参数

```text
mvs://0?timeout_ms=2000&trigger=software&pixel_format=bgr8
```

支持的常见参数：

- `timeout_ms`
- `trigger`
- `pixel_format`

当前常用值：

- `trigger=continuous`
- `trigger=software`
- `pixel_format=bgr8`
- `pixel_format=mono8`

## 7. 当前项目里如何使用它

在当前项目里，`mvsCamera` 不是直接被 `seat_inspection` 调的，而是通过 `media_inputs` 间接接入。

调用链是：

```text
mvsCamera
  ↓
media_inputs
  ↓
seat_inspection
```

对应代码关系：

- [src/mvsCamera/frame_source.py](/Users/yyh/code/poseDetect/src/mvsCamera/frame_source.py)
- [src/media_inputs/core.py](/Users/yyh/code/poseDetect/src/media_inputs/core.py)
- [src/seat_inspection/inference.py](/Users/yyh/code/poseDetect/src/seat_inspection/inference.py)
- [src/seat_inspection/dataset_capture.py](/Users/yyh/code/poseDetect/src/seat_inspection/dataset_capture.py)

### 具体过程

1. `seat_inspection` 读取配置里的 `source`
2. `media_inputs` 判断它是不是 `mvs://...`
3. 如果是，就调用 `mvsCamera.open_mvs_capture(...)`
4. 相机帧被转换成标准图像
5. 上层继续做人体检测、座椅检测、姿态检测和动作流程判断

## 8. 在 `seat_inspection` 中如何启用工业相机

在配置文件里把 `source` 写成：

```json
{
  "source": "mvs://0?timeout_ms=1000"
}
```

或者：

```json
{
  "source": "mvs://sn/ABC123456?trigger=continuous&pixel_format=bgr8"
}
```

之后直接运行：

```bash
python -m seat_inspection.main infer --config your_config.json
```

或者采集数据集：

```bash
python -m seat_inspection.main collect --config your_config.json
```

这时候 `seat_inspection` 不需要知道海康 SDK 细节，它只会看到正常的视频帧。

## 9. `media_inputs` 为什么重要

当前项目里，推荐不要在业务层直接大量调用 `HikCamera`。

更推荐的方式是：

- `mvsCamera` 负责相机 SDK 接入
- `media_inputs` 负责把图片 / 视频 / 普通摄像头 / 工业相机统一成标准帧流
- `seat_inspection` 只处理标准帧流

这样做的好处是：

- 业务层更干净
- 更容易切换输入源
- 更容易扩展 RTSP、文件夹图片、HTTP 流等新输入类型
- 工业相机问题和业务识别问题能分开排查

## 10. 推荐排障方式

如果在 Windows 测试机上排查问题，建议按这个顺序。

### 1）先检查 SDK DLL 路径

```python
from mvsCamera import describe_mvs_sdk_candidates

print("\n".join(describe_mvs_sdk_candidates()))
```

### 2）再检查设备枚举

```python
from mvsCamera import HikCamera

cam = HikCamera()
print(cam.enumerate_devices())
cam.close()
```

### 3）再检查单帧取图

```python
from mvsCamera import open_mvs_capture

cap = open_mvs_capture("mvs://0")
ok, frame = cap.read()
print(ok, None if frame is None else frame.shape)
cap.release()
```

### 4）最后再接入 `seat_inspection`

也就是把：

```json
"source": "mvs://0?timeout_ms=1000"
```

写进推理或采集配置，再跑项目主命令。

## 11. 当前模块边界

当前 `src/mvsCamera` 负责：

- MVS SDK 封装
- 相机打开与取流
- 图像像素格式转换
- 相机定位与基础参数控制

当前 `src/mvsCamera` 不负责：

- 人体检测
- 座椅检测
- 姿态估计
- 动作规则
- 状态机
- OK/NG 判定

这些能力都属于 `seat_inspection`。

## 12. 当前最适合的使用方式

在当前项目里，最推荐的实际用法是：

### 如果你只是想让项目跑起来

直接在配置里写：

```json
"source": "mvs://0?timeout_ms=1000"
```

然后通过：

- `collect`
- `infer`

让上层流程自动走。

### 如果你想调试海康相机本身

直接用：

- `HikCamera`
- `open_mvs_capture`

单独验证设备枚举、打开、取帧。

## 13. 总结

一句话理解当前 `src/mvsCamera`：

它是当前项目中“把海康工业相机变成标准图像帧输入”的模块。

一句话理解它在整个项目中的位置：

它是输入层，不是识别层。

