import os
import sys
import unittest
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytestmark = pytest.mark.harness


class TaskGraphV2Tests(unittest.TestCase):
    def test_c_cpp_workflow_extension_owns_task_graph_without_session_field(self):
        from embedagent_core.session import Observation, Session
        from embedagent_host.runtime.session_runtime import ManagedSession
        from embedagent_workflow_cpp.extension import CHarnessWorkflowExtension

        extension = CHarnessWorkflowExtension()
        session = Session()

        patch = extension.initialize_workflow_state(
            session,
            user_text="build the demo program",
            current_mode="build",
            workflow_state="chat",
        )

        self.assertFalse(hasattr(session, "task_graph"))
        self.assertEqual(session.workflow_state, {})
        self.assertIsNotNone(patch)
        self.assertIn("summary", patch.workflow)

        managed = ManagedSession(
            session_id=session.session_id,
            current_mode="build",
            projection={
                "workflow_state": {
                    "workflow": dict(patch.workflow),
                }
            },
            workflow_state="chat",
        )
        task_store = MagicMock()
        extension.refresh_managed_session(
            managed,
            os.getcwd(),
            observations=[Observation("run_recipe", True, None, {"recipe_id": "unit"})],
            task_store_module=task_store,
        )

        task_store.save_task_snapshot.assert_called_once()
        saved = task_store.save_task_snapshot.call_args.args
        self.assertEqual(saved[1], session.session_id)
        self.assertTrue(saved[6])
        self.assertTrue(saved[7])
        kwargs = task_store.save_task_snapshot.call_args.kwargs
        self.assertEqual(kwargs["snapshot_schema_version"], 2)
        self.assertTrue(kwargs["workflow_fingerprint"])

    def test_new_graph_starts_with_single_active_task(self):
        from embedagent_workflow_cpp.task_graph import TaskGraph

        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        self.assertEqual(len(graph.tasks), 1)
        self.assertEqual(graph.tasks[0].status, "in_progress")

    def test_graph_can_be_rebuilt_from_workflow_projection(self):
        from embedagent_core.session import Session
        from embedagent_workflow_cpp.session_graph_state import HarnessSessionGraphState
        from embedagent_workflow_cpp.task_graph import TaskGraph

        source = TaskGraph.for_mode("build", "full_spec_tdd", current_phase="contract")
        session = Session()
        session.workflow_state["workflow"] = {
            "summary": source.render_summary(),
            "items": source.to_items(),
            "metadata": {
                "current_phase": source.current_phase,
                "discipline_profile": source.discipline,
            },
        }

        graph = HarnessSessionGraphState().get(session)

        self.assertIsNotNone(graph)
        self.assertEqual(graph.mode_name, "build")
        self.assertEqual(graph.current_phase, "contract")
        self.assertEqual(graph.to_items(), source.to_items())

    def test_initialize_does_not_publish_graph_before_workflow_patch_commit(self):
        from embedagent_core.session import Session
        from embedagent_workflow_cpp.extension import CHarnessWorkflowExtension

        extension = CHarnessWorkflowExtension()
        session = Session()

        patch = extension.initialize_workflow_state(
            session,
            user_text="build the demo program",
            current_mode="build",
            workflow_state="chat",
        )

        self.assertIsNotNone(patch)
        self.assertEqual(session.workflow_state, {})
        self.assertIsNone(extension.graph_state.get(session))

    def test_graph_can_advance_task_status(self):
        from embedagent_workflow_cpp.task_graph import TaskGraph

        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        graph.complete_current("contract ready")
        self.assertEqual(graph.tasks[0].status, "completed")

    def test_graph_summary_is_stable_text(self):
        from embedagent_workflow_cpp.task_graph import TaskGraph

        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        summary = graph.render_summary()
        self.assertIn("in_progress", summary)


if __name__ == "__main__":
    unittest.main()
