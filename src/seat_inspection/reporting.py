from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .schemas import ActionDecision


def export_action_report(
    output_path: str,
    decisions: list[ActionDecision],
    metadata: dict[str, Any],
) -> None:
    report = {
        "metadata": metadata,
        "summary": {
            "frame_count": len(decisions),
            "touch_side_surface_frames": [
                decision.frame_index
                for decision in decisions
                if decision.touch_side_surface
            ],
            "lift_seat_bottom_frames": [
                decision.frame_index
                for decision in decisions
                if decision.lift_seat_bottom
            ],
        },
        "decisions": [asdict(decision) for decision in decisions],
    }

    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
