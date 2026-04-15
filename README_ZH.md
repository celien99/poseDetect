# poseDetect 中文说明

本项目是一个面向企业场景的座椅检测动作识别骨架工程，基于 Ultralytics YOLO Pose 模型构建，目标是对操作人员在座椅检测设备前的标准作业行为进行识别与校验。

## 一、项目目标

适用于固定机位工业场景，例如：

- 操作人员需要用手触摸座椅侧表面；
- 操作人员需要抬起座椅底部执行检测动作；
- 后续还可扩展更多 SOP 标准动作识别。

项目采用“姿态识别 + 区域标定 + 规则引擎”的方案，更适合工业现场落地，原因包括：

- 可解释性强，便于质检和审计；
- 阈值可调，适合现场反复标定；
- 比直接做黑盒动作分类更容易上线和维护；
- 便于后续与 MES、质检系统、日志平台集成。

## 二、整体架构

当前项目采用如下结构：

1. `YOLO Pose` 识别人体关键点；
2. `seat_regions` 定义座椅整体区域、侧面区域、底部区域；
3. `Rule Engine` 基于关键点和区域关系判定动作是否成立；
4. `Reporting` 输出逐帧 JSON 结果，便于追溯和集成；
5. `Main Entry` 统一管理训练与推理流程。

## 三、目录说明

- `src/seat_inspection/main.py`：项目主入口
- `src/seat_inspection/__main__.py`：包级启动入口，支持 `python -m seat_inspection`
- `src/seat_inspection/config.py`：训练、规则、推理配置定义
- `src/seat_inspection/runtime_config.py`：运行时 JSON 配置加载器
- `src/seat_inspection/training.py`：YOLO 姿态训练封装
- `src/seat_inspection/inference.py`：视频推理与动作识别流程
- `src/seat_inspection/rules.py`：工业动作规则判定核心
- `src/seat_inspection/engine.py`：动作识别引擎
- `src/seat_inspection/reporting.py`：JSON 报告输出
- `configs/runtime.example.json`：企业级运行配置示例
- `tests/test_rules.py`：规则判定测试
- `tests/test_runtime_config.py`：配置加载测试

## 四、环境准备

建议使用 Python 3.10+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

当前依赖包括：

- `ultralytics`
- `opencv-python`
- `pytest`

## 五、启动方式

### 1）推荐启动方式

由于当前项目采用 `src` 目录结构，推荐统一使用如下命令：

```bash
python -m seat_inspection collect --config configs/runtime.example.json
python -m seat_inspection train --config configs/runtime.example.json
```

执行推理：

```bash
python -m seat_inspection infer --config configs/runtime.example.json
```

执行单张图片判断：

```bash
python -m seat_inspection infer-image --config configs/runtime.example.json
```

### 2）为什么推荐这种方式

这样做的好处是：

- IDE 对包引用识别更稳定；
- 避免根目录脚本和包内模块重复；
- 更符合企业级 Python 项目结构；
- 后续更容易演进为安装包或服务化部署。

其中 `collect` 命令会从真实相机或视频源采集图像，并使用当前姿态模型自动生成一版 YOLO pose 数据集骨架。

## 六、运行配置说明

项目通过 `configs/runtime.example.json` 统一加载配置，主要包含三部分：

### `training`

用于模型训练，例如：

- `model_path`：YOLO pose 模型或权重路径
- `data_config`：训练数据 YAML
- `epochs`：训练轮数
- `image_size`：输入尺寸
- `batch`：批大小
- `device`：训练设备
- `project`：训练输出目录
- `name`：实验名称

### `rules`

用于动作规则判定，例如：

- `touch_hold_frames`：触摸侧面动作连续成立帧数
- `lift_hold_frames`：抬起底部动作连续成立帧数
- `wrist_to_surface_margin`：手腕接近侧面的容忍距离
- `wrist_to_bottom_margin`：手腕接近底部的容忍距离
- `lift_ratio_threshold`：抬起动作判定阈值

另外也支持 `rules.actions` 配置动作列表，当前内置两种动作类型：

- `touch_region`
- `lift_region`

### `inference`

用于推理运行，例如：

- `pose_model_path`：姿态模型路径
- `source`：视频文件、摄像头编号、视频流地址，或 `mvs://0` 这类海康 MVS 相机源
- `seat_regions`：固定机位下的座椅区域标定
- `output_json_path`：动作识别结果 JSON 输出路径
- `output_video_path`：可视化视频输出路径
- `save_visualization`：是否导出标注视频

### `image_inference`

用于单张图片动作判断，例如：

- `source`：图片路径
- `pose_model_path`：姿态模型路径
- `seat_regions`：区域标定
- `output_json_path`：单图动作结果输出
- `output_image_path`：单图可视化输出

其中如果接入 `src/mvsCamera` 适配后的工业相机，可使用类似下面的配置：

```json
{
  "source": "mvs://0?timeout_ms=1000"
}
```

## 七、训练说明

在训练之前，建议先采集真实产线数据：

```bash
python -m seat_inspection collect --config configs/runtime.example.json
```

该命令会自动生成：

- `datasets/seat_pose/images/train`
- `datasets/seat_pose/images/val`
- `datasets/seat_pose/labels/train`
- `datasets/seat_pose/labels/val`
- `datasets/seat_pose/dataset.yaml`
- `datasets/seat_pose/capture_manifest.json`

执行训练：

```bash
python -m seat_inspection train --config configs/runtime.example.json
```

说明：

- 训练实际调用 `src/seat_inspection/training.py`
- 当前适合作为企业项目初期训练入口
- 如果后续需要，可继续扩展多模型、多数据集、多环境配置

## 八、推理说明

执行推理：

```bash
python -m seat_inspection infer --config configs/runtime.example.json
```

推理流程包括：

1. 打开视频或摄像头；
2. 调用 YOLO Pose 提取人体关键点；
3. 根据 `seat_regions` 生成观测数据；
4. 调用规则引擎识别动作；
5. 输出逐帧 JSON 报告；
6. 如果启用了可视化，则导出标注视频。

输出结果包括：

- `outputs/action_results.json`
- `outputs/action_preview.mp4`（当 `save_visualization=true` 时）

## 九、企业落地建议

如果你要把这个项目真正用于产线，建议继续补充以下能力：

- 对 `collect` 自动生成的伪标签做人工复核；
- 座椅区域标定工具；
- 实时摄像头流推理；
- 动作事件按时间段聚合，而不是只输出逐帧结果；
- 识别失败告警和质检日志；
- 与 MES / QMS / 设备系统对接；
- 模型版本管理与灰度发布机制。

## 十、测试

如果当前环境已安装 `pytest`，可执行：

```bash
pytest
```

如果只想做快速语法校验，也可以执行：

```bash
python3 -m compileall src tests
```

## 十一、Windows 测试机部署说明

如果你要把项目放到 Windows 测试机，并连接海康工业相机，请优先阅读：

- [WINDOWS_TEST_GUIDE.md](WINDOWS_TEST_GUIDE.md)

## 十二、文档索引

如果你要快速了解当前项目各模块的职责、能力边界和接入方式，建议按下面顺序阅读：

- [docs/MVS_CAMERA_USAGE.md](docs/MVS_CAMERA_USAGE.md)：`src/mvsCamera` 的模块定位、可实现功能、`mvs://` 资源格式，以及如何接入 `seat_inspection`
- [docs/VIDEO_INFERENCE_GUIDE.md](docs/VIDEO_INFERENCE_GUIDE.md)：如何提供一份视频并输出动作流程检测结果
- [docs/runtime.video.example.json](docs/runtime.video.example.json)：视频推理配置模板，可直接复制修改

## 十三、当前推荐命令汇总

训练：

```bash
python -m seat_inspection train --config configs/runtime.example.json
```

采集：

```bash
python -m seat_inspection collect --config configs/runtime.example.json
```

推理：

```bash
python -m seat_inspection infer --config configs/runtime.example.json
```

单图判断：

```bash
python -m seat_inspection infer-image --config configs/runtime.example.json
```

查看帮助：

```bash
python -m seat_inspection --help
```


## 十四、可编辑安装说明

执行 `pip install -e .` 后，就不再需要 `PYTHONPATH=src`。

也可以直接使用命令行入口：

```bash
seat-inspection --help
seat-inspection train --config configs/runtime.example.json
seat-inspection infer --config configs/runtime.example.json
```
