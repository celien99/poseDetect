import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from seat_inspection.config import MultiCameraInferenceConfig, RuleConfig
from seat_inspection.inference import run_multi_camera_inference
from seat_inspection.schemas import (
    ActionDecision,
    BoundingBox,
    InspectionResult,
    PersonDetection,
    SeatRegions,
)


class FakeStream:
    def __init__(self, name: str, timestamps: list[float | None]) -> None:
        self._name = name
        self._timestamps = list(timestamps)
        self._index = 0

    def is_opened(self) -> bool:
        return True

    def read_frame(self):
        if self._index >= len(self._timestamps):
            return None
        self._index += 1
        return SimpleNamespace(
            frame_index=self._index,
            image=np.zeros((32, 48, 3), dtype="uint8"),
            timestamp_ms=self._timestamps[self._index - 1],
        )

    def release(self) -> None:
        return None

    def get(self, prop_id: int) -> float:
        if prop_id == 5:
            return 25.0
        return 0.0


class FakePipeline:
    def __init__(self, camera_name: str) -> None:
        self._camera_name = camera_name
        self._counter = 0
        self.seat_region_provider = SimpleNamespace(mode="fixed_roi")

    def process_frame(self, frame, frame_index: int, snapshot: bool = False):
        del frame, snapshot
        self._counter += 1
        return SimpleNamespace(
            seat_regions=SeatRegions(
                overall=BoundingBox(0, 0, 100, 100),
                side_surface=BoundingBox(10, 10, 20, 20),
                bottom_surface=BoundingBox(30, 30, 50, 50),
            ),
            person_detection=PersonDetection(
                bounding_box=BoundingBox(5, 5, 45, 95),
                confidence=0.9,
            ),
            decision=ActionDecision(
                frame_index=frame_index,
                actions={"touch_side_surface": self._camera_name == "front"},
                scores={"touch_side_surface": 0.9},
                reasons={"touch_side_surface": "detected"},
            ),
            inspection_result=InspectionResult(
                status="PENDING",
                current_state="in_progress",
            ),
        )

    def finalize(self):
        return InspectionResult(status="OK", current_state="completed")


def test_run_multi_camera_inference_exports_operator_and_camera_stats(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "report.json"

    streams = {
        "front": FakeStream("front", [0.0, 40.0]),
        "side": FakeStream("side", [5.0, None]),
    }

    monkeypatch.setattr(
        "seat_inspection.inference.open_frame_stream",
        lambda source: streams["front"] if "front" in source else streams["side"],
    )
    monkeypatch.setattr(
        "seat_inspection.inference._build_pipeline",
        lambda pose_model_path, seat_regions, person_model_path, seat_model_path, confidence, iou, device, keypoint_processing, state_machine, rule_config=None: FakePipeline(
            "front" if seat_regions.overall.x1 == 1 else "side",
        ),
    )

    config = MultiCameraInferenceConfig(
        pose_model_path="pose.pt",
        output_json_path=str(output_path),
        min_active_cameras=1,
        cameras=[
            SimpleNamespace(
                name="front",
                source="front-stream",
                seat_regions=SeatRegions(
                    overall=BoundingBox(1, 0, 100, 100),
                    side_surface=BoundingBox(10, 10, 20, 20),
                    bottom_surface=BoundingBox(30, 30, 50, 50),
                ),
                pose_model_path=None,
                person_model_path=None,
                seat_model_path=None,
                confidence=None,
                iou=None,
                device=None,
            ),
            SimpleNamespace(
                name="side",
                source="side-stream",
                seat_regions=SeatRegions(
                    overall=BoundingBox(2, 0, 100, 100),
                    side_surface=BoundingBox(10, 10, 20, 20),
                    bottom_surface=BoundingBox(30, 30, 50, 50),
                ),
                pose_model_path=None,
                person_model_path=None,
                seat_model_path=None,
                confidence=None,
                iou=None,
                device=None,
            ),
        ],
    )

    decisions = run_multi_camera_inference(config, RuleConfig())
    payload = json.loads(Path(output_path).read_text(encoding="utf-8"))

    assert len(decisions) == 2
    assert decisions[0].operator_association_id == "operator-1"
    assert "front" in decisions[0].operator_track_ids
    assert payload["metadata"]["operator_association_strategy"] == "persistent_primary_operator"
    assert payload["metadata"]["cameras"][0]["frames_processed"] >= 1
