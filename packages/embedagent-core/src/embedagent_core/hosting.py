from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from embedagent_core.api import AgentInteractionRequest, AgentSession


@dataclass(frozen=True)
class HostedSessionProjection:
    session_id: str
    current_mode: str
    status: str
    pending_interaction: Optional[AgentInteractionRequest]
    snapshot: Dict[str, Any] = field(default_factory=dict)
    history: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HostedCommandResult:
    projection: HostedSessionProjection
    termination_reason: str
    termination_message: str
    next_mode: str
    turns_used: int
    observation: Optional[Dict[str, Any]] = None


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
class HostedResourcePrompt:
    content: str
    reason: str = ""
    revision: int = 0


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

    def initialize(self, mode: str, workflow_state: str) -> HostedSessionProjection:
        return self._runtime.transaction.initialize_host(
            self.session_id,
            mode,
            workflow_state,
        )

    def apply_mode(self, mode: str, workflow_state: str) -> HostedSessionProjection:
        return self._runtime.transaction.apply_host_mode(
            self.session_id,
            mode,
            workflow_state,
        )

    def record_command_result(
        self,
        record: HostedCommandRecord,
    ) -> HostedSessionProjection:
        return self._runtime.transaction.record_host_command(
            self.session_id,
            user_text=record.user_text,
            command_name=record.command_name,
            success=record.success,
            message=record.message,
            data=dict(record.data),
            turn_id=record.turn_id,
            step_id=record.step_id,
            step_index=record.step_index,
        )

    def submit_command(self, request: HostedCommandTurn) -> HostedCommandResult:
        return self._runtime.transaction.submit_host_command(
            self.session_id, **dict(request.arguments)
        )

    def resume_command_interaction(self, request: HostedCommandResume) -> HostedCommandResult:
        return self._runtime.transaction.resume_host_command(
            self.session_id, **dict(request.arguments)
        )

    def snapshot(self) -> HostedSessionProjection:
        return self._runtime.transaction.snapshot_host(self.session_id)

    def update_resource_prompt(self, prompt: HostedResourcePrompt) -> HostedSessionProjection:
        return self._runtime.transaction.update_host_resource_prompt(
            self.session_id,
            content=prompt.content,
            reason=prompt.reason,
            revision=prompt.revision,
        )
