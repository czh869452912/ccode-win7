from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState


def build_editor_status(state: TerminalState) -> str:
    buffer = state.editor.buffer
    if not buffer.path:
        return ""
    return "Editing %s dirty=%s" % (buffer.path, buffer.dirty)
