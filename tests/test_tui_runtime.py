from __future__ import annotations

import pytest
from embedagent_protocol import SessionEventEnvelope

from embedagent.frontend.tui.runtime import TerminalRuntime


def bootstrap_payload(session_id="s-1", event_cursor=0):
    return {
        "event_cursor": event_cursor,
        "thread": {"session_id": session_id},
        "snapshot": {
            "session_id": session_id,
            "current_mode": "explore",
            "status": "idle",
        },
        "history": {"session_id": session_id, "activities": []},
        "capabilities": {},
        "workflow": {},
        "integrity": {},
    }


def session_event(session_id, sequence, event_id):
    return SessionEventEnvelope(
        schema_version=1,
        event_id=event_id,
        session_id=session_id,
        sequence=sequence,
        event_kind="assistant.delta",
        timestamp="2026-08-03T00:00:00Z",
        payload={"text": event_id},
    )


class FakeHostedSessionHost(object):
    def __init__(self, bootstraps=None):
        self.bootstraps = list(bootstraps or [bootstrap_payload()])
        self.bootstrap_calls = []
        self.event_handler = None
        self.during_bootstrap = None

    def list_sessions(self, limit=10):
        return [{"session_id": "s-1"}][:limit]

    def create_session(self, mode, event_handler=None):
        self.event_handler = event_handler
        return {"session_id": "s-1", "current_mode": mode}

    def resume_session(self, reference, mode, event_handler=None):
        self.event_handler = event_handler
        return {"session_id": reference, "current_mode": mode}

    def get_session_bootstrap(self, session_id):
        self.bootstrap_calls.append(session_id)
        if self.during_bootstrap is not None:
            callback, self.during_bootstrap = self.during_bootstrap, None
            callback()
        if len(self.bootstraps) > 1:
            return self.bootstraps.pop(0)
        return self.bootstraps[0]

    def set_session_mode(self, session_id, mode):
        return {"session_id": session_id, "current_mode": mode}

    def submit_user_message(self, **kwargs):
        self.event_handler = kwargs["event_handler"]
        return None

    def respond_to_interaction(self, session_id, interaction_id, payload):
        return {"session_id": session_id, "interaction_id": interaction_id, "payload": payload}

    def cancel_session(self, session_id):
        return {"session_id": session_id, "status": "cancelled"}

    def load_session_summary(self, reference):
        return {"reference": reference}

    def list_tasks(self, session_id=""):
        return {"session_id": session_id, "tasks": []}

    def get_workspace_snapshot(self):
        return {"workspace": "D:/work"}

    def list_workspace_tree(self, path=".", max_depth=3, limit=200):
        return {"root": path, "items": [], "max_depth": max_depth, "limit": limit}

    def read_workspace_file(self, path):
        return {"path": path, "content": ""}

    def write_workspace_file(self, path, content):
        return {"path": path, "content": content}


def test_terminal_runtime_installs_bootstrap_cursor_and_applies_contiguous_event():
    host = FakeHostedSessionHost([bootstrap_payload(event_cursor=2)])
    actions = []
    runtime = TerminalRuntime(host, dispatch=actions.append)

    runtime.activate_session("s-1")
    runtime.on_session_event(session_event("s-1", 3, "evt-3"))

    assert runtime.selected_session_id == "s-1"
    assert runtime.event_cursor == 3
    assert [item["type"] for item in actions] == ["session_activated", "session_event"]
    assert actions[1]["event"]["event_id"] == "evt-3"


def test_terminal_runtime_buffers_live_event_while_bootstrap_is_loading():
    host = FakeHostedSessionHost([bootstrap_payload(event_cursor=2)])
    actions = []
    runtime = TerminalRuntime(host, dispatch=actions.append)
    host.during_bootstrap = lambda: runtime.on_session_event(session_event("s-1", 3, "buffered"))

    runtime.activate_session("s-1")

    assert runtime.event_cursor == 3
    assert [item["type"] for item in actions] == ["session_activated", "session_event"]
    assert actions[-1]["event"]["event_id"] == "buffered"


def test_terminal_runtime_accepts_only_canonical_envelopes_and_selected_session():
    actions = []
    runtime = TerminalRuntime(
        FakeHostedSessionHost([bootstrap_payload(event_cursor=2)]),
        dispatch=actions.append,
    )
    runtime.activate_session("s-1")

    with pytest.raises(TypeError):
        runtime.on_session_event("assistant_delta", "s-1", {"text": "legacy"})

    runtime.on_session_event(session_event("s-2", 3, "other-session"))
    runtime.on_session_event(session_event("s-1", 2, "duplicate"))
    assert [item["type"] for item in actions] == ["session_activated"]


def test_terminal_runtime_recovers_sequence_gap_from_current_bootstrap():
    host = FakeHostedSessionHost(
        [bootstrap_payload(event_cursor=2), bootstrap_payload(event_cursor=4)]
    )
    actions = []
    runtime = TerminalRuntime(host, dispatch=actions.append)
    runtime.activate_session("s-1")

    runtime.on_session_event(session_event("s-1", 4, "evt-4"))

    assert host.bootstrap_calls == ["s-1", "s-1"]
    assert runtime.event_cursor == 4
    assert [item["type"] for item in actions] == ["session_activated", "session_activated"]
    assert actions[-1]["reason"] == "recovery"


def test_terminal_runtime_rejects_operations_and_ignores_events_after_close():
    actions = []
    runtime = TerminalRuntime(FakeHostedSessionHost(), dispatch=actions.append)
    runtime.activate_session("s-1")
    runtime.close()

    with pytest.raises(RuntimeError, match="terminal_runtime_closed"):
        runtime.list_sessions()
    runtime.on_session_event(session_event("s-1", 1, "late"))
    assert [item["type"] for item in actions] == ["session_activated"]


def test_terminal_runtime_requires_complete_host_boundary():
    with pytest.raises(TypeError, match="host_method_missing:list_sessions"):
        TerminalRuntime(object(), dispatch=lambda action: None)
