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
from embedagent.workspace_intelligence import WorkspaceIntelligenceBroker


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
