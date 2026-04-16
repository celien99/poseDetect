# poseDetect 中文说明

`poseDetect` 是一个聚焦于多相机、多机位协同座椅检测的项目。

当前仓库保留两条主流程：

- 搭建流程：控制全部机位拍照，并对每个机位照片进行座椅区域标注
- 运行流程：执行多机位协同推理、跨机位融合动作、输出统一流程结果

以下旧能力已经移除：

- 单相机推理
- 单图推理
- 区域交互标定旧流程
- 数据采集
- 模型训练

## 一、项目当前能做什么

当前保留能力：

- 多机位协同推理
- 通过 `mvs://...` 接入工业相机
- 控制全部配置机位抓拍参考照片
- 对每个机位照片交互式标注 `seat_regions`
- 通过独立人体模型或姿态框识别操作人员
- 基于姿态和座椅区域判断是否在操作座椅
- 支持 `any`、`all`、`majority` 三种多机位融合策略
- 输出 `OK`、`NG`、`PENDING` 等流程状态
- 支持轻量主操作者跟踪与跨机位关联
- 导出包含动作片段和相机运行统计的 JSON 报告

当前内置动作类型：

- `touch_region`
- `lift_region`

## 二、当前能力边界

当前项目更适合固定工业机位场景。

- 默认座椅定位方式是配置好的 `seat_regions`
- 可选 `seat_model_path` 用于识别座椅整体框，并映射子区域
- 当前方案是规则驱动，不是端到端动作分类
- 多人场景鲁棒性已经增强，但仍属于轻量主操作者跟踪，不是完整的重识别系统

## 三、目录说明

- `src/seat_inspection/main.py`：CLI 入口
- `src/seat_inspection/camera_setup.py`：多机位拍照与座椅区域标注
- `src/seat_inspection/inference.py`：多机位推理编排
- `src/seat_inspection/pipeline.py`：单机位处理链路
- `src/seat_inspection/multi_camera.py`：跨机位动作融合
- `src/seat_inspection/tracking.py`：主操作者跟踪与跨机位关联
- `src/seat_inspection/rules.py`：规则动作判断
- `src/seat_inspection/state_machine.py`：流程状态推进
- `src/seat_inspection/reporting.py`：JSON 报告导出
- `src/media_inputs/`：统一输入流抽象
- `src/mvsCamera/`：海康 MVS 接入层
- `configs/multi_camera_setup.example.json`：搭建拍照配置示例
- `configs/runtime.multi_camera.example.json`：通用推理配置
- `configs/runtime.multi_camera.mvs.json`：多路 MVS 推理配置

## 四、环境准备

建议使用 Python 3.10+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

## 五、搭建流程：先拍照，再标注

当你还没有 `seat_regions` 时，建议按这个流程操作。

### 1. 准备拍照配置文件

示例：

```json
{
  "multi_camera_setup": {
    "cameras": [
      {
        "name": "front",
        "source": "mvs://0?timeout_ms=1000"
      },
      {
        "name": "side",
        "source": "mvs://1?timeout_ms=1000"
      }
    ]
  }
}
```

参考文件：

- `configs/multi_camera_setup.example.json`

### 2. 控制全部机位进行拍照

更省事的方式：一条命令走完整个配置流程

```bash
python -m seat_inspection setup-seat-regions \
  --setup-config configs/multi_camera_setup.example.json \
  --runtime-config configs/runtime.multi_camera.example.json \
  --capture-dir outputs/setup_capture \
  --annotation-output outputs/setup_capture/seat_regions.annotations.json
```

如果你不想原地覆盖推理配置，也可以输出到新文件：

```bash
python -m seat_inspection setup-seat-regions \
  --setup-config configs/multi_camera_setup.example.json \
  --runtime-config configs/runtime.multi_camera.example.json \
  --capture-dir outputs/setup_capture \
  --annotation-output outputs/setup_capture/seat_regions.annotations.json \
  --output-runtime-config configs/runtime.multi_camera.ready.json
```

这个引导式命令会连续完成：

- 打开全部已配置机位并抓拍
- 逐张照片标注座椅区域
- 把 `seat_regions` 自动写回推理配置

如果你希望分步骤操作，也可以继续使用下面的手动流程。

```bash
python -m seat_inspection capture-setup \
  --config configs/multi_camera_setup.example.json \
  --output-dir outputs/setup_capture
```

这个命令会：

- 打开全部已配置机位
- 每个机位抓拍一张参考图
- 保存 `front.jpg`、`side.jpg` 这类照片
- 生成 `capture_manifest.json`

### 3. 对每个机位照片标注座椅区域

```bash
python -m seat_inspection annotate-setup \
  --capture-dir outputs/setup_capture \
  --output outputs/setup_capture/seat_regions.annotations.json
```

对每张照片，工具会依次要求你框选：

1. `overall`
2. `side_surface`
3. `bottom_surface`

输出文件中会包含：

- 每个机位自己的 `seat_regions`
- 可直接复制的 `multi_camera_inference_patch`

### 4. 把标注结果自动写回推理配置

原地更新推理配置：

```bash
python -m seat_inspection apply-setup \
  --annotations outputs/setup_capture/seat_regions.annotations.json \
  --runtime-config configs/runtime.multi_camera.example.json
```

如果你不想原地覆盖，也可以输出到新文件：

```bash
python -m seat_inspection apply-setup \
  --annotations outputs/setup_capture/seat_regions.annotations.json \
  --runtime-config configs/runtime.multi_camera.example.json \
  --output configs/runtime.multi_camera.ready.json
```

这个命令会按机位 `name` 匹配，并把标注结果写回：

- `multi_camera_inference.cameras[i].seat_regions`

## 六、推理流程

完成区域配置后，执行多机位协同推理：

```bash
python -m seat_inspection infer --config configs/runtime.multi_camera.example.json
```

或：

```bash
seat-inspection infer --config configs/runtime.multi_camera.example.json
```

## 七、运行配置说明

当前推理配置只保留两个顶层配置块：

- `rules`
- `multi_camera_inference`

其中 `multi_camera_inference.cameras` 下每一路机位可配置：

- `name`
- `source`
- `seat_regions`
- 可选 `pose_model_path`
- 可选 `person_model_path`
- 可选 `seat_model_path`
- 可选 `confidence`
- 可选 `iou`
- 可选 `device`

共享多机位配置包括：

- 默认姿态模型
- 融合策略
- 最低活跃相机数量
- 连续读帧失败容忍次数
- 流程状态机
- 实时窗口配置
- 可视化输出配置

## 八、`seat_regions` 应该怎么画

- `overall`：当前机位画面中完整可见的座椅主体
- `side_surface`：用于判断“触摸侧面”的操作区域
- `bottom_surface`：用于判断“托起/抬起底部”的操作区域

建议：

- 框不要画得太大，避免带入太多背景
- `side_surface` 和 `bottom_surface` 应该按真实动作区域分别标
- 每个机位都要单独标，因为视角不同
- 如果机位固定，一次标定后通常可以长期复用

## 九、输出内容

当前导出的融合 JSON 报告包含：

- 逐帧融合动作结果
- 动作原因统计
- 连续动作片段
- 流程最终状态
- 每帧参与融合的活跃机位列表
- 统一主操作者关联 ID
- 每路相机运行统计信息

启用可视化后，画面中还会显示：

- 座椅区域框
- 被选中的主操作者框和轨迹 ID
- 融合后的操作者关联 ID
- 掉帧或离线机位的占位画面

## 十、测试

```bash
.venv/bin/pytest -q
```

当前测试覆盖：

- 配置解析
- 拍照与标注流程
- 输入流标准化
- 规则判断
- 流水线断帧处理
- 多机位融合
- 报告输出
- 主操作者跟踪
- 多机位主流程联调

## 十一、文档策略

当前仓库以 README 为唯一真实文档入口。

- `README.md`：英文说明
- `README_ZH.md`：中文说明
- 旧的独立文档已经全部移除
