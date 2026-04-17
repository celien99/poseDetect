# 汽车座椅状态检测

### 一、核心思路

#### YOLO负责“找东西”, 传统视觉负责“算状态”

也就是：

```text
检测（YOLO） ≠ 识别状态
状态判断 = 几何 + ROI + 规则
```

### 二、整体架构

```text
    相机输入
    ↓
    YOLO（人 + 座椅检测）
    ↓
    ROI裁剪（座椅区域）
    ↓
    座椅状态分析（核心）
    ↓
    状态机（行为判断）
    ↓
    输出（是否合规）
```

### 三、座椅状态检测(核心实现)

你要识别:

- 左右旋转
- 前后翻转
- 是否被抬起

👉 全部可以用 几何 + 边缘 实现

</br>

#### Step1: ROI裁剪

```python
seat_roi = frame[y1:y2, x1:x2]
```

👉 降低干扰（人、背景）

</br>

#### Step2: 边缘提取

使用 Canny Edge Detection:

```python
edges = cv2.Canny(gray, 50, 150)
```

👉 提取座椅轮廓

#### Step3: 直线检测

使用 Hough Transform:

```python
lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50)
```

👉 提取座椅轮廓
