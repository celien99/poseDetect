import json

from seat_inspection.reporting import export_action_report
from seat_inspection.schemas import ActionDecision


def test_export_action_report_includes_action_reason_counts(tmp_path) -> None:
    output_path = tmp_path / "report.json"

    export_action_report(
        str(output_path),
        decisions=[
            ActionDecision(
                frame_index=1,
                actions={"touch_side_surface": False},
                scores={"touch_side_surface": 0.2},
                reasons={"touch_side_surface": "wrist_not_in_region"},
            ),
            ActionDecision(
                frame_index=2,
                actions={"touch_side_surface": True},
                scores={"touch_side_surface": 0.9},
                reasons={"touch_side_surface": "detected"},
            ),
        ],
        metadata={"mode": "test"},
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["summary"]["action_reason_counts"]["touch_side_surface"] == {
        "wrist_not_in_region": 1,
        "detected": 1,
    }
    assert "touch_side_surface_frames" not in payload["summary"]
