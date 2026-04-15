"""动作流程状态机。

职责：
- 把逐帧动作判定提升为“流程步骤是否完成”
- 生成更适合业务消费的 OK / NG 结果与事件日志
"""

from __future__ import annotations

from dataclasses import replace

from .config import StateMachineConfig, WorkflowStepConfig
from .schemas import ActionDecision, InspectionResult, WorkflowEvent, WorkflowStepState


class InspectionStateMachine:
    """面向流程检测的顺序状态机。"""

    def __init__(self, config: StateMachineConfig | None = None) -> None:
        self.config = config or StateMachineConfig()
        self.reset()

    def reset(self) -> None:
        """重置流程状态。"""
        self._step_index = 0
        self._hold_count = 0
        self._events: list[WorkflowEvent] = []
        self._step_states = [
            WorkflowStepState(name=step.name, action=step.action)
            for step in self.config.steps
        ]
        self._seen_positive_action = False

    def update(self, decision: ActionDecision) -> InspectionResult:
        """用当前帧动作结果驱动状态机向前推进。"""
        if not self.config.enabled:
            return self._build_result(status="PENDING", current_state="disabled")

        if any(decision.actions.values()):
            self._seen_positive_action = True

        if not self.config.steps:
            return self._build_result(status="PENDING", current_state="stateless")

        current_step = self.config.steps[self._step_index] if self._step_index < len(self.config.steps) else None
        if current_step is None:
            return self._build_result(status=self.config.ok_label, current_state="completed")

        if decision.actions.get(current_step.action, False):
            self._hold_count += 1
            if self._hold_count >= max(1, current_step.min_frames):
                self._complete_current_step(decision.frame_index, current_step)
        else:
            self._hold_count = 0

        if self._step_index >= len(self.config.steps):
            return self._build_result(status=self.config.ok_label, current_state="completed")

        next_step_name = self.config.steps[self._step_index].name
        return self._build_result(
            status="PENDING",
            current_state="in_progress",
            current_step=next_step_name,
        )

    def finalize(self) -> InspectionResult:
        """在视频结束时输出最终流程结果。"""
        if not self.config.enabled:
            return self._build_result(status="PENDING", current_state="disabled")

        if not self.config.steps:
            status = self.config.ok_label if self._seen_positive_action else self.config.ng_label
            current_state = "completed" if self._seen_positive_action else "no_action_detected"
            return self._build_result(status=status, current_state=current_state)

        if self._step_index >= len(self.config.steps):
            return self._build_result(status=self.config.ok_label, current_state="completed")

        if not self.config.require_all_steps and self._step_index > 0:
            return self._build_result(status=self.config.ok_label, current_state="partial_completed")

        return self._build_result(
            status=self.config.ng_label,
            current_state="incomplete",
            current_step=self.config.steps[self._step_index].name,
        )

    def _complete_current_step(self, frame_index: int, step: WorkflowStepConfig) -> None:
        step_state = self._step_states[self._step_index]
        self._step_states[self._step_index] = replace(
            step_state,
            completed=True,
            completed_frame=frame_index,
        )
        self._events.append(
            WorkflowEvent(
                frame_index=frame_index,
                event_type="step_completed",
                message=f"Step '{step.name}' completed by action '{step.action}'",
            ),
        )
        self._step_index += 1
        self._hold_count = 0

    def _build_result(
        self,
        status: str,
        current_state: str,
        current_step: str | None = None,
    ) -> InspectionResult:
        return InspectionResult(
            status=status,
            current_state=current_state,
            current_step=current_step,
            completed_steps=[
                step.name
                for step in self._step_states
                if step.completed
            ],
            step_states=list(self._step_states),
            events=list(self._events),
        )
