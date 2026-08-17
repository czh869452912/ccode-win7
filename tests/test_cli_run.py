from __future__ import annotations

import builtins
import io
import json
from types import SimpleNamespace

import pytest
from embedagent_protocol import (
    CapabilitySnapshot,
    SessionBootstrap,
    SessionEventEnvelope,
    ThreadShell,
)

from embedagent.cli.options import CliLaunchOptions, CliOptions
from embedagent.frontend.runtime import SessionClientRuntime


def _bootstrap(session_id="session-1", mode="build", cursor=1):
    return SessionBootstrap(
        schema_version=1,
        event_cursor=cursor,
        thread=ThreadShell(
            id=session_id,
            title="Session",
            archived=False,
            current_mode=mode,
            status="idle",
            updated_at="2026-08-14T00:00:00Z",
        ),
        snapshot={"session_id": session_id, "status": "idle", "current_mode": mode},
        activities=[],
        capabilities=CapabilitySnapshot(),
    )


def _event(event_kind, payload, session_id="session-1", sequence=2):
    return SessionEventEnvelope(
        schema_version=1,
        event_id="event-%s" % sequence,
        session_id=session_id,
        sequence=sequence,
        event_kind=event_kind,
        timestamp="2026-08-14T00:00:01Z",
        payload=payload,
    )


class FakeSessionPort(object):
    def __init__(self, runtime, event, bootstrap=None):
        self.runtime = runtime
        self.event = event
        self.bootstrap = bootstrap if bootstrap is not None else _bootstrap()
        self.created_modes = []
        self.resumed = []
        self.submissions = []
        self.interaction_responses = []
        self.closed = False

    def create_session(self, mode):
        self.created_modes.append(mode)
        return self.bootstrap

    def resume_session(self, reference, mode):
        self.resumed.append((reference, mode))
        return self.bootstrap

    def get_session_bootstrap(self, reference, mode=""):
        del reference, mode
        return self.bootstrap

    def submit_user_message(self, session_id, text, stream):
        self.submissions.append((session_id, text, stream))
        self.runtime.on_session_event(self.event)

    def respond_to_interaction(self, session_id, interaction_id, payload):
        self.interaction_responses.append((session_id, interaction_id, payload))
        raise AssertionError("one-shot run must leave interactions pending")

    def close(self):
        self.closed = True


def _options(output="text", resume="", mode=""):
    return CliOptions(
        command="run",
        launch=CliLaunchOptions(workspace="C:\\workspace"),
        mode=mode,
        resume=resume,
        output=output,
        task="say hi",
    )


def _application(event, output="text", resume="", mode="", bootstrap=None):
    runtime = SessionClientRuntime()
    port = FakeSessionPort(runtime, event, bootstrap=bootstrap)
    runtime.bind_session_port(port)
    application = SimpleNamespace(
        options=_options(output=output, resume=resume, mode=mode),
        launch_config=SimpleNamespace(
            app_config=SimpleNamespace(default_mode="verify"),
        ),
        client_runtime=runtime,
        session_port=port,
    )
    return application, port


def test_run_creates_session_submits_once_and_writes_only_final_text():
    from embedagent.cli.run import run_command

    application, port = _application(
        _event(
            "session.finished",
            {
                "final_text": "hello",
                "outcome": {"kind": "completed", "reason": "completed"},
            },
        )
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_command(application, stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert port.created_modes == ["verify"]
    assert port.resumed == []
    assert port.submissions == [("session-1", "say hi", True)]
    assert stdout.getvalue() == "hello\n"
    assert stderr.getvalue() == ""


def test_run_resumes_with_explicit_mode():
    from embedagent.cli.run import execute_run

    application, port = _application(
        _event(
            "session.finished",
            {"final_text": "resumed", "outcome": {"kind": "completed"}},
        ),
        resume="latest",
        mode="debug",
    )

    result = execute_run(application)

    assert result.status == "completed"
    assert port.created_modes == []
    assert port.resumed == [("latest", "debug")]


@pytest.mark.parametrize("event_kind", ["approval.requested", "user-input.requested"])
def test_run_leaves_permission_and_user_input_pending(event_kind, monkeypatch):
    from embedagent.cli.run import run_command

    event = _event(
        event_kind,
        {"interaction_id": "interaction-1", "request_id": "interaction-1"},
    )
    application, port = _application(event)
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(
        builtins,
        "input",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("one-shot run must not prompt")
        ),
    )

    exit_code = run_command(application, stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert port.interaction_responses == []
    assert application.client_runtime.lifecycle == "waiting_interaction"
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "error: interaction_required\n"


@pytest.mark.parametrize("failure_code", ["provider_error", "runtime_error"])
def test_run_preserves_structured_host_failure_category(failure_code):
    from embedagent.cli.run import run_command

    application, _port = _application(
        _event(
            "session.error",
            {
                "failure": {
                    "code": failure_code,
                    "message": "redacted failure",
                    "retryable": False,
                    "source": "host",
                    "phase": "host",
                    "kind": "provider" if failure_code == "provider_error" else "runtime",
                    "correlation_id": "",
                    "safe_message": (
                        "The model provider request failed."
                        if failure_code == "provider_error"
                        else "The operation failed."
                    ),
                    "exception_type": "",
                }
            },
        )
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_command(application, stdout=stdout, stderr=stderr)

    assert exit_code == 4
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "error: %s\n" % failure_code


def test_run_maps_invalid_failure_envelope_to_protocol_failure():
    from embedagent.cli.run import execute_run

    application, _port = _application(
        _event("session.error", {"failure": {"code": "provider_error"}})
    )

    result = execute_run(application)

    assert result.status == "failed"
    assert result.exit_code == 4
    assert result.failure.code == "protocol_error"


def test_run_preserves_cancellation_terminal_state():
    from embedagent.cli.run import execute_run

    application, _port = _application(
        _event(
            "session.finished",
            {
                "final_text": "",
                "outcome": {"kind": "cancelled", "reason": "aborted"},
            },
        )
    )

    result = execute_run(application)

    assert result.status == "cancelled"
    assert result.exit_code == 130
    assert result.failure.code == "cancelled"


def test_run_maps_invalid_bootstrap_to_protocol_failure_without_submitting():
    from embedagent.cli.run import execute_run

    application, port = _application(
        _event(
            "session.finished",
            {"final_text": "unused", "outcome": {"kind": "completed"}},
        ),
        bootstrap={"not": "a bootstrap"},
    )

    result = execute_run(application)

    assert result.status == "failed"
    assert result.failure.code == "protocol_error"
    assert port.submissions == []


def test_run_json_writes_one_stable_result_and_keeps_stderr_empty():
    from embedagent.cli.run import run_command

    application, _port = _application(
        _event(
            "session.error",
            {
                "failure": {
                    "code": "provider_error",
                    "message": "The model provider request failed.",
                    "retryable": True,
                    "source": "provider",
                    "phase": "provider_request",
                    "kind": "provider",
                    "correlation_id": "",
                    "safe_message": "The model provider request failed.",
                    "exception_type": "",
                }
            },
        ),
        output="json",
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_command(application, stdout=stdout, stderr=stderr)

    assert exit_code == 4
    assert stderr.getvalue() == ""
    assert stdout.getvalue().count("\n") == 1
    assert list(json.loads(stdout.getvalue())) == [
        "schema_version",
        "session_id",
        "status",
        "exit_code",
        "final_text",
        "outcome",
        "failure",
    ]
    assert json.loads(stdout.getvalue())["failure"] == {
        "code": "provider_error",
        "message": "The model provider request failed.",
        "retryable": True,
        "source": "provider",
        "phase": "provider_request",
        "kind": "provider",
        "correlation_id": "",
        "safe_message": "The model provider request failed.",
        "exception_type": "",
    }
