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

    def test_build_mode_schema_defaults_to_mode_contract(self):
        from embedagent.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [item["function"]["name"] for item in runtime.schemas_for("build")]
        self.assertIn("read_file", names)
        self.assertIn("list_dir", names)
        self.assertIn("write_file", names)
        self.assertIn("edit_file", names)
        self.assertNotIn("run_recipe", names)
        self.assertNotIn("task_status", names)

    def test_debug_mode_schema_defaults_to_mode_contract(self):
        from embedagent.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [item["function"]["name"] for item in runtime.schemas_for("debug")]
        self.assertIn("read_file", names)
        self.assertIn("edit_file", names)
        self.assertIn("ask_user", names)
        self.assertNotIn("run_recipe", names)
        self.assertNotIn("record_failing_evidence", names)
        self.assertNotIn("task_status", names)

    def test_verify_mode_schema_defaults_to_read_only_mode_contract(self):
        from embedagent.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [item["function"]["name"] for item in runtime.schemas_for("verify")]
        self.assertIn("read_file", names)
        self.assertIn("list_dir", names)
        self.assertIn("grep_text", names)
        self.assertIn("ask_user", names)
        self.assertNotIn("run_recipe", names)
        self.assertNotIn("list_recipes", names)
        self.assertNotIn("report_quality_v2", names)
        self.assertNotIn("task_status", names)


if __name__ == "__main__":
    unittest.main()
