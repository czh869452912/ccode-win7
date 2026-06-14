import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.tui.views.timeline import FlatTimelineView


class TestStreamingUpdates(unittest.TestCase):
    def setUp(self):
        self.view = FlatTimelineView()

    def test_command_execution_starts_empty(self):
        self.view.update(
            {
                "items": [
                    {
                        "type": "command_execution",
                        "id": "cmd1",
                        "content": "",
                        "status": "started",
                        "parent_id": "",
                        "turn_id": "t1",
                    }
                ]
            }
        )
        item = self.view._items[0]
        self.assertEqual(item["content"], "")
        self.assertEqual(item["status"], "started")

    def test_update_command_output_appends(self):
        self.view.update(
            {
                "items": [
                    {
                        "type": "command_execution",
                        "id": "cmd1",
                        "content": "",
                        "status": "started",
                        "parent_id": "",
                        "turn_id": "t1",
                    }
                ]
            }
        )
        result = self.view.update_command_output("cmd1", "line1\n")
        self.assertTrue(result)
        self.assertEqual(self.view._items[0]["content"], "line1\n")
        self.assertEqual(self.view._items[0]["status"], "running")

    def test_multiple_chunks_append(self):
        self.view.update(
            {
                "items": [
                    {
                        "type": "command_execution",
                        "id": "cmd1",
                        "content": "",
                        "status": "started",
                        "parent_id": "",
                        "turn_id": "t1",
                    }
                ]
            }
        )
        self.view.update_command_output("cmd1", "line1\n")
        self.view.update_command_output("cmd1", "line2\n")
        self.assertEqual(self.view._items[0]["content"], "line1\nline2\n")

    def test_mark_command_complete(self):
        self.view.update(
            {
                "items": [
                    {
                        "type": "command_execution",
                        "id": "cmd1",
                        "content": "done",
                        "status": "running",
                        "parent_id": "",
                        "turn_id": "t1",
                    }
                ]
            }
        )
        result = self.view.mark_command_complete("cmd1")
        self.assertTrue(result)
        self.assertEqual(self.view._items[0]["status"], "completed")

    def test_update_missing_item_returns_false(self):
        result = self.view.update_command_output("nonexistent", "data")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
