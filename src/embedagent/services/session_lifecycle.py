from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from embedagent.interaction import UserInputResponse
from embedagent.modes import DEFAULT_MODE, require_mode
from embedagent.plan_store import PlanStore
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Session
from embedagent.session_restore import SessionRestorer
from embedagent.session_runtime import ManagedSession
from embedagent.session_store import SessionSummaryStore
from embedagent.session_timeline import SessionTimelineStore
from embedagent.transcript_store import TranscriptStore

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class SessionLifecycleManager(object):
    """Session creation, restoration, and teardown logic."""

    def __init__(
        self,
        session_store: SessionSummaryStore,
        timeline_store: SessionTimelineStore,
        summary_store: SessionSummaryStore,
        plan_store: PlanStore,
        project_memory: ProjectMemoryStore,
        session_restorer: SessionRestorer,
        transcript_store: TranscriptStore,
    ) -> None:
        self.session_store = session_store
        self.timeline_store = timeline_store
        self.summary_store = summary_store
        self.plan_store = plan_store
        self.project_memory = project_memory
        self.session_restorer = session_restorer
        self.transcript_store = transcript_store

    def create_session_state(self, mode: str = DEFAULT_MODE) -> ManagedSession:
        current_mode = require_mode(mode)["slug"]
        session = Session()
        plan = self.plan_store.load(session.session_id)
        state = ManagedSession(
            session=session,
            current_mode=current_mode,
            active_plan_ref=plan.path if plan is not None else "",
            workflow_state="plan" if plan is not None else "chat",
        )
        return state

    def restore_session_state(
        self,
        reference: str,
        mode: str = "",
    ) -> ManagedSession:
        transcript_path = self.summary_store.resolve_transcript_path(reference)
        events = self.transcript_store.load_events(transcript_path)
        restored = self.session_restorer.restore(events)
        current_mode = require_mode(
            mode or restored.current_mode or DEFAULT_MODE
        )["slug"]
        session = restored.session
        summary_ref = ""
        try:
            summary_ref = self.summary_store.persist(session, current_mode)
        except (OSError, ValueError, TypeError):
            summary_ref = ""
        state = ManagedSession(
            session=session,
            current_mode=current_mode,
            summary_ref=summary_ref,
            updated_at=_utc_now(),
            resume_summary=None,
            last_assistant_message=self._last_assistant_from_session(session),
            restore_stop_reason=str(restored.stop_reason or ""),
            restore_consumed_event_count=int(restored.consumed_event_count or 0),
            restore_transcript_event_count=int(restored.transcript_event_count or 0),
        )
        if session.pending_interaction is not None:
            if session.pending_interaction.kind == "permission":
                state.status = "waiting_permission"
                permission_payload = dict(
                    session.pending_interaction.request_payload.get("permission") or {}
                )
                interaction_id = str(session.pending_interaction.interaction_id or "").strip()
                if interaction_id:
                    state.pending_permission = {
                        "permission_id": interaction_id,
                        "session_id": session.session_id,
                        "tool_name": session.pending_interaction.tool_name,
                        "category": str(permission_payload.get("category") or ""),
                        "reason": str(permission_payload.get("reason") or ""),
                        "details": dict(permission_payload.get("details") or {}),
                    }
                else:
                    state.status = "idle"
            elif session.pending_interaction.kind == "user_input":
                state.status = "waiting_user_input"
                request_payload = dict(
                    session.pending_interaction.request_payload.get("request") or {}
                )
                interaction_id = str(session.pending_interaction.interaction_id or "").strip()
                if interaction_id:
                    state.pending_user_input = {
                        "request_id": interaction_id,
                        "session_id": session.session_id,
                        "tool_name": session.pending_interaction.tool_name,
                        "question": str(request_payload.get("question") or ""),
                        "options": list(request_payload.get("options") or []),
                        "details": dict(request_payload.get("details") or {}),
                    }
                else:
                    state.status = "idle"
        plan = self.plan_store.load(session.session_id)
        if plan is not None:
            state.active_plan_ref = plan.path
            state.workflow_state = "plan"
        return state

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.summary_store.list_summaries(limit=limit)

    def persist_state(self, session: Session, current_mode: str, state: ManagedSession) -> str:
        try:
            summary_ref = self.summary_store.persist(session, current_mode)
        except (OSError, ValueError, TypeError):
            summary_ref = ""
        else:
            try:
                self.project_memory.refresh(session, current_mode, summary_ref)
            except (OSError, ValueError, TypeError):
                pass
        with state.lock:
            state.summary_ref = summary_ref or state.summary_ref
            state.updated_at = _utc_now()
        return summary_ref

    def _last_assistant_from_session(self, session: Session) -> str:
        for turn in reversed(session.turns):
            if turn.assistant_message:
                return str(turn.assistant_message)
        return ""

    def read_summary_for_state(self, state: ManagedSession) -> Optional[Dict[str, Any]]:
        if state.summary_ref or state.session.turns:
            try:
                summary = self.summary_store.load_summary(state.session.session_id)
            except ValueError:
                summary = None
            if summary is not None:
                return summary
        return state.resume_summary
