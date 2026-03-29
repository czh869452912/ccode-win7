from __future__ import annotations

from embedagent.frontends.terminal.state import TerminalState


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_header_text(state: TerminalState) -> str:
    snapshot = state.session.current_snapshot
    git_info = state.workspace_snapshot.get("git") if isinstance(state.workspace_snapshot.get("git"), dict) else {}
    branch = str(git_info.get("branch") or "-")
    dirty = int(git_info.get("dirty_count") or 0)
    last_error = state.session.last_error or str(snapshot.get("last_error") or "")
    second_line = "host=%s  explorer=%s  inspector=%s  main=%s  branch=%s  dirty=%s" % (
        state.capability.host_mode,
        state.explorer.tab,
        state.inspector.tab,
        state.main_view,
        branch,
        dirty,
    )
    if state.session.pending_permission is not None:
        second_line += "  permission=waiting"
    if not state.timeline.follow_output:
        second_line += "  follow=off"
    if state.editor.buffer.dirty:
        second_line += "  editor=dirty"
    if last_error:
        second_line += "  error=%s" % _truncate_text(last_error, 64)
    return (
        "session=%s  mode=%s  status=%s  workspace=%s\n%s"
    ) % (
        str(snapshot.get("session_id") or "-")[:12],
        snapshot.get("current_mode") or state.initial_mode,
        snapshot.get("status") or "idle",
        state.workspace,
        second_line,
    )
