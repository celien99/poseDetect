"""多相机动作融合。"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .config import MultiCameraFusionConfig
from .schemas import ActionDecision


@dataclass(slots=True)
class CameraDecisionSample:
    """单路相机当前时刻的动作样本。"""

    camera_name: str
    frame_index: int
    timestamp_ms: float | None
    decision: ActionDecision


def fuse_camera_decisions(
    samples: list[CameraDecisionSample],
    frame_index: int,
    fusion_config: MultiCameraFusionConfig | None = None,
) -> ActionDecision:
    """按融合策略把多路动作结果合并为单个决策。"""
    if not samples:
        return ActionDecision(frame_index=frame_index)

    config = fusion_config or MultiCameraFusionConfig()
    aligned_samples = _filter_aligned_samples(samples, config.time_tolerance_ms)

    action_names: list[str] = []
    for sample in aligned_samples:
        for action_name in sample.decision.actions:
            if action_name not in action_names:
                action_names.append(action_name)

    actions: dict[str, bool] = {}
    scores: dict[str, float] = {}
    for action_name in action_names:
        states = [sample.decision.actions.get(action_name, False) for sample in aligned_samples]
        action_scores = [sample.decision.scores.get(action_name, 0.0) for sample in aligned_samples]
        actions[action_name] = _apply_strategy(states, _resolve_strategy(config, action_name))
        scores[action_name] = max(action_scores, default=0.0)

    return ActionDecision(
        frame_index=frame_index,
        actions=actions,
        scores=scores,
    )


def _filter_aligned_samples(
    samples: list[CameraDecisionSample],
    tolerance_ms: float,
) -> list[CameraDecisionSample]:
    timestamps = [sample.timestamp_ms for sample in samples]
    if tolerance_ms < 0 or any(timestamp is None for timestamp in timestamps):
        return samples

    reference = float(median(timestamp for timestamp in timestamps if timestamp is not None))
    aligned = [
        sample
        for sample in samples
        if sample.timestamp_ms is not None and abs(sample.timestamp_ms - reference) <= tolerance_ms
    ]
    return aligned or samples


def _resolve_strategy(config: MultiCameraFusionConfig, action_name: str) -> str:
    normalized = action_name.lower()
    if "lift" in normalized:
        return config.lift_action_strategy
    if "touch" in normalized:
        return config.touch_action_strategy
    return config.default_action_strategy


def _apply_strategy(states: list[bool], strategy: str) -> bool:
    if not states:
        return False

    normalized = strategy.lower()
    if normalized == "all":
        return all(states)
    if normalized == "majority":
        return sum(states) >= (len(states) // 2 + 1)
    if normalized != "any":
        raise ValueError(f"Unsupported fusion strategy: {strategy}")
    return any(states)
