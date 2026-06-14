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


class VerifyQualityV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("verify-quality")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_report_quality_v2_returns_structured_summary(self):
        from conftest import register_default_c_workflow_tools

        from embedagent.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        register_default_c_workflow_tools(runtime, self.workspace)
        result = runtime.execute(
            "report_quality_v2",
            {"error_count": 0, "warning_count": 1, "test_failures": 0},
        )
        self.assertTrue(result.success)
        self.assertIn("passed", result.data)


if __name__ == "__main__":
    unittest.main()
