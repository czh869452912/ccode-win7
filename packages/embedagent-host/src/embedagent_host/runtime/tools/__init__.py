"""Tool runtime package."""

from __future__ import annotations

__all__ = ["ToolRuntime", "ToolDefinition"]


def __getattr__(name: str):
    if name == "ToolRuntime":
        from embedagent_host.runtime.tools.runtime import ToolRuntime as _ToolRuntime

        return _ToolRuntime
    if name == "ToolDefinition":
        from embedagent_core.tool_contracts import ToolDefinition as _ToolDefinition

        return _ToolDefinition
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
