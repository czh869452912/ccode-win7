import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.tui.views.diff import DiffView


class TestDiffView(unittest.TestCase):
    def setUp(self):
        self.view = DiffView()

    def test_empty_diff_renders(self):
        result = self.view.render()
        self.assertIsNotNone(result)

    def test_simple_diff_renders(self):
        self.view.set_diff(
            "def old():\n    pass\n",
            "def new():\n    return 42\n",
            "test.py",
        )
        result = self.view.render()
        self.assertIsNotNone(result)

    def test_diff_detects_language(self):
        self.view.set_diff("", "", "test.py")
        self.assertEqual(self.view._language, "python")

        self.view.set_diff("", "", "test.c")
        self.assertEqual(self.view._language, "c")

    def test_inline_render(self):
        result = self.view.render_inline(
            "line1\nline2\n",
            "line1\nmodified\nline3\n",
            "file.txt",
        )
        self.assertIsNotNone(result)

    def test_theme_colors(self):
        from embedagent.frontend.tui.theme import get_diff_theme

        dark = get_diff_theme("dark")
        light = get_diff_theme("light")
        self.assertNotEqual(dark["addition_fg"], light["addition_fg"])


if __name__ == "__main__":
    unittest.main()
