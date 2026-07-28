import shutil
import tempfile
import unittest

from embedagent_core.session import Action, Observation
from embedagent_host.runtime.projection_db import ProjectionDb
from embedagent_host.runtime.tool_commit import ToolCommitCoordinator
from embedagent_host.runtime.tool_result_store import ToolResultStore
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_host.runtime.transcript_store import TranscriptStore


class TestToolCommitCoordinator(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-tool-commit-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.store = ToolResultStore(self.workspace)
        self.db = ProjectionDb(self.workspace + "/.embedagent/memory/projections.sqlite3")
        self.transcript = TranscriptStore(self.workspace)
        self.coordinator = ToolCommitCoordinator(self.store, self.db)

    def test_large_content_creates_stored_path_and_replacement_record(self):
        action = Action("read_file", {"path": "src/demo.c"}, "call-1")
        observation = Observation(
            "read_file",
            True,
            None,
            {"path": "src/demo.c", "content": "x" * 5000},
        )
        prepared = self.coordinator.materialize(
            "session-1",
            action,
            observation,
        )
        self.assertTrue(prepared.observation.success)
        self.assertIn("content_stored_path", prepared.observation.data)
        self.assertIn("content_preview", prepared.observation.data)
        self.assertEqual(len(prepared.replacements), 1)
        self.assertFalse(self.transcript.transcript_exists("session-1"))
        self.assertEqual(self.db.list_tool_results(), [])

        self.coordinator.finalize(prepared.commit_token)

        self.assertEqual(len(self.db.list_tool_results()), 1)

    def test_tool_runtime_materializes_then_finalizes_projection(self):
        runtime = ToolRuntime(self.workspace)
        action = Action("read_file", {"path": "src/demo.c"}, "call-runtime")
        observation = Observation(
            "read_file",
            True,
            None,
            {"path": "src/demo.c", "content": "y" * 5000},
        )

        prepared = runtime.materialize_observation(
            "session-runtime",
            action,
            observation,
        )

        self.assertIn("content_stored_path", prepared.observation.data)
        self.assertFalse(self.transcript.transcript_exists("session-runtime"))
        self.assertEqual(runtime.projection_db.list_tool_results(), [])
        runtime.finalize_observation(prepared.commit_token)
        self.assertEqual(len(runtime.projection_db.list_tool_results()), 1)


if __name__ == "__main__":
    unittest.main()
