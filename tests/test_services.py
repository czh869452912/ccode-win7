import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.services.event_emitter import EventEmitter
from embedagent.services.harness_state_synchronizer import HarnessStateSynchronizer
from embedagent.services.session_lifecycle import SessionLifecycleManager
from embedagent.services.workspace_file_service import WorkspaceFileService


class TestEventEmitter(unittest.TestCase):
    def setUp(self):
        self.emitter = EventEmitter()

    def test_emit_calls_registered_handlers(self):
        calls = []

        def handler(event_type, session_id, payload):
            calls.append((event_type, session_id, payload))

        self.emitter.add_handler("test_event", handler)
        self.emitter.emit(None, "test_event", "sess1", {"key": "value"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ("test_event", "sess1", {"key": "value"}))

    def test_handler_exception_isolated(self):
        calls = []

        def bad_handler(event_type, session_id, payload):
            raise RuntimeError("boom")

        def good_handler(event_type, session_id, payload):
            calls.append((event_type, session_id, payload))

        self.emitter.add_handler("test_event", bad_handler)
        self.emitter.add_handler("test_event", good_handler)
        self.emitter.emit(None, "test_event", "sess1", {"key": "value"})
        self.assertEqual(len(calls), 1)

    def test_add_remove_handler(self):
        calls = []

        def handler(event_type, session_id, payload):
            calls.append((event_type, session_id, payload))

        self.emitter.add_handler("test_event", handler)
        self.emitter.emit(None, "test_event", "sess1", {"key": "value"})
        self.assertEqual(len(calls), 1)

        self.emitter.remove_handler("test_event", handler)
        self.emitter.emit(None, "test_event", "sess1", {"key": "value"})
        self.assertEqual(len(calls), 1)

    def test_global_handler(self):
        calls = []

        def handler(event_type, session_id, payload):
            calls.append((event_type, session_id, payload))

        self.emitter.add_handler(None, handler)
        self.emitter.emit(None, "any_event", "sess1", {"key": "value"})
        self.assertEqual(len(calls), 1)


class TestWorkspaceFileService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.realpath(tempfile.mkdtemp())
        self.service = WorkspaceFileService(self.temp_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_path_enforces_boundary(self):
        with self.assertRaises(ValueError):
            self.service.resolve_path("../../../etc/passwd")

    def test_read_file_returns_content(self):
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("hello world")
        result = self.service.read_file("test.txt")
        self.assertEqual(result["content"], "hello world")
        self.assertEqual(result["path"], "test.txt")

    def test_list_directory_filters_skip_dirs(self):
        os.makedirs(os.path.join(self.temp_dir, ".git"))
        with open(os.path.join(self.temp_dir, "file.txt"), "w") as f:
            f.write("content")
        result = self.service.list_directory(".")
        names = [item["name"] for item in result["items"]]
        self.assertNotIn(".git", names)
        self.assertIn("file.txt", names)

    def test_write_file_creates_file(self):
        result = self.service.write_file("new.txt", "new content")
        self.assertTrue(result["created"])
        self.assertEqual(result["path"], "new.txt")
        with open(os.path.join(self.temp_dir, "new.txt"), "r") as f:
            self.assertEqual(f.read(), "new content")


class TestSessionLifecycleManager(unittest.TestCase):
    def setUp(self):
        self.summary_store = MagicMock()
        self.timeline_store = MagicMock()
        self.plan_store = MagicMock()
        self.project_memory = MagicMock()
        self.session_restorer = MagicMock()
        self.transcript_store = MagicMock()
        self.manager = SessionLifecycleManager(
            session_store=self.summary_store,
            timeline_store=self.timeline_store,
            summary_store=self.summary_store,
            plan_store=self.plan_store,
            project_memory=self.project_memory,
            session_restorer=self.session_restorer,
            transcript_store=self.transcript_store,
        )

    def test_list_sessions_delegates_to_store(self):
        self.summary_store.list_summaries.return_value = [{"id": "1"}]
        result = self.manager.list_sessions(limit=5)
        self.summary_store.list_summaries.assert_called_once_with(limit=5)
        self.assertEqual(result, [{"id": "1"}])

    def test_create_session_state_returns_managed_session(self):
        self.plan_store.load.return_value = None
        state = self.manager.create_session_state(mode="explore")
        self.assertIsNotNone(state.session)
        self.assertEqual(state.current_mode, "explore")

    def test_persist_state_saves_summary(self):
        from embedagent.session import Session
        from embedagent.session_runtime import ManagedSession

        session = Session()
        state = ManagedSession(session=session, current_mode="explore")
        self.summary_store.persist.return_value = "ref123"
        result = self.manager.persist_state(session, "explore", state)
        self.summary_store.persist.assert_called_once_with(session, "explore")
        self.assertEqual(result, "ref123")


class TestHarnessStateSynchronizer(unittest.TestCase):
    def setUp(self):
        self.harness_runner = MagicMock()
        self.synchronizer = HarnessStateSynchronizer(
            harness_runner=self.harness_runner,
            workspace="/tmp/workspace",
        )

    def test_refresh_task_graph_updates_snapshot(self):
        from embedagent.session import Session
        from embedagent.session_runtime import ManagedSession

        session = Session()
        state = ManagedSession(session=session, current_mode="explore")
        graph = MagicMock()
        graph.current_phase = "phase1"
        graph.discipline = "disc1"
        graph.render_summary.return_value = "summary"
        graph.to_items.return_value = []
        context = MagicMock()
        context.current_phase = "phase1"
        context.discipline_label = "disc1"
        context.task_summary = "summary"
        context.task_items = []

        self.harness_runner.update_task_graph.return_value = graph
        self.harness_runner.describe_mode.return_value = context

        with patch("embedagent.services.harness_state_synchronizer.task_store") as mock_task_store:
            self.synchronizer.refresh_task_graph(state)
            mock_task_store.save_task_snapshot.assert_called_once()

    def test_sync_mode_changes_mode(self):
        from embedagent.session import Session
        from embedagent.session_runtime import ManagedSession

        session = Session()
        state = ManagedSession(session=session, current_mode="explore")
        self.synchronizer.sync_mode(state, "build")
        self.assertEqual(state.current_mode, "build")

    def test_build_mode_context_uses_supplied_mode(self):
        from embedagent.session import Session
        from embedagent.session_runtime import ManagedSession

        session = Session()
        state = ManagedSession(session=session, current_mode="explore")
        self.synchronizer.build_mode_context(state, mode="build")

        self.harness_runner.describe_mode.assert_called_once()
        call_args = self.harness_runner.describe_mode.call_args
        self.assertEqual(call_args[0][0], "build")


if __name__ == "__main__":
    unittest.main()
