"""检测流水线编排层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .engine import ActionRecognitionEngine
from .person_detection import PersonDetector
from .pose_estimation import PoseEstimator, build_observation_from_pose_result
from .region_provider import SeatRegionProvider
from .schemas import ActionDecision, FrameObservation, InspectionResult, PersonDetection, SeatRegions


@dataclass(slots=True)
class PipelineFrameResult:
    """流水线处理单帧后的完整结果。"""

    frame_index: int
    seat_regions: SeatRegions
    person_detection: PersonDetection | None
    observation: FrameObservation | None
    decision: ActionDecision
    inspection_result: InspectionResult


class InspectionPipeline:
    """把人体检测、区域提供、姿态估计、动作识别串起来的处理流水线。"""

    def __init__(
        self,
        pose_estimator: PoseEstimator,
        seat_region_provider: SeatRegionProvider,
        engine: ActionRecognitionEngine,
        confidence: float,
        iou: float,
        device: str,
        person_detector: PersonDetector | None = None,
    ) -> None:
        self.pose_estimator = pose_estimator
        self.seat_region_provider = seat_region_provider
        self.engine = engine
        self.person_detector = person_detector or PersonDetector()
        self.confidence = confidence
        self.iou = iou
        self.device = device

    def process_frame(
        self,
        frame: Any,
        frame_index: int,
        snapshot: bool = False,
    ) -> PipelineFrameResult:
        """处理单帧并返回各层输出。"""
        seat_regions = self.seat_region_provider.get_regions(frame)
        pose_result = self.pose_estimator.predict(
            frame,
            confidence=self.confidence,
            iou=self.iou,
            device=self.device,
        )
        person_detection = self._detect_person(frame, pose_result)
        observation = build_observation_from_pose_result(
            frame_index=frame_index,
            result=pose_result,
            seat_regions=seat_regions,
        )

        if observation is None:
            if not snapshot:
                self.engine.reset_frame_context()
            decision = self.engine.empty_decision(frame_index)
        elif snapshot:
            decision = self.engine.process_snapshot(observation)
        else:
            decision = self.engine.process_frame(observation)

        inspection_result = self.engine.update_state(decision)
        return PipelineFrameResult(
            frame_index=frame_index,
            seat_regions=seat_regions,
            person_detection=person_detection,
            observation=observation,
            decision=decision,
            inspection_result=inspection_result,
        )

    def finalize(self) -> InspectionResult:
        """输出整段流程的最终状态。"""
        return self.engine.finalize_state()

    def _detect_person(self, frame: Any, pose_result: Any) -> PersonDetection | None:
        """优先走独立人体检测，否则回退到姿态结果的人体框。"""
        if self.person_detector.enabled:
            return self.person_detector.detect(
                frame,
                confidence=self.confidence,
                iou=self.iou,
                device=self.device,
            )
        return self.person_detector.extract_from_pose_result(pose_result)
