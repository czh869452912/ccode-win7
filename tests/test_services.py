import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.hosting import HostedSessionProjection
from embedagent_host.runtime.services.event_emitter import EventEmitter
from embedagent_host.runtime.services.session_lifecycle import SessionLifecycleManager
from embedagent_host.runtime.services.workspace_file_service import WorkspaceFileService
from embedagent_workflow_cpp.extension import CHarnessWorkflowExtension


class TestEventEmitter(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.sink = SimpleNamespace(on_session_event=self.calls.append)
        self.emitter = EventEmitter(self.sink)

    def test_emit_calls_bound_sink(self):
        self.emitter.emit("test_event", "sess1", {"key": "value"})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0].event_kind, "test.event")
        self.assertEqual(self.calls[0].session_id, "sess1")
        self.assertEqual(self.calls[0].payload, {"key": "value"})

    def test_handler_exception_propagates(self):
        def bad_handler(envelope):
            del envelope
            raise RuntimeError("boom")

        emitter = EventEmitter(SimpleNamespace(on_session_event=bad_handler))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            emitter.emit("test_event", "sess1", {"key": "value"})

    def test_sink_is_construction_bound(self):
        self.assertFalse(hasattr(self.emitter, "add_handler"))
        self.assertFalse(hasattr(self.emitter, "remove_handler"))

    def test_global_handler(self):
        self.emitter.emit("any_event", "sess1", {"key": "value"})
        self.assertEqual(len(self.calls), 1)


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
    def _manager_kwargs(self):
        return {
            "session_store": self.summary_store,
            "summary_store": self.summary_store,
            "plan_store": self.plan_store,
            "transcript_store": self.transcript_store,
            "session_opener": self.session_opener,
        }

    def setUp(self):
        self.summary_store = MagicMock()
        self.plan_store = MagicMock()
        self.transcript_store = MagicMock()
        self.controllers = {}

        def open_session(requested):
            session_id = str(requested or "session-new")
            agent_session = SimpleNamespace(session_id=session_id)
            controller = MagicMock()

            def projection(mode="explore"):
                return HostedSessionProjection(
                    session_id,
                    mode,
                    "idle",
                    None,
                    snapshot={"session_id": session_id, "current_mode": mode},
                    history={"session_id": session_id, "turns": []},
                )

            controller.snapshot.return_value = projection()
            controller.initialize.side_effect = lambda mode, workflow_state: projection(mode)
            self.controllers[session_id] = controller
            return agent_session, controller

        self.session_opener = open_session
        self.manager = SessionLifecycleManager(
            **self._manager_kwargs(),
            mode_resolver=lambda name: {"slug": name} if name in ("explore", "build") else {},
            default_mode="explore",
        )

    def test_mode_policy_is_required(self):
        with self.assertRaises(TypeError):
            SessionLifecycleManager(**self._manager_kwargs())

    def test_invalid_mode_fails_closed_through_resolver(self):
        def resolve_mode(name):
            if name not in ("explore", "build"):
                raise ValueError("invalid mode")
            return {"slug": name}

        manager = SessionLifecycleManager(
            **self._manager_kwargs(),
            mode_resolver=resolve_mode,
            default_mode="explore",
        )

        with self.assertRaisesRegex(ValueError, "invalid mode"):
            manager.create_session_state("bogus")

    def test_list_sessions_delegates_to_store(self):
        self.summary_store.list_summaries.return_value = [{"id": "1"}]
        result = self.manager.list_sessions(limit=5)
        self.summary_store.list_summaries.assert_called_once_with(
            limit=5,
            include_archived=False,
        )
        self.assertEqual(result, [{"id": "1"}])

    def test_thread_lifecycle_delegates_to_summary_store(self):
        self.summary_store.rename_session.return_value = {
            "session_id": "sess-1",
            "title": "Renamed",
        }
        self.summary_store.archive_session.return_value = {
            "session_id": "sess-1",
            "thread": {"archived": True},
        }
        self.summary_store.fork_session.return_value = {"session_id": "sess-2"}

        renamed = self.manager.rename_session("sess-1", "Renamed")
        archived = self.manager.archive_session("sess-1")
        forked = self.manager.fork_session("sess-1", "Copy")

        self.summary_store.rename_session.assert_called_once_with("sess-1", "Renamed")
        self.summary_store.archive_session.assert_called_once_with("sess-1")
        self.summary_store.fork_session.assert_called_once_with("sess-1", title="Copy")
        self.assertEqual(renamed["title"], "Renamed")
        self.assertTrue(archived["thread"]["archived"])
        self.assertEqual(forked["session_id"], "sess-2")

    def test_list_sessions_passes_include_archived(self):
        self.summary_store.list_summaries.return_value = [{"id": "archived"}]

        result = self.manager.list_sessions(limit=20, include_archived=True)

        self.summary_store.list_summaries.assert_called_once_with(
            limit=20,
            include_archived=True,
        )
        self.assertEqual(result, [{"id": "archived"}])

    def test_create_session_state_returns_managed_session(self):
        self.plan_store.load.return_value = None
        state = self.manager.create_session_state(mode="explore")
        self.assertEqual(state.session_id, "session-new")
        self.assertEqual(state.current_mode, "explore")
        self.assertEqual(state.workflow_state, "")

    def test_restore_resolves_reference_before_controller_restore(self):
        self.summary_store.resolve_transcript_path.return_value = "transcript-reference"
        self.transcript_store.session_id_for_reference.return_value = "session-one"
        self.manager.restore_session_state("latest")
        controller = self.controllers["session-one"]

        self.transcript_store.session_id_for_reference.assert_called_once_with(
            "transcript-reference"
        )
        controller.snapshot.assert_called_once_with()
        controller.initialize.assert_called_once_with("explore", "")
        self.transcript_store.load_events.assert_not_called()
        self.transcript_store.load_events_from_reference.assert_not_called()

    def test_persist_state_saves_summary(self):
        from embedagent_host.runtime.session_runtime import ManagedSession

        state = ManagedSession(session_id="session-one", current_mode="explore")
        self.summary_store.load_summary.return_value = {"summary_ref": "ref123"}
        result = self.manager.persist_state(state)
        self.summary_store.load_summary.assert_called_once_with("session-one")
        self.assertEqual(result, "ref123")


class TestHarnessWorkflowExtensionRefresh(unittest.TestCase):
    def setUp(self):
        self.harness_runner = MagicMock()
        self.extension = CHarnessWorkflowExtension(harness_runner=self.harness_runner)

    def test_refresh_task_graph_updates_snapshot(self):
        from embedagent_host.runtime.session_runtime import ManagedSession

        state = ManagedSession(
            session_id="session-one",
            current_mode="explore",
            projection={
                "workflow_state": {
                    "workflow": {
                        "summary": "summary",
                        "items": [],
                        "metadata": {
                            "current_phase": "phase1",
                            "discipline_profile": "disc1",
                        },
                    }
                }
            },
        )

        mock_task_store = MagicMock()
        self.extension.refresh_managed_session(
            state,
            "/tmp/workspace",
            task_store_module=mock_task_store,
        )
        mock_task_store.save_task_snapshot.assert_called_once_with(
            "/tmp/workspace",
            "session-one",
            "explore",
            "",
            "disc1",
            "phase1",
            "summary",
            [],
        )

        mock_task_store.save_task_snapshot.assert_called_once()

    def test_build_mode_context_uses_supplied_mode(self):
        from embedagent_core.session import Session

        session = Session()
        self.extension.build_mode_context(session, current_mode="build")

        self.harness_runner.describe_mode.assert_called_once()
        call_args = self.harness_runner.describe_mode.call_args
        self.assertEqual(call_args[0][0], "build")


if __name__ == "__main__":
    unittest.main()
