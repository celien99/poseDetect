"""运行时配置加载与 JSON -> dataclass 转换入口。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (
    ActionConfig,
    CameraInferenceConfig,
    KeypointProcessingConfig,
    MultiCameraFusionConfig,
    MultiCameraInferenceConfig,
    RuleConfig,
    StateMachineConfig,
    WorkflowStepConfig,
    build_default_rule_actions,
)
from .schemas import BoundingBox, SeatRegions


@dataclass(slots=True)
class RuntimeConfigBundle:
    """聚合多机位协同推理所需的运行配置。"""

    multi_camera_inference: MultiCameraInferenceConfig | None = None
    rules: RuleConfig = field(default_factory=RuleConfig)


def load_runtime_config(path: str) -> RuntimeConfigBundle:
    """从 JSON 文件加载多机位协同推理配置。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rule_payload = dict(payload.get("rules") or {})
    rule_actions = rule_payload.pop("actions", None)
    legacy_action_options = _pop_legacy_rule_action_options(rule_payload)

    multi_camera_payload = payload.get("multi_camera_inference")
    multi_camera_inference = None
    if multi_camera_payload is not None:
        inference_payload = dict(multi_camera_payload)
        state_machine_payload = dict(inference_payload.pop("state_machine", {}) or {})
        state_machine_steps = [
            WorkflowStepConfig(**step_payload)
            for step_payload in state_machine_payload.pop("steps", [])
        ]
        inference_payload["cameras"] = [
            CameraInferenceConfig(
                **{
                    **camera_payload,
                    "seat_regions": _build_seat_regions(camera_payload["seat_regions"]),
                },
            )
            for camera_payload in inference_payload.get("cameras", [])
        ]
        inference_payload["fusion"] = MultiCameraFusionConfig(
            **(inference_payload.pop("fusion", {}) or {}),
        )
        inference_payload["keypoint_processing"] = KeypointProcessingConfig(
            **(inference_payload.pop("keypoint_processing", {}) or {}),
        )
        inference_payload["state_machine"] = StateMachineConfig(
            **state_machine_payload,
            steps=state_machine_steps,
        )
        multi_camera_inference = MultiCameraInferenceConfig(**inference_payload)

    return RuntimeConfigBundle(
        multi_camera_inference=multi_camera_inference,
        rules=RuleConfig(
            **rule_payload,
            actions=(
                build_default_rule_actions(**legacy_action_options)
                if rule_actions is None
                else [ActionConfig(**action_payload) for action_payload in rule_actions]
            ),
        ),
    )


def _pop_legacy_rule_action_options(payload: dict[str, Any]) -> dict[str, Any]:
    """提取旧版固定动作字段，并转换为默认动作的构造参数。"""
    touch_hold_frames = payload.pop("touch_hold_frames", None)
    lift_hold_frames = payload.pop("lift_hold_frames", None)
    touch_wrist_margin = payload.pop("wrist_to_surface_margin", None)
    lift_wrist_margin = payload.pop("wrist_to_bottom_margin", None)
    lift_ratio_threshold = payload.pop("lift_ratio_threshold", None)

    options: dict[str, Any] = {}
    if touch_hold_frames is not None:
        options["touch_hold_frames"] = int(touch_hold_frames)
    if lift_hold_frames is not None:
        options["lift_hold_frames"] = int(lift_hold_frames)
    if touch_wrist_margin is not None:
        options["touch_wrist_margin"] = float(touch_wrist_margin)
    if lift_wrist_margin is not None:
        options["lift_wrist_margin"] = float(lift_wrist_margin)
    if lift_ratio_threshold is not None:
        options["lift_ratio_threshold"] = float(lift_ratio_threshold)
    return options


def _build_seat_regions(payload: dict[str, Any]) -> SeatRegions:
    """把区域配置字典转成 `SeatRegions`。"""
    return SeatRegions(
        overall=_build_box(payload["overall"]),
        side_surface=_build_box(payload["side_surface"]),
        bottom_surface=_build_box(payload["bottom_surface"]),
    )


def _build_box(payload: dict[str, Any]) -> BoundingBox:
    """把矩形框字典标准化成浮点型边界框。"""
    return BoundingBox(
        x1=float(payload["x1"]),
        y1=float(payload["y1"]),
        x2=float(payload["x2"]),
        y2=float(payload["y2"]),
    )
