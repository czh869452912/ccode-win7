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


class DebugEvidenceV2Tests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("debug-evidence")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_record_failing_evidence_returns_structured_payload(self):
        from conftest import register_default_c_workflow_tools
        from embedagent_host.runtime.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        register_default_c_workflow_tools(runtime, self.workspace)
        result = runtime.execute(
            "record_failing_evidence",
            {"summary": "reproduced failure in src/demo.c"},
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data.get("summary"), "reproduced failure in src/demo.c")
        self.assertTrue(result.data.get("failing_evidence_ready"))


if __name__ == "__main__":
    unittest.main()
