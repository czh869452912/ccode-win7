from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from embedagent_core.session import Action, ContextAssemblyResult, Observation, Session


class ContextAssemblerPort(Protocol):
    reducers: Any

    def build_messages(
        self,
        session: Session,
        mode_name: str,
        tools: Any = None,
        workflow_state: str = "chat",
        intelligence_broker: Any = None,
        force_compact: bool = False,
    ) -> ContextAssemblyResult:
        raise NotImplementedError


class TranscriptStorePort(Protocol):
    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        schema_version: int = 2,
    ) -> None:
        raise NotImplementedError

    def transcript_exists(self, session_id: str) -> bool:
        raise NotImplementedError

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class SessionSummaryStorePort(Protocol):
    def persist(
        self,
        session: Session,
        current_mode: str,
        assembly: Optional[ContextAssemblyResult] = None,
    ) -> Any:
        raise NotImplementedError


class ProjectMemoryStorePort(Protocol):
    def refresh(self, session: Session, current_mode: str, summary_ref: Any = None) -> None:
        raise NotImplementedError


class MemoryMaintenancePort(Protocol):
    def run(self) -> None:
        raise NotImplementedError


class ToolCommitCoordinatorPort(Protocol):
    def commit(
        self,
        session: Session,
        action: Action,
        observation: Observation,
        current_mode: str,
        turn_id: str = "",
        step_id: str = "",
        message_id: str = "",
        parent_message_id: str = "",
        finished_at: str = "",
    ) -> Observation:
        raise NotImplementedError


class WorkspaceProfilePort(Protocol):
    def build_message(self, workspace: str, session_id: str) -> str:
        raise NotImplementedError


class NoopContextAssembler(object):
    reducers = {}

    def build_messages(
        self,
        session: Session,
        mode_name: str,
        tools: Any = None,
        workflow_state: str = "chat",
        intelligence_broker: Any = None,
        force_compact: bool = False,
    ) -> ContextAssemblyResult:
        del mode_name, tools, workflow_state, intelligence_broker, force_compact
        messages = [message.to_api_dict() for message in list(session.messages or [])]
        return ContextAssemblyResult(
            messages=messages,
            used_chars=sum(len(str(item.get("content") or "")) for item in messages),
            approx_tokens=0,
            compacted=False,
            summarized_turns=0,
            recent_turns=len(session.turns or []),
            policy=None,
            budget=None,
            stats=None,
        )


class InMemoryTranscriptStore(object):
    def __init__(self) -> None:
        self._events = {}  # type: Dict[str, List[Dict[str, Any]]]

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        schema_version: int = 2,
    ) -> None:
        if schema_version != 2:
            raise ValueError("transcript events must use schema_version 2")
        event = {
            "type": event_type,
            "payload": dict(payload or {}),
            "schema_version": 2,
        }
        self._events.setdefault(str(session_id or ""), []).append(event)

    def transcript_exists(self, session_id: str) -> bool:
        return bool(self._events.get(str(session_id or "")))

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        return [dict(item) for item in list(self._events.get(str(session_id or ""), []) or [])]


class NoopSessionSummaryStore(object):
    def persist(
        self,
        session: Session,
        current_mode: str,
        assembly: Optional[ContextAssemblyResult] = None,
    ) -> Any:
        del session, current_mode, assembly
        return None


class NoopProjectMemoryStore(object):
    def refresh(self, session: Session, current_mode: str, summary_ref: Any = None) -> None:
        del session, current_mode, summary_ref


class NoopMemoryMaintenance(object):
    def run(self) -> None:
        return None


class NoopToolCommitCoordinator(object):
    def commit(
        self,
        session: Session,
        action: Action,
        observation: Observation,
        current_mode: str,
        turn_id: str = "",
        step_id: str = "",
        message_id: str = "",
        parent_message_id: str = "",
        finished_at: str = "",
    ) -> Observation:
        del session, action, current_mode, turn_id, step_id, message_id, parent_message_id
        del finished_at
        return observation


class EmptyWorkspaceProfile(object):
    def build_message(self, workspace: str, session_id: str) -> str:
        del workspace, session_id
        return ""
