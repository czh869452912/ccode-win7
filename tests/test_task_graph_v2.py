import os
import sys
import unittest

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

        extension.initialize_workflow_state(
            session,
            user_text="build the demo program",
            current_mode="build",
            workflow_state="chat",
        )

        self.assertFalse(hasattr(session, "task_graph"))
        self.assertIn("workflow", session.workflow_state)
        self.assertIn("summary", session.workflow_state["workflow"])

        managed = ManagedSession(
            session=session,
            current_mode="build",
            workflow_state="chat",
        )
        extension.refresh_managed_session(
            managed,
            os.getcwd(),
            observations=[Observation("run_recipe", True, None, {"recipe_id": "unit"})],
        )

        workflow = session.workflow_state["workflow"]
        self.assertTrue(workflow["summary"])
        self.assertTrue(workflow["items"])

    def test_new_graph_starts_with_single_active_task(self):
        from embedagent_workflow_cpp.task_graph import TaskGraph

        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        self.assertEqual(len(graph.tasks), 1)
        self.assertEqual(graph.tasks[0].status, "in_progress")

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
