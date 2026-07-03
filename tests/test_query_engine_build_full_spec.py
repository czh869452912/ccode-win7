import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.session import AssistantReply
from embedagent.tools import ToolRuntime
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.query_engine import QueryEngine
from embedagent_host.default_extensions import build_default_extension_set
from embedagent_host.inprocess_adapter import InProcessAdapter

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


class QueryEngineBuildFullSpecTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("build-full-spec")
        os.makedirs(os.path.join(self.workspace, "src"), exist_ok=True)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n    return 0;\n}\n")
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        self.tools = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _build_engine(self, client=None):
        default_extensions = build_default_extension_set(self.tools)
        return QueryEngine(
            client=client or DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            extension_manager=default_extensions.manager,
        )

    def test_build_mode_full_spec_adds_full_harness_context(self):
        engine = self._build_engine()
        result = engine.submit_user_turn(
            user_text="build full spec",
            stream=False,
            initial_mode="build",
            workflow_state="plan",
        )
        system_messages = [
            message.content for message in result.session.messages if message.role == "system"
        ]
        self.assertTrue(any("full_spec_tdd" in content for content in system_messages))

    def test_adapter_snapshot_exposes_task_summary(self):
        adapter = InProcessAdapter(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        self.assertIn("task_summary", snapshot)


if __name__ == "__main__":
    unittest.main()
