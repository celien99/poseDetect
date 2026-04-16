"""多机位拍照与座椅区域标注工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from media_inputs import open_frame_stream

from .schemas import BoundingBox, SeatRegions


@dataclass(slots=True)
class SetupCameraConfig:
    """多机位拍照阶段所需的最小相机配置。"""

    name: str
    source: str


@dataclass(slots=True)
class CameraSnapshotResult:
    """单路相机抓拍结果。"""

    name: str
    source: str
    status: str
    image_path: str | None = None
    error: str | None = None


@dataclass(slots=True)
class CaptureSummary:
    """多机位抓拍汇总。"""

    output_dir: str
    manifest_path: str
    results: list[CameraSnapshotResult]

    @property
    def success_count(self) -> int:
        return sum(1 for result in self.results if result.status == "captured")


@dataclass(slots=True)
class SetupSeatRegionsSummary:
    """一键完成抓拍、标注、写回配置后的汇总。"""

    capture_summary: CaptureSummary
    annotation_path: str
    runtime_config_output_path: str


def load_setup_cameras(config_path: str) -> list[SetupCameraConfig]:
    """从配置文件读取拍照阶段所需的机位列表。"""
    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))

    camera_payloads = (
        payload.get("multi_camera_setup", {}).get("cameras")
        or payload.get("multi_camera_inference", {}).get("cameras")
        or []
    )
    if not camera_payloads:
        raise ValueError(
            "Config must contain either multi_camera_setup.cameras or multi_camera_inference.cameras",
        )

    cameras = [
        SetupCameraConfig(
            name=str(camera_payload["name"]),
            source=str(camera_payload["source"]),
        )
        for camera_payload in camera_payloads
    ]
    if len({camera.name for camera in cameras}) != len(cameras):
        raise ValueError("Camera names must be unique in setup capture config")
    return cameras


def capture_multi_camera_snapshots(
    config_path: str,
    output_dir: str,
    read_attempts: int = 3,
) -> CaptureSummary:
    """对配置中的全部机位抓拍一张照片，并生成 manifest。"""
    cameras = load_setup_cameras(config_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    results: list[CameraSnapshotResult] = []
    for camera in cameras:
        stream = open_frame_stream(camera.source)
        try:
            if not stream.is_opened():
                results.append(
                    CameraSnapshotResult(
                        name=camera.name,
                        source=camera.source,
                        status="failed",
                        error="unable_to_open_stream",
                    ),
                )
                continue

            media_frame = None
            for _ in range(max(1, read_attempts)):
                media_frame = stream.read_frame()
                if media_frame is not None:
                    break

            if media_frame is None:
                results.append(
                    CameraSnapshotResult(
                        name=camera.name,
                        source=camera.source,
                        status="failed",
                        error="unable_to_read_frame",
                    ),
                )
                continue

            image_path = target_dir / f"{camera.name}.jpg"
            cv2.imwrite(str(image_path), media_frame.image)
            results.append(
                CameraSnapshotResult(
                    name=camera.name,
                    source=camera.source,
                    status="captured",
                    image_path=str(image_path),
                ),
            )
        finally:
            stream.release()

    manifest_path = target_dir / "capture_manifest.json"
    manifest_payload = {
        "generated_at": _utc_now_isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "output_dir": str(target_dir.resolve()),
        "results": [
            {
                "name": result.name,
                "source": result.source,
                "status": result.status,
                "image_path": result.image_path,
                "error": result.error,
            }
            for result in results
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return CaptureSummary(
        output_dir=str(target_dir),
        manifest_path=str(manifest_path),
        results=results,
    )


def annotate_multi_camera_snapshots(
    capture_dir: str,
    output_path: str,
    window_name_prefix: str = "seat-region-annotation",
) -> str:
    """对抓拍目录中的照片逐机位标注座椅区域，并导出结果。"""
    capture_root = Path(capture_dir)
    manifest_path = capture_root / "capture_manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"Capture manifest does not exist: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = manifest.get("results", [])
    successful = [item for item in results if item.get("status") == "captured" and item.get("image_path")]
    if not successful:
        raise ValueError("No captured camera images found in manifest")

    cameras_payload: list[dict[str, Any]] = []
    for index, item in enumerate(successful, start=1):
        image_path = Path(str(item["image_path"]))
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Unable to read captured image: {image_path}")

        seat_regions = _annotate_single_camera(
            image=image,
            camera_name=str(item["name"]),
            source=str(item["source"]),
            window_name=f"{window_name_prefix}-{index}-{item['name']}",
        )
        cameras_payload.append(
            {
                "name": str(item["name"]),
                "source": str(item["source"]),
                "image_path": str(image_path),
                "seat_regions": seat_regions_to_payload(seat_regions),
            },
        )

    annotation_payload = {
        "generated_at": _utc_now_isoformat(),
        "capture_manifest_path": str(manifest_path.resolve()),
        "cameras": cameras_payload,
        "multi_camera_inference_patch": {
            "cameras": [
                {
                    "name": camera["name"],
                    "source": camera["source"],
                    "seat_regions": camera["seat_regions"],
                }
                for camera in cameras_payload
            ],
        },
    }

    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(annotation_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target_path)


def apply_annotations_to_runtime_config(
    annotation_path: str,
    runtime_config_path: str,
    output_path: str | None = None,
) -> str:
    """把标注结果自动回写到多机位推理配置。"""
    annotation_payload = json.loads(Path(annotation_path).read_text(encoding="utf-8"))
    runtime_path = Path(runtime_config_path)
    runtime_payload = json.loads(runtime_path.read_text(encoding="utf-8"))

    inference_payload = runtime_payload.get("multi_camera_inference")
    if not isinstance(inference_payload, dict):
        raise ValueError("Runtime config must contain multi_camera_inference")

    camera_payloads = inference_payload.get("cameras")
    if not isinstance(camera_payloads, list) or not camera_payloads:
        raise ValueError("Runtime config must contain multi_camera_inference.cameras")

    annotations_by_name = {
        str(camera["name"]): camera["seat_regions"]
        for camera in annotation_payload.get("cameras", [])
        if camera.get("name") and camera.get("seat_regions")
    }
    if not annotations_by_name:
        raise ValueError("Annotation file does not contain any camera seat_regions")

    updated_camera_names: list[str] = []
    for camera_payload in camera_payloads:
        camera_name = str(camera_payload.get("name", ""))
        seat_regions = annotations_by_name.get(camera_name)
        if seat_regions is None:
            continue
        camera_payload["seat_regions"] = seat_regions
        updated_camera_names.append(camera_name)

    missing_names = sorted(set(annotations_by_name) - set(updated_camera_names))
    if missing_names:
        raise ValueError(
            "Annotation cameras not found in runtime config: " + ", ".join(missing_names),
        )

    target_path = Path(output_path) if output_path else runtime_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(runtime_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target_path)


def setup_seat_regions(
    setup_config_path: str,
    runtime_config_path: str,
    capture_dir: str,
    annotation_output_path: str,
    output_runtime_config_path: str | None = None,
    read_attempts: int = 3,
) -> SetupSeatRegionsSummary:
    """一键执行抓拍、标注和配置写回。"""
    capture_summary = capture_multi_camera_snapshots(
        config_path=setup_config_path,
        output_dir=capture_dir,
        read_attempts=read_attempts,
    )
    annotation_path = annotate_multi_camera_snapshots(
        capture_dir=capture_dir,
        output_path=annotation_output_path,
    )
    runtime_output_path = apply_annotations_to_runtime_config(
        annotation_path=annotation_path,
        runtime_config_path=runtime_config_path,
        output_path=output_runtime_config_path,
    )
    return SetupSeatRegionsSummary(
        capture_summary=capture_summary,
        annotation_path=annotation_path,
        runtime_config_output_path=runtime_output_path,
    )


def seat_regions_to_payload(seat_regions: SeatRegions) -> dict[str, dict[str, float]]:
    """把结构化区域转成 JSON 可序列化的 payload。"""
    return {
        "overall": _box_to_payload(seat_regions.overall),
        "side_surface": _box_to_payload(seat_regions.side_surface),
        "bottom_surface": _box_to_payload(seat_regions.bottom_surface),
    }


def _annotate_single_camera(
    image: Any,
    camera_name: str,
    source: str,
    window_name: str,
) -> SeatRegions:
    prompts = [
        ("overall", "Select the overall seat region"),
        ("side_surface", "Select the seat side operation region"),
        ("bottom_surface", "Select the seat bottom operation region"),
    ]

    rois: dict[str, BoundingBox] = {}
    for region_name, prompt in prompts:
        roi = _select_roi(
            image=image,
            camera_name=camera_name,
            source=source,
            prompt=prompt,
            window_name=window_name,
        )
        rois[region_name] = _roi_to_box(roi)

    _destroy_window(window_name)
    return SeatRegions(
        overall=rois["overall"],
        side_surface=rois["side_surface"],
        bottom_surface=rois["bottom_surface"],
    )


def _select_roi(
    image: Any,
    camera_name: str,
    source: str,
    prompt: str,
    window_name: str,
) -> tuple[int, int, int, int]:
    annotated = image.copy()
    cv2.putText(
        annotated,
        f"{camera_name}: {prompt}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        annotated,
        source,
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    try:
        roi = cv2.selectROI(window_name, annotated, showCrosshair=True, fromCenter=False)
    except cv2.error as exc:
        raise RuntimeError(
            "OpenCV ROI annotation is unavailable in the current environment. "
            "Run on a machine with GUI support.",
        ) from exc
    if roi[2] <= 0 or roi[3] <= 0:
        raise ValueError(f"Invalid ROI selected for {camera_name}: {prompt}")
    return tuple(int(value) for value in roi)


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


def _destroy_window(window_name: str) -> None:
    try:
        cv2.destroyWindow(window_name)
    except cv2.error:
        pass


def _utc_now_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat()
