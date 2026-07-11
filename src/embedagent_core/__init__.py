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
from embedagent_core.runner import AgentRequest, AgentRuntime, run_agent

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentObserver",
    "AgentPorts",
    "AgentRequest",
    "AgentResult",
    "AgentRuntime",
    "AgentSession",
    "AgentSessionView",
    "CancelToken",
    "InteractionReply",
    "RuntimeDefinition",
    "UserTurn",
    "__version__",
    "run_agent",
]
