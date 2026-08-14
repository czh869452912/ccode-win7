from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from embedagent_host import SessionNotFoundError
from embedagent_protocol import ThreadShell

from embedagent.cli.options import CliLaunchOptions, CliOptions


def _thread(
    session_id="session-1",
    title="First session",
    archived=False,
    mode="build",
    status="idle",
    updated_at="2026-08-14T08:00:00Z",
):
    return ThreadShell(
        id=session_id,
        title=title,
        archived=archived,
        current_mode=mode,
        status=status,
        updated_at=updated_at,
    )


def _summary(session_id="session-1", title="First session"):
    return {
        "schema_version": 1,
        "session_id": session_id,
        "title": title,
        "current_mode": "build",
        "status": "idle",
        "updated_at": "2026-08-14T08:00:00Z",
        "turn_count": 2,
        "summary_text": "Implemented the requested change.",
        "thread": {"title": title, "archived": False},
    }


class FakeSessionPort(object):
    def __init__(self):
        self.threads = [_thread(), _thread("session-2", "Second session", mode="debug")]
        self.summaries = {
            "latest": _summary(),
            "session-1": _summary(),
            "session-2": _summary("session-2", "Second session"),
        }
        self.list_calls = []
        self.summary_calls = []
        self.rename_calls = []
        self.archive_calls = []
        self.fork_calls = []

    def list_sessions(self, limit=10):
        self.list_calls.append(limit)
        return self.threads[:limit]

    def load_session_summary(self, reference):
        self.summary_calls.append(reference)
        if reference not in self.summaries:
            raise SessionNotFoundError(reference)
        return dict(self.summaries[reference])

    def rename_session(self, session_id, title):
        self.rename_calls.append((session_id, title))
        return _thread(session_id, title.strip())

    def archive_session(self, session_id):
        self.archive_calls.append(session_id)
        return _thread(session_id, archived=True)

    def fork_session(self, session_id, title=""):
        self.fork_calls.append((session_id, title))
        return _thread("session-fork", title or "First session Copy")

    def submit_user_message(self, *args, **kwargs):
        raise AssertionError("session management must not submit a turn")

    def respond_to_interaction(self, *args, **kwargs):
        raise AssertionError("session management must not answer an interaction")

    def get_session_bootstrap(self, *args, **kwargs):
        raise AssertionError("session management must not activate a session")


def _options(action, output="text", reference="", title="", limit=10):
    return CliOptions(
        command="sessions",
        launch=CliLaunchOptions(workspace="C:\\workspace"),
        output=output,
        sessions_action=action,
        reference=reference,
        title=title,
        limit=limit,
    )


def _application(action, output="text", reference="", title="", limit=10):
    runtime = MagicMock()
    port = FakeSessionPort()
    return (
        SimpleNamespace(
            options=_options(action, output, reference, title, limit),
            client_runtime=runtime,
            session_port=port,
        ),
        port,
        runtime,
    )


def _run(application):
    from embedagent.cli.sessions import run_sessions_command

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_sessions_command(application, stdout=stdout, stderr=stderr)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def test_sessions_list_text_uses_stable_columns_and_limit():
    application, port, runtime = _application("list", limit=1)

    exit_code, stdout, stderr = _run(application)

    assert exit_code == 0
    assert stdout == (
        "ID\tSTATUS\tMODE\tUPDATED\tTITLE\n"
        "session-1\tidle\tbuild\t2026-08-14T08:00:00Z\tFirst session\n"
    )
    assert stderr == ""
    assert port.list_calls == [1]
    assert runtime.method_calls == []


def test_sessions_list_json_serializes_thread_dtos_directly():
    application, _port, runtime = _application("list", output="json")

    exit_code, stdout, stderr = _run(application)

    assert exit_code == 0
    assert json.loads(stdout) == [thread.to_dict() for thread in application.session_port.threads]
    assert stdout.count("\n") == 1
    assert stderr == ""
    assert runtime.method_calls == []


def test_sessions_show_uses_summary_without_bootstrap_or_activation():
    application, port, runtime = _application("show", reference="latest")

    exit_code, stdout, stderr = _run(application)

    assert exit_code == 0
    assert stdout == (
        "ID: session-1\n"
        "Title: First session\n"
        "Status: idle\n"
        "Mode: build\n"
        "Updated: 2026-08-14T08:00:00Z\n"
        "Archived: no\n"
        "Turns: 2\n"
        "Summary: Implemented the requested change.\n"
    )
    assert stderr == ""
    assert port.summary_calls == ["latest"]
    assert runtime.method_calls == []


def test_sessions_show_json_serializes_summary_projection_directly():
    application, port, runtime = _application(
        "show",
        output="json",
        reference="session-1",
    )

    exit_code, stdout, stderr = _run(application)

    assert exit_code == 0
    assert json.loads(stdout) == port.summaries["session-1"]
    assert stderr == ""
    assert runtime.method_calls == []


@pytest.mark.parametrize(
    "action,title,expected_call,expected_arguments,expected_id",
    [
        ("rename", "Renamed", "rename_calls", [("session-1", "Renamed")], "session-1"),
        ("archive", "", "archive_calls", ["session-1"], "session-1"),
        ("fork", "Branch", "fork_calls", [("session-1", "Branch")], "session-fork"),
        ("fork", "", "fork_calls", [("session-1", "")], "session-fork"),
    ],
)
def test_session_mutations_resolve_reference_and_return_thread_json(
    action,
    title,
    expected_call,
    expected_arguments,
    expected_id,
):
    application, port, runtime = _application(
        action,
        output="json",
        reference="latest",
        title=title,
    )

    exit_code, stdout, stderr = _run(application)

    assert exit_code == 0
    assert json.loads(stdout)["id"] == expected_id
    assert port.summary_calls == ["latest"]
    assert getattr(port, expected_call) == expected_arguments
    assert stderr == ""
    assert runtime.method_calls == []


def test_sessions_rename_rejects_empty_title_before_calling_port():
    application, port, runtime = _application(
        "rename",
        reference="session-1",
        title="   ",
    )

    exit_code, stdout, stderr = _run(application)

    assert exit_code == 3
    assert stdout == ""
    assert stderr == "error: usage_error\n"
    assert port.summary_calls == []
    assert port.rename_calls == []
    assert runtime.method_calls == []


def test_sessions_missing_reference_uses_structured_failure_in_json():
    application, port, runtime = _application(
        "show",
        output="json",
        reference="missing",
    )

    exit_code, stdout, stderr = _run(application)

    result = json.loads(stdout)
    assert exit_code == 4
    assert result["status"] == "failed"
    assert result["failure"]["code"] == "session_not_found"
    assert stderr == ""
    assert port.summary_calls == ["missing"]
    assert runtime.method_calls == []
