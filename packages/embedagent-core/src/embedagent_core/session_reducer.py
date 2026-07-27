from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Set

from embedagent_core.session import Session


class SessionReduceError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "session_reduce_error")
        super(SessionReduceError, self).__init__(self.reason)


@dataclass
class SessionReducerContext:
    current_mode: str = ""
    seen_turn_ids: Set[str] = field(default_factory=set)
    seen_step_ids: Set[str] = field(default_factory=set)
    seen_message_ids: Set[str] = field(default_factory=set)
    seen_tool_call_ids: Set[str] = field(default_factory=set)
    seen_interaction_ids: Set[str] = field(default_factory=set)
    seen_boundary_ids: Set[str] = field(default_factory=set)
    seen_compacted_history_ids: Set[str] = field(default_factory=set)


class SessionReducer(object):
    _STATE_NEUTRAL_TYPES = frozenset(
        (
            "operation_started",
            "operation_finished",
            "operation_interrupted",
            "tool_use",
            "command_execution",
            "interaction",
            "runtime_configured",
            "resource_reloaded",
            "recovery_marker",
        )
    )

    def __init__(self) -> None:
        self._handlers = {"session_meta": self._apply_session_meta}

    def apply(
        self,
        session: Session,
        context: SessionReducerContext,
        event: Dict[str, Any],
    ) -> None:
        if int(event.get("schema_version") or 0) != 2:
            raise SessionReduceError("unsupported_schema_version")
        if str(event.get("session_id") or "") != session.session_id:
            raise SessionReduceError("session_id_mismatch")
        event_type = str(event.get("type") or "")
        if event_type in self._STATE_NEUTRAL_TYPES:
            return
        handler = self._handlers.get(event_type)
        if handler is None:
            raise SessionReduceError("unknown_event_type")
        handler(session, context, dict(event.get("payload") or {}))

    def _apply_session_meta(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        context.current_mode = str(payload.get("current_mode") or context.current_mode)
        if payload.get("started_at"):
            session.started_at = str(payload["started_at"])
