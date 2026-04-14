from __future__ import annotations

from collections import deque

from .config import RuleConfig
from .geometry import average_y, normalized_horizontal_reach, point_in_box
from .schemas import ActionDecision, FrameObservation, Point


class ActionRuleEvaluator:
    """动作规则评估器。"""
    def __init__(self, config: RuleConfig | None = None) -> None:
        self.config = config or RuleConfig()
        self._touch_history: deque[bool] = deque(maxlen=self.config.touch_hold_frames)
        self._lift_history: deque[bool] = deque(maxlen=self.config.lift_hold_frames)

    def evaluate(self, observation: FrameObservation) -> ActionDecision:
        touch_score, touch_candidate = self._touch_side_surface(observation)
        lift_score, lift_candidate = self._lift_seat_bottom(observation)

        self._touch_history.append(touch_candidate)
        self._lift_history.append(lift_candidate)

        return ActionDecision(
            frame_index=observation.frame_index,
            touch_side_surface=self._held(self._touch_history),
            lift_seat_bottom=self._held(self._lift_history),
            scores={
                "touch_side_surface": touch_score,
                "lift_seat_bottom": lift_score,
            },
        )

    def reset(self) -> None:
        self._touch_history.clear()
        self._lift_history.clear()

    def _held(self, history: deque[bool]) -> bool:
        return len(history) == history.maxlen and all(history)

    def _touch_side_surface(self, observation: FrameObservation) -> tuple[float, bool]:
        left_wrist = observation.pose.left_wrist
        right_wrist = observation.pose.right_wrist
        side_box = observation.seat_regions.side_surface

        candidates = [
            self._valid_wrist(left_wrist) and point_in_box(
                left_wrist,
                side_box,
                self.config.wrist_to_surface_margin,
            ),
            self._valid_wrist(right_wrist) and point_in_box(
                right_wrist,
                side_box,
                self.config.wrist_to_surface_margin,
            ),
        ]

        reach_score = max(
            1.0 - normalized_horizontal_reach(left_wrist, side_box),
            1.0 - normalized_horizontal_reach(right_wrist, side_box),
        )
        return max(0.0, min(1.0, reach_score)), any(candidates)

    def _lift_seat_bottom(self, observation: FrameObservation) -> tuple[float, bool]:
        left_wrist = observation.pose.left_wrist
        right_wrist = observation.pose.right_wrist
        bottom_box = observation.seat_regions.bottom_surface

        wrists_near_bottom = (
            self._valid_wrist(left_wrist)
            and self._valid_wrist(right_wrist)
            and point_in_box(left_wrist, bottom_box, self.config.wrist_to_bottom_margin)
            and point_in_box(right_wrist, bottom_box, self.config.wrist_to_bottom_margin)
        )

        shoulder_y = average_y(
            observation.pose.left_shoulder,
            observation.pose.right_shoulder,
        )
        hip_y = average_y(observation.pose.left_hip, observation.pose.right_hip)
        torso_height = max(1.0, hip_y - shoulder_y)
        wrist_y = average_y(left_wrist, right_wrist)
        lift_ratio = max(0.0, (hip_y - wrist_y) / torso_height)
        candidate = wrists_near_bottom and lift_ratio >= self.config.lift_ratio_threshold
        return max(0.0, min(1.0, lift_ratio)), candidate

    def _valid_wrist(self, point: Point) -> bool:
        return point.confidence >= self.config.min_wrist_confidence
