from __future__ import annotations

from typing import Dict, Optional

from embedagent.frontend.tui.shell_state import close_palette, open_palette
from embedagent.frontend.tui.state import TerminalState


def set_snapshot(state: TerminalState, snapshot: Dict[str, object]) -> None:
    state.session.current_snapshot = dict(snapshot)
    state.session.current_session_id = str(snapshot.get("session_id") or "")
    state.session.current_mode = str(
        snapshot.get("current_mode") or state.session.current_mode or state.initial_mode
    )


def update_snapshot(state: TerminalState, **updates: object) -> None:
    merged = dict(state.session.current_snapshot)
    merged.update(updates)
    set_snapshot(state, merged)


def reset_session_buffers(state: TerminalState) -> None:
    state.timeline.items = []
    state.timeline.stream_text = ""
    state.timeline.follow_output = True
    state.session.pending_interaction = None
    state.session.last_context_event = {}
    state.session.last_failure = None
    state.overlay.active_id = ""
    for contribution in state.contributions.values():
        contribution.active = False
        contribution.data = {}


def close_stream(state: TerminalState) -> None:
    if not state.timeline.stream_text:
        return
    state.timeline.items.append(state.timeline.stream_text)
    state.timeline.stream_text = ""
    trim_timeline(state)


def append_line(state: TerminalState, line: str) -> None:
    close_stream(state)
    state.timeline.items.append(line)
    trim_timeline(state)


def append_delta(state: TerminalState, text: str) -> None:
    if not text:
        return
    if not state.timeline.stream_text:
        state.timeline.stream_text = "assistant> "
    state.timeline.stream_text += text


def trim_timeline(state: TerminalState) -> None:
    if len(state.timeline.items) > state.transcript_limit:
        state.timeline.items = state.timeline.items[-state.transcript_limit :]


def set_pending_interaction(state: TerminalState, ticket: Optional[Dict[str, object]]) -> None:
    state.session.pending_interaction = dict(ticket or {}) if ticket else None
    state.overlay.active_id = "session.interaction" if ticket else ""


def set_last_failure(state: TerminalState, failure: Optional[Dict[str, object]]) -> None:
    state.session.last_failure = dict(failure or {}) if failure else None


def set_context_event(state: TerminalState, payload: Dict[str, object]) -> None:
    state.session.last_context_event = dict(payload)


def set_follow_output(state: TerminalState, enabled: bool) -> None:
    state.timeline.follow_output = bool(enabled)


def activate_contribution(state: TerminalState, surface: str) -> None:
    for contribution in state.contributions.values():
        contribution.active = contribution.surface_id == surface
    state.overlay.active_id = surface if surface in state.contributions else ""


def show_command_palette(state: TerminalState) -> None:
    state.shell = open_palette(state.shell)
    state.overlay.active_id = "session.command_palette"


def hide_command_palette(state: TerminalState) -> None:
    state.shell = close_palette(state.shell)
    if state.overlay.active_id == "session.command_palette":
        state.overlay.active_id = ""
