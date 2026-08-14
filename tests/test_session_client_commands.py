from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from embedagent_protocol import (
    CapabilitySnapshot,
    CommandDescriptor,
    SessionBootstrap,
    SessionEventEnvelope,
    ShellDescriptor,
    ThreadShell,
)

from embedagent.frontend.runtime import SessionClientRuntime
from embedagent.frontend.runtime.commands import (
    UnavailableShellCommand,
    UnknownShellCommand,
    UnsupportedShellDispatch,
    resolve_command,
)

ROOT = Path(__file__).resolve().parents[1]


def _bootstrap(session_id="session-1", cursor=1):
    return SessionBootstrap(
        schema_version=1,
        event_cursor=cursor,
        thread=ThreadShell(
            id=session_id,
            title="Session",
            archived=False,
            current_mode="build",
            status="idle",
            updated_at="2026-08-13T00:00:00Z",
        ),
        snapshot={"session_id": session_id, "status": "idle"},
        activities=[],
        capabilities=CapabilitySnapshot(),
    )


def _event(event_kind, payload, sequence=2):
    return SessionEventEnvelope(
        schema_version=1,
        event_id="event-%s" % sequence,
        session_id="session-1",
        sequence=sequence,
        event_kind=event_kind,
        timestamp="2026-08-13T00:00:02Z",
        payload=payload,
    )


class FakeSessionPort(object):
    def __init__(self):
        self.bootstrap = _bootstrap()
        self.submissions = []
        self.closed = False

    def get_session_bootstrap(self, reference, mode=""):
        del reference, mode
        return self.bootstrap

    def submit_user_message(self, session_id, text, stream):
        self.submissions.append((session_id, text, stream))

    def close(self):
        self.closed = True


def _shell():
    return ShellDescriptor(
        commands=[
            CommandDescriptor(
                id="workflow.inspect",
                label="Inspect",
                group="workflow",
                dispatch={"kind": "session.command", "command": "inspect"},
                availability={"visible_when": "has_session"},
            ),
            CommandDescriptor(
                id="custom.dynamic",
                label="Dynamic",
                group="custom",
                dispatch={"kind": "session.command", "command": "totally-dynamic"},
            ),
            CommandDescriptor(
                id="custom.hidden",
                label="Hidden",
                group="custom",
                dispatch={"kind": "session.command", "command": "hidden"},
                availability={"visible_when": "feature_enabled"},
            ),
            CommandDescriptor(
                id="custom.unsupported",
                label="Unsupported",
                group="custom",
                dispatch={"kind": "custom.unknown"},
            ),
        ]
    )


def _runtime():
    runtime = SessionClientRuntime()
    port = FakeSessionPort()
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    return runtime, port


def test_resolve_command_uses_declared_identity_alias_and_availability():
    shell = _shell()

    assert resolve_command(shell, "workflow.inspect", {"has_session": True}).id == (
        "workflow.inspect"
    )
    assert resolve_command(shell, "/inspect", {"has_session": True}).id == ("workflow.inspect")
    with pytest.raises(UnavailableShellCommand):
        resolve_command(shell, "custom.hidden", {"feature_enabled": False})
    with pytest.raises(UnknownShellCommand):
        resolve_command(shell, "agent.cpp.magic", {"has_session": True})


def test_runtime_dispatches_only_descriptor_declared_command_and_arguments():
    runtime, port = _runtime()

    runtime.dispatch_command(
        _shell(),
        "custom.dynamic",
        ["src/main.c", "--brief"],
        availability={"has_session": True},
    )

    assert port.submissions == [("session-1", "/totally-dynamic src/main.c --brief", True)]
    with pytest.raises(UnsupportedShellDispatch):
        runtime.dispatch_command(
            _shell(),
            "custom.unsupported",
            [],
            availability={"has_session": True},
        )


def test_runtime_command_source_has_no_application_workflow_or_tool_branches():
    source = (ROOT / "src/embedagent/frontend/runtime/commands.py").read_text(encoding="utf-8") + (
        ROOT / "src/embedagent/frontend/runtime/session_client_runtime.py"
    ).read_text(encoding="utf-8")

    for forbidden in ("application_id", "workflow_type", "tool_name"):
        assert forbidden not in source


@pytest.mark.parametrize(
    "event,expected_status,expected_failure",
    (
        (
            _event(
                "session.finished",
                {
                    "final_text": "done",
                    "outcome": {"kind": "completed", "reason": "completed"},
                },
            ),
            "completed",
            None,
        ),
        (
            _event(
                "approval.requested",
                {"interaction_id": "approval-1", "request_id": "approval-1"},
            ),
            "blocked",
            "interaction_required",
        ),
        (
            _event(
                "session.error",
                {
                    "status": "error",
                    "failure": {
                        "code": "provider_error",
                        "message": "provider failed",
                        "retryable": True,
                        "source": "provider",
                    },
                },
            ),
            "failed",
            "provider_error",
        ),
        (
            _event(
                "session.finished",
                {
                    "final_text": "",
                    "outcome": {"kind": "cancelled", "reason": "aborted"},
                },
            ),
            "cancelled",
            "cancelled",
        ),
    ),
)
def test_runtime_waits_for_structured_terminal_outcomes(event, expected_status, expected_failure):
    runtime, _port = _runtime()

    runtime.on_session_event(event)
    result = runtime.wait_for_terminal(timeout_s=0).to_dict()

    assert result["status"] == expected_status
    failure = result.get("failure")
    assert (failure or {}).get("code") == expected_failure


def test_runtime_wait_uses_condition_and_returns_timeout():
    runtime, _port = _runtime()

    def complete():
        time.sleep(0.02)
        runtime.on_session_event(
            _event(
                "session.finished",
                {
                    "final_text": "done",
                    "outcome": {"kind": "completed", "reason": "completed"},
                },
            )
        )

    worker = threading.Thread(target=complete)
    worker.start()
    completed = runtime.wait_for_terminal(timeout_s=1.0).to_dict()
    worker.join(1.0)
    assert completed["status"] == "completed"

    other, _other_port = _runtime()
    timed_out = other.wait_for_terminal(timeout_s=0.01).to_dict()
    assert timed_out["status"] == "timeout"
    assert timed_out["failure"]["code"] == "runtime_error"
