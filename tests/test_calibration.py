from seat_inspection.calibration import seat_regions_to_payload, _roi_to_box
from seat_inspection.schemas import BoundingBox, SeatRegions


def test_roi_to_box_converts_xywh_to_xyxy() -> None:
    box = _roi_to_box((10, 20, 30, 40))

    assert box.x1 == 10.0
    assert box.y1 == 20.0
    assert box.x2 == 40.0
    assert box.y2 == 60.0


def test_seat_regions_to_payload_serializes_all_regions() -> None:
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
