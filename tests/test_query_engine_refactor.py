import json
import os
import shutil
import sys
import threading
import time
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from conftest import register_default_c_workflow_tools
from embedagent_core.extensions import ExtensionManager, ToolResultPatch, WorkflowPatch
from embedagent_core.interaction import UserInputResponse
from embedagent_core.model import ModelClientError
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.session import Action, AssistantReply, Observation, PendingInteraction, Session
from embedagent_core.session_journal import EventIntent
from embedagent_core.tool_contracts import PreparedToolObservation
from embedagent_core.tool_execution import partition_tool_actions
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.runtime.context import ContextManager
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_host.runtime.transcript_store import TranscriptStore
from embedagent_host.runtime.workspace_intelligence import (
    CtagsProvider,
    DiagnosticsProvider,
    GitStateProvider,
    LlspProvider,
    RecipeProvider,
    WorkspaceIntelligenceBroker,
)
from query_engine_product_helpers import build_product_agent_application
from query_engine_product_helpers import build_product_query_engine as QueryEngine
from session_journal_test_helpers import apply_session_event, restore_events

from embedagent.config import AppConfig

_COUNTER = count(1)


def _make_workspace(name):
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "%s-%s-%s" % (name, os.getpid(), next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


def _py_sleep_command(seconds):
    return '"%s" -c "import time; time.sleep(%s)"' % (sys.executable, seconds)


def _wait_for_session_settled(adapter, session_id, timeout=5.0):
    deadline = time.time() + timeout
    snapshot = adapter.get_session_snapshot(session_id)
    while time.time() < deadline:
        snapshot = adapter.get_session_snapshot(session_id)
        if snapshot.get("status") != "running":
            return snapshot
        time.sleep(0.01)
    return snapshot


class AskThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="ask_user",
                        arguments={
                            "question": "下一步怎么做？",
                            "option_1": "切到 debug 模式继续排查",
                            "option_1_mode": "debug",
                            "option_2": "保持当前模式继续说明",
                        },
                        call_id="ask-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class WriteThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="write_file",
                        arguments={
                            "path": "src/generated_write.c",
                            "content": "int generated_write(void) {\n    return 0;\n}\n",
                            "overwrite": True,
                        },
                        call_id="write-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="written", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ModeSwitchThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="propose_mode_switch",
                        arguments={
                            "target_mode": "debug",
                            "reason": "需要进入 debug 模式继续排查",
                        },
                        call_id="mode-switch-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="debug ready", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class FakeLlspBackend(object):
    def collect(self, workspace, session, mode_name):
        return [
            {
                "title": "LLSP Symbols",
                "content": "llsp symbol demo -> src/demo.c",
                "metadata": {"backend": "fake", "workspace": workspace, "mode_name": mode_name},
            }
        ]


class CompactRetryClient(object):
    def __init__(self):
        self.calls = 0
        self.message_sizes = []
        self.messages = []

    def generate(self, messages, tools=None):
        self.calls += 1
        self.messages.append(messages)
        self.message_sizes.append(sum(len(str(item.get("content") or "")) for item in messages))
        if self.calls == 1:
            raise ModelClientError("prompt is too long: context length exceeded")
        return AssistantReply(content="after compact", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ToolClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="read_file",
                        arguments={"path": "src/demo.c"},
                        call_id="call-read-demo",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class TwoFailingBashThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls <= 2:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="bash",
                        arguments={
                            "command": "exit 1",
                            "cwd": ".",
                            "timeout_sec": 5,
                        },
                        call_id="bash-fail-%s" % self.calls,
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="diagnostics inspected", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ThreeFileWriteThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls <= 3:
            files = [
                ("README.md", "# Demo\n"),
                ("src/main.c", "int main(void) { return 0; }\n"),
                ("tests/test_demo.py", "def test_demo():\n    assert True\n"),
            ]
            path, content = files[self.calls - 1]
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="write_file",
                        arguments={
                            "path": path,
                            "content": content,
                            "overwrite": False,
                        },
                        call_id="write-%s" % self.calls,
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="files created", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ThreeDistinctBashFailuresThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls <= 3:
            commands = [
                'python -c "import sys; sys.exit(1)"',
                'python -c "import sys; sys.exit(2)"',
                'python -c "import sys; sys.exit(3)"',
            ]
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="bash",
                        arguments={
                            "command": commands[self.calls - 1],
                            "cwd": ".",
                            "timeout_sec": 5,
                        },
                        call_id="bash-diag-%s" % self.calls,
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="diagnostics completed", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class TwoReadDiagnosticsThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            action = Action(
                name="read_file",
                arguments={"path": "src/missing.c"},
                call_id="read-missing",
            )
            return AssistantReply(content="", actions=[action], finish_reason="tool_calls")
        if self.calls == 2:
            action = Action(
                name="read_file",
                arguments={"path": "src/binary.dat"},
                call_id="read-binary",
            )
            return AssistantReply(content="", actions=[action], finish_reason="tool_calls")
        return AssistantReply(
            content="read diagnostics inspected", actions=[], finish_reason="stop"
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class LongToolThenDoneClient(object):
    def __init__(self, tool_turns):
        self.calls = 0
        self.tool_turns = int(tool_turns)

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls <= self.tool_turns:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="read_file",
                        arguments={"path": "src/step_%02d.c" % self.calls},
                        call_id="read-step-%02d" % self.calls,
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(
            content="done after %s tool turns" % self.tool_turns,
            actions=[],
            finish_reason="stop",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class WorkflowPatchExtension(object):
    extension_id = "workflow_patch_test"
    builtin_extension = False

    def extension_capabilities(self):
        from embedagent_core.extensions import ExtensionCapability

        return [ExtensionCapability("tool_result", self.tool_result)]

    def tool_result(self, event, context):
        del event, context
        return ToolResultPatch(
            workflow_patch=WorkflowPatch(
                workflow={
                    "id": "patch-test",
                    "items": [{"id": "task-1", "title": "patched task"}],
                    "task_summary": {"total": 1},
                },
                metadata={"source": "workflow_patch_test"},
            )
        )


class SpecCodeWriteClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="write_file",
                        arguments={
                            "path": "src/spec_illegal.c",
                            "content": "int spec_illegal(void) {\n    return 0;\n}\n",
                            "overwrite": True,
                        },
                        call_id="write-spec-illegal",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class FakeClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        return AssistantReply(content="ok", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class EmptyStopClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        return AssistantReply(content="", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        return self.generate(messages, tools=tools)


class SnapshotInspectingClient(object):
    def __init__(self):
        self.messages = []
        self.tools = []

    def generate(self, messages, tools=None):
        self.messages.append(messages)
        self.tools.append(tools or [])
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        return reply


class UnsafeToolCallIdClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="read_file",
                        arguments={"path": "src/demo.c"},
                        call_id="read_file:1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class InspectingDoneClient(object):
    def __init__(self):
        self.messages = []

    def generate(self, messages, tools=None):
        self.messages.append(messages)
        return AssistantReply(content="recovered", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class RecordingSessionLock(object):
    def __init__(self):
        self._lock = threading.RLock()
        self._depth = 0

    def __enter__(self):
        self._lock.acquire()
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self._depth -= 1
        self._lock.release()

    def held(self):
        return self._depth > 0


class SpyTurnFrame(object):
    def __init__(self, kernel, turn_id, source):
        self._kernel = kernel
        self.turn_id = turn_id
        self.source = source

    def finish(self, transition, current_mode=None, workflow_state=None):
        self._kernel.finished.append(
            {
                "turn_id": self.turn_id,
                "source": self.source,
                "reason": transition.reason,
                "current_mode": current_mode,
                "workflow_state": workflow_state,
            }
        )

    def interrupt(self, reason, error="", current_mode=None, workflow_state=None):
        self._kernel.interrupted.append(
            {
                "turn_id": self.turn_id,
                "source": self.source,
                "reason": reason,
                "error": error,
                "current_mode": current_mode,
                "workflow_state": workflow_state,
            }
        )


class SpyKernel(object):
    def __init__(self, delegate=None):
        self._delegate = delegate
        self.started = []
        self.finished = []
        self.interrupted = []
        self.pending_permissions = []
        self.pending_user_inputs = []
        self.resolved_pending = []

    def begin_turn(self, session, turn_id, current_mode, workflow_state, source):
        del session
        self.started.append(
            {
                "turn_id": turn_id,
                "current_mode": current_mode,
                "workflow_state": workflow_state,
                "source": source,
            }
        )
        return SpyTurnFrame(self, turn_id, source)

    def record_pending_permission(
        self, session, action, permission_payload, current_mode, interaction_id=""
    ):
        self.pending_permissions.append(
            {
                "tool_name": action.name,
                "permission_payload": dict(permission_payload),
                "current_mode": current_mode,
                "interaction_id": interaction_id,
            }
        )
        return self._delegate.record_pending_permission(
            session,
            action,
            permission_payload,
            current_mode,
            interaction_id=interaction_id,
        )

    def record_pending_user_input(
        self,
        session,
        action,
        tool_name,
        request_payload,
        message,
        current_mode,
        interaction_id="",
    ):
        self.pending_user_inputs.append(
            {
                "tool_name": tool_name,
                "request_payload": dict(request_payload),
                "message": message,
                "current_mode": current_mode,
                "interaction_id": interaction_id,
            }
        )
        return self._delegate.record_pending_user_input(
            session,
            action,
            tool_name,
            request_payload,
            message,
            current_mode,
            interaction_id=interaction_id,
        )

    def resolve_pending_interaction(self, session, pending, resolution):
        self.resolved_pending.append(
            {
                "interaction_id": pending.interaction_id,
                "kind": pending.kind,
                "tool_name": pending.tool_name,
                "resolution": dict(resolution),
            }
        )
        return self._delegate.resolve_pending_interaction(session, pending, resolution)


class SpyActionService(object):
    def __init__(self, delegate):
        self.delegate = delegate
        self.executed = []

    def is_extension_blocked_observation(self, observation):
        return self.delegate.is_extension_blocked_observation(observation)

    def is_interactive_serial_skip(self, observation):
        return self.delegate.is_interactive_serial_skip(observation)

    def prepare_extension_tool_call(self, *args, **kwargs):
        return self.delegate.prepare_extension_tool_call(*args, **kwargs)

    def execute_parallel_tool_action(self, *args, **kwargs):
        return self.delegate.execute_parallel_tool_action(*args, **kwargs)

    def execute(self, effect, *args, **kwargs):
        self.executed.extend(action.name for action in effect.actions)
        return self.delegate.execute(effect, *args, **kwargs)

    def finalize(self, commit_tokens):
        return self.delegate.finalize(commit_tokens)


class LockCheckingContextManager(ContextManager):
    def __init__(self, lock, *args, **kwargs):
        super(LockCheckingContextManager, self).__init__(*args, **kwargs)
        self._lock = lock

    def build_messages(
        self,
        session,
        mode_name=None,
        tools=None,
        workflow_state="chat",
        force_compact=False,
    ):
        if not self._lock.held():
            raise AssertionError("session lock not held during context build")
        return super(LockCheckingContextManager, self).build_messages(
            session,
            mode_name=mode_name,
            tools=tools,
            workflow_state=workflow_state,
            force_compact=force_compact,
        )


class ParallelReadThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action("read_file", {"path": "src/missing.c"}, "call-read-missing"),
                    Action("read_file", {"path": "src/demo.c"}, "call-read-demo-1"),
                    Action("read_file", {"path": "src/demo.c"}, "call-read-demo-2"),
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="after discard", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ParallelSuccessfulReadThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action("read_file", {"path": "src/demo.c"}, "call-read-demo-a"),
                    Action("read_file", {"path": "src/demo.c"}, "call-read-demo-b"),
                    Action("read_file", {"path": "src/demo.c"}, "call-read-demo-c"),
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="after cancel", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ParallelReadThenEditClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action("read_file", {"path": "src/missing.c"}, "call-read-missing"),
                    Action("read_file", {"path": "src/demo.c"}, "call-read-demo-a"),
                    Action("read_file", {"path": "src/demo.c"}, "call-read-demo-b"),
                    Action(
                        "edit_file",
                        {"path": "src/demo.c", "old_text": "0", "new_text": "1"},
                        "call-edit-demo",
                    ),
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="after retry boundary", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class SlowCommandClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        "run_recipe",
                        {"recipe_id": "slow.recipe"},
                        "call-sleep-command",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="after long command", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class CountingToolRuntime(object):
    def __init__(self, base, slow_first=False, slow_read_calls=0, slow_delay_sec=0.2):
        self._base = base
        self.execute_calls = 0
        self.slow_first = slow_first
        self.slow_read_calls = int(slow_read_calls or 0)
        self.slow_delay_sec = float(slow_delay_sec or 0.0)
        self.call_names = []
        self.read_file_calls = 0

    def execute(self, name, arguments):
        self.execute_calls += 1
        self.call_names.append((name, dict(arguments)))
        if name == "read_file":
            self.read_file_calls += 1
        if name == "read_file":
            should_sleep = self.slow_first and self.read_file_calls == 1
            should_sleep = should_sleep or (
                self.slow_read_calls > 0 and self.read_file_calls <= self.slow_read_calls
            )
            if should_sleep:
                time.sleep(self.slow_delay_sec)
        return self._base.execute(name, arguments)

    def execute_with_interrupt(self, name, arguments, stop_event=None):
        self.execute_calls += 1
        self.call_names.append((name, dict(arguments)))
        if name == "read_file":
            self.read_file_calls += 1
            should_sleep = self.slow_first and self.read_file_calls == 1
            should_sleep = should_sleep or (
                self.slow_read_calls > 0 and self.read_file_calls <= self.slow_read_calls
            )
            if should_sleep:
                time.sleep(self.slow_delay_sec)
        return self._base.execute_with_interrupt(name, arguments, stop_event)

    def __getattr__(self, name):
        return getattr(self._base, name)


class TestQueryEngineRefactor(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("query-engine")
        os.makedirs(os.path.join(self.workspace, "src"), exist_ok=True)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n    return 0;\n}\n")
        with open(os.path.join(self.workspace, "src", "binary.dat"), "wb") as handle:
            handle.write(b"not text\x00data")
        for index in range(1, 11):
            with open(
                os.path.join(self.workspace, "src", "step_%02d.c" % index),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write("int step_%02d(void) {\n    return %d;\n}\n" % (index, index))
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        self.tools = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_partition_tool_actions_uses_capabilities(self):
        actions = [
            Action("read_file", {"path": "src/demo.c"}, "c1"),
            Action("grep_text", {"path": ".", "pattern": "demo"}, "c2"),
            Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "c3"),
            Action("git_status", {"path": "."}, "c4"),
        ]
        batches = partition_tool_actions(actions, self.tools.tool_capabilities)
        self.assertEqual([batch.parallel for batch in batches], [True, False, True])
        self.assertEqual([len(batch.actions) for batch in batches], [2, 1, 1])

    def test_read_file_execution_returns_raw_observation_without_stored_path(self):
        result = self.tools.execute("read_file", {"path": "src/demo.c"})
        self.assertTrue(result.success)
        self.assertIn("content", result.data)
        self.assertNotIn("content_stored_path", result.data)

    def test_agent_tool_action_service_rejects_inactive_tool(self):
        from embedagent_core.agent_effects import ExecuteToolBatchEffect, ToolBatchCompleted
        from embedagent_core.agent_extension_host import AgentExtensionHost
        from embedagent_core.agent_tool_action_service import (
            AgentToolActionService,
            InteractionFactory,
        )
        from embedagent_core.extensions import ExtensionManager

        class EmptyModeToolPolicy(object):
            def allowed_tools_for(self, mode_name, workflow_state=None):
                del mode_name, workflow_state
                return []

        policy = PermissionPolicy(auto_approve_all=True, workspace=self.workspace)
        host = AgentExtensionHost(
            manager=ExtensionManager(),
            tools=self.tools,
            permission_policy=policy,
            mode_tool_policy=EmptyModeToolPolicy(),
        )
        service = AgentToolActionService(
            tools=self.tools,
            permission_policy=policy,
            extension_host=host,
            app_config_provider=lambda: None,
            interaction_factory=InteractionFactory(),
        )

        result = service.execute(
            ExecuteToolBatchEffect(
                "tools-1",
                (Action("read_file", {"path": "missing.txt"}, "call-read"),),
                "build",
                "chat",
            ),
            Session(),
        )

        self.assertIsInstance(result, ToolBatchCompleted)
        observation = result.observations[0]
        self.assertFalse(observation.success)
        self.assertEqual(observation.data["error_kind"], "mode_tool_blocked")

    def test_parallel_interactive_action_requires_serial_action_execution(self):
        from embedagent_core.agent_tool_action_service import (
            AgentToolActionService,
            InteractionFactory,
        )

        policy = PermissionPolicy(auto_approve_all=True, workspace=self.workspace)
        engine = QueryEngine(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=policy,
        )
        service = AgentToolActionService(
            tools=self.tools,
            permission_policy=policy,
            extension_host=engine.extension_host,
            app_config_provider=lambda: None,
            interaction_factory=InteractionFactory(),
        )

        observation = service.execute_parallel_tool_action(
            Session(),
            Action("ask_user", {"question": "继续吗？"}, "call-ask"),
            "build",
            "chat",
            stop_event=None,
        )

        self.assertFalse(observation.success)
        self.assertEqual(observation.data["error_kind"], "interactive_serial_skip")
        self.assertTrue(service.is_interactive_serial_skip(observation))

    def test_agent_loop_can_be_constructed_without_runner_callback(self):
        import inspect

        from embedagent_core.agent_loop import AgentLoop

        self.assertEqual(
            list(inspect.signature(AgentLoop).parameters),
            ["kernel", "journal", "provider_steps", "tool_actions", "continuation_policy"],
        )

    def test_query_engine_exposes_slim_agent_components(self):
        from embedagent_core.agent_extension_host import AgentExtensionHost
        from embedagent_core.agent_loop import AgentLoop
        from embedagent_core.agent_tool_action_service import AgentToolActionService

        engine = QueryEngine(client=FakeClient(), tools=self.tools, max_turns=1)

        self.assertIsInstance(engine.extension_host, AgentExtensionHost)
        self.assertIsInstance(engine._action_service, AgentToolActionService)
        self.assertIsInstance(engine._agent_loop, AgentLoop)
        self.assertFalse(hasattr(engine._agent_loop, "_runner"))
        self.assertFalse(hasattr(QueryEngine, "_run_loop_impl"))
        self.assertFalse(hasattr(QueryEngine, "_execute_parallel_tool_action"))
        self.assertFalse(hasattr(QueryEngine, "_execute_action"))
        self.assertFalse(hasattr(QueryEngine, "_apply_extension_tool_result_patch"))
        self.assertFalse(hasattr(QueryEngine, "_prepare_extension_tool_call"))
        self.assertFalse(hasattr(QueryEngine, "_is_extension_blocked_observation"))
        self.assertFalse(hasattr(QueryEngine, "_schemas_for_active_tools"))
        self.assertFalse(hasattr(QueryEngine, "_allowed_tools_for_mode"))
        self.assertIs(engine.extension_manager, engine.extension_host.manager)

    def test_query_engine_does_not_own_compaction_payload_helpers(self):
        for helper_name in (
            "_compaction_token_counts",
            "_compaction_message_counts",
            "_compaction_file_activity",
            "_compaction_evidence_refs",
            "_compacted_history_payload",
        ):
            self.assertFalse(hasattr(QueryEngine, helper_name), helper_name)

    def test_query_engine_guard_stops_empty_provider_reply_without_tool_calls(self):
        client = EmptyStopClient()
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "guard_stop")
        self.assertIn("empty assistant response", result.transition.message)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result.final_text, "")
        self.assertEqual(session.turns[-1].steps[-1].status, "guard_stop")
        events = transcript_store.load_events(session.session_id)
        transitions = [item for item in events if item["type"] == "loop_transition"]
        self.assertEqual(transitions[-1]["payload"]["reason"], "guard_stop")

    def test_query_engine_continues_after_diagnostic_bash_failures(self):
        client = TwoFailingBashThenDoneClient()
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="运行诊断命令并继续分析",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "diagnostics inspected")
        self.assertEqual(client.calls, 3)
        self.assertEqual(len(session.turns[-1].observations), 2)
        self.assertTrue(
            all(
                isinstance(observation.data, dict)
                and observation.data.get("error_kind") == "command_failed"
                for observation in session.turns[-1].observations
            )
        )
        events = transcript_store.load_events(session.session_id)
        transitions = [item for item in events if item["type"] == "loop_transition"]
        self.assertEqual(transitions[-1]["payload"]["reason"], "completed")

    def test_query_engine_allows_progressive_multi_file_writes(self):
        client = ThreeFileWriteThenDoneClient()
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="创建三个项目文件",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "files created")
        self.assertEqual(client.calls, 4)
        self.assertTrue(os.path.exists(os.path.join(self.workspace, "README.md")))
        self.assertTrue(os.path.exists(os.path.join(self.workspace, "src", "main.c")))
        self.assertTrue(os.path.exists(os.path.join(self.workspace, "tests", "test_demo.py")))

    def test_query_engine_allows_distinct_diagnostic_bash_attempts(self):
        client = ThreeDistinctBashFailuresThenDoneClient()
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="运行三个不同诊断命令后继续",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "diagnostics completed")
        self.assertEqual(client.calls, 4)
        self.assertEqual(len(session.turns[-1].observations), 3)

    def test_query_engine_continues_after_read_diagnostic_failures(self):
        client = TwoReadDiagnosticsThenDoneClient()
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：explore")

        result = engine.submit_user_turn(
            user_text="检查读取错误后继续总结",
            stream=False,
            initial_mode="explore",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "read diagnostics inspected")
        self.assertEqual(client.calls, 3)
        observations = session.turns[-1].observations
        self.assertEqual(len(observations), 2)
        self.assertTrue(
            all(item.data.get("outcome_class") == "diagnostic_failure" for item in observations)
        )
        self.assertEqual(observations[0].data.get("error_kind"), "path_not_found")
        self.assertEqual(observations[1].data.get("error_kind"), "binary_file")
        events = transcript_store.load_events(session.session_id)
        transitions = [item for item in events if item["type"] == "loop_transition"]
        self.assertEqual(transitions[-1]["payload"]["reason"], "completed")

    def test_query_engine_guard_stops_repeated_parallel_no_progress_actions(self):
        client = ParallelSuccessfulReadThenDoneClient()
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="重复读取同一个文件",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "guard_stop")
        self.assertEqual(result.transition.message, "repeated no-progress action")
        self.assertEqual(client.calls, 1)
        self.assertEqual(len(session.turns[-1].observations), 3)

    def test_query_engine_handles_natural_language_mode_switch_before_provider(self):
        client = FakeClient()
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()

        result = engine.submit_user_turn(
            user_text="切换到build模式",
            stream=False,
            initial_mode="explore",
            session=session,
        )

        self.assertEqual(result.transition.reason, "mode_changed")
        self.assertEqual(result.transition.next_mode, "build")
        self.assertEqual(client.calls, 0)
        self.assertEqual(result.final_text, "已切换到 `build` 模式。")
        self.assertEqual(session.turns[-1].assistant_message, result.final_text)
        events = transcript_store.load_events(session.session_id)
        provider_events = [
            item
            for item in events
            if item["type"] == "operation_started"
            and item["payload"].get("kind") == "provider_request"
        ]
        self.assertEqual(provider_events, [])
        step_starts = [
            item
            for item in events
            if item["type"] == "operation_started" and item["payload"].get("kind") == "agent_step"
        ]
        step_finishes = [
            item
            for item in events
            if item["type"] == "operation_finished" and item["payload"].get("kind") == "agent_step"
        ]
        self.assertEqual(len(step_starts), 1)
        self.assertEqual(len(step_finishes), 1)
        self.assertEqual(step_finishes[0]["payload"]["result"].get("reason"), "mode_changed")

    def test_query_engine_handles_slash_mode_switch_before_provider(self):
        client = FakeClient()
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )

        result = engine.submit_user_turn(
            user_text="/mode debug",
            stream=False,
            initial_mode="build",
            session=Session(),
        )

        self.assertEqual(result.transition.reason, "mode_changed")
        self.assertEqual(result.transition.next_mode, "debug")
        self.assertEqual(client.calls, 0)

    def test_query_engine_slash_mode_with_remainder_uses_target_mode_context(self):
        client = SnapshotInspectingClient()
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )

        result = engine.submit_user_turn(
            user_text="/mode debug inspect workspace",
            stream=False,
            initial_mode="explore",
            session=Session(),
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.transition.next_mode, "debug")
        self.assertEqual(len(client.messages), 1)
        rendered = "\n".join(str(item.get("content") or "") for item in client.messages[0])
        self.assertIn("当前模式：debug", rendered)
        self.assertNotIn("当前模式：explore", rendered)
        self.assertIn("inspect workspace", rendered)

    def test_query_engine_routes_ask_user_through_action_service(self):
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        spy = SpyActionService(engine._action_service)
        engine._action_service = spy
        engine._agent_loop._tool_actions = spy
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")

        result = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )

        self.assertEqual(result.transition.reason, "user_input_wait")
        self.assertIn("ask_user", spy.executed)

    def test_query_engine_routes_mode_switch_proposal_through_action_service(self):
        engine = QueryEngine(
            client=ModeSwitchThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        spy = SpyActionService(engine._action_service)
        engine._action_service = spy
        engine._agent_loop._tool_actions = spy
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="调试",
            stream=False,
            initial_mode="build",
            session=session,
            user_input_handler=lambda request: None,
        )

        self.assertEqual(result.transition.reason, "user_input_wait")
        self.assertIn("propose_mode_switch", spy.executed)

    def test_mode_switch_proposal_records_own_tool_observation(self):
        engine = QueryEngine(
            client=ModeSwitchThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="调试",
            stream=False,
            initial_mode="build",
            session=session,
            user_input_handler=lambda request: UserInputResponse(
                answer="同意",
                selected_mode="debug",
            ),
        )

        self.assertEqual(result.transition.reason, "completed")
        observation = session.turns[-1].observations[0]
        self.assertEqual(observation.tool_name, "propose_mode_switch")
        self.assertEqual(observation.data["selected_mode"], "debug")
        self.assertTrue(observation.data["mode_changed"])

    def test_mode_switch_proposal_uses_action_target_when_response_omits_mode(self):
        engine = QueryEngine(
            client=ModeSwitchThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="调试",
            stream=False,
            initial_mode="build",
            session=session,
            user_input_handler=lambda request: UserInputResponse(answer="同意"),
        )

        self.assertEqual(result.transition.reason, "completed")
        observation = session.turns[-1].observations[0]
        self.assertEqual(observation.tool_name, "propose_mode_switch")
        self.assertEqual(observation.data["selected_mode"], "debug")
        self.assertTrue(observation.data["mode_changed"])

    def test_query_engine_routes_user_input_resume_through_action_service(self):
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        first = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )
        self.assertEqual(first.transition.reason, "user_input_wait")
        spy = SpyActionService(engine._action_service)
        engine._action_service = spy
        engine._agent_loop._tool_actions = spy

        resumed = engine.resume_interaction(
            session=session,
            initial_mode="spec",
            stream=False,
            interaction_resolution={
                "answer": "切到 debug 模式继续排查",
                "selected_index": 1,
                "selected_mode": "debug",
                "selected_option_text": "切到 debug 模式继续排查",
            },
        )

        self.assertEqual(resumed.transition.reason, "completed")
        self.assertIn("ask_user", spy.executed)

    def test_default_agent_loop_continues_past_eight_tool_steps(self):
        client = LongToolThenDoneClient(tool_turns=9)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="读取多个文件后完成",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.turns_used, 10)
        self.assertEqual(client.calls, 10)
        self.assertGreater(result.turns_used, 8)

    def test_explicit_loop_safety_limit_still_stops_after_configured_step_count(self):
        client = LongToolThenDoneClient(tool_turns=2)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            max_turns=1,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="读取多个文件但安全限制为一步",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "max_turns")
        self.assertEqual(result.turns_used, 1)
        self.assertEqual(result.transition.metadata.get("loop_safety_limit"), 1)
        self.assertEqual(result.transition.metadata.get("turns_used"), 1)
        self.assertEqual(client.calls, 1)

    def test_projection_failure_does_not_flip_tool_success(self):
        transcript_store = TranscriptStore(self.workspace)
        self.tools.projection_db.upsert_tool_result_projection = lambda **_: (_ for _ in ()).throw(
            RuntimeError("db down")
        )
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertTrue(result.session.turns[-1].observations[-1].success)

    def test_initialize_session_injects_profile_mode_and_harness_once(self):
        transcript_store = TranscriptStore(self.workspace)
        default_extensions = build_product_agent_application(self.tools)
        engine = QueryEngine(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
            extension_manager=default_extensions.extension_manager,
        )
        session = Session()

        current_mode = engine.initialize_session(
            session, "build", workflow_state="chat", user_text="build the project"
        )
        self.assertEqual(current_mode, "build")
        first_messages = list(session.messages)
        self.assertGreaterEqual(len(first_messages), 2)
        self.assertTrue(any(message.kind == "workflow_prompt" for message in first_messages))

        current_mode = engine.initialize_session(
            session, "build", workflow_state="chat", user_text="build the project"
        )
        self.assertEqual(current_mode, "build")
        self.assertEqual(len(session.messages), len(first_messages))

    def test_workflow_prompt_dedupe_ignores_non_workflow_prompt_kinds(self):
        transcript_store = TranscriptStore(self.workspace)
        default_extensions = build_product_agent_application(self.tools)
        engine = QueryEngine(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
            extension_manager=default_extensions.extension_manager,
        )
        session = Session()
        session.add_system_message(
            "unrelated system prompt",
            kind="system_note",
            metadata={
                "mode_name": "build",
                "discipline_label": "lite_spec_tdd",
            },
        )

        current_mode = engine.initialize_session(
            session, "build", workflow_state="chat", user_text="build the project"
        )
        prompt_messages = [
            message
            for message in session.messages
            if message.kind in ("system_note", "workflow_prompt")
        ]
        workflow_prompt_messages = [
            message for message in session.messages if message.kind == "workflow_prompt"
        ]

        self.assertEqual(current_mode, "build")
        self.assertEqual(len(prompt_messages), 2)
        self.assertEqual(len(workflow_prompt_messages), 1)

    def test_query_engine_writes_tool_presentation_into_tool_call_event(self):
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        events = transcript_store.load_events(session.session_id)
        tool_call_events = [item for item in events if item["type"] == "tool_call"]
        self.assertTrue(tool_call_events)
        presentation = tool_call_events[0]["payload"]["presentation"]
        self.assertIn("tool_label", presentation)
        self.assertIn("progress_renderer_key", presentation)

    def test_query_engine_emits_explicit_operation_events_for_tool_execution(self):
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        started = [item for item in events if item["type"] == "operation_started"]
        finished = [item for item in events if item["type"] == "operation_finished"]
        started_ids = [item["payload"].get("operation_id") for item in started]
        finished_ids = [item["payload"].get("operation_id") for item in finished]
        self.assertIn("tool:call-read-demo", started_ids)
        self.assertIn("tool:call-read-demo", finished_ids)

    def test_query_engine_emits_core_runtime_operation_events(self):
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        started = [item for item in events if item["type"] == "operation_started"]
        finished = [item for item in events if item["type"] == "operation_finished"]
        started_by_kind = {}
        finished_by_kind = {}
        for item in started:
            started_by_kind.setdefault(item["payload"].get("kind"), []).append(item["payload"])
        for item in finished:
            finished_by_kind.setdefault(item["payload"].get("kind"), []).append(item["payload"])

        self.assertIn("context_assembly", started_by_kind)
        self.assertIn("context_assembly", finished_by_kind)
        self.assertIn("provider_request", started_by_kind)
        self.assertIn("provider_request", finished_by_kind)
        self.assertIn("save_point", started_by_kind)
        self.assertIn("save_point", finished_by_kind)

        context_start = started_by_kind["context_assembly"][0]
        context_finish = finished_by_kind["context_assembly"][0]
        provider_start = started_by_kind["provider_request"][0]
        provider_finish = finished_by_kind["provider_request"][0]
        savepoint_start = started_by_kind["save_point"][-1]
        savepoint_finish = finished_by_kind["save_point"][-1]

        self.assertTrue(context_start["operation_id"].startswith("context:"))
        self.assertTrue(context_finish["operation_id"].startswith("context:"))
        self.assertEqual(context_start["metadata"]["mode_name"], "build")
        self.assertIn("approx_tokens", context_finish["result"])
        self.assertTrue(provider_start["operation_id"].startswith("provider:"))
        self.assertTrue(provider_finish["operation_id"].startswith("provider:"))
        self.assertEqual(provider_start["metadata"]["mode_name"], "build")
        self.assertIn("finish_reason", provider_finish["result"])
        self.assertTrue(savepoint_start["operation_id"].startswith("savepoint:"))
        self.assertTrue(savepoint_finish["operation_id"].startswith("savepoint:"))
        self.assertEqual(savepoint_finish["result"]["reason"], "completed")

    def test_provider_request_consumes_turn_snapshot_and_records_safe_metadata(self):
        transcript_store = TranscriptStore(self.workspace)
        client = SnapshotInspectingClient()
        session = Session()
        transcript_store.append_event(
            session.session_id,
            "runtime_configured",
            {
                "reason": "test",
                "model_profile": {
                    "name": "reduced-local-model",
                    "source_type": "configured",
                    "source_id": "llm",
                    "metadata": {"base_url": "http://localhost:11434/v1"},
                },
                "resource_revision": {
                    "revision": 7,
                    "event_id": "evt-resource-7",
                    "reason": "test",
                },
            },
        )
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
            max_turns=1,
        )
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="检查项目",
            stream=False,
            initial_mode="build",
            workflow_state="chat",
            session=session,
        )

        snapshot = engine.last_turn_snapshot()
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(len(client.messages), 1)
        self.assertIsNotNone(snapshot)
        self.assertEqual(client.messages[0], snapshot.messages)
        self.assertEqual(client.tools[0], snapshot.tool_schemas)
        self.assertIn("read_file", snapshot.active_tool_names)
        self.assertEqual(snapshot.model_profile["name"], "reduced-local-model")
        self.assertEqual(snapshot.resource_revision["revision"], 7)

        events = transcript_store.load_events(session.session_id)
        started = [
            item["payload"]
            for item in events
            if item["type"] == "operation_started"
            and item["payload"].get("kind") == "provider_request"
        ]
        finished = [
            item["payload"]
            for item in events
            if item["type"] == "operation_finished"
            and item["payload"].get("kind") == "provider_request"
        ]

        metadata = started[0]["metadata"]
        result_payload = finished[0]["result"]

        self.assertTrue(metadata["turn_snapshot"]["snapshot_id"].startswith("ts-"))
        self.assertIn("snapshot_id", metadata["turn_snapshot"])
        self.assertIn("mode_name", metadata["turn_snapshot"])
        self.assertIn("workflow_state", metadata["turn_snapshot"])
        self.assertIn("active_tool_names", metadata["turn_snapshot"])
        self.assertEqual(
            metadata["turn_snapshot"]["active_tool_names"],
            sorted(snapshot.active_tool_names),
        )
        self.assertIn("registered_tool_names", metadata["turn_snapshot"])
        self.assertIn("read_file", metadata["turn_snapshot"]["registered_tool_names"])
        self.assertIn("capability_counts", metadata["turn_snapshot"])
        self.assertEqual(metadata["turn_snapshot"]["resource_revision"]["revision"], 7)
        self.assertEqual(
            result_payload["turn_snapshot"]["snapshot_id"],
            metadata["turn_snapshot"]["snapshot_id"],
        )
        self.assertNotIn("messages", metadata["turn_snapshot"])
        self.assertNotIn("tool_schemas", metadata["turn_snapshot"])
        self.assertNotIn("prompt", metadata["turn_snapshot"])
        self.assertNotIn("api_key", repr(metadata["turn_snapshot"]).lower())

    def test_turn_snapshot_records_safe_local_skill_prompt_unit_metadata(self):
        skill_dir = os.path.join(self.workspace, ".embedagent", "skills", "review")
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                "name: code-review\n"
                "description: Review local C changes.\n"
                "---\n"
                "# Secret Body\n"
            )
        self.tools.reload_resources(reason="test")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=SnapshotInspectingClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
            max_turns=1,
        )
        session = Session()

        result = engine.submit_user_turn(
            user_text="inspect",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        snapshot_events = [
            event
            for event in transcript_store.load_events(session.session_id)
            if event["type"] == "operation_started"
            and (event.get("payload") or {}).get("kind") == "provider_request"
        ]
        metadata = (snapshot_events[0].get("payload") or {}).get("metadata") or {}
        prompt_units = metadata["turn_snapshot"]["prompt_units"]

        self.assertEqual(
            prompt_units,
            [
                {
                    "kind": "local_skill_listing",
                    "visible_skill_names": ["code-review"],
                    "visible_skill_count": 1,
                }
            ],
        )
        self.assertNotIn("Secret Body", str(metadata))

    def test_resource_reload_updates_only_future_prompt_unit_snapshots(self):
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=SnapshotInspectingClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
            max_turns=1,
        )
        session = Session()

        first = engine.submit_user_turn(
            user_text="first",
            stream=False,
            initial_mode="build",
            session=session,
        )

        skill_dir = os.path.join(self.workspace, ".embedagent", "skills", "review")
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                "name: code-review\n"
                "description: Review local C changes.\n"
                "---\n"
                "# Reloaded Secret Body\n"
            )
        self.tools.reload_resources(reason="test")

        second = engine.submit_user_turn(
            user_text="second",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(first.transition.reason, "completed")
        self.assertEqual(second.transition.reason, "completed")
        snapshot_events = [
            event
            for event in transcript_store.load_events(session.session_id)
            if event["type"] == "operation_started"
            and (event.get("payload") or {}).get("kind") == "provider_request"
        ]
        first_metadata = (snapshot_events[0].get("payload") or {}).get("metadata") or {}
        second_metadata = (snapshot_events[1].get("payload") or {}).get("metadata") or {}

        self.assertEqual(first_metadata["turn_snapshot"]["prompt_units"], [])
        self.assertEqual(
            second_metadata["turn_snapshot"]["prompt_units"],
            [
                {
                    "kind": "local_skill_listing",
                    "visible_skill_names": ["code-review"],
                    "visible_skill_count": 1,
                }
            ],
        )
        self.assertNotIn("Reloaded Secret Body", str(first_metadata))
        self.assertNotIn("Reloaded Secret Body", str(second_metadata))

    def test_query_engine_emits_turn_operation_lifecycle(self):
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        started = [
            item["payload"]
            for item in events
            if item["type"] == "operation_started" and item["payload"].get("kind") == "turn"
        ]
        finished = [
            item["payload"]
            for item in events
            if item["type"] == "operation_finished" and item["payload"].get("kind") == "turn"
        ]
        self.assertEqual(len(started), 1)
        self.assertEqual(len(finished), 1)
        self.assertTrue(started[0]["operation_id"].startswith("turn:"))
        self.assertEqual(finished[0]["operation_id"], started[0]["operation_id"])
        self.assertEqual(finished[0]["result"]["transition_reason"], "completed")

    def test_query_engine_user_turn_uses_kernel_turn_frame(self):
        engine = QueryEngine(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        spy_kernel = SpyKernel(delegate=engine.kernel)
        engine.kernel = spy_kernel
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual([item["source"] for item in spy_kernel.started], ["user"])
        self.assertEqual([item["source"] for item in spy_kernel.finished], ["user"])
        self.assertEqual(spy_kernel.finished[0]["reason"], "completed")
        self.assertEqual(spy_kernel.interrupted, [])

    def test_query_engine_command_turn_uses_kernel_turn_frame(self):
        engine = QueryEngine(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        spy_kernel = SpyKernel(delegate=engine.kernel)
        engine.kernel = spy_kernel
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result, observation = engine.submit_command_turn(
            user_text="/read",
            action=Action("read_file", {"path": "src/demo.c"}, "cmd-read"),
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertTrue(observation.success)
        self.assertEqual([item["source"] for item in spy_kernel.started], ["command"])
        self.assertEqual([item["source"] for item in spy_kernel.finished], ["command"])
        self.assertEqual(spy_kernel.finished[0]["reason"], "completed")
        self.assertEqual(spy_kernel.interrupted, [])

    def test_query_engine_resume_turn_uses_kernel_turn_frame(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        first = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )
        self.assertEqual(first.transition.reason, "user_input_wait")
        spy_kernel = SpyKernel(delegate=engine.kernel)
        engine.kernel = spy_kernel

        resumed = engine.resume_interaction(
            session=session,
            initial_mode="spec",
            stream=False,
            interaction_resolution={
                "answer": "切到 debug 模式继续排查",
                "selected_index": 1,
                "selected_mode": "debug",
                "selected_option_text": "切到 debug 模式继续排查",
            },
        )

        self.assertEqual(resumed.transition.reason, "completed")
        self.assertEqual([item["source"] for item in spy_kernel.started], ["resume"])
        self.assertEqual([item["source"] for item in spy_kernel.finished], ["resume"])
        self.assertEqual(spy_kernel.finished[0]["reason"], "completed")
        self.assertEqual(spy_kernel.interrupted, [])

    def test_tool_result_store_failure_degrades_without_breaking_tool_pairing(self):
        transcript_store = TranscriptStore(self.workspace)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n%s\n}\n" % ("x" * 2500))
        self.tools.tool_result_store.write_text = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("disk down")
        )
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        observation = result.session.turns[-1].observations[-1]
        self.assertTrue(observation.success)
        self.assertNotIn("content_stored_path", observation.data)
        warnings = observation.data.get("tool_result_storage_warnings") or []
        self.assertEqual(len(warnings), 1)
        self.assertIn("disk down", warnings[0].get("error", ""))
        events = transcript_store.load_events(session.session_id)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertEqual(len(tool_results), 1)
        self.assertEqual(tool_results[0]["payload"]["call_id"], "call-read-demo")

    def test_query_engine_accepts_windows_unsafe_tool_call_ids_for_large_results(self):
        transcript_store = TranscriptStore(self.workspace)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n%s\n}\n" % ("x" * 2500))
        engine = QueryEngine(
            client=UnsafeToolCallIdClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        observation = result.session.turns[-1].observations[-1]
        self.assertTrue(observation.success)
        stored_path = str(observation.data.get("content_stored_path") or "")
        self.assertTrue(stored_path)
        self.assertNotIn("read_file:1", stored_path)
        self.assertNotIn(":", stored_path)
        events = transcript_store.load_events(session.session_id)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertEqual(tool_results[0]["payload"]["call_id"], "read_file:1")

    def test_context_manager_repairs_dangling_tool_calls_before_next_llm_request(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        session.add_user_message("先读文件", turn_id="t-old", message_id="m-user-old")
        session.begin_step(step_id="s-old")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[Action("read_file", {"path": "src/demo.c"}, "read_file:1")],
                finish_reason="tool_calls",
            ),
            message_id="m-assistant-old",
            turn_id="t-old",
            step_id="s-old",
        )
        client = InspectingDoneClient()
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
        )
        result = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(len(client.messages), 1)
        tool_messages = [
            item
            for item in client.messages[0]
            if item.get("role") == "tool" and item.get("tool_call_id") == "read_file:1"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("missing_tool_result", tool_messages[0].get("content", ""))

    def test_context_manager_exposes_intelligence_and_boundary(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        session.add_user_message("请检查工程")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[Action("read_file", {"path": "src/demo.c"}, "read-1")],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action("read_file", {"path": "src/demo.c"}, "read-1"),
            Observation(
                tool_name="read_file",
                success=True,
                error=None,
                data={
                    "path": "src/demo.c",
                    "content": "int demo(void) {\n    return 0;\n}\n",
                    "content_stored_path": ".embedagent/memory/sessions/sess-context/tool-results/read-demo/content.txt",
                },
            ),
        )
        apply_session_event(
            session,
            "compact_boundary",
            {
                "boundary_id": "cb-context-manager",
                "summary_text": "Earlier work summary",
                "compacted_turn_count": 1,
                "mode_name": "build",
                "metadata": {"test": True},
            },
        )
        manager = ContextManager(
            intelligence_broker=WorkspaceIntelligenceBroker(),
        )
        result = manager.build_messages(
            session,
            "build",
            tools=self.tools,
            workflow_state="chat",
        )
        rendered = "\n".join(str(item.get("content") or "") for item in result.messages)
        self.assertIn("Earlier work summary", result.summary_message)
        self.assertIn("工程情报", rendered)
        self.assertGreaterEqual(result.analysis.get("replacement_count") or 0, 1)

    def test_context_manager_preserves_tool_response_pairs_for_recent_tool_calls(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        session.add_user_message("继续分析")
        actions = [
            Action("list_dir", {"path": "src"}, "call-list-1"),
            Action("read_file", {"path": "src/demo.c"}, "call-read-1"),
            Action("read_file", {"path": "src/demo.c"}, "call-read-2"),
        ]
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=actions,
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            actions[0],
            Observation(
                tool_name="list_dir",
                success=True,
                error=None,
                data={
                    "path": "src",
                    "entries": [{"name": "demo.c", "path": "src/demo.c", "type": "file"}],
                    "entries_stored_path": ".embedagent/memory/sessions/sess-context/tool-results/list-src/entries.json",
                },
            ),
        )
        session.add_observation(
            actions[1],
            Observation(
                tool_name="read_file",
                success=True,
                error=None,
                data={
                    "path": "src/demo.c",
                    "content": "int demo(void) {\n    return 0;\n}\n",
                    "content_stored_path": ".embedagent/memory/sessions/sess-context/tool-results/read-1/content.txt",
                },
            ),
        )
        session.add_observation(
            actions[2],
            Observation(
                tool_name="read_file",
                success=True,
                error=None,
                data={
                    "path": "src/demo.c",
                    "content": "int demo(void) {\n    return 0;\n}\n",
                    "content_stored_path": ".embedagent/memory/sessions/sess-context/tool-results/read-2/content.txt",
                },
            ),
        )

        result = ContextManager().build_messages(session, "build")

        assistant_messages = [
            item
            for item in result.messages
            if item.get("role") == "assistant" and item.get("tool_calls")
        ]
        self.assertEqual(len(assistant_messages), 1)
        expected_call_ids = [item["id"] for item in assistant_messages[0]["tool_calls"]]
        tool_call_ids = [
            item.get("tool_call_id") for item in result.messages if item.get("role") == "tool"
        ]
        self.assertEqual(tool_call_ids, expected_call_ids)
        rendered = "\n".join(str(item.get("content") or "") for item in result.messages)
        self.assertNotIn("Tool result replaced:", rendered)

    def test_ctags_provider_parses_symbol_entries(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write('demo\tsrc/demo.c\t/^int demo(void) {$/;"\tf\n')
            handle.write('helper\tsrc/demo.c\t/^static int helper(int x) {$/;"\tf\n')
        provider = CtagsProvider()
        evidence = provider.collect(Session(), "build", self.tools, None)
        self.assertEqual(len(evidence), 1)
        self.assertIn("demo", evidence[0].content)
        self.assertIn("src/demo.c", evidence[0].content)
        self.assertTrue(evidence[0].metadata.get("parsed_tags"))

    def test_broker_renders_symbol_evidence_for_code_mode(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write('demo\tsrc/demo.c\t/^int demo(void) {$/;"\tf\n')
        broker = WorkspaceIntelligenceBroker()
        message = broker.render_system_message(
            Session(), "build", self.tools, None, limit=5, char_limit=2000
        )
        self.assertIn("demo", message)
        self.assertIn("src/demo.c", message)

    def test_git_state_provider_uses_session_observations_without_executing_tools(self):
        class ForbiddenExecuteTools(object):
            def execute(self, name, arguments):
                raise AssertionError("git intelligence must not execute tools")

        session = Session()
        action = Action("git_status", {"path": "."}, "git-1")
        session.add_user_message("check git")
        session.record_tool_call(action)
        session.add_observation(
            action,
            Observation(
                "git_status",
                True,
                "",
                {
                    "branch": "main",
                    "entries": [
                        {"status": " M", "path": "src/demo.c"},
                        {"status": "??", "path": "src/new.c"},
                    ],
                },
            ),
        )

        evidence = GitStateProvider().collect(session, "build", ForbiddenExecuteTools(), None)

        self.assertEqual(len(evidence), 1)
        self.assertIn("main", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("dirty_count"), 2)

    def test_ctags_provider_prioritizes_recent_working_set_files(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write('other_symbol\tsrc/other.c\t/^int other_symbol(void) {$/;"\tf\n')
            handle.write('demo\tsrc/demo.c\t/^int demo(void) {$/;"\tf\n')
        session = Session()
        session.add_user_message("改 demo")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[
                    Action(
                        "edit_file",
                        {"path": "src/demo.c", "old_text": "0", "new_text": "1"},
                        "edit-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-1"),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        provider = CtagsProvider()
        evidence = provider.collect(session, "build", self.tools, None)
        self.assertTrue(
            evidence[0].content.index("demo") < evidence[0].content.index("other_symbol")
        )

    def test_diagnostics_provider_prioritizes_focused_file(self):
        session = Session()
        session.add_user_message("修复 demo")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[
                    Action(
                        "edit_file",
                        {"path": "src/demo.c", "old_text": "0", "new_text": "1"},
                        "edit-demo",
                    )
                ],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action(
                "edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-demo"
            ),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        session.add_observation(
            Action("run_recipe", {"recipe_id": "cmake.build.default"}, "compile-1"),
            Observation(
                "run_recipe",
                False,
                "compile failed",
                {
                    "recipe_action": "build",
                    "diagnostics": [
                        {"file": "src/other.c", "line": 3, "column": 1, "message": "other failure"}
                    ],
                },
            ),
        )
        session.add_observation(
            Action("run_recipe", {"recipe_id": "custom.tidy"}, "tidy-1"),
            Observation(
                "run_recipe",
                False,
                "tidy failed",
                {
                    "recipe_action": "tidy",
                    "diagnostics": [
                        {"file": "src/demo.c", "line": 5, "column": 2, "message": "demo warning"}
                    ],
                },
            ),
        )
        provider = DiagnosticsProvider()
        evidence = provider.collect(session, "build", self.tools, None)
        self.assertGreaterEqual(len(evidence), 2)
        self.assertIn("src/demo.c", evidence[0].content)

    def test_diagnostics_provider_aggregates_hotspots_by_file(self):
        session = Session()
        session.add_user_message("继续修复 demo")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[
                    Action(
                        "edit_file",
                        {"path": "src/demo.c", "old_text": "0", "new_text": "2"},
                        "edit-demo-2",
                    )
                ],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action(
                "edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "2"}, "edit-demo-2"
            ),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        session.add_observation(
            Action("run_recipe", {"recipe_id": "cmake.build.default"}, "compile-2"),
            Observation(
                "run_recipe",
                False,
                "compile failed",
                {
                    "recipe_action": "build",
                    "diagnostics": [
                        {"file": "src/demo.c", "line": 7, "column": 3, "message": "compile failure"}
                    ],
                },
            ),
        )
        session.add_observation(
            Action("run_recipe", {"recipe_id": "custom.tidy"}, "tidy-2"),
            Observation(
                "run_recipe",
                False,
                "tidy failed",
                {
                    "recipe_action": "tidy",
                    "diagnostics": [
                        {"file": "src/demo.c", "line": 9, "column": 2, "message": "tidy warning"}
                    ],
                },
            ),
        )
        session.add_observation(
            Action("run_recipe", {"recipe_id": "custom.analyze"}, "analyzer-2"),
            Observation(
                "run_recipe",
                False,
                "analyzer failed",
                {
                    "recipe_action": "analyze",
                    "diagnostics": [
                        {"file": "src/other.c", "line": 4, "column": 1, "message": "other issue"}
                    ],
                },
            ),
        )
        provider = DiagnosticsProvider()
        evidence = provider.collect(session, "debug", self.tools, None)
        self.assertGreaterEqual(len(evidence), 2)
        self.assertIn("src/demo.c", evidence[0].content)
        self.assertIn("2 条", evidence[0].content)
        self.assertIn("build", evidence[0].content)
        self.assertIn("tidy", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("diagnostic_count"), 2)
        self.assertEqual(evidence[0].metadata.get("path"), "src/demo.c")
        self.assertEqual(evidence[0].metadata.get("group_kind"), "path_hotspot")

    def test_diagnostics_provider_aggregates_quality_gate_and_pathless_failures(self):
        session = Session()
        session.add_user_message("验证当前质量门")
        session.add_observation(
            Action("run_recipe", {"recipe_id": "cmake.test.default"}, "tests-1"),
            Observation(
                "run_recipe",
                False,
                "tests failed",
                {
                    "recipe_action": "test",
                    "test_summary": {"total": 5, "passed": 3, "failed": 2, "skipped": 0},
                },
            ),
        )
        session.add_observation(
            Action("run_recipe", {"recipe_id": "coverage.default"}, "coverage-1"),
            Observation(
                "run_recipe",
                True,
                None,
                {"recipe_action": "coverage", "coverage_summary": {"line_coverage": 62.5}},
            ),
        )
        session.add_observation(
            Action("report_quality_v2", {}, "quality-1"),
            Observation(
                "report_quality_v2",
                True,
                None,
                {
                    "passed": False,
                    "error_count": 0,
                    "warning_count": 0,
                    "test_failures": 2,
                    "line_coverage": 62.5,
                    "min_line_coverage": 80.0,
                    "reasons": ["存在 2 个失败测试。", "行覆盖率 62.50% 低于阈值 80.00%。"],
                },
            ),
        )
        provider = DiagnosticsProvider()
        evidence = provider.collect(session, "verify", self.tools, None)
        self.assertGreaterEqual(len(evidence), 1)
        self.assertEqual(evidence[0].title, "Quality Gate Summary")
        self.assertIn("质量门", evidence[0].content)
        self.assertIn("test", evidence[0].content)
        self.assertIn("coverage", evidence[0].content)
        self.assertIn("report_quality_v2", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("group_kind"), "quality_gate_summary")
        self.assertEqual(
            set(evidence[0].metadata.get("tool_names") or []), {"run_recipe", "report_quality_v2"}
        )

    def test_diagnostics_provider_accepts_run_recipe_and_report_quality_v2(self):
        session = Session()
        session.add_user_message("验证 V2 质量门")
        session.add_observation(
            Action("run_recipe", {"recipe_id": "detected:test"}, "recipe-1"),
            Observation(
                "run_recipe",
                False,
                "recipe failed",
                {
                    "recipe_id": "detected:test",
                    "diagnostics": [
                        {"file": "src/demo.c", "line": 9, "column": 2, "message": "demo failure"}
                    ],
                },
            ),
        )
        session.add_observation(
            Action("report_quality_v2", {}, "quality-v2-1"),
            Observation(
                "report_quality_v2",
                True,
                None,
                {"passed": False, "error_count": 1, "warning_count": 0, "test_failures": 2},
            ),
        )
        provider = DiagnosticsProvider()
        evidence = provider.collect(session, "verify", self.tools, None)
        self.assertGreaterEqual(len(evidence), 1)
        self.assertTrue(
            any(
                "run_recipe" in item.content or "report_quality_v2" in item.content
                for item in evidence
            )
        )

    def test_diagnostics_provider_classifies_evidence_by_payload_shape_not_tool_name(self):
        session = Session()
        session.add_user_message("验证自定义 workflow 质量门")
        session.add_observation(
            Action("custom_verify_runner", {"recipe_id": "test"}, "custom-tests"),
            Observation(
                "custom_verify_runner",
                False,
                "tests failed",
                {
                    "recipe_action": "test",
                    "test_summary": {"total": 2, "passed": 1, "failed": 1, "skipped": 0},
                },
            ),
        )
        session.add_observation(
            Action("custom_quality_gate", {}, "custom-quality"),
            Observation(
                "custom_quality_gate",
                True,
                None,
                {
                    "passed": False,
                    "error_count": 0,
                    "warning_count": 0,
                    "test_failures": 1,
                },
            ),
        )
        provider = DiagnosticsProvider()
        evidence = provider.collect(session, "verify", self.tools, None)

        self.assertGreaterEqual(len(evidence), 1)
        self.assertEqual(evidence[0].title, "Quality Gate Summary")
        self.assertIn("test", evidence[0].content)
        self.assertIn("custom_quality_gate", evidence[0].content)
        self.assertEqual(
            set(evidence[0].metadata.get("tool_names") or []),
            {"custom_verify_runner", "custom_quality_gate"},
        )

    def test_recipe_provider_prefers_verify_tools_in_verify_mode(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                "["
                + '{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build","cwd":"."},'
                + '{"id":"custom.test","tool_name":"run_recipe","recipe_action":"test","label":"Custom Test","command":"cmd /c echo test","cwd":"."},'
                + '{"id":"custom.tidy","tool_name":"run_recipe","recipe_action":"tidy","label":"Custom Tidy","command":"cmd /c echo tidy","cwd":"."}'
                + "]"
            )
        provider = RecipeProvider()
        evidence = provider.collect(Session(), "verify", self.tools, None)
        self.assertIn("custom.test", evidence[0].content)
        self.assertIn("custom.tidy", evidence[0].content)
        self.assertIn("[test]", evidence[0].content)

    def test_recipe_provider_prefers_project_recipe_over_detected_in_build_mode(self):
        register_default_c_workflow_tools(self.tools, self.workspace)
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                "["
                + '{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build","cwd":"."}'
                + "]"
            )
        provider = RecipeProvider()
        evidence = provider.collect(Session(), "build", self.tools, None)
        self.assertIn("custom.build", evidence[0].content)
        self.assertIn("cmake.build.default", evidence[0].content)
        self.assertLess(
            evidence[0].content.index("custom.build"),
            evidence[0].content.index("cmake.build.default"),
        )

    def test_recipe_provider_prefers_history_test_recipe_over_detected_in_verify_mode(self):
        register_default_c_workflow_tools(self.tools, self.workspace)
        history_root = os.path.join(self.workspace, ".embedagent", "memory", "project")
        os.makedirs(history_root, exist_ok=True)
        with open(
            os.path.join(history_root, "command-recipes.json"), "w", encoding="utf-8"
        ) as handle:
            handle.write(
                "["
                + '{"tool_name":"run_recipe","recipe_action":"test","command":"python -m unittest","cwd":"."}'
                + "]"
            )
        provider = RecipeProvider()
        evidence = provider.collect(Session(), "verify", self.tools, None)
        self.assertIn("history.test.1", evidence[0].content)
        self.assertIn("cmake.test.default", evidence[0].content)
        self.assertLess(
            evidence[0].content.index("history.test.1"),
            evidence[0].content.index("cmake.test.default"),
        )

    def test_llsp_provider_uses_backend_contract(self):
        provider = LlspProvider(backend=FakeLlspBackend())
        evidence = provider.collect(Session(), "build", self.tools, None)
        self.assertEqual(len(evidence), 1)
        self.assertIn("llsp symbol demo", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("backend"), "fake")

    def test_llsp_provider_uses_default_file_backend_and_prioritizes_focus_path(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent", "llsp"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "llsp", "evidence.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                {
                    "items": [
                        {
                            "path": "src/other.c",
                            "symbol": "other_symbol",
                            "kind": "function",
                            "priority": 60,
                        },
                        {
                            "path": "src/demo.c",
                            "symbol": "demo_symbol",
                            "kind": "function",
                            "priority": 60,
                        },
                    ]
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        session = Session()
        session.add_user_message("修 demo")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[
                    Action(
                        "edit_file",
                        {"path": "src/demo.c", "old_text": "0", "new_text": "1"},
                        "edit-demo-llsp",
                    )
                ],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action(
                "edit_file",
                {"path": "src/demo.c", "old_text": "0", "new_text": "1"},
                "edit-demo-llsp",
            ),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        provider = LlspProvider()
        evidence = provider.collect(session, "build", self.tools, None)
        self.assertGreaterEqual(len(evidence), 1)
        self.assertIn("demo_symbol", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("path"), "src/demo.c")
        self.assertTrue(evidence[0].metadata.get("focus_match"))
        self.assertEqual(evidence[0].metadata.get("source"), "llsp_file")

    def test_llsp_provider_silently_degrades_when_default_file_is_missing(self):
        provider = LlspProvider()
        evidence = provider.collect(Session(), "build", self.tools, None)
        self.assertEqual(evidence, [])

    def test_query_engine_waits_for_user_input_and_can_resume(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        first = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )
        self.assertEqual(first.transition.reason, "user_input_wait")
        self.assertIsNotNone(first.pending_interaction)
        resumed = engine.resume_interaction(
            session=session,
            initial_mode="spec",
            stream=False,
            interaction_resolution={
                "answer": "切到 debug 模式继续排查",
                "selected_index": 1,
                "selected_mode": "debug",
                "selected_option_text": "切到 debug 模式继续排查",
            },
        )
        self.assertEqual(resumed.transition.reason, "completed")
        self.assertEqual(resumed.final_text, "done")
        self.assertTrue(
            any(
                "当前模式：debug" in item.content
                for item in session.messages
                if item.role == "system"
            )
        )

    def test_query_engine_waits_for_permission_and_can_resume(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        engine = QueryEngine(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        first = engine.submit_user_turn(
            user_text="写文件",
            stream=False,
            initial_mode="build",
            session=session,
            permission_handler=None,
        )
        self.assertEqual(first.transition.reason, "permission_wait")
        self.assertIsNotNone(first.pending_interaction)
        self.assertEqual(len(session.turns[-1].transitions), 1)
        resumed = engine.resume_interaction(
            session=session,
            initial_mode="build",
            stream=False,
            interaction_resolution={"approved": True},
        )
        self.assertEqual(resumed.transition.reason, "completed")
        self.assertEqual(resumed.final_text, "written")
        self.assertTrue(os.path.isfile(os.path.join(self.workspace, "src", "generated_write.c")))

    def test_permission_wait_payload_contains_execution_checkpoint_fields(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        engine = QueryEngine(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        first = engine.submit_user_turn(
            user_text="写文件",
            stream=False,
            initial_mode="build",
            session=session,
            permission_handler=None,
        )
        self.assertEqual(first.transition.reason, "permission_wait")
        payload = first.pending_interaction.request_payload
        self.assertIn("action", payload)
        self.assertIn("turn_id", payload)
        self.assertIn("step_id", payload)
        self.assertIn("interaction_id", payload)

    def test_resume_pending_permission_rechecks_mode_path_policy(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        engine = QueryEngine(
            client=SpecCodeWriteClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        target_path = os.path.join(self.workspace, "src", "spec_illegal.c")
        self.assertFalse(os.path.exists(target_path))

        first = engine.submit_user_turn(
            user_text="写 C 文件",
            stream=False,
            initial_mode="spec",
            session=session,
            permission_handler=None,
        )
        self.assertEqual(first.transition.reason, "permission_wait")

        resumed = engine.resume_interaction(
            session=session,
            initial_mode="spec",
            stream=False,
            interaction_resolution={"approved": True},
        )

        self.assertEqual(resumed.transition.reason, "completed")
        self.assertFalse(os.path.exists(target_path))
        self.assertEqual(
            session.turns[-1].observations[-1].data.get("error_kind"), "mode_path_blocked"
        )

    def test_query_engine_retries_with_compact_context_after_context_limit_error(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        for index in range(5):
            session.add_user_message("old user %s %s" % (index, "u" * 400))
            session.add_assistant_reply(
                AssistantReply(
                    content="old assistant %s %s" % (index, "a" * 300),
                    actions=[],
                    finish_reason="stop",
                )
            )
            session.add_observation(
                Action("read_file", {"path": "src/demo.c"}, "read-old-%s" % index),
                Observation(
                    "read_file",
                    True,
                    None,
                    {
                        "path": "src/demo.c",
                        "content": "int demo(void) {\n%s\n}\n" % ("x" * 1200),
                        "content_stored_path": ".embedagent/memory/sessions/sess-compact/tool-results/demo-%s/content.txt"
                        % index,
                    },
                ),
            )
        client = CompactRetryClient()
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        result = engine.submit_user_turn(
            user_text="继续分析并给我结论",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "after compact")
        self.assertEqual(client.calls, 2)
        self.assertGreater(client.message_sizes[0], client.message_sizes[1])
        self.assertTrue(
            any(item.reason == "compact_retry" for item in session.turns[-1].transitions)
        )
        self.assertIsNotNone(session.latest_compact_boundary())
        retry_transition = [
            item for item in session.turns[-1].transitions if item.reason == "compact_retry"
        ][0]
        self.assertEqual(retry_transition.metadata.get("retry_mode"), "compact")
        self.assertEqual(retry_transition.metadata.get("source_mode"), "build")

    def test_query_engine_persists_compact_boundary_event_for_restore(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        for index in range(5):
            session.add_user_message("old user %s %s" % (index, "u" * 400))
            session.add_assistant_reply(
                AssistantReply(
                    content="old assistant %s %s" % (index, "a" * 300),
                    actions=[],
                    finish_reason="stop",
                )
            )
            session.add_observation(
                Action("read_file", {"path": "src/demo.c"}, "read-old-%s" % index),
                Observation(
                    "read_file",
                    True,
                    None,
                    {
                        "path": "src/demo.c",
                        "content": "int demo(void) {\n%s\n}\n" % ("x" * 1200),
                        "content_stored_path": ".embedagent/memory/sessions/sess-compact/tool-results/demo-%s/content.txt"
                        % index,
                    },
                ),
            )
        transcript_store = TranscriptStore(self.workspace)
        client = CompactRetryClient()
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        result = engine.submit_user_turn(
            user_text="继续分析并给我结论",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        boundary = session.latest_compact_boundary()
        self.assertIsNotNone(boundary)
        self.assertTrue(boundary.preserved_head_message_id)
        self.assertTrue(boundary.preserved_tail_message_id)
        events = transcript_store.load_events(session.session_id)
        self.assertIn("compact_boundary", [item["type"] for item in events])
        compact_events = [item for item in events if item["type"] == "compact_boundary"]
        self.assertEqual(len(compact_events), 1)
        compact_payload = compact_events[0]["payload"]
        self.assertGreater(int(compact_payload["token_counts"]["approx_after"]), 0)
        self.assertEqual(
            compact_payload["message_counts"]["summarized_turns"], boundary.compacted_turn_count
        )
        self.assertEqual(
            compact_payload["message_counts"]["recent_turns"],
            len(session.turns) - boundary.compacted_turn_count,
        )
        self.assertGreater(compact_payload["message_counts"]["after"], 0)
        self.assertGreater(compact_payload["message_counts"]["before"], 0)
        self.assertEqual(
            boundary.metadata.get("selected_message_count"),
            compact_payload["message_counts"]["after"],
        )
        self.assertEqual(
            boundary.metadata.get("summarized_turns"),
            compact_payload["message_counts"]["summarized_turns"],
        )
        self.assertIn("src/demo.c", compact_payload["file_activity"]["read_files"])
        self.assertEqual(compact_payload["file_activity"]["modified_files"], [])
        self.assertTrue(compact_payload["evidence_refs"])
        self.assertEqual(compact_payload["extension_summary"], False)
        self.assertEqual(compact_payload["trigger"], "reactive_retry")
        self.assertEqual(compact_payload["phase"], "provider_retry")
        self.assertEqual(compact_payload["context_window_generation"], 1)
        self.assertEqual(boundary.metadata.get("trigger"), "reactive_retry")
        self.assertEqual(boundary.metadata.get("phase"), "provider_retry")
        self.assertEqual(boundary.metadata.get("context_window_generation"), 1)
        compacted_history_events = [item for item in events if item["type"] == "compacted_history"]
        self.assertEqual(len(compacted_history_events), 1)
        history_payload = compacted_history_events[0]["payload"]
        self.assertTrue(history_payload["checkpoint_id"].startswith("ch-"))
        self.assertEqual(history_payload["boundary_id"], boundary.boundary_id)
        self.assertEqual(history_payload["summary_text"], boundary.summary_text)
        self.assertEqual(
            history_payload["first_kept_message_id"],
            boundary.preserved_head_message_id,
        )
        self.assertEqual(history_payload["replacement_messages"][0]["role"], "system")
        self.assertIn(
            boundary.summary_text,
            history_payload["replacement_messages"][0]["content"],
        )
        self.assertEqual(history_payload["trigger"], compact_payload["trigger"])
        self.assertEqual(history_payload["phase"], compact_payload["phase"])
        self.assertEqual(history_payload["token_counts"], compact_payload["token_counts"])
        self.assertEqual(history_payload["message_counts"], compact_payload["message_counts"])

        restored = restore_events(events)
        restored_boundary = restored.session.latest_compact_boundary()
        self.assertIsNotNone(restored_boundary)
        self.assertEqual(restored_boundary.summary_text, boundary.summary_text)
        self.assertEqual(restored_boundary.compacted_turn_count, boundary.compacted_turn_count)
        self.assertEqual(
            restored_boundary.preserved_head_message_id, boundary.preserved_head_message_id
        )
        self.assertEqual(
            restored_boundary.preserved_tail_message_id, boundary.preserved_tail_message_id
        )
        self.assertEqual(restored_boundary.metadata.get("trigger"), "reactive_retry")
        self.assertEqual(restored_boundary.metadata.get("phase"), "provider_retry")
        self.assertEqual(restored_boundary.metadata.get("context_window_generation"), 1)
        restored_compaction = restored.compaction_state.to_dict()
        self.assertEqual(restored_compaction["boundary_count"], 1)
        self.assertEqual(restored_compaction["latest_boundary_id"], boundary.boundary_id)
        self.assertEqual(restored_compaction["latest_boundary"]["trigger"], "reactive_retry")
        self.assertEqual(restored_compaction["latest_boundary"]["phase"], "provider_retry")
        self.assertEqual(restored_compaction["latest_boundary"]["context_window_generation"], 1)
        self.assertIn(
            "src/demo.c",
            restored_compaction["latest_boundary"]["file_activity"]["read_files"],
        )
        restored_checkpoint = restored.session.latest_compacted_history()
        self.assertIsNotNone(restored_checkpoint)
        self.assertEqual(restored_checkpoint.boundary_id, boundary.boundary_id)
        self.assertEqual(
            restored.compaction_state.to_dict()["compacted_history"]["checkpoint_count"], 1
        )

    def test_query_engine_writes_transcript_for_completed_turn(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        event_types = [item["type"] for item in events]
        # Schema v2 normalizes message events to their role type
        self.assertIn("user", event_types)
        self.assertIn("assistant", event_types)
        self.assertIn("system", event_types)
        self.assertIn("step_started", event_types)
        self.assertIn("tool_call", event_types)
        self.assertIn("tool_result", event_types)
        loop_transitions = [item for item in events if item["type"] == "loop_transition"]
        self.assertEqual(loop_transitions[-1]["payload"]["reason"], "completed")

    def test_query_engine_persists_message_parent_ids_in_transcript(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        # Schema v2 normalizes message events to their role type
        message_events = [
            item for item in events if item["type"] in ("user", "assistant", "system", "tool")
        ]
        tool_result = [item for item in events if item["type"] == "tool_result"][0]
        self.assertEqual(
            message_events[-2]["payload"].get("parent_message_id"),
            message_events[-3]["payload"].get("message_id"),
        )
        self.assertEqual(
            tool_result["payload"].get("parent_message_id"),
            message_events[-2]["payload"].get("message_id"),
        )
        self.assertTrue(tool_result["payload"].get("message_id"))
        self.assertEqual(
            message_events[-1]["payload"].get("parent_message_id"),
            tool_result["payload"].get("message_id"),
        )

    def test_tool_commit_failure_falls_back_to_replayable_tool_result(self):
        def failing_materialize(*args, **kwargs):
            del args, kwargs
            raise OSError("commit unavailable")

        session = Session()
        transcript_store = TranscriptStore(self.workspace)
        original_materialize = self.tools.materialize_observation
        self.tools.materialize_observation = failing_materialize
        self.addCleanup(setattr, self.tools, "materialize_observation", original_materialize)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        events = transcript_store.load_events(session.session_id)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        restored = restore_events(events)

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(len(tool_results), 1)
        self.assertEqual(restored.stop_reason, "")
        self.assertEqual(restored.consumed_event_count, len(events))

    def test_tool_projection_finalizes_after_durable_observation_events(self):
        session = Session()
        transcript_store = TranscriptStore(self.workspace)
        finalized_event_types = []
        original_materialize = self.tools.materialize_observation
        original_finalize = self.tools.finalize_observation

        def materialize(session_id, action, observation):
            self.assertEqual(session_id, session.session_id)
            return PreparedToolObservation(
                observation=observation,
                replacements=[
                    {
                        "field_name": "content",
                        "stored_path": "tool-results/call-read-demo/content.txt",
                        "replacement_text": "stored",
                    }
                ],
                commit_token={"projection": "ready"},
            )

        def finalize(commit_token):
            self.assertEqual(commit_token, {"projection": "ready"})
            finalized_event_types.append(
                [item["type"] for item in transcript_store.load_events(session.session_id)]
            )

        self.tools.materialize_observation = materialize
        self.tools.finalize_observation = finalize
        self.addCleanup(setattr, self.tools, "materialize_observation", original_materialize)
        self.addCleanup(setattr, self.tools, "finalize_observation", original_finalize)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(len(finalized_event_types), 1)
        event_types_at_finalize = finalized_event_types[0]
        self.assertIn("tool_result", event_types_at_finalize)
        self.assertIn("content_replacement", event_types_at_finalize)
        self.assertLess(
            event_types_at_finalize.index("tool_result"),
            event_types_at_finalize.index("content_replacement"),
        )

    def test_query_engine_on_step_start_receives_engine_step_id(self):
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        session = Session()
        engine.initialize_session(session, "build", workflow_state="chat")
        callback_payloads = []

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
            on_step_start=lambda step_id, step_index: callback_payloads.append(
                (step_id, step_index)
            ),
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertGreaterEqual(len(callback_payloads), 1)
        self.assertEqual(callback_payloads[0][0], session.turns[-1].steps[0].step_id)
        self.assertEqual(callback_payloads[0][1], 1)

    def test_query_engine_writes_pending_interaction_events(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )
        self.assertEqual(result.transition.reason, "user_input_wait")
        events = transcript_store.load_events(session.session_id)
        event_types = [item["type"] for item in events]
        self.assertIn("pending_interaction", event_types)
        loop_transitions = [item for item in events if item["type"] == "loop_transition"]
        self.assertEqual(loop_transitions[-1]["payload"]["reason"], "user_input_wait")

    def test_query_engine_emits_pending_interaction_operation_lifecycle(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        result = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )

        self.assertEqual(result.transition.reason, "user_input_wait")
        interaction_id = result.pending_interaction.interaction_id
        events = transcript_store.load_events(session.session_id)
        pending_starts = [
            item["payload"]
            for item in events
            if item["type"] == "operation_started"
            and item["payload"].get("kind") == "pending_interaction"
        ]
        self.assertEqual(len(pending_starts), 1)
        self.assertEqual(pending_starts[0]["operation_id"], "pending:%s" % interaction_id)
        self.assertEqual(pending_starts[0]["metadata"]["kind"], "user_input")
        self.assertEqual(pending_starts[0]["metadata"]["tool_name"], "ask_user")

    def test_query_engine_permission_wait_commits_factory_pending_event(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        engine = QueryEngine(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )

        result = engine.submit_user_turn(
            user_text="写文件",
            stream=False,
            initial_mode="build",
            session=session,
            permission_handler=None,
        )

        self.assertEqual(result.transition.reason, "permission_wait")
        pending_events = [
            event
            for event in engine.transcript_store.load_events(session.session_id)
            if event["type"] == "pending_interaction"
        ]
        self.assertEqual(len(pending_events), 1)
        self.assertEqual(pending_events[0]["payload"]["kind"], "permission")
        self.assertEqual(pending_events[0]["payload"]["tool_name"], "write_file")
        self.assertEqual(
            pending_events[0]["payload"]["request_payload"]["permission"]["category"],
            "workspace_write",
        )

    def test_query_engine_user_input_wait_commits_factory_pending_event(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )

        result = engine.submit_user_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )
        self.assertTrue(result.pending_interaction.created_at)

        self.assertEqual(result.transition.reason, "user_input_wait")
        pending_events = [
            event
            for event in engine.transcript_store.load_events(session.session_id)
            if event["type"] == "pending_interaction"
        ]
        self.assertEqual(len(pending_events), 1)
        self.assertEqual(pending_events[0]["payload"]["kind"], "user_input")
        self.assertEqual(pending_events[0]["payload"]["tool_name"], "ask_user")
        self.assertEqual(
            pending_events[0]["payload"]["request_payload"]["request"]["question"], "下一步怎么做？"
        )

    def test_agent_kernel_returns_pending_intent_without_mutating_session(self):
        session = Session()
        session.add_user_message("write", turn_id="turn-1", message_id="message-user")
        session.begin_step(step_id="step-1")
        engine = QueryEngine(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        action = Action("write_file", {"path": "a.txt"}, "call-1")

        intent, transition = engine.kernel.record_pending_permission(
            session,
            action,
            {
                "tool_name": "write_file",
                "category": "workspace_write",
                "reason": "confirm",
                "details": {},
            },
            "build",
            interaction_id="interaction-1",
        )

        self.assertIsInstance(intent, EventIntent)
        self.assertEqual(intent.event_type, "pending_interaction")
        self.assertEqual(intent.payload["interaction_id"], "interaction-1")
        self.assertEqual(intent.payload["turn_id"], "turn-1")
        self.assertEqual(intent.payload["step_id"], "step-1")
        self.assertEqual(transition.reason, "permission_wait")
        self.assertEqual(intent.payload["created_at"], transition.pending_interaction.created_at)
        self.assertIsNone(session.pending_interaction)
        self.assertIsNone(session.turns[-1].pending_interaction)

    def test_agent_kernel_returns_resolution_intent_without_mutating_session(self):
        session = Session()
        session.add_user_message("write", turn_id="turn-1", message_id="message-user")
        session.begin_step(step_id="step-1")
        pending = PendingInteraction(
            interaction_id="interaction-1",
            kind="permission",
            tool_name="write_file",
            request_payload={"permission": {"category": "workspace_write"}},
        )
        session.pending_interaction = pending
        session.turns[-1].pending_interaction = pending
        engine = QueryEngine(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )

        intent = engine.kernel.resolve_pending_interaction(
            session,
            pending,
            {"approved": True},
        )

        self.assertIsInstance(intent, EventIntent)
        self.assertEqual(intent.event_type, "pending_resolution")
        self.assertEqual(intent.payload["interaction_id"], "interaction-1")
        self.assertEqual(intent.payload["resolution_payload"], {"approved": True})
        self.assertIs(session.pending_interaction, pending)
        self.assertEqual(pending.status, "pending")

    def test_query_engine_resume_uses_kernel_pending_resolution_boundary(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        engine = QueryEngine(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        first = engine.submit_user_turn(
            user_text="写文件",
            stream=False,
            initial_mode="build",
            session=session,
            permission_handler=None,
        )
        self.assertEqual(first.transition.reason, "permission_wait")
        spy_kernel = SpyKernel(delegate=engine.kernel)
        engine.kernel = spy_kernel

        resumed = engine.resume_interaction(
            session=session,
            initial_mode="build",
            stream=False,
            interaction_resolution={"approved": True},
        )

        self.assertEqual(resumed.transition.reason, "completed")
        self.assertEqual(len(spy_kernel.resolved_pending), 1)
        self.assertEqual(spy_kernel.resolved_pending[0]["kind"], "permission")
        self.assertEqual(spy_kernel.resolved_pending[0]["resolution"], {"approved": True})

    def test_query_engine_resume_pending_persists_resolution_and_tool_result(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        first = engine.submit_user_turn(
            user_text="写文件",
            stream=False,
            initial_mode="build",
            session=session,
            permission_handler=None,
        )
        self.assertEqual(first.transition.reason, "permission_wait")

        resumed = engine.resume_interaction(
            session=session,
            initial_mode="build",
            stream=False,
            interaction_resolution={"approved": True},
        )
        self.assertEqual(resumed.transition.reason, "completed")

        events = transcript_store.load_events(session.session_id)
        event_types = [item["type"] for item in events]
        self.assertIn("pending_resolution", event_types)
        pending_finishes = [
            item["payload"]
            for item in events
            if item["type"] == "operation_finished"
            and item["payload"].get("kind") == "pending_interaction"
        ]
        self.assertEqual(len(pending_finishes), 1)
        self.assertEqual(pending_finishes[0]["result"]["resolution_status"], "resolved")
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertTrue(any(item["payload"].get("call_id") == "write-1" for item in tool_results))

        restored = restore_events(events)
        self.assertIsNone(restored.session.pending_interaction)
        first_step = restored.session.turns[-1].steps[0]
        self.assertEqual(first_step.tool_calls[0].call_id, "write-1")
        self.assertEqual(first_step.tool_calls[0].status, "completed")

    def test_query_engine_persists_content_replacement_and_context_snapshot_events(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        session.add_user_message("old user " + ("u" * 400))
        session.add_assistant_reply(
            AssistantReply(
                content="old assistant " + ("a" * 300),
                actions=[],
                finish_reason="stop",
            )
        )
        session.add_observation(
            Action("read_file", {"path": "src/demo.c"}, "read-old"),
            Observation(
                "read_file",
                True,
                None,
                {
                    "path": "src/demo.c",
                    "content": "int demo(void) {\n%s\n}\n" % ("x" * 1200),
                    "content_stored_path": ".embedagent/memory/sessions/sess-existing/tool-results/read-old/content.txt",
                },
            ),
        )
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=CompactRetryClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_user_turn(
            user_text="继续分析并给我结论",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        event_types = [item["type"] for item in events]
        self.assertIn("context_snapshot", event_types)
        context_snapshot_operations = [
            item["payload"]
            for item in events
            if item["type"] == "operation_finished"
            and item["payload"].get("kind") == "context_snapshot"
        ]
        self.assertGreaterEqual(len(context_snapshot_operations), 1)
        self.assertEqual(
            context_snapshot_operations[-1]["result"]["approx_tokens"],
            session.latest_context_snapshot["approx_tokens"],
        )

    def test_query_engine_persists_and_restores_workflow_patch_events(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            extension_manager=ExtensionManager([WorkflowPatchExtension()]),
        )

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(session.workflow_state["workflow"]["id"], "patch-test")
        events = transcript_store.load_events(session.session_id)
        workflow_patch_events = [item for item in events if item["type"] == "workflow_patch"]
        self.assertEqual(len(workflow_patch_events), 1)
        workflow_patch_operations = [
            item["payload"]
            for item in events
            if item["type"] == "operation_finished"
            and item["payload"].get("kind") == "workflow_patch"
        ]
        self.assertEqual(len(workflow_patch_operations), 1)
        self.assertEqual(
            workflow_patch_operations[0]["result"]["metadata"]["source"],
            "workflow_patch_test",
        )

        restored = restore_events(events)
        self.assertEqual(restored.session.workflow_state["workflow"]["id"], "patch-test")
        self.assertEqual(
            restored.session.workflow_state["extensions"]["last_workflow_patch"]["source"],
            "workflow_patch_test",
        )

    def test_context_manager_uses_persisted_replacement_text_without_regeneration(self):
        session = Session()
        session.add_user_message("show file", turn_id="t-1", message_id="m-1")
        session.begin_step(step_id="s-1")
        session.record_content_replacement(
            {
                "message_id": "m-tool",
                "tool_call_id": "call-1",
                "tool_name": "read_file",
                "replacements": [
                    {
                        "field_name": "content",
                        "stored_path": ".embedagent/memory/sessions/s/tool-results/call-1/content.txt",
                        "replacement_text": "PERSISTED REPLACEMENT TEXT",
                    }
                ],
            }
        )
        session.messages.append(
            session.messages[-1].__class__(
                role="tool",
                content='{"success": true, "error": null, "data": {"path": "src/demo.c", "content_stored_path": ".embedagent/memory/sessions/s/tool-results/call-1/content.txt"}}',
                name="read_file",
                tool_call_id="call-1",
                message_id="m-tool",
                turn_id="t-1",
                step_id="s-1",
                kind="tool_result",
                replaced_by_refs=[".embedagent/memory/sessions/s/tool-results/call-1/content.txt"],
            )
        )
        session.turns[-1].message_end_index = len(session.messages) - 1
        rendered = (
            ContextManager(
                intelligence_broker=WorkspaceIntelligenceBroker(),
            )
            .build_messages(
                session,
                "build",
                tools=self.tools,
                workflow_state="chat",
            )
            .messages
        )
        self.assertIn("PERSISTED REPLACEMENT TEXT", json.dumps(rendered, ensure_ascii=False))

    def test_restored_session_reuses_persisted_content_replacements(self):
        transcript_store = TranscriptStore(self.workspace)
        session_id = "sess-replacements"
        transcript_store.append_event(session_id, "session_meta", {"current_mode": "build"})
        transcript_store.append_event(
            session_id,
            "message",
            {
                "role": "user",
                "content": "继续",
                "message_id": "m-user",
                "turn_id": "t-1",
                "step_id": "",
            },
        )
        transcript_store.append_event(
            session_id,
            "step_started",
            {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
        )
        transcript_store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "call-read-1",
                "tool_name": "read_file",
                "arguments": {"path": "src/demo.c"},
                "status": "started",
            },
        )
        transcript_store.append_event(
            session_id,
            "message",
            {
                "role": "tool",
                "content": '{"success": true, "error": null, "data": {"path": "src/demo.c", "content_stored_path": ".embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt"}}',
                "message_id": "m-tool",
                "parent_message_id": "m-user",
                "turn_id": "t-1",
                "step_id": "s-1",
                "tool_call_id": "call-read-1",
                "tool_name": "read_file",
                "replaced_by_refs": [
                    ".embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt"
                ],
            },
        )
        transcript_store.append_event(
            session_id,
            "content_replacement",
            {
                "message_id": "m-tool",
                "tool_call_id": "call-read-1",
                "tool_name": "read_file",
                "replacements": [
                    {
                        "field_name": "content",
                        "stored_path": ".embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt",
                        "replacement_text": "Tool result replaced: read_file src/demo.c -> .embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt",
                    }
                ],
            },
        )
        restored = restore_events(transcript_store.load_events(session_id))
        result = ContextManager(
            intelligence_broker=WorkspaceIntelligenceBroker(),
        ).build_messages(
            restored.session,
            "build",
            tools=self.tools,
            workflow_state="chat",
        )
        rendered = "\n".join(str(item.get("content") or "") for item in result.messages)
        self.assertIn(
            "Tool result replaced: read_file src/demo.c -> .embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt",
            rendered,
        )

    def test_query_engine_bootstrap_persists_existing_content_replacements(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        session.add_user_message("继续")
        session.messages.append(
            session.messages[-1].__class__(
                role="tool",
                content='{"success": true, "error": null, "data": {"path": "src/demo.c", "content_stored_path": ".embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt"}}',
                name="read_file",
                tool_call_id="call-read-1",
                message_id="m-tool",
                turn_id=session.turns[-1].turn_id,
                step_id="s-1",
                kind="tool_result",
                replaced_by_refs=[
                    ".embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt"
                ],
            )
        )
        session.turns[-1].message_end_index = len(session.messages) - 1
        session.record_content_replacement(
            {
                "message_id": "m-tool",
                "tool_call_id": "call-read-1",
                "tool_name": "read_file",
                "replacements": [
                    {
                        "field_name": "content",
                        "stored_path": ".embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt",
                        "replacement_text": "Tool result replaced: read_file src/demo.c -> .embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt",
                    }
                ],
            }
        )
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        result = engine.submit_user_turn(
            user_text="再继续",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")

        restored = restore_events(transcript_store.load_events(session.session_id))
        built = ContextManager(
            intelligence_broker=WorkspaceIntelligenceBroker(),
        ).build_messages(
            restored.session,
            "build",
            tools=self.tools,
            workflow_state="chat",
        )
        rendered = "\n".join(str(item.get("content") or "") for item in built.messages)
        self.assertIn(
            "Tool result replaced: read_file src/demo.c -> .embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt",
            rendered,
        )

    def test_query_engine_emits_interrupted_tool_result_when_stop_event_is_set_after_tool_start(
        self,
    ):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        stop_event = threading.Event()
        wrapped_tools = CountingToolRuntime(self.tools, slow_first=True)
        engine = QueryEngine(
            client=ToolClient(),
            tools=wrapped_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
            stop_event=stop_event,
            on_tool_start=lambda action: stop_event.set(),
        )
        self.assertEqual(result.transition.reason, "aborted")
        observation = session.turns[-1].observations[-1]
        self.assertFalse(observation.success)
        self.assertEqual(observation.data.get("error_kind"), "interrupted")
        events = transcript_store.load_events(session.session_id)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertEqual(
            tool_results[-1]["payload"]["observation"]["data"].get("error_kind"), "interrupted"
        )

    def test_query_engine_keeps_discarded_parallel_results_out_of_guard_stop(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ParallelReadThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            max_parallel_tools=1,
        )
        result = engine.submit_user_turn(
            user_text="并行读取",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "after discard")
        discarded = [
            item
            for item in session.turns[-1].observations
            if isinstance(item.data, dict) and item.data.get("error_kind") == "discarded"
        ]
        self.assertGreaterEqual(len(discarded), 2)
        events = transcript_store.load_events(session.session_id)
        discarded_events = [
            item
            for item in events
            if item["type"] == "tool_result"
            and isinstance(item["payload"].get("observation", {}).get("data"), dict)
            and item["payload"]["observation"]["data"].get("error_kind") == "discarded"
        ]
        self.assertGreaterEqual(len(discarded_events), 2)

    def test_query_engine_discards_not_started_parallel_actions_after_cancel(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        stop_event = threading.Event()
        wrapped_tools = CountingToolRuntime(self.tools, slow_first=True)
        engine = QueryEngine(
            client=ParallelSuccessfulReadThenDoneClient(),
            tools=wrapped_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            max_parallel_tools=1,
        )
        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
            stop_event=stop_event,
            on_tool_start=lambda action: stop_event.set(),
        )
        self.assertEqual(result.transition.reason, "aborted")
        error_kinds = [
            item.data.get("error_kind")
            for item in session.turns[-1].observations
            if isinstance(item.data, dict)
        ]
        self.assertIn("interrupted", error_kinds)
        self.assertIn("discarded", error_kinds)
        events = transcript_store.load_events(session.session_id)
        tool_call_ids = [
            item["payload"]["call_id"] for item in events if item["type"] == "tool_call"
        ]
        self.assertEqual(
            tool_call_ids, ["call-read-demo-a", "call-read-demo-b", "call-read-demo-c"]
        )

    def test_query_engine_discards_queued_parallel_actions_after_cancel_with_higher_parallelism(
        self,
    ):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        stop_event = threading.Event()
        wrapped_tools = CountingToolRuntime(self.tools, slow_read_calls=2, slow_delay_sec=0.3)
        engine = QueryEngine(
            client=ParallelSuccessfulReadThenDoneClient(),
            tools=wrapped_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            max_parallel_tools=2,
        )

        started_call_ids = []

        def trigger_cancel(action):
            started_call_ids.append(action.call_id)
            if len(started_call_ids) == 1:
                thread = threading.Thread(target=lambda: (time.sleep(0.05), stop_event.set()))
                thread.daemon = True
                thread.start()

        result = engine.submit_user_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="build",
            session=session,
            stop_event=stop_event,
            on_tool_start=trigger_cancel,
        )
        self.assertEqual(result.transition.reason, "aborted")
        self.assertEqual(started_call_ids[:2], ["call-read-demo-a", "call-read-demo-b"])
        self.assertNotIn("call-read-demo-c", started_call_ids)
        error_kinds = [
            item.data.get("error_kind")
            for item in session.turns[-1].observations
            if isinstance(item.data, dict)
        ]
        self.assertEqual(error_kinds, ["interrupted", "interrupted", "discarded"])
        events = transcript_store.load_events(session.session_id)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertEqual(
            [
                (
                    item["payload"]["call_id"],
                    item["payload"]["observation"]["data"].get("error_kind"),
                )
                for item in tool_results
            ],
            [
                ("call-read-demo-a", "interrupted"),
                ("call-read-demo-b", "interrupted"),
                ("call-read-demo-c", "discarded"),
            ],
        )

    def test_query_engine_discards_later_batches_after_parallel_discard(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")
        transcript_store = TranscriptStore(self.workspace)
        wrapped_tools = CountingToolRuntime(self.tools, slow_read_calls=2, slow_delay_sec=0.2)
        engine = QueryEngine(
            client=ParallelReadThenEditClient(),
            tools=wrapped_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            max_parallel_tools=2,
        )

        result = engine.submit_user_turn(
            user_text="读取并修改文件",
            stream=False,
            initial_mode="build",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "after retry boundary")
        with open(os.path.join(self.workspace, "src", "demo.c"), "r", encoding="utf-8") as handle:
            self.assertIn("return 0;", handle.read())
        tool_results = [
            (item.tool_name, item.data.get("error_kind") if isinstance(item.data, dict) else None)
            for item in session.turns[-1].observations
        ]
        self.assertEqual(
            tool_results,
            [
                ("read_file", "path_not_found"),
                ("read_file", None),
                ("read_file", "discarded"),
                ("edit_file", "discarded"),
            ],
        )
        events = transcript_store.load_events(session.session_id)
        transcript_results = [
            (item["payload"]["call_id"], item["payload"]["observation"]["data"].get("error_kind"))
            for item in events
            if item["type"] == "tool_result"
        ]
        self.assertEqual(
            transcript_results,
            [
                ("call-read-missing", "path_not_found"),
                ("call-read-demo-a", None),
                ("call-read-demo-b", "discarded"),
                ("call-edit-demo", "discarded"),
            ],
        )

    def test_query_engine_interrupts_long_running_command_without_waiting_for_completion(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：debug")
        transcript_store = TranscriptStore(self.workspace)
        stop_event = threading.Event()
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                [
                    {
                        "id": "slow.recipe",
                        "tool_name": "run_recipe",
                        "label": "Slow Recipe",
                        "command": _py_sleep_command(5),
                        "cwd": ".",
                    }
                ],
                handle,
                ensure_ascii=False,
                indent=2,
            )
        interrupt_tools = ToolRuntime(
            self.workspace,
            app_config=AppConfig(allow_system_tool_fallback=True),
        )
        default_extensions = build_product_agent_application(interrupt_tools)
        engine = QueryEngine(
            client=SlowCommandClient(),
            tools=interrupt_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            extension_manager=default_extensions.extension_manager,
        )

        def trigger_cancel(action):
            thread = threading.Thread(target=lambda: (time.sleep(0.2), stop_event.set()))
            thread.daemon = True
            thread.start()

        started = time.time()
        result = engine.submit_user_turn(
            user_text="运行长命令",
            stream=False,
            initial_mode="debug",
            session=session,
            stop_event=stop_event,
            on_tool_start=trigger_cancel,
        )
        elapsed = time.time() - started
        self.assertEqual(result.transition.reason, "aborted")
        self.assertLess(elapsed, 8.0)
        observation = session.turns[-1].observations[-1]
        self.assertFalse(observation.success)
        self.assertEqual(observation.data.get("error_kind"), "interrupted")
        self.assertIsNot(observation.data.get("synthetic"), True)
        events = transcript_store.load_events(session.session_id)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertEqual(
            tool_results[-1]["payload"]["observation"]["data"].get("error_kind"), "interrupted"
        )

    def test_adapter_resumes_pending_user_input(self):
        adapter = InProcessAdapter(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="继续",
            stream=False,
            wait=True,
            event_handler=lambda envelope: None,
        )
        waiting = adapter.get_session_snapshot(session_id)
        self.assertEqual(waiting["status"], "waiting_user_input")
        pending_interaction = waiting.get("pending_interaction") or {}
        self.assertEqual(pending_interaction.get("kind"), "user_input")
        request_id = str(pending_interaction.get("interaction_id") or "")
        adapter.respond_to_interaction(
            session_id,
            request_id,
            {"answers": {"answer": "切到 debug 模式继续排查"}},
        )
        final_snapshot = _wait_for_session_settled(adapter, session_id)
        self.assertEqual(final_snapshot["status"], "idle")
        self.assertEqual(final_snapshot["current_mode"], "debug")

    def test_adapter_resumes_pending_permission(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="写文件",
            stream=False,
            wait=True,
            event_handler=lambda envelope: None,
        )
        waiting = adapter.get_session_snapshot(session_id)
        self.assertEqual(waiting["status"], "waiting_permission")
        pending_interaction = waiting.get("pending_interaction") or {}
        self.assertEqual(pending_interaction.get("kind"), "permission")
        permission_id = str(pending_interaction.get("interaction_id") or "")
        adapter.respond_to_interaction(session_id, permission_id, {"decision": "accept"})
        final_snapshot = _wait_for_session_settled(adapter, session_id)
        self.assertEqual(final_snapshot["status"], "idle")
        self.assertTrue(os.path.isfile(os.path.join(self.workspace, "src", "generated_write.c")))


if __name__ == "__main__":
    unittest.main()
