from seat_inspection.schemas import BoundingBox, PersonDetection
from seat_inspection.tracking import MultiCameraOperatorAssociator, PrimaryOperatorTracker


def test_primary_operator_tracker_keeps_same_track_for_overlapping_boxes() -> None:
    tracker = PrimaryOperatorTracker("front")

    first = tracker.update(
        1,
        PersonDetection(BoundingBox(10, 20, 110, 220), 0.9),
    )
    second = tracker.update(
        2,
        PersonDetection(BoundingBox(12, 22, 112, 222), 0.88),
    )

    assert first is not None
    assert second is not None
    assert first.track_id == "front-1"
    assert second.track_id == "front-1"


def test_multi_camera_operator_associator_reuses_association_id() -> None:
    associator = MultiCameraOperatorAssociator()

    first = associator.update(
        [
            PrimaryOperatorTracker("front").update(
                1,
                PersonDetection(BoundingBox(10, 20, 110, 220), 0.9),
            ),
        ],
    )
    second = associator.update([])
    third = associator.update(
        [
            PrimaryOperatorTracker("side").update(
                3,
                PersonDetection(BoundingBox(12, 18, 108, 218), 0.85),
            ),
        ],
    )

    assert first.association_id == "operator-1"
    assert second.association_id == "operator-1"
    assert third.association_id == "operator-1"
