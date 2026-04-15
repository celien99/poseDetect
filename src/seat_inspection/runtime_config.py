"""运行时配置加载与 JSON -> dataclass 转换入口。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (
    ActionConfig,
    CameraInferenceConfig,
    CollectionConfig,
    ImageInferenceConfig,
    InferenceConfig,
    KeypointProcessingConfig,
    MultiCameraFusionConfig,
    MultiCameraInferenceConfig,
    RuleConfig,
    StateMachineConfig,
    TrainingConfig,
    WorkflowStepConfig,
)
from .schemas import BoundingBox, SeatRegions


@dataclass(slots=True)
class RuntimeConfigBundle:
    """聚合训练、采集、视频推理和图片推理所需的运行配置。"""

    training: TrainingConfig | None = None
    inference: InferenceConfig | None = None
    multi_camera_inference: MultiCameraInferenceConfig | None = None
    image_inference: ImageInferenceConfig | None = None
    collection: CollectionConfig | None = None
    rules: RuleConfig = field(default_factory=RuleConfig)


def load_runtime_config(path: str) -> RuntimeConfigBundle:
    """从 JSON 文件加载整套运行配置。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    training_payload = payload.get("training")
    inference_payload = payload.get("inference")
    multi_camera_inference_payload = payload.get("multi_camera_inference")
    image_inference_payload = payload.get("image_inference")
    collection_payload = payload.get("collection")
    rules_payload = payload.get("rules", {})

    return RuntimeConfigBundle(
        training=_build_training_config(training_payload),
        inference=_build_inference_config(inference_payload),
        multi_camera_inference=_build_multi_camera_inference_config(multi_camera_inference_payload),
        image_inference=_build_image_inference_config(image_inference_payload),
        collection=_build_collection_config(collection_payload),
        rules=_build_rule_config(rules_payload),
    )


def _build_training_config(payload: dict[str, Any] | None) -> TrainingConfig | None:
    """构造训练配置，不存在时返回 `None`。"""
    if payload is None:
        return None
    return TrainingConfig(**payload)


def _build_inference_config(payload: dict[str, Any] | None) -> InferenceConfig | None:
    """构造视频推理配置，并把区域字典转成结构化对象。"""
    if payload is None:
        return None

    config_payload = dict(payload)
    config_payload["seat_regions"] = _build_seat_regions(config_payload["seat_regions"])
    config_payload["keypoint_processing"] = _build_keypoint_processing_config(
        config_payload.get("keypoint_processing"),
    )
    config_payload["state_machine"] = _build_state_machine_config(
        config_payload.get("state_machine"),
    )
    return InferenceConfig(**config_payload)


def _build_image_inference_config(payload: dict[str, Any] | None) -> ImageInferenceConfig | None:
    """构造单张图片推理配置。"""
    if payload is None:
        return None

    config_payload = dict(payload)
    config_payload["seat_regions"] = _build_seat_regions(config_payload["seat_regions"])
    config_payload["keypoint_processing"] = _build_keypoint_processing_config(
        config_payload.get("keypoint_processing"),
    )
    config_payload["state_machine"] = _build_state_machine_config(
        config_payload.get("state_machine"),
    )
    return ImageInferenceConfig(**config_payload)


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


def _build_collection_config(payload: dict[str, Any] | None) -> CollectionConfig | None:
    """构造数据采集配置。"""
    if payload is None:
        return None
    return CollectionConfig(**payload)


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
    """构造动作规则配置，同时解析自定义动作列表。"""
    config_payload = dict(payload)
    action_payloads = config_payload.pop("actions", [])
    config_payload["actions"] = [
        ActionConfig(**action_payload)
        for action_payload in action_payloads
    ]
    return RuleConfig(**config_payload)


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
