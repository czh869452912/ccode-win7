from __future__ import annotations

from typing import List

from embedagent.tools._base import ToolContext
from embedagent_core.tool_contracts import ToolDefinition


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:
    """No-op module kept importable while C workflow command execution lives in bash/recipes."""

    return []
