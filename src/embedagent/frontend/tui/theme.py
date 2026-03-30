from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TerminalTheme:
    vertical: str = "|"
    horizontal: str = "-"
    prompt_user: str = "user> "
    prompt_confirm: str = "confirm(y/n)> "


def default_theme() -> TerminalTheme:
    return TerminalTheme()
