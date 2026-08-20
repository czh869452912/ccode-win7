"""
Tests for new architecture - Protocol, Core, Frontend separation
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


from embedagent_protocol import (
    CommandResult,
    Message,
    MessageType,
    PlanSnapshot,
    SessionEventEnvelope,
    SessionEventSink,
    SessionSnapshot,
    SessionStatus,
    ToolCall,
    ToolResult,
    TurnRecord,
    WorkspaceInfo,
)


class MockEventSink(SessionEventSink):
    def __init__(self):
        self.events = []

    def on_session_event(self, envelope: SessionEventEnvelope) -> None:
        self.events.append(envelope)


class TestSessionEventSink(unittest.TestCase):
    def test_frontend_protocol_exposes_one_session_event_sink_method(self):
        self.assertIn("on_session_event", SessionEventSink.__dict__)
        for legacy_name in (
            "on_message",
            "on_tool_start",
            "on_tool_finish",
            "on_session_status_change",
            "on_command_result",
        ):
            self.assertNotIn(legacy_name, SessionEventSink.__dict__)

    def test_frontend_receives_protocol_envelope(self):
        frontend = MockEventSink()
        envelope = SessionEventEnvelope(
            2,
            "evt-1",
            "session-1",
            1,
            "turn.started",
            "2026-07-26T00:00:00Z",
            {"turn_id": "turn-1"},
        )

        frontend.on_session_event(envelope)

        self.assertEqual(frontend.events, [envelope])


class TestProtocol(unittest.TestCase):
    """Test protocol layer"""

    def test_message_creation(self):
        msg = Message(id="msg_001", type=MessageType.USER, content="Hello")
        self.assertEqual(msg.id, "msg_001")
        self.assertEqual(msg.type, MessageType.USER)
        self.assertEqual(msg.content, "Hello")

    def test_session_snapshot(self):
        snap = SessionSnapshot(
            session_id="sess_001",
            status=SessionStatus.IDLE,
            current_mode="build",
            created_at="2026-03-30T10:00:00",
            updated_at="2026-03-30T10:00:00",
        )
        self.assertEqual(snap.session_id, "sess_001")
        self.assertEqual(snap.status, SessionStatus.IDLE)

    def test_tool_call(self):
        call = ToolCall(tool_name="read_file", arguments={"path": "test.py"}, call_id="call_001")
        self.assertEqual(call.tool_name, "read_file")

    def test_tool_result(self):
        result = ToolResult(tool_name="read_file", success=True, data={"content": "hello"})
        self.assertTrue(result.success)
        self.assertEqual(result.data["content"], "hello")

    def test_workspace_info(self):
        info = WorkspaceInfo(path="/workspace", git_branch="main", git_dirty=2)
        self.assertEqual(info.git_branch, "main")

    def test_command_result(self):
        result = CommandResult(
            command_name="help",
            success=True,
            message="ok",
            data={"items": 1},
            turn_id="turn_1",
            step_id="",
            step_index=0,
        )
        self.assertEqual(result.command_name, "help")
        self.assertTrue(result.success)
        self.assertEqual(result.turn_id, "turn_1")

    def test_plan_snapshot(self):
        plan = PlanSnapshot(
            session_id="sess_001",
            title="Current Plan",
            content="## Summary",
            updated_at="2026-03-30T10:00:00",
        )
        self.assertEqual(plan.workflow_state, "plan")

    def test_turn_record(self):
        turn = TurnRecord(turn_id="turn_1", user_text="hi")
        self.assertEqual(turn.turn_id, "turn_1")


class TestFrontendTUIImport(unittest.TestCase):
    """Test TUI frontend imports"""

    def test_import_tui_app(self):
        try:
            from embedagent.frontend.tui import TerminalApp

            self.assertIsNotNone(TerminalApp)
        except ImportError:
            self.skipTest("prompt_toolkit not installed")

    def test_import_tui_frontend(self):
        from embedagent.frontend.tui import TUIFrontend

        self.assertIsNotNone(TUIFrontend)

    def test_import_launcher(self):
        try:
            from embedagent.frontend.tui import launch_tui

            self.assertIsNotNone(launch_tui)
        except ImportError:
            self.skipTest("prompt_toolkit not installed")


class TestFrontendGUIImport(unittest.TestCase):
    """Test GUI frontend imports"""

    def test_import_gui_backend(self):
        from embedagent.frontend.gui.backend import GUIBackend

        self.assertIsNotNone(GUIBackend)

    def test_import_gui_launcher(self):
        from embedagent.frontend.gui import launch_gui

        self.assertIsNotNone(launch_gui)


if __name__ == "__main__":
    unittest.main()
