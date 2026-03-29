"""Tests for embedagent.modes module."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.config import AppConfig
from embedagent.modes import (
    allowed_tools_for,
    build_system_prompt,
    get_writable_globs,
    is_path_writable,
    mode_names,
    parse_mode_command,
    require_mode,
)


class TestModeRegistry(unittest.TestCase):
    def test_all_expected_modes_present(self):
        names = mode_names()
        for m in ("ask", "orchestra", "spec", "code", "test", "verify", "debug", "compact"):
            self.assertIn(m, names)

    def test_require_mode_invalid_raises(self):
        with self.assertRaises(ValueError):
            require_mode("nonexistent_mode")


class TestAllowedTools(unittest.TestCase):
    def test_switch_mode_always_present(self):
        for m in mode_names():
            self.assertIn("switch_mode", allowed_tools_for(m))

    def test_orchestra_has_manage_todos(self):
        tools = allowed_tools_for("orchestra")
        self.assertIn("manage_todos", tools)

    def test_orchestra_does_not_have_git_status(self):
        tools = allowed_tools_for("orchestra")
        self.assertNotIn("git_status", tools)

    def test_code_has_manage_todos(self):
        self.assertIn("manage_todos", allowed_tools_for("code"))

    def test_ask_is_read_only_tools(self):
        tools = allowed_tools_for("ask")
        for write_tool in ("edit_file", "run_command", "compile_project"):
            self.assertNotIn(write_tool, tools)

    def test_verify_has_no_edit_file(self):
        self.assertNotIn("edit_file", allowed_tools_for("verify"))


class TestWritableGlobs(unittest.TestCase):
    def test_read_only_modes_have_empty_globs(self):
        for m in ("ask", "orchestra", "verify", "compact"):
            self.assertEqual(get_writable_globs(m), [])

    def test_code_mode_default_globs(self):
        globs = get_writable_globs("code")
        self.assertIn("**/*.py", globs)
        self.assertIn("**/*.c", globs)
        self.assertIn("**/*.h", globs)

    def test_spec_mode_default_globs(self):
        globs = get_writable_globs("spec")
        self.assertIn("**/*.md", globs)
        self.assertIn("**/*.rst", globs)

    def test_config_override_replaces_defaults(self):
        cfg = AppConfig(mode_writable_globs={"code": ["app/**/*.py"]})
        globs = get_writable_globs("code", cfg)
        self.assertEqual(globs, ["app/**/*.py"])

    def test_config_override_only_affects_specified_mode(self):
        cfg = AppConfig(mode_writable_globs={"code": ["app/**/*.py"]})
        spec_globs = get_writable_globs("spec", cfg)
        self.assertIn("**/*.md", spec_globs)

    def test_config_none_uses_defaults(self):
        default_globs = get_writable_globs("code")
        globs_with_none = get_writable_globs("code", None)
        self.assertEqual(default_globs, globs_with_none)


class TestIsPathWritable(unittest.TestCase):
    # --- relaxed default patterns ---
    def test_python_file_in_any_dir(self):
        self.assertTrue(is_path_writable("code", "scripts/build.py"))
        self.assertTrue(is_path_writable("code", "src/main.py"))
        self.assertTrue(is_path_writable("code", "app/models/user.py"))

    def test_c_file_in_any_dir(self):
        self.assertTrue(is_path_writable("code", "src/main.c"))
        self.assertTrue(is_path_writable("code", "lib/utils.c"))

    def test_markdown_in_spec_mode(self):
        self.assertTrue(is_path_writable("spec", "README.md"))
        self.assertTrue(is_path_writable("spec", "docs/README.md"))
        self.assertTrue(is_path_writable("spec", "wiki/design.md"))
        self.assertTrue(is_path_writable("spec", "ADR/001-decision.rst"))

    def test_root_toml_in_code_mode(self):
        self.assertTrue(is_path_writable("code", "pyproject.toml"))

    def test_root_python_in_code_mode(self):
        self.assertTrue(is_path_writable("code", "manage.py"))

    def test_markdown_blocked_in_code_mode(self):
        self.assertFalse(is_path_writable("code", "README.md"))

    def test_python_blocked_in_spec_mode(self):
        self.assertFalse(is_path_writable("spec", "src/main.py"))

    def test_read_only_mode_blocks_everything(self):
        for path in ("src/main.py", "README.md", "src/main.c"):
            self.assertFalse(is_path_writable("ask", path))
            self.assertFalse(is_path_writable("verify", path))

    # --- config override ---
    def test_config_override_restricts_to_subdirectory(self):
        cfg = AppConfig(mode_writable_globs={"code": ["src/*.py", "src/**/*.py"]})
        self.assertTrue(is_path_writable("code", "src/main.py", cfg))
        self.assertFalse(is_path_writable("code", "scripts/build.py", cfg))

    def test_config_override_empty_list_means_readonly(self):
        cfg = AppConfig(mode_writable_globs={"code": []})
        self.assertFalse(is_path_writable("code", "src/main.py", cfg))

    def test_windows_backslash_normalized(self):
        self.assertTrue(is_path_writable("code", "src\\main.py"))


class TestBuildSystemPrompt(unittest.TestCase):
    def test_prompt_contains_mode_name(self):
        prompt = build_system_prompt("code")
        self.assertIn("code", prompt)

    def test_prompt_contains_manage_todos_in_orchestra(self):
        prompt = build_system_prompt("orchestra")
        self.assertIn("manage_todos", prompt)

    def test_prompt_shows_readonly_for_ask(self):
        prompt = build_system_prompt("ask")
        self.assertIn("只读", prompt)

    def test_config_override_reflected_in_prompt(self):
        cfg = AppConfig(mode_writable_globs={"code": ["custom/**/*.py"]})
        prompt = build_system_prompt("code", cfg)
        self.assertIn("custom/**/*.py", prompt)


class TestParseModeCommand(unittest.TestCase):
    def test_mode_command_parsed(self):
        mode, msg, switched = parse_mode_command("/mode code 实现登录接口")
        self.assertEqual(mode, "code")
        self.assertEqual(msg, "实现登录接口")
        self.assertTrue(switched)

    def test_no_command_returns_fallback(self):
        mode, msg, switched = parse_mode_command("普通消息", fallback_mode="ask")
        self.assertEqual(mode, "ask")
        self.assertFalse(switched)

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            parse_mode_command("/mode invalid_mode")

    def test_mode_only_no_message(self):
        mode, msg, switched = parse_mode_command("/mode debug")
        self.assertEqual(mode, "debug")
        self.assertEqual(msg, "")
        self.assertTrue(switched)


if __name__ == "__main__":
    unittest.main()
