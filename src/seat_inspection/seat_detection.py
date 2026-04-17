"""座椅检测层。

职责：
- 可选地加载独立的 YOLO 座椅检测模型
- 输出当前帧座椅整体区域
- 供区域提供层进一步映射出 side/bottom 子区域
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schemas import BoundingBox


@dataclass(slots=True)
class SeatDetection:
    """单个座椅检测结果。"""

    bounding_box: BoundingBox
    confidence: float


class SeatDetector:
    """独立座椅检测器。"""

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        self._model = None

    def detect(
        self,
        frame: Any,
        confidence: float,
        iou: float,
        device: str,
    ) -> SeatDetection | None:
        """使用独立模型执行座椅检测。"""
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
        return extract_primary_seat_detection(result)


def extract_primary_seat_detection(result: Any) -> SeatDetection | None:
    """从 YOLO 结果中提取置信度最高的座椅框。"""
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
        selected_index = int(confidences.argmax())
        confidence = float(confidences[selected_index])

    x1, y1, x2, y2 = xyxy[selected_index]
    return SeatDetection(
        bounding_box=BoundingBox(float(x1), float(y1), float(x2), float(y2)),
        confidence=confidence,
    )
