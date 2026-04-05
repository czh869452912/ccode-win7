import os
import shutil
import tempfile
import unittest

from embedagent.tool_result_store import ToolResultStore


class TestToolResultStore(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-tool-results-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.store = ToolResultStore(self.workspace)

    def test_write_text_field_is_session_local_and_write_once(self):
        first = self.store.write_text(
            session_id="s-1",
            tool_call_id="call-1",
            field_name="content",
            text="hello\nworld",
        )
        second = self.store.write_text(
            session_id="s-1",
            tool_call_id="call-1",
            field_name="content",
            text="DIFFERENT",
        )
        self.assertEqual(first.relative_path, second.relative_path)
        self.assertTrue(first.relative_path.endswith("tool-results/call-1/content.txt"))
        with open(first.absolute_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "hello\nworld")


if __name__ == "__main__":
    unittest.main()
