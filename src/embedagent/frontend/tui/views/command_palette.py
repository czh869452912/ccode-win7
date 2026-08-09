from __future__ import annotations

from embedagent.frontend.tui.shell_state import visible_palette_commands
from embedagent.frontend.tui.state import TerminalState


def build_command_palette_text(state: TerminalState) -> str:
    palette = state.shell.command_palette
    if not palette.open:
        return ""
    commands = visible_palette_commands(state.shell, palette.query)
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
