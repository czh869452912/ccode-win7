import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.project_memory import ProjectMemoryStore
from embedagent.session_store import SessionSummaryStore
from embedagent.transcript_store import TranscriptStore
from embedagent_core.session import Action, AssistantReply, Observation, Session


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
            os.path.exists(
                os.path.join(self.workspace, ".embedagent", "memory", "sessions", "index.json")
            )
        )
        items = store.list_summaries(limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("session_id"), session.session_id)
        self.assertEqual(items[0].get("summary_ref"), summary_ref)
        self.assertTrue(str(items[0].get("transcript_ref") or "").endswith("/transcript.jsonl"))

    def test_rename_session_updates_thread_title_and_projection(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("original goal")
        summary_ref = store.persist(session, "build")

        result = store.rename_session(session.session_id, "  Renamed Thread  ")

        self.assertEqual(result["session_id"], session.session_id)
        self.assertEqual(result["thread"]["title"], "Renamed Thread")
        self.assertEqual(result["title"], "Renamed Thread")
        summary = store.load_summary(summary_ref)
        self.assertEqual(summary["thread"]["title"], "Renamed Thread")
        self.assertEqual(summary["user_goal"], "original goal")
        listed = store.list_summaries(limit=5)
        self.assertEqual(listed[0]["title"], "Renamed Thread")
        self.assertEqual(listed[0]["thread"]["title"], "Renamed Thread")

    def test_rename_session_rejects_empty_title(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("original goal")
        store.persist(session, "build")

        with self.assertRaises(ValueError) as raised:
            store.rename_session(session.session_id, "   ")

        self.assertEqual(str(raised.exception), "invalid_thread_title")

    def test_archive_session_hides_from_default_list_but_keeps_explicit_listing(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("archive me")
        store.persist(session, "build")

        archived = store.archive_session(session.session_id)

        self.assertTrue(archived["thread"]["archived"])
        self.assertTrue(archived["thread"]["archived_at"])
        self.assertEqual(store.list_summaries(limit=5), [])
        with_archived = store.list_summaries(limit=5, include_archived=True)
        self.assertEqual(len(with_archived), 1)
        self.assertEqual(with_archived[0]["session_id"], session.session_id)
        self.assertTrue(with_archived[0]["thread"]["archived"])

    def test_collect_stored_paths_keeps_archived_session_refs(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("archive refs")
        action = Action("read_file", {}, "call-archive-ref")
        session.add_assistant_reply(AssistantReply("", [action]))
        session.add_observation(
            action,
            Observation(
                "read_file",
                True,
                None,
                {"output_stored_path": ".embedagent/tool-results/result-1.json"},
            ),
        )
        store.persist(session, "build")
        store.archive_session(session.session_id)

        self.assertEqual(
            store.collect_stored_paths(),
            [".embedagent/tool-results/result-1.json"],
        )

    def test_cleanup_keeps_archived_sessions(self):
        store = SessionSummaryStore(self.workspace)
        archived_session = Session()
        archived_session.add_user_message("archived")
        active_session = Session()
        active_session.add_user_message("active")
        store.persist(archived_session, "build")
        store.persist(active_session, "build")
        store.archive_session(archived_session.session_id)

        result = store.cleanup(max_sessions=1)

        self.assertEqual(result["deleted"], 0)
        self.assertTrue(os.path.isfile(store.resolve_summary_path(archived_session.session_id)))
        self.assertTrue(os.path.isfile(store.resolve_summary_path(active_session.session_id)))

    def test_fork_session_copies_transcript_with_new_session_id_and_thread_metadata(self):
        store = SessionSummaryStore(self.workspace)
        transcript_store = TranscriptStore(self.workspace)
        session = Session()
        session.add_user_message("source goal")
        summary_ref = store.persist(session, "debug")
        transcript_store.append_event(
            session.session_id,
            "session_meta",
            {"current_mode": "debug", "session_id": session.session_id},
        )
        transcript_store.append_event(
            session.session_id,
            "user",
            {
                "role": "user",
                "content": "source goal",
                "message_id": "m-source",
                "session_id": session.session_id,
            },
        )
        store.rename_session(session.session_id, "Source Title")

        forked = store.fork_session(session.session_id, title="Fork Title")

        self.assertNotEqual(forked["session_id"], session.session_id)
        self.assertEqual(forked["thread"]["title"], "Fork Title")
        self.assertEqual(forked["thread"]["forked_from"], session.session_id)
        self.assertTrue(forked["thread"]["forked_at"])
        source_summary = store.load_summary(summary_ref)
        self.assertEqual(source_summary["thread"]["title"], "Source Title")
        fork_events = transcript_store.load_events(forked["session_id"])
        self.assertEqual(fork_events[0]["session_id"], forked["session_id"])
        self.assertEqual(fork_events[0]["payload"]["session_id"], forked["session_id"])
        self.assertEqual(fork_events[1]["session_id"], forked["session_id"])
        self.assertEqual(fork_events[1]["payload"]["session_id"], forked["session_id"])
        listed = store.list_summaries(limit=5)
        self.assertEqual(listed[0]["session_id"], forked["session_id"])


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

        with open(
            os.path.join(
                self.workspace, ".embedagent", "memory", "project", "command-recipes.json"
            ),
            "r",
            encoding="utf-8",
        ) as handle:
            recipes = json.load(handle)
        self.assertEqual(recipes[0]["tool_name"], "run_recipe")
        self.assertEqual(recipes[0]["recipe_action"], "build")

        message = store.build_system_message("build", 600) or ""
        self.assertIn("[build]", message)
        self.assertNotIn("compile_project", message)


if __name__ == "__main__":
    unittest.main()
