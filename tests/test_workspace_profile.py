import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_host.runtime.workspace_profile import (
    build_workspace_profile_message,
    profile_workspace,
)
from embedagent_workflow_cpp import task_store

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


class WorkspaceProfileTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("workspace-profile")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_workspace_profile_does_not_emit_task_sidecar_hint(self):
        session_id = "session-tasks"
        task_store.save_task_snapshot(
            self.workspace,
            session_id,
            mode_name="build",
            workflow_state="active",
            discipline_profile="delivery",
            current_phase="build:implement",
            task_summary="summary",
            task_items=[
                {"id": 1, "content": "build:understand", "status": "in_progress", "done": False},
                {"id": 2, "content": "build:implement", "status": "pending", "done": False},
            ],
        )

        message = build_workspace_profile_message(self.workspace, session_id=session_id)

        self.assertNotIn("任务提示", message)
        self.assertNotIn("待办", message)

    def test_base_workspace_profile_does_not_treat_cmake_as_generic_code(self):
        native_dir = os.path.join(self.workspace, "native")
        os.makedirs(native_dir)
        with open(os.path.join(native_dir, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.10)\n")

        profile = profile_workspace(self.workspace)

        self.assertEqual(profile["code_roots"], [])

    def test_c_cpp_application_contributes_workspace_profile_detector(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.runtime.tools import ToolRuntime
        from embedagent_workflow_cpp.application_record import (
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        )

        from embedagent.agent_application_registry import product_agent_application_registry

        native_dir = os.path.join(self.workspace, "native")
        os.makedirs(native_dir)
        with open(os.path.join(native_dir, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.10)\n")

        adapter = InProcessAdapter(
            tools=ToolRuntime(self.workspace),
            agent_application_id=DEFAULT_C_CPP_AGENT_APPLICATION_ID,
            agent_application_registry=product_agent_application_registry(),
        )

        message = adapter.workspace_profile.build_message(self.workspace, session_id="session")

        self.assertIn("已探测代码/工程目录：native", message)

    def test_profile_only_application_does_not_inherit_c_cpp_workspace_detector(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.runtime.tools import ToolRuntime

        native_dir = os.path.join(self.workspace, "native")
        os.makedirs(native_dir)
        with open(os.path.join(native_dir, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.10)\n")

        adapter = InProcessAdapter(
            tools=ToolRuntime(self.workspace),
            agent_application_id="embedagent.python",
        )

        message = adapter.workspace_profile.build_message(self.workspace, session_id="session")

        self.assertNotIn("已探测代码/工程目录：native", message)


if __name__ == "__main__":
    unittest.main()
