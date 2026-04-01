from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ParsedSlashCommand:
    name: str
    raw_args: str
    args: List[str]


@dataclass
class SlashCommandSpec:
    name: str
    usage: str
    summary: str


_COMMAND_SPECS = [
    SlashCommandSpec("help", "/help", "显示内建命令帮助。"),
    SlashCommandSpec("mode", "/mode <name> [message]", "切换核心模式；若带正文则继续提交该消息。"),
    SlashCommandSpec("sessions", "/sessions", "查看最近可恢复会话。"),
    SlashCommandSpec("resume", "/resume [reference] [mode]", "恢复一个历史会话并切换到它。"),
    SlashCommandSpec("workspace", "/workspace", "查看当前工作区与 Git 摘要。"),
    SlashCommandSpec("run", "/run <recipe_id>", "直接执行一个工作区 recipe。"),
    SlashCommandSpec("clear", "/clear", "清空当前前端时间线视图，不删除会话存档。"),
    SlashCommandSpec("plan", "/plan [content]", "查看或更新当前会话计划。"),
    SlashCommandSpec("review", "/review", "基于最近证据生成只读审查结论。"),
    SlashCommandSpec("recipes", "/recipes", "查看当前工作区可用的 build/test recipe。"),
    SlashCommandSpec("diff", "/diff", "查看当前工作区 Git diff。"),
    SlashCommandSpec("permissions", "/permissions", "查看当前会话权限上下文。"),
    SlashCommandSpec("todos", "/todos", "查看当前会话待办。"),
    SlashCommandSpec("artifacts", "/artifacts", "查看最近工件。"),
]

_COMMAND_LOOKUP = dict((item.name, item) for item in _COMMAND_SPECS)  # type: Dict[str, SlashCommandSpec]


class SlashCommandRegistry(object):
    def __init__(self) -> None:
        self._commands = list(_COMMAND_SPECS)

    def command_names(self) -> List[str]:
        return [item.name for item in self._commands]

    def specs(self) -> List[SlashCommandSpec]:
        return list(self._commands)

    def get(self, name: str) -> Optional[SlashCommandSpec]:
        return _COMMAND_LOOKUP.get(str(name or "").strip().lower())

    def help_markdown(self) -> str:
        lines = [
            "## Slash Commands",
            "",
        ]
        for item in self._commands:
            lines.append("- `%s` - %s" % (item.usage, item.summary))
        return "\n".join(lines)


def parse_slash_command(text: str) -> Optional[ParsedSlashCommand]:
    raw = str(text or "").strip()
    if not raw.startswith("/"):
        return None
    parts = raw[1:].split(None, 1)
    name = str(parts[0] or "").strip().lower() if parts else ""
    if not name:
        return None
    raw_args = str(parts[1] or "").strip() if len(parts) > 1 else ""
    args = raw_args.split() if raw_args else []
    return ParsedSlashCommand(name=name, raw_args=raw_args, args=args)


def slash_command_names() -> List[str]:
    return SlashCommandRegistry().command_names()
