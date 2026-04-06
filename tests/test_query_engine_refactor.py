import json
import os
import shutil
import sys
import threading
import time
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.context import ContextManager
from embedagent.config import AppConfig
from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.llm import ModelClientError
from embedagent.permissions import PermissionPolicy
from embedagent.query_engine import QueryEngine
from embedagent.session_restore import SessionRestorer
from embedagent.session import Action, AssistantReply, Observation, Session
from embedagent.transcript_store import TranscriptStore
from embedagent.tool_execution import partition_tool_actions
from embedagent.tools import ToolRuntime
from embedagent.workspace_intelligence import CtagsProvider, DiagnosticsProvider, LlspProvider, RecipeProvider, WorkspaceIntelligenceBroker


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
    return 'python -c "import time; time.sleep(%s)"' % seconds


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
                        arguments={"path": "notes/out.md", "content": "# hi\n", "overwrite": True},
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


class LockCheckingContextManager(ContextManager):
    def __init__(self, lock, *args, **kwargs):
        super(LockCheckingContextManager, self).__init__(*args, **kwargs)
        self._lock = lock

    def build_messages(self, session, mode_name=None, tools=None, workflow_state="chat", intelligence_broker=None, force_compact=False):
        if not self._lock.held():
            raise AssertionError("session lock not held during context build")
        return super(LockCheckingContextManager, self).build_messages(
            session,
            mode_name=mode_name,
            tools=tools,
            workflow_state=workflow_state,
            intelligence_broker=intelligence_broker,
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
                        "run_command",
                        {"command": _py_sleep_command(5), "cwd": ".", "timeout_sec": 10},
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
            should_sleep = should_sleep or (self.slow_read_calls > 0 and self.read_file_calls <= self.slow_read_calls)
            if should_sleep:
                time.sleep(self.slow_delay_sec)
        return self._base.execute(name, arguments)

    def execute_with_interrupt(self, name, arguments, stop_event=None):
        self.execute_calls += 1
        self.call_names.append((name, dict(arguments)))
        if name == "read_file":
            self.read_file_calls += 1
            should_sleep = self.slow_first and self.read_file_calls == 1
            should_sleep = should_sleep or (self.slow_read_calls > 0 and self.read_file_calls <= self.slow_read_calls)
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
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        self.tools = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_partition_tool_actions_uses_capabilities(self):
        actions = [
            Action("read_file", {"path": "src/demo.c"}, "c1"),
            Action("search_text", {"path": ".", "query": "demo"}, "c2"),
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

    def test_projection_failure_does_not_flip_tool_success(self):
        transcript_store = TranscriptStore(self.workspace)
        self.tools.projection_db.upsert_tool_result_projection = (
            lambda **_: (_ for _ in ()).throw(RuntimeError("db down"))
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
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertTrue(result.session.turns[-1].observations[-1].success)

    def test_tool_result_store_failure_degrades_without_breaking_tool_pairing(self):
        transcript_store = TranscriptStore(self.workspace)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n%s\n}\n" % ("x" * 2500))
        self.tools.tool_result_store.write_text = (
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("disk down"))
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
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
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
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
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
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
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
        result = engine.submit_turn(
            user_text="继续",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(len(client.messages), 1)
        tool_messages = [
            item for item in client.messages[0]
            if item.get("role") == "tool" and item.get("tool_call_id") == "read_file:1"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("missing_tool_result", tool_messages[0].get("content", ""))

    def test_context_manager_exposes_intelligence_and_boundary(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
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
        session.add_compact_boundary("Earlier work summary", 1, "code", {"test": True})
        manager = ContextManager()
        result = manager.build_messages(
            session,
            "code",
            tools=self.tools,
            workflow_state="chat",
            intelligence_broker=WorkspaceIntelligenceBroker(),
        )
        rendered = "\n".join(str(item.get("content") or "") for item in result.messages)
        self.assertIn("Earlier work summary", result.summary_message)
        self.assertIn("工程情报", rendered)
        self.assertGreaterEqual(result.analysis.get("replacement_count") or 0, 1)

    def test_context_manager_preserves_tool_response_pairs_for_recent_tool_calls(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        session.add_user_message("继续分析")
        actions = [
            Action("list_files", {"path": "src"}, "call-list-1"),
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
                tool_name="list_files",
                success=True,
                error=None,
                data={
                    "path": "src",
                    "files": ["src/demo.c"],
                    "files_stored_path": ".embedagent/memory/sessions/sess-context/tool-results/list-src/files.json",
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

        result = ContextManager().build_messages(session, "code")

        assistant_messages = [
            item for item in result.messages
            if item.get("role") == "assistant" and item.get("tool_calls")
        ]
        self.assertEqual(len(assistant_messages), 1)
        expected_call_ids = [item["id"] for item in assistant_messages[0]["tool_calls"]]
        tool_call_ids = [
            item.get("tool_call_id") for item in result.messages
            if item.get("role") == "tool"
        ]
        self.assertEqual(tool_call_ids, expected_call_ids)
        rendered = "\n".join(str(item.get("content") or "") for item in result.messages)
        self.assertNotIn("Tool result replaced:", rendered)

    def test_ctags_provider_parses_symbol_entries(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write("demo\tsrc/demo.c\t/^int demo(void) {$/;\"\tf\n")
            handle.write("helper\tsrc/demo.c\t/^static int helper(int x) {$/;\"\tf\n")
        provider = CtagsProvider()
        evidence = provider.collect(Session(), "code", self.tools, None)
        self.assertEqual(len(evidence), 1)
        self.assertIn("demo", evidence[0].content)
        self.assertIn("src/demo.c", evidence[0].content)
        self.assertTrue(evidence[0].metadata.get("parsed_tags"))

    def test_broker_renders_symbol_evidence_for_code_mode(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write("demo\tsrc/demo.c\t/^int demo(void) {$/;\"\tf\n")
        broker = WorkspaceIntelligenceBroker()
        message = broker.render_system_message(Session(), "code", self.tools, None, limit=5, char_limit=2000)
        self.assertIn("demo", message)
        self.assertIn("src/demo.c", message)

    def test_ctags_provider_prioritizes_recent_working_set_files(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write("other_symbol\tsrc/other.c\t/^int other_symbol(void) {$/;\"\tf\n")
            handle.write("demo\tsrc/demo.c\t/^int demo(void) {$/;\"\tf\n")
        session = Session()
        session.add_user_message("改 demo")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-1")],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-1"),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        provider = CtagsProvider()
        evidence = provider.collect(session, "code", self.tools, None)
        self.assertTrue(evidence[0].content.index("demo") < evidence[0].content.index("other_symbol"))

    def test_diagnostics_provider_prioritizes_focused_file(self):
        session = Session()
        session.add_user_message("修复 demo")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-demo")],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-demo"),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        session.add_observation(
            Action("compile_project", {}, "compile-1"),
            Observation("compile_project", False, "compile failed", {"diagnostics": [{"file": "src/other.c", "line": 3, "column": 1, "message": "other failure"}]}),
        )
        session.add_observation(
            Action("run_clang_tidy", {}, "tidy-1"),
            Observation("run_clang_tidy", False, "tidy failed", {"diagnostics": [{"file": "src/demo.c", "line": 5, "column": 2, "message": "demo warning"}]}),
        )
        provider = DiagnosticsProvider()
        evidence = provider.collect(session, "code", self.tools, None)
        self.assertGreaterEqual(len(evidence), 2)
        self.assertIn("src/demo.c", evidence[0].content)

    def test_diagnostics_provider_aggregates_hotspots_by_file(self):
        session = Session()
        session.add_user_message("继续修复 demo")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "2"}, "edit-demo-2")],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "2"}, "edit-demo-2"),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        session.add_observation(
            Action("compile_project", {}, "compile-2"),
            Observation(
                "compile_project",
                False,
                "compile failed",
                {"diagnostics": [{"file": "src/demo.c", "line": 7, "column": 3, "message": "compile failure"}]},
            ),
        )
        session.add_observation(
            Action("run_clang_tidy", {}, "tidy-2"),
            Observation(
                "run_clang_tidy",
                False,
                "tidy failed",
                {"diagnostics": [{"file": "src/demo.c", "line": 9, "column": 2, "message": "tidy warning"}]},
            ),
        )
        session.add_observation(
            Action("run_clang_analyzer", {}, "analyzer-2"),
            Observation(
                "run_clang_analyzer",
                False,
                "analyzer failed",
                {"diagnostics": [{"file": "src/other.c", "line": 4, "column": 1, "message": "other issue"}]},
            ),
        )
        provider = DiagnosticsProvider()
        evidence = provider.collect(session, "debug", self.tools, None)
        self.assertGreaterEqual(len(evidence), 2)
        self.assertIn("src/demo.c", evidence[0].content)
        self.assertIn("2 条", evidence[0].content)
        self.assertIn("compile_project", evidence[0].content)
        self.assertIn("run_clang_tidy", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("diagnostic_count"), 2)
        self.assertEqual(evidence[0].metadata.get("path"), "src/demo.c")
        self.assertEqual(evidence[0].metadata.get("group_kind"), "path_hotspot")

    def test_diagnostics_provider_aggregates_quality_gate_and_pathless_failures(self):
        session = Session()
        session.add_user_message("验证当前质量门")
        session.add_observation(
            Action("run_tests", {}, "tests-1"),
            Observation(
                "run_tests",
                False,
                "tests failed",
                {"test_summary": {"total": 5, "passed": 3, "failed": 2, "skipped": 0}},
            ),
        )
        session.add_observation(
            Action("collect_coverage", {}, "coverage-1"),
            Observation(
                "collect_coverage",
                True,
                None,
                {"coverage_summary": {"line_coverage": 62.5}},
            ),
        )
        session.add_observation(
            Action("report_quality", {}, "quality-1"),
            Observation(
                "report_quality",
                False,
                "quality gate failed",
                {
                    "passed": False,
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
        self.assertIn("run_tests", evidence[0].content)
        self.assertIn("collect_coverage", evidence[0].content)
        self.assertIn("report_quality", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("group_kind"), "quality_gate_summary")
        self.assertEqual(set(evidence[0].metadata.get("tool_names") or []), {"run_tests", "collect_coverage", "report_quality"})

    def test_recipe_provider_prefers_verify_tools_in_verify_mode(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"), "w", encoding="utf-8") as handle:
            handle.write(
                "[" +
                '{"id":"custom.build","tool_name":"compile_project","label":"Custom Build","command":"cmd /c echo build","cwd":"."},' +
                '{"id":"custom.test","tool_name":"run_tests","label":"Custom Test","command":"cmd /c echo test","cwd":"."},' +
                '{"id":"custom.tidy","tool_name":"run_clang_tidy","label":"Custom Tidy","command":"cmd /c echo tidy","cwd":"."}' +
                "]"
            )
        provider = RecipeProvider()
        evidence = provider.collect(Session(), "verify", self.tools, None)
        self.assertIn("run_tests", evidence[0].content)
        self.assertIn("run_clang_tidy", evidence[0].content)

    def test_recipe_provider_prefers_project_recipe_over_detected_in_code_mode(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"), "w", encoding="utf-8") as handle:
            handle.write(
                "[" +
                '{"id":"custom.build","tool_name":"compile_project","label":"Custom Build","command":"cmd /c echo build","cwd":"."}' +
                "]"
            )
        provider = RecipeProvider()
        evidence = provider.collect(Session(), "code", self.tools, None)
        self.assertIn("custom.build", evidence[0].content)
        self.assertIn("cmake.build.default", evidence[0].content)
        self.assertLess(evidence[0].content.index("custom.build"), evidence[0].content.index("cmake.build.default"))

    def test_recipe_provider_prefers_history_test_recipe_over_detected_in_verify_mode(self):
        history_root = os.path.join(self.workspace, ".embedagent", "memory", "project")
        os.makedirs(history_root, exist_ok=True)
        with open(os.path.join(history_root, "command-recipes.json"), "w", encoding="utf-8") as handle:
            handle.write(
                "[" +
                '{"tool_name":"run_tests","command":"python -m unittest","cwd":"."}' +
                "]"
            )
        provider = RecipeProvider()
        evidence = provider.collect(Session(), "verify", self.tools, None)
        self.assertIn("history.run_tests.1", evidence[0].content)
        self.assertIn("cmake.test.default", evidence[0].content)
        self.assertLess(evidence[0].content.index("history.run_tests.1"), evidence[0].content.index("cmake.test.default"))

    def test_llsp_provider_uses_backend_contract(self):
        provider = LlspProvider(backend=FakeLlspBackend())
        evidence = provider.collect(Session(), "code", self.tools, None)
        self.assertEqual(len(evidence), 1)
        self.assertIn("llsp symbol demo", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("backend"), "fake")

    def test_llsp_provider_uses_default_file_backend_and_prioritizes_focus_path(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent", "llsp"), exist_ok=True)
        with open(os.path.join(self.workspace, ".embedagent", "llsp", "evidence.json"), "w", encoding="utf-8") as handle:
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
                actions=[Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-demo-llsp")],
                finish_reason="tool_calls",
            )
        )
        session.add_observation(
            Action("edit_file", {"path": "src/demo.c", "old_text": "0", "new_text": "1"}, "edit-demo-llsp"),
            Observation("edit_file", True, None, {"path": "src/demo.c"}),
        )
        provider = LlspProvider()
        evidence = provider.collect(session, "code", self.tools, None)
        self.assertGreaterEqual(len(evidence), 1)
        self.assertIn("demo_symbol", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("path"), "src/demo.c")
        self.assertTrue(evidence[0].metadata.get("focus_match"))
        self.assertEqual(evidence[0].metadata.get("source"), "llsp_file")

    def test_llsp_provider_silently_degrades_when_default_file_is_missing(self):
        provider = LlspProvider()
        evidence = provider.collect(Session(), "code", self.tools, None)
        self.assertEqual(evidence, [])

    def test_query_engine_waits_for_user_input_and_can_resume(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：spec")
        engine = QueryEngine(
            client=AskThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        first = engine.submit_turn(
            user_text="继续",
            stream=False,
            initial_mode="spec",
            session=session,
            user_input_handler=None,
        )
        self.assertEqual(first.transition.reason, "user_input_wait")
        self.assertIsNotNone(first.pending_interaction)
        resumed = engine.resume_pending(
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
            any("当前模式：debug" in item.content for item in session.messages if item.role == "system")
        )

    def test_query_engine_waits_for_permission_and_can_resume(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        engine = QueryEngine(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        first = engine.submit_turn(
            user_text="写文件",
            stream=False,
            initial_mode="code",
            session=session,
            permission_handler=None,
        )
        self.assertEqual(first.transition.reason, "permission_wait")
        self.assertIsNotNone(first.pending_interaction)
        self.assertEqual(len(session.turns[-1].transitions), 1)
        resumed = engine.resume_pending(
            session=session,
            initial_mode="code",
            stream=False,
            interaction_resolution={"approved": True},
        )
        self.assertEqual(resumed.transition.reason, "completed")
        self.assertEqual(resumed.final_text, "written")
        self.assertTrue(os.path.isfile(os.path.join(self.workspace, "notes", "out.md")))

    def test_query_engine_retries_with_compact_context_after_context_limit_error(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
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
                        "content_stored_path": ".embedagent/memory/sessions/sess-compact/tool-results/demo-%s/content.txt" % index,
                    },
                ),
            )
        client = CompactRetryClient()
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        result = engine.submit_turn(
            user_text="继续分析并给我结论",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.final_text, "after compact")
        self.assertEqual(client.calls, 2)
        self.assertGreater(client.message_sizes[0], client.message_sizes[1])
        self.assertTrue(any(item.reason == "compact_retry" for item in session.turns[-1].transitions))
        self.assertIsNotNone(session.latest_compact_boundary())
        retry_transition = [item for item in session.turns[-1].transitions if item.reason == "compact_retry"][0]
        self.assertEqual(retry_transition.metadata.get("retry_mode"), "compact")
        self.assertEqual(retry_transition.metadata.get("source_mode"), "code")

    def test_query_engine_persists_compact_boundary_event_for_restore(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
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
                        "content_stored_path": ".embedagent/memory/sessions/sess-compact/tool-results/demo-%s/content.txt" % index,
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

        result = engine.submit_turn(
            user_text="继续分析并给我结论",
            stream=False,
            initial_mode="code",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        boundary = session.latest_compact_boundary()
        self.assertIsNotNone(boundary)
        self.assertTrue(boundary.preserved_head_message_id)
        self.assertTrue(boundary.preserved_tail_message_id)
        events = transcript_store.load_events(session.session_id)
        self.assertIn("compact_boundary", [item["type"] for item in events])

        restored = SessionRestorer().restore(events)
        restored_boundary = restored.session.latest_compact_boundary()
        self.assertIsNotNone(restored_boundary)
        self.assertEqual(restored_boundary.summary_text, boundary.summary_text)
        self.assertEqual(restored_boundary.compacted_turn_count, boundary.compacted_turn_count)
        self.assertEqual(restored_boundary.preserved_head_message_id, boundary.preserved_head_message_id)
        self.assertEqual(restored_boundary.preserved_tail_message_id, boundary.preserved_tail_message_id)

    def test_query_engine_writes_transcript_for_completed_turn(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        event_types = [item["type"] for item in events]
        self.assertIn("message", event_types)
        self.assertIn("step_started", event_types)
        self.assertIn("tool_call", event_types)
        self.assertIn("tool_result", event_types)
        self.assertEqual(event_types[-1], "loop_transition")

    def test_query_engine_persists_message_parent_ids_in_transcript(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        message_events = [item for item in events if item["type"] == "message"]
        tool_result = [item for item in events if item["type"] == "tool_result"][0]
        self.assertEqual(message_events[-2]["payload"].get("parent_message_id"), message_events[-3]["payload"].get("message_id"))
        self.assertEqual(tool_result["payload"].get("parent_message_id"), message_events[-2]["payload"].get("message_id"))
        self.assertTrue(tool_result["payload"].get("message_id"))
        self.assertEqual(message_events[-1]["payload"].get("parent_message_id"), tool_result["payload"].get("message_id"))

    def test_query_engine_uses_session_lock_for_context_and_session_mutation(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        lock = RecordingSessionLock()
        context_manager = LockCheckingContextManager(lock)

        original_add_user_message = session.add_user_message
        original_begin_step = session.begin_step
        original_add_assistant_reply = session.add_assistant_reply
        original_add_observation = session.add_observation

        def checked_add_user_message(*args, **kwargs):
            self.assertTrue(lock.held())
            return original_add_user_message(*args, **kwargs)

        def checked_begin_step(*args, **kwargs):
            self.assertTrue(lock.held())
            return original_begin_step(*args, **kwargs)

        def checked_add_assistant_reply(*args, **kwargs):
            self.assertTrue(lock.held())
            return original_add_assistant_reply(*args, **kwargs)

        def checked_add_observation(*args, **kwargs):
            self.assertTrue(lock.held())
            return original_add_observation(*args, **kwargs)

        session.add_user_message = checked_add_user_message
        session.begin_step = checked_begin_step
        session.add_assistant_reply = checked_add_assistant_reply
        session.add_observation = checked_add_observation

        engine = QueryEngine(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            context_manager=context_manager,
            session_lock=lock,
        )
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")

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
        result = engine.submit_turn(
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
        self.assertEqual(events[-1]["type"], "loop_transition")

    def test_query_engine_resume_pending_persists_resolution_and_tool_result(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        first = engine.submit_turn(
            user_text="写文件",
            stream=False,
            initial_mode="code",
            session=session,
            permission_handler=None,
        )
        self.assertEqual(first.transition.reason, "permission_wait")

        resumed = engine.resume_pending(
            session=session,
            initial_mode="code",
            stream=False,
            interaction_resolution={"approved": True},
        )
        self.assertEqual(resumed.transition.reason, "completed")

        events = transcript_store.load_events(session.session_id)
        event_types = [item["type"] for item in events]
        self.assertIn("pending_resolution", event_types)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertTrue(any(item["payload"].get("call_id") == "write-1" for item in tool_results))

        restored = SessionRestorer().restore(events)
        self.assertIsNone(restored.session.pending_interaction)
        first_step = restored.session.turns[-1].steps[0]
        self.assertEqual(first_step.tool_calls[0].call_id, "write-1")
        self.assertEqual(first_step.tool_calls[0].status, "completed")

    def test_query_engine_persists_content_replacement_and_context_snapshot_events(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
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
        result = engine.submit_turn(
            user_text="继续分析并给我结论",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")
        events = transcript_store.load_events(session.session_id)
        event_types = [item["type"] for item in events]
        self.assertIn("context_snapshot", event_types)

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
        rendered = ContextManager().build_messages(
            session,
            "code",
            tools=self.tools,
            workflow_state="chat",
            intelligence_broker=WorkspaceIntelligenceBroker(),
        ).messages
        self.assertIn("PERSISTED REPLACEMENT TEXT", json.dumps(rendered, ensure_ascii=False))

    def test_restored_session_reuses_persisted_content_replacements(self):
        transcript_store = TranscriptStore(self.workspace)
        session_id = "sess-replacements"
        transcript_store.append_event(session_id, "session_meta", {"current_mode": "code"})
        transcript_store.append_event(session_id, "message", {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""})
        transcript_store.append_event(
            session_id,
            "message",
            {
                "role": "tool",
                "content": "{\"success\": true, \"error\": null, \"data\": {\"path\": \"src/demo.c\", \"content_stored_path\": \".embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt\"}}",
                "message_id": "m-tool",
                "turn_id": "t-1",
                "step_id": "s-1",
                "tool_call_id": "call-read-1",
                "tool_name": "read_file",
                "replaced_by_refs": [".embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt"],
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
        restored = SessionRestorer().restore(transcript_store.load_events(session_id))
        result = ContextManager().build_messages(
            restored.session,
            "code",
            tools=self.tools,
            workflow_state="chat",
            intelligence_broker=WorkspaceIntelligenceBroker(),
        )
        rendered = "\n".join(str(item.get("content") or "") for item in result.messages)
        self.assertIn("Tool result replaced: read_file src/demo.c -> .embedagent/memory/sessions/sess-replacements/tool-results/call-read-1/content.txt", rendered)

    def test_query_engine_bootstrap_persists_existing_content_replacements(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        session.add_user_message("继续")
        session.messages.append(
            session.messages[-1].__class__(
                role="tool",
                content="{\"success\": true, \"error\": null, \"data\": {\"path\": \"src/demo.c\", \"content_stored_path\": \".embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt\"}}",
                name="read_file",
                tool_call_id="call-read-1",
                message_id="m-tool",
                turn_id=session.turns[-1].turn_id,
                step_id="s-1",
                kind="tool_result",
                replaced_by_refs=[".embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt"],
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

        result = engine.submit_turn(
            user_text="再继续",
            stream=False,
            initial_mode="code",
            session=session,
        )
        self.assertEqual(result.transition.reason, "completed")

        restored = SessionRestorer().restore(transcript_store.load_events(session.session_id))
        built = ContextManager().build_messages(
            restored.session,
            "code",
            tools=self.tools,
            workflow_state="chat",
            intelligence_broker=WorkspaceIntelligenceBroker(),
        )
        rendered = "\n".join(str(item.get("content") or "") for item in built.messages)
        self.assertIn("Tool result replaced: read_file src/demo.c -> .embedagent/memory/sessions/sess-bootstrap/tool-results/call-read-1/content.txt", rendered)

    def test_query_engine_emits_interrupted_tool_result_when_stop_event_is_set_after_tool_start(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        transcript_store = TranscriptStore(self.workspace)
        stop_event = threading.Event()
        wrapped_tools = CountingToolRuntime(self.tools, slow_first=True)
        engine = QueryEngine(
            client=ToolClient(),
            tools=wrapped_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
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
        self.assertEqual(tool_results[-1]["payload"]["observation"]["data"].get("error_kind"), "interrupted")

    def test_query_engine_keeps_discarded_parallel_results_out_of_guard_stop(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        transcript_store = TranscriptStore(self.workspace)
        engine = QueryEngine(
            client=ParallelReadThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            max_parallel_tools=1,
        )
        result = engine.submit_turn(
            user_text="并行读取",
            stream=False,
            initial_mode="code",
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
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
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
        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
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
        tool_call_ids = [item["payload"]["call_id"] for item in events if item["type"] == "tool_call"]
        self.assertEqual(tool_call_ids, ["call-read-demo-a", "call-read-demo-b", "call-read-demo-c"])

    def test_query_engine_discards_queued_parallel_actions_after_cancel_with_higher_parallelism(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
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

        result = engine.submit_turn(
            user_text="读取文件",
            stream=False,
            initial_mode="code",
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
            [(item["payload"]["call_id"], item["payload"]["observation"]["data"].get("error_kind")) for item in tool_results],
            [
                ("call-read-demo-a", "interrupted"),
                ("call-read-demo-b", "interrupted"),
                ("call-read-demo-c", "discarded"),
            ],
        )

    def test_query_engine_discards_later_batches_after_parallel_discard(self):
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：code")
        transcript_store = TranscriptStore(self.workspace)
        wrapped_tools = CountingToolRuntime(self.tools, slow_read_calls=2, slow_delay_sec=0.2)
        engine = QueryEngine(
            client=ParallelReadThenEditClient(),
            tools=wrapped_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
            max_parallel_tools=2,
        )

        result = engine.submit_turn(
            user_text="读取并修改文件",
            stream=False,
            initial_mode="code",
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
                ("read_file", "tool_error"),
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
                ("call-read-missing", "tool_error"),
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
        interrupt_tools = ToolRuntime(
            self.workspace,
            app_config=AppConfig(allow_system_tool_fallback=True),
        )
        engine = QueryEngine(
            client=SlowCommandClient(),
            tools=interrupt_tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            transcript_store=transcript_store,
        )

        def trigger_cancel(action):
            thread = threading.Thread(target=lambda: (time.sleep(0.2), stop_event.set()))
            thread.daemon = True
            thread.start()

        started = time.time()
        result = engine.submit_turn(
            user_text="运行长命令",
            stream=False,
            initial_mode="debug",
            session=session,
            stop_event=stop_event,
            on_tool_start=trigger_cancel,
        )
        elapsed = time.time() - started
        self.assertEqual(result.transition.reason, "aborted")
        self.assertLess(elapsed, 3.0)
        observation = session.turns[-1].observations[-1]
        self.assertFalse(observation.success)
        self.assertEqual(observation.data.get("error_kind"), "interrupted")
        self.assertIsNot(observation.data.get("synthetic"), True)
        events = transcript_store.load_events(session.session_id)
        tool_results = [item for item in events if item["type"] == "tool_result"]
        self.assertEqual(tool_results[-1]["payload"]["observation"]["data"].get("error_kind"), "interrupted")

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
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        waiting = adapter.get_session_snapshot(session_id)
        self.assertEqual(waiting["status"], "waiting_user_input")
        request_id = str((waiting.get("pending_user_input") or {}).get("request_id") or "")
        adapter.reply_user_input(
            session_id=session_id,
            request_id=request_id,
            answer="切到 debug 模式继续排查",
            selected_index=1,
            selected_mode="debug",
            selected_option_text="切到 debug 模式继续排查",
        )
        final_snapshot = adapter.get_session_snapshot(session_id)
        self.assertEqual(final_snapshot["status"], "idle")
        self.assertEqual(final_snapshot["current_mode"], "debug")

    def test_adapter_resumes_pending_permission(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("code")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="写文件",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        waiting = adapter.get_session_snapshot(session_id)
        self.assertEqual(waiting["status"], "waiting_permission")
        permission_id = str((waiting.get("pending_permission") or {}).get("permission_id") or "")
        adapter.approve_permission(session_id, permission_id)
        final_snapshot = adapter.get_session_snapshot(session_id)
        self.assertEqual(final_snapshot["status"], "idle")
        self.assertTrue(os.path.isfile(os.path.join(self.workspace, "notes", "out.md")))


if __name__ == "__main__":
    unittest.main()
