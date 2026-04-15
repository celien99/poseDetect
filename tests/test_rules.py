from seat_inspection.config import ActionConfig, RuleConfig
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


def test_touch_side_surface_requires_hold_frames() -> None:
    engine = ActionRecognitionEngine(RuleConfig(touch_hold_frames=2))

    first = engine.process_frame(
        build_observation(1, Point(285, 180, 0.95), Point(240, 210, 0.95))
    )
    second = engine.process_frame(
        build_observation(2, Point(290, 178, 0.95), Point(235, 208, 0.95))
    )

    assert not first.touch_side_surface
    assert second.touch_side_surface


def test_lift_bottom_requires_both_wrists_near_bottom() -> None:
    engine = ActionRecognitionEngine(RuleConfig(lift_hold_frames=2, lift_ratio_threshold=0.01))

    first = engine.process_frame(
        build_observation(1, Point(170, 230, 0.95), Point(230, 228, 0.95))
    )
    second = engine.process_frame(
        build_observation(2, Point(175, 225, 0.95), Point(225, 223, 0.95))
    )

    assert not first.lift_seat_bottom
    assert second.lift_seat_bottom


def test_custom_touch_action_can_be_configured_from_rules() -> None:
    engine = ActionRecognitionEngine(
        RuleConfig(
            actions=[
                ActionConfig(
                    name="touch_bottom_surface",
                    kind="touch_region",
                    region="bottom_surface",
                    hold_frames=1,
                    wrist_margin=5.0,
                    min_wrist_count=1,
                ),
            ],
        ),
    )

    decision = engine.process_frame(
        build_observation(1, Point(170, 230, 0.95), Point(260, 180, 0.95)),
    )

    assert decision.actions["touch_bottom_surface"]
    assert not decision.touch_side_surface
    assert not decision.lift_seat_bottom


def test_snapshot_mode_returns_current_action_without_hold_history() -> None:
    engine = ActionRecognitionEngine(
        RuleConfig(
            touch_hold_frames=3,
            actions=[
                ActionConfig(
                    name="touch_side_surface",
                    kind="touch_region",
                    region="side_surface",
                    hold_frames=3,
                    wrist_margin=5.0,
                    min_wrist_count=1,
                ),
            ],
        ),
    )

    decision = engine.process_snapshot(
        build_observation(1, Point(285, 180, 0.95), Point(240, 210, 0.95)),
    )

    assert decision.actions["touch_side_surface"]
    assert decision.touch_side_surface
