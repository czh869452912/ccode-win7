import os
import shutil
import tempfile
import unittest

from embedagent.projection_db import ProjectionDb


class TestProjectionDb(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-projection-db-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.db = ProjectionDb(
            os.path.join(
                self.workspace,
                ".embedagent",
                "memory",
                "projections.sqlite3",
            )
        )

    def test_schema_bootstrap_and_session_projection_upsert(self):
        self.db.initialize()
        self.db.upsert_session_projection(
            session_id="session-1",
            updated_at="2026-04-05T00:00:00Z",
            current_mode="explore",
            started_at="2026-04-05T00:00:00Z",
            turn_count=1,
            message_count=2,
            user_goal="demo",
            transcript_ref=".embedagent/memory/sessions/session-1/transcript.jsonl",
            summary_ref=".embedagent/memory/sessions/session-1/summary.json",
            last_transition_reason="completed",
            last_transition_message="ok",
            summary_text="demo",
        )
        row = self.db.get_session_projection("session-1")
        self.assertIsNotNone(row)
        self.assertEqual(row["current_mode"], "explore")
        self.assertEqual(row["summary_ref"], ".embedagent/memory/sessions/session-1/summary.json")
        rows = self.db.list_session_projections(limit=5)
        self.assertEqual(len(rows), 1)
        self.db.delete_session_projections_except([])
        self.assertEqual(self.db.list_session_projections(limit=5), [])


if __name__ == "__main__":
    unittest.main()
