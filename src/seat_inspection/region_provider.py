"""座椅区域提供层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .schemas import BoundingBox, SeatRegions
from .seat_detection import SeatDetection, SeatDetector


class SeatRegionProvider(Protocol):
    """座椅区域提供协议。"""

    mode: str

    def get_regions(self, frame: Any) -> SeatRegions:
        ...


@dataclass(slots=True)
class FixedSeatRegionProvider:
    """固定 ROI 座椅区域提供器。"""

    seat_regions: SeatRegions
    mode: str = "fixed_roi"

    def get_regions(self, frame: Any) -> SeatRegions:
        """返回固定标定区域。"""
        del frame
        return self.seat_regions


@dataclass(slots=True)
class DetectedSeatRegionProvider:
    """基于独立座椅检测模型的区域提供器。

    检测到整体座椅框后，会按模板比例映射出 side/bottom 子区域。
    如果当前帧检测失败，则自动回退到模板区域。
    """

    template_regions: SeatRegions
    detector: SeatDetector
    confidence: float
    iou: float
    device: str
    mode: str = "seat_model"

    def get_regions(self, frame: Any) -> SeatRegions:
        """根据当前帧检测结果动态生成区域。"""
        detection = self.detector.detect(
            frame,
            confidence=self.confidence,
            iou=self.iou,
            device=self.device,
        )
        if detection is None:
            return self.template_regions
        return map_template_regions_to_detection(self.template_regions, detection)


def map_template_regions_to_detection(
    template_regions: SeatRegions,
    detection: SeatDetection,
) -> SeatRegions:
    """把模板子区域按比例映射到当前检测到的座椅框。"""
    template_overall = template_regions.overall
    detected_overall = detection.bounding_box
    return SeatRegions(
        overall=detected_overall,
        side_surface=_map_box(template_regions.side_surface, template_overall, detected_overall),
        bottom_surface=_map_box(template_regions.bottom_surface, template_overall, detected_overall),
    )


def _map_box(
    box: BoundingBox,
    template_overall: BoundingBox,
    detected_overall: BoundingBox,
) -> BoundingBox:
    template_width = max(1.0, template_overall.width)
    template_height = max(1.0, template_overall.height)
    width_scale = detected_overall.width / template_width
    height_scale = detected_overall.height / template_height
    return BoundingBox(
        x1=detected_overall.x1 + (box.x1 - template_overall.x1) * width_scale,
        y1=detected_overall.y1 + (box.y1 - template_overall.y1) * height_scale,
        x2=detected_overall.x1 + (box.x2 - template_overall.x1) * width_scale,
        y2=detected_overall.y1 + (box.y2 - template_overall.y1) * height_scale,
    )
