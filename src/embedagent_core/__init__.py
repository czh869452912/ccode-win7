"""Generic EmbedAgent Core runtime package."""

from embedagent_core.api import (
    Agent,
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

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentObserver",
    "AgentPorts",
    "AgentResult",
    "AgentSession",
    "AgentSessionView",
    "CancelToken",
    "InteractionReply",
    "RuntimeDefinition",
    "UserTurn",
    "__version__",
]
