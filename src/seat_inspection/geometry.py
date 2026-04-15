"""动作规则中复用的基础几何计算函数。"""

from __future__ import annotations

from .schemas import BoundingBox, Point


def point_in_box(point: Point, box: BoundingBox, margin: float = 0.0) -> bool:
    """判断关键点是否落在区域框内，`margin` 用于容忍轻微抖动。"""
    return (
        box.x1 - margin <= point.x <= box.x2 + margin
        and box.y1 - margin <= point.y <= box.y2 + margin
    )


def normalized_horizontal_reach(point: Point, box: BoundingBox) -> float:
    """计算点到区域横向距离的归一化值，越接近 0 表示越靠近目标区域。"""
    if box.width == 0:
        return 0.0
    if point.x < box.x1:
        distance = box.x1 - point.x
    elif point.x > box.x2:
        distance = point.x - box.x2
    else:
        distance = 0.0
    return distance / box.width


def average_y(first: Point, second: Point) -> float:
    """返回两个关键点纵坐标的平均值。"""
    return (first.y + second.y) / 2.0
