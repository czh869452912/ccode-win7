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

    def test_build_lite_pack_exposes_list_dir_and_run_recipe(self):
        from embedagent.tools_v2.runtime import ToolRuntimeV2

        runtime = ToolRuntimeV2(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for_pack("build_lite")
        ]
        self.assertIn("list_dir", names)
        self.assertIn("run_recipe", names)

    def test_debug_lite_pack_exposes_read_edit_and_run_recipe(self):
        from embedagent.tools_v2.runtime import ToolRuntimeV2

        runtime = ToolRuntimeV2(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for_pack("debug_lite")
        ]
        self.assertIn("read_file", names)
        self.assertIn("edit_file", names)
        self.assertIn("run_recipe", names)

    def test_verify_pack_exposes_run_recipe_and_list_recipes(self):
        from embedagent.tools_v2.runtime import ToolRuntimeV2

        runtime = ToolRuntimeV2(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for_pack("verify")
        ]
        self.assertIn("run_recipe", names)
        self.assertIn("list_recipes", names)


if __name__ == "__main__":
    unittest.main()
