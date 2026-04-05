import shutil
import tempfile
import unittest

from embedagent.projection_db import ProjectionDb
from embedagent.session import Action, Observation, Session
from embedagent.tool_commit import ToolCommitCoordinator
from embedagent.tool_result_store import ToolResultStore
from embedagent.transcript_store import TranscriptStore


class TestToolCommitCoordinator(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-tool-commit-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.store = ToolResultStore(self.workspace)
        self.db = ProjectionDb(self.workspace + "/.embedagent/memory/projections.sqlite3")
        self.transcript = TranscriptStore(self.workspace)
        self.coordinator = ToolCommitCoordinator(self.store, self.db, self.transcript)
        self.session = Session()
        self.session.add_user_message("inspect file", turn_id="t-1", message_id="m-user")
        self.session.begin_step(step_id="s-1")

    def test_large_content_creates_stored_path_and_replacement_record(self):
        action = Action("read_file", {"path": "src/demo.c"}, "call-1")
        observation = Observation(
            "read_file",
            True,
            None,
            {"path": "src/demo.c", "content": "x" * 5000},
        )
        committed = self.coordinator.commit(
            self.session,
            action,
            observation,
            current_mode="explore",
        )
        self.assertTrue(committed.success)
        self.assertIn("content_stored_path", committed.data)
        self.assertIn("content_preview", committed.data)
        self.assertEqual(len(self.session.content_replacements), 1)


if __name__ == "__main__":
    unittest.main()
