import os
import shutil
import sys
import tempfile
import threading
import unittest
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Action, AssistantReply, Observation, Session
from embedagent.session_store import SessionSummaryStore


class TestSessionSummaryStore(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-session-store-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))

    def test_list_summaries_comes_from_projection_without_index_json(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("hello")
        summary_ref = store.persist(session, "build")
        self.assertTrue(summary_ref.endswith("/summary.json"))
        self.assertFalse(
            os.path.exists(os.path.join(self.workspace, ".embedagent", "memory", "sessions", "index.json"))
        )
        items = store.list_summaries(limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("session_id"), session.session_id)
        self.assertEqual(items[0].get("summary_ref"), summary_ref)
        self.assertTrue(str(items[0].get("transcript_ref") or "").endswith("/transcript.jsonl"))


class TestProjectMemoryStore(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-project-memory-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))

    def test_concurrent_refresh_keeps_json_files_valid(self):
        store = ProjectMemoryStore(self.workspace)
        session = Session()
        session.add_user_message("hello")
        failures = []

        def worker():
            try:
                for _ in range(10):
                    store.refresh(session, "build", ".embedagent/memory/sessions/demo/summary.json")
            except Exception as exc:
                failures.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(failures, [])
        root = os.path.join(self.workspace, ".embedagent", "memory", "project")
        for name in (
            "project-profile.json",
            "command-recipes.json",
            "known-issues.json",
            "memory-index.json",
        ):
            path = os.path.join(root, name)
            self.assertTrue(os.path.isfile(path))
            with open(path, "r", encoding="utf-8") as handle:
                self.assertTrue(handle.read().strip())
        tmp_files = [item for item in os.listdir(root) if item.endswith(".tmp")]
        self.assertEqual(tmp_files, [])

    def test_refresh_records_official_run_recipe_history(self):
        store = ProjectMemoryStore(self.workspace)
        session = Session()
        session.add_user_message("build")
        action = Action("run_recipe", {"recipe_id": "cmake.build.default"}, "call-build")
        session.add_assistant_reply(
            AssistantReply(
                content="",
                actions=[action],
                finish_reason="tool_calls",
            )
        )
        observation = Observation(
            "run_recipe",
            True,
            None,
            {
                "command": "cmake --build build",
                "cwd": ".",
                "recipe_id": "cmake.build.default",
                "recipe_action": "build",
            },
        )
        session.add_observation(action, observation)

        store.refresh(session, "build", ".embedagent/memory/sessions/demo/summary.json")

        with open(os.path.join(self.workspace, ".embedagent", "memory", "project", "command-recipes.json"), "r", encoding="utf-8") as handle:
            recipes = json.load(handle)
        self.assertEqual(recipes[0]["tool_name"], "run_recipe")
        self.assertEqual(recipes[0]["recipe_action"], "build")

        message = store.build_system_message("build", 600) or ""
        self.assertIn("[build]", message)
        self.assertNotIn("compile_project", message)


if __name__ == "__main__":
    unittest.main()

