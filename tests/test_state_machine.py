from seat_inspection.config import (
    KeypointProcessingConfig,
    RuleConfig,
    StateMachineConfig,
    WorkflowStepConfig,
    build_default_rule_actions,
)
from seat_inspection.engine import ActionRecognitionEngine
from seat_inspection.schemas import BoundingBox, FrameObservation, Point, PoseSample, SeatRegions


def build_observation(frame_index: int, left_wrist: Point, right_wrist: Point) -> FrameObservation:
    return FrameObservation(
        frame_index=frame_index,
        seat_regions=SeatRegions(
            overall=BoundingBox(100, 100, 300, 320),
            side_surface=BoundingBox(280, 130, 330, 260),
            bottom_surface=BoundingBox(140, 220, 260, 330),
        ),
        pose=PoseSample(
            left_shoulder=Point(150, 140, 0.9),
            right_shoulder=Point(220, 142, 0.9),
            left_wrist=left_wrist,
            right_wrist=right_wrist,
            left_hip=Point(170, 250, 0.9),
            right_hip=Point(210, 252, 0.9),
        ),
    )


def test_state_machine_marks_ok_after_required_steps_complete() -> None:
    engine = ActionRecognitionEngine(
        rule_config=RuleConfig(
            actions=build_default_rule_actions(
                touch_hold_frames=1,
                lift_hold_frames=1,
                lift_ratio_threshold=0.01,
            ),
        ),
        keypoint_processing_config=KeypointProcessingConfig(enabled=False),
        state_machine_config=StateMachineConfig(
            steps=[
                WorkflowStepConfig(name="touch_side", action="touch_side_surface", min_frames=1),
                WorkflowStepConfig(name="lift_bottom", action="lift_seat_bottom", min_frames=1),
            ],
        ),
    )

    decision_1 = engine.process_frame(
        build_observation(1, Point(285, 180, 0.95), Point(240, 210, 0.95)),
    )
    result_1 = engine.update_state(decision_1)
    decision_2 = engine.process_frame(
        build_observation(2, Point(170, 230, 0.95), Point(230, 228, 0.95)),
    )
    result_2 = engine.update_state(decision_2)
    final_result = engine.finalize_state()

    assert result_1.current_step == "lift_bottom"
    assert result_2.status == "OK"
    assert final_result.status == "OK"


def test_state_machine_marks_ng_when_steps_not_completed() -> None:
    engine = ActionRecognitionEngine(
        rule_config=RuleConfig(
            actions=build_default_rule_actions(
                touch_hold_frames=1,
                lift_hold_frames=1,
                lift_ratio_threshold=0.01,
            ),
        ),
        keypoint_processing_config=KeypointProcessingConfig(enabled=False),
        state_machine_config=StateMachineConfig(
            steps=[
                WorkflowStepConfig(name="touch_side", action="touch_side_surface", min_frames=1),
                WorkflowStepConfig(name="lift_bottom", action="lift_seat_bottom", min_frames=1),
            ],
        ),
    )

    decision = engine.process_frame(
        build_observation(1, Point(285, 180, 0.95), Point(240, 210, 0.95)),
    )
    engine.update_state(decision)
    final_result = engine.finalize_state()

    assert final_result.status == "NG"
