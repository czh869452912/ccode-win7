import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.permissions import PermissionPolicy
from embedagent.query_engine import QueryEngine
from embedagent.session import AssistantReply, Session
from embedagent.tools import ToolRuntime
from embedagent.inprocess_adapter import InProcessAdapter


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


class DoneClient(object):
    def generate(self, messages, tools=None):
        del messages, tools
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None and reply.reasoning_content:
            on_reasoning_delta(reply.reasoning_content)
        return reply


class QueryEngineBuildLiteTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("build-lite")
        os.makedirs(os.path.join(self.workspace, "src"), exist_ok=True)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n    return 0;\n}\n")
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        self.tools = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_build_mode_submit_turn_adds_harness_context(self):
        engine = QueryEngine(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )

        result = engine.submit_user_turn(
            user_text="开始 build-lite",
            stream=False,
            initial_mode="build",
        )

        self.assertEqual(result.transition.reason, "completed")
        system_messages = [message.content for message in result.session.messages if message.role == "system"]
        self.assertTrue(any("Discipline: lite_spec_tdd" in content for content in system_messages))
        self.assertTrue(any("Mode: build" in content for content in system_messages))

    def test_build_mode_existing_session_gets_harness_context(self):
        engine = QueryEngine(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        session = Session()
        session.add_system_message("seed")
        result = engine.submit_user_turn(
            user_text="继续 build-lite",
            stream=False,
            initial_mode="build",
            session=session,
        )
        system_messages = [message.content for message in result.session.messages if message.role == "system"]
        self.assertTrue(any("Mode: build" in content for content in system_messages))
        self.assertTrue(any("Core pack:" in content for content in system_messages))

    def test_build_mode_schemas_use_v2_pack(self):
        engine = QueryEngine(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        names = sorted(
            item["function"]["name"]
            for item in engine._schemas_for_mode("build", "chat")
        )
        self.assertIn("list_dir", names)
        self.assertIn("run_recipe", names)
        self.assertNotIn("list_files", names)
        self.assertNotIn("compile_project", names)

    def test_adapter_create_session_exposes_build_lite_snapshot_fields(self):
        adapter = InProcessAdapter(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )

        snapshot = adapter.create_session("build")
        self.assertEqual(snapshot["current_mode"], "build")
        self.assertEqual(snapshot["current_phase"], "understand")
        self.assertEqual(snapshot["discipline_profile"], "lite_spec_tdd")
        self.assertTrue(snapshot["current_activity"])
        state = adapter._sessions[snapshot["session_id"]]
        system_messages = [message.content for message in state.session.messages if message.role == "system"]
        self.assertTrue(any("Mode: build" in content for content in system_messages))


if __name__ == "__main__":
    unittest.main()
