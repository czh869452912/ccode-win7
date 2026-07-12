from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, Tuple, Union

from embedagent_core.extensions import ExtensionManager
from embedagent_core.model import ModelClient
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.policies import (
    DenyWritePathPolicy,
    EmptyModeToolPolicy,
    ModeRuntimePolicy,
    ModeToolPolicy,
    NeutralModeRuntimePolicy,
    WritePathPolicy,
)
from embedagent_core.ports import ContextAssemblerPort
from embedagent_core.session import PendingInteraction
from embedagent_core.session_log import SessionLogPort, normalize_session_id
from embedagent_core.tool_contracts import ToolRuntimePort


class AgentObserver(Protocol):
    def on_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError


class AgentInteractionObserver(AgentObserver, Protocol):
    def on_permission_request(self, request: Any) -> Optional[bool]:
        raise NotImplementedError

    def on_user_input_request(self, request: Any) -> Any:
        raise NotImplementedError


class CancelToken(Protocol):
    def is_set(self) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class UserTurn:
    text: str
    mode: str = ""
    stream: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("user turn text must be a string")
        if not self.text.strip():
            raise ValueError("user turn text is required")


@dataclass(frozen=True)
class InteractionReply:
    interaction_id: str
    value: Dict[str, Any]
    stream: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.interaction_id, str):
            raise TypeError("interaction id must be a string")
        if not self.interaction_id.strip():
            raise ValueError("interaction id is required")
        if self.value is not None and not isinstance(self.value, dict):
            raise TypeError("interaction reply value must be a dict or None")
        object.__setattr__(self, "value", deepcopy(self.value or {}))


AgentInput = Union[UserTurn, InteractionReply]


@dataclass(frozen=True)
class AgentRuntimeServices:
    max_turns: Optional[int] = None
    summary_store: Any = None
    project_memory_store: Any = None
    memory_maintenance: Any = None
    maintenance_interval: int = 4
    intelligence_broker: Any = None
    tool_commit: Any = None
    workspace_profile: Any = None
    remembered_permission_categories_provider: Optional[Callable[[Any], list]] = None
    workflow_state_provider: Optional[Callable[[str], str]] = None
    best_effort_history_count_provider: Optional[Callable[[str], int]] = None


@dataclass(frozen=True)
class AgentPorts:
    model: ModelClient
    tools: ToolRuntimePort
    session_log: SessionLogPort
    context: ContextAssemblerPort
    permissions: PermissionPolicy
    runtime_services: Optional[AgentRuntimeServices] = None
    extension_manager: Optional[ExtensionManager] = None


@dataclass(frozen=True)
class RuntimeDefinition:
    agent_id: str = "embedagent.base"
    default_mode: str = ""
    workflow_state: str = ""
    extensions: Tuple[Any, ...] = field(default_factory=tuple)
    mode_tool_policy: ModeToolPolicy = field(default_factory=EmptyModeToolPolicy)
    write_path_policy: WritePathPolicy = field(default_factory=DenyWritePathPolicy)
    mode_runtime_policy: ModeRuntimePolicy = field(default_factory=NeutralModeRuntimePolicy)


@dataclass(frozen=True)
class AgentSessionView:
    session_id: str
    current_mode: str
    workflow_state: Dict[str, Any]
    message_count: int
    turn_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "workflow_state", deepcopy(self.workflow_state))


@dataclass(frozen=True)
class AgentResult:
    final_text: str
    session: AgentSessionView
    termination_reason: str
    pending_interaction: Optional[PendingInteraction]
    turn_snapshot: Optional[Any]
    outcome: Dict[str, Any] = field(default_factory=dict)
    turns_used: int = 0
    termination_message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "session", deepcopy(self.session))
        object.__setattr__(self, "pending_interaction", deepcopy(self.pending_interaction))
        object.__setattr__(self, "turn_snapshot", deepcopy(self.turn_snapshot))
        object.__setattr__(self, "outcome", deepcopy(self.outcome))


class Agent(object):
    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime

    @classmethod
    def create(
        cls,
        ports: AgentPorts,
        definition: Optional[RuntimeDefinition] = None,
    ) -> "Agent":
        from embedagent_core.runner import AgentRuntime

        if not isinstance(ports, AgentPorts):
            raise TypeError("ports must be AgentPorts")
        if definition is not None and not isinstance(definition, RuntimeDefinition):
            raise TypeError("definition must be RuntimeDefinition")
        for port_name in ("model", "tools", "session_log", "context", "permissions"):
            if getattr(ports, port_name) is None:
                raise ValueError("agent port %s is required" % port_name)
        if ports.runtime_services is not None and not isinstance(
            ports.runtime_services,
            AgentRuntimeServices,
        ):
            raise TypeError("runtime services must be AgentRuntimeServices")
        runtime_definition = definition if definition is not None else RuntimeDefinition()
        if ports.extension_manager is not None and not isinstance(
            ports.extension_manager,
            ExtensionManager,
        ):
            raise TypeError("extension manager must be ExtensionManager")
        return cls(AgentRuntime(ports, runtime_definition))

    def open(self, session_id: str = "") -> "AgentSession":
        if not isinstance(session_id, str):
            raise TypeError("session id must be a string")
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            normalized_session_id = "s-" + uuid.uuid4().hex
        return AgentSession(self._runtime, normalized_session_id)


class AgentSession(object):
    def __init__(self, runtime: Any, session_id: str) -> None:
        self._runtime = runtime
        self._session_id = normalize_session_id(session_id)
        self._submit_lock = threading.Lock()

    @property
    def session_id(self) -> str:
        return self._session_id

    def submit(
        self,
        input_value: AgentInput,
        observer: Optional[AgentObserver] = None,
        cancel: Optional[CancelToken] = None,
    ) -> AgentResult:
        from embedagent_core.runner import AgentRequest, run_agent
        from embedagent_core.session_log import SessionLeaseConflict

        if not self._submit_lock.acquire(blocking=False):
            raise SessionLeaseConflict("agent session already has an active submit")
        try:
            return run_agent(
                self._runtime,
                AgentRequest(self.session_id, input_value),
                observer=observer,
                cancel=cancel,
            )
        finally:
            self._submit_lock.release()

    def _host_initialize_session(
        self,
        session: Any,
        current_mode: str,
        workflow_state: str,
    ) -> str:
        return self._runtime.host_initialize_session(
            self.session_id,
            session,
            current_mode,
            workflow_state,
        )

    def _host_apply_mode(self, session: Any, mode: str, workflow_state: str) -> str:
        return self._runtime.host_apply_mode(
            self.session_id,
            session,
            mode,
            workflow_state,
        )

    def _host_record_command_result(self, session: Any, **kwargs: Any) -> None:
        self._runtime.host_record_command_result(self.session_id, session, **kwargs)

    def _host_record_pending_permission(
        self,
        session: Any,
        action: Any,
        permission_payload: Dict[str, Any],
        current_mode: str,
        interaction_id: str = "",
    ) -> None:
        self._runtime.host_record_pending_permission(
            self.session_id,
            session,
            action,
            permission_payload,
            current_mode,
            interaction_id=interaction_id,
        )

    def _host_submit_command_turn(self, **kwargs: Any) -> Any:
        return self._runtime.host_submit_command_turn(self.session_id, **kwargs)

    def _host_resume_command_interaction(self, **kwargs: Any) -> Any:
        return self._runtime.host_resume_command_interaction(self.session_id, **kwargs)
