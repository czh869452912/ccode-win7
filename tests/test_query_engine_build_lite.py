import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.permissions import PermissionPolicy
from embedagent_core.query_engine import QueryEngine
from embedagent_core.session import AssistantReply, Session
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.runtime.context import ContextManager
from embedagent_host.runtime.project_memory import ProjectMemoryStore
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_host.runtime.workspace_intelligence import WorkspaceIntelligenceBroker
from query_engine_product_helpers import build_product_agent_application

from embedagent.modes import (
    allowed_tools_for,
    build_system_prompt,
    is_path_writable,
    parse_mode_command,
    parse_natural_language_mode_switch,
    require_mode,
)

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


class ProductModeToolPolicy(object):
    def allowed_tools_for(self, mode_name, workflow_state=None):
        del workflow_state
        return allowed_tools_for(mode_name)


class ProductWritePathPolicy(object):
    def is_path_writable(self, mode_name, normalized_path, app_config=None):
        return is_path_writable(mode_name, normalized_path, app_config)


class ProductModeRuntimePolicy(object):
    def default_mode(self):
        return "explore"

    def require_mode(self, mode_name):
        return require_mode(mode_name or self.default_mode())

    def build_system_prompt(self, mode_name, app_config=None, workspace="", local_resources=None):
        return build_system_prompt(
            mode_name,
            app_config,
            workspace,
            local_resources=local_resources,
        )

    def parse_mode_switch_request(self, user_text, fallback_mode):
        mode_name, remainder, switched = parse_mode_command(
            user_text,
            fallback_mode=fallback_mode,
        )
        if switched:
            return mode_name, remainder, True
        return parse_natural_language_mode_switch(user_text, fallback_mode=fallback_mode)


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

    def _build_engine(self, client=None):
        default_extensions = build_product_agent_application(self.tools)
        project_memory = ProjectMemoryStore(self.workspace)
        return QueryEngine(
            client=client or DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            context_manager=ContextManager(project_memory=project_memory),
            project_memory_store=project_memory,
            intelligence_broker=WorkspaceIntelligenceBroker(),
            extension_manager=default_extensions.extension_manager,
            mode_tool_policy=ProductModeToolPolicy(),
            write_path_policy=ProductWritePathPolicy(),
            mode_runtime_policy=ProductModeRuntimePolicy(),
        )

    def test_build_mode_submit_turn_adds_harness_context(self):
        engine = self._build_engine()

        result = engine.submit_user_turn(
            user_text="开始 build-lite",
            stream=False,
            initial_mode="build",
        )

        self.assertEqual(result.transition.reason, "completed")
        system_messages = [
            message.content for message in result.session.messages if message.role == "system"
        ]
        self.assertTrue(any("Discipline: lite_spec_tdd" in content for content in system_messages))
        self.assertTrue(any("Mode: build" in content for content in system_messages))

    def test_build_mode_existing_session_gets_harness_context(self):
        engine = self._build_engine()
        session = Session()
        session.add_system_message("seed")
        result = engine.submit_user_turn(
            user_text="继续 build-lite",
            stream=False,
            initial_mode="build",
            session=session,
        )
        system_messages = [
            message.content for message in result.session.messages if message.role == "system"
        ]
        self.assertTrue(any("Mode: build" in content for content in system_messages))
        self.assertFalse(any("Core pack:" in content for content in system_messages))

    def test_build_mode_schemas_use_v2_pack(self):
        engine = self._build_engine()
        session = Session()
        engine._ensure_extension_tools_registered(session, "build", "chat", reason="test")
        names = sorted(
            item["function"]["name"]
            for item in engine.extension_host.schemas_for_active_tools("build", "chat")
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
        # No harness state pre-generated on session creation
        self.assertEqual(snapshot["current_phase"], "")
        self.assertEqual(snapshot["discipline_profile"], "")
        self.assertEqual(snapshot["current_activity"], "")
        state = adapter._sessions[snapshot["session_id"]]
        system_messages = [
            message.content for message in state.session.messages if message.role == "system"
        ]
        # Harness context is only injected on explicit work requests, not on session creation
        self.assertFalse(any("Mode: build" in content for content in system_messages))
        # System prompt should still be present
        self.assertTrue(any("build" in content for content in system_messages))


if __name__ == "__main__":
    unittest.main()
