from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from embedagent_core.session import Session
from embedagent_core.session_restore import SessionRestorer

from embedagent_host.runtime.plan_store import PlanStore
from embedagent_host.runtime.project_memory import ProjectMemoryStore
from embedagent_host.runtime.session_runtime import ManagedSession
from embedagent_host.runtime.session_store import SessionSummaryStore
from embedagent_host.runtime.transcript_store import TranscriptStore

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SessionLifecycleManager(object):
    """Session creation, restoration, and teardown logic."""

    def __init__(
        self,
        session_store: SessionSummaryStore,
        summary_store: SessionSummaryStore,
        plan_store: PlanStore,
        project_memory: ProjectMemoryStore,
        session_restorer: SessionRestorer,
        transcript_store: TranscriptStore,
        mode_resolver: Callable[[str], Dict[str, Any]],
        default_mode: str,
    ) -> None:
        self.session_store = session_store
        self.summary_store = summary_store
        self.plan_store = plan_store
        self.project_memory = project_memory
        self.session_restorer = session_restorer
        self.transcript_store = transcript_store
        if not callable(mode_resolver):
            raise TypeError("mode_resolver must be callable")
        requested_default = str(default_mode or "").strip()
        if not requested_default:
            raise ValueError("default_mode is required")
        self.mode_resolver = mode_resolver
        self.default_mode = self._require_mode_slug(requested_default)

    def _require_mode_slug(self, requested: str) -> str:
        definition = self.mode_resolver(requested)
        if not isinstance(definition, dict):
            raise ValueError("Mode resolver returned an invalid definition for %r" % requested)
        slug = str(definition.get("slug") or "").strip()
        if not slug:
            raise ValueError("Mode resolver returned no slug for %r" % requested)
        return slug

    def _resolve_mode(self, mode: str) -> str:
        requested = str(mode or self.default_mode).strip()
        return self._require_mode_slug(requested)

    def create_session_state(self, mode: str = "") -> ManagedSession:
        current_mode = self._resolve_mode(mode)
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
        events = self.transcript_store.load_events_from_reference(transcript_path)
        restored = self.session_restorer.restore(events)
        current_mode = self._resolve_mode(mode or restored.current_mode)
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
                interaction_id = str(session.pending_interaction.interaction_id or "").strip()
                if interaction_id:
                    state.status = "waiting_permission"
                else:
                    state.status = "idle"
            elif session.pending_interaction.kind == "user_input":
                interaction_id = str(session.pending_interaction.interaction_id or "").strip()
                if interaction_id:
                    state.status = "waiting_user_input"
                else:
                    state.status = "idle"
        plan = self.plan_store.load(session.session_id)
        if plan is not None:
            state.active_plan_ref = plan.path
            state.workflow_state = "plan"
        return state

    def list_sessions(
        self,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        return self.summary_store.list_summaries(
            limit=limit,
            include_archived=include_archived,
        )

    def rename_session(self, session_id: str, title: str) -> Dict[str, Any]:
        return self.summary_store.rename_session(session_id, title)

    def archive_session(self, session_id: str) -> Dict[str, Any]:
        return self.summary_store.archive_session(session_id)

    def fork_session(self, session_id: str, title: str = "") -> Dict[str, Any]:
        return self.summary_store.fork_session(session_id, title=title)

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
