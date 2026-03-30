"""
Tests for new architecture - Protocol, Core, Frontend separation
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from embedagent.protocol import (
    CoreInterface,
    FrontendCallbacks,
    Message,
    MessageType,
    PermissionRequest,
    SessionSnapshot,
    SessionStatus,
    ToolCall,
    ToolResult,
    WorkspaceInfo,
)


class MockFrontend(FrontendCallbacks):
    """Mock frontend for testing"""
    
    def __init__(self):
        self.messages = []
        self.tools_started = []
        self.tools_finished = []
        self.permissions_requested = []
        self.session_changes = []
        self.stream_deltas = []
    
    def on_message(self, message: Message) -> None:
        self.messages.append(message)
    
    def on_tool_start(self, call: ToolCall) -> None:
        self.tools_started.append(call)
    
    def on_tool_progress(self, call_id: str, progress: dict) -> None:
        pass
    
    def on_tool_finish(self, result: ToolResult) -> None:
        self.tools_finished.append(result)
    
    def on_permission_request(self, request: PermissionRequest) -> bool:
        self.permissions_requested.append(request)
        return True
    
    def on_user_input_request(self, request):
        return None
    
    def on_session_status_change(self, snapshot: SessionSnapshot) -> None:
        self.session_changes.append(snapshot)
    
    def on_stream_delta(self, text: str) -> None:
        self.stream_deltas.append(text)


class TestProtocol(unittest.TestCase):
    """Test protocol layer"""
    
    def test_message_creation(self):
        msg = Message(
            id="msg_001",
            type=MessageType.USER,
            content="Hello"
        )
        self.assertEqual(msg.id, "msg_001")
        self.assertEqual(msg.type, MessageType.USER)
        self.assertEqual(msg.content, "Hello")
    
    def test_session_snapshot(self):
        snap = SessionSnapshot(
            session_id="sess_001",
            status=SessionStatus.IDLE,
            current_mode="code",
            created_at="2026-03-30T10:00:00",
            updated_at="2026-03-30T10:00:00"
        )
        self.assertEqual(snap.session_id, "sess_001")
        self.assertEqual(snap.status, SessionStatus.IDLE)
    
    def test_tool_call(self):
        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "test.py"},
            call_id="call_001"
        )
        self.assertEqual(call.tool_name, "read_file")
    
    def test_tool_result(self):
        result = ToolResult(
            tool_name="read_file",
            success=True,
            data={"content": "hello"}
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["content"], "hello")
    
    def test_workspace_info(self):
        info = WorkspaceInfo(
            path="/workspace",
            git_branch="main",
            git_dirty=2
        )
        self.assertEqual(info.git_branch, "main")


class TestMockFrontend(unittest.TestCase):
    """Test mock frontend implementation"""
    
    def setUp(self):
        self.frontend = MockFrontend()
    
    def test_message_handling(self):
        msg = Message(id="1", type=MessageType.ASSISTANT, content="Hi")
        self.frontend.on_message(msg)
        self.assertEqual(len(self.frontend.messages), 1)
        self.assertEqual(self.frontend.messages[0].content, "Hi")
    
    def test_tool_start(self):
        call = ToolCall(tool_name="edit_file", arguments={}, call_id="1")
        self.frontend.on_tool_start(call)
        self.assertEqual(len(self.frontend.tools_started), 1)
    
    def test_tool_finish(self):
        result = ToolResult(tool_name="edit_file", success=True, data={})
        self.frontend.on_tool_finish(result)
        self.assertEqual(len(self.frontend.tools_finished), 1)
    
    def test_permission_request(self):
        req = PermissionRequest(
            permission_id="perm_1",
            tool_name="write_file",
            category="file_write",
            reason="Test"
        )
        result = self.frontend.on_permission_request(req)
        self.assertTrue(result)
        self.assertEqual(len(self.frontend.permissions_requested), 1)
    
    def test_session_status_change(self):
        snap = SessionSnapshot(
            session_id="s1",
            status=SessionStatus.RUNNING,
            current_mode="code",
            created_at="2026-03-30T10:00:00",
            updated_at="2026-03-30T10:00:00"
        )
        self.frontend.on_session_status_change(snap)
        self.assertEqual(len(self.frontend.session_changes), 1)
    
    def test_stream_delta(self):
        self.frontend.on_stream_delta("Hello")
        self.frontend.on_stream_delta(" World")
        self.assertEqual(self.frontend.stream_deltas, ["Hello", " World"])


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


class TestCoreAdapterImport(unittest.TestCase):
    """Test Core adapter imports"""
    
    def test_import_adapter(self):
        from embedagent.core import AgentCoreAdapter
        self.assertIsNotNone(AgentCoreAdapter)


if __name__ == '__main__':
    unittest.main()
