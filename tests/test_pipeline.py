from seat_inspection.engine import ActionRecognitionEngine
from seat_inspection.config import KeypointProcessingConfig, RuleConfig, StateMachineConfig, WorkflowStepConfig
from seat_inspection.pipeline import InspectionPipeline
from seat_inspection.schemas import (
    ActionDecision,
    BoundingBox,
    FrameObservation,
    Point,
    PoseSample,
    SeatRegions,
)


class StubPoseEstimator:
    def __init__(self, results):
        self._results = iter(results)

    def predict(self, frame, confidence: float, iou: float, device: str):
        del frame, confidence, iou, device
        return next(self._results)


class StubSeatRegionProvider:
    mode = "fixed_roi"

    def __init__(self, seat_regions: SeatRegions) -> None:
        self._seat_regions = seat_regions

    def get_regions(self, frame) -> SeatRegions:
        del frame
        return self._seat_regions


def build_observation(frame_index: int) -> FrameObservation:
    return FrameObservation(
        frame_index=frame_index,
        seat_regions=build_seat_regions(),
        pose=PoseSample(
            left_shoulder=Point(150, 140, 0.95),
            right_shoulder=Point(220, 142, 0.95),
            left_wrist=Point(285, 180, 0.95),
            right_wrist=Point(240, 210, 0.95),
            left_hip=Point(170, 250, 0.95),
            right_hip=Point(210, 252, 0.95),
        ),
    )


def build_seat_regions() -> SeatRegions:
    return SeatRegions(
        overall=BoundingBox(100, 100, 300, 320),
        side_surface=BoundingBox(280, 130, 330, 260),
        bottom_surface=BoundingBox(140, 220, 260, 330),
    )


def test_pipeline_tolerates_short_pose_gaps_without_resetting_workflow(monkeypatch) -> None:
    observations = {
        "pose-1": build_observation(1),
        "pose-3": build_observation(3),
    }

    monkeypatch.setattr(
        "seat_inspection.pipeline.build_observation_from_pose_result",
        lambda frame_index, result, seat_regions: observations.get(result),
    )

    pipeline = InspectionPipeline(
        pose_estimator=StubPoseEstimator(["pose-1", "missing", "pose-3"]),
        seat_region_provider=StubSeatRegionProvider(build_seat_regions()),
        confidence=0.25,
        iou=0.45,
        device="cpu",
        engine=ActionRecognitionEngine(
            rule_config=RuleConfig(touch_hold_frames=1, max_action_gap_frames=1),
            keypoint_processing_config=KeypointProcessingConfig(enabled=False),
            state_machine_config=StateMachineConfig(
                steps=[
                    WorkflowStepConfig(
                        name="touch_side",
                        action="touch_side_surface",
                        min_frames=2,
                    ),
                ],
            ),
        ),
    )

    first = pipeline.process_frame(frame="frame-1", frame_index=1)
    second = pipeline.process_frame(frame="frame-2", frame_index=2)
    third = pipeline.process_frame(frame="frame-3", frame_index=3)
    final_result = pipeline.finalize()

    assert first.inspection_result.current_step == "touch_side"
    assert second.decision.frame_index == 2
    assert second.decision.touch_side_surface is False
    assert second.decision.actions["touch_side_surface"] is False
    assert second.inspection_result.current_step == "touch_side"
    assert third.inspection_result.status == "OK"
    assert final_result.status == "OK"


def test_pipeline_resets_after_gap_limit_is_exceeded(monkeypatch) -> None:
    observations = {
        "pose-1": build_observation(1),
        "pose-4": build_observation(4),
    }

    monkeypatch.setattr(
        "seat_inspection.pipeline.build_observation_from_pose_result",
        lambda frame_index, result, seat_regions: observations.get(result),
    )

    pipeline = InspectionPipeline(
        pose_estimator=StubPoseEstimator(["pose-1", "missing", "missing", "pose-4"]),
        seat_region_provider=StubSeatRegionProvider(build_seat_regions()),
        confidence=0.25,
        iou=0.45,
        device="cpu",
        engine=ActionRecognitionEngine(
            rule_config=RuleConfig(touch_hold_frames=2, max_action_gap_frames=1),
            keypoint_processing_config=KeypointProcessingConfig(enabled=False),
            state_machine_config=StateMachineConfig(
                steps=[
                    WorkflowStepConfig(
                        name="touch_side",
                        action="touch_side_surface",
                        min_frames=1,
                    ),
                ],
            ),
        ),
    )

    pipeline.process_frame(frame="frame-1", frame_index=1)
    pipeline.process_frame(frame="frame-2", frame_index=2)
    third = pipeline.process_frame(frame="frame-3", frame_index=3)
    fourth = pipeline.process_frame(frame="frame-4", frame_index=4)
    final_result = pipeline.finalize()

    assert third.inspection_result.current_step == "touch_side"
    assert fourth.decision.touch_side_surface is False
    assert final_result.status == "NG"
