from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from embedagent_core.session import (
    ToolPresentationSnapshot,
)


class _Record(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _as_record(value: Any) -> Any:
    if isinstance(value, dict):
        return _Record((str(key), _as_record(item)) for key, item in value.items())
    if isinstance(value, list):
        return [_as_record(item) for item in value]
    return value


def _display_transition_reason(reason: str) -> str:
    value = str(reason or "").strip()
    mapping = {
        "aborted": "cancelled",
        "guard_stop": "guard",
        "permission_wait": "waiting_permission",
        "permission_required": "waiting_permission",
        "user_input_wait": "waiting_user_input",
        "user_input_required": "waiting_user_input",
    }
    return mapping.get(value, value)


def _transition_kind(reason: str) -> str:
    value = str(reason or "").strip()
    if value == "permission_wait":
        return "permission_required"
    if value == "user_input_wait":
        return "user_input_required"
    return value


class SessionHistoryAssembler(object):
    def __init__(
        self,
        tool_catalog_lookup: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        runtime_snapshot_lookup: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self._tool_catalog_lookup = tool_catalog_lookup
        self._runtime_snapshot_lookup = runtime_snapshot_lookup

    def build(
        self,
        history: Dict[str, Any],
        history_source: str,
        integrity_status: str,
        restore_stop_reason: str = "",
        consumed_event_count: int = 0,
        transcript_event_count: int = 0,
    ) -> Dict[str, Any]:
        session = _as_record(history)
        runtime = self._runtime_snapshot_lookup() if callable(self._runtime_snapshot_lookup) else {}
        turns = []
        activities = []
        for turn_index, turn in enumerate(session.turns):
            steps = []
            if turn.user_message:
                activities.append(
                    {
                        "kind": "user",
                        "id": self._message_id_for_turn(session, turn.turn_id, "user")
                        or "user-%s" % turn.turn_id,
                        "turn_id": turn.turn_id,
                        "step_id": "",
                        "step_index": 0,
                        "content": turn.user_message,
                        "status": "completed",
                        "projection_source": str(history_source or ""),
                    }
                )
            for step_index, step in enumerate(turn.steps):
                step_transitions = self._step_transitions(turn_index, step_index, session)
                step_transition = step_transitions[-1] if step_transitions else None
                step_status = self._step_status(
                    step, step_transition, turn_index, step_index, session
                )
                if step.reasoning:
                    activities.append(
                        {
                            "kind": "reasoning",
                            "id": "reasoning-%s" % step.step_id,
                            "turn_id": turn.turn_id,
                            "step_id": step.step_id,
                            "step_index": step.step_index,
                            "content": step.reasoning,
                            "status": step_status,
                            "projection_source": str(history_source or ""),
                        }
                    )
                serialized_tools = [
                    self._serialize_tool_call(record, runtime) for record in step.tool_calls
                ]
                for tool in serialized_tools:
                    activities.append(
                        {
                            "kind": "tool",
                            "id": "tool-%s" % str(tool.get("call_id") or ""),
                            "turn_id": turn.turn_id,
                            "step_id": step.step_id,
                            "step_index": step.step_index,
                            "content": "",
                            "status": str(tool.get("status") or "running"),
                            "projection_source": str(history_source or ""),
                            "tool_name": str(tool.get("tool_name") or ""),
                            "tool_label": str(tool.get("tool_label") or ""),
                            "call_id": str(tool.get("call_id") or ""),
                            "arguments": dict(tool.get("arguments") or {}),
                            "data": tool.get("data"),
                            "error": str(tool.get("error") or ""),
                            "permission_category": str(tool.get("permission_category") or ""),
                            "supports_diff_preview": bool(tool.get("supports_diff_preview")),
                            "progress_renderer_key": str(
                                tool.get("progress_renderer_key") or "default"
                            ),
                            "result_renderer_key": str(
                                tool.get("result_renderer_key") or "default"
                            ),
                        }
                    )
                if step.assistant_message:
                    activities.append(
                        {
                            "kind": "assistant",
                            "id": self._message_id_for_step(
                                session, turn.turn_id, step.step_id, "assistant"
                            )
                            or "assistant-%s" % step.step_id,
                            "turn_id": turn.turn_id,
                            "step_id": step.step_id,
                            "step_index": step.step_index,
                            "content": step.assistant_message,
                            "status": step_status,
                            "projection_source": str(history_source or ""),
                        }
                    )
                steps.append(
                    {
                        "step_id": step.step_id,
                        "step_index": step.step_index,
                        "reasoning": step.reasoning,
                        "assistant_text": step.assistant_message,
                        "tool_calls": serialized_tools,
                        "transitions": [
                            self._serialize_transition(transition)
                            for transition in step_transitions
                        ],
                        "status": step_status,
                    }
                )
            turns.append(
                {
                    "turn_id": turn.turn_id,
                    "user_text": turn.user_message,
                    "steps": steps,
                    "transitions": [
                        self._serialize_transition(transition) for transition in turn.transitions
                    ],
                    "status": self._turn_status(turn),
                }
            )
        return {
            "session_id": session.session_id,
            "history_source": str(history_source or ""),
            "turns": turns,
            "activities": activities,
            "current_interaction": self._serialize_pending_interaction(
                getattr(session, "current_interaction", None)
            ),
            "integrity": {
                "status": str(integrity_status or "healthy"),
                "restore_stop_reason": str(restore_stop_reason or ""),
                "consumed_event_count": int(consumed_event_count or 0),
                "transcript_event_count": int(transcript_event_count or 0),
            },
        }

    def _serialize_tool_call(self, record: Any, runtime: Dict[str, Any]) -> Dict[str, Any]:
        presentation = self._resolve_tool_presentation(record)
        observation = record.observation
        return {
            "call_id": record.call_id,
            "tool_name": record.tool_name,
            "arguments": dict(record.arguments),
            "status": self._tool_status(record),
            "data": observation.data if observation is not None else None,
            "error": observation.error if observation is not None else "",
            "tool_label": presentation["tool_label"],
            "permission_category": presentation["permission_category"],
            "supports_diff_preview": presentation["supports_diff_preview"],
            "progress_renderer_key": presentation["progress_renderer_key"],
            "result_renderer_key": presentation["result_renderer_key"],
            "runtime_source": str(runtime.get("runtime_source") or ""),
            "resolved_tool_roots": dict(runtime.get("resolved_tool_roots") or {}),
            "fallback_warnings": list(runtime.get("fallback_warnings") or []),
        }

    def _resolve_tool_presentation(self, record: Any) -> Dict[str, Any]:
        snapshot = (
            record.presentation
            if isinstance(record.presentation, ToolPresentationSnapshot)
            else ToolPresentationSnapshot()
        )
        raw_snapshot = getattr(record, "presentation", None)
        if isinstance(raw_snapshot, dict):
            snapshot = ToolPresentationSnapshot(
                tool_label=str(raw_snapshot.get("tool_label") or ""),
                permission_category=str(raw_snapshot.get("permission_category") or ""),
                supports_diff_preview=bool(raw_snapshot.get("supports_diff_preview")),
                progress_renderer_key=str(raw_snapshot.get("progress_renderer_key") or "default"),
                result_renderer_key=str(raw_snapshot.get("result_renderer_key") or "default"),
            )
        catalog_entry = {}
        if callable(self._tool_catalog_lookup):
            item = self._tool_catalog_lookup(record.tool_name) or {}
            if isinstance(item, dict):
                catalog_entry = item
        use_snapshot = self._snapshot_has_value(snapshot)
        return {
            "tool_label": (
                snapshot.tool_label
                if use_snapshot and snapshot.tool_label
                else str(catalog_entry.get("user_label") or record.tool_name)
            ),
            "permission_category": (
                snapshot.permission_category
                if use_snapshot
                else str(catalog_entry.get("permission_category") or "")
            ),
            "supports_diff_preview": (
                bool(snapshot.supports_diff_preview)
                if use_snapshot
                else bool(catalog_entry.get("supports_diff_preview"))
            ),
            "progress_renderer_key": (
                snapshot.progress_renderer_key
                if use_snapshot and snapshot.progress_renderer_key
                else str(catalog_entry.get("progress_renderer_key") or "default")
            ),
            "result_renderer_key": (
                snapshot.result_renderer_key
                if use_snapshot and snapshot.result_renderer_key
                else str(catalog_entry.get("result_renderer_key") or "default")
            ),
        }

    def _snapshot_has_value(self, snapshot: ToolPresentationSnapshot) -> bool:
        return bool(
            snapshot.tool_label
            or snapshot.permission_category
            or snapshot.supports_diff_preview
            or snapshot.progress_renderer_key not in ("", "default")
            or snapshot.result_renderer_key not in ("", "default")
        )

    def _serialize_transition(self, transition: Any) -> Dict[str, Any]:
        kind = _transition_kind(str(getattr(transition, "reason", "") or ""))
        metadata = dict(getattr(transition, "metadata", {}) or {})
        pending = getattr(transition, "pending_interaction", None)
        if pending is not None:
            metadata.setdefault("interaction_id", str(pending.interaction_id or ""))
            if pending.kind == "permission":
                metadata.setdefault(
                    "permission", dict(pending.request_payload.get("permission") or {})
                )
            elif pending.kind == "user_input":
                metadata.setdefault(
                    "user_input", dict(pending.request_payload.get("request") or {})
                )
        return {
            "kind": kind,
            "display_reason": _display_transition_reason(
                str(getattr(transition, "reason", "") or "")
            ),
            "message": str(getattr(transition, "message", "") or ""),
            "metadata": metadata,
        }

    def _serialize_pending_interaction(self, pending: Optional[Any]) -> Optional[Dict[str, Any]]:
        if pending is None:
            return None
        return {
            "interaction_id": str(pending.interaction_id or ""),
            "kind": str(pending.kind or ""),
            "tool_name": str(pending.tool_name or ""),
            "request_payload": dict(pending.request_payload or {}),
            "created_at": str(pending.created_at or ""),
            "status": str(pending.status or ""),
            "resolution_payload": dict(pending.resolution_payload or {}),
        }

    def _tool_status(self, record: Any) -> str:
        if record.observation is not None:
            return "success" if record.observation.success else "error"
        if str(record.status or "") in ("pending", "started"):
            return "running"
        return str(record.status or "running")

    def _turn_status(self, turn: Any) -> str:
        pending = getattr(turn, "pending_interaction", None)
        if pending is not None:
            if pending.kind == "permission":
                return "waiting_permission"
            if pending.kind == "user_input":
                return "waiting_user_input"
        transitions = list(getattr(turn, "transitions", []) or [])
        if not transitions:
            return "completed"
        for transition in reversed(transitions):
            reason = str(getattr(transition, "reason", "") or "")
            if reason == "command_result":
                continue
            if reason == "permission_wait":
                return "waiting_permission"
            if reason == "user_input_wait":
                return "waiting_user_input"
            return reason or "completed"
        return "completed"

    def _step_status(
        self,
        step: Any,
        step_transition: Optional[Any],
        turn_index: int,
        step_index: int,
        session: Any,
    ) -> str:
        turn = session.turns[turn_index]
        is_last_step = step_index == len(turn.steps) - 1
        pending = getattr(turn, "pending_interaction", None)
        if is_last_step and pending is not None:
            if pending.kind == "permission":
                return "permission_wait"
            if pending.kind == "user_input":
                return "user_input_wait"
        transitions = self._step_transitions(turn_index, step_index, session)
        for transition in reversed(transitions):
            reason = str(getattr(transition, "reason", "") or "")
            if reason == "command_result":
                continue
            if reason:
                return reason
        return str(getattr(step, "status", "") or "completed")

    def _step_transitions(
        self,
        turn_index: int,
        step_index: int,
        session: Any,
    ) -> list:
        turn = session.turns[turn_index]
        step = turn.steps[step_index]
        transitions = []
        if getattr(step, "transition", None) is not None:
            transitions.append(step.transition)
        if step_index == len(turn.steps) - 1 and turn.transitions:
            for transition in turn.transitions:
                if transition not in transitions:
                    transitions.append(transition)
        return transitions

    def _find_message_for_turn_step(self, session, turn_id, step_id, role):
        """Find the transcript message matching turn_id, step_id, and role."""
        for msg in session.messages:
            if (
                getattr(msg, "turn_id", "") == turn_id
                and getattr(msg, "step_id", "") == step_id
                and getattr(msg, "role", "") == role
            ):
                return msg
        return None

    def _message_id_for_turn(self, session, turn_id, role):
        for msg in session.messages:
            if getattr(msg, "turn_id", "") == turn_id and getattr(msg, "role", "") == role:
                return getattr(msg, "message_id", "")
        return ""

    def _message_id_for_step(self, session, turn_id, step_id, role):
        message = self._find_message_for_turn_step(session, turn_id, step_id, role)
        return getattr(message, "message_id", "") if message is not None else ""
