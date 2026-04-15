# 项目结构与配置规范建议

本文档用于约束当前项目后续迭代时的目录结构、配置文件组织方式和命名习惯，目标是让项目继续保持“规则驱动的工业动作检测骨架”这一方向，而不是重新退化成杂乱脚本集合。

## 1. 当前推荐的项目定位

当前项目建议保持为三层结构：

1. `seat_inspection`
2. `media_inputs`
3. `mvsCamera`

职责划分建议固定如下：

- `seat_inspection`：业务主流程、推理、规则、状态机、报表
- `media_inputs`：统一媒体输入抽象
- `mvsCamera`：海康工业相机 SDK 接入

不要把相机逻辑、推理逻辑、规则逻辑重新混写在一个脚本里。

## 2. 推荐目录结构

建议长期维持如下结构：

```text
poseDetect/
├── configs/
│   ├── runtime.example.json
│   ├── runtime.multi_camera.example.json
│   ├── runtime.<site-or-line>.json
│   └── seat_regions.<camera-or-line>.json
├── docs/
│   ├── VIDEO_INFERENCE_GUIDE.md
│   ├── MVS_CAMERA_USAGE.md
│   ├── PROJECT_CAPABILITY_ASSESSMENT.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── PROJECT_STRUCTURE_AND_CONFIG_GUIDE.md
├── src/
│   ├── media_inputs/
│   ├── mvsCamera/
│   └── seat_inspection/
├── tests/
├── outputs/
├── datasets/
└── runs/
```

说明：

- `outputs/`：只放推理结果、预览视频、单图标注结果
- `datasets/`：只放采集后的数据集和标注
- `runs/`：只放训练输出
- `configs/`：只放运行配置和区域配置
- `docs/`：只放说明文档，不放业务数据

## 3. `src/seat_inspection` 内部职责建议

建议继续保持下面的分层：

- `main.py`：统一 CLI 入口
- `runtime_config.py`：配置加载与兼容转换
- `config.py`：配置 dataclass 定义
- `training.py`：训练入口封装
- `dataset_capture.py`：采集与伪标注
- `inference.py`：单路、多路、单图推理编排
- `pipeline.py`：单帧处理流水线
- `rules.py`：动作规则识别
- `state_machine.py`：流程状态机
- `reporting.py`：JSON 输出
- `visualization.py`：可视化输出
- `calibration.py`：区域标定

建议不要再新增：

- 与 `main.py` 重复的轻量 CLI
- 与 `media_inputs` 重复的旧输入封装
- 与 `rules.actions` 平行存在的第二套动作配置模型

## 4. 配置文件组织建议

当前项目后续应以“一个工位或一种部署场景对应一份 runtime 配置”为原则。

推荐做法：

- `runtime.example.json`：仓库主示例
- `runtime.multi_camera.example.json`：多相机场景示例
- `runtime.line_a.json`：产线 A 配置
- `runtime.station_3.json`：工位 3 配置

不建议：

- 把不同工位的配置混到一份 JSON 里
- 把实验参数直接硬编码进 Python 文件
- 把临时调参版本直接覆盖主示例文件

## 5. 区域配置建议

如果后续项目增多，建议把区域标定从完整 runtime 里拆出来，单独保存。

推荐命名：

- `configs/seat_regions.front.json`
- `configs/seat_regions.side.json`
- `configs/seat_regions.line_a_front.json`

推荐原则：

- 同一相机、同一安装位，区域配置单独版本化
- 区域配置和动作规则配置分开维护
- runtime 配置引用区域配置内容时，优先通过复制固定内容或后续引入 include 机制

当前仓库还没有 include 机制，因此短期内仍可直接内嵌在 runtime JSON 中。

## 6. 动作配置规范建议

当前项目已经统一到 `rules.actions`。

建议后续所有动作都通过该字段定义，不再新增平行字段。

每个动作项建议统一包含：

- `name`
- `kind`
- `region`
- `hold_frames`
- `wrist_margin`
- `min_wrist_count`
- `lift_ratio_threshold`，仅 `lift_region` 需要
- `enabled`

命名建议：

- 动作名使用 `snake_case`
- 动作名要体现“行为 + 目标区域”

推荐示例：

- `touch_side_surface`
- `lift_seat_bottom`
- `touch_bottom_surface`

不推荐示例：

- `action1`
- `touch`
- `step_a`

## 7. 状态机配置规范建议

`state_machine.steps` 的职责是描述工艺流程，不是描述动作识别逻辑。

因此建议：

- `rules.actions` 负责定义“能识别什么动作”
- `state_machine.steps` 负责定义“动作出现的顺序要求”

每个步骤建议只包含：

- `name`
- `action`
- `min_frames`

命名建议：

- 步骤名描述业务步骤，不描述算法细节

推荐示例：

- `touch_side`
- `lift_bottom`
- `final_check`

## 8. 示例配置文件职责建议

建议后续示例文件保持明确职责，不要互相混淆。

- `configs/runtime.example.json`
  作用：单路主示例，覆盖训练、采集、视频推理、单图推理

- `configs/runtime.multi_camera.example.json`
  作用：多相机主示例

- `docs/runtime.video.example.json`
  作用：给文档配套的视频推理最小样例

建议：

- `configs/` 下示例更完整
- `docs/` 下示例更小、更容易复制修改

## 9. 输出文件规范建议

建议统一输出目录，不把运行产物散落到仓库各处。

推荐：

- `outputs/action_results.json`
- `outputs/action_preview.mp4`
- `outputs/image_action_result.json`
- `outputs/image_action_preview.jpg`
- `outputs/multi_camera_action_results.json`
- `outputs/multi_camera_action_preview.mp4`

不建议：

- 在 `docs/` 中写入运行结果
- 在仓库根目录到处生成 `*.json`、`*.mp4`

## 10. 测试规范建议

当前项目测试已经覆盖核心主链，建议继续保持：

- 每新增一个配置兼容逻辑，补 `runtime_config` 测试
- 每新增一个动作类型，补 `rules` 测试
- 每新增一个流程行为，补 `state_machine` 测试
- 每新增一种输入源语法，补 `media_inputs` 或 `mvs` 测试

不要只改示例配置而不补测试。

## 11. 后续扩展时的边界建议

如果后续要扩展新能力，建议按下面原则判断放在哪里：

- 输入源相关：放 `media_inputs` 或 `mvsCamera`
- 业务推理编排：放 `inference.py` / `pipeline.py`
- 动作识别逻辑：放 `rules.py`
- 工艺流程逻辑：放 `state_machine.py`
- 输出格式：放 `reporting.py`

不建议把“临时需求”直接堆进 `main.py`。

## 12. 一句话结论

当前项目后续最重要的不是继续加文件，而是继续保持：

**单一入口、单一动作配置模型、清晰模块边界、统一配置文件组织方式。**
