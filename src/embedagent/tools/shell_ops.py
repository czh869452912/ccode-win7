from __future__ import annotations

from typing import Any, Dict, List

from embedagent.command_sanitizer import get_command_sanitizer
from embedagent.tools._base import (
    DEFAULT_COMMAND_TIMEOUT_SEC,
    ToolContext,
    ToolDefinition,
    ToolError,
)
from embedagent_core.session import Observation


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:
    def _bash(arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_COMMAND_TIMEOUT_SEC)
        sanitizer = get_command_sanitizer()
        blocked, reason = sanitizer.is_blocked(command_text)
        if blocked:
            raise ToolError(reason)
        return ctx.run_shell_tool("bash", command_text, cwd_argument, timeout_sec)

    return [
        ToolDefinition(
            name="bash",
            description=(
                "Execute a Bash command in the workspace. Use this for build commands, "
                "tests, scripts, and command-line exploration. Do not repeat the same "
                "failing command unchanged."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command text to execute. Example: git status --short",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Execution directory relative to the workspace. Example: .",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "Command timeout in seconds. Example: 30",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=_bash,
        ),
    ]
