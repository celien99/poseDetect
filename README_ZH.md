# poseDetect 中文说明

当前仓库只保留一种工作模式：多相机、多机位协同座椅检测。

## 一、当前保留的能力

当前主链路固定为：

1. 同时打开多路视频流或 MVS 工业相机流；
2. 每路相机分别执行人体姿态推理；
3. 每路相机分别执行动作规则判定；
4. 跨机位做动作融合，支持 `any`、`all`、`majority`；
5. 用融合结果推进统一状态机，并输出融合后的 JSON 报告。

以下能力已经从项目中移除：

- 单相机推理
- 单图推理
- 区域交互标定
- 数据采集
- 模型训练

## 二、目录说明

- `src/seat_inspection/main.py`：仅保留 `infer` 入口
- `src/seat_inspection/inference.py`：多机位协同推理编排
- `src/seat_inspection/multi_camera.py`：跨机位动作融合
- `src/seat_inspection/pipeline.py`：单机位处理流水线
- `src/seat_inspection/rules.py`：动作规则判定
- `src/seat_inspection/state_machine.py`：融合后的流程状态管理
- `src/seat_inspection/reporting.py`：JSON 报告输出
- `src/media_inputs/`：统一视频流输入层
- `src/mvsCamera/`：海康 MVS 工业相机接入层
- `configs/runtime.multi_camera.example.json`：多机位示例配置
- `configs/runtime.multi_camera.mvs.json`：MVS 多机位示例配置

## 三、环境准备

建议使用 Python 3.10+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

## 四、启动方式

```bash
python -m seat_inspection infer --config configs/runtime.multi_camera.example.json
```

或：

```bash
seat-inspection infer --config configs/runtime.multi_camera.example.json
```

## 五、运行配置说明

当前只保留两个顶层配置块：

- `rules`
- `multi_camera_inference`

其中 `multi_camera_inference.cameras` 下每一路相机可以配置：

- `name`
- `source`
- `seat_regions`
- 可选的 `pose_model_path`
- 可选的 `person_model_path`
- 可选的 `seat_model_path`
- 可选的 `confidence`、`iou`、`device`

共享配置用于控制：

- 默认姿态模型
- 多机位融合策略
- 状态机流程
- 可视化输出
- 实时窗口显示

## 六、补充说明

- 支持 `mvs://...` 形式的工业相机源。
- 默认仍使用固定 `seat_regions`。
- 如需按座椅整体检测结果动态映射区域，仍可启用 `seat_model_path`。
