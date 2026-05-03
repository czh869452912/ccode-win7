import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.tui.views.timeline import FlatTimelineView


class TestFlatTimelineView(unittest.TestCase):
    def setUp(self):
        self.view = FlatTimelineView()

    def test_empty_timeline_renders(self):
        self.view.update({"items": []})
        result = self.view.render()
        self.assertIsNotNone(result)

    def test_user_item_renders(self):
        self.view.update({
            "items": [{"type": "user", "id": "m1", "content": "Hello", "status": "completed", "parent_id": "", "turn_id": "t1"}]
        })
        result = self.view.render()
        self.assertIsNotNone(result)

    def test_tool_use_item_renders(self):
        self.view.update({
            "items": [{"type": "tool_use", "id": "tu1", "content": "", "status": "started", "parent_id": "m1", "turn_id": "t1", "tool_name": "read_file", "call_id": "c1", "arguments": {"path": "test.txt"}}]
        })
        result = self.view.render()
        self.assertIsNotNone(result)

    def test_tool_result_item_renders(self):
        self.view.update({
            "items": [{"type": "tool_result", "id": "tr1", "content": "file content", "status": "success", "parent_id": "tu1", "turn_id": "t1", "tool_name": "read_file", "call_id": "c1", "data": "file content", "error": ""}]
        })
        result = self.view.render()
        self.assertIsNotNone(result)

    def test_multiple_items_render(self):
        self.view.update({
            "items": [
                {"type": "user", "id": "m1", "content": "Read file", "status": "completed", "parent_id": "", "turn_id": "t1"},
                {"type": "tool_use", "id": "tu1", "content": "", "status": "started", "parent_id": "m1", "turn_id": "t1", "tool_name": "read_file", "call_id": "c1", "arguments": {"path": "test.txt"}},
                {"type": "tool_result", "id": "tr1", "content": "content", "status": "success", "parent_id": "tu1", "turn_id": "t1", "tool_name": "read_file", "call_id": "c1", "data": "content", "error": ""},
            ]
        })
        result = self.view.render()
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
