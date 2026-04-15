from seat_inspection.region_provider import (
    DetectedSeatRegionProvider,
    build_seat_region_provider,
    map_template_regions_to_detection,
)
from seat_inspection.schemas import BoundingBox, SeatRegions
from seat_inspection.seat_detection import SeatDetection


def test_build_seat_region_provider_returns_fixed_regions() -> None:
    regions = SeatRegions(
        overall=BoundingBox(1, 2, 3, 4),
        side_surface=BoundingBox(5, 6, 7, 8),
        bottom_surface=BoundingBox(9, 10, 11, 12),
    )

    provider = build_seat_region_provider(regions)
    resolved = provider.get_regions(frame=None)

    assert resolved == regions


def test_map_template_regions_to_detection_scales_sub_regions() -> None:
    template = SeatRegions(
        overall=BoundingBox(100, 100, 300, 300),
        side_surface=BoundingBox(260, 120, 300, 240),
        bottom_surface=BoundingBox(140, 220, 260, 300),
    )
    detection = SeatDetection(
        bounding_box=BoundingBox(200, 200, 500, 500),
        confidence=0.9,
    )

    mapped = map_template_regions_to_detection(template, detection)

    assert mapped.overall == detection.bounding_box
    assert round(mapped.side_surface.x1, 1) == 440.0
    assert round(mapped.bottom_surface.y1, 1) == 380.0


class FakeSeatDetector:
    def __init__(self, detection):
        self._detection = detection

    def detect(self, frame, confidence, iou, device):
        del frame, confidence, iou, device
        return self._detection


def test_detected_provider_falls_back_to_template_when_detection_missing() -> None:
    template = SeatRegions(
        overall=BoundingBox(100, 100, 300, 300),
        side_surface=BoundingBox(260, 120, 300, 240),
        bottom_surface=BoundingBox(140, 220, 260, 300),
    )
    provider = DetectedSeatRegionProvider(
        template_regions=template,
        detector=FakeSeatDetector(None),
        confidence=0.25,
        iou=0.45,
        device="cpu",
    )

    assert provider.get_regions(frame=None) == template
