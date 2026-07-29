from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Dict, Optional, Tuple

from embedagent_core.session import Session


class _SessionReadRecord(dict):
    def __init__(self, record_kind: str, values: Dict[str, Any]) -> None:
        dict.__init__(self, values)
        object.__setattr__(self, "_record_kind", str(record_kind or "record"))

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        del name, value
        raise TypeError("session read records are immutable")

    def __setitem__(self, key: Any, value: Any) -> None:
        del key, value
        raise TypeError("session read records are immutable")

    def __delitem__(self, key: Any) -> None:
        del key
        raise TypeError("session read records are immutable")

    def clear(self) -> None:
        raise TypeError("session read records are immutable")

    def pop(self, key: Any, default: Any = None) -> Any:
        del key, default
        raise TypeError("session read records are immutable")

    def popitem(self) -> Any:
        raise TypeError("session read records are immutable")

    def setdefault(self, key: Any, default: Any = None) -> Any:
        del key, default
        raise TypeError("session read records are immutable")

    def update(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise TypeError("session read records are immutable")

    def __deepcopy__(self, memo: Dict[int, Any]) -> "_SessionReadRecord":
        del memo
        return self

    def to_api_dict(self) -> Dict[str, Any]:
        if self._record_kind == "action":
            arguments = str(self.get("raw_arguments") or "")
            if not arguments:
                import json

                arguments = json.dumps(_thaw(self.get("arguments") or {}), ensure_ascii=False)
            return {
                "id": str(self.get("call_id") or ""),
                "type": "function",
                "function": {
                    "name": str(self.get("name") or ""),
                    "arguments": arguments,
                },
            }
        payload = {
            "role": str(self.get("role") or ""),
            "content": str(self.get("content") or ""),
        }
        if self.get("name"):
            payload["name"] = str(self.get("name"))
        if self.get("tool_call_id"):
            payload["tool_call_id"] = str(self.get("tool_call_id"))
        action_calls = tuple(self.get("action_calls") or ())
        if action_calls:
            payload["tool_calls"] = [action.to_api_dict() for action in action_calls]
        if self.get("reasoning_content"):
            payload["reasoning_content"] = str(self.get("reasoning_content"))
        return payload

    def to_dict(self) -> Dict[str, Any]:
        if self._record_kind == "observation":
            return {
                "success": bool(self.get("success")),
                "error": self.get("error"),
                "data": _thaw(self.get("data")),
            }
        return _thaw(self)


@dataclass(frozen=True)
class SessionReadView:
    session_id: str
    started_at: str
    messages: Tuple[Dict[str, Any], ...]
    turns: Tuple[Dict[str, Any], ...]
    workflow_state: Dict[str, Any]
    compact_boundaries: Tuple[Dict[str, Any], ...]
    compacted_history: Tuple[Dict[str, Any], ...]
    content_replacements: Tuple[Dict[str, Any], ...]
    latest_context_snapshot: Dict[str, Any]
    pending_interaction: Optional[Dict[str, Any]] = None

    def latest_compact_boundary(self) -> Optional[Dict[str, Any]]:
        return self.compact_boundaries[-1] if self.compact_boundaries else None

    def latest_compacted_history(self) -> Optional[Dict[str, Any]]:
        return self.compacted_history[-1] if self.compacted_history else None

    def current_step(self) -> Optional[Dict[str, Any]]:
        if not self.turns:
            return None
        steps = tuple(self.turns[-1].get("steps") or ())
        return steps[-1] if steps else None


def session_read_view(session: Session) -> SessionReadView:
    if not isinstance(session, Session):
        raise TypeError("session must be Session")
    return SessionReadView(
        session_id=str(session.session_id or ""),
        started_at=str(session.started_at or ""),
        messages=tuple(
            _message_record(item)
            for item in list(session.messages or [])
            if not bool(getattr(item, "archived", False))
        ),
        turns=tuple(_turn_record(item) for item in list(session.turns or [])),
        workflow_state=_freeze(session.workflow_state or {}),
        compact_boundaries=tuple(
            _record("compact_boundary", _object_fields(item))
            for item in list(session.compact_boundaries or [])
        ),
        compacted_history=tuple(
            _record("compacted_history", item.to_dict())
            for item in list(session.compacted_history or [])
        ),
        content_replacements=tuple(
            _record("content_replacement", dict(item or {}))
            for item in list(session.content_replacements or [])
        ),
        latest_context_snapshot=_freeze(session.latest_context_snapshot or {}),
        pending_interaction=(
            _record("pending_interaction", _object_fields(session.pending_interaction))
            if session.pending_interaction is not None
            else None
        ),
    )


def _turn_record(turn: Any) -> _SessionReadRecord:
    return _record(
        "turn",
        {
            "user_message": str(getattr(turn, "user_message", "") or ""),
            "turn_id": str(getattr(turn, "turn_id", "") or ""),
            "assistant_message": str(getattr(turn, "assistant_message", "") or ""),
            "actions": tuple(_action_record(item) for item in list(turn.actions or [])),
            "observations": tuple(
                _observation_record(item) for item in list(turn.observations or [])
            ),
            "steps": tuple(_step_record(item) for item in list(turn.steps or [])),
            "message_start_index": int(turn.message_start_index or 0),
            "message_end_index": int(turn.message_end_index or 0),
            "pending_interaction": (
                _record("pending_interaction", _object_fields(turn.pending_interaction))
                if turn.pending_interaction is not None
                else None
            ),
            "transitions": tuple(
                _record("transition", _object_fields(item)) for item in list(turn.transitions or [])
            ),
            "compact_boundaries": tuple(
                _record("compact_boundary", _object_fields(item))
                for item in list(turn.compact_boundaries or [])
            ),
        },
    )


def _step_record(step: Any) -> _SessionReadRecord:
    return _record(
        "step",
        {
            "step_id": str(getattr(step, "step_id", "") or ""),
            "step_index": int(getattr(step, "step_index", 0) or 0),
            "reasoning": str(getattr(step, "reasoning", "") or ""),
            "assistant_message": str(getattr(step, "assistant_message", "") or ""),
            "actions": tuple(_action_record(item) for item in list(step.actions or [])),
            "observations": tuple(
                _observation_record(item) for item in list(step.observations or [])
            ),
            "tool_calls": tuple(
                _record("tool_call", _object_fields(item)) for item in list(step.tool_calls or [])
            ),
            "status": str(getattr(step, "status", "") or ""),
            "transition": (
                _record("transition", _object_fields(step.transition))
                if step.transition is not None
                else None
            ),
        },
    )


def _message_record(message: Any) -> _SessionReadRecord:
    return _record(
        "message",
        {
            "role": str(getattr(message, "role", "") or ""),
            "content": str(getattr(message, "content", "") or ""),
            "name": getattr(message, "name", None),
            "tool_call_id": getattr(message, "tool_call_id", None),
            "action_calls": tuple(
                _action_record(item) for item in list(message.action_calls or [])
            ),
            "reasoning_content": str(getattr(message, "reasoning_content", "") or ""),
            "message_id": str(getattr(message, "message_id", "") or ""),
            "parent_message_id": str(getattr(message, "parent_message_id", "") or ""),
            "turn_id": str(getattr(message, "turn_id", "") or ""),
            "step_id": str(getattr(message, "step_id", "") or ""),
            "kind": str(getattr(message, "kind", "message") or "message"),
            "metadata": _freeze(getattr(message, "metadata", {}) or {}),
            "replaced_by_refs": tuple(getattr(message, "replaced_by_refs", []) or []),
            "archived": bool(getattr(message, "archived", False)),
        },
    )


def _action_record(action: Any) -> _SessionReadRecord:
    return _record(
        "action",
        {
            "name": str(getattr(action, "name", "") or ""),
            "arguments": _freeze(getattr(action, "arguments", {}) or {}),
            "call_id": str(getattr(action, "call_id", "") or ""),
            "raw_arguments": str(getattr(action, "raw_arguments", "") or ""),
        },
    )


def _observation_record(observation: Any) -> _SessionReadRecord:
    return _record(
        "observation",
        {
            "tool_name": str(getattr(observation, "tool_name", "") or ""),
            "success": bool(getattr(observation, "success", False)),
            "error": getattr(observation, "error", None),
            "data": _freeze(getattr(observation, "data", None)),
        },
    )


def _object_fields(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    return dict((name, _freeze(item)) for name, item in vars(value).items())


def _record(record_kind: str, values: Dict[str, Any]) -> _SessionReadRecord:
    return _SessionReadRecord(
        record_kind,
        dict((str(key), _freeze(value)) for key, value in dict(values or {}).items()),
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, _SessionReadRecord):
        return value
    if isinstance(value, dict):
        return _record("mapping", value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze(item) for item in value), key=lambda item: str(item)))
    if is_dataclass(value):
        return _record(
            type(value).__name__,
            dict((item.name, _freeze(getattr(value, item.name))) for item in fields(value)),
        )
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _thaw(value: Any) -> Any:
    if isinstance(value, dict):
        return dict((str(key), _thaw(item)) for key, item in value.items())
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
