import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.default_extensions import build_default_extension_set
from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.permissions import PermissionPolicy
from embedagent.query_engine import QueryEngine
from embedagent.session import AssistantReply
from embedagent.tools import ToolRuntime

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


class QueryEngineVerifySliceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("verify-slice")
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

    def test_verify_mode_submit_turn_adds_verify_context(self):
        engine = self._build_engine()
        result = engine.submit_user_turn(
            user_text="开始 verify",
            stream=False,
            initial_mode="verify",
        )
        system_messages = [
            message.content for message in result.session.messages if message.role == "system"
        ]
        # Harness context is not injected for verify mode (read-only mode)
        self.assertFalse(any("Mode: verify" in content for content in system_messages))
        # System prompt should still be present
        self.assertTrue(any("verify" in content for content in system_messages))

    def test_verify_mode_schemas_use_v2_pack(self):
        engine = self._build_engine()
        names = sorted(
            item["function"]["name"] for item in engine._schemas_for_mode("verify", "chat")
        )
        self.assertIn("run_recipe", names)
        self.assertIn("report_quality_v2", names)
        self.assertNotIn("compile_project", names)
        self.assertNotIn("report_quality", names)

    def test_adapter_snapshot_exposes_verify_activity(self):
        adapter = InProcessAdapter(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("verify")
        self.assertEqual(snapshot["current_mode"], "verify")
        # No harness state pre-generated on session creation for verify mode
        self.assertEqual(snapshot["current_activity"], "")
        state = adapter._sessions[snapshot["session_id"]]
        system_messages = [
            message.content for message in state.session.messages if message.role == "system"
        ]
        # Harness context is not injected for verify mode on session creation
        self.assertFalse(any("Mode: verify" in content for content in system_messages))
        # System prompt should still be present
        self.assertTrue(any("verify" in content for content in system_messages))

    def test_set_session_mode_refreshes_harness_snapshot(self):
        adapter = InProcessAdapter(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        # No harness state pre-generated on session creation
        self.assertEqual(snapshot["current_phase"], "")
        updated = adapter.set_session_mode(snapshot["session_id"], "verify")
        self.assertEqual(updated["current_mode"], "verify")
        # set_session_mode triggers harness refresh
        self.assertEqual(updated["current_phase"], "select_recipe")
        self.assertEqual(updated["discipline_profile"], "lite_spec_tdd")
        self.assertTrue(updated["current_activity"])
        self.assertIn("verify:select_recipe", updated["task_summary"])


if __name__ == "__main__":
    unittest.main()
