from __future__ import annotations

from dataclasses import dataclass
from typing import List

from embedagent.frontend.tui.shell_state import slash_name_strings


@dataclass
class ParsedCommand:
    name: str
    args: List[str]


def command_names(state) -> List[str]:
    return slash_name_strings(state)


def parse_command(text: str) -> ParsedCommand:
    parts = text.strip().split()
    if not parts:
        return ParsedCommand(name="", args=[])
    name = parts[0][1:] if parts[0].startswith("/") else parts[0]
    return ParsedCommand(name=name.lower(), args=parts[1:])
