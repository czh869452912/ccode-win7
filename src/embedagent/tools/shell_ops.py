from __future__ import annotations

from typing import Any, Dict, List

from embedagent.command_sanitizer import get_default_sanitizer
from embedagent.session import Observation
from embedagent.tools._base import (
    DEFAULT_COMMAND_TIMEOUT_SEC,
    ToolContext,
    ToolDefinition,
    ToolError,
)


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:

    def _run_command(arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_COMMAND_TIMEOUT_SEC)
        sanitizer = get_default_sanitizer()
        blocked, reason = sanitizer.is_blocked(command_text)
        if blocked:
            raise ToolError(reason)
        return ctx.run_shell_tool("run_command", command_text, cwd_argument, timeout_sec)

    return [
        ToolDefinition(
            name="run_command",
            description="执行工作区内的 shell 命令。用于构建、运行脚本或采集终端结果。命令在项目工作区或其子目录中执行。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令文本，按系统 shell 语法书写。示例：git status --short",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "命令执行目录，相对于项目根目录。示例：.",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "命令超时时间，单位为秒。示例：30",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=_run_command,
        ),
    ]
