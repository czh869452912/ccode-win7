"""Tests for multi-search-replace diff engine."""

import unittest

from embedagent.strategies.diff_engine import DiffBlock, MultiSearchReplaceDiffEngine


class TestMultiSearchReplaceDiffEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MultiSearchReplaceDiffEngine()

    def test_single_exact_match(self):
        content = "def foo():\n    pass\n"
        block = DiffBlock(old_text="def foo():\n    pass", new_text="def bar():\n    return 1")
        updated, results = self.engine.apply_diff(content, [block])
        self.assertEqual(results[0]["status"], "applied")
        self.assertEqual(updated, "def bar():\n    return 1\n")

    def test_multiple_blocks_applied(self):
        content = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        blocks = [
            DiffBlock(old_text="def foo():\n    pass", new_text="def foo():\n    return 1"),
            DiffBlock(old_text="def bar():\n    pass", new_text="def bar():\n    return 2"),
        ]
        updated, results = self.engine.apply_diff(content, blocks)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "applied" for r in results))
        self.assertIn("def foo():\n    return 1", updated)
        self.assertIn("def bar():\n    return 2", updated)

    def test_fuzzy_match_whitespace_variation(self):
        content = "def foo():\n    x = 1\n"
        # Different indentation in old_text
        block = DiffBlock(old_text="def foo():\n  x = 1", new_text="def foo():\n    y = 2")
        updated, results = self.engine.apply_diff(content, [block])
        self.assertEqual(results[0]["status"], "applied")
        self.assertEqual(updated, "def foo():\n    y = 2\n")

    def test_expected_start_line_disambiguation(self):
        content = "def foo():\n    pass\n\ndef foo():\n    pass\n"
        blocks = [
            DiffBlock(old_text="def foo():\n    pass", new_text="def first():\n    pass", expected_start_line=0),
            DiffBlock(old_text="def foo():\n    pass", new_text="def second():\n    pass", expected_start_line=3),
        ]
        updated, results = self.engine.apply_diff(content, blocks)
        self.assertEqual(len([r for r in results if r["status"] == "applied"]), 2)
        self.assertIn("def first():", updated)
        self.assertIn("def second():", updated)

    def test_overlapping_blocks_rejected(self):
        content = "def foo():\n    pass\n"
        blocks = [
            DiffBlock(old_text="def foo():\n    pass", new_text="def bar():\n    pass"),
            DiffBlock(old_text="def foo():\n    pass", new_text="def baz():\n    pass"),
        ]
        updated, results = self.engine.apply_diff(content, blocks)
        # Overlap detection should catch this
        self.assertTrue(any(r["status"] == "failed" for r in results))

    def test_partial_failure_recorded(self):
        content = "def foo():\n    pass\n"
        blocks = [
            DiffBlock(old_text="def foo():\n    pass", new_text="def bar():\n    pass"),
            DiffBlock(old_text="nonexistent", new_text="something"),
        ]
        updated, results = self.engine.apply_diff(content, blocks)
        self.assertEqual(results[0]["status"], "applied")
        self.assertEqual(results[1]["status"], "failed")

    def test_empty_old_text_rejected(self):
        content = "def foo():\n    pass\n"
        block = DiffBlock(old_text="", new_text="something")
        updated, results = self.engine.apply_diff(content, [block])
        self.assertEqual(results[0]["status"], "failed")

    def test_preview_does_not_modify(self):
        content = "def foo():\n    pass\n"
        block = DiffBlock(old_text="def foo():\n    pass", new_text="def bar():\n    pass")
        results = self.engine.preview_diff(content, [block])
        self.assertEqual(content, "def foo():\n    pass\n")  # Original unchanged
        self.assertEqual(results[0]["status"], "applied")


class TestDiffSuccessRate(unittest.TestCase):
    def setUp(self):
        self.engine = MultiSearchReplaceDiffEngine()

    def test_realistic_code_editing_scenarios(self):
        scenarios = [
            # Simple variable rename
            ("x = 1\n", "x = 1", "y = 1", "y = 1\n"),
            # Function parameter addition
            ("def foo():\n    pass\n", "def foo():", "def foo(x):", "def foo(x):\n    pass\n"),
            # Import statement modification
            ("import os\n", "import os", "import sys", "import sys\n"),
            # Class method addition
            ("class Foo:\n    pass\n", "    pass", "    def bar(self):\n        pass", "class Foo:\n    def bar(self):\n        pass\n"),
            # Conditional branch modification
            ("if x:\n    pass\n", "if x:", "if y:", "if y:\n    pass\n"),
            # Loop variable rename
            ("for i in range(10):\n    pass\n", "for i in range(10):", "for j in range(10):", "for j in range(10):\n    pass\n"),
            # Return statement change
            ("return 1\n", "return 1", "return 2", "return 2\n"),
            # Exception handling addition
            ("try:\n    pass\nexcept:\n    pass\n", "except:", "except ValueError:", "try:\n    pass\nexcept ValueError:\n    pass\n"),
            # Docstring addition
            ("def foo():\n    pass\n", "def foo():", 'def foo():\n    """Doc."""', 'def foo():\n    """Doc."""\n    pass\n'),
            # Type hint addition
            ("def foo(x):\n    pass\n", "def foo(x):", "def foo(x: int):", "def foo(x: int):\n    pass\n"),
            # Decorator addition
            ("def foo():\n    pass\n", "def foo():", "@decorator\ndef foo():", "@decorator\ndef foo():\n    pass\n"),
            # Logging statement insertion
            ("x = 1\n", "x = 1", "import logging\nx = 1", "import logging\nx = 1\n"),
            # Configuration constant change
            ("MAX = 10\n", "MAX = 10", "MAX = 20", "MAX = 20\n"),
            # API endpoint URL change
            ('url = "/api/v1"\n', 'url = "/api/v1"', 'url = "/api/v2"', 'url = "/api/v2"\n'),
            # File path update
            ('path = "/old"\n', 'path = "/old"', 'path = "/new"', 'path = "/new"\n'),
            # Format string modification
            ('f"hello {name}"\n', 'f"hello {name}"', 'f"hi {name}"', 'f"hi {name}"\n'),
            # List comprehension to loop
            ("[x for x in range(10)]\n", "[x for x in range(10)]", "for x in range(10):\n    print(x)", "for x in range(10):\n    print(x)\n"),
            # Dictionary key rename
            ('{"old": 1}\n', '"old": 1', '"new": 1', '{"new": 1}\n'),
            # Boolean flag inversion
            ("flag = True\n", "flag = True", "flag = False", "flag = False\n"),
            # Callback function replacement
            ("cb = old_fn\n", "cb = old_fn", "cb = new_fn", "cb = new_fn\n"),
        ]

        success_count = 0
        for content, old_text, new_text, expected in scenarios:
            block = DiffBlock(old_text=old_text, new_text=new_text)
            updated, results = self.engine.apply_diff(content, [block])
            if results[0]["status"] == "applied" and updated == expected:
                success_count += 1

        total = len(scenarios)
        success_rate = success_count / total
        self.assertGreaterEqual(
            success_rate, 0.95,
            f"Success rate {success_rate:.0%} below 95% ({success_count}/{total})"
        )

    def test_backward_compatibility_single_replace(self):
        content = "def foo():\n    pass\n"
        block = DiffBlock(old_text="def foo():\n    pass", new_text="def bar():\n    pass")
        updated, results = self.engine.apply_diff(content, [block])
        self.assertEqual(results[0]["status"], "applied")
        self.assertEqual(updated, "def bar():\n    pass\n")


if __name__ == "__main__":
    unittest.main()
