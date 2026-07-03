from __future__ import annotations

import hashlib
import json

from embedagent_core.session import Action, Observation


def _action_key(action: Action) -> str:
    return json.dumps(
        {"name": action.name, "arguments": action.arguments},
        ensure_ascii=False,
        sort_keys=True,
    )


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _normalize_for_fingerprint(value):
    if isinstance(value, dict):
        return {str(key): _normalize_for_fingerprint(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_fingerprint(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _fingerprint_payload(payload) -> str:
    return json.dumps(_normalize_for_fingerprint(payload), ensure_ascii=False, sort_keys=True)


def _action_progress_fingerprint(action: Action) -> str:
    arguments = dict(action.arguments or {})
    if action.name in (
        "write_file",
        "edit_file",
        "read_file",
        "list_dir",
        "glob_files",
        "grep_text",
    ):
        return _fingerprint_payload(
            {
                "tool": action.name,
                "path": arguments.get("path") or arguments.get("root") or "",
                "pattern": arguments.get("pattern") or "",
                "content_hash": (
                    _short_hash(str(arguments.get("content") or ""))
                    if action.name == "write_file"
                    else ""
                ),
                "old_hash": (
                    _short_hash(str(arguments.get("old_text") or ""))
                    if action.name == "edit_file"
                    else ""
                ),
                "new_hash": (
                    _short_hash(str(arguments.get("new_text") or ""))
                    if action.name == "edit_file"
                    else ""
                ),
            }
        )
    if action.name == "bash":
        return _fingerprint_payload(
            {
                "tool": action.name,
                "cwd": arguments.get("cwd") or ".",
                "command": arguments.get("command") or "",
            }
        )
    return _action_key(action)


def _observation_evidence_fingerprint(observation: Observation) -> str:
    data = observation.data if isinstance(observation.data, dict) else {}
    if data:
        return _fingerprint_payload(
            {
                "success": observation.success,
                "path": data.get("path") or "",
                "created": data.get("created"),
                "overwritten": data.get("overwritten"),
                "exit_code": data.get("exit_code"),
                "error_kind": data.get("error_kind") or "",
                "outcome_class": data.get("outcome_class") or "",
                "stdout_hash": _short_hash(str(data.get("stdout") or "")),
                "stderr_hash": _short_hash(str(data.get("stderr") or "")),
                "error": observation.error or "",
            }
        )
    return _fingerprint_payload(
        {
            "success": observation.success,
            "error": observation.error or "",
            "data": observation.data,
        }
    )


def _progress_key(action: Action, observation: Observation) -> str:
    return _fingerprint_payload(
        {
            "action": _action_progress_fingerprint(action),
            "evidence": _observation_evidence_fingerprint(observation),
        }
    )


def _is_diagnostic_failure(observation: Observation) -> bool:
    if not isinstance(observation.data, dict):
        return False
    outcome_class = str(observation.data.get("outcome_class") or "")
    return outcome_class == "diagnostic_failure"


class ProgressGuard(object):
    def __init__(
        self,
        max_consecutive_failures: int = 2,
        max_same_action_failures: int = 3,
        max_same_non_retryable_failures: int = 1,
        max_repeated_no_progress: int = 3,
    ) -> None:
        self.max_consecutive_failures = max_consecutive_failures
        self.max_same_action_failures = max_same_action_failures
        self.max_same_non_retryable_failures = max_same_non_retryable_failures
        self.max_repeated_no_progress = max_repeated_no_progress
        self.consecutive_failures = 0
        self.last_failed_action_key = None  # type: Optional[str]
        self.same_failed_action_count = 0
        self.last_failed_retryable = True
        self.no_progress_history = []  # type: List[str]
        self.failure_count = 0
        self._user_override = False

    def should_block(self, action: Action) -> bool:
        if self._user_override:
            return False
        recent = self.no_progress_history[-self.max_repeated_no_progress :]
        if len(recent) >= self.max_repeated_no_progress and len(set(recent)) == 1:
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
            self.no_progress_history.append(_progress_key(action, observation))
            return
        # User clicking "deny" on a permission prompt is a deliberate choice,
        # not a tool malfunction.  Do not count it toward the failure thresholds
        # so that a single user rejection does not trigger the guard.
        if isinstance(observation.data, dict):
            if observation.data.get("blocked_by") == "user_confirmation":
                return
            if observation.data.get("error_kind") in ("discarded", "interrupted"):
                return
            if _is_diagnostic_failure(observation):
                self.no_progress_history.append(_progress_key(action, observation))
                return
        self.no_progress_history.append(_progress_key(action, observation))
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
        recent = self.no_progress_history[-self.max_repeated_no_progress :]
        if len(recent) >= self.max_repeated_no_progress and len(set(recent)) == 1:
            return "repeated no-progress action"
        return "连续 %s 次工具调用失败，已触发防护。" % self.max_consecutive_failures

    def user_override(self) -> None:
        """Allow user to override guard decision."""
        self._user_override = True
