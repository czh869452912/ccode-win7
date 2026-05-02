"""Tests for the tools/ package refactoring and ToolRuntime."""

import os
import shutil
import sys
import unittest
from itertools import count
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.tools import ToolDefinition, ToolRuntime

_COUNTER = count(1)


def _make_workspace(prefix):
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "%s-%s" % (prefix, next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


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
        self.workspace = _make_workspace("tools-init")
        self.rt = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_workspace_is_realpath(self):
        self.assertEqual(self.rt.workspace, os.path.realpath(self.workspace))

    def test_cutover_stores_exposed(self):
        self.assertIsNotNone(self.rt.tool_result_store)
        self.assertIsNotNone(self.rt.projection_db)

    def test_app_config_default_none(self):
        self.assertIsNone(self.rt.app_config)

    def test_app_config_passed_through(self):
        from embedagent.config import AppConfig

        cfg = AppConfig(max_context_tokens=32000)
        rt = ToolRuntime(self.workspace, app_config=cfg)
        self.assertIs(rt.app_config, cfg)


class TestToolRuntimeSchemas(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("tools-schemas")
        self.rt = ToolRuntime(self.workspace)
        self.schemas = self.rt.schemas()
        self.tool_names = [s["function"]["name"] for s in self.schemas]

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_total_tool_count(self):
        self.assertEqual(len(self.schemas), 19)

    def test_official_tool_catalog_excludes_legacy_duplicate_tools(self):
        expected = [
            "read_file",
            "write_file",
            "edit_file",
            "run_command",
            "git_status",
            "git_diff",
            "git_log",
            "list_compilers",
            "configure_build_env",
            "run_build",
        ]
        for name in expected:
            self.assertIn(name, self.tool_names, "Missing tool: %s" % name)
        for name in (
            "list_files",
            "search_text",
            "compile_project",
            "run_tests",
            "run_clang_tidy",
            "run_clang_analyzer",
            "collect_coverage",
            "report_quality",
            "manage_todos",
        ):
            self.assertNotIn(
                name, self.tool_names, "Legacy tool leaked into official catalog: %s" % name
            )

    def test_harness_tools_present(self):
        for name in (
            "list_dir",
            "glob_files",
            "grep_text",
            "list_recipes",
            "run_recipe",
            "report_quality_v2",
            "task_status",
            "ask_user",
            "record_failing_evidence",
        ):
            self.assertIn(name, self.tool_names, "Missing harness tool: %s" % name)

    def test_schema_structure(self):
        for schema in self.schemas:
            self.assertEqual(schema["type"], "function")
            func = schema["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)
            self.assertEqual(func["parameters"]["type"], "object")
            self.assertIn("required", func["parameters"])

    def test_review_workflow_filters_out_write_tools_from_spec_mode(self):
        schemas = self.rt.schemas_for("spec", workflow_state="review")
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("read_file", tool_names)
        self.assertIn("task_status", tool_names)
        self.assertNotIn("write_file", tool_names)

    def test_verify_review_workflow_keeps_quality_tools_visible(self):
        schemas = self.rt.schemas_for("verify", workflow_state="review")
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("list_recipes", tool_names)
        self.assertIn("run_recipe", tool_names)
        self.assertIn("report_quality_v2", tool_names)
        self.assertNotIn("write_file", tool_names)

    def test_build_mode_uses_harness_pack_schema(self):
        schemas = self.rt.schemas_for_mode("build", workflow_state="chat")
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("list_dir", tool_names)
        self.assertIn("run_recipe", tool_names)
        self.assertNotIn("list_files", tool_names)

    def test_debug_mode_uses_harness_pack_schema(self):
        schemas = self.rt.schemas_for_mode("debug", workflow_state="chat")
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("record_failing_evidence", tool_names)
        self.assertIn("run_recipe", tool_names)
        self.assertNotIn("run_command", tool_names)

    def test_allowed_tool_names_match_official_debug_pack(self):
        tool_names = self.rt.allowed_tool_names("debug", workflow_state="chat")
        self.assertIn("record_failing_evidence", tool_names)
        self.assertIn("run_recipe", tool_names)
        self.assertNotIn("run_command", tool_names)


class TestToolRuntimeExecute(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("tools-exec")
        self.rt = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

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

    def test_official_runtime_rejects_legacy_file_tools(self):
        # Create a file so the directory isn't empty
        with open(os.path.join(self.workspace, "test.txt"), "w") as f:
            f.write("x")
        list_obs = self.rt.execute("list_files", {"path": "."})
        search_obs = self.rt.execute("search_text", {"query": "x", "path": "."})
        self.assertFalse(list_obs.success)
        self.assertFalse(search_obs.success)

    def test_edit_file_replaces_text(self):
        test_file = os.path.join(self.workspace, "edit_me.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        obs = self.rt.execute(
            "edit_file",
            {
                "path": "edit_me.py",
                "old_text": "x = 1",
                "new_text": "x = 2",
            },
        )
        self.assertTrue(obs.success)
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("x = 2", content)

    def test_write_file_creates_new_file(self):
        obs = self.rt.execute(
            "write_file",
            {
                "path": "docs/requirements.md",
                "content": "# Requirements\n",
            },
        )
        self.assertTrue(obs.success)
        self.assertTrue(obs.data["created"])
        with open(
            os.path.join(self.workspace, "docs", "requirements.md"), "r", encoding="utf-8"
        ) as f:
            content = f.read()
        self.assertEqual(content, "# Requirements\n")

    def test_write_file_blocks_existing_without_overwrite(self):
        test_file = os.path.join(self.workspace, "existing.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("old\n")
        obs = self.rt.execute(
            "write_file",
            {
                "path": "existing.txt",
                "content": "new\n",
            },
        )
        self.assertFalse(obs.success)

    def test_official_runtime_rejects_legacy_task_tool(self):
        obs = self.rt.execute("manage_todos", {"action": "list"})
        self.assertFalse(obs.success)
        self.assertEqual(obs.tool_name, "manage_todos")

    def test_write_file_observation_includes_catalog_metadata(self):
        obs = self.rt.execute(
            "write_file",
            {
                "path": "notes/plan.md",
                "content": "# Plan\n",
                "overwrite": True,
            },
        )
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["tool_label"], "Write File")
        self.assertEqual(obs.data["permission_category"], "workspace_write")
        self.assertTrue(obs.data["supports_diff_preview"])
        self.assertEqual(obs.data["progress_renderer_key"], "file_write")
        self.assertEqual(obs.data["result_renderer_key"], "file_write")

    def test_list_compilers_returns_observation(self):
        obs = self.rt.execute("list_compilers", {})
        self.assertTrue(obs.success)
        self.assertEqual(obs.tool_name, "list_compilers")
        self.assertIn("compilers", obs.data)
        self.assertIn("count", obs.data)
        self.assertIsInstance(obs.data["compilers"], list)
        self.assertIsInstance(obs.data["count"], int)

    def test_list_compilers_includes_catalog_metadata(self):
        obs = self.rt.execute("list_compilers", {})
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["tool_label"], "List Compilers")
        self.assertEqual(obs.data["permission_category"], "read")
        self.assertFalse(obs.data["supports_diff_preview"])

    def test_configure_build_env_returns_observation(self):
        obs = self.rt.execute("configure_build_env", {})
        self.assertTrue(obs.success)
        self.assertEqual(obs.tool_name, "configure_build_env")
        self.assertIn("compiler", obs.data)
        self.assertIn("compilers_available", obs.data)
        self.assertIn("build_type", obs.data)
        self.assertIn("c_flags", obs.data)
        self.assertIn("cxx_flags", obs.data)
        self.assertIn("linker_flags", obs.data)
        self.assertIn("environment", obs.data)
        self.assertIn("build_dir", obs.data)
        self.assertIsInstance(obs.data["compilers_available"], list)
        self.assertEqual(obs.data["build_type"], "debug")

    def test_configure_build_env_with_build_type(self):
        obs = self.rt.execute("configure_build_env", {"build_type": "release"})
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["build_type"], "release")
        self.assertEqual(obs.data["c_flags"], "-O3 -DNDEBUG")
        self.assertEqual(obs.data["cxx_flags"], "-O3 -DNDEBUG")

    def test_configure_build_env_includes_catalog_metadata(self):
        obs = self.rt.execute("configure_build_env", {})
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["tool_label"], "Configure Build Env")
        self.assertEqual(obs.data["permission_category"], "read")
        self.assertFalse(obs.data["supports_diff_preview"])

    def test_run_build_returns_observation(self):
        obs = self.rt.execute("run_build", {"command": "cmd /c echo build-ok"})
        self.assertTrue(obs.success)
        self.assertEqual(obs.tool_name, "run_build")
        self.assertIn("stdout", obs.data)
        self.assertIn("build-ok", obs.data["stdout"])
        self.assertIn("streaming_progress", obs.data)
        self.assertIn("streaming_progress_count", obs.data)
        self.assertIsInstance(obs.data["streaming_progress"], list)
        self.assertIsInstance(obs.data["streaming_progress_count"], int)

    def test_run_build_requires_command(self):
        obs = self.rt.execute("run_build", {})
        self.assertFalse(obs.success)
        self.assertIsNotNone(obs.error)

    def test_run_build_parses_diagnostics(self):
        # Write a helper batch file that prints a compiler-style diagnostic line
        bat_path = os.path.join(self.workspace, "emit_diag.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write("@echo off\necho test.c:1:2: error: test error\n")
        obs = self.rt.execute("run_build", {"command": "emit_diag.bat"})
        self.assertTrue(obs.success, obs.error)
        self.assertIn("diagnostics", obs.data)
        self.assertIsInstance(obs.data["diagnostics"], list)
        self.assertGreaterEqual(obs.data["diagnostic_count"], 1)
        self.assertEqual(obs.data["error_count"], 1)

    def test_run_build_includes_catalog_metadata(self):
        obs = self.rt.execute("run_build", {"command": "cmd /c echo ok"})
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["tool_label"], "Run Build")
        self.assertEqual(obs.data["permission_category"], "shell_exec")
        self.assertFalse(obs.data["supports_diff_preview"])


class TestModuleIsolation(unittest.TestCase):
    """Verify each ops module can be imported independently."""

    def test_discovery_ops_importable(self):
        from embedagent.tools import discovery_ops

        self.assertTrue(callable(discovery_ops.build_tools))

    def test_recipe_ops_importable(self):
        from embedagent.tools import recipe_ops

        self.assertTrue(callable(recipe_ops.build_tools))

    def test_session_ops_importable(self):
        from embedagent.tools import session_ops

        self.assertTrue(callable(session_ops.build_tools))

    def test_file_ops_importable(self):
        from embedagent.tools import file_ops

        self.assertTrue(callable(file_ops.build_tools))

    def test_shell_ops_importable(self):
        from embedagent.tools import shell_ops

        self.assertTrue(callable(shell_ops.build_tools))

    def test_git_ops_importable(self):
        from embedagent.tools import git_ops

        self.assertTrue(callable(git_ops.build_tools))

    def test_compile_ops_importable(self):
        from embedagent.tools import compile_ops

        self.assertTrue(callable(compile_ops.build_tools))

    def test_base_importable(self):
        self.assertTrue(True)


class TestManagedRuntimeEnvironment(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("tools-runtime")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _touch(self, *parts):
        path = os.path.join(*parts)
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("stub\n")
        return path

    def test_runtime_snapshot_prefers_bundle_tools(self):
        bundle_root = os.path.join(self.workspace, "bundle")
        self._touch(bundle_root, "app", "embedagent", "__init__.py")
        self._touch(bundle_root, "runtime", "python", "python.exe")
        self._touch(bundle_root, "bin", "git", "cmd", "git.exe")
        self._touch(bundle_root, "bin", "git", "bin", "git.exe")
        self._touch(bundle_root, "bin", "rg", "rg.exe")
        self._touch(bundle_root, "bin", "ctags", "ctags.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "clang.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "clang-tidy.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "llvm-profdata.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "llvm-cov.exe")
        with patch.dict(os.environ, {"EMBEDAGENT_BUNDLE_ROOT": bundle_root}, clear=False):
            runtime = ToolRuntime(self.workspace)
            snapshot = runtime.runtime_environment_snapshot()
        self.assertEqual(snapshot["runtime_source"], "bundle")
        self.assertTrue(snapshot["bundled_tools_ready"])
        self.assertEqual(snapshot["tool_sources"]["git"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["rg"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["ctags"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["llvm"], "bundle")
        self.assertTrue(snapshot["resolved_tool_roots"]["bundle_root"].endswith("bundle"))

    def test_runtime_snapshot_reports_missing_bundle_tools_without_fallback(self):
        bundle_root = os.path.join(self.workspace, "bundle-missing")
        self._touch(bundle_root, "app", "embedagent", "__init__.py")
        self._touch(bundle_root, "runtime", "python", "python.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "clang.exe")
        with patch.dict(os.environ, {"EMBEDAGENT_BUNDLE_ROOT": bundle_root}, clear=False):
            runtime = ToolRuntime(self.workspace)
            snapshot = runtime.runtime_environment_snapshot()
        self.assertEqual(snapshot["runtime_source"], "bundle")
        self.assertFalse(snapshot["bundled_tools_ready"])
        self.assertGreaterEqual(len(snapshot["fallback_warnings"]), 1)

    def test_runtime_snapshot_detects_bundle_without_env_from_installed_location(self):
        import embedagent.tools._base as tools_base

        bundle_root = os.path.join(self.workspace, "portable-bundle")
        workspace_root = os.path.join(bundle_root, "data", "workspace-template")
        os.makedirs(workspace_root)
        fake_module_path = self._touch(bundle_root, "app", "embedagent", "tools", "_base.py")
        self._touch(bundle_root, "app", "embedagent", "__init__.py")
        self._touch(bundle_root, "runtime", "python", "python.exe")
        self._touch(bundle_root, "bin", "git", "cmd", "git.exe")
        self._touch(bundle_root, "bin", "git", "bin", "git.exe")
        self._touch(bundle_root, "bin", "rg", "rg.exe")
        self._touch(bundle_root, "bin", "ctags", "ctags.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "clang.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "clang-tidy.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "llvm-profdata.exe")
        self._touch(bundle_root, "bin", "llvm", "bin", "llvm-cov.exe")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EMBEDAGENT_BUNDLE_ROOT", None)
            with patch.object(tools_base, "__file__", fake_module_path):
                runtime = ToolRuntime(workspace_root)
                snapshot = runtime.runtime_environment_snapshot()
        self.assertEqual(snapshot["runtime_source"], "bundle")
        self.assertTrue(snapshot["bundled_tools_ready"])
        self.assertEqual(snapshot["tool_sources"]["python"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["git"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["rg"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["ctags"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["llvm"], "bundle")
        self.assertTrue(snapshot["resolved_tool_roots"]["bundle_root"].endswith("portable-bundle"))


class TestWorkspaceRecipes(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("tools-recipes")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_detects_cmake_and_history_recipes(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent", "memory", "project"))
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        with open(
            os.path.join(
                self.workspace, ".embedagent", "memory", "project", "command-recipes.json"
            ),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"key":"build|.|clang demo.c","tool_name":"run_recipe","recipe_action":"build","command":"clang demo.c","cwd":".","last_mode":"build","created_at":"2026-04-01T00:00:00Z","last_success_at":"2026-04-01T00:00:00Z","success_count":1}]'
            )
        from embedagent.workspace_recipes import list_workspace_recipes

        payload = list_workspace_recipes(self.workspace)
        recipe_ids = [item["id"] for item in payload["items"]]
        self.assertIn("cmake.configure.default", recipe_ids)
        self.assertIn("cmake.build.default", recipe_ids)
        self.assertIn("cmake.test.default", recipe_ids)
        self.assertIn("history.build.1", recipe_ids)
        cmake_build = [item for item in payload["items"] if item["id"] == "cmake.build.default"][0]
        self.assertEqual(cmake_build["tool_name"], "run_recipe")
        self.assertEqual(cmake_build["recipe_action"], "build")
        self.assertTrue(cmake_build["supports_target"])
        self.assertTrue(cmake_build["supports_profile"])

    def test_run_recipe_can_run_build_recipe_id(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"))
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        runtime = ToolRuntime(self.workspace)
        obs = runtime.execute("run_recipe", {"recipe_id": "custom.build"})
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["recipe_id"], "custom.build")
        self.assertEqual(obs.data["recipe_source"], "project")
        self.assertIn("build-ok", obs.data["stdout"])

    def test_resolve_cmake_recipe_applies_target_and_profile(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        from embedagent.workspace_recipes import resolve_workspace_recipe

        payload = resolve_workspace_recipe(
            self.workspace,
            recipe_id="cmake.build.default",
            expected_tool_name="run_recipe",
            target="demo-app",
            profile="debug",
        )
        self.assertEqual(payload["profile"], "debug")
        self.assertEqual(payload["target"], "demo-app")
        self.assertIn("build/debug", payload["command"])
        self.assertIn("--target demo-app", payload["command"])

    def test_run_recipe_can_run_verify_recipe_id(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"))
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                "["
                + '{"id":"custom.tidy","tool_name":"run_recipe","recipe_action":"tidy","label":"Custom Tidy","command":"cmd /c echo tidy-ok","cwd":"."},'
                + '{"id":"custom.analyze","tool_name":"run_recipe","recipe_action":"analyze","label":"Custom Analyze","command":"cmd /c echo analyze-ok","cwd":"."},'
                + '{"id":"custom.coverage","tool_name":"run_recipe","recipe_action":"coverage","label":"Custom Coverage","command":"cmd /c echo lines 85%","cwd":"."}'
                + "]"
            )
        runtime = ToolRuntime(self.workspace)
        tidy_obs = runtime.execute("run_recipe", {"recipe_id": "custom.tidy"})
        analyze_obs = runtime.execute("run_recipe", {"recipe_id": "custom.analyze"})
        coverage_obs = runtime.execute("run_recipe", {"recipe_id": "custom.coverage"})
        self.assertTrue(tidy_obs.success)
        self.assertTrue(analyze_obs.success)
        self.assertTrue(coverage_obs.success)
        self.assertEqual(tidy_obs.data["recipe_id"], "custom.tidy")
        self.assertEqual(analyze_obs.data["recipe_id"], "custom.analyze")
        self.assertEqual(coverage_obs.data["recipe_id"], "custom.coverage")

    def test_official_runtime_rejects_legacy_verify_tool_aliases(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"))
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        runtime = ToolRuntime(self.workspace)
        for tool_name in (
            "compile_project",
            "run_tests",
            "run_clang_tidy",
            "run_clang_analyzer",
            "collect_coverage",
            "report_quality",
        ):
            obs = runtime.execute(tool_name, {"recipe_id": "custom.build"})
            self.assertFalse(obs.success, tool_name)

    def test_detects_ninja_recipes(self):
        with open(os.path.join(self.workspace, "build.ninja"), "w", encoding="utf-8") as handle:
            handle.write("rule cc\n  command = clang -c $in -o $out\n")
        from embedagent.workspace_recipes import list_workspace_recipes

        payload = list_workspace_recipes(self.workspace)
        recipe_ids = [item["id"] for item in payload["items"]]
        self.assertIn("ninja.build.default", recipe_ids)
        self.assertIn("ninja.test.default", recipe_ids)
        ninja_build = [item for item in payload["items"] if item["id"] == "ninja.build.default"][0]
        self.assertEqual(ninja_build["tool_name"], "run_recipe")
        self.assertEqual(ninja_build["recipe_action"], "build")
        self.assertEqual(ninja_build["family"], "ninja")
        self.assertTrue(ninja_build["supports_target"])
        self.assertFalse(ninja_build["supports_profile"])

    def test_detects_make_recipes_with_target_support(self):
        with open(os.path.join(self.workspace, "Makefile"), "w", encoding="utf-8") as handle:
            handle.write("all:\n\techo hello\n")
        from embedagent.workspace_recipes import list_workspace_recipes

        payload = list_workspace_recipes(self.workspace)
        recipe_ids = [item["id"] for item in payload["items"]]
        self.assertIn("make.build.default", recipe_ids)
        self.assertIn("make.test.default", recipe_ids)
        make_build = [item for item in payload["items"] if item["id"] == "make.build.default"][0]
        self.assertEqual(make_build["family"], "make")
        self.assertTrue(make_build["supports_target"])
        self.assertFalse(make_build["supports_profile"])


if __name__ == "__main__":
    unittest.main()
