from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_header_text(state: TerminalState) -> str:
    snapshot = state.session.current_snapshot
    last_error = state.session.last_error or str(snapshot.get("last_error") or "")
    second_line = "host=%s" % state.capability.host_mode
    pending = state.session.pending_interaction
    if pending is not None and pending.get("kind") == "permission":
        second_line += "  permission=waiting"
    if pending is not None and pending.get("kind") == "user_input":
        second_line += "  user_input=waiting"
    if not state.timeline.follow_output:
        second_line += "  follow=off"
    if state.shell.command_palette.open:
        second_line += "  palette=open"
    if state.overlay.active_id:
        second_line += "  overlay=%s" % state.overlay.active_id
    if last_error:
        second_line += "  error=%s" % _truncate_text(last_error, 64)
    return ("session=%s  mode=%s  status=%s  workspace=%s\n%s") % (
        str(snapshot.get("session_id") or "-")[:12],
        state.session.current_mode or state.initial_mode,
        snapshot.get("status") or "idle",
        state.workspace,
        second_line,
    )
