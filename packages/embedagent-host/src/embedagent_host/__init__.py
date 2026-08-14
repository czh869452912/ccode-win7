"""Hosted EmbedAgent product composition package."""

from embedagent_host.frontend_errors import FrontendPortError as FrontendPortError
from embedagent_host.frontend_errors import SessionNotFoundError as SessionNotFoundError
from embedagent_host.frontend_ports import (
    InProcessFrontendSessionPort as InProcessFrontendSessionPort,
)
from embedagent_host.frontend_ports import (
    InProcessFrontendWorkspacePort as InProcessFrontendWorkspacePort,
)

__version__ = "0.1.0"
