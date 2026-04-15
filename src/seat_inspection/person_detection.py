"""人体检测层。

职责：
- 可选地加载独立的人体检测模型
- 在未提供独立模型时，复用姿态模型结果中的人体框
"""

from __future__ import annotations

from typing import Any

from .schemas import BoundingBox, PersonDetection


class PersonDetector:
    """人体检测器。

    如果传入独立 `person_model_path`，则优先使用独立模型。
    否则可通过 `extract_from_pose_result()` 从 YOLO Pose 输出中提取主人体框。
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        self._model = None

    @property
    def enabled(self) -> bool:
        """返回是否启用了独立人体检测模型。"""
        return self.model_path is not None

    def detect(
        self,
        frame: Any,
        confidence: float,
        iou: float,
        device: str,
    ) -> PersonDetection | None:
        """使用独立模型执行人体检测。"""
        if self.model_path is None:
            return None

        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.model_path)

        result = self._model.predict(
            frame,
            conf=confidence,
            iou=iou,
            device=device,
            verbose=False,
        )[0]
        return extract_primary_person_detection(result)

    def extract_from_pose_result(self, pose_result: Any) -> PersonDetection | None:
        """从姿态模型结果中提取主人体框。"""
        return extract_primary_person_detection(pose_result)


def extract_primary_person_detection(result: Any) -> PersonDetection | None:
    """从 YOLO 结果中提取置信度最高的人体框。"""
    boxes = getattr(result, "boxes", None)
    if boxes is None or getattr(boxes, "xyxy", None) is None:
        return None

    xyxy = boxes.xyxy.cpu().numpy()
    if len(xyxy) == 0:
        return None

    selected_index = 0
    confidence = 1.0
    if boxes.conf is not None:
        confidences = boxes.conf.cpu().numpy()
        selected_index = max(range(len(confidences)), key=lambda index: float(confidences[index]))
        confidence = float(confidences[selected_index])

    x1, y1, x2, y2 = xyxy[selected_index]
    return PersonDetection(
        bounding_box=BoundingBox(float(x1), float(y1), float(x2), float(y2)),
        confidence=confidence,
    )
