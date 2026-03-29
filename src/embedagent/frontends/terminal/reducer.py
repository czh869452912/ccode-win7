from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from embedagent.frontends.terminal.models import ArtifactRow, EditorBuffer, ExplorerItem
from embedagent.frontends.terminal.state import TerminalState


def set_snapshot(state: TerminalState, snapshot: Dict[str, object]) -> None:
    state.session.current_snapshot = dict(snapshot)
    state.session.current_session_id = str(snapshot.get("session_id") or "")


def update_snapshot(state: TerminalState, **updates: object) -> None:
    merged = dict(state.session.current_snapshot)
    merged.update(updates)
    state.session.current_snapshot = merged
    state.session.current_session_id = str(merged.get("session_id") or state.session.current_session_id or "")


def reset_session_buffers(state: TerminalState) -> None:
    state.timeline.lines = []
    state.timeline.stream_text = ""
    state.timeline.follow_output = True
    state.session.pending_permission = None
    state.session.pending_user_input = None
    state.session.last_context_event = {}
    state.session.last_error = ""
    state.preview_path = ""
    state.preview_text = ""
    state.editor = state.editor.__class__()
    state.main_view = "timeline"
    state.inspector.tab = "status"


def close_stream(state: TerminalState) -> None:
    if not state.timeline.stream_text:
        return
    state.timeline.lines.append(state.timeline.stream_text)
    state.timeline.stream_text = ""
    trim_timeline(state)


def append_line(state: TerminalState, line: str) -> None:
    close_stream(state)
    state.timeline.lines.append(line)
    trim_timeline(state)


def append_delta(state: TerminalState, text: str) -> None:
    if not text:
        return
    if not state.timeline.stream_text:
        state.timeline.stream_text = "assistant> "
    state.timeline.stream_text += text


def trim_timeline(state: TerminalState) -> None:
    if len(state.timeline.lines) > state.transcript_limit:
        state.timeline.lines = state.timeline.lines[-state.transcript_limit :]


def set_explorer_items(state: TerminalState, tab: str, items: Iterable[ExplorerItem], root: str = ".") -> None:
    state.explorer.tab = tab
    state.explorer.items = list(items)
    state.explorer.root = root
    if not state.explorer.items:
        state.explorer.selection = 0
        return
    state.explorer.selection = max(0, min(state.explorer.selection, len(state.explorer.items) - 1))


def move_explorer_selection(state: TerminalState, step: int) -> None:
    if not state.explorer.items:
        state.explorer.selection = 0
        return
    limit = len(state.explorer.items) - 1
    state.explorer.selection = max(0, min(limit, state.explorer.selection + step))


def current_explorer_item(state: TerminalState) -> Optional[ExplorerItem]:
    if not state.explorer.items:
        return None
    index = max(0, min(state.explorer.selection, len(state.explorer.items) - 1))
    return state.explorer.items[index]


def set_workspace_snapshot(state: TerminalState, snapshot: Dict[str, object]) -> None:
    state.workspace_snapshot = dict(snapshot)


def set_preview(state: TerminalState, path: str, text: str) -> None:
    state.preview_path = path
    state.preview_text = text
    state.main_view = "preview"


def set_main_view(state: TerminalState, name: str) -> None:
    state.main_view = name


def set_inspector_tab(state: TerminalState, tab: str) -> None:
    state.inspector.tab = tab


def set_artifact_items(state: TerminalState, items: Iterable[ArtifactRow]) -> None:
    state.inspector.artifact_items = list(items)


def set_selected_artifact(state: TerminalState, reference: str) -> None:
    state.inspector.selected_artifact_ref = reference


def set_pending_permission(state: TerminalState, ticket: Optional[Dict[str, object]]) -> None:
    state.session.pending_permission = ticket


def set_pending_user_input(state: TerminalState, ticket: Optional[Dict[str, object]]) -> None:
    state.session.pending_user_input = ticket


def set_last_error(state: TerminalState, message: str) -> None:
    state.session.last_error = message


def set_context_event(state: TerminalState, payload: Dict[str, object]) -> None:
    state.session.last_context_event = dict(payload)


def set_editor_buffer(state: TerminalState, buffer: EditorBuffer, diff_preview: str = "", warning: str = "") -> None:
    state.editor.buffer = buffer
    state.editor.diff_preview = diff_preview
    state.editor.warning = warning
    state.main_view = "editor"


def update_editor_content(state: TerminalState, content: str) -> None:
    buffer = state.editor.buffer
    buffer.content = content
    buffer.dirty = buffer.content != buffer.original_content


def set_follow_output(state: TerminalState, enabled: bool) -> None:
    state.timeline.follow_output = bool(enabled)
