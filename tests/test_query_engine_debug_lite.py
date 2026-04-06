import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.permissions import PermissionPolicy
from embedagent.query_engine import QueryEngine
from embedagent.session import AssistantReply
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


class QueryEngineDebugLiteTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("debug-lite")
        os.makedirs(os.path.join(self.workspace, "src"), exist_ok=True)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n    return 0;\n}\n")
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        self.tools = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_debug_mode_submit_turn_adds_harness_context(self):
        engine = QueryEngine(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        result = engine.submit_turn(
            user_text="开始 debug-lite",
            stream=False,
            initial_mode="debug",
        )
        system_messages = [message.content for message in result.session.messages if message.role == "system"]
        self.assertTrue(any("Mode: debug" in content for content in system_messages))

    def test_adapter_create_session_exposes_debug_lite_snapshot_fields(self):
        adapter = InProcessAdapter(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("debug")
        self.assertEqual(snapshot["current_mode"], "debug")
        self.assertEqual(snapshot["current_phase"], "reproduce")
        self.assertEqual(snapshot["discipline_profile"], "lite_spec_tdd")
        self.assertTrue(snapshot["current_activity"])


if __name__ == "__main__":
    unittest.main()
