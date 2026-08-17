"""Generic EmbedAgent Core runtime package."""

from embedagent_core.api import (
    Agent,
    AgentInteractionRequest,
    AgentObserver,
    AgentPorts,
    AgentResult,
    AgentSession,
    AgentSessionView,
    ApplicationRuntimePolicy,
    CancelToken,
    InteractionReply,
    RuntimeDefinition,
    UserTurn,
)
from embedagent_core.application import ApplicationRegistrar
from embedagent_core.model import ModelClient, ModelClientError
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.ports import (
    ContextAssemblerPort,
    NoopContextAssembler,
    NoopSessionProjection,
    SessionProjectionPort,
    SessionRestorePolicyPort,
    StrictSessionRestorePolicy,
)
from embedagent_core.profile import AgentModeDescriptor, AgentProfile
from embedagent_core.session import Action, AssistantReply, Observation
from embedagent_core.session_log import InMemorySessionLog, SessionLeaseConflict, SessionLogPort
from embedagent_core.session_transaction import SessionRecoveryRequired
from embedagent_core.tool_contracts import PreparedToolObservation, ToolError, ToolRuntimePort

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Agent",
    "AgentInteractionRequest",
    "AgentModeDescriptor",
    "AgentObserver",
    "AgentPorts",
    "AgentProfile",
    "AgentResult",
    "AgentSession",
    "AgentSessionView",
    "ApplicationRuntimePolicy",
    "ApplicationRegistrar",
    "AssistantReply",
    "CancelToken",
    "ContextAssemblerPort",
    "InMemorySessionLog",
    "InteractionReply",
    "ModelClient",
    "ModelClientError",
    "NoopContextAssembler",
    "NoopSessionProjection",
    "Observation",
    "PermissionPolicy",
    "PreparedToolObservation",
    "RuntimeDefinition",
    "SessionLeaseConflict",
    "SessionLogPort",
    "SessionProjectionPort",
    "SessionRecoveryRequired",
    "SessionRestorePolicyPort",
    "StrictSessionRestorePolicy",
    "ToolError",
    "ToolRuntimePort",
    "UserTurn",
    "__version__",
]
