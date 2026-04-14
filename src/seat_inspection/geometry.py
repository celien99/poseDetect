from __future__ import annotations

from .schemas import BoundingBox, Point


def point_in_box(point: Point, box: BoundingBox, margin: float = 0.0) -> bool:
    return (
        box.x1 - margin <= point.x <= box.x2 + margin
        and box.y1 - margin <= point.y <= box.y2 + margin
    )


def normalized_horizontal_reach(point: Point, box: BoundingBox) -> float:
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
    return (first.y + second.y) / 2.0
