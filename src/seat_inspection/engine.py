from __future__ import annotations

from typing import Iterable

from .config import RuleConfig
from .rules import ActionRuleEvaluator
from .schemas import ActionDecision, FrameObservation


class ActionRecognitionEngine:
    """动作识别引擎。"""
    def __init__(self, rule_config: RuleConfig | None = None) -> None:
        self.evaluator = ActionRuleEvaluator(rule_config)

    def process_frame(self, observation: FrameObservation) -> ActionDecision:
        return self.evaluator.evaluate(observation)

    def process_stream(
        self,
        observations: Iterable[FrameObservation],
    ) -> list[ActionDecision]:
        return [self.process_frame(observation) for observation in observations]

    def reset(self) -> None:
        self.evaluator.reset()
