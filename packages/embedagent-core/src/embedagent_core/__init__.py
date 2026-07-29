"""Generic EmbedAgent Core runtime package."""

from embedagent_core.api import (
    Agent,
    AgentInteractionRequest,
    AgentObserver,
    AgentPorts,
    AgentResult,
    AgentSession,
    AgentSessionView,
    CancelToken,
    InteractionReply,
    RuntimeDefinition,
    UserTurn,
)
from embedagent_core.profile import AgentModeDescriptor, AgentProfile

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentInteractionRequest",
    "AgentModeDescriptor",
    "AgentObserver",
    "AgentPorts",
    "AgentProfile",
    "AgentResult",
    "AgentSession",
    "AgentSessionView",
    "CancelToken",
    "InteractionReply",
    "RuntimeDefinition",
    "UserTurn",
    "__version__",
]
