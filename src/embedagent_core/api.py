from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, Tuple, Union

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
from embedagent_core.session_log import SessionLogPort
from embedagent_core.tool_contracts import ToolRuntimePort


class AgentObserver(Protocol):
    def on_event(self, event_type: str, payload: Dict[str, Any]) -> None:
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
class AgentPorts:
    model: ModelClient
    tools: ToolRuntimePort
    session_log: SessionLogPort
    context: ContextAssemblerPort
    permissions: PermissionPolicy


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "pending_interaction", deepcopy(self.pending_interaction))
        object.__setattr__(self, "turn_snapshot", deepcopy(self.turn_snapshot))


class Agent(object):
    @classmethod
    def create(
        cls,
        ports: AgentPorts,
        definition: Optional[RuntimeDefinition] = None,
    ) -> "Agent":
        raise NotImplementedError

    def open(self, session_id: str = "") -> "AgentSession":
        raise NotImplementedError


class AgentSession(object):
    def submit(
        self,
        input_value: AgentInput,
        observer: Optional[AgentObserver] = None,
        cancel: Optional[CancelToken] = None,
    ) -> AgentResult:
        raise NotImplementedError
