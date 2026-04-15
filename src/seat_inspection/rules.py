from __future__ import annotations

from collections import deque

from .config import ActionConfig, RuleConfig
from .geometry import average_y, normalized_horizontal_reach, point_in_box
from .schemas import ActionDecision, FrameObservation, Point


class ActionRuleEvaluator:
    """基于人体关键点与座椅区域的动作规则评估器。"""

    def __init__(self, config: RuleConfig | None = None) -> None:
        self.config = config or RuleConfig()
        self.actions = self._resolve_actions(self.config)  # 当前启用的动作规则列表
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
        scores, candidates = self._evaluate_actions(observation)
        states: dict[str, bool] = {}
        for action in self.actions:
            history = self._histories[action.name]
            history.append(candidates[action.name])
            states[action.name] = self._held(history)
        return self._build_decision(observation.frame_index, states, scores)

    def evaluate_snapshot(self, observation: FrameObservation) -> ActionDecision:
        """处理单帧快照，不使用历史帧连续判定。"""
        scores, candidates = self._evaluate_actions(observation)
        return self._build_decision(observation.frame_index, candidates, scores)

    def empty_decision(self, frame_index: int) -> ActionDecision:
        """在未检测到人体时返回全 False 的空结果。"""
        states = {action.name: False for action in self.actions}
        scores = {action.name: 0.0 for action in self.actions}
        return self._build_decision(frame_index, states, scores)

    def reset(self) -> None:
        """清空连续帧历史，通常用于视频中断或当前帧无人时。"""
        for history in self._histories.values():
            history.clear()

    def _resolve_actions(self, config: RuleConfig) -> list[ActionConfig]:
        """解析最终生效的动作列表，兼容旧版固定动作配置。"""
        if config.actions:
            return [action for action in config.actions if action.enabled]
        return [
            ActionConfig(
                name="touch_side_surface",
                kind="touch_region",
                region="side_surface",
                hold_frames=config.touch_hold_frames,
                wrist_margin=config.wrist_to_surface_margin,
                min_wrist_count=1,
            ),
            ActionConfig(
                name="lift_seat_bottom",
                kind="lift_region",
                region="bottom_surface",
                hold_frames=config.lift_hold_frames,
                wrist_margin=config.wrist_to_bottom_margin,
                min_wrist_count=2,
                lift_ratio_threshold=config.lift_ratio_threshold,
            ),
        ]

    def _held(self, history: deque[bool]) -> bool:
        """只有当历史窗口全部为真时，动作才算连续成立。"""
        return len(history) == history.maxlen and all(history)

    def _evaluate_actions(self, observation: FrameObservation) -> tuple[dict[str, float], dict[str, bool]]:
        """批量计算所有动作的分数和候选状态。"""
        scores: dict[str, float] = {}
        candidates: dict[str, bool] = {}
        for action in self.actions:
            score, candidate = self._evaluate_action(action, observation)
            scores[action.name] = score
            candidates[action.name] = candidate
        return scores, candidates

    def _evaluate_action(
        self,
        action: ActionConfig,
        observation: FrameObservation,
    ) -> tuple[float, bool]:
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
    ) -> tuple[float, bool]:
        """判断手腕是否触达指定区域。"""
        region_box = self._get_region_box(action, observation)
        wrist_margin = (
            action.wrist_margin
            if action.wrist_margin is not None
            else self.config.wrist_to_surface_margin
        )
        wrists = [
            observation.pose.left_wrist,
            observation.pose.right_wrist,
        ]
        candidates = [
            self._valid_wrist(wrist) and point_in_box(wrist, region_box, wrist_margin)
            for wrist in wrists
        ]
        score = max(
            1.0 - normalized_horizontal_reach(wrist, region_box)
            for wrist in wrists
        )
        return max(0.0, min(1.0, score)), sum(candidates) >= max(1, action.min_wrist_count)

    def _lift_region(
        self,
        action: ActionConfig,
        observation: FrameObservation,
    ) -> tuple[float, bool]:
        """判断双手是否在区域内并完成向上抬起动作。"""
        region_box = self._get_region_box(action, observation)
        wrist_margin = (
            action.wrist_margin
            if action.wrist_margin is not None
            else self.config.wrist_to_bottom_margin
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
            return 0.0, False

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
            else self.config.lift_ratio_threshold
        )
        candidate = (
            sum(wrists_in_region) >= max(1, action.min_wrist_count)
            and lift_ratio >= threshold
        )
        return max(0.0, min(1.0, lift_ratio)), candidate

    def _get_region_box(self, action: ActionConfig, observation: FrameObservation):
        """从区域配置中取出动作绑定的目标区域。"""
        try:
            return getattr(observation.seat_regions, action.region)
        except AttributeError as exc:
            raise ValueError(
                f"Unknown seat region '{action.region}' for action '{action.name}'",
            ) from exc

    def _build_decision(
        self,
        frame_index: int,
        states: dict[str, bool],
        scores: dict[str, float],
    ) -> ActionDecision:
        """把通用动作状态映射回兼容旧结构的决策对象。"""
        return ActionDecision(
            frame_index=frame_index,
            touch_side_surface=states.get("touch_side_surface", False),
            lift_seat_bottom=states.get("lift_seat_bottom", False),
            actions=states,
            scores=scores,
        )

    def _valid_wrist(self, point: Point) -> bool:
        """判断手腕关键点是否达到可用置信度。"""
        return point.confidence >= self.config.min_wrist_confidence

    def _valid_shoulder(self, point: Point) -> bool:
        """判断肩部关键点是否达到可用置信度。"""
        return point.confidence >= self.config.min_shoulder_confidence

    def _valid_hip(self, point: Point) -> bool:
        """判断髋部关键点是否达到可用置信度。"""
        return point.confidence >= self.config.min_hip_confidence
