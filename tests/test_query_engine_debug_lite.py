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
from embedagent.session import Action, AssistantReply, Session
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


class RecordEvidenceClient(object):
    def __init__(self):
        self._calls = 0

    def generate(self, messages, tools=None):
        del messages, tools
        self._calls += 1
        if self._calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="record_failing_evidence",
                        arguments={"summary": "reproduced failure in src/demo.c"},
                        call_id="call-1",
                        raw_arguments='{"summary":"reproduced failure in src/demo.c"}',
                    )
                ],
                finish_reason="tool_calls",
            )
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

    def _build_engine(self, client=None):
        default_extensions = build_default_extension_set(self.tools)
        return QueryEngine(
            client=client or DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            extension_manager=default_extensions.manager,
        )

    def test_debug_mode_submit_turn_adds_harness_context(self):
        engine = self._build_engine()
        result = engine.submit_user_turn(
            user_text="开始 debug-lite",
            stream=False,
            initial_mode="debug",
        )
        system_messages = [
            message.content for message in result.session.messages if message.role == "system"
        ]
        self.assertTrue(any("Mode: debug" in content for content in system_messages))

    def test_debug_mode_schemas_use_v2_pack(self):
        engine = self._build_engine()
        session = Session()
        engine._ensure_extension_tools_registered(session, "debug", "chat", reason="test")
        names = sorted(
            item["function"]["name"] for item in engine._schemas_for_active_tools("debug", "chat")
        )
        self.assertIn("record_failing_evidence", names)
        self.assertIn("run_recipe", names)
        self.assertIn("bash", names)

    def test_adapter_create_session_exposes_debug_lite_snapshot_fields(self):
        adapter = InProcessAdapter(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("debug")
        self.assertEqual(snapshot["current_mode"], "debug")
        # No harness state pre-generated on session creation
        self.assertEqual(snapshot["current_phase"], "")
        self.assertEqual(snapshot["discipline_profile"], "")
        self.assertEqual(snapshot["current_activity"], "")

    def test_adapter_submit_user_message_refreshes_debug_phase(self):
        adapter = InProcessAdapter(
            client=RecordEvidenceClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("debug")
        self.assertEqual(snapshot["current_phase"], "")
        # Use English work request to trigger harness injection
        updated = adapter.submit_user_message(snapshot["session_id"], "fix this bug", stream=False)
        # Phase should change from empty to a non-empty debug phase
        self.assertTrue(updated["current_phase"])
        # task_summary should show debug track, not be empty
        self.assertIn("debug:", updated["task_summary"])


if __name__ == "__main__":
    unittest.main()
