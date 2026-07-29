from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from embedagent_core.api import AgentSession
from embedagent_core.session import Session


@dataclass(frozen=True)
class HostedCommandRecord:
    user_text: str
    command_name: str
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0


@dataclass(frozen=True)
class HostedCommandTurn:
    arguments: Dict[str, Any]


@dataclass(frozen=True)
class HostedCommandResume:
    arguments: Dict[str, Any]


class HostedSessionController(object):
    """Supported non-root hosting operations for one AgentSession."""

    def __init__(self, agent_session: AgentSession) -> None:
        if not isinstance(agent_session, AgentSession):
            raise TypeError("agent_session must be AgentSession")
        self._runtime = agent_session._runtime
        self.session_id = agent_session.session_id

    def initialize(self, session: Session, mode: str, workflow_state: str) -> str:
        return self._runtime.transaction.initialize_host(
            self.session_id,
            session,
            mode,
            workflow_state,
        )

    def apply_mode(self, session: Session, mode: str, workflow_state: str) -> str:
        return self._runtime.transaction.apply_host_mode(
            self.session_id,
            session,
            mode,
            workflow_state,
        )

    def record_command_result(
        self,
        session: Session,
        record: HostedCommandRecord,
    ) -> None:
        self._runtime.transaction.record_host_command(
            self.session_id,
            session,
            user_text=record.user_text,
            command_name=record.command_name,
            success=record.success,
            message=record.message,
            data=dict(record.data),
            turn_id=record.turn_id,
            step_id=record.step_id,
            step_index=record.step_index,
        )

    def submit_command(self, request: HostedCommandTurn) -> Any:
        return self._runtime.transaction.submit_host_command(
            self.session_id, **dict(request.arguments)
        )

    def resume_command_interaction(self, request: HostedCommandResume) -> Any:
        return self._runtime.transaction.resume_host_command(
            self.session_id, **dict(request.arguments)
        )
