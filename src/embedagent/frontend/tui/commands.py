from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ParsedCommand:
    name: str
    args: List[str]


_COMMANDS = [
    "help",
    "new",
    "resume",
    "sessions",
    "snapshot",
    "mode",
    "plan",
    "review",
    "diff",
    "permissions",
    "close",
    "workspace",
    "todos",
    "artifacts",
    "artifact",
    "open",
    "edit",
    "save",
    "explorer",
    "inspector",
    "follow",
    "quit",
]


def command_names() -> List[str]:
    return list(_COMMANDS)


def parse_command(text: str) -> ParsedCommand:
    parts = text.strip().split()
    if not parts:
        return ParsedCommand(name="", args=[])
    name = parts[0][1:] if parts[0].startswith("/") else parts[0]
    return ParsedCommand(name=name.lower(), args=parts[1:])
