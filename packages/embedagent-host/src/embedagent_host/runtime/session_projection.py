from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from embedagent_core.compaction_state import CompactionStateReducer
from embedagent_core.recovery_state import RecoveryStateReducer
from embedagent_core.runtime_config import RuntimeConfigReducer
from embedagent_core.session_operation_log import OperationLogReducer, operation_diagnostics
from embedagent_core.turn_experience import TurnExperienceReducer

from embedagent_host.runtime.session_history import SessionHistoryAssembler
from embedagent_host.runtime.session_projector import SessionSnapshotProjector
from embedagent_host.runtime.transcript_store import TranscriptStore


class SessionProjectionService(object):
    """Build Host read models from durable events and frozen Core projections."""

    def __init__(
        self,
        transcript_store: TranscriptStore,
        summary_loader: Callable[[Any], Optional[Dict[str, Any]]],
        runtime_snapshot_lookup: Optional[Callable[[], Dict[str, Any]]] = None,
        tool_catalog_lookup: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        extension_diagnostics_lookup: Optional[Callable[[], Any]] = None,
        snapshot_projector: Optional[SessionSnapshotProjector] = None,
    ) -> None:
        self._transcript_store = transcript_store
        self._summary_loader = summary_loader
        self._runtime_snapshot_lookup = runtime_snapshot_lookup
        self._tool_catalog_lookup = tool_catalog_lookup
        self._extension_diagnostics_lookup = extension_diagnostics_lookup
        self._snapshot_projector = snapshot_projector or SessionSnapshotProjector()

    def refresh(self, state: Any) -> bool:
        """Refresh reducer-backed read models from the trusted transcript prefix."""
        try:
            events = self._transcript_store.load_events(state.session_id)
        except (OSError, ValueError, TypeError):
            return False
        events = self._trusted_events(state, events)
        close_unfinished = bool(getattr(state, "restore_transcript_event_count", 0) or 0)
        state.operation_diagnostics = operation_diagnostics(
            OperationLogReducer(close_unfinished=close_unfinished).reduce(events)
        )
        state.runtime_config = RuntimeConfigReducer().reduce(events).to_dict()
        state.compaction_state = CompactionStateReducer().reduce(events).to_dict()
        state.recovery_state = RecoveryStateReducer().reduce(events).to_dict()
        state.turn_experience = TurnExperienceReducer().reduce(events).to_dict()
        return True

    def _trusted_events(self, state: Any, events: Any) -> Any:
        total = int(getattr(state, "restore_transcript_event_count", 0) or 0)
        consumed = int(getattr(state, "restore_consumed_event_count", 0) or 0)
        if total > 0 and consumed < total:
            return list(events or [])[: max(consumed, 0)]
        return events

    def build_snapshot(
        self,
        state: Any,
        pending_interaction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.refresh(state)
        runtime = self._runtime_snapshot_lookup() if callable(self._runtime_snapshot_lookup) else {}
        summary = self._summary_loader(state)
        diagnostics = (
            self._extension_diagnostics_lookup()
            if callable(self._extension_diagnostics_lookup)
            else []
        )
        return self._snapshot_projector.build_snapshot(
            state,
            summary,
            runtime,
            pending_interaction=pending_interaction,
            extension_diagnostics=diagnostics,
        )

    def build_history(self, state: Any) -> Dict[str, Any]:
        assembler = SessionHistoryAssembler(
            tool_catalog_lookup=self._tool_catalog_lookup,
            runtime_snapshot_lookup=self._runtime_snapshot_lookup,
        )
        history_source = "session_state"
        integrity_status = "healthy"
        if int(state.restore_transcript_event_count or 0) > 0:
            history_source = "transcript_restore"
            if str(state.restore_stop_reason or "").strip():
                integrity_status = "partial"
        return assembler.build(
            state.history,
            history_source=history_source,
            integrity_status=integrity_status,
            restore_stop_reason=str(state.restore_stop_reason or ""),
            consumed_event_count=int(state.restore_consumed_event_count or 0),
            transcript_event_count=int(state.restore_transcript_event_count or 0),
        )

    def unavailable_history(self, session_id: str, reason: str) -> Dict[str, Any]:
        return {
            "session_id": str(session_id or ""),
            "history_source": "transcript_restore",
            "turns": [],
            "activities": [],
            "current_interaction": None,
            "integrity": {
                "status": "unavailable",
                "restore_stop_reason": str(reason or "history_unavailable"),
                "consumed_event_count": 0,
                "transcript_event_count": 0,
            },
        }
