import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TaskGraphV2Tests(unittest.TestCase):
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
