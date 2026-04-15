"""座椅区域标定工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
from media_inputs import infer_source_kind, load_image_frame, open_frame_stream

from .schemas import BoundingBox, SeatRegions


def calibrate_seat_regions(
    source: str,
    output_path: str | None = None,
    window_name: str = "seat-region-calibration",
) -> SeatRegions:
    """从媒体源读取一帧并交互式标定座椅区域。"""
    frame = _load_reference_frame(source)
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        regions = SeatRegions(
            overall=_select_region(frame, window_name, "overall"),
            side_surface=_select_region(frame, window_name, "side_surface"),
            bottom_surface=_select_region(frame, window_name, "bottom_surface"),
        )
    finally:
        try:
            cv2.destroyWindow(window_name)
        except cv2.error:
            pass

    payload = seat_regions_to_payload(regions)
    formatted = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(formatted, encoding="utf-8")
    else:
        print(formatted)
    return regions


def seat_regions_to_payload(regions: SeatRegions) -> dict[str, dict[str, float]]:
    """将区域对象转换为 JSON 可序列化结构。"""
    return {
        "overall": _box_to_payload(regions.overall),
        "side_surface": _box_to_payload(regions.side_surface),
        "bottom_surface": _box_to_payload(regions.bottom_surface),
    }


def _load_reference_frame(source: str) -> Any:
    source_kind = infer_source_kind(source)
    if source_kind == "image":
        return load_image_frame(source).image

    stream = open_frame_stream(source)
    try:
        if not stream.is_opened():
            raise ValueError(f"Unable to open calibration source: {source}")
        media_frame = stream.read_frame()
        if media_frame is None:
            raise ValueError(f"Unable to read a frame from calibration source: {source}")
        return media_frame.image
    finally:
        stream.release()


def _select_region(frame: Any, window_name: str, region_name: str) -> BoundingBox:
    preview = frame.copy()
    _draw_instruction(preview, f"Select {region_name}, ENTER confirm, C cancel")
    try:
        roi = cv2.selectROI(window_name, preview, showCrosshair=True, fromCenter=False)
    except cv2.error as exc:
        raise RuntimeError(
            "OpenCV ROI selection is unavailable in the current environment. "
            "Run calibration on a machine with GUI support.",
        ) from exc

    box = _roi_to_box(roi)
    if box.width <= 0 or box.height <= 0:
        raise ValueError(f"Region '{region_name}' was not selected")
    return box


def _roi_to_box(roi: tuple[int, int, int, int]) -> BoundingBox:
    x, y, width, height = roi
    return BoundingBox(
        x1=float(x),
        y1=float(y),
        x2=float(x + width),
        y2=float(y + height),
    )


def _box_to_payload(box: BoundingBox) -> dict[str, float]:
    return {
        "x1": box.x1,
        "y1": box.y1,
        "x2": box.x2,
        "y2": box.y2,
    }


def _draw_instruction(frame: Any, text: str) -> None:
    cv2.putText(
        frame,
        text,
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
