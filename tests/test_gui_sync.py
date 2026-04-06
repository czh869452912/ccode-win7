"""Tests for GUI real-time sync callbacks: todos_refresh and artifacts_refresh."""
import os
import sys
import tempfile
import time
import shutil
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from embedagent.protocol import MessageType
from embedagent.permissions import PermissionPolicy
from embedagent.tools import ToolRuntime


class TestGuiSync(unittest.TestCase):
    def test_gui_backend_route_resolves_real_pending_input_waiter(self):
        import asyncio
        from embedagent.core.adapter import AgentCoreAdapter
        from embedagent.frontend.gui.backend.server import GUIBackend
        from tests.test_inprocess_adapter_frontend_api import AskUserClient

        workspace = tempfile.mkdtemp(prefix="gui-sync-")
        static_dir = tempfile.mkdtemp(prefix="gui-sync-static-")
        try:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            tools = ToolRuntime(workspace)
            core = AgentCoreAdapter(workspace=workspace)
            core.initialize(
                client=AskUserClient(),
                tools=tools,
                max_turns=8,
                permission_policy=PermissionPolicy(auto_approve_all=True, workspace=workspace),
            )
            backend = GUIBackend(core, static_dir=static_dir)
            backend.frontend._dispatch_message = lambda message: True

            snapshot = core.create_session("spec")
            session_id = snapshot.session_id

            core.submit_message(session_id, "请继续")
            deadline = time.time() + 3.0
            interaction_id = ""
            while time.time() < deadline:
                with backend.frontend._pending_lock:
                    pending_ids = list(backend.frontend._pending_inputs.keys())
                if pending_ids:
                    interaction_id = str(pending_ids[0] or "")
                    break
                time.sleep(0.02)

            self.assertTrue(interaction_id)
            route = None
            for item in backend.app.routes:
                if (
                    getattr(item, "path", "") == "/api/sessions/{session_id}/interactions/{interaction_id}/respond"
                    and "POST" in getattr(item, "methods", set())
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            asyncio.run(
                route.endpoint(
                    session_id,
                    interaction_id,
                    {
                        "response_kind": "answer",
                        "answer": "切到 debug 模式继续排查",
                        "selected_index": 1,
                        "selected_mode": "debug",
                        "selected_option_text": "切到 debug 模式继续排查",
                    },
                )
            )

            deadline = time.time() + 3.0
            current_snapshot = None
            while time.time() < deadline:
                current_snapshot = core.get_session_snapshot(session_id)
                if current_snapshot.pending_interaction is None and current_snapshot.current_mode == "debug":
                    break
                time.sleep(0.02)
            self.assertIsNotNone(current_snapshot)
            self.assertIsNone(current_snapshot.pending_interaction)
            self.assertEqual(current_snapshot.current_mode, "debug")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
            shutil.rmtree(static_dir, ignore_errors=True)

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

    def test_callback_bridge_session_status_preserves_pending_interaction_fields(self):
        from embedagent.core.adapter import CallbackBridge
        mock_frontend = MagicMock()
        bridge = CallbackBridge(mock_frontend)
        bridge.emit("session_status", "session-1", {
            "session_snapshot": {
                "session_id": "session-1",
                "status": "waiting_user_input",
                "current_mode": "spec",
                "started_at": "2026-04-06T00:00:00Z",
                "updated_at": "2026-04-06T00:00:01Z",
                "has_pending_input": True,
                "pending_user_input": {
                    "request_id": "ask-1",
                    "session_id": "session-1",
                    "tool_name": "ask_user",
                    "question": "下一步怎么做？",
                    "options": [{"index": 1, "text": "继续"}],
                },
                "pending_interaction": {
                    "interaction_id": "ask-1",
                    "session_id": "session-1",
                    "kind": "user_input",
                    "tool_name": "ask_user",
                    "question": "下一步怎么做？",
                    "options": [{"index": 1, "text": "继续"}],
                },
                "pending_interaction_valid": True,
                "restore_stop_reason": "",
                "timeline_replay_status": "healthy",
                "timeline_first_seq": 10,
                "timeline_last_seq": 12,
                "timeline_integrity": "healthy",
            }
        })
        snapshot = mock_frontend.on_session_status_change.call_args[0][0]
        self.assertTrue(snapshot.has_pending_input)
        self.assertEqual(snapshot.pending_input.request_id, "ask-1")
        self.assertEqual(snapshot.pending_interaction["interaction_id"], "ask-1")
        self.assertTrue(snapshot.pending_interaction_valid)
        self.assertEqual(snapshot.restore_stop_reason, "")

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
