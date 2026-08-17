"""Tests for embedagent.modes module."""

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.modes import (
    allowed_tools_for,
    build_system_prompt,
    get_writable_globs,
    is_path_writable,
    mode_names,
    parse_mode_command,
    parse_natural_language_mode_switch,
    require_mode,
)


class TestModeRegistry(unittest.TestCase):
    def test_all_expected_modes_present(self):
        """Verify current built-in modes are present."""
        names = mode_names()
        # Current built-in modes: explore, spec, build, debug, verify
        for m in ("explore", "spec", "build", "debug", "verify"):
            self.assertIn(m, names)

    def test_require_mode_invalid_raises(self):
        with self.assertRaises(ValueError):
            require_mode("nonexistent_mode")


class TestAllowedTools(unittest.TestCase):
    def test_explore_has_read_tools(self):
        tools = allowed_tools_for("explore")
        self.assertIn("read_file", tools)
        self.assertIn("list_dir", tools)
        self.assertIn("glob_files", tools)
        self.assertIn("grep_text", tools)

    def test_explore_has_git_status(self):
        # git_status and git_log were added to explore in Phase 1 (P3 fix)
        tools = allowed_tools_for("explore")
        self.assertIn("git_status", tools)
        self.assertIn("git_log", tools)

    def test_mode_contracts_do_not_own_harness_workflow_tools(self):
        harness_tools = {
            "list_recipes",
            "run_recipe",
            "report_quality_v2",
            "record_failing_evidence",
            "task_status",
        }
        for mode_name in ("explore", "spec", "build", "debug", "verify"):
            self.assertEqual(set(allowed_tools_for(mode_name)) & harness_tools, set())

    def test_explore_is_read_only_tools(self):
        tools = allowed_tools_for("explore")
        self.assertIn("ask_user", tools)
        for write_tool in ("edit_file", "write_file", "bash", "compile_project"):
            self.assertNotIn(write_tool, tools)

    def test_verify_has_no_edit_file(self):
        self.assertNotIn("edit_file", allowed_tools_for("verify"))

    def test_build_has_write_file(self):
        self.assertIn("write_file", allowed_tools_for("build"))

    def test_verify_has_read_tools(self):
        tools = allowed_tools_for("verify")
        self.assertIn("read_file", tools)
        self.assertIn("list_dir", tools)
        self.assertIn("glob_files", tools)
        self.assertIn("grep_text", tools)


class TestWritableGlobs(unittest.TestCase):
    def test_read_only_modes_have_empty_globs(self):
        for m in ("explore", "verify"):
            self.assertEqual(get_writable_globs(m), [])

    def test_build_mode_default_globs_are_generic(self):
        globs = get_writable_globs("build")
        self.assertEqual(globs, ["**/*"])

    def test_spec_mode_default_globs(self):
        globs = get_writable_globs("spec")
        self.assertIn("**/*.md", globs)
        self.assertIn("**/*.rst", globs)

    def test_config_override_replaces_defaults(self):
        cfg = SimpleNamespace(
            mode_writable_globs={"build": ["app/**/*.py"]}, mode_extra_writable_globs={}
        )
        globs = get_writable_globs("build", cfg)
        self.assertEqual(globs, ["app/**/*.py"])

    def test_config_override_only_affects_specified_mode(self):
        cfg = SimpleNamespace(
            mode_writable_globs={"build": ["app/**/*.py"]}, mode_extra_writable_globs={}
        )
        spec_globs = get_writable_globs("spec", cfg)
        self.assertIn("**/*.md", spec_globs)

    def test_extra_globs_append_to_defaults(self):
        cfg = SimpleNamespace(
            mode_writable_globs={}, mode_extra_writable_globs={"build": ["**/*.cmake"]}
        )
        globs = get_writable_globs("build", cfg)
        self.assertEqual(globs, ["**/*", "**/*.cmake"])

    def test_config_none_uses_defaults(self):
        default_globs = get_writable_globs("build")
        globs_with_none = get_writable_globs("build", None)
        self.assertEqual(default_globs, globs_with_none)


class TestIsPathWritable(unittest.TestCase):
    # --- relaxed default patterns ---
    def test_python_file_in_any_dir(self):
        self.assertTrue(is_path_writable("build", "scripts/build.py"))
        self.assertTrue(is_path_writable("build", "src/main.py"))
        self.assertTrue(is_path_writable("build", "app/models/user.py"))

    def test_c_file_in_any_dir(self):
        self.assertTrue(is_path_writable("build", "src/main.c"))
        self.assertTrue(is_path_writable("build", "lib/utils.c"))

    def test_markdown_in_spec_mode(self):
        self.assertTrue(is_path_writable("spec", "README.md"))
        self.assertTrue(is_path_writable("spec", "docs/README.md"))
        self.assertTrue(is_path_writable("spec", "wiki/design.md"))
        self.assertTrue(is_path_writable("spec", "ADR/001-decision.rst"))

    def test_root_toml_in_build_mode(self):
        self.assertTrue(is_path_writable("build", "pyproject.toml"))

    def test_root_python_in_build_mode(self):
        self.assertTrue(is_path_writable("build", "manage.py"))

    def test_development_modes_can_write_project_docs(self):
        for mode_name in ("build", "debug"):
            self.assertTrue(is_path_writable(mode_name, "README.md"))
            self.assertTrue(is_path_writable(mode_name, "docs/design.md"))
            self.assertTrue(is_path_writable(mode_name, "notes/plan.txt"))

    def test_python_blocked_in_spec_mode(self):
        self.assertFalse(is_path_writable("spec", "src/main.py"))

    def test_read_only_mode_blocks_everything(self):
        for path in ("src/main.py", "README.md", "src/main.c"):
            self.assertFalse(is_path_writable("explore", path))
            self.assertFalse(is_path_writable("verify", path))

    # --- config override ---
    def test_config_override_restricts_to_subdirectory(self):
        cfg = SimpleNamespace(
            mode_writable_globs={"build": ["src/*.py", "src/**/*.py"]}, mode_extra_writable_globs={}
        )
        self.assertTrue(is_path_writable("build", "src/main.py", cfg))
        self.assertFalse(is_path_writable("build", "scripts/build.py", cfg))

    def test_config_override_empty_list_means_readonly(self):
        cfg = SimpleNamespace(mode_writable_globs={"build": []}, mode_extra_writable_globs={})
        self.assertFalse(is_path_writable("build", "src/main.py", cfg))

    def test_windows_backslash_normalized(self):
        self.assertTrue(is_path_writable("build", "src\\main.py"))


class TestBuildSystemPrompt(unittest.TestCase):
    def test_prompt_contains_mode_name(self):
        prompt = build_system_prompt("build")
        self.assertIn("build", prompt)

    def test_prompt_excludes_tool_directory_in_explore(self):
        prompt = build_system_prompt("explore")
        self.assertNotIn("task_status", prompt)
        self.assertNotIn("ask_user", prompt)

    def test_prompt_does_not_list_active_tool_directory(self):
        prompt = build_system_prompt("build")
        self.assertNotIn("允许工具：", prompt)
        self.assertNotIn("read_file", prompt)
        self.assertNotIn("write_file", prompt)
        self.assertNotIn("ask_user", prompt)

    def test_prompt_shows_readonly_for_explore(self):
        prompt = build_system_prompt("explore")
        self.assertIn("只读", prompt)

    def test_config_override_reflected_in_prompt(self):
        cfg = SimpleNamespace(
            mode_writable_globs={"build": ["custom/**/*.py"]}, mode_extra_writable_globs={}
        )
        prompt = build_system_prompt("build", cfg)
        self.assertIn("custom/**/*.py", prompt)

    def test_build_prompt_does_not_prescribe_workflow_track(self):
        prompt = build_system_prompt("build")
        self.assertNotIn("lite_spec_tdd", prompt)
        self.assertNotIn("当前阶段先以", prompt)

    def test_build_prompt_uses_generic_profile_copy(self):
        prompt = build_system_prompt("build")
        self.assertIn("通用工程", prompt)
        self.assertNotIn("C/C++", prompt)


class TestParseModeCommand(unittest.TestCase):
    def test_mode_command_parsed(self):
        mode, msg, switched = parse_mode_command("/mode build 实现登录接口")
        self.assertEqual(mode, "build")
        self.assertEqual(msg, "实现登录接口")
        self.assertTrue(switched)

    def test_no_command_returns_fallback(self):
        mode, msg, switched = parse_mode_command("普通消息", fallback_mode="explore")
        self.assertEqual(mode, "explore")
        self.assertFalse(switched)

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            parse_mode_command("/mode invalid_mode")

    def test_mode_only_no_message(self):
        mode, msg, switched = parse_mode_command("/mode debug")
        self.assertEqual(mode, "debug")
        self.assertEqual(msg, "")
        self.assertTrue(switched)

    def test_natural_language_mode_switch_chinese(self):
        mode, remainder, switched = parse_natural_language_mode_switch("切换到build模式")
        self.assertEqual(mode, "build")
        self.assertEqual(remainder, "")
        self.assertTrue(switched)

    def test_natural_language_mode_switch_english(self):
        mode, remainder, switched = parse_natural_language_mode_switch("switch to debug mode")
        self.assertEqual(mode, "debug")
        self.assertEqual(remainder, "")
        self.assertTrue(switched)

    def test_natural_language_mode_switch_ignores_compound_request(self):
        mode, remainder, switched = parse_natural_language_mode_switch("切换到build模式，然后编译")
        self.assertEqual(mode, "explore")
        self.assertEqual(remainder, "切换到build模式，然后编译")
        self.assertFalse(switched)


if __name__ == "__main__":
    unittest.main()
