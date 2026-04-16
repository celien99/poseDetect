import json

import numpy as np

from seat_inspection.camera_setup import (
    annotate_multi_camera_snapshots,
    apply_annotations_to_runtime_config,
    capture_multi_camera_snapshots,
    load_setup_cameras,
    seat_regions_to_payload,
    setup_seat_regions,
)
from seat_inspection.schemas import BoundingBox, SeatRegions


class FakeStream:
    def __init__(self, image) -> None:
        self._image = image
        self._read_count = 0

    def is_opened(self) -> bool:
        return True

    def read_frame(self):
        if self._read_count > 0:
            return None
        self._read_count += 1
        return type(
            "MediaFrame",
            (),
            {
                "image": self._image,
            },
        )()

    def release(self) -> None:
        return None


def test_load_setup_cameras_supports_multi_camera_setup_block(tmp_path) -> None:
    config_path = tmp_path / "setup.json"
    config_path.write_text(
        json.dumps(
            {
                "multi_camera_setup": {
                    "cameras": [
                        {"name": "front", "source": "mvs://0"},
                        {"name": "side", "source": "mvs://1"},
                    ],
                },
            },
        ),
        encoding="utf-8",
    )

    cameras = load_setup_cameras(str(config_path))

    assert [camera.name for camera in cameras] == ["front", "side"]
    assert cameras[1].source == "mvs://1"


def test_capture_multi_camera_snapshots_writes_manifest(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "setup.json"
    output_dir = tmp_path / "captures"
    config_path.write_text(
        json.dumps(
            {
                "multi_camera_setup": {
                    "cameras": [
                        {"name": "front", "source": "mvs://0"},
                    ],
                },
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "seat_inspection.camera_setup.open_frame_stream",
        lambda source: FakeStream(np.zeros((20, 30, 3), dtype="uint8")),
    )

    summary = capture_multi_camera_snapshots(str(config_path), str(output_dir))
    manifest = json.loads((output_dir / "capture_manifest.json").read_text(encoding="utf-8"))

    assert summary.success_count == 1
    assert manifest["results"][0]["status"] == "captured"
    assert (output_dir / "front.jpg").exists()


def test_annotate_multi_camera_snapshots_exports_config_patch(tmp_path, monkeypatch) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    image_path = capture_dir / "front.jpg"
    manifest_path = capture_dir / "capture_manifest.json"
    image_path.write_bytes(b"fake-image")
    manifest_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "name": "front",
                        "source": "mvs://0",
                        "status": "captured",
                        "image_path": str(image_path),
                    },
                ],
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "seat_inspection.camera_setup.cv2.imread",
        lambda path: np.zeros((120, 160, 3), dtype="uint8"),
    )
    rois = iter(
        [
            (10, 20, 30, 40),
            (15, 25, 20, 30),
            (18, 35, 25, 20),
        ],
    )
    monkeypatch.setattr(
        "seat_inspection.camera_setup.cv2.selectROI",
        lambda window_name, image, showCrosshair=True, fromCenter=False: next(rois),
    )

    output_path = capture_dir / "annotations.json"
    annotate_multi_camera_snapshots(str(capture_dir), str(output_path))
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["cameras"][0]["name"] == "front"
    assert payload["multi_camera_inference_patch"]["cameras"][0]["seat_regions"]["overall"]["x2"] == 40.0


def test_seat_regions_to_payload_serializes_regions() -> None:
    payload = seat_regions_to_payload(
        SeatRegions(
            overall=BoundingBox(1, 2, 3, 4),
            side_surface=BoundingBox(5, 6, 7, 8),
            bottom_surface=BoundingBox(9, 10, 11, 12),
        ),
    )

    assert payload["overall"]["x1"] == 1
    assert payload["side_surface"]["y2"] == 8
    assert payload["bottom_surface"]["x2"] == 11


def test_apply_annotations_to_runtime_config_updates_matching_cameras(tmp_path) -> None:
    annotation_path = tmp_path / "annotations.json"
    runtime_config_path = tmp_path / "runtime.json"
    annotation_path.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "name": "front",
                        "seat_regions": {
                            "overall": {"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                            "side_surface": {"x1": 11, "y1": 21, "x2": 31, "y2": 41},
                            "bottom_surface": {"x1": 12, "y1": 22, "x2": 32, "y2": 42},
                        },
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    runtime_config_path.write_text(
        json.dumps(
            {
                "multi_camera_inference": {
                    "pose_model_path": "pose.pt",
                    "cameras": [
                        {
                            "name": "front",
                            "source": "mvs://0",
                            "seat_regions": {
                                "overall": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                                "side_surface": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                                "bottom_surface": {"x1": 9, "y1": 10, "x2": 11, "y2": 12},
                            },
                        },
                    ],
                },
            },
        ),
        encoding="utf-8",
    )

    output_path = apply_annotations_to_runtime_config(
        str(annotation_path),
        str(runtime_config_path),
    )
    payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))

    assert output_path == str(runtime_config_path)
    assert payload["multi_camera_inference"]["cameras"][0]["seat_regions"]["overall"]["x1"] == 10


def test_apply_annotations_to_runtime_config_rejects_missing_camera(tmp_path) -> None:
    annotation_path = tmp_path / "annotations.json"
    runtime_config_path = tmp_path / "runtime.json"
    annotation_path.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "name": "front",
                        "seat_regions": {
                            "overall": {"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                            "side_surface": {"x1": 11, "y1": 21, "x2": 31, "y2": 41},
                            "bottom_surface": {"x1": 12, "y1": 22, "x2": 32, "y2": 42},
                        },
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    runtime_config_path.write_text(
        json.dumps(
            {
                "multi_camera_inference": {
                    "pose_model_path": "pose.pt",
                    "cameras": [
                        {
                            "name": "side",
                            "source": "mvs://1",
                            "seat_regions": {
                                "overall": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                                "side_surface": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                                "bottom_surface": {"x1": 9, "y1": 10, "x2": 11, "y2": 12},
                            },
                        },
                    ],
                },
            },
        ),
        encoding="utf-8",
    )

    try:
        apply_annotations_to_runtime_config(
            str(annotation_path),
            str(runtime_config_path),
        )
    except ValueError as exc:
        assert "Annotation cameras not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing camera")


def test_setup_seat_regions_runs_full_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "seat_inspection.camera_setup.capture_multi_camera_snapshots",
        lambda config_path, output_dir, read_attempts=3: captured.update(
            {
                "setup_config_path": config_path,
                "capture_dir": output_dir,
                "read_attempts": read_attempts,
            },
        )
        or type(
            "CaptureSummaryStub",
            (),
            {
                "success_count": 2,
                "results": [object(), object()],
            },
        )(),
    )
    monkeypatch.setattr(
        "seat_inspection.camera_setup.annotate_multi_camera_snapshots",
        lambda capture_dir, output_path: captured.update(
            {
                "annotate_capture_dir": capture_dir,
                "annotation_output_path": output_path,
            },
        )
        or output_path,
    )
    monkeypatch.setattr(
        "seat_inspection.camera_setup.apply_annotations_to_runtime_config",
        lambda annotation_path, runtime_config_path, output_path=None: captured.update(
            {
                "annotation_path": annotation_path,
                "runtime_config_path": runtime_config_path,
                "output_runtime_config_path": output_path,
            },
        )
        or (output_path or runtime_config_path),
    )

    summary = setup_seat_regions(
        setup_config_path="configs/multi_camera_setup.example.json",
        runtime_config_path="configs/runtime.multi_camera.example.json",
        capture_dir="outputs/setup_capture",
        annotation_output_path="outputs/setup_capture/seat_regions.annotations.json",
        output_runtime_config_path="configs/runtime.multi_camera.ready.json",
        read_attempts=5,
    )

    assert captured["setup_config_path"] == "configs/multi_camera_setup.example.json"
    assert captured["capture_dir"] == "outputs/setup_capture"
    assert captured["read_attempts"] == 5
    assert captured["annotate_capture_dir"] == "outputs/setup_capture"
    assert captured["annotation_output_path"] == "outputs/setup_capture/seat_regions.annotations.json"
    assert captured["annotation_path"] == "outputs/setup_capture/seat_regions.annotations.json"
    assert captured["runtime_config_path"] == "configs/runtime.multi_camera.example.json"
    assert captured["output_runtime_config_path"] == "configs/runtime.multi_camera.ready.json"
    assert summary.annotation_path == "outputs/setup_capture/seat_regions.annotations.json"
    assert summary.runtime_config_output_path == "configs/runtime.multi_camera.ready.json"
