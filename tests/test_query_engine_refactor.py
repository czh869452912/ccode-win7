import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.context import ContextManager
from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.permissions import PermissionPolicy
from embedagent.query_engine import QueryEngine
from embedagent.session import Action, AssistantReply, Observation, Session
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
        "%s-%s" % (name, next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


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
                    "content_artifact_ref": ".embedagent/memory/artifacts/demo.json",
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
        self.assertGreaterEqual(result.analysis.get("artifact_replacement_count") or 0, 1)

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

    def test_llsp_provider_uses_backend_contract(self):
        provider = LlspProvider(backend=FakeLlspBackend())
        evidence = provider.collect(Session(), "code", self.tools, None)
        self.assertEqual(len(evidence), 1)
        self.assertIn("llsp symbol demo", evidence[0].content)
        self.assertEqual(evidence[0].metadata.get("backend"), "fake")

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
