from __future__ import annotations

import json

from embedagent.session import Action, Observation


def _action_key(action: Action) -> str:
    return json.dumps(
        {"name": action.name, "arguments": action.arguments},
        ensure_ascii=False,
        sort_keys=True,
    )


class LoopGuard(object):
    def __init__(
        self,
        max_consecutive_failures: int = 2,
        max_same_action_failures: int = 3,
        max_same_non_retryable_failures: int = 1,
        max_repeated_tool_calls: int = 3,
    ) -> None:
        self.max_consecutive_failures = max_consecutive_failures
        self.max_same_action_failures = max_same_action_failures
        self.max_same_non_retryable_failures = max_same_non_retryable_failures
        self.max_repeated_tool_calls = max_repeated_tool_calls
        self.consecutive_failures = 0
        self.last_failed_action_key = None  # type: Optional[str]
        self.same_failed_action_count = 0
        self.last_failed_retryable = True
        self.tool_call_history = []  # type: List[str]
        self.failure_count = 0
        self._user_override = False

    def should_block(self, action: Action) -> bool:
        if self._user_override:
            return False
        # Check for repeated tool calls (runaway loop detection)
        recent_calls = self.tool_call_history[-self.max_repeated_tool_calls:]
        if len(recent_calls) >= self.max_repeated_tool_calls:
            if all(c == action.name for c in recent_calls):
                return True
        if not self.last_failed_action_key:
            return False
        if (
            (not self.last_failed_retryable)
            and self.same_failed_action_count >= self.max_same_non_retryable_failures
            and self.last_failed_action_key == _action_key(action)
        ):
            return True
        if (
            self.same_failed_action_count >= self.max_same_action_failures
            and self.last_failed_action_key == _action_key(action)
        ):
            return True
        return False

    def blocked_observation(self, action: Action) -> Observation:
        if not self.last_failed_retryable:
            return Observation(
                tool_name=action.name,
                success=False,
                error="防护触发：同一非重试型阻塞已重复出现，主循环已停止继续尝试。",
                data={
                    "guard": "same_non_retryable_action",
                    "action_name": action.name,
                    "threshold": self.max_same_non_retryable_failures,
                    "retryable": False,
                    "error_kind": "guard_blocked",
                },
            )
        return Observation(
            tool_name=action.name,
            success=False,
            error="防护触发：相同失败工具调用已连续出现，主循环已阻止再次执行。",
            data={
                "guard": "same_failed_action",
                "action_name": action.name,
                "threshold": self.max_same_action_failures,
                "retryable": False,
                "error_kind": "guard_blocked",
            },
        )

    def record(self, action: Action, observation: Observation) -> None:
        if observation.success:
            self.consecutive_failures = 0
            self.failure_count = 0
            self.last_failed_action_key = None
            self.same_failed_action_count = 0
            self.last_failed_retryable = True
            self.tool_call_history.append(action.name)
            return
        # User clicking "deny" on a permission prompt is a deliberate choice,
        # not a tool malfunction.  Do not count it toward the failure thresholds
        # so that a single user rejection does not trigger the guard.
        if isinstance(observation.data, dict):
            if observation.data.get("blocked_by") == "user_confirmation":
                return
            if observation.data.get("error_kind") in ("discarded", "interrupted"):
                return
        self.tool_call_history.append(action.name)
        self.consecutive_failures += 1
        self.failure_count += 1
        action_key = _action_key(action)
        retryable = True
        if isinstance(observation.data, dict) and observation.data.get("retryable") is False:
            retryable = False
        if action_key == self.last_failed_action_key:
            self.same_failed_action_count += 1
        else:
            self.last_failed_action_key = action_key
            self.same_failed_action_count = 1
        self.last_failed_retryable = retryable

    def should_stop(self) -> bool:
        if self._user_override:
            return False
        return self.consecutive_failures >= self.max_consecutive_failures

    def stop_reason(self) -> str:
        if (
            not self.last_failed_retryable
            and self.same_failed_action_count >= self.max_same_non_retryable_failures
        ):
            return "同一非重试型阻塞重复出现，已触发防护。"
        recent_calls = self.tool_call_history[-self.max_repeated_tool_calls:]
        if len(recent_calls) >= self.max_repeated_tool_calls:
            if len(set(recent_calls)) == 1:
                return "repeated tool calls: %s" % recent_calls[0]
        return "连续 %s 次工具调用失败，已触发防护。" % self.max_consecutive_failures

    def user_override(self) -> None:
        """Allow user to override guard decision."""
        self._user_override = True
