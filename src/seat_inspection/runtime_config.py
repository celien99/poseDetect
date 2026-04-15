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
    return RuntimeConfigBundle(
        multi_camera_inference=_build_multi_camera_inference_config(
            payload.get("multi_camera_inference"),
        ),
        rules=_build_rule_config(payload.get("rules", {})),
    )


def _build_multi_camera_inference_config(
    payload: dict[str, Any] | None,
) -> MultiCameraInferenceConfig | None:
    """构造多相机推理配置。"""
    if payload is None:
        return None

    config_payload = dict(payload)
    config_payload["cameras"] = [
        _build_camera_inference_config(camera_payload)
        for camera_payload in config_payload.get("cameras", [])
    ]
    config_payload["fusion"] = _build_multi_camera_fusion_config(
        config_payload.get("fusion"),
    )
    config_payload["keypoint_processing"] = _build_keypoint_processing_config(
        config_payload.get("keypoint_processing"),
    )
    config_payload["state_machine"] = _build_state_machine_config(
        config_payload.get("state_machine"),
    )
    return MultiCameraInferenceConfig(**config_payload)


def _build_keypoint_processing_config(payload: dict[str, Any] | None) -> KeypointProcessingConfig:
    """构造关键点时序处理配置。"""
    if payload is None:
        return KeypointProcessingConfig()
    return KeypointProcessingConfig(**payload)


def _build_state_machine_config(payload: dict[str, Any] | None) -> StateMachineConfig:
    """构造流程状态机配置。"""
    if payload is None:
        return StateMachineConfig()

    config_payload = dict(payload)
    config_payload["steps"] = [
        WorkflowStepConfig(**step_payload)
        for step_payload in config_payload.get("steps", [])
    ]
    return StateMachineConfig(**config_payload)


def _build_multi_camera_fusion_config(payload: dict[str, Any] | None) -> MultiCameraFusionConfig:
    """构造多相机融合配置。"""
    if payload is None:
        return MultiCameraFusionConfig()
    return MultiCameraFusionConfig(**payload)


def _build_rule_config(payload: dict[str, Any]) -> RuleConfig:
    """构造动作规则配置，同时兼容旧版固定动作字段。"""
    config_payload = dict(payload)
    action_payloads = config_payload.pop("actions", None)
    legacy_action_options = _pop_legacy_rule_action_options(config_payload)
    if action_payloads is None:
        config_payload["actions"] = build_default_rule_actions(**legacy_action_options)
    else:
        config_payload["actions"] = [
            ActionConfig(**action_payload)
            for action_payload in action_payloads
        ]
    return RuleConfig(**config_payload)


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


def _build_camera_inference_config(payload: dict[str, Any]) -> CameraInferenceConfig:
    """构造多相机模式下的单路相机配置。"""
    config_payload = dict(payload)
    config_payload["seat_regions"] = _build_seat_regions(config_payload["seat_regions"])
    return CameraInferenceConfig(**config_payload)


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
