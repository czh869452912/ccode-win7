import inspect
from concurrent.futures import CancelledError
from unittest.mock import MagicMock

import pytest
from embedagent_core.model import ModelClientError
from embedagent_host.frontend_errors import (
    FrontendPortError,
    SessionNotFoundError,
    failure_for_exception,
)
from embedagent_host.frontend_ports import (
    InProcessFrontendSessionPort,
    InProcessFrontendWorkspacePort,
)
from embedagent_host.hosted_command_service import HostedCommandService
from embedagent_host.hosted_interaction_service import HostedInteractionService
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_protocol import CapabilitySnapshot, SessionBootstrap, ThreadShell


def _capabilities():
    return {
        "modes": [
            {
                "slug": "build",
                "label": "Build",
                "description": "Implement",
            }
        ],
        "commands": [
            {
                "name": "help",
                "usage": "/help",
                "source_type": "builtin",
                "active": True,
                "dispatch": {"kind": "session.command", "command": "/help"},
            }
        ],
        "tools": [
            {
                "name": "read_file",
                "label": "Read File",
                "active": True,
                "renderer_key": "generic",
                "permission_category": "read",
            }
        ],
        "workflowPackages": [],
        "agentApplication": {
            "applicationId": "embedagent.generic",
            "label": "Generic Agent",
            "profileId": "embedagent.generic",
            "workflowPackageIds": [],
            "active": True,
        },
        "agentApplications": [],
        "resources": [],
        "modelProfiles": [],
        "emptyState": {},
    }


def _bootstrap(session_id="s-1"):
    return {
        "event_cursor": 3,
        "snapshot": {
            "session_id": session_id,
            "status": "idle",
            "current_mode": "build",
            "updated_at": "2026-08-13T00:00:00Z",
            "workflow_state": {},
            "pending_interaction_valid": False,
        },
        "history": {"activities": [], "integrity": {"status": "healthy"}},
        "capabilities": _capabilities(),
        "plan": None,
        "permission_context": {"session_id": session_id, "categories": []},
    }


def _summary(session_id="s-1"):
    return {
        "session_id": session_id,
        "title": "Session",
        "current_mode": "build",
        "status": "idle",
        "updated_at": "2026-08-13T00:00:00Z",
        "thread": {"title": "Session", "archived": False},
    }


def test_session_port_returns_strict_protocol_dtos_without_exposing_adapter():
    adapter = MagicMock()
    adapter.list_sessions.return_value = [_summary()]
    adapter.summary_store.load_summary.return_value = _summary()
    adapter.get_session_bootstrap.return_value = _bootstrap()
    adapter.get_session_capabilities.return_value = _capabilities()
    adapter.create_session.return_value = {"session_id": "s-1"}
    adapter.resume_session.return_value = {"session_id": "s-1"}
    adapter.rename_session.return_value = _summary()
    adapter.archive_session.return_value = {
        **_summary(),
        "thread": {"title": "Session", "archived": True},
    }
    adapter.fork_session.return_value = _summary("s-2")
    port = InProcessFrontendSessionPort(adapter)

    assert isinstance(port.list_sessions()[0], ThreadShell)
    assert isinstance(port.get_session_capabilities(), CapabilitySnapshot)
    assert isinstance(port.get_session_bootstrap("s-1"), SessionBootstrap)
    assert isinstance(port.create_session("build"), SessionBootstrap)
    assert isinstance(port.resume_session("latest", "build"), SessionBootstrap)
    assert isinstance(port.rename_session("s-1", "Renamed"), ThreadShell)
    assert port.archive_session("s-1").archived is True
    assert port.fork_session("s-1").id == "s-2"
    assert not hasattr(port, "adapter")


def test_session_port_submission_has_no_callback_or_wait_surface():
    adapter = MagicMock()
    port = InProcessFrontendSessionPort(adapter)

    result = port.submit_user_message("s-1", "hello", stream=False)

    assert result is None
    adapter.submit_user_message.assert_called_once_with(
        session_id="s-1",
        text="hello",
        stream=False,
        wait=False,
    )


def test_host_execution_signatures_have_no_frontend_callbacks():
    forbidden = {"event_handler", "permission_resolver", "user_input_resolver"}
    methods = (
        InProcessAdapter.__init__,
        InProcessAdapter.create_session,
        InProcessAdapter.resume_session,
        InProcessAdapter.submit_user_message,
        InProcessAdapter._run_turn,
        HostedCommandService.dispatch,
        HostedInteractionService.__init__,
    )
    for method in methods:
        assert forbidden.isdisjoint(inspect.signature(method).parameters)


def test_host_failure_classification_uses_exception_types_not_messages():
    cases = (
        (ModelClientError("任意服务错误"), "provider_error"),
        (SessionNotFoundError("missing"), "session_not_found"),
        (CancelledError("任意取消文本"), "cancelled"),
        (ValueError("任意协议错误"), "protocol_error"),
        (RuntimeError("任意运行时错误"), "runtime_error"),
    )

    for error, expected_code in cases:
        assert failure_for_exception(error, source="session").code == expected_code


@pytest.mark.parametrize(
    "error,expected_code",
    (
        (ModelClientError("provider text"), "provider_error"),
        (SessionNotFoundError("missing"), "session_not_found"),
        (CancelledError("cancel text"), "cancelled"),
        (TypeError("protocol text"), "protocol_error"),
    ),
)
def test_session_port_exposes_structured_failure(error, expected_code):
    adapter = MagicMock()
    adapter.get_session_bootstrap.side_effect = error
    port = InProcessFrontendSessionPort(adapter)

    with pytest.raises(FrontendPortError) as raised:
        port.get_session_bootstrap("s-1")

    assert raised.value.failure.code == expected_code


def test_workspace_port_delegates_json_safe_workspace_operations():
    adapter = MagicMock()
    adapter.get_workspace_snapshot.return_value = {"workspace": "D:/work"}
    adapter.list_workspace_tree.return_value = {"root": ".", "items": []}
    adapter.list_workspace_children.return_value = {"items": [{"path": "README.md"}]}
    adapter.read_workspace_file.return_value = {"path": "README.md", "content": "old\n"}
    adapter.write_workspace_file.return_value = {"path": "README.md", "content": "new\n"}
    adapter.reload_resources.return_value = {"status": "reloaded"}
    port = InProcessFrontendWorkspacePort(adapter)

    assert port.get_workspace_snapshot() == {"workspace": "D:/work"}
    assert port.list_workspace_tree() == {"root": ".", "items": []}
    assert port.list_file_children() == [{"path": "README.md"}]
    assert port.read_file("README.md")["content"] == "old\n"
    assert port.write_file("README.md", "new\n")["content"] == "new\n"
    assert "-old" in port.get_diff_preview("README.md", "new\n")["unified_diff"]
    assert port.reload_resources("s-1") == {"status": "reloaded"}
    assert not hasattr(port, "adapter")
