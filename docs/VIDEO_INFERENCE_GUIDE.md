# 视频推理操作文档

本文档说明如何在当前项目中输入一段视频，并输出动作流程检测结果。

## 1. 目标

当你提供一段视频后，当前项目可以输出：

- 逐帧动作判断结果
- 流程状态机结果
- 最终 `OK / NG`
- JSON 日志文件
- 可选的标注视频

当前项目适用于固定机位场景，尤其适合：

- 操作员在固定工位前执行标准动作
- 座椅或被检对象位置相对稳定
- 希望基于规则和流程状态机输出可解释结果

## 2. 运行前准备

建议使用 Python 3.10+ 虚拟环境。

安装依赖：

```bash
pip install -e .
```

如果需要运行测试：

```bash
pip install -e .[dev]
```

## 3. 推荐文件准备

你至少需要准备：

- 1 个视频文件，例如 `data/demo.mp4`
- 1 个可用的 YOLO Pose 模型，例如 `yolo26n-pose.pt`
- 1 份推理配置文件

建议先直接复制本仓库提供的模板：

- [docs/runtime.video.example.json](/Users/yyh/code/poseDetect/docs/runtime.video.example.json)

## 4. 配置文件怎么改

视频推理最少要改下面这些字段：

### `inference.source`

改成你的视频路径，例如：

```json
"source": "data/demo.mp4"
```

### `inference.pose_model_path`

改成你当前可用的姿态模型路径，例如：

```json
"pose_model_path": "yolo26n-pose.pt"
```

### `inference.seat_regions`

这是当前最关键的配置。  
如果你的场景是固定机位，建议先使用固定 ROI 模式跑通。

你需要按视频中的实际座椅位置，填写：

- `overall`
- `side_surface`
- `bottom_surface`

例如：

```json
"seat_regions": {
  "overall": { "x1": 100, "y1": 100, "x2": 300, "y2": 320 },
  "side_surface": { "x1": 280, "y1": 130, "x2": 330, "y2": 260 },
  "bottom_surface": { "x1": 140, "y1": 220, "x2": 260, "y2": 330 }
}
```

### `rules.actions`

这里定义你要识别的动作。例如：

- `touch_side_surface`
- `lift_seat_bottom`

### `inference.state_machine.steps`

这里定义流程顺序。  
例如希望“先摸侧面，再抬底部”：

```json
"steps": [
  {
    "name": "touch_side",
    "action": "touch_side_surface",
    "min_frames": 2
  },
  {
    "name": "lift_bottom",
    "action": "lift_seat_bottom",
    "min_frames": 2
  }
]
```

## 5. 如何执行视频推理

在项目根目录执行：

```bash
python -m seat_inspection.main infer --config docs/runtime.video.example.json
```

如果你已经把配置另存为自己的文件，例如 `docs/runtime.video.demo.json`，则执行：

```bash
python -m seat_inspection.main infer --config docs/runtime.video.demo.json
```

## 6. 输出结果在哪里

默认输出：

- JSON：`outputs/action_results.json`
- 标注视频：`outputs/action_preview.mp4`

也可以在配置里自定义：

- `inference.output_json_path`
- `inference.output_video_path`

## 7. JSON 结果怎么看

输出 JSON 里重点看这几个部分：

### `summary.final_status`

最终流程结果，通常为：

- `OK`
- `NG`

### `summary.current_state`

流程最终状态，例如：

- `completed`
- `incomplete`
- `partial_completed`
- `no_action_detected`

### `inspection_result.completed_steps`

已经完成的流程步骤。

### `inspection_result.events`

流程事件日志，例如哪个步骤在哪一帧完成。

### `decisions`

逐帧动作判断结果。  
如果你要排查为什么某段视频没识别出来，优先看这里。

## 8. 标注视频怎么看

如果 `save_visualization=true`，会输出标注视频。

画面里一般会包含：

- 人体框
- 座椅整体框
- 侧面区域框
- 底部区域框
- 当前动作状态
- 当前流程状态
- 最终结果趋势

如果标注视频里的区域框位置明显不对，优先回去调整 `seat_regions`。

## 9. 两种常见模式

### 模式 A：固定 ROI

适合：

- 机位固定
- 座椅位置稳定
- 希望先快速跑通

配置方式：

- `seat_model_path = null`
- 手工设置 `seat_regions`

### 模式 B：座椅检测模型 + 模板映射

适合：

- 座椅在画面中有轻微移动
- 已经训练好了座椅检测模型

配置方式：

- `seat_model_path = "your_seat_model.pt"`
- 同时保留 `seat_regions` 作为模板和失败回退区域

说明：

当前实现会先检测整体座椅框，再把 `side_surface / bottom_surface` 按模板比例映射到当前帧。  
如果当前帧座椅检测失败，会自动回退到固定 ROI。

## 10. 常见问题

### 1）视频能跑，但是结果全是 `NG`

优先检查：

- `seat_regions` 是否标准
- 动作顺序是否和 `state_machine.steps` 一致
- `rules.actions` 阈值是否过严
- 人体关键点是否稳定

### 2）动作明明做了，但某一步不触发

优先检查：

- `hold_frames` 是否过大
- `min_frames` 是否过大
- `wrist_margin` 是否太小
- `lift_ratio_threshold` 是否太高

### 3）标注视频区域框不贴合座椅

优先检查：

- 固定 ROI 是否重新标定
- 是否需要启用 `seat_model_path`

### 4）视频里没有明显人体框

优先检查：

- `pose_model_path` 是否正确
- 画面分辨率是否过低
- 人体过小或遮挡严重

## 11. 推荐实操顺序

建议按下面顺序推进：

1. 先用固定 ROI 跑通一段视频
2. 看 `outputs/action_preview.mp4`，确认区域框和人体框基本正常
3. 再看 `outputs/action_results.json`，确认动作帧和流程步骤
4. 然后再调规则阈值
5. 最后如果固定 ROI 不稳定，再接 `seat_model_path`

## 12. 当前能力边界

当前项目已经支持：

- 视频输入
- 图片输入
- 普通摄像头输入
- MVS 工业相机输入
- 动作规则判断
- 流程状态机
- `OK / NG` 输出

但结果准确率仍依赖：

- 视频机位
- ROI 标定
- 模型质量
- 动作规则是否贴合真实工序

如果你后面有真实视频样例，最推荐的做法是基于该视频再单独微调：

- `seat_regions`
- `rules.actions`
- `state_machine.steps`

