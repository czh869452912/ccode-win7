from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from embedagent.capabilities import command_capability_descriptors


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
    SlashCommandSpec(
        "resources", "/resources [reload]", "查看或重载本地 skill/prompt/recipe 资源。"
    ),
    SlashCommandSpec("diff", "/diff", "查看当前工作区 Git diff。"),
    SlashCommandSpec("permissions", "/permissions", "查看当前会话权限上下文。"),
    SlashCommandSpec("tasks", "/tasks", "查看当前会话任务。"),
    SlashCommandSpec("artifacts", "/artifacts", "查看最近工件。"),
]

_COMMAND_LOOKUP = dict(
    (item.name, item) for item in _COMMAND_SPECS
)  # type: Dict[str, SlashCommandSpec]


class SlashCommandRegistry(object):
    def __init__(self) -> None:
        self._commands = list(_COMMAND_SPECS)

    def command_names(self, extra_specs: Optional[List[SlashCommandSpec]] = None) -> List[str]:
        return [item.name for item in self.specs(extra_specs=extra_specs)]

    def specs(self, extra_specs: Optional[List[SlashCommandSpec]] = None) -> List[SlashCommandSpec]:
        commands = list(self._commands)
        commands.extend(list(extra_specs or []))
        return commands

    def get(self, name: str) -> Optional[SlashCommandSpec]:
        return _COMMAND_LOOKUP.get(str(name or "").strip().lower())

    def capability_descriptors(self):
        return command_capability_descriptors(self)

    def help_markdown(self, extra_specs: Optional[List[SlashCommandSpec]] = None) -> str:
        lines = [
            "## Slash Commands",
            "",
        ]
        for item in self.specs(extra_specs=extra_specs):
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


def resource_command_specs(resources: Dict[str, Any]) -> List[SlashCommandSpec]:
    from embedagent.prompts import prompt_command_specs
    from embedagent.skill_index import build_skill_index

    specs = []  # type: List[SlashCommandSpec]
    specs.extend(build_skill_index(resources).command_specs())
    specs.extend(prompt_command_specs(resources))
    return specs
