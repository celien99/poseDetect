from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .config import (
    ActionConfig,
    DEFAULT_LIFT_RATIO_THRESHOLD,
    DEFAULT_LIFT_WRIST_MARGIN,
    DEFAULT_TOUCH_WRIST_MARGIN,
    RuleConfig,
)
from .geometry import average_y, normalized_horizontal_reach, point_in_box
from .schemas import ActionDecision, FrameObservation, Point


@dataclass(slots=True)
class ActionEvaluation:
    """单个动作在当前帧的原始评估结果。"""

    score: float
    candidate: bool
    reason: str
    diagnostics: dict[str, float | int | bool | str]


class ActionRuleEvaluator:
    """基于人体关键点与座椅区域的动作规则评估器。"""

    def __init__(self, config: RuleConfig | None = None) -> None:
        self.config = config or RuleConfig()
        self.actions = [action for action in self.config.actions if action.enabled]
        self._histories = {
            action.name: deque(maxlen=max(1, action.hold_frames))
            for action in self.actions
        }

    @property
    def action_names(self) -> list[str]:
        """返回当前启用的动作名称，便于外部做可视化或报表汇总。"""
        return [action.name for action in self.actions]

    def evaluate(self, observation: FrameObservation) -> ActionDecision:
        """处理连续视频帧，会应用 `hold_frames` 连续成立判定。"""
        evaluations = self._evaluate_actions(observation)
        states: dict[str, bool] = {}
        scores: dict[str, float] = {}
        reasons: dict[str, str] = {}
        diagnostics: dict[str, dict[str, float | int | bool | str]] = {}
        for action in self.actions:
            evaluation = evaluations[action.name]
            history = self._histories[action.name]
            history.append(evaluation.candidate)
            states[action.name] = self._held(history)
            scores[action.name] = evaluation.score
            diagnostics[action.name] = {
                **evaluation.diagnostics,
                "hold_frames_required": history.maxlen,
                "hold_frames_observed": sum(history),
            }
            reasons[action.name] = (
                "detected"
                if states[action.name]
                else "hold_frames_pending" if evaluation.candidate else evaluation.reason
            )
        return ActionDecision(
            frame_index=observation.frame_index,
            actions=states,
            scores=scores,
            reasons=reasons,
            diagnostics=diagnostics,
        )

    def evaluate_snapshot(self, observation: FrameObservation) -> ActionDecision:
        """处理单帧快照，不使用历史帧连续判定。"""
        evaluations = self._evaluate_actions(observation)
        states = {name: evaluation.candidate for name, evaluation in evaluations.items()}
        scores = {name: evaluation.score for name, evaluation in evaluations.items()}
        reasons = {
            name: "detected" if evaluation.candidate else evaluation.reason
            for name, evaluation in evaluations.items()
        }
        diagnostics = {
            name: evaluation.diagnostics
            for name, evaluation in evaluations.items()
        }
        return ActionDecision(
            frame_index=observation.frame_index,
            actions=states,
            scores=scores,
            reasons=reasons,
            diagnostics=diagnostics,
        )

    def empty_decision(self, frame_index: int) -> ActionDecision:
        """在未检测到人体时返回全 False 的空结果。"""
        states = {action.name: False for action in self.actions}
        scores = {action.name: 0.0 for action in self.actions}
        reasons = {action.name: "no_observation" for action in self.actions}
        diagnostics = {
            action.name: {
                "hold_frames_required": max(1, action.hold_frames),
                "hold_frames_observed": 0,
            }
            for action in self.actions
        }
        return ActionDecision(
            frame_index=frame_index,
            actions=states,
            scores=scores,
            reasons=reasons,
            diagnostics=diagnostics,
        )

    def reset(self) -> None:
        """清空连续帧历史，通常用于视频中断或当前帧无人时。"""
        for history in self._histories.values():
            history.clear()

    def _held(self, history: deque[bool]) -> bool:
        """只有当历史窗口全部为真时，动作才算连续成立。"""
        return len(history) == history.maxlen and all(history)

    def _evaluate_actions(self, observation: FrameObservation) -> dict[str, ActionEvaluation]:
        """批量计算所有动作的原始评估结果。"""
        evaluations: dict[str, ActionEvaluation] = {}
        for action in self.actions:
            evaluations[action.name] = self._evaluate_action(action, observation)
        return evaluations

    def _evaluate_action(
        self,
        action: ActionConfig,
        observation: FrameObservation,
    ) -> ActionEvaluation:
        """根据动作类型分发到具体的规则实现。"""
        if action.kind == "touch_region":
            return self._touch_region(action, observation)
        if action.kind == "lift_region":
            return self._lift_region(action, observation)
        raise ValueError(f"Unsupported action kind: {action.kind}")

    def _touch_region(
        self,
        action: ActionConfig,
        observation: FrameObservation,
    ) -> ActionEvaluation:
        """判断手腕是否触达指定区域。"""
        region_box = self._get_region_box(action, observation)
        wrist_margin = (
            action.wrist_margin
            if action.wrist_margin is not None
            else DEFAULT_TOUCH_WRIST_MARGIN
        )
        wrists = [
            observation.pose.left_wrist,
            observation.pose.right_wrist,
        ]
        valid_wrists = [self._valid_wrist(wrist) for wrist in wrists]
        wrists_in_region = [
            self._valid_wrist(wrist) and point_in_box(wrist, region_box, wrist_margin)
            for wrist in wrists
        ]
        reach_scores = [
            max(0.0, 1.0 - normalized_horizontal_reach(wrist, region_box))
            for wrist in wrists
        ]
        extension_ratios = [
            self._arm_extension_ratio(observation, wrist, index)
            if valid_wrists[index]
            else 0.0
            for index, wrist in enumerate(wrists)
        ]
        reach_threshold = max(0.0, self.config.reach_ratio_threshold)
        candidate = (
            sum(wrists_in_region) >= max(1, action.min_wrist_count)
            and max(extension_ratios, default=0.0) >= reach_threshold
        )
        if not any(valid_wrists):
            reason = "no_valid_wrist"
        elif sum(wrists_in_region) < max(1, action.min_wrist_count):
            reason = "wrist_not_in_region"
        elif max(extension_ratios, default=0.0) < reach_threshold:
            reason = "insufficient_reach"
        else:
            reason = "candidate_detected"
        score = max(
            0.0,
            min(
                1.0,
                0.6 * max(reach_scores, default=0.0)
                + 0.4 * min(1.0, max(extension_ratios, default=0.0)),
            ),
        )
        return ActionEvaluation(
            score=score,
            candidate=candidate,
            reason=reason,
            diagnostics={
                "valid_wrist_count": sum(valid_wrists),
                "wrists_in_region": sum(wrists_in_region),
                "min_wrist_count_required": max(1, action.min_wrist_count),
                "reach_ratio_threshold": reach_threshold,
                "max_arm_extension_ratio": max(extension_ratios, default=0.0),
                "max_region_reach_score": max(reach_scores, default=0.0),
            },
        )

    def _lift_region(
        self,
        action: ActionConfig,
        observation: FrameObservation,
    ) -> ActionEvaluation:
        """判断双手是否在区域内并完成向上抬起动作。"""
        region_box = self._get_region_box(action, observation)
        wrist_margin = (
            action.wrist_margin
            if action.wrist_margin is not None
            else DEFAULT_LIFT_WRIST_MARGIN
        )
        wrists = [
            observation.pose.left_wrist,
            observation.pose.right_wrist,
        ]
        wrists_in_region = [
            self._valid_wrist(wrist) and point_in_box(wrist, region_box, wrist_margin)
            for wrist in wrists
        ]
        shoulders_valid = self._valid_shoulder(observation.pose.left_shoulder) and self._valid_shoulder(
            observation.pose.right_shoulder,
        )
        hips_valid = self._valid_hip(observation.pose.left_hip) and self._valid_hip(
            observation.pose.right_hip,
        )
        if not shoulders_valid or not hips_valid:
            return ActionEvaluation(
                score=0.0,
                candidate=False,
                reason="missing_torso_keypoints",
                diagnostics={
                    "valid_wrist_count": sum(self._valid_wrist(wrist) for wrist in wrists),
                    "wrists_in_region": sum(wrists_in_region),
                    "torso_keypoints_valid": False,
                },
            )

        shoulder_y = average_y(
            observation.pose.left_shoulder,
            observation.pose.right_shoulder,
        )
        hip_y = average_y(
            observation.pose.left_hip,
            observation.pose.right_hip,
        )
        torso_height = max(1.0, hip_y - shoulder_y)
        valid_wrists = [wrist for wrist in wrists if self._valid_wrist(wrist)]
        if valid_wrists:
            wrist_y = sum(wrist.y for wrist in valid_wrists) / len(valid_wrists)
        else:
            wrist_y = average_y(observation.pose.left_wrist, observation.pose.right_wrist)
        lift_ratio = max(0.0, (hip_y - wrist_y) / torso_height)
        threshold = (
            action.lift_ratio_threshold
            if action.lift_ratio_threshold is not None
            else DEFAULT_LIFT_RATIO_THRESHOLD
        )
        candidate = (
            sum(wrists_in_region) >= max(1, action.min_wrist_count)
            and lift_ratio >= threshold
        )
        if not valid_wrists:
            reason = "no_valid_wrist"
        elif sum(wrists_in_region) < max(1, action.min_wrist_count):
            reason = "insufficient_wrists_in_region"
        elif lift_ratio < threshold:
            reason = "insufficient_lift_ratio"
        else:
            reason = "candidate_detected"
        return ActionEvaluation(
            score=max(0.0, min(1.0, lift_ratio)),
            candidate=candidate,
            reason=reason,
            diagnostics={
                "valid_wrist_count": len(valid_wrists),
                "wrists_in_region": sum(wrists_in_region),
                "min_wrist_count_required": max(1, action.min_wrist_count),
                "lift_ratio": lift_ratio,
                "lift_ratio_threshold": threshold,
                "torso_height": torso_height,
                "torso_keypoints_valid": True,
            },
        )

    def _get_region_box(self, action: ActionConfig, observation: FrameObservation):
        """从区域配置中取出动作绑定的目标区域。"""
        try:
            return getattr(observation.seat_regions, action.region)
        except AttributeError as exc:
            raise ValueError(
                f"Unknown seat region '{action.region}' for action '{action.name}'",
            ) from exc

    def _valid_wrist(self, point: Point) -> bool:
        """判断手腕关键点是否达到可用置信度。"""
        return point.confidence >= self.config.min_wrist_confidence

    def _valid_shoulder(self, point: Point) -> bool:
        """判断肩部关键点是否达到可用置信度。"""
        return point.confidence >= self.config.min_shoulder_confidence

    def _valid_hip(self, point: Point) -> bool:
        """判断髋部关键点是否达到可用置信度。"""
        return point.confidence >= self.config.min_hip_confidence

    def _arm_extension_ratio(
        self,
        observation: FrameObservation,
        wrist: Point,
        wrist_index: int,
    ) -> float:
        """估算手腕相对同侧肩部的水平伸展比例。"""
        torso_width = max(
            1.0,
            abs(observation.pose.right_shoulder.x - observation.pose.left_shoulder.x),
        )
        shoulder = observation.pose.left_shoulder if wrist_index == 0 else observation.pose.right_shoulder
        return abs(wrist.x - shoulder.x) / torso_width
