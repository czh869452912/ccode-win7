from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List


def _text(value: Any) -> str:
    return str(value or "").strip()


def _copy_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _stable_append(items: List[Dict[str, Any]], item: Dict[str, Any]) -> None:
    if item not in items:
        items.append(item)


def _status_from_transition(reason: str) -> str:
    if reason == "completed":
        return "completed"
    if reason == "guard_stop":
        return "blocked"
    if reason == "max_turns":
        return "partial"
    if reason == "aborted":
        return "aborted"
    if reason.endswith("_wait"):
        return "waiting"
    return reason or "running"


@dataclass
class TurnExperienceState(object):
    status: str = "running"
    completed: List[Dict[str, Any]] = field(default_factory=list)
    unverified: List[Dict[str, Any]] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    critical_files: List[str] = field(default_factory=list)
    blocker: Dict[str, Any] = field(default_factory=dict)
    last_failure: Dict[str, Any] = field(default_factory=dict)
    last_transition: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "completed": [dict(item) for item in self.completed],
            "unverified": [dict(item) for item in self.unverified],
            "next_steps": list(self.next_steps),
            "critical_files": list(self.critical_files),
            "blocker": dict(self.blocker),
            "last_failure": dict(self.last_failure),
            "last_transition": dict(self.last_transition),
        }


class TurnExperienceReducer(object):
    """Reduce transcript events into a shell-facing turn experience read model."""

    def reduce(self, events: List[Dict[str, Any]]) -> TurnExperienceState:
        state = TurnExperienceState()
        active_turn_id = ""
        for event in list(events or []):
            if not isinstance(event, dict):
                continue
            event_type = _text(event.get("type"))
            payload = _copy_dict(event.get("payload"))
            if event_type == "operation_started" and _text(payload.get("kind")) == "turn":
                active_turn_id = _text(payload.get("turn_id"))
                state = TurnExperienceState()
                continue
            payload_turn_id = _text(payload.get("turn_id"))
            if active_turn_id and payload_turn_id and payload_turn_id != active_turn_id:
                continue
            if event_type == "tool_result":
                self._apply_tool_result(state, payload)
            elif event_type == "loop_transition":
                self._apply_transition(state, payload)
        self._finalize(state)
        return state

    def _apply_tool_result(self, state: TurnExperienceState, payload: Dict[str, Any]) -> None:
        tool_name = _text(payload.get("tool_name"))
        observation = _copy_dict(payload.get("observation"))
        data = _copy_dict(observation.get("data"))
        success = bool(observation.get("success"))
        if tool_name in ("write_file", "edit_file") and success:
            path = _text(data.get("path"))
            if path:
                if path not in state.critical_files:
                    state.critical_files.append(path)
                kind = "file_created" if data.get("created") else "file_modified"
                _stable_append(state.completed, {"kind": kind, "path": path})
            return
        if tool_name == "bash" and not success:
            command = _text(data.get("command") or data.get("requested_command"))
            failure = {
                "tool_name": tool_name,
                "command": command,
                "exit_code": int(data.get("exit_code") or 0),
                "error": _text(observation.get("error")),
            }
            state.last_failure = failure
            if self._is_validation_result(data):
                _stable_append(
                    state.unverified,
                    {
                        "kind": "validation_failed",
                        "command": command,
                        "exit_code": failure["exit_code"],
                    },
                )

    def _apply_transition(self, state: TurnExperienceState, payload: Dict[str, Any]) -> None:
        reason = _text(payload.get("reason"))
        message = _text(payload.get("message"))
        state.status = _status_from_transition(reason)
        state.last_transition = {
            "reason": reason,
            "message": message,
            "turns_used": int(payload.get("turns_used") or 0),
        }
        if reason == "guard_stop":
            state.blocker = {
                "reason": reason,
                "message": message,
            }

    def _finalize(self, state: TurnExperienceState) -> None:
        if state.completed and not any(
            item.get("kind") == "validation_failed" for item in state.unverified
        ):
            _stable_append(
                state.unverified,
                {
                    "kind": "validation_missing",
                    "message": "Created files have not been validated.",
                },
            )
        if state.blocker:
            self._append_next(
                state,
                "Review the blocker, then resume the session after changing the action or project state.",
            )
            if state.completed:
                self._append_next(state, "Run validation for the changed files.")
            return
        if any(item.get("kind") == "validation_failed" for item in state.unverified):
            self._append_next(state, "Inspect the failed validation output and fix the project.")
        elif any(item.get("kind") == "validation_missing" for item in state.unverified):
            self._append_next(state, "Run validation for the changed files.")

    def _append_next(self, state: TurnExperienceState, message: str) -> None:
        if message not in state.next_steps:
            state.next_steps.append(message)

    def _is_validation_result(self, data: Dict[str, Any]) -> bool:
        if data.get("validation") is True:
            return True
        return _text(data.get("result_kind")) == "validation"
