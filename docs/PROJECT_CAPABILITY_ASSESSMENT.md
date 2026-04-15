# 当前项目能力评估

本文档基于当前仓库中的实际代码、CLI 入口、配置结构与测试覆盖进行评估，不以早期规划为准。

## 1. 当前项目本质上是什么

当前项目已经不是单纯的 YOLO 训练脚本，而是一个可运行的“固定机位动作检测骨架系统”。

它采用的是：

1. `YOLO Pose` 提取人体关键点
2. `seat_regions` 描述座椅区域
3. `rules.actions` 定义动作规则
4. `state_machine.steps` 定义工艺流程顺序
5. `reporting` 输出逐帧和最终结果

也就是说，当前主路线并不是“训练一个端到端动作分类模型”，而是“姿态估计 + 几何规则 + 流程状态机”。

## 2. 当前已经能实现的功能

### 2.1 CLI 能力

当前统一入口支持：

- `train`
- `collect`
- `calibrate-regions`
- `infer`
- `infer-multi`
- `infer-image`

对应入口见：

- [src/seat_inspection/main.py](/Users/yyh/code/poseDetect/src/seat_inspection/main.py)

### 2.2 数据采集与伪标注

当前可以从以下来源采集图像：

- 视频文件
- 普通摄像头
- `mvs://...` 工业相机

并自动：

- 抽帧
- 用当前姿态模型生成 YOLO pose 标签
- 划分 `train/val`
- 生成 `dataset.yaml`
- 生成采集清单 `capture_manifest.json`

对应实现见：

- [src/seat_inspection/dataset_capture.py](/Users/yyh/code/poseDetect/src/seat_inspection/dataset_capture.py)

### 2.3 区域标定

当前支持从图片、视频、摄像头、MVS 相机读取一帧，交互式标定：

- `overall`
- `side_surface`
- `bottom_surface`

对应实现见：

- [src/seat_inspection/calibration.py](/Users/yyh/code/poseDetect/src/seat_inspection/calibration.py)

### 2.4 单路视频推理

当前支持：

- 打开视频流或相机流
- 运行 YOLO Pose
- 基于规则识别动作
- 推进状态机
- 导出 JSON 报告
- 导出标注视频
- 可选实时窗口显示

对应实现见：

- [src/seat_inspection/inference.py](/Users/yyh/code/poseDetect/src/seat_inspection/inference.py)

### 2.5 单图推理

当前支持对单张图片执行：

- 姿态估计
- 动作判断
- 状态输出
- 标注图导出

### 2.6 多相机融合推理

当前支持：

- 多路相机并行推理
- 动作级融合
- `any / all / majority` 融合策略
- 多画面拼接可视化
- 融合后的流程状态输出

对应实现见：

- [src/seat_inspection/multi_camera.py](/Users/yyh/code/poseDetect/src/seat_inspection/multi_camera.py)
- [src/seat_inspection/inference.py](/Users/yyh/code/poseDetect/src/seat_inspection/inference.py)

### 2.7 输入源统一抽象

当前项目已经把这些输入源统一到一个标准帧接口：

- 图片
- 视频
- 普通摄像头
- MVS 工业相机

对应实现见：

- [src/media_inputs/core.py](/Users/yyh/code/poseDetect/src/media_inputs/core.py)

### 2.8 海康 MVS 工业相机接入

当前支持：

- `mvs://0`
- `mvs://sn/...`
- `mvs://ip/...`
- `mvs://mac/...`
- `timeout_ms`
- `trigger`
- `pixel_format`

对应实现见：

- [src/mvsCamera/frame_source.py](/Users/yyh/code/poseDetect/src/mvsCamera/frame_source.py)

### 2.9 可配置动作规则

当前规则系统已经统一为 `rules.actions` 单入口。

目前已实现的动作类型：

- `touch_region`
- `lift_region`

每个动作可配置：

- `name`
- `kind`
- `region`
- `hold_frames`
- `wrist_margin`
- `min_wrist_count`
- `lift_ratio_threshold`

对应实现见：

- [src/seat_inspection/config.py](/Users/yyh/code/poseDetect/src/seat_inspection/config.py)
- [src/seat_inspection/rules.py](/Users/yyh/code/poseDetect/src/seat_inspection/rules.py)

### 2.10 流程状态机

当前支持：

- 顺序步骤定义
- 每步最少持续帧数
- `OK / NG / PENDING`
- 完成步骤记录
- 事件日志输出

对应实现见：

- [src/seat_inspection/state_machine.py](/Users/yyh/code/poseDetect/src/seat_inspection/state_machine.py)

## 3. 当前相对完善的部分

如果从“工程闭环是否成型”的角度看，当前比较完善的是这些模块：

### 3.1 推理主链路

已经形成完整闭环：

- 输入源打开
- 姿态推理
- 规则识别
- 状态机推进
- 报告输出
- 可视化输出

这条主链路已经可以直接支撑 PoC 或小范围现场验证。

### 3.2 配置驱动能力

当前项目大部分能力都已经通过 JSON 配置驱动，而不是写死在代码里。

包括：

- 动作列表
- 状态机步骤
- 单路推理
- 多相机推理
- 图像推理
- 采集
- 训练

### 3.3 规则引擎和状态机

这部分不是占位代码，已经有：

- 连续帧判定
- 缺帧容忍
- 动作原因
- 诊断字段
- 顺序流程推进
- 最终 OK/NG 输出

### 3.4 输入层与工业相机接入

输入抽象层清晰，MVS 接入也不是“预留字段”，而是已经落到了可用代码路径中。

### 3.5 测试覆盖

当前测试覆盖了以下关键区域：

- 运行配置解析
- 规则判定
- 状态机
- 多相机融合
- 数据采集
- 标定
- 媒体输入
- MVS 源解析
- 主入口逻辑

当前仓库测试结果为：

- `.venv/bin/pytest -q`
- `36 passed`

## 4. 当前不算完善，但已具备基础实现的部分

### 4.1 训练能力

训练入口已经有，但它更像“能力补充”，不是当前主流程的中心。

当前仓库可以训练 YOLO Pose，但仓库本身并没有提供：

- 真实产线数据集
- 评估脚本
- 指标报表
- 模型版本管理
- 最佳实践训练流程

所以训练能力存在，但完成度明显低于推理与规则主链。

### 4.2 独立人体检测与座椅检测

代码支持：

- `person_model_path`
- `seat_model_path`

但这两项更接近可扩展能力，不是当前最成熟的默认使用路线。

### 4.3 多相机

多相机功能是可运行的，但它的现场稳定性仍取决于：

- 相机时间同步质量
- 机位设计
- 网络和带宽
- 工业现场部署环境

所以它的代码功能已经具备，但落地复杂度高于单路方案。

## 5. 当前项目需求下，是否真的需要训练模型

结论先说：

**对当前项目的主需求而言，通常不需要先训练模型。**

更准确地说：

- 如果你的目标是先完成固定机位下的 SOP 动作检测验证
- 且动作类型主要是“触摸某区域”“抬起某区域”
- 且画面中的人体姿态能被通用 YOLO Pose 稳定识别

那么当前阶段的关键工作不是训练，而是：

1. 选一个可用的通用 pose 权重
2. 标定好 `seat_regions`
3. 配置好 `rules.actions`
4. 配置好 `state_machine.steps`
5. 用真实视频调阈值

也就是说，当前项目更适合先走：

**规则校准优先，训练后置。**

## 6. 为什么当前阶段通常不需要训练

### 6.1 当前识别目标是“简单几何动作”

当前主动作是：

- 手触达某个区域
- 双手在某区域并向上抬起

这类动作本质上依赖的是：

- 手腕位置
- 肩髋位置
- 区域位置关系

它们更适合通过：

- 通用姿态模型
- 区域约束
- 阈值规则

来完成，而不是一开始就做专门训练。

### 6.2 固定机位场景天然适合规则方案

如果机位固定、座椅位置稳定，那么：

- ROI 可标定
- 动作顺序可配置
- 判定逻辑可解释
- 联调成本低

这时训练一个专用动作模型未必比规则更划算。

### 6.3 训练的真实成本比“加一个训练入口”高得多

真正训练可上线的模型，通常还需要：

- 采集大量真实产线样本
- 做人工标注或校正
- 设计验证集
- 跑精度评估
- 做版本对比
- 处理不同人、不同光照、不同工装带来的域偏移

对当前需求来说，这个投入未必是第一优先级。

## 7. 什么时候才真正需要训练

当出现以下情况时，才建议把训练提到前面：

### 7.1 通用 YOLO Pose 在现场识别不稳定

例如：

- 手腕点经常漂移
- 关键点丢失严重
- 工人姿态被设备遮挡
- 特殊工装导致人体关键点识别偏差大

### 7.2 现场动作细节超出简单规则表达能力

例如：

- 动作差异很细微
- 仅靠区域触达无法区分“正确/错误动作”
- 需要识别复杂时序行为

### 7.3 座椅或目标位置变化较大

如果固定 ROI 不够用了，且通用检测模型也不稳定，那么就可能需要：

- 训练座椅检测模型
- 甚至训练更贴近业务的姿态/动作模型

### 7.4 需要显著提高鲁棒性

例如要覆盖：

- 多班组
- 多工位
- 多机位
- 多种光照
- 多种工装差异

这时训练会从“可选项”变成“必要项”。

## 8. 当前更合理的实施顺序

对于当前项目，建议按下面顺序推进：

1. 先用现成 pose 权重跑通单路视频推理
2. 标定 `seat_regions`
3. 调整 `rules.actions`
4. 调整 `state_machine.steps`
5. 用真实视频验证误报和漏报
6. 只有当通用姿态模型不够用时，再启动训练

这是当前项目性价比最高的路线。

## 9. 最终判断

如果站在“当前需求是否必须训练模型”的角度，结论是：

**不是必须。**

如果站在“未来要不要训练更贴近现场的模型”的角度，结论是：

**可能需要，但那应该建立在当前规则方案已经跑过一轮现场验证之后。**

换句话说：

- 当前最重要的是把推理、标定、规则和流程跑通
- 训练应当是第二阶段优化手段
- 不应在还没验证规则方案之前就把训练当成主任务
