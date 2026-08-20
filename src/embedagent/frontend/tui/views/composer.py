from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState


def build_prompt(state: TerminalState) -> str:
    pending = state.session.pending_interaction
    if pending is not None and pending.get("kind") == "permission":
        choices = pending.get("choices") if isinstance(pending.get("choices"), list) else []
        labels = "/".join(str(item.get("key") or "") for item in choices if isinstance(item, dict))
        return "permission[%s]> " % labels if labels else "permission> "
    if pending is not None and pending.get("kind") == "user_input":
        return "%s> " % str(pending.get("prompt") or "answer")
    return "user> "
