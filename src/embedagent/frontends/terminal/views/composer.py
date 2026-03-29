from __future__ import annotations

from embedagent.frontends.terminal.state import TerminalState


def build_prompt(state: TerminalState) -> str:
    if state.session.pending_permission is not None:
        return "confirm(y/n)> "
    return "user> "
