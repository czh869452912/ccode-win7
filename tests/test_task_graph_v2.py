import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TaskGraphV2Tests(unittest.TestCase):
    def test_session_starts_with_empty_task_graph(self):
        from embedagent.harness.task_graph import TaskGraph
        from embedagent.session import Session

        session = Session()
        self.assertIsInstance(session.task_graph, TaskGraph)
        self.assertEqual(session.task_graph.tasks, [])

    def test_runner_update_task_graph_mutates_session_graph_in_place(self):
        from embedagent.harness.runner import HarnessRunner
        from embedagent.session import Observation, Session

        runner = HarnessRunner()
        session = Session()
        graph = session.task_graph

        runner.update_task_graph(
            session, "build", [Observation("run_recipe", True, None, {"recipe_id": "unit"})]
        )

        self.assertIs(session.task_graph, graph)
        self.assertGreaterEqual(len(session.task_graph.tasks), 1)
        self.assertEqual(session.task_graph.tasks[0].status, "in_progress")

    def test_new_graph_starts_with_single_active_task(self):
        from embedagent.harness.task_graph import TaskGraph

        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        self.assertEqual(len(graph.tasks), 1)
        self.assertEqual(graph.tasks[0].status, "in_progress")

    def test_graph_can_advance_task_status(self):
        from embedagent.harness.task_graph import TaskGraph

        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        graph.complete_current("contract ready")
        self.assertEqual(graph.tasks[0].status, "completed")

    def test_graph_summary_is_stable_text(self):
        from embedagent.harness.task_graph import TaskGraph

        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        summary = graph.render_summary()
        self.assertIn("in_progress", summary)


if __name__ == "__main__":
    unittest.main()
