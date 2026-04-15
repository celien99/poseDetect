"""目标选择辅助函数。"""

from __future__ import annotations

from math import hypot

from .schemas import BoundingBox


def select_primary_box_index(
    xyxy: list[list[float]] | tuple[tuple[float, ...], ...],
    confidences: list[float] | tuple[float, ...] | None = None,
    reference_box: BoundingBox | None = None,
) -> int:
    """从多个候选框中选出最相关的一个。

    当提供 `reference_box` 时，优先选择与参考区域重叠或更接近的目标，
    用于多人场景下优先锁定靠近座椅的主操作者。
    """
    best_index = 0
    best_score = float("-inf")

    for index, coords in enumerate(xyxy):
        candidate = BoundingBox(
            float(coords[0]),
            float(coords[1]),
            float(coords[2]),
            float(coords[3]),
        )
        confidence = (
            float(confidences[index])
            if confidences is not None and index < len(confidences)
            else 1.0
        )
        score = confidence
        if reference_box is not None:
            overlap = intersection_ratio(candidate, reference_box)
            proximity = normalized_center_proximity(candidate, reference_box)
            score = overlap * 2.0 + proximity + confidence * 0.1

        if score > best_score:
            best_index = index
            best_score = score

    return best_index


def intersection_ratio(first: BoundingBox, second: BoundingBox) -> float:
    """返回两个框的交集面积占 `first` 面积的比例。"""
    intersection_width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    intersection_height = max(0.0, min(first.y2, second.y2) - max(first.y1, second.y1))
    intersection_area = intersection_width * intersection_height
    candidate_area = max(1.0, first.width * first.height)
    return intersection_area / candidate_area


def normalized_center_proximity(first: BoundingBox, second: BoundingBox) -> float:
    """返回两个框中心点的归一化接近度，越接近 1 表示越近。"""
    reference_diagonal = max(1.0, hypot(second.width, second.height))
    center_distance = hypot(first.center_x - second.center_x, first.center_y - second.center_y)
    return max(0.0, 1.0 - center_distance / reference_diagonal)
