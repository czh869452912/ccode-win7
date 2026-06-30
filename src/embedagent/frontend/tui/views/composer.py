from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState


def build_prompt(state: TerminalState) -> str:
    pending = state.session.pending_interaction
    if pending is not None and pending.get("kind") == "permission":
        return "confirm(y/n)> "
    if pending is not None and pending.get("kind") == "user_input":
        return "answer> "
    return "user> "
