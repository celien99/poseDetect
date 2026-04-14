# Windows 测试机部署与联调说明

本文档用于指导你将当前项目部署到 Windows 测试机，并完成以下闭环验证：

1. 连接海康 MVS SDK
2. 打开工业相机并获取真实图像
3. 采集真实数据并自动生成 YOLO Pose 数据集
4. 使用生成的数据集训练模型
5. 使用模型回到真实相机做推理验证

---

## 1. 目标结果

完成后你应该能够执行以下命令：

```powershell
python -m seat_inspection collect --config configs/runtime.example.json
python -m seat_inspection train --config configs/runtime.example.json
python -m seat_inspection infer --config configs/runtime.example.json
```

---

## 2. 测试机准备

建议准备如下环境：

- Windows 10 或 Windows 11
- Python 3.10.x
- 海康 MVS SDK
- 已连接并可被 MVS 客户端识别的工业相机
- 可联网安装 Python 依赖，或提前准备离线包

建议目录结构：

```text
D:\projects\poseDetect
```

---

## 3. 安装海康 MVS SDK

### 3.1 安装 SDK

在测试机安装海康提供的 MVS SDK，并确认以下几点：

- 安装完成后可以打开海康的 MVS 客户端工具
- 在客户端中能看到相机设备
- 可以在客户端里正常打开相机并看到图像

如果这一步做不到，Python 项目也无法正常连通相机。

### 3.2 确认 DLL

当前项目的 SDK Python 封装会优先尝试加载：

```text
src\mvsCamera\MvCameraControl.dll
```

因此建议确认仓库中的这个文件存在。

如果仓库中的 DLL 与测试机 SDK 版本不一致，优先使用测试机上与驱动匹配的版本，并保持名称为：

```text
MvCameraControl.dll
```

---

## 4. 安装 Python 环境

在 PowerShell 中进入项目目录：

```powershell
cd D:\projects\poseDetect
```

确认 Python 版本：

```powershell
python --version
```

建议输出类似：

```text
Python 3.10.x
```

创建虚拟环境：

```powershell
python -m venv .venv
```

激活虚拟环境：

```powershell
.venv\Scripts\Activate.ps1
```

如果 PowerShell 限制脚本执行，可先执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

安装项目依赖：

```powershell
python -m pip install --upgrade pip
pip install -e .
```

如果你还想装测试依赖：

```powershell
pip install -e .[dev]
```

---

## 5. 首次导入检查

先确认项目入口和模块导入没有问题。

### 5.1 检查主命令

```powershell
python -m seat_inspection --help
```

预期能看到三个子命令：

- `collect`
- `train`
- `infer`

### 5.2 检查 mvsCamera 模块导入

```powershell
python -c "import mvsCamera.Basicdemo as demo; import mvsCamera.CamOperation_class as camop; import mvsCamera.MvCameraControl_class as sdk; print('ok')"
```

如果输出：

```text
ok
```

说明 Python 模块路径已经正常。

### 5.3 检查 DLL 加载

执行：

```powershell
python -c "from mvsCamera.MvCameraControl_class import MvCamCtrldll; print(type(MvCamCtrldll))"
```

如果不是异常退出，通常说明 DLL 至少已被找到。

---

## 6. 检查相机能否被枚举

建议先用最基础的 demo 做设备枚举：

```powershell
python -m mvsCamera.Basicdemo
```

运行后应至少看到设备数量和设备信息输出。

如果这里直接失败，优先检查：

- MVS 客户端是否能看到设备
- 网口工业相机 IP 是否和测试机网卡同网段
- USB 工业相机驱动是否正常
- `MvCameraControl.dll` 是否可加载

---

## 7. 配置 runtime.example.json

打开：

[configs/runtime.example.json](/Users/yyh/code/poseDetect/configs/runtime.example.json)

重点确认以下字段。

### 7.1 采集配置 `collection`

```json
"collection": {
  "pose_model_path": "yolo26n-pose.pt",
  "source": "mvs://0?timeout_ms=1000",
  "output_dir": "datasets/seat_pose",
  "dataset_yaml_path": "datasets/seat_pose/dataset.yaml",
  "confidence": 0.25,
  "iou": 0.45,
  "device": "cpu",
  "save_every_n_frames": 15,
  "max_images": 200,
  "train_split": 0.8,
  "random_seed": 42,
  "overwrite": true
}
```

说明：

- `source`
  `mvs://0` 表示第 0 号海康相机
- `timeout_ms`
  单帧读取超时时间，建议先用 `1000`
- `save_every_n_frames`
  每隔多少帧保存一张图，避免连续帧过密
- `max_images`
  本次最多采集多少张图，建议先用 50 到 200 跑通流程

### 7.2 训练配置 `training`

```json
"training": {
  "model_path": "yolo26n-pose.pt",
  "data_config": "datasets/seat_pose/dataset.yaml",
  "epochs": 50,
  "image_size": 640,
  "batch": 8,
  "device": "cpu",
  "project": "runs/seat_pose",
  "name": "baseline"
}
```

建议首次验证时：

- `epochs` 不要太大
- `batch` 先小一点
- 没有 NVIDIA GPU 时用 `cpu`

### 7.3 推理配置 `inference`

```json
"inference": {
  "pose_model_path": "yolo26n-pose.pt",
  "source": "mvs://0?timeout_ms=1000",
  "output_json_path": "outputs/action_results.json",
  "output_video_path": "outputs/action_preview.mp4",
  "device": "cpu",
  "save_visualization": true,
  "seat_regions": { ... }
}
```

注意：

- `seat_regions` 需要根据真实机位调
- 初次测试先保证能跑通，不必一次把区域框调到很准

---

## 8. 第一步：采集真实数据

执行：

```powershell
python -m seat_inspection collect --config configs/runtime.example.json
```

这个命令会做三件事：

1. 打开相机
2. 按抽帧策略保存图片
3. 用当前 pose 模型自动生成一版 YOLO pose 标签

成功后应生成：

```text
datasets\seat_pose\images\train
datasets\seat_pose\images\val
datasets\seat_pose\labels\train
datasets\seat_pose\labels\val
datasets\seat_pose\dataset.yaml
datasets\seat_pose\capture_manifest.json
```

建议你检查：

- 是否真的保存了图片
- 标签 `.txt` 是否与图片数量基本对应
- 是否至少有 train 和 val 两个目录内容

### 8.1 重要提醒

这里生成的是“自动伪标签”。

这能帮助流程先跑通，但如果你要认真训练模型，建议后续：

- 抽样检查标签质量
- 对明显错误标签进行人工修正

---

## 9. 第二步：训练模型

执行：

```powershell
python -m seat_inspection train --config configs/runtime.example.json
```

训练会读取：

```text
datasets\seat_pose\dataset.yaml
```

训练输出通常在：

```text
runs\seat_pose\baseline
```

重点看：

- 是否能正常开始 epoch
- 是否没有因为数据集路径、标签格式、空目录报错

如果只是验证流程，训练几轮能跑起来就说明链路已经通了。

---

## 10. 第三步：回到真实相机做推理

执行：

```powershell
python -m seat_inspection infer --config configs/runtime.example.json
```

成功后应生成：

```text
outputs\action_results.json
outputs\action_preview.mp4
```

你要重点确认：

- 相机是否能正常打开
- 推理是否持续出结果
- 可视化视频是否能正常保存
- JSON 是否正常写出

---

## 11. 推荐的首次联调顺序

建议按这个顺序来，不要一上来就直接训练：

1. 海康客户端确认相机可见
2. `python -m seat_inspection --help`
3. `python -m mvsCamera.Basicdemo`
4. `python -m seat_inspection collect --config configs/runtime.example.json`
5. 检查 `datasets/seat_pose`
6. `python -m seat_inspection train --config configs/runtime.example.json`
7. `python -m seat_inspection infer --config configs/runtime.example.json`

---

## 12. 常见问题排查

### 12.1 `Cannot find module mvsCamera...`

先确认你是在项目根目录下执行命令，并且已经做过：

```powershell
pip install -e .
```

### 12.2 `MvCameraControl.dll` 加载失败

检查：

- `src\mvsCamera\MvCameraControl.dll` 是否存在
- 海康 MVS SDK 是否安装完成
- Python 位数与 DLL 位数是否匹配

一般建议：

- Python 64 位
- 海康 SDK 64 位

### 12.3 相机枚举不到

检查：

- MVS 客户端中是否能看到设备
- 网口工业相机 IP 是否配置正确
- 是否使用了错误的设备序号，如 `mvs://1`

### 12.4 `collect` 没有生成任何标签

说明当前 `pose_model_path` 对真实场景的人体姿态识别效果太差，或者当前画面里没有被检测到的人。

可以尝试：

- 提高画面亮度和稳定性
- 调整相机角度
- 先用更通用的 pose 模型验证
- 适当降低 `confidence`

### 12.5 `train` 报数据集格式错误

检查：

- `dataset.yaml` 路径是否正确
- `images/train`、`labels/train` 是否一一对应
- 标签文件是否为空

---

## 13. 建议的真实落地方式

如果你的目标是后续真正回收真实数据训练模型，建议这样推进：

1. 先用 `collect` 跑通自动采集
2. 先采 50 到 200 张，确认链路正确
3. 人工抽查伪标签质量
4. 小规模训练验证
5. 再扩大到更长时间、更复杂姿态的数据采集
6. 最终建立自己的高质量训练集

---

## 14. 当前项目在测试机上的可行性结论

当前项目已经可以作为“Windows 测试机联调版本”使用，适合完成以下验证：

- SDK 是否可连通
- 相机是否可打开
- 是否能采真实数据
- 是否能生成 YOLO pose 数据集骨架
- 是否能开始训练
- 是否能回到真实相机做推理

但仍建议把它视为“联调验证版”，不是“已完成全部生产验证版”。

真实投产前仍需补：

- 伪标签人工校正
- 更稳定的数据采样策略
- 更准确的区域标定
- 更完整的异常处理和日志

