from __future__ import annotations

from typing import Any, Optional, Protocol

from embedagent_core.session import Action, ContextAssemblyResult, Observation, Session


class ContextAssemblerPort(Protocol):
    reducers: Any

    def build_messages(
        self,
        session: Session,
        mode_name: str,
        tools: Any = None,
        workflow_state: str = "",
        intelligence_broker: Any = None,
        force_compact: bool = False,
    ) -> ContextAssemblyResult:
        raise NotImplementedError


class SessionRestorePolicyPort(Protocol):
    def trusted_event_count(self, session_id: str) -> int:
        raise NotImplementedError


class StrictSessionRestorePolicy(object):
    def trusted_event_count(self, session_id: str) -> int:
        del session_id
        return 0


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
    persists_transcript: bool

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
        workflow_state: str = "",
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
    persists_transcript = False

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
