from __future__ import annotations

from embedagent_protocol import SessionEventEnvelope, SessionEventSink

from embedagent.frontend.gui.backend.server import WebSocketFrontend


def _event():
    return SessionEventEnvelope(
        schema_version=1,
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
