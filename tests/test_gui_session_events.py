from __future__ import annotations

from embedagent_host.frontend_errors import FrontendPortError
from embedagent_protocol import SessionEventEnvelope, SessionEventSink

from embedagent.frontend.gui.backend.server import WebSocketFrontend


def _event():
    return SessionEventEnvelope(
        schema_version=2,
        event_id="event-1",
        session_id="session-1",
        sequence=3,
        event_kind="tool.finished",
        timestamp="2026-08-13T00:00:00Z",
        payload={
            "tool_name": "edit_file",
            "success": False,
            "failure": {
                "code": "path_missing",
                "message": "path does not exist",
                "retryable": False,
                "source": "edit_file",
            },
        },
    )


def test_websocket_frontend_is_the_canonical_event_sink():
    frontend = WebSocketFrontend()
    dispatched = []
    frontend._dispatch_message = lambda message: dispatched.append(message) or True
    envelope = _event()

    assert isinstance(frontend, SessionEventSink)
    frontend.on_session_event(envelope)

    assert dispatched == [{"type": "session_event", "data": envelope.to_dict()}]


def test_websocket_frontend_rejects_publication_without_bound_loop():
    frontend = WebSocketFrontend()
    try:
        frontend.on_session_event(_event())
    except FrontendPortError as exc:
        assert exc.failure.code == "runtime_error"
        assert exc.failure.source == "gui_websocket"
    else:
        raise AssertionError("unbound websocket loop must be an explicit sink failure")


def test_websocket_frontend_emits_workspace_notification_on_app_channel():
    frontend = WebSocketFrontend()
    dispatched = []
    frontend._dispatch_message = lambda message: dispatched.append(message) or True
    from embedagent_protocol import WorkspaceChangedNotification

    frontend.connections.add(object())
    frontend.on_workspace_changed(
        WorkspaceChangedNotification(
            schema_version=2,
            workspace_id="workspace-1",
            path="C:/workspace",
            reason="activated",
        )
    )

    assert dispatched[0]["type"] == "workspace_changed"
    assert dispatched[0]["data"]["workspace_id"] == "workspace-1"
