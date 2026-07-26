import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


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


class ToolsV2RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("tools-v2")
        os.makedirs(os.path.join(self.workspace, "src"), exist_ok=True)
        with open(os.path.join(self.workspace, "src", "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int demo(void) {\n    return 0;\n}\n")
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_schema_projection_requires_explicit_tool_names(self):
        from embedagent_host.runtime.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [item["function"]["name"] for item in runtime.schemas_for("build")]
        self.assertEqual(names, [])

    def test_explicit_build_tool_names_project_schemas(self):
        from embedagent_host.runtime.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for(
                "build",
                tool_names=["read_file", "list_dir", "write_file", "edit_file"],
            )
        ]
        self.assertEqual(names, ["read_file", "list_dir", "write_file", "edit_file"])

    def test_workflow_neutral_tools_accept_arbitrary_workflow_state(self):
        from embedagent_host.runtime.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for(
                "build",
                workflow_state="custom-review-state",
                tool_names=["read_file", "write_file", "ask_user"],
            )
        ]
        self.assertEqual(names, ["read_file", "write_file", "ask_user"])

    def test_explicit_verify_tool_names_preserve_workflow_visibility_filter(self):
        from embedagent_host.runtime.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for(
                "verify",
                workflow_state="chat",
                tool_names=["read_file", "grep_text", "ask_user"],
            )
        ]
        self.assertEqual(names, ["read_file", "grep_text", "ask_user"])

    def test_bash_preserves_shell_fallback_when_managed_primary_tool_is_missing(self):
        from unittest.mock import patch

        from embedagent_host.runtime.tools import ToolRuntime

        from embedagent.config import AppConfig

        command = (
            'clang-analyzer --version || "%s" -c "print(\'fallback-ok\')"'
            % sys.executable.replace("\\", "\\\\")
        )
        with patch.dict(
            os.environ,
            {
                "EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK": "0",
                "EMBEDAGENT_BUNDLE_ROOT": "",
                "EMBEDAGENT_LLVM_ROOT": "",
            },
            clear=False,
        ):
            runtime = ToolRuntime(
                self.workspace,
                app_config=AppConfig(allow_system_tool_fallback=False),
            )
            observation = runtime.execute(
                "bash",
                {
                    "command": command,
                    "cwd": ".",
                    "timeout_sec": 10,
                },
            )

        self.assertTrue(observation.success)
        self.assertEqual(observation.data["requested_command"], command)
        self.assertIn("fallback-ok", observation.data["stdout"])
        self.assertNotIn("managed_primary_tool", observation.data)


if __name__ == "__main__":
    unittest.main()
