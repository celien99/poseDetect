# MVS Camera 包使用指南

这份文档面向刚接触本项目的同学，目标是帮助你快速理解 `src/mvsCamera/` 目录下每个文件的作用、常见参数的含义，以及如何基于当前项目正确配置海康 MVS 工业相机。

本文内容基于当前仓库中的实现整理，重点对应以下代码：

- [src/mvsCamera/frame_source.py](/Users/yyh/code/poseDetect/src/mvsCamera/frame_source.py)
- [src/mvsCamera/camera_controller.py](/Users/yyh/code/poseDetect/src/mvsCamera/camera_controller.py)
- [src/mvsCamera/sdk/MvCameraControl_class.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/MvCameraControl_class.py)

## 一、先建立整体认识

把 `mvsCamera` 想成 3 层最容易理解：

1. 配置入口层
   负责解析 `mvs://...` 这样的相机地址，并对外提供类似 `cv2.VideoCapture` 的接口。
2. 相机控制层
   负责真正打开海康相机、设置曝光、增益、触发模式、帧率、ROI，并抓取图像。
3. SDK 包装层
   负责把海康官方 DLL 包装成 Python 可以调用的方法。

项目里的调用路径可以概括成：

```text
业务配置中的 source
  -> mvs://sn/DA9184658?timeout_ms=1000&exposure_time=6000
  -> src/media_inputs/core.py
  -> src/mvsCamera/frame_source.py
  -> src/mvsCamera/camera_controller.py
  -> src/mvsCamera/sdk/MvCameraControl_class.py
  -> 海康 MVS SDK DLL
```

如果你只是要改配置，主要看 `frame_source.py`。  
如果你要理解某个参数最后是怎么作用到相机上的，继续看 `camera_controller.py`。  
如果你要排查底层 SDK 节点或 DLL 问题，再看 `sdk/`。

## 二、目录中每个文件是做什么的

### 1. 顶层文件

`src/mvsCamera/__init__.py`

- 包的统一导出入口。
- 外部代码 `from mvsCamera import ...` 时，通常都是从这里拿到类和函数。
- 当前导出的常用对象包括：
  - `parse_mvs_source`
  - `open_mvs_capture`
  - `MvsCameraSourceConfig`
  - `HikCamera`
  - `CameraPropertyConfig`

`src/mvsCamera/frame_source.py`

- 这是最贴近配置文件的一层。
- 作用：
  - 判断一个输入源是不是 `mvs://...`
  - 解析 `mvs://...` 中的参数
  - 把解析结果封装成 `MvsCameraSourceConfig`
  - 创建 `MvsCameraCapture`
  - 对外暴露 `read()`、`release()`、`isOpened()` 这些类似 OpenCV 的方法
- 小白最推荐先读这个文件。

`src/mvsCamera/camera_controller.py`

- 这是整个 `mvsCamera` 的核心。
- 作用：
  - 初始化 MVS SDK
  - 枚举设备
  - 通过 `index`、`sn`、`ip`、`mac` 找到目标相机
  - 打开相机
  - 设置触发模式和像素格式
  - 设置曝光、增益、Gamma、帧率、ROI、翻转
  - 开始取流
  - 从 SDK 获取一帧图像并转成 OpenCV 常用的 BGR 图像
- 你想控制相机参数，主要看这里。

`src/mvsCamera/pixel_utils.py`

- 这是一些辅助工具函数。
- 作用：
  - 把 C 风格字符数组转换成 Python 字符串
  - 把整数形式的 IP 转成人类可读格式
  - 判断像素格式是单通道还是彩色
  - 计算图像缓冲区大小
- 平时一般不需要改。

### 2. SDK 子目录

`src/mvsCamera/sdk/sdk_loader.py`

- 负责寻找并加载 `MvCameraControl.dll`。
- 会尝试项目本地 DLL、环境变量目录、常见安装目录、注册表安装目录。
- 如果你的程序提示 SDK 无法加载，通常从这个文件开始排查。

`src/mvsCamera/sdk/MvCameraControl_class.py`

- 把 DLL 中的函数包装成 Python 方法。
- 常见的底层能力都在这里，例如：
  - `MV_CC_SetIntValue`
  - `MV_CC_SetFloatValue`
  - `MV_CC_SetEnumValue`
  - `MV_CC_SetBoolValue`
  - `MV_CC_GetOneFrameTimeout`
  - `MV_CC_StartGrabbing`
  - `MV_CC_StopGrabbing`
- 这个文件更偏底层，适合排查 SDK 节点和返回码。

`src/mvsCamera/sdk/MvCameraControl_header.py`

- 自动生成的 ctypes 头文件映射。
- 里面包含：
  - 枚举值
  - 像素格式常量
  - 结构体定义
  - 读取整型、浮点型节点范围时需要的数据结构
- 例如：
  - `MVCC_INTVALUE`
  - `MVCC_FLOATVALUE`
  - `PixelType_Gvsp_*`

`src/mvsCamera/sdk/CameraParams_header.py`

- 也是自动生成的参数头文件映射。
- 当前项目里直接使用较少，主要是 SDK 配套结构定义。

`src/mvsCamera/sdk/CameraParams_const.py`

- 设备类型、访问模式等基础常量定义。

`src/mvsCamera/sdk/MvErrorDefine_const.py`

- SDK 错误码定义。
- `camera_controller.py` 会基于这些常量把错误码翻译成可读文本。

`src/mvsCamera/sdk/PixelType_header.py`

- 像素格式相关常量。

`src/mvsCamera/MvCameraControl.dll`

- 真正的海康 MVS 动态库。
- 没有它，底层控制函数无法运行。

## 三、最重要的几个类分别干什么

### 1. `MvsCameraSourceConfig`

定义在 [src/mvsCamera/frame_source.py](/Users/yyh/code/poseDetect/src/mvsCamera/frame_source.py)。

这是“配置对象”，对应 `mvs://...` 里所有可写参数。

当前主要字段包括：

- 相机选择
  - `device_index`
  - `serial_number`
  - `ip_address`
  - `mac_address`
- 取流行为
  - `grab_timeout_ms`
  - `trigger_mode`
  - `pixel_format`
- 图像参数
  - `exposure_auto`
  - `exposure_time_us`
  - `gain_auto`
  - `gain`
  - `gamma`
  - `acquisition_frame_rate_enable`
  - `acquisition_frame_rate`
  - `width`
  - `height`
  - `offset_x`
  - `offset_y`
  - `reverse_x`
  - `reverse_y`

### 2. `CameraPropertyConfig`

定义在 [src/mvsCamera/camera_controller.py](/Users/yyh/code/poseDetect/src/mvsCamera/camera_controller.py)。

这是“运行时属性配置对象”。
`frame_source.py` 会把 URI 里的参数解析出来，再转换成 `CameraPropertyConfig`，最后传给 `HikCamera`。

你可以把它理解为“真正准备发给相机的参数集合”。

### 3. `HikCamera`

定义在 [src/mvsCamera/camera_controller.py](/Users/yyh/code/poseDetect/src/mvsCamera/camera_controller.py)。

这是海康相机控制器，是本包最核心的类。

常见职责：

- `enumerate_devices()`
  - 枚举当前可见设备
- `open()`
  - 打开相机并应用配置
- `start_grabbing()`
  - 开始取流
- `get_frame()`
  - 获取一帧图像
- `close()`
  - 关闭相机
- `set_exposure_time()`
  - 设置曝光时间
- `set_gain()`
  - 设置增益
- `set_acquisition_frame_rate()`
  - 设置帧率
- `set_roi()`
  - 设置 ROI

### 4. `MvsCameraCapture`

定义在 [src/mvsCamera/frame_source.py](/Users/yyh/code/poseDetect/src/mvsCamera/frame_source.py)。

这是给业务层使用的“适配器”。
它把 `HikCamera` 包成类似 OpenCV 的相机对象。

你通常不会直接感知底层 SDK，而是通过这个对象来：

- `isOpened()`
- `read()`
- `release()`
- `get()`

## 四、配置字符串 `mvs://...` 到底怎么工作

这是你在配置文件中最常见的写法：

```json
{
  "name": "cam_0",
  "source": "mvs://sn/DA9184658?timeout_ms=1000&exposure_auto=off&exposure_time=6000&gain_auto=off&gain=8"
}
```

这段字符串的含义可以拆成两部分：

第一部分是相机选择器：

```text
mvs://sn/DA9184658
```

表示按序列号选择相机。

第二部分是查询参数：

```text
?timeout_ms=1000&exposure_auto=off&exposure_time=6000&gain_auto=off&gain=8
```

表示打开后还要设置这些属性。

解析过程如下：

1. `parse_mvs_source()` 识别 `mvs://`
2. 解析 `sn`、`timeout_ms`、`exposure_time` 等字段
3. 构造 `MvsCameraSourceConfig`
4. 生成 `CameraPropertyConfig`
5. 创建 `HikCamera`
6. `HikCamera.open()` 中应用这些参数

## 五、当前支持的参数说明

下面是当前项目里已经支持并接通到 `HikCamera` 的常用参数。

### 1. 相机选择参数

`mvs://0`

- 按枚举顺序选择第 0 台相机。
- 适合快速测试。
- 不适合稳定生产环境，因为设备顺序可能变化。

`mvs://index/1`

- 和 `mvs://1` 类似，语义更明确。

`mvs://sn/DA9184658`

- 按序列号选择相机。
- 多相机环境最推荐。

`mvs://ip/192.168.1.10`

- 按 IP 选择相机，常见于 GigE 相机。

`mvs://mac/AA:BB:CC:DD:EE:FF`

- 按 MAC 地址选择相机。

推荐顺序：

1. `sn`
2. `ip`
3. `index`

### 2. 取流行为参数

`timeout_ms`

- 含义：取一帧图像时最长等待时间，单位毫秒。
- 常见值：`500`、`1000`、`2000`

`trigger`

- 可选值：
  - `continuous`
  - `software`
- `continuous` 表示连续采图。
- `software` 表示每次读取前主动发一次软件触发。

`pixel_format`

- 当前常用值：
  - `bgr8`
  - `rgb8`
  - `mono8`
- 和 OpenCV 联动时，优先使用 `bgr8`。

### 3. 曝光参数

`exposure_auto`

- 可选值：
  - `off`
  - `once`
  - `continuous`

`exposure_time`
或
`exposure_time_us`

- 含义：曝光时间，单位微秒。

理解方法：

- 曝光时间越大，图像越亮。
- 曝光时间越大，运动拖影也越明显。

建议：

- 稳定现场优先 `exposure_auto=off`
- 然后手动调 `exposure_time`

### 4. 增益参数

`gain_auto`

- 可选值：
  - `off`
  - `once`
  - `continuous`

`gain`

- 含义：模拟增益。

理解方法：

- 增益越大，画面越亮。
- 增益越大，噪点一般也越多。

建议：

- 先调曝光，再调增益。
- 要求结果稳定时，通常 `gain_auto=off`。

### 5. Gamma 参数

`gamma`

- 调整图像亮暗曲线。
- 不是最优先的参数。
- 没特殊需求可以先不改。

### 6. 帧率参数

`frame_rate_enable`
或
`acquisition_frame_rate_enable`

- 布尔值：`true` 或 `false`

`fps`
或
`frame_rate`
或
`acquisition_frame_rate`

- 目标采集帧率。

建议：

- 机器算力有限时，可以适当降低 `fps`
- 很多检测任务用 `8` 到 `15` FPS 就够了

### 7. ROI 参数

`width`

- ROI 宽度

`height`

- ROI 高度

`offset_x`

- ROI 左上角横向偏移

`offset_y`

- ROI 左上角纵向偏移

注意：

- ROI 参数不能乱写。
- 它们必须满足相机本身支持的最小值、最大值、步进值。
- 如果你改了 ROI，后面的区域标注坐标通常也要重新检查。

### 8. 翻转参数

`reverse_x`

- 水平翻转

`reverse_y`

- 垂直翻转

适合安装方向不一致时快速修正图像方向。

## 六、推荐给小白的调参顺序

不要一上来同时改很多参数，最稳妥的顺序如下：

### 第一步：先确认相机能连通

```text
mvs://sn/DA9184658?timeout_ms=1000
```

只验证设备选择是否正确、相机能否正常出图。

### 第二步：固定基础取流模式

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8
```

先把触发方式和像素格式稳定下来。

### 第三步：锁定曝光

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8&exposure_auto=off&exposure_time=5000
```

### 第四步：补增益

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8&exposure_auto=off&exposure_time=5000&gain_auto=off&gain=6
```

### 第五步：控制帧率

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8&exposure_auto=off&exposure_time=5000&gain_auto=off&gain=6&frame_rate_enable=true&fps=10
```

### 第六步：最后再动 ROI

```text
mvs://sn/DA9184658?timeout_ms=1000&exposure_auto=off&exposure_time=5000&gain_auto=off&gain=6&width=1920&height=1080&offset_x=0&offset_y=0
```

ROI 会影响图像尺寸和后续标注，不建议一开始就改。

## 七、几套可以直接抄的配置模板

### 1. 稳定识别模板

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8&exposure_auto=off&exposure_time=5000&gain_auto=off&gain=6&frame_rate_enable=true&fps=10
```

适合大多数固定机位识别场景。

### 2. 低光环境模板

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8&exposure_auto=off&exposure_time=8000&gain_auto=off&gain=10
```

适合现场偏暗时先快速起步。

### 3. 减少拖影模板

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8&exposure_auto=off&exposure_time=2000&gain_auto=off&gain=12&frame_rate_enable=true&fps=15
```

适合目标动作较快、需要更清晰边缘时。

### 4. 软件触发模板

```text
mvs://sn/DA9184658?timeout_ms=1000&trigger=software&pixel_format=bgr8&exposure_auto=off&exposure_time=4000
```

适合“发一次命令，拍一张”的流程。

## 八、如何从代码里直接控制参数

除了在 `source` 字符串里配置，你也可以直接在 Python 代码里调用相机控制器。

示例：

```python
from mvsCamera import CameraLocator, CameraPropertyConfig, HikCamera

camera = HikCamera(
    locator=CameraLocator(serial_number="DA9184658"),
    property_config=CameraPropertyConfig(
        exposure_auto="off",
        exposure_time_us=6000,
        gain_auto="off",
        gain=8.0,
        acquisition_frame_rate_enable=True,
        acquisition_frame_rate=10.0,
        reverse_x=False,
        reverse_y=False,
    ),
)

device_info = camera.open()
print(device_info)
camera.start_grabbing()

frame = camera.get_frame(timeout_ms=1000)
print(frame.shape if frame is not None else None)

camera.close()
```

这种方式更适合：

- 写调试脚本
- 做现场联调
- 逐步验证某个参数到底有没有生效

## 九、如何查看一个参数的可调范围

当前 `HikCamera` 已经提供了范围读取方法：

- `get_int_node(node_name)`
- `get_float_node(node_name)`

示例：

```python
from mvsCamera import CameraLocator, HikCamera

cam = HikCamera(locator=CameraLocator(serial_number="DA9184658"))
cam.open()

print(cam.get_float_node("ExposureTime"))
print(cam.get_float_node("Gain"))
print(cam.get_float_node("AcquisitionFrameRate"))
print(cam.get_int_node("Width"))
print(cam.get_int_node("Height"))
print(cam.get_int_node("OffsetX"))
print(cam.get_int_node("OffsetY"))

cam.close()
```

典型返回信息包括：

- `current`
- `min`
- `max`
- `inc`

其中最关键的是：

- `min`
  - 最小值
- `max`
  - 最大值
- `inc`
  - 步进值

ROI 参数尤其依赖 `inc`。  
例如有的相机要求宽度必须每次按 `8` 或 `16` 递增，这时你不能随便写 `1919`。

## 十、当前项目配置文件如何落地使用

当前项目的多路 MVS 配置文件在：

- [configs/runtime.multi_camera.mvs.json](/Users/yyh/code/poseDetect/configs/runtime.multi_camera.mvs.json)

里面每个相机大概长这样：

```json
{
  "name": "cam_0",
  "source": "mvs://sn/DA9184658?timeout_ms=1000",
  "seat_regions": {
    "overall": {
      "x1": 1116.0,
      "y1": 332.0,
      "x2": 2722.0,
      "y2": 2911.0
    }
  }
}
```

如果你准备开始做现场调参，可以从下面这种写法起步：

```json
{
  "name": "cam_0",
  "source": "mvs://sn/DA9184658?timeout_ms=1000&trigger=continuous&pixel_format=bgr8&exposure_auto=off&exposure_time=5000&gain_auto=off&gain=6&frame_rate_enable=true&fps=10",
  "seat_regions": {
    "overall": {
      "x1": 1116.0,
      "y1": 332.0,
      "x2": 2722.0,
      "y2": 2911.0
    }
  }
}
```

注意：

- 如果你调整了 ROI，`seat_regions` 很可能要重新检查。
- 如果你只调整曝光、增益、帧率，`seat_regions` 通常不需要重画。

## 十一、小白最常见的坑

### 1. 手动曝光前没先关闭自动曝光

错误思路：

```text
...&exposure_time=6000
```

更稳妥的写法：

```text
...&exposure_auto=off&exposure_time=6000
```

### 2. 手动增益前没先关闭自动增益

错误思路：

```text
...&gain=10
```

更稳妥的写法：

```text
...&gain_auto=off&gain=10
```

### 3. 改帧率时没启用帧率控制

更稳妥的写法：

```text
...&frame_rate_enable=true&fps=10
```

### 4. 用设备序号做长期配置

`mvs://0` 很适合测试，但不适合长期固定部署。  
多相机情况下推荐改成 `mvs://sn/...`。

### 5. 改了 ROI 却忘了检查标注区域

ROI 会改变图像尺寸和坐标系。  
如果你改了 `width`、`height`、`offset_x`、`offset_y`，记得重新确认 `seat_regions`。

### 6. 以为所有相机都支持同一组节点

同一套代码可以支持很多型号，但不同机型并不一定都支持完全一样的参数范围。  
现场联调时要用 `get_int_node()` 和 `get_float_node()` 看真实可用范围。

## 十二、推荐阅读顺序

如果你要系统理解这个包，建议按下面顺序读：

1. [src/mvsCamera/__init__.py](/Users/yyh/code/poseDetect/src/mvsCamera/__init__.py)
2. [src/mvsCamera/frame_source.py](/Users/yyh/code/poseDetect/src/mvsCamera/frame_source.py)
3. [src/mvsCamera/camera_controller.py](/Users/yyh/code/poseDetect/src/mvsCamera/camera_controller.py)
4. [src/mvsCamera/pixel_utils.py](/Users/yyh/code/poseDetect/src/mvsCamera/pixel_utils.py)
5. [src/media_inputs/core.py](/Users/yyh/code/poseDetect/src/media_inputs/core.py)
6. [src/mvsCamera/sdk/MvCameraControl_class.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/MvCameraControl_class.py)
7. [src/mvsCamera/sdk/MvCameraControl_header.py](/Users/yyh/code/poseDetect/src/mvsCamera/sdk/MvCameraControl_header.py)

原因很简单：

- 前面几个文件回答“怎么用”
- 后面几个文件回答“底层怎么实现”

## 十三、快速结论

如果你只记住最关键的几点，可以先记下面这些：

1. 日常改配置，优先看 `frame_source.py`
2. 真正控制曝光、增益、帧率、ROI，优先看 `camera_controller.py`
3. 多相机场景尽量用 `sn` 而不是 `index`
4. 手动调曝光前先关自动曝光
5. 手动调增益前先关自动增益
6. 改 ROI 后记得检查标注坐标
7. 不确定取值范围时，用 `get_int_node()` / `get_float_node()` 先查

如果后面你要继续扩展这个包，最常见的新增方向是：

- 补更多可配置节点
- 增加配置文件模板
- 增加相机参数自检脚本
- 增加现场排障文档
