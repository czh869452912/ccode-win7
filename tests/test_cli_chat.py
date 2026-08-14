from __future__ import annotations

import io
from types import SimpleNamespace

from embedagent_protocol import (
    CapabilitySnapshot,
    CommandDescriptor,
    FailureRecord,
    InteractionDescriptor,
    SessionBootstrap,
    SessionEventEnvelope,
    ShellDescriptor,
    ThreadShell,
)

from embedagent.cli.options import CliLaunchOptions, CliOptions
from embedagent.frontend.runtime import RuntimeAction


def _shell():
    return ShellDescriptor(
        commands=[
            CommandDescriptor(
                id="custom.dynamic",
                label="Dynamic Inspect",
                group="custom",
                summary="Inspect with the active application",
                dispatch={"kind": "session.command", "command": "dynamic"},
                availability={"visible_when": "has_session"},
            )
        ],
        interactions=[
            InteractionDescriptor(kind="permission", renderer_key="interaction"),
            InteractionDescriptor(kind="user_input", renderer_key="interaction"),
        ],
    )


def _bootstrap(session_id="session-1", mode="verify", activities=None, pending=None):
    snapshot = {"session_id": session_id, "status": "idle", "current_mode": mode}
    thread_pending = pending is not None
    if pending is not None:
        snapshot.update(
            {
                "status": (
                    "waiting_permission"
                    if pending.get("kind") == "permission"
                    else "waiting_user_input"
                ),
                "pending_interaction_valid": True,
                "pending_interaction": dict(pending),
            }
        )
    return SessionBootstrap(
        schema_version=1,
        event_cursor=0,
        thread=ThreadShell(
            id=session_id,
            title="Session",
            archived=False,
            current_mode=mode,
            status=str(snapshot["status"]),
            updated_at="2026-08-14T00:00:00Z",
            pending_interaction=thread_pending,
        ),
        snapshot=snapshot,
        activities=list(activities or []),
        capabilities=CapabilitySnapshot(),
    )


class ScriptedInput(object):
    def __init__(self, values):
        self.values = list(values)

    def readline(self):
        if not self.values:
            return ""
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class FakeRuntime(object):
    def __init__(self, bootstrap=None, turn_events=None, response_events=None):
        self.bootstrap = bootstrap or _bootstrap()
        self.turn_events = list(turn_events or [])
        self.response_events = list(response_events or [])
        self.active_session_id = ""
        self.dispatch = None
        self.created_modes = []
        self.resumed = []
        self.submissions = []
        self.commands = []
        self.responses = []
        self.cancelled = []
        self.wait_interrupts = 0
        self.submit_interrupts = 0
        self._sequence = 0
        self._terminal = None

    def bind_dispatch(self, dispatch):
        assert self.dispatch is None
        self.dispatch = dispatch

    def create_session(self, mode):
        self.created_modes.append(mode)
        self.active_session_id = self.bootstrap.thread.id
        self._activate("create")
        return self.bootstrap

    def resume_session(self, reference, mode):
        self.resumed.append((reference, mode))
        self.active_session_id = self.bootstrap.thread.id
        self._activate("resume")
        return self.bootstrap

    def submit_user_message(self, session_id, text, stream=True):
        self.submissions.append((session_id, text, stream))
        if self.submit_interrupts:
            self.submit_interrupts -= 1
            raise KeyboardInterrupt
        events = self.turn_events.pop(0) if self.turn_events else []
        self._emit_all(events)

    def wait_for_terminal(self):
        if self.wait_interrupts:
            self.wait_interrupts -= 1
            raise KeyboardInterrupt
        assert self._terminal is not None
        terminal, self._terminal = self._terminal, None
        return terminal

    def dispatch_command(self, shell, name, args, availability=None, default_mode=""):
        del availability, default_mode
        command = next(item for item in shell.commands if item.id == name)
        values = list(args)
        self.commands.append((name, values))
        if command.dispatch.get("kind") == "session.command":
            text = "/" + str(command.dispatch.get("command") or "")
            if values:
                text += " " + " ".join(values)
            self.submit_user_message(self.active_session_id, text, stream=True)
        return command

    def respond_to_interaction(self, session_id, interaction_id, payload):
        self.responses.append((session_id, interaction_id, payload))
        events = self.response_events.pop(0) if self.response_events else []
        self._emit_all(events)
        return self.bootstrap

    def cancel_session(self, session_id):
        self.cancelled.append(session_id)
        return self.bootstrap

    def _activate(self, reason):
        self.dispatch(
            RuntimeAction(
                "session_activated",
                {
                    "session_id": self.bootstrap.thread.id,
                    "cursor": self.bootstrap.event_cursor,
                    "generation": 1,
                    "reason": reason,
                    "bootstrap": self.bootstrap.to_dict(),
                },
            )
        )

    def _emit_all(self, records):
        for event_kind, payload in records:
            self._sequence += 1
            envelope = SessionEventEnvelope(
                schema_version=1,
                event_id="event-%s" % self._sequence,
                session_id=self.active_session_id,
                sequence=self._sequence,
                event_kind=event_kind,
                timestamp="2026-08-14T00:00:01Z",
                payload=payload,
            )
            self.dispatch(
                RuntimeAction(
                    "session_event",
                    {
                        "event": envelope.to_dict(),
                        "lifecycle": "ready",
                        "generation": 1,
                    },
                )
            )
            self._set_terminal(event_kind, payload)

    def _set_terminal(self, event_kind, payload):
        if event_kind in ("approval.requested", "user-input.requested"):
            failure = FailureRecord(
                code="interaction_required",
                message="interaction required",
                retryable=False,
                source="session",
            )
            status = "blocked"
            final_text = ""
            outcome = {}
        elif event_kind == "session.finished":
            failure = None
            status = "completed"
            final_text = str(payload.get("final_text") or "")
            outcome = dict(payload.get("outcome") or {})
        else:
            return
        self._terminal = RuntimeAction(
            "terminal_outcome",
            {
                "session_id": self.active_session_id,
                "status": status,
                "final_text": final_text,
                "outcome": outcome,
                "failure": failure.to_dict() if failure is not None else None,
            },
        )


def _options(resume="", mode=""):
    return CliOptions(
        command="chat",
        launch=CliLaunchOptions(workspace="C:\\workspace"),
        resume=resume,
        mode=mode,
    )


def _application(runtime, resume="", mode=""):
    return SimpleNamespace(
        options=_options(resume=resume, mode=mode),
        launch_config=SimpleNamespace(
            app_config=SimpleNamespace(default_mode="verify"),
        ),
        client_runtime=runtime,
        shell_descriptor=_shell(),
    )


def _run(application, values):
    from embedagent.cli.chat import run_chat_command

    stdout = io.StringIO()
    stderr = io.StringIO()
    result = run_chat_command(
        application,
        input_stream=ScriptedInput(values),
        stdout=stdout,
        stderr=stderr,
    )
    return result, stdout.getvalue(), stderr.getvalue()


def _completed(text="done"):
    return [
        ("assistant.delta", {"text": text}),
        (
            "session.finished",
            {"final_text": text, "outcome": {"kind": "completed"}},
        ),
    ]


def test_chat_creates_session_renders_history_and_runs_ordinary_turn():
    runtime = FakeRuntime(
        bootstrap=_bootstrap(
            activities=[
                {"kind": "user", "content": "Earlier question", "status": "completed"},
                {"kind": "assistant", "content": "Earlier answer", "status": "completed"},
            ]
        ),
        turn_events=[_completed("hello")],
    )

    exit_code, stdout, stderr = _run(_application(runtime), ["hi\n", "/exit\n"])

    assert exit_code == 0
    assert runtime.created_modes == ["verify"]
    assert runtime.submissions == [("session-1", "hi", True)]
    assert "user> Earlier question" in stdout
    assert "assistant> Earlier answer" in stdout
    assert "hello" in stdout
    assert stderr == ""


def test_chat_resumes_selected_session_without_creating():
    runtime = FakeRuntime()

    exit_code, _stdout, _stderr = _run(
        _application(runtime, resume="latest", mode="debug"),
        ["/exit\n"],
    )

    assert exit_code == 0
    assert runtime.created_modes == []
    assert runtime.resumed == [("latest", "debug")]


def test_chat_help_and_dynamic_slash_command_use_shell_descriptor():
    runtime = FakeRuntime(turn_events=[_completed("inspected")])

    exit_code, stdout, stderr = _run(
        _application(runtime),
        ["/help\n", "/dynamic src/main.c\n", "/missing\n", "/exit\n"],
    )

    assert exit_code == 0
    assert "/help" in stdout
    assert "Dynamic Inspect" in stdout
    assert runtime.commands == [("custom.dynamic", ["src/main.c"])]
    assert runtime.submissions == [("session-1", "/dynamic src/main.c", True)]
    assert "error: usage_error" in stderr


def test_chat_answers_permission_only_through_runtime_interaction_operation():
    runtime = FakeRuntime(
        turn_events=[
            [
                (
                    "approval.requested",
                    {
                        "interaction_id": "approval-1",
                        "reason": "Allow operation?",
                        "category": "custom",
                    },
                )
            ]
        ],
        response_events=[
            [
                ("approval.resolved", {"interaction_id": "approval-1"}),
                *_completed("approved"),
            ]
        ],
    )

    exit_code, stdout, stderr = _run(
        _application(runtime),
        ["change it\n", "1\n", "/exit\n"],
    )

    assert exit_code == 0
    assert "Allow operation?" in stdout
    assert runtime.responses == [("session-1", "approval-1", {"decision": "accept"})]
    assert stderr == ""


def test_chat_local_exit_leaves_pending_interaction_untouched():
    runtime = FakeRuntime(
        turn_events=[
            [
                (
                    "approval.requested",
                    {"interaction_id": "approval-1", "reason": "Allow operation?"},
                )
            ]
        ]
    )

    exit_code, _stdout, _stderr = _run(
        _application(runtime),
        ["change it\n", "/exit\n"],
    )

    assert exit_code == 0
    assert runtime.responses == []


def test_chat_answers_interaction_restored_from_bootstrap_projection():
    pending = {
        "interaction_id": "approval-restored",
        "kind": "permission",
        "reason": "Approve restored operation?",
    }
    runtime = FakeRuntime(
        bootstrap=_bootstrap(pending=pending),
        response_events=[[_completed("restored")[1]]],
    )

    exit_code, stdout, stderr = _run(
        _application(runtime, resume="latest"),
        ["3\n", "/exit\n"],
    )

    assert exit_code == 0
    assert "Approve restored operation?" in stdout
    assert runtime.responses == [("session-1", "approval-restored", {"decision": "decline"})]
    assert stderr == ""


def test_chat_answers_user_input_option_with_descriptor_payload():
    runtime = FakeRuntime(
        turn_events=[
            [
                (
                    "user-input.requested",
                    {
                        "interaction_id": "input-1",
                        "questions": [
                            {
                                "id": "answer",
                                "question": "Choose target",
                                "options": [
                                    {"index": 1, "label": "Build", "value": "build"},
                                    {"index": 2, "label": "Verify", "value": "verify"},
                                ],
                            }
                        ],
                    },
                )
            ]
        ],
        response_events=[
            [
                ("user-input.resolved", {"interaction_id": "input-1"}),
                *_completed("selected"),
            ]
        ],
    )

    exit_code, stdout, stderr = _run(
        _application(runtime),
        ["choose\n", "2\n", "/exit\n"],
    )

    assert exit_code == 0
    assert "Choose target" in stdout
    assert runtime.responses == [("session-1", "input-1", {"answers": {"answer": "verify"}})]
    assert stderr == ""


def test_chat_eof_exits_and_repeated_idle_interrupt_returns_cancelled():
    eof_runtime = FakeRuntime()
    assert _run(_application(eof_runtime), [])[0] == 0

    interrupted = FakeRuntime()
    exit_code, stdout, _stderr = _run(
        _application(interrupted),
        [KeyboardInterrupt(), KeyboardInterrupt()],
    )
    assert exit_code == 130
    assert "^C" in stdout
    assert interrupted.cancelled == []


def test_chat_running_interrupt_cancels_active_turn_and_returns_to_input():
    runtime = FakeRuntime(turn_events=[[("turn.started", {"turn_id": "turn-1"})]])
    runtime.wait_interrupts = 1

    exit_code, _stdout, _stderr = _run(
        _application(runtime),
        ["long task\n", "/exit\n"],
    )

    assert exit_code == 0
    assert runtime.cancelled == ["session-1"]


def test_chat_interrupt_during_submit_also_cancels_active_turn():
    runtime = FakeRuntime()
    runtime.submit_interrupts = 1

    exit_code, _stdout, _stderr = _run(
        _application(runtime),
        ["long task\n", "/exit\n"],
    )

    assert exit_code == 0
    assert runtime.cancelled == ["session-1"]


def test_chat_object_owns_no_session_history_workflow_or_task_truth():
    from embedagent.cli.chat import CliChat

    runtime = FakeRuntime()
    chat = CliChat(
        _application(runtime),
        input_stream=ScriptedInput([]),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    owned = set(chat.__dict__)
    for forbidden in ("history", "session", "workflow", "task"):
        assert all(forbidden not in name for name in owned)
