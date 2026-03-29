"""Tests for the tools/ package refactoring and ToolRuntime."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.tools import ToolRuntime, ToolDefinition


class TestToolRuntimeImport(unittest.TestCase):
    def test_import_from_package(self):
        # The original import path must still work
        from embedagent.tools import ToolRuntime as RT
        self.assertIs(RT, ToolRuntime)

    def test_tool_definition_importable(self):
        from embedagent.tools import ToolDefinition as TD
        self.assertIs(TD, ToolDefinition)


class TestToolRuntimeInit(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.rt = ToolRuntime(self.workspace)

    def test_workspace_is_realpath(self):
        self.assertEqual(self.rt.workspace, os.path.realpath(self.workspace))

    def test_artifact_store_exposed(self):
        self.assertIsNotNone(self.rt.artifact_store)

    def test_app_config_default_none(self):
        self.assertIsNone(self.rt.app_config)

    def test_app_config_passed_through(self):
        from embedagent.config import AppConfig
        cfg = AppConfig(max_context_tokens=32000)
        rt = ToolRuntime(self.workspace, app_config=cfg)
        self.assertIs(rt.app_config, cfg)


class TestToolRuntimeSchemas(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.rt = ToolRuntime(self.workspace)
        self.schemas = self.rt.schemas()
        self.tool_names = [s["function"]["name"] for s in self.schemas]

    def test_total_tool_count(self):
        self.assertEqual(len(self.schemas), 16)

    def test_all_original_tools_present(self):
        expected = [
            "read_file", "list_files", "search_text", "write_file", "edit_file",
            "run_command",
            "git_status", "git_diff", "git_log",
            "compile_project", "run_tests", "run_clang_tidy",
            "run_clang_analyzer", "collect_coverage", "report_quality",
        ]
        for name in expected:
            self.assertIn(name, self.tool_names, "Missing tool: %s" % name)

    def test_manage_todos_present(self):
        self.assertIn("manage_todos", self.tool_names)

    def test_schema_structure(self):
        for schema in self.schemas:
            self.assertEqual(schema["type"], "function")
            func = schema["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)
            self.assertEqual(func["parameters"]["type"], "object")
            self.assertIn("required", func["parameters"])


class TestToolRuntimeExecute(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.rt = ToolRuntime(self.workspace)

    def test_unknown_tool_returns_error(self):
        obs = self.rt.execute("nonexistent_tool", {})
        self.assertFalse(obs.success)
        self.assertIsNotNone(obs.error)
        self.assertEqual(obs.tool_name, "nonexistent_tool")

    def test_invalid_arguments_type_returns_error(self):
        obs = self.rt.execute("read_file", "not a dict")
        self.assertFalse(obs.success)

    def test_read_file_workspace_file(self):
        test_file = os.path.join(self.workspace, "hello.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("hello world")
        obs = self.rt.execute("read_file", {"path": "hello.txt"})
        self.assertTrue(obs.success)
        self.assertIn("hello world", obs.data["content"])

    def test_read_file_outside_workspace_blocked(self):
        obs = self.rt.execute("read_file", {"path": "/etc/passwd"})
        self.assertFalse(obs.success)

    def test_list_files_workspace_root(self):
        # Create a file so the directory isn't empty
        with open(os.path.join(self.workspace, "test.txt"), "w") as f:
            f.write("x")
        obs = self.rt.execute("list_files", {"path": "."})
        self.assertTrue(obs.success)
        self.assertIn("files", obs.data)

    def test_search_text_in_workspace(self):
        test_file = os.path.join(self.workspace, "code.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def my_function():\n    pass\n")
        obs = self.rt.execute("search_text", {"query": "my_function", "path": "."})
        self.assertTrue(obs.success)
        self.assertGreater(obs.data["match_count"], 0)

    def test_edit_file_replaces_text(self):
        test_file = os.path.join(self.workspace, "edit_me.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        obs = self.rt.execute("edit_file", {
            "path": "edit_me.py",
            "old_text": "x = 1",
            "new_text": "x = 2",
        })
        self.assertTrue(obs.success)
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("x = 2", content)

    def test_write_file_creates_new_file(self):
        obs = self.rt.execute("write_file", {
            "path": "docs/requirements.md",
            "content": "# Requirements\n",
        })
        self.assertTrue(obs.success)
        self.assertTrue(obs.data["created"])
        with open(os.path.join(self.workspace, "docs", "requirements.md"), "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "# Requirements\n")

    def test_write_file_blocks_existing_without_overwrite(self):
        test_file = os.path.join(self.workspace, "existing.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("old\n")
        obs = self.rt.execute("write_file", {
            "path": "existing.txt",
            "content": "new\n",
        })
        self.assertFalse(obs.success)

    def test_observation_tool_name_set(self):
        obs = self.rt.execute("manage_todos", {"action": "list"})
        self.assertEqual(obs.tool_name, "manage_todos")


class TestModuleIsolation(unittest.TestCase):
    """Verify each ops module can be imported independently."""
    def test_file_ops_importable(self):
        from embedagent.tools import file_ops
        self.assertTrue(callable(file_ops.build_tools))

    def test_shell_ops_importable(self):
        from embedagent.tools import shell_ops
        self.assertTrue(callable(shell_ops.build_tools))

    def test_git_ops_importable(self):
        from embedagent.tools import git_ops
        self.assertTrue(callable(git_ops.build_tools))

    def test_build_ops_importable(self):
        from embedagent.tools import build_ops
        self.assertTrue(callable(build_ops.build_tools))

    def test_todo_ops_importable(self):
        from embedagent.tools import todo_ops
        self.assertTrue(callable(todo_ops.build_tools))

    def test_base_importable(self):
        from embedagent.tools._base import ToolContext, ToolDefinition, ToolError
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
