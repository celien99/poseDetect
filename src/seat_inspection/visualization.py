"""推理结果可视化。"""

from __future__ import annotations

from typing import Any

import cv2

from .schemas import ActionDecision, BoundingBox, InspectionResult, PersonDetection, SeatRegions


def annotate_frame(
    frame: Any,
    seat_regions: SeatRegions,
    decision: ActionDecision,
    inspection_result: InspectionResult | None = None,
    person_detection: PersonDetection | None = None,
) -> Any:
    """在图像上绘制人体框、座椅区域和动作结果。"""
    annotated = frame.copy()

    if person_detection is not None:
        draw_box(annotated, person_detection.bounding_box, (0, 165, 255), "person")
    draw_box(annotated, seat_regions.overall, (0, 255, 0), "seat")
    draw_box(annotated, seat_regions.side_surface, (255, 255, 0), "side")
    draw_box(annotated, seat_regions.bottom_surface, (255, 0, 255), "bottom")

    status_items = [f"{name}={int(state)}" for name, state in decision.actions.items()]
    if not status_items:
        status_items = [
            f"touch={int(decision.touch_side_surface)}",
            f"lift={int(decision.lift_seat_bottom)}",
        ]
    status = " ".join(status_items[:3])
    cv2.putText(
        annotated,
        status,
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    if inspection_result is not None:
        summary = f"state={inspection_result.current_state} result={inspection_result.status}"
        cv2.putText(
            annotated,
            summary,
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 200, 0) if inspection_result.status == "OK" else (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    return annotated


def draw_box(frame: Any, box: BoundingBox, color: tuple[int, int, int], label: str) -> None:
    """绘制矩形框与标签。"""
    cv2.rectangle(
        frame,
        (int(box.x1), int(box.y1)),
        (int(box.x2), int(box.y2)),
        color,
        2,
    )
    cv2.putText(
        frame,
        label,
        (int(box.x1), max(20, int(box.y1) - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
        cv2.LINE_AA,
    )
