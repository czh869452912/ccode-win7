"""Tests for GUI real-time sync callbacks: todos_refresh and artifacts_refresh."""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from embedagent.protocol import MessageType


class TestGuiSync(unittest.TestCase):
    def test_websocket_frontend_has_on_todos_refresh(self):
        from embedagent.frontend.gui.backend.server import WebSocketFrontend
        self.assertTrue(hasattr(WebSocketFrontend, "on_todos_refresh"))

    def test_websocket_frontend_has_on_artifacts_refresh(self):
        from embedagent.frontend.gui.backend.server import WebSocketFrontend
        self.assertTrue(hasattr(WebSocketFrontend, "on_artifacts_refresh"))

    def test_on_todos_refresh_dispatches_correct_type(self):
        from embedagent.frontend.gui.backend.server import WebSocketFrontend
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda msg: dispatched.append(msg) or True
        frontend.on_todos_refresh()
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(dispatched[0]["type"], "todos_refresh")

    def test_on_artifacts_refresh_dispatches_correct_type(self):
        from embedagent.frontend.gui.backend.server import WebSocketFrontend
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda msg: dispatched.append(msg) or True
        frontend.on_artifacts_refresh()
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(dispatched[0]["type"], "artifacts_refresh")

    def test_callback_bridge_calls_todos_refresh_for_manage_todos(self):
        from embedagent.core.adapter import CallbackBridge
        mock_frontend = MagicMock()
        bridge = CallbackBridge(mock_frontend)
        bridge.emit("tool_finished", "session-1", {
            "tool_name": "manage_todos",
            "success": True,
            "data": {},
            "call_id": "call-1",
        })
        mock_frontend.on_todos_refresh.assert_called_once()

    def test_callback_bridge_calls_artifacts_refresh_for_write_file(self):
        from embedagent.core.adapter import CallbackBridge
        mock_frontend = MagicMock()
        bridge = CallbackBridge(mock_frontend)
        bridge.emit("tool_finished", "session-1", {
            "tool_name": "write_file",
            "success": True,
            "data": {},
            "call_id": "call-2",
        })
        mock_frontend.on_artifacts_refresh.assert_called_once()

    def test_callback_bridge_calls_artifacts_refresh_for_edit_file(self):
        from embedagent.core.adapter import CallbackBridge
        mock_frontend = MagicMock()
        bridge = CallbackBridge(mock_frontend)
        bridge.emit("tool_finished", "session-1", {
            "tool_name": "edit_file",
            "success": True,
            "data": {},
            "call_id": "call-3",
        })
        mock_frontend.on_artifacts_refresh.assert_called_once()

    def test_callback_bridge_context_compacted_preserves_metadata(self):
        from embedagent.core.adapter import CallbackBridge
        mock_frontend = MagicMock()
        bridge = CallbackBridge(mock_frontend)
        bridge.emit("context_compacted", "session-1", {
            "recent_turns": 2,
            "summarized_turns": 5,
            "approx_tokens_after": 1024,
            "turn_id": "turn-1",
            "step_id": "step-2",
            "step_index": 2,
        })
        mock_frontend.on_message.assert_called_once()
        message = mock_frontend.on_message.call_args[0][0]
        self.assertEqual(message.type, MessageType.CONTEXT_COMPACTED)
        self.assertEqual(message.metadata.get("recent_turns"), 2)
        self.assertEqual(message.metadata.get("summarized_turns"), 5)
        self.assertEqual(message.metadata.get("approx_tokens_after"), 1024)
        self.assertEqual(message.metadata.get("turn_id"), "turn-1")
        self.assertEqual(message.metadata.get("step_id"), "step-2")
        self.assertEqual(message.metadata.get("step_index"), 2)

    def test_callback_bridge_does_not_call_refresh_for_unrelated_tool(self):
        from embedagent.core.adapter import CallbackBridge
        mock_frontend = MagicMock()
        bridge = CallbackBridge(mock_frontend)
        bridge.emit("tool_finished", "session-1", {
            "tool_name": "read_file",
            "success": True,
            "data": {},
            "call_id": "call-4",
        })
        mock_frontend.on_todos_refresh.assert_not_called()
        mock_frontend.on_artifacts_refresh.assert_not_called()

if __name__ == "__main__":
    unittest.main()
