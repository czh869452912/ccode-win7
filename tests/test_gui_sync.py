"""Tests for GUI real-time sync callbacks: todos_refresh and artifacts_refresh."""
import pytest
from unittest.mock import MagicMock


def test_websocket_frontend_has_on_todos_refresh():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    assert hasattr(WebSocketFrontend, "on_todos_refresh"), \
        "WebSocketFrontend must have on_todos_refresh method"


def test_websocket_frontend_has_on_artifacts_refresh():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    assert hasattr(WebSocketFrontend, "on_artifacts_refresh"), \
        "WebSocketFrontend must have on_artifacts_refresh method"


def test_on_todos_refresh_dispatches_correct_type():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    frontend = WebSocketFrontend()
    dispatched = []
    frontend._dispatch_message = lambda msg: dispatched.append(msg) or True
    frontend.on_todos_refresh()
    assert len(dispatched) == 1
    assert dispatched[0]["type"] == "todos_refresh"


def test_on_artifacts_refresh_dispatches_correct_type():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    frontend = WebSocketFrontend()
    dispatched = []
    frontend._dispatch_message = lambda msg: dispatched.append(msg) or True
    frontend.on_artifacts_refresh()
    assert len(dispatched) == 1
    assert dispatched[0]["type"] == "artifacts_refresh"


def test_callback_bridge_calls_todos_refresh_for_manage_todos():
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


def test_callback_bridge_calls_artifacts_refresh_for_write_file():
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


def test_callback_bridge_calls_artifacts_refresh_for_edit_file():
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


def test_callback_bridge_does_not_call_refresh_for_unrelated_tool():
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
