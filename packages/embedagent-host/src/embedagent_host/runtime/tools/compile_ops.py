from __future__ import annotations

from typing import List

from embedagent_core.tool_contracts import ToolDefinition

from embedagent_host.runtime.tools._base import ToolContext


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:
    """No-op module kept importable while C workflow command execution lives in bash/recipes."""

    return []
