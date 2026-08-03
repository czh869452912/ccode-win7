from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState
from embedagent.frontend.tui.workbench import visible_palette_commands


def build_command_palette_text(state: TerminalState) -> str:
    palette = state.workbench.command_palette
    if not palette.open:
        return ""
    commands = visible_palette_commands(state.workbench, palette.query)
    lines = [
        " Command Palette",
        " query: %s" % (palette.query or ""),
        "",
    ]
    if not commands:
        lines.append(" No matching command")
        return "\n".join(lines)
    selected = max(0, min(palette.selected_index, len(commands) - 1))
    for index, command in enumerate(commands[:12]):
        marker = ">" if index == selected else " "
        slash = command.slash or command.id
        lines.append("%s %-24s %s" % (marker, command.label[:24], slash))
    return "\n".join(lines)
