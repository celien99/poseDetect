"""动作识别结果导出工具。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .schemas import ActionDecision, InspectionResult


def export_action_report(
    output_path: str,
    decisions: list[ActionDecision],
    metadata: dict[str, Any],
    inspection_result: InspectionResult | None = None,
) -> None:
    """把动作结果导出为 JSON，供联调、回溯和系统集成使用。"""
    action_names: list[str] = []
    for decision in decisions:
        for action_name in decision.actions:
            if action_name not in action_names:
                action_names.append(action_name)

    report = {
        "metadata": metadata,
        "summary": {
            "frame_count": len(decisions),
            "action_frames": {
                action_name: [
                    decision.frame_index
                    for decision in decisions
                    if decision.actions.get(action_name, False)
                ]
                for action_name in action_names
            },
            "action_reason_counts": {
                action_name: _collect_reason_counts(decisions, action_name)
                for action_name in action_names
            },
            "action_segments": {
                action_name: _collect_action_segments(decisions, action_name)
                for action_name in action_names
            },
            "final_status": inspection_result.status if inspection_result is not None else None,
            "current_state": inspection_result.current_state if inspection_result is not None else None,
            "completed_steps": inspection_result.completed_steps if inspection_result is not None else [],
        },
        "decisions": [asdict(decision) for decision in decisions],
        "inspection_result": asdict(inspection_result) if inspection_result is not None else None,
    }

    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _collect_reason_counts(
    decisions: list[ActionDecision],
    action_name: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        reason = decision.reasons.get(action_name)
        if reason is None:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _collect_action_segments(
    decisions: list[ActionDecision],
    action_name: str,
) -> list[dict[str, int]]:
    segments: list[dict[str, int]] = []
    start_frame: int | None = None
    previous_frame: int | None = None

    for decision in decisions:
        detected = decision.actions.get(action_name, False)
        if detected and start_frame is None:
            start_frame = decision.frame_index
        if not detected and start_frame is not None and previous_frame is not None:
            segments.append(
                {
                    "start_frame": start_frame,
                    "end_frame": previous_frame,
                    "length": previous_frame - start_frame + 1,
                },
            )
            start_frame = None
        previous_frame = decision.frame_index

    if start_frame is not None and previous_frame is not None:
        segments.append(
            {
                "start_frame": start_frame,
                "end_frame": previous_frame,
                "length": previous_frame - start_frame + 1,
            },
        )
    return segments
