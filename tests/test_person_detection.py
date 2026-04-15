from seat_inspection.person_detection import extract_primary_person_detection


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
