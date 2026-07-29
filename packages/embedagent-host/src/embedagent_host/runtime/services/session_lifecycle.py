from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent_host.runtime.plan_store import PlanStore
from embedagent_host.runtime.session_runtime import ManagedSession, apply_hosted_projection
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
        transcript_store: TranscriptStore,
        session_opener: Callable[[str], Tuple[Any, Any]],
        mode_resolver: Callable[[str], Dict[str, Any]],
        default_mode: str,
        default_workflow_state: str = "",
    ) -> None:
        self.session_store = session_store
        self.summary_store = summary_store
        self.plan_store = plan_store
        self.transcript_store = transcript_store
        if not callable(session_opener):
            raise TypeError("session_opener must be callable")
        self.session_opener = session_opener
        if not callable(mode_resolver):
            raise TypeError("mode_resolver must be callable")
        requested_default = str(default_mode or "").strip()
        if not requested_default:
            raise ValueError("default_mode is required")
        self.mode_resolver = mode_resolver
        self.default_mode = self._require_mode_slug(requested_default)
        self.default_workflow_state = str(default_workflow_state or "")

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
        agent_session, hosted_session = self.session_opener("")
        plan = self.plan_store.load(agent_session.session_id)
        workflow_state = "plan" if plan is not None else self.default_workflow_state
        projection = hosted_session.initialize(current_mode, workflow_state)
        state = ManagedSession(
            session_id=agent_session.session_id,
            current_mode=current_mode,
            active_plan_ref=plan.path if plan is not None else "",
            workflow_state=workflow_state,
            agent_session=agent_session,
            hosted_session=hosted_session,
        )
        apply_hosted_projection(state, projection)
        return state

    def restore_session_state(
        self,
        reference: str,
        mode: str = "",
    ) -> ManagedSession:
        transcript_path = self.summary_store.resolve_transcript_path(reference)
        session_id = self.transcript_store.session_id_for_reference(transcript_path)
        agent_session, hosted_session = self.session_opener(session_id)
        projection = hosted_session.snapshot()
        current_mode = self._resolve_mode(mode or projection.current_mode)
        projection = hosted_session.initialize(current_mode, self.default_workflow_state)
        summary = None
        try:
            summary = self.summary_store.load_summary(session_id)
        except ValueError:
            summary = None
        state = ManagedSession(
            session_id=session_id,
            current_mode=current_mode,
            agent_session=agent_session,
            hosted_session=hosted_session,
            workflow_state=self.default_workflow_state,
            summary_ref=str((summary or {}).get("summary_ref") or ""),
            updated_at=_utc_now(),
            resume_summary=None,
        )
        apply_hosted_projection(state, projection)
        state.restore_stop_reason = str(projection.snapshot.get("restore_stop_reason") or "")
        state.restore_consumed_event_count = int(
            projection.snapshot.get("restore_consumed_event_count") or 0
        )
        state.restore_transcript_event_count = int(
            projection.snapshot.get("restore_transcript_event_count") or 0
        )
        state.status = projection.status
        state.last_assistant_message = self._last_assistant_from_history(state.history)
        plan = self.plan_store.load(session_id)
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

    def persist_state(self, state: ManagedSession) -> str:
        summary = None
        try:
            summary = self.summary_store.load_summary(state.session_id)
        except ValueError:
            summary = None
        summary_ref = str((summary or {}).get("summary_ref") or state.summary_ref or "")
        with state.lock:
            state.summary_ref = summary_ref
            state.updated_at = _utc_now()
        return summary_ref

    def _last_assistant_from_history(self, history: Dict[str, Any]) -> str:
        for turn in reversed(list(history.get("turns") or [])):
            if not isinstance(turn, dict):
                continue
            assistant = str(turn.get("assistant_message") or "")
            if assistant:
                return assistant
        return ""

    def read_summary_for_state(self, state: ManagedSession) -> Optional[Dict[str, Any]]:
        if state.summary_ref or list(state.history.get("turns") or []):
            try:
                summary = self.summary_store.load_summary(state.session_id)
            except ValueError:
                summary = None
            if summary is not None:
                return summary
        return state.resume_summary
