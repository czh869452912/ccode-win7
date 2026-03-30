from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState


def build_prompt(state: TerminalState) -> str:
    if state.session.pending_permission is not None:
        return "confirm(y/n)> "
    if state.session.pending_user_input is not None:
        return "answer> "
    return "user> "
