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
        schema_version=2,
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
        schema_version=2,
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

    def respond_to_interaction(self, session_id, interaction_id, payload):
        del session_id, interaction_id, payload
        return self.bootstrap

    def close(self):
        self.closed = True


class ImmediateInteractionPort(FakeSessionPort):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime

    def respond_to_interaction(self, session_id, interaction_id, payload):
        del session_id, interaction_id, payload
        self.runtime.on_session_event(
            _event(
                "approval.resolved",
                {"interaction_id": "approval-1", "request_id": "approval-1"},
                sequence=3,
            )
        )
        self.runtime.on_session_event(
            _event(
                "session.finished",
                {
                    "final_text": "done",
                    "outcome": {"kind": "completed", "reason": "completed"},
                },
                sequence=4,
            )
        )
        return _bootstrap(cursor=4)


class CursorInterleavingInteractionPort(FakeSessionPort):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime

    def respond_to_interaction(self, session_id, interaction_id, payload):
        del session_id, interaction_id, payload
        self.runtime.on_session_event(
            _event(
                "approval.resolved",
                {"interaction_id": "approval-1", "request_id": "approval-1"},
                sequence=3,
            )
        )
        captured = _bootstrap(cursor=3)
        self.runtime.on_session_event(
            _event(
                "session.finished",
                {
                    "final_text": "done",
                    "outcome": {"kind": "completed", "reason": "completed"},
                },
                sequence=4,
            )
        )
        return captured


class InspectingMutationPort(FakeSessionPort):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime
        self.observed = []
        self.error = None
        self.during_request = None

    def get_session_bootstrap(self, reference, mode=""):
        del mode
        cursor = 1 if reference == "session-1" else 2
        return _bootstrap(session_id=reference, cursor=cursor)

    def _response(self, session_id="session-1"):
        self.observed.append((self.runtime.lifecycle, self.runtime.generation))
        callback, self.during_request = self.during_request, None
        if callback is not None:
            callback()
        if self.error is not None:
            raise self.error
        return _bootstrap(session_id=session_id, cursor=2)

    def create_session(self, mode):
        del mode
        return self._response("session-2")

    def resume_session(self, reference, mode):
        del reference, mode
        return self._response()

    def set_session_mode(self, session_id, mode):
        del mode
        return self._response(session_id)

    def cancel_session(self, session_id):
        return self._response(session_id)


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
    "event,expected_status,expected_failure,expected_lifecycle",
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
            "ready",
        ),
        (
            _event(
                "approval.requested",
                {"interaction_id": "approval-1", "request_id": "approval-1"},
            ),
            "blocked",
            "interaction_required",
            "waiting_interaction",
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
                        "phase": "provider_request",
                        "kind": "provider",
                        "correlation_id": "",
                        "safe_message": "The model provider request failed.",
                        "exception_type": "",
                    },
                },
            ),
            "failed",
            "provider_error",
            "failed",
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
            "ready",
        ),
    ),
)
def test_runtime_waits_for_structured_terminal_outcomes(
    event,
    expected_status,
    expected_failure,
    expected_lifecycle,
):
    runtime, _port = _runtime()
    runtime.submit_active_message("test", stream=True)

    runtime.on_session_event(event)
    result = runtime.wait_for_terminal(timeout_s=0).to_dict()

    assert result["status"] == expected_status
    failure = result.get("failure")
    assert (failure or {}).get("code") == expected_failure
    assert runtime.lifecycle == expected_lifecycle


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


def test_terminal_outcome_is_published_only_after_event_action_delivery():
    dispatch_entered = threading.Event()
    release_dispatch = threading.Event()
    delivered = []

    def dispatch(action):
        if action.kind == "session_event":
            dispatch_entered.set()
            assert release_dispatch.wait(1.0)
        delivered.append(action.kind)

    runtime = SessionClientRuntime(dispatch=dispatch)
    port = FakeSessionPort()
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    worker = threading.Thread(
        target=runtime.on_session_event,
        args=(
            _event(
                "approval.requested",
                {"interaction_id": "approval-1", "request_id": "approval-1"},
            ),
        ),
    )
    worker.start()
    assert dispatch_entered.wait(1.0)

    try:
        during = runtime.wait_for_terminal(timeout_s=0).to_dict()

        assert during["status"] == "timeout"
        assert runtime.event_cursor == 1
        assert runtime.lifecycle == "ready"
        assert delivered == ["session_activated"]
    finally:
        release_dispatch.set()
        worker.join(1.0)

    assert not worker.is_alive()
    assert runtime.wait_for_terminal(timeout_s=0).to_dict()["status"] == "blocked"


def test_event_action_dispatch_failure_does_not_commit_the_event():
    actions = []

    def dispatch(action):
        actions.append(action)
        if action.kind == "session_event":
            raise RuntimeError("renderer failed")

    runtime = SessionClientRuntime(dispatch=dispatch)
    port = FakeSessionPort()
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")

    runtime.on_session_event(
        _event(
            "approval.requested",
            {"interaction_id": "approval-1", "request_id": "approval-1"},
        )
    )

    outcome = runtime.wait_for_terminal(timeout_s=0).to_dict()
    assert outcome["status"] == "failed"
    assert outcome["failure"] == {
        "code": "protocol_error",
        "message": "The runtime returned an invalid response.",
        "retryable": False,
        "source": "client_runtime",
        "phase": "client_runtime",
        "kind": "protocol",
        "correlation_id": "",
        "safe_message": "The runtime returned an invalid response.",
        "exception_type": "RuntimeError",
    }
    assert runtime.event_cursor == 1
    assert runtime.lifecycle == "failed"
    assert [action.kind for action in actions] == ["session_activated", "session_event"]


def test_interaction_response_preserves_terminal_event_arriving_before_bootstrap():
    runtime = SessionClientRuntime()
    port = ImmediateInteractionPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    runtime.on_session_event(
        _event(
            "approval.requested",
            {"interaction_id": "approval-1", "request_id": "approval-1"},
            sequence=2,
        )
    )
    assert runtime.wait_for_terminal(timeout_s=0).to_dict()["status"] == "blocked"

    runtime.respond_to_interaction("approval-1", {"decision": "accept"})
    result = runtime.wait_for_terminal(timeout_s=0).to_dict()

    assert result["status"] == "completed"
    assert result["final_text"] == "done"
    assert runtime.event_cursor == 4
    assert runtime.lifecycle == "ready"


def test_interaction_response_does_not_rewind_cursor_after_captured_bootstrap():
    actions = []
    runtime = SessionClientRuntime(dispatch=actions.append)
    port = CursorInterleavingInteractionPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    runtime.on_session_event(
        _event(
            "approval.requested",
            {"interaction_id": "approval-1", "request_id": "approval-1"},
            sequence=2,
        )
    )

    runtime.respond_to_interaction(
        "approval-1",
        {"decision": "accept"},
    )

    result = runtime.wait_for_terminal(timeout_s=0).to_dict()
    assert result["status"] == "completed"
    assert result["final_text"] == "done"
    assert runtime.event_cursor == 4
    assert [
        action.to_dict()["reason"] for action in actions if action.kind == "session_activated"
    ] == ["activate", "interaction_response"]


def test_interaction_response_discards_old_blocked_outcome_while_resume_is_pending():
    runtime, port = _runtime()
    runtime.on_session_event(
        _event(
            "approval.requested",
            {"interaction_id": "approval-1", "request_id": "approval-1"},
            sequence=2,
        )
    )
    assert runtime.wait_for_terminal(timeout_s=0).to_dict()["status"] == "blocked"
    port.bootstrap = _bootstrap(cursor=2)

    runtime.respond_to_interaction("approval-1", {"decision": "accept"})

    pending = runtime.wait_for_terminal(timeout_s=0).to_dict()
    assert pending["status"] == "timeout"
    runtime.on_session_event(
        _event(
            "session.finished",
            {"final_text": "later", "outcome": {"kind": "completed"}},
            sequence=3,
        )
    )
    assert runtime.wait_for_terminal(timeout_s=0).to_dict()["final_text"] == "later"


@pytest.mark.parametrize(
    "invoke",
    (
        lambda runtime: runtime.create_session("debug"),
        lambda runtime: runtime.resume_session("latest", "debug"),
        lambda runtime: runtime.set_session_mode("session-1", "verify"),
        lambda runtime: runtime.cancel_session("session-1"),
    ),
)
def test_bootstrap_operations_begin_generation_before_port_request(invoke):
    runtime = SessionClientRuntime()
    port = InspectingMutationPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    port.observed = []

    invoke(runtime)

    assert port.observed == [("activating", 2)]


def test_failed_bootstrap_request_rolls_back_and_replays_buffered_event():
    runtime = SessionClientRuntime()
    port = InspectingMutationPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    port.error = RuntimeError("request failed")
    port.during_request = lambda: runtime.on_session_event(
        _event("assistant.delta", {"text": "two"}, sequence=2)
    )

    with pytest.raises(RuntimeError, match="request failed"):
        runtime.set_session_mode("session-1", "verify")

    assert runtime.active_session_id == "session-1"
    assert runtime.event_cursor == 2
    assert runtime.lifecycle == "ready"
    assert runtime.generation == 2


def test_stale_returned_bootstrap_cannot_overwrite_nested_activation():
    runtime = SessionClientRuntime()
    port = InspectingMutationPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    port.during_request = lambda: runtime.activate_session("session-2")

    with pytest.raises(RuntimeError, match="bootstrap_transaction_superseded"):
        runtime.set_session_mode("session-1", "verify")

    assert runtime.active_session_id == "session-2"
    assert runtime.event_cursor == 2
    assert runtime.generation == 3


def test_runtime_installs_failed_lifecycle_from_error_bootstrap():
    runtime = SessionClientRuntime()
    port = FakeSessionPort()
    port.bootstrap = SessionBootstrap(
        schema_version=2,
        event_cursor=1,
        thread=ThreadShell(
            id="session-1",
            title="Session",
            archived=False,
            current_mode="build",
            status="error",
            updated_at="2026-08-13T00:00:00Z",
        ),
        snapshot={"session_id": "session-1", "status": "error"},
        activities=[],
        capabilities=CapabilitySnapshot(),
    )
    runtime.bind_session_port(port)

    runtime.activate_session("session-1")

    assert runtime.lifecycle == "failed"
