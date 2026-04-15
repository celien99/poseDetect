from __future__ import annotations

from typing import Iterable

from .config import KeypointProcessingConfig, RuleConfig, StateMachineConfig
from .preprocessing import KeypointSequenceProcessor
from .rules import ActionRuleEvaluator
from .schemas import ActionDecision, FrameObservation, InspectionResult
from .state_machine import InspectionStateMachine


class ActionRecognitionEngine:
    """对外暴露的动作识别引擎。

    内部包含三层核心处理：
    - 关键点处理层：平滑、补帧
    - 动作识别层：几何规则、空间关系、时间逻辑
    - 状态机层：把动作结果提升为流程 OK / NG
    """

    def __init__(
        self,
        rule_config: RuleConfig | None = None,
        keypoint_processing_config: KeypointProcessingConfig | None = None,
        state_machine_config: StateMachineConfig | None = None,
    ) -> None:
        self.evaluator = ActionRuleEvaluator(rule_config)
        self.keypoint_processor = KeypointSequenceProcessor(keypoint_processing_config)
        self.state_machine = InspectionStateMachine(state_machine_config)

    @property
    def action_names(self) -> list[str]:
        """返回当前启用动作名称。"""
        return self.evaluator.action_names

    def process_frame(self, observation: FrameObservation) -> ActionDecision:
        """处理视频流中的单帧观测。"""
        processed = self._preprocess_observation(observation)
        return self.evaluator.evaluate(processed)

    def process_snapshot(self, observation: FrameObservation) -> ActionDecision:
        """处理图片等无时间历史的单帧观测。"""
        processed = self._preprocess_observation(observation)
        return self.evaluator.evaluate_snapshot(processed)

    def process_stream(
        self,
        observations: Iterable[FrameObservation],
    ) -> list[ActionDecision]:
        """批量处理一个观测序列。"""
        return [self.process_frame(observation) for observation in observations]

    def empty_decision(self, frame_index: int) -> ActionDecision:
        """生成空判定，供无人帧或解析失败时使用。"""
        return self.evaluator.empty_decision(frame_index)

    @property
    def max_action_gap_frames(self) -> int:
        """返回动作识别允许的最大连续漏检帧数。"""
        return max(0, self.evaluator.config.max_action_gap_frames)

    def update_state(self, decision: ActionDecision) -> InspectionResult:
        """用当前帧动作结果推进流程状态机。"""
        return self.state_machine.update(decision)

    def snapshot_state(self) -> InspectionResult:
        """返回当前流程状态快照，不推进状态机。"""
        return self.state_machine.snapshot()

    def finalize_state(self) -> InspectionResult:
        """在流结束时生成最终流程结果。"""
        return self.state_machine.finalize()

    def reset(self) -> None:
        """重置引擎内部所有状态。"""
        self.evaluator.reset()
        self.keypoint_processor.reset()
        self.state_machine.reset()

    def reset_frame_context(self) -> None:
        """仅重置逐帧上下文，不清空流程状态机。"""
        self.evaluator.reset()
        self.keypoint_processor.reset()

    def _preprocess_observation(self, observation: FrameObservation) -> FrameObservation:
        """在进入规则层前，对姿态关键点做时序增强。"""
        return FrameObservation(
            frame_index=observation.frame_index,
            seat_regions=observation.seat_regions,
            pose=self.keypoint_processor.process(observation.pose),
        )
