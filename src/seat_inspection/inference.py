from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
from media_inputs import FrameStream, load_image_frame, open_frame_stream

from .config import ImageInferenceConfig, InferenceConfig, RuleConfig
from .engine import ActionRecognitionEngine
from .person_detection import PersonDetector
from .pipeline import InspectionPipeline
from .pose_estimation import PoseEstimator
from .region_provider import build_seat_region_provider
from .reporting import export_action_report
from .schemas import ActionDecision, FrameObservation
from .visualization import annotate_frame


def run_rule_based_inference(
    observations: Iterable[FrameObservation],
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    """直接对结构化观测序列运行规则，不依赖 YOLO 模型。"""
    engine = ActionRecognitionEngine(rule_config)
    return engine.process_stream(observations)


def run_video_inference(
    config: InferenceConfig,
    rule_config: RuleConfig | None = None,
) -> list[ActionDecision]:
    """对视频流或 MVS 相机流执行姿态推理与动作识别。"""
    engine = ActionRecognitionEngine(
        rule_config,
        config.keypoint_processing,
        config.state_machine,
    )
    pipeline = InspectionPipeline(
        pose_estimator=PoseEstimator(config.pose_model_path),
        seat_region_provider=build_seat_region_provider(
            config.seat_regions,
            config.seat_model_path,
            confidence=config.confidence,
            iou=config.iou,
            device=config.device,
        ),
        engine=engine,
        confidence=config.confidence,
        iou=config.iou,
        device=config.device,
        person_detector=PersonDetector(config.person_model_path),
    )
    stream = open_frame_stream(config.source)

    if not stream.is_opened():
        raise ValueError(f"Unable to open inference source: {config.source}")

    writer = _build_writer(stream, config)
    decisions: list[ActionDecision] = []

    try:
        while True:
            media_frame = stream.read_frame()
            if media_frame is None:
                break

            frame_result = pipeline.process_frame(
                frame=media_frame.image,
                frame_index=media_frame.frame_index,
                snapshot=False,
            )
            decisions.append(frame_result.decision)

            if writer is not None:
                annotated = annotate_frame(
                    media_frame.image,
                    frame_result.seat_regions,
                    frame_result.decision,
                    frame_result.inspection_result,
                    frame_result.person_detection,
                )
                writer.write(annotated)
    finally:
        stream.release()
        if writer is not None:
            writer.release()

    inspection_result = pipeline.finalize()

    export_action_report(
        config.output_json_path,
        decisions,
        metadata={
            "source": config.source,
            "pose_model_path": config.pose_model_path,
            "person_model_path": config.person_model_path,
            "seat_region_mode": pipeline.seat_region_provider.mode,
            "seat_model_path": config.seat_model_path,
            "save_visualization": config.save_visualization,
            "mode": "video",
        },
        inspection_result=inspection_result,
    )
    return decisions


def run_image_inference(
    config: ImageInferenceConfig,
    rule_config: RuleConfig | None = None,
) -> ActionDecision:
    """对单张图片执行姿态推理与动作判断。"""
    media_frame = load_image_frame(config.source)

    engine = ActionRecognitionEngine(
        rule_config,
        config.keypoint_processing,
        config.state_machine,
    )
    pipeline = InspectionPipeline(
        pose_estimator=PoseEstimator(config.pose_model_path),
        seat_region_provider=build_seat_region_provider(
            config.seat_regions,
            config.seat_model_path,
            confidence=config.confidence,
            iou=config.iou,
            device=config.device,
        ),
        engine=engine,
        confidence=config.confidence,
        iou=config.iou,
        device=config.device,
        person_detector=PersonDetector(config.person_model_path),
    )
    frame_result = pipeline.process_frame(
        frame=media_frame.image,
        frame_index=media_frame.frame_index,
        snapshot=True,
    )
    inspection_result = pipeline.finalize()

    annotated_image_path = config.output_image_path
    if config.save_visualization:
        annotated_image_path = annotated_image_path or "outputs/action_image_preview.jpg"
        annotated = annotate_frame(
            media_frame.image,
            frame_result.seat_regions,
            frame_result.decision,
            inspection_result,
            frame_result.person_detection,
        )
        output_path = Path(annotated_image_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), annotated)

    export_action_report(
        config.output_json_path,
        [frame_result.decision],
        metadata={
            "source": config.source,
            "pose_model_path": config.pose_model_path,
            "person_model_path": config.person_model_path,
            "seat_region_mode": pipeline.seat_region_provider.mode,
            "seat_model_path": config.seat_model_path,
            "save_visualization": config.save_visualization,
            "output_image_path": annotated_image_path,
            "mode": "image",
        },
        inspection_result=inspection_result,
    )
    return frame_result.decision


def _build_writer(
    stream: FrameStream,
    config: InferenceConfig,
) -> cv2.VideoWriter | None:
    """按输入视频尺寸创建可视化输出视频写入器。"""
    if not config.save_visualization:
        return None

    output_path = config.output_video_path or "outputs/action_preview.mp4"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    width = int(stream.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = stream.get(cv2.CAP_PROP_FPS) or 25.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(output_path, fourcc, fps, (width, height))
