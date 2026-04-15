from seat_inspection.person_detection import extract_primary_person_detection
from seat_inspection.schemas import BoundingBox


class FakeTensor:
    def __init__(self, value):
        self._value = value

    def cpu(self):
        return self

    def numpy(self):
        return self._value


class FakeBoxes:
    def __init__(self, xyxy, conf):
        self.xyxy = FakeTensor(xyxy)
        self.conf = FakeTensor(conf)


class FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


def test_extract_primary_person_detection_selects_highest_confidence_box() -> None:
    result = FakeResult(
        FakeBoxes(
            xyxy=[
                [10, 20, 110, 220],
                [50, 60, 150, 260],
            ],
            conf=[0.4, 0.9],
        ),
    )

    detection = extract_primary_person_detection(result)

    assert detection is not None
    assert detection.confidence == 0.9
    assert detection.bounding_box.x1 == 50.0


def test_extract_primary_person_detection_prefers_box_near_seat() -> None:
    result = FakeResult(
        FakeBoxes(
            xyxy=[
                [10, 20, 110, 220],
                [150, 160, 260, 320],
            ],
            conf=[0.95, 0.55],
        ),
    )

    detection = extract_primary_person_detection(
        result,
        reference_box=BoundingBox(140, 150, 280, 340),
    )

    assert detection is not None
    assert detection.bounding_box.x1 == 150.0
