from seat_inspection.config import MultiCameraFusionConfig
from seat_inspection.multi_camera import CameraDecisionSample, fuse_camera_decisions
from seat_inspection.schemas import ActionDecision


def build_sample(name: str, touch: bool, lift: bool, timestamp_ms: float) -> CameraDecisionSample:
    return CameraDecisionSample(
        camera_name=name,
        frame_index=1,
        timestamp_ms=timestamp_ms,
        decision=ActionDecision(
            frame_index=1,
            actions={
                "touch_side_surface": touch,
                "lift_seat_bottom": lift,
            },
            scores={
                "touch_side_surface": 1.0 if touch else 0.0,
                "lift_seat_bottom": 1.0 if lift else 0.0,
            },
        ),
    )


def test_fuse_camera_decisions_supports_any_and_all_strategies() -> None:
    samples = [
        build_sample("cam-a", touch=True, lift=False, timestamp_ms=1000),
        build_sample("cam-b", touch=False, lift=True, timestamp_ms=1010),
    ]

    decision = fuse_camera_decisions(
        samples,
        frame_index=5,
        fusion_config=MultiCameraFusionConfig(
            touch_action_strategy="any",
            lift_action_strategy="all",
        ),
    )

    assert decision.frame_index == 5
    assert decision.actions["touch_side_surface"] is True
    assert decision.actions["lift_seat_bottom"] is False


def test_fuse_camera_decisions_filters_out_of_sync_samples() -> None:
    samples = [
        build_sample("cam-a", touch=False, lift=False, timestamp_ms=1000),
        build_sample("cam-b", touch=True, lift=False, timestamp_ms=1010),
        build_sample("cam-c", touch=False, lift=True, timestamp_ms=1500),
    ]

    decision = fuse_camera_decisions(
        samples,
        frame_index=9,
        fusion_config=MultiCameraFusionConfig(
            touch_action_strategy="majority",
            lift_action_strategy="any",
            time_tolerance_ms=30.0,
        ),
    )

    assert decision.actions["touch_side_surface"] is False
    assert decision.actions["lift_seat_bottom"] is False
