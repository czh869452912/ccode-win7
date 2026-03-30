"""Tests for manage_todos tool."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.tools import ToolRuntime


class TestManageTodos(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.rt = ToolRuntime(self.workspace)

    def _exec(self, **kwargs):
        return self.rt.execute("manage_todos", kwargs)

    def test_list_empty(self):
        obs = self._exec(action="list")
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["count"], 0)
        self.assertEqual(obs.data["todos"], [])

    def test_add_single(self):
        obs = self._exec(action="add", content="实现登录接口")
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["id"], 1)
        self.assertEqual(obs.data["content"], "实现登录接口")

    def test_add_multiple_ids_increment(self):
        self._exec(action="add", content="任务1")
        obs2 = self._exec(action="add", content="任务2")
        self.assertEqual(obs2.data["id"], 2)
        obs3 = self._exec(action="add", content="任务3")
        self.assertEqual(obs3.data["id"], 3)

    def test_list_after_add(self):
        self._exec(action="add", content="任务A")
        self._exec(action="add", content="任务B")
        obs = self._exec(action="list")
        self.assertEqual(obs.data["count"], 2)
        texts = [t["content"] for t in obs.data["todos"]]
        self.assertIn("任务A", texts)
        self.assertIn("任务B", texts)

    def test_add_without_content_fails(self):
        obs = self._exec(action="add")
        self.assertFalse(obs.success)
        self.assertIn("content", obs.error)

    def test_complete_marks_done(self):
        self._exec(action="add", content="任务1")
        self._exec(action="add", content="任务2")
        obs = self._exec(action="complete", item_id=1)
        self.assertTrue(obs.success)
        # Verify via list
        list_obs = self._exec(action="list")
        todos = {t["id"]: t for t in list_obs.data["todos"]}
        self.assertTrue(todos[1]["done"])
        self.assertFalse(todos[2]["done"])

    def test_complete_nonexistent_id_fails(self):
        obs = self._exec(action="complete", item_id=99)
        self.assertFalse(obs.success)
        self.assertIn("99", obs.error)

    def test_complete_without_item_id_fails(self):
        obs = self._exec(action="complete")
        self.assertFalse(obs.success)

    def test_remove_deletes_item(self):
        self._exec(action="add", content="任务1")
        self._exec(action="add", content="任务2")
        obs = self._exec(action="remove", item_id=1)
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["remaining"], 1)
        list_obs = self._exec(action="list")
        self.assertEqual(list_obs.data["count"], 1)
        self.assertEqual(list_obs.data["todos"][0]["content"], "任务2")

    def test_remove_renumbers_remaining(self):
        self._exec(action="add", content="任务1")
        self._exec(action="add", content="任务2")
        self._exec(action="add", content="任务3")
        self._exec(action="remove", item_id=2)
        list_obs = self._exec(action="list")
        ids = [t["id"] for t in list_obs.data["todos"]]
        self.assertEqual(sorted(ids), [1, 2])

    def test_remove_nonexistent_id_fails(self):
        obs = self._exec(action="remove", item_id=99)
        self.assertFalse(obs.success)

    def test_remove_without_item_id_fails(self):
        obs = self._exec(action="remove")
        self.assertFalse(obs.success)

    def test_invalid_action_fails(self):
        obs = self._exec(action="unknown")
        self.assertFalse(obs.success)

    def test_persisted_to_json(self):
        self._exec(action="add", content="持久化测试")
        todos_path = os.path.join(self.workspace, ".embedagent", "todos.json")
        self.assertTrue(os.path.exists(todos_path))
        with open(todos_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "持久化测试")

    def test_persisted_across_runtime_instances(self):
        self._exec(action="add", content="跨实例任务")
        # Create a new ToolRuntime pointing to same workspace
        rt2 = ToolRuntime(self.workspace)
        obs = rt2.execute("manage_todos", {"action": "list"})
        self.assertEqual(obs.data["count"], 1)
        self.assertEqual(obs.data["todos"][0]["content"], "跨实例任务")

    def test_full_workflow(self):
        """Add 3 todos, complete #2, remove #1, verify final state."""
        self._exec(action="add", content="步骤1")
        self._exec(action="add", content="步骤2")
        self._exec(action="add", content="步骤3")
        self._exec(action="complete", item_id=2)
        self._exec(action="remove", item_id=1)
        final = self._exec(action="list")
        self.assertEqual(final.data["count"], 2)
        todos = {t["id"]: t for t in final.data["todos"]}
        # After renumber, remaining items are id=1 (步骤2) and id=2 (步骤3)
        contents = {t["content"] for t in final.data["todos"]}
        self.assertIn("步骤2", contents)
        self.assertIn("步骤3", contents)
        done_todos = [t for t in final.data["todos"] if t["done"]]
        self.assertEqual(len(done_todos), 1)
        self.assertEqual(done_todos[0]["content"], "步骤2")

    def test_session_scoped_todos_do_not_overlap(self):
        self._exec(action="add", content="会话A任务", session_id="sess-a")
        self._exec(action="add", content="会话B任务", session_id="sess-b")
        todos_a = self._exec(action="list", session_id="sess-a")
        todos_b = self._exec(action="list", session_id="sess-b")
        self.assertEqual(todos_a.data["count"], 1)
        self.assertEqual(todos_b.data["count"], 1)
        self.assertEqual(todos_a.data["todos"][0]["content"], "会话A任务")
        self.assertEqual(todos_b.data["todos"][0]["content"], "会话B任务")


if __name__ == "__main__":
    unittest.main()
