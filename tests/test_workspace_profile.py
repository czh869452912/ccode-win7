import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.harness import task_store
from embedagent.workspace_profile import build_workspace_profile_message


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


if __name__ == "__main__":
    unittest.main()
