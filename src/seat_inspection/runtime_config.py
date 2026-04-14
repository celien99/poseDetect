from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import InferenceConfig, RuleConfig, TrainingConfig
from .schemas import BoundingBox, SeatRegions


@dataclass(slots=True)
class RuntimeConfigBundle:
    training: TrainingConfig | None = None
    inference: InferenceConfig | None = None
    rules: RuleConfig = field(default_factory=RuleConfig)


def load_runtime_config(path: str) -> RuntimeConfigBundle:
    """加载运行时配置。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    training_payload = payload.get("training")
    inference_payload = payload.get("inference")
    rules_payload = payload.get("rules", {})

    return RuntimeConfigBundle(
        training=_build_training_config(training_payload),
        inference=_build_inference_config(inference_payload),
        rules=RuleConfig(**rules_payload),
    )


def _build_training_config(payload: dict[str, Any] | None) -> TrainingConfig | None:
    if payload is None:
        return None
    return TrainingConfig(**payload)


def _build_inference_config(payload: dict[str, Any] | None) -> InferenceConfig | None:
    if payload is None:
        return None

    config_payload = dict(payload)
    config_payload["seat_regions"] = _build_seat_regions(config_payload["seat_regions"])
    return InferenceConfig(**config_payload)


def _build_seat_regions(payload: dict[str, Any]) -> SeatRegions:
    return SeatRegions(
        overall=_build_box(payload["overall"]),
        side_surface=_build_box(payload["side_surface"]),
        bottom_surface=_build_box(payload["bottom_surface"]),
    )


def _build_box(payload: dict[str, Any]) -> BoundingBox:
    return BoundingBox(
        x1=float(payload["x1"]),
        y1=float(payload["y1"]),
        x2=float(payload["x2"]),
        y2=float(payload["y2"]),
    )
