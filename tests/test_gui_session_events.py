import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_protocol import SessionEventEnvelope

from embedagent.core.adapter import AgentCoreAdapter
from embedagent.frontend.gui.backend.server import WebSocketFrontend


def _event(event_kind="tool.finished", sequence=3):
    return SessionEventEnvelope(
        schema_version=1,
        event_id="evt-1",
        session_id="sess-1",
        sequence=sequence,
        event_kind=event_kind,
        timestamp="2026-07-26T00:00:00Z",
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


class RecordingFrontend(object):
    def __init__(self):
        self.events = []

    def on_session_event(self, envelope):
        self.events.append(envelope)


class GuiSessionEventTests(unittest.TestCase):
    def test_core_adapter_forwards_the_same_protocol_envelope(self):
        frontend = RecordingFrontend()
        adapter = AgentCoreAdapter(workspace=".")
        adapter.register_frontend(frontend)
        envelope = _event()

        adapter._on_adapter_event(envelope)

        self.assertIs(frontend.events[0], envelope)
        self.assertEqual(frontend.events[0].to_dict(), envelope.to_dict())

    def test_websocket_frontend_dispatches_exact_protocol_envelope(self):
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda message: dispatched.append(message) or True
        envelope = _event()

        frontend.on_session_event(envelope)

        self.assertEqual(
            dispatched,
            [{"type": "session_event", "data": envelope.to_dict()}],
        )


if __name__ == "__main__":
    unittest.main()
