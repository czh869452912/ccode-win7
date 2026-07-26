"""Tests for the tools/ package refactoring and ToolRuntime."""

import json
import os
import shutil
import sys
import unittest
from itertools import count
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from conftest import register_default_c_workflow_tools
from embedagent_host.runtime.tools import ToolDefinition, ToolRuntime
from embedagent_host.runtime.tools._base import MAX_COMMAND_OUTPUT_CHARS, ToolContext
from embedagent_host.runtime.tools.discovery_ops import build_tools as build_discovery_tools

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


SPEC_BASE_TOOLS = ["read_file", "list_dir", "glob_files", "grep_text", "write_file", "ask_user"]
VERIFY_BASE_TOOLS = ["read_file", "list_dir", "glob_files", "grep_text", "bash", "ask_user"]
WRITE_BASE_TOOLS = [
    "read_file",
    "list_dir",
    "glob_files",
    "grep_text",
    "write_file",
    "edit_file",
    "bash",
    "author_local_capability",
    "ask_user",
]


class TestToolRuntimeImport(unittest.TestCase):
    def test_import_from_package(self):
        # The original import path must still work
        from embedagent_host.runtime.tools import ToolRuntime as RT

        self.assertIs(RT, ToolRuntime)

    def test_tool_definition_importable(self):
        from embedagent_host.runtime.tools import ToolDefinition as TD

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
        self.assertEqual(len(self.schemas), 13)

    def test_official_tool_catalog_excludes_legacy_duplicate_tools(self):
        expected = [
            "read_file",
            "write_file",
            "edit_file",
            "bash",
            "git_status",
            "git_diff",
            "git_log",
        ]
        for name in expected:
            self.assertIn(name, self.tool_names, "Missing tool: %s" % name)
        for name in (
            "run_command",
            "list_compilers",
            "configure_build_env",
            "run_build",
            "list_files",
            "search_text",
            "compile_project",
            "run_tests",
            "run_clang_tidy",
            "run_clang_analyzer",
            "collect_coverage",
            "report_quality",
            "manage" + "_to" + "dos",
        ):
            self.assertNotIn(
                name, self.tool_names, "Legacy tool leaked into official catalog: %s" % name
            )

    def test_default_c_workflow_package_tools_present_after_registration(self):
        register_default_c_workflow_tools(self.rt, self.workspace)
        tool_names = [s["function"]["name"] for s in self.rt.schemas()]
        for name in (
            "list_dir",
            "glob_files",
            "grep_text",
            "bash",
            "list_recipes",
            "run_recipe",
            "report_quality_v2",
            "task_status",
            "ask_user",
            "record_failing_evidence",
        ):
            self.assertIn(name, tool_names, "Missing workflow tool: %s" % name)
        for name in ("list_compilers", "configure_build_env", "run_build"):
            self.assertNotIn(name, tool_names, "Removed build helper leaked: %s" % name)

    def test_schema_structure(self):
        for schema in self.schemas:
            self.assertEqual(schema["type"], "function")
            func = schema["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)
            self.assertEqual(func["parameters"]["type"], "object")
            self.assertIn("required", func["parameters"])

    def test_explicit_spec_tool_names_are_not_reinterpreted_by_workflow_state(self):
        schemas = self.rt.schemas_for(
            "spec",
            workflow_state="review",
            tool_names=SPEC_BASE_TOOLS,
        )
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("read_file", tool_names)
        self.assertNotIn("task_status", tool_names)
        self.assertIn("write_file", tool_names)

    def test_verify_review_workflow_uses_explicit_read_only_tool_names(self):
        schemas = self.rt.schemas_for(
            "verify",
            workflow_state="review",
            tool_names=VERIFY_BASE_TOOLS,
        )
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("read_file", tool_names)
        self.assertIn("grep_text", tool_names)
        self.assertIn("ask_user", tool_names)
        self.assertNotIn("list_recipes", tool_names)
        self.assertNotIn("run_recipe", tool_names)
        self.assertNotIn("report_quality_v2", tool_names)
        self.assertNotIn("write_file", tool_names)

    def test_schemas_for_explicit_verify_mode_contract(self):
        schemas = self.rt.schemas_for(
            "verify",
            workflow_state="review",
            tool_names=VERIFY_BASE_TOOLS,
        )
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("read_file", tool_names)
        self.assertIn("list_dir", tool_names)
        self.assertIn("glob_files", tool_names)
        self.assertIn("grep_text", tool_names)
        self.assertIn("ask_user", tool_names)
        self.assertNotIn("list_recipes", tool_names)
        self.assertNotIn("run_recipe", tool_names)
        self.assertNotIn("report_quality_v2", tool_names)
        self.assertNotIn("task_status", tool_names)
        self.assertNotIn("write_file", tool_names)

    def test_schemas_for_explicit_build_mode_contract(self):
        schemas = self.rt.schemas_for(
            "build",
            workflow_state="chat",
            tool_names=WRITE_BASE_TOOLS,
        )
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("read_file", tool_names)
        self.assertIn("list_dir", tool_names)
        self.assertIn("write_file", tool_names)
        self.assertIn("edit_file", tool_names)
        self.assertIn("bash", tool_names)
        self.assertIn("ask_user", tool_names)
        self.assertNotIn("run_command", tool_names)
        self.assertNotIn("run_build", tool_names)
        self.assertNotIn("run_recipe", tool_names)
        self.assertNotIn("task_status", tool_names)
        self.assertNotIn("list_files", tool_names)

    def test_schemas_for_explicit_debug_mode_contract(self):
        schemas = self.rt.schemas_for(
            "debug",
            workflow_state="chat",
            tool_names=WRITE_BASE_TOOLS,
        )
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("read_file", tool_names)
        self.assertIn("list_dir", tool_names)
        self.assertIn("write_file", tool_names)
        self.assertIn("edit_file", tool_names)
        self.assertIn("bash", tool_names)
        self.assertIn("ask_user", tool_names)
        self.assertNotIn("record_failing_evidence", tool_names)
        self.assertNotIn("run_recipe", tool_names)
        self.assertNotIn("task_status", tool_names)
        self.assertNotIn("run_command", tool_names)

    def test_schemas_for_verify_exposes_bash_without_write_tools(self):
        schemas = self.rt.schemas_for(
            "verify",
            workflow_state="chat",
            tool_names=VERIFY_BASE_TOOLS,
        )
        tool_names = [item["function"]["name"] for item in schemas]
        self.assertIn("bash", tool_names)
        self.assertNotIn("write_file", tool_names)
        self.assertNotIn("edit_file", tool_names)
        self.assertNotIn("run_command", tool_names)
        self.assertNotIn("run_build", tool_names)

    def test_author_local_capability_schema_is_build_debug_only(self):
        build_names = [
            item["function"]["name"]
            for item in self.rt.schemas_for(
                "build",
                workflow_state="chat",
                tool_names=WRITE_BASE_TOOLS,
            )
        ]
        debug_names = [
            item["function"]["name"]
            for item in self.rt.schemas_for(
                "debug",
                workflow_state="chat",
                tool_names=WRITE_BASE_TOOLS,
            )
        ]
        verify_names = [
            item["function"]["name"]
            for item in self.rt.schemas_for(
                "verify",
                workflow_state="review",
                tool_names=VERIFY_BASE_TOOLS,
            )
        ]

        self.assertIn("author_local_capability", build_names)
        self.assertIn("author_local_capability", debug_names)
        self.assertNotIn("author_local_capability", verify_names)

    def test_author_local_capability_writes_skill_artifact(self):
        obs = self.rt.execute(
            "author_local_capability",
            {
                "kind": "skill",
                "name": "Review Helper",
                "summary": "Review local changes.",
            },
        )

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["kind"], "skill")
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.workspace,
                    ".embedagent",
                    "skills",
                    "review-helper.md",
                )
            )
        )


class TestCommandOutputDecoding(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("command-decoding")
        self.ctx = ToolContext(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_decode_command_output_prefers_utf8(self):
        decoded = self.ctx.decode_command_output("stdout", "hello Chinese".encode("utf-8"))
        self.assertEqual(decoded.text, "hello Chinese")
        self.assertEqual(decoded.encoding, "utf-8")
        self.assertEqual(decoded.decode_errors_count, 0)

    def test_decode_command_output_falls_back_to_gbk(self):
        decoded = self.ctx.decode_command_output("stdout", "中文".encode("gbk"))
        self.assertEqual(decoded.text, "中文")
        self.assertIn(decoded.encoding, ("gbk", "cp936"))
        self.assertEqual(decoded.decode_errors_count, 0)

    def test_decode_command_output_reports_replacement_fallback(self):
        decoded = self.ctx.decode_command_output("stdout", b"\xff\xfe\x00\x81")
        self.assertTrue(decoded.decode_errors_count >= 0)
        self.assertIn("stdout_encoding", decoded.to_metadata())

    def test_read_text_uses_replacement_fallback_for_mixed_encoding_bytes(self):
        path = os.path.join(self.workspace, "mixed.txt")
        with open(path, "wb") as handle:
            handle.write("prefix\n".encode("utf-8") + b"\xd7" + b"\n")

        content, newline_style, encoding = self.ctx.read_text(path)

        self.assertIn("prefix", content)
        self.assertIn("\ufffd", content)
        self.assertEqual(newline_style, "\n")
        self.assertEqual(encoding, "utf-8-replace")

    def test_write_text_maps_replacement_encoding_to_real_codec(self):
        path = os.path.join(self.workspace, "mixed.txt")

        self.ctx.write_text(path, "prefix\n\ufffd\n", "\n", "utf-8-replace")

        with open(path, "rb") as handle:
            raw = handle.read()
        self.assertEqual(raw, "prefix\n\ufffd\n".encode("utf-8"))

    @unittest.skipIf(sys.platform != "win32", "Windows-only: requires cmd.exe")
    def test_bash_result_contains_decode_metadata(self):
        rt = ToolRuntime(self.workspace)
        obs = rt.execute("bash", {"command": "cmd /c echo hello"})
        self.assertTrue(obs.success)
        self.assertIn("stdout", obs.data)
        self.assertIn("stdout_encoding", obs.data)
        self.assertIn("stdout_decode_errors_count", obs.data)
        self.assertIn("stderr_encoding", obs.data)

    def test_truncate_output_keeps_tail(self):
        text = "head" + ("a" * MAX_COMMAND_OUTPUT_CHARS) + "tail"
        truncated, was_truncated = self.ctx.truncate_output(text)
        self.assertTrue(was_truncated)
        self.assertEqual(len(truncated), MAX_COMMAND_OUTPUT_CHARS)
        self.assertTrue(truncated.endswith("tail"))
        self.assertNotIn("head", truncated)

    def test_command_observation_records_full_output_ref_when_truncated(self):
        long_text = "x" * (MAX_COMMAND_OUTPUT_CHARS + 10)
        result = {
            "exit_code": 0,
            "stdout": long_text,
            "stderr": "",
            "stdout_truncated": True,
            "stderr_truncated": False,
            "duration_ms": 1,
            "timed_out": False,
            "interrupted": False,
            "stdout_encoding": "utf-8",
            "stderr_encoding": "utf-8",
            "stdout_decode_errors_count": 0,
            "stderr_decode_errors_count": 0,
            "stdout_output_maybe_mojibake": False,
            "stderr_output_maybe_mojibake": False,
        }
        obs = self.ctx.build_command_observation("bash", "echo long", self.workspace, result)
        self.assertTrue(obs.data["stdout_truncated"])
        self.assertIn("full_output_ref", obs.data)
        self.assertTrue(os.path.isfile(os.path.join(self.workspace, obs.data["full_output_ref"])))


class TestToolRuntimeExecute(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("tools-exec")
        self.rt = ToolRuntime(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _register_default_c_workflow_tools(self):
        register_default_c_workflow_tools(self.rt, self.workspace)

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

    def test_read_file_missing_path_is_diagnostic_failure(self):
        obs = self.rt.execute("read_file", {"path": "missing.txt"})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "path_not_found")
        self.assertEqual(obs.data["outcome_class"], "diagnostic_failure")
        self.assertFalse(obs.data["retryable"])

    def test_read_file_binary_path_is_diagnostic_failure(self):
        with open(os.path.join(self.workspace, "image.bin"), "wb") as handle:
            handle.write(b"abc\x00def")

        obs = self.rt.execute("read_file", {"path": "image.bin"})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "binary_file")
        self.assertEqual(obs.data["outcome_class"], "diagnostic_failure")
        self.assertFalse(obs.data["retryable"])

    def test_list_dir_outside_workspace_is_diagnostic_failure(self):
        outside = os.path.dirname(self.workspace)

        obs = self.rt.execute("list_dir", {"path": outside})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "path_outside_workspace")
        self.assertEqual(obs.data["outcome_class"], "diagnostic_failure")
        self.assertFalse(obs.data["retryable"])

    def test_grep_text_continues_with_replacement_decoded_files(self):
        with open(os.path.join(self.workspace, "good.txt"), "w", encoding="utf-8") as handle:
            handle.write("needle\n")
        with open(os.path.join(self.workspace, "mixed.txt"), "wb") as handle:
            handle.write(b"prefix\n\xd7\n")

        obs = self.rt.execute("grep_text", {"pattern": "needle", "path": "."})

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["returned_count"], 1)
        self.assertEqual(obs.data["decode_error_count"], 1)

    def test_grep_text_accepts_single_file_path(self):
        with open(os.path.join(self.workspace, "hal_uart.h"), "w", encoding="utf-8") as handle:
            handle.write("class HAL_UART {\npublic:\n  void init();\n};\n")

        obs = self.rt.execute(
            "grep_text",
            {"pattern": "class HAL_UART", "path": "hal_uart.h"},
        )

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["returned_count"], 1)
        self.assertEqual(obs.data["total_count"], 1)
        self.assertIn("hal_uart.h:1:class HAL_UART", obs.data["preview"][0])

    def test_grep_text_supports_regex_and_literal_mode(self):
        with open(os.path.join(self.workspace, "hal_uart.h"), "w", encoding="utf-8") as handle:
            handle.write("class HAL_UART {\npublic:\n  void init();\n};\n")

        regex_obs = self.rt.execute(
            "grep_text",
            {"pattern": "HAL_UART|public:|void ", "path": "hal_uart.h"},
        )
        literal_obs = self.rt.execute(
            "grep_text",
            {"pattern": "HAL_UART|public:", "path": "hal_uart.h", "literal": True},
        )

        self.assertTrue(regex_obs.success)
        self.assertEqual(regex_obs.data["returned_count"], 3)
        self.assertTrue(literal_obs.success)
        self.assertEqual(literal_obs.data["returned_count"], 0)
        self.assertEqual(literal_obs.data["total_count"], 0)

    def test_grep_text_invalid_regex_is_diagnostic_failure_with_catalog_metadata(self):
        with open(os.path.join(self.workspace, "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int main(void) { return 0; }\n")

        obs = self.rt.execute("grep_text", {"pattern": "[", "path": "."})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "invalid_pattern")
        self.assertEqual(obs.data["outcome_class"], "diagnostic_failure")
        self.assertFalse(obs.data["retryable"])
        self.assertEqual(obs.data["tool_label"], "Grep Text")
        self.assertEqual(obs.data["permission_category"], "read")

    def test_grep_text_missing_path_is_diagnostic_failure(self):
        obs = self.rt.execute("grep_text", {"pattern": "needle", "path": "missing"})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "path_not_found")
        self.assertEqual(obs.data["outcome_class"], "diagnostic_failure")
        self.assertFalse(obs.data["retryable"])

    def test_grep_text_skips_embedagent_memory_by_default(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent", "memory", "sessions", "s1"))
        with open(os.path.join(self.workspace, "src.txt"), "w", encoding="utf-8") as handle:
            handle.write("needle in source\n")
        with open(
            os.path.join(
                self.workspace, ".embedagent", "memory", "sessions", "s1", "transcript.jsonl"
            ),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write("needle in agent memory\n")

        obs = self.rt.execute("grep_text", {"pattern": "needle", "path": "."})

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["returned_count"], 1)
        self.assertIn("src.txt:1:needle in source", obs.data["preview"][0])
        self.assertNotIn(".embedagent/memory", "\n".join(obs.data["preview"]))

    def test_grep_text_uses_managed_ripgrep_when_available(self):
        class FakeRgContext(ToolContext):
            def __init__(self, workspace):
                super(FakeRgContext, self).__init__(workspace)
                self.commands = []

            def resolve_managed_tool_path(self, tool_key):
                if tool_key == "rg":
                    return os.path.join(self.workspace, "bin", "rg", "rg.exe"), "workspace"
                return super(FakeRgContext, self).resolve_managed_tool_path(tool_key)

            def run_subprocess(self, command, cwd, timeout_sec, shell, stop_event=None):
                self.commands.append(
                    {
                        "command": command,
                        "cwd": cwd,
                        "timeout_sec": timeout_sec,
                        "shell": shell,
                    }
                )
                return {
                    "exit_code": 0,
                    "stdout": "src/main.c:2:needle hit\n",
                    "stderr": "",
                    "stdout_decode_errors_count": 0,
                    "stderr_decode_errors_count": 0,
                    "timed_out": False,
                    "interrupted": False,
                }

        ctx = FakeRgContext(self.workspace)
        grep_tool = [tool for tool in build_discovery_tools(ctx) if tool.name == "grep_text"][0]

        obs = grep_tool.handler({"pattern": "needle", "path": ".", "limit": 1, "offset": 0})

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["preview"], ["src/main.c:2:needle hit"])
        self.assertEqual(obs.data["search_backend"], "rg")
        self.assertEqual(obs.data["managed_tool_source"], "workspace")
        command = ctx.commands[0]["command"]
        self.assertFalse(ctx.commands[0]["shell"])
        self.assertIn("--line-number", command)
        self.assertIn("--hidden", command)
        self.assertIn("--no-ignore", command)
        self.assertIn("--ignore-case", command)
        self.assertIn("--encoding", command)
        self.assertIn("auto", command)
        self.assertIn("!.embedagent/memory/**", command)

    def test_grep_text_rg_invalid_regex_is_diagnostic_failure(self):
        class FakeRgContext(ToolContext):
            def resolve_managed_tool_path(self, tool_key):
                if tool_key == "rg":
                    return os.path.join(self.workspace, "bin", "rg", "rg.exe"), "workspace"
                return super(FakeRgContext, self).resolve_managed_tool_path(tool_key)

            def run_subprocess(self, command, cwd, timeout_sec, shell, stop_event=None):
                return {
                    "exit_code": 2,
                    "stdout": "",
                    "stderr": "regex parse error:\n    [\n    ^\nerror: unclosed character class",
                    "stdout_decode_errors_count": 0,
                    "stderr_decode_errors_count": 0,
                    "timed_out": False,
                    "interrupted": False,
                }

        ctx = FakeRgContext(self.workspace)
        grep_tool = [tool for tool in build_discovery_tools(ctx) if tool.name == "grep_text"][0]

        with self.assertRaisesRegex(Exception, "搜索模式不是有效正则表达式"):
            grep_tool.handler({"pattern": "[", "path": "."})

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
        self.assertEqual(obs.data["additions"], 1)
        self.assertEqual(obs.data["deletions"], 1)
        self.assertIn("@@", obs.data["diff_preview"])
        self.assertEqual(obs.data["changed_files"][0]["path"], "edit_me.py")
        self.assertEqual(obs.data["changed_files"][0]["additions"], 1)
        self.assertEqual(obs.data["changed_files"][0]["deletions"], 1)
        self.assertEqual(obs.data["changed_files"][0]["diff"], obs.data["diff_preview"])
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("x = 2", content)

    def test_edit_file_does_not_stash_or_remove_untracked_target(self):
        target = os.path.join(self.workspace, "untracked.txt")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("before\n")

        class DestructiveSnapshot:
            def __init__(self, _workspace):
                pass

            def create_snapshot(self, reason=""):
                del reason
                os.remove(target)

        with patch(
            "embedagent_host.runtime.tools.file_ops.ShadowGitSnapshot",
            DestructiveSnapshot,
            create=True,
        ):
            obs = self.rt.execute(
                "edit_file",
                {"path": "untracked.txt", "old_text": "before", "new_text": "after"},
            )

        self.assertTrue(obs.success)
        with open(target, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "after\n")

    def test_edit_file_missing_replacement_arguments_is_failure_observation(self):
        with open(os.path.join(self.workspace, "edit_me.py"), "w", encoding="utf-8") as handle:
            handle.write("x = 1\n")

        obs = self.rt.execute("edit_file", {"path": "edit_me.py"})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "tool_error")
        self.assertIn("old_text", obs.error)

    def test_runtime_converts_unexpected_tool_exception_to_failure_observation(self):
        def broken_handler(_arguments):
            raise OSError("file disappeared")

        self.rt.register_tool(
            ToolDefinition(
                name="broken_tool",
                description="test tool",
                parameters={"type": "object", "properties": {}},
                handler=broken_handler,
                metadata={"permission_category": "read"},
            ),
            source_id="tests",
        )

        obs = self.rt.execute("broken_tool", {})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "tool_error")
        self.assertIn("file disappeared", obs.error)

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
        self.assertEqual(obs.data["additions"], 1)
        self.assertEqual(obs.data["deletions"], 0)
        self.assertIn("+# Requirements", obs.data["diff_preview"])
        self.assertEqual(obs.data["changed_files"][0]["path"], "docs/requirements.md")
        self.assertEqual(obs.data["changed_files"][0]["additions"], 1)
        with open(
            os.path.join(self.workspace, "docs", "requirements.md"), "r", encoding="utf-8"
        ) as f:
            content = f.read()
        self.assertEqual(content, "# Requirements\n")

    def test_write_file_identical_overwrite_reports_no_changed_files(self):
        target = os.path.join(self.workspace, "same.txt")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("same\n")

        obs = self.rt.execute(
            "write_file",
            {
                "path": "same.txt",
                "content": "same\n",
                "overwrite": True,
            },
        )

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["additions"], 0)
        self.assertEqual(obs.data["deletions"], 0)
        self.assertEqual(obs.data["diff_preview"], "")
        self.assertEqual(obs.data["changed_files"], [])

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
        self.assertEqual(
            obs.data["read_model_invalidations"],
            ["workspace_files", "tasks", "source_control"],
        )

    def test_runtime_rejects_removed_build_wrapper_tools(self):
        self._register_default_c_workflow_tools()
        for tool_name in ("list_compilers", "configure_build_env", "run_build"):
            obs = self.rt.execute(tool_name, {})
            self.assertFalse(obs.success, tool_name)
            self.assertEqual(obs.tool_name, tool_name)

    def test_mode_aware_execution_shortcut_removed(self):
        self.assertFalse(hasattr(ToolRuntime, "execute_for_mode"))


class TestDiagnosticParsing(unittest.TestCase):
    """Tests for enhanced diagnostic parsing across compiler formats."""

    def setUp(self):
        import tempfile

        self.workspace = tempfile.mkdtemp(prefix="diag-parse-")
        self.ctx = ToolContext(self.workspace)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_clang_single_line_diagnostic(self):
        text = "test.c:10:5: error: use of undeclared identifier 'x'"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["file"], "test.c")
        self.assertEqual(diags[0]["line"], 10)
        self.assertEqual(diags[0]["column"], 5)
        self.assertEqual(diags[0]["level"], "error")
        self.assertEqual(diags[0]["message"], "use of undeclared identifier 'x'")
        self.assertEqual(diags[0]["category"], "compiler")

    def test_clang_no_column_diagnostic(self):
        text = "test.c:10: error: something went wrong"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["line"], 10)
        self.assertEqual(diags[0]["column"], 1)
        self.assertEqual(diags[0]["level"], "error")

    def test_gcc_diagnostic_format(self):
        text = "test.c:20:10: warning: unused variable 'y'"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["file"], "test.c")
        self.assertEqual(diags[0]["line"], 20)
        self.assertEqual(diags[0]["column"], 10)
        self.assertEqual(diags[0]["level"], "warning")
        self.assertEqual(diags[0]["category"], "compiler")

    def test_msvc_diagnostic_format(self):
        text = "test.c(10,5): error C2065: 'x': undeclared identifier"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["file"], "test.c")
        self.assertEqual(diags[0]["line"], 10)
        self.assertEqual(diags[0]["column"], 5)
        self.assertEqual(diags[0]["level"], "error")
        self.assertEqual(diags[0]["category"], "compiler")

    def test_msvc_no_column_diagnostic(self):
        text = "test.c(10): warning C4013: 'foo' undefined"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["line"], 10)
        self.assertEqual(diags[0]["column"], 1)
        self.assertEqual(diags[0]["level"], "warning")

    def test_multi_line_context_capture(self):
        text = (
            "test.c:10:5: error: use of undeclared identifier 'x'\n"
            "   int y = x;\n"
            "           ^\n"
            "test.c:10:5: note: did you mean 'y'?"
        )
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 2)
        self.assertIn("context", diags[0])
        self.assertEqual(len(diags[0]["context"]), 2)
        self.assertEqual(diags[0]["context"][0], "   int y = x;")
        self.assertEqual(diags[0]["context"][1], "           ^")

    def test_linker_diagnostic_classified(self):
        text = "ld: cannot find -lfoo"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["category"], "linker")
        self.assertEqual(diags[0]["level"], "error")
        self.assertEqual(diags[0]["message"], "ld: cannot find -lfoo")

    def test_linker_undefined_reference(self):
        text = "undefined reference to `bar'"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["category"], "linker")
        self.assertEqual(diags[0]["level"], "error")

    def test_linker_lnk_error(self):
        text = "LINK : fatal error LNK1181: cannot open input file 'foo.lib'"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["category"], "linker")
        self.assertEqual(diags[0]["level"], "error")

    def test_mixed_compiler_and_linker_diagnostics(self):
        text = "test.c:1:1: error: syntax error\nld: cannot find -lfoo\ntest.c:2:1: warning: unused"
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 3)
        categories = [d["category"] for d in diags]
        self.assertEqual(categories[0], "compiler")
        self.assertEqual(categories[1], "linker")
        self.assertEqual(categories[2], "compiler")

    def test_diagnostic_counts(self):
        diags = [
            {"level": "error", "category": "compiler"},
            {"level": "warning", "category": "compiler"},
            {"level": "error", "category": "linker"},
            {"level": "note", "category": "compiler"},
        ]
        counts = self.ctx.diagnostic_counts(diags)
        self.assertEqual(counts["error_count"], 2)
        self.assertEqual(counts["warning_count"], 1)
        self.assertEqual(counts["note_count"], 1)

    def test_linker_diagnostic_counts(self):
        diags = [
            {"level": "error", "category": "linker"},
            {"level": "warning", "category": "linker"},
            {"level": "error", "category": "compiler"},
        ]
        counts = self.ctx.linker_diagnostic_counts(diags)
        self.assertEqual(counts["linker_error_count"], 1)
        self.assertEqual(counts["linker_warning_count"], 1)

    def test_max_diagnostics_limit(self):
        text = "\n".join("test.c:%d:1: error: msg" % i for i in range(300))
        diags = self.ctx.parse_diagnostics(text)
        self.assertEqual(len(diags), 200)

    def test_build_diagnostic_observation_includes_linker_counts(self):
        result = {
            "stdout": "",
            "stderr": "ld: cannot find -lfoo\ntest.c:1:1: error: syntax error",
            "exit_code": 1,
            "stdout_truncated": False,
            "stderr_truncated": False,
            "duration_ms": 100,
            "timed_out": False,
            "interrupted": False,
        }
        obs = self.ctx.build_diagnostic_observation("bash", "cmd /c test", self.workspace, result)
        self.assertIn("linker_error_count", obs.data)
        self.assertIn("linker_warning_count", obs.data)
        self.assertIn("linker_diagnostics", obs.data)
        self.assertEqual(obs.data["linker_error_count"], 1)
        self.assertEqual(obs.data["error_count"], 2)


class TestModuleIsolation(unittest.TestCase):
    """Verify each ops module can be imported independently."""

    def test_discovery_ops_importable(self):
        from embedagent_host.runtime.tools import discovery_ops

        self.assertTrue(callable(discovery_ops.build_tools))

    def test_session_ops_importable(self):
        from embedagent_host.runtime.tools import session_ops

        self.assertTrue(callable(session_ops.build_interaction_tools))

    def test_c_workflow_recipe_ops_importable(self):
        from embedagent_workflow_cpp import recipe_ops

        self.assertTrue(callable(recipe_ops.build_tools))

    def test_c_workflow_session_ops_importable(self):
        from embedagent_workflow_cpp import session_ops

        self.assertTrue(callable(session_ops.build_workflow_tools))

    def test_file_ops_importable(self):
        from embedagent_host.runtime.tools import file_ops

        self.assertTrue(callable(file_ops.build_tools))

    def test_shell_ops_importable(self):
        from embedagent_host.runtime.tools import shell_ops

        self.assertTrue(callable(shell_ops.build_tools))

    def test_git_ops_importable(self):
        from embedagent_host.runtime.tools import git_ops

        self.assertTrue(callable(git_ops.build_tools))

    def test_compile_ops_importable(self):
        from embedagent_host.runtime.tools import compile_ops

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
        self._touch(bundle_root, "bin", "git", "bin", "bash.exe")
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
        self.assertEqual(snapshot["tool_sources"]["bash"], "bundle")
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
        import embedagent_host.runtime.tools._base as tools_base

        bundle_root = os.path.join(self.workspace, "portable-bundle")
        workspace_root = os.path.join(bundle_root, "data", "workspace-template")
        os.makedirs(workspace_root)
        fake_module_path = self._touch(
            bundle_root,
            "runtime",
            "site-packages",
            "embedagent_host",
            "runtime",
            "tools",
            "_base.py",
        )
        self._touch(bundle_root, "app", "embedagent", "__init__.py")
        self._touch(bundle_root, "runtime", "python", "python.exe")
        self._touch(bundle_root, "bin", "git", "cmd", "git.exe")
        self._touch(bundle_root, "bin", "git", "bin", "git.exe")
        self._touch(bundle_root, "bin", "git", "bin", "bash.exe")
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
        self.assertEqual(snapshot["tool_sources"]["bash"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["rg"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["ctags"], "bundle")
        self.assertEqual(snapshot["tool_sources"]["llvm"], "bundle")
        self.assertTrue(snapshot["resolved_tool_roots"]["bundle_root"].endswith("portable-bundle"))

    def test_runtime_snapshot_detects_bundle_from_host_source_layout(self):
        import embedagent_host.runtime.tools._base as tools_base

        bundle_root = os.path.join(self.workspace, "source-bundle")
        workspace_root = os.path.join(bundle_root, "data", "workspace-template")
        os.makedirs(workspace_root)
        fake_module_path = self._touch(
            bundle_root,
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "runtime",
            "tools",
            "_base.py",
        )
        self._touch(bundle_root, "app", "embedagent", "__init__.py")
        self._touch(bundle_root, "runtime", "python", "python.exe")
        self._touch(bundle_root, "bin", "rg", "rg.exe")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EMBEDAGENT_BUNDLE_ROOT", None)
            with patch.object(tools_base, "__file__", fake_module_path):
                runtime = ToolRuntime(workspace_root)
                snapshot = runtime.runtime_environment_snapshot()
        self.assertTrue(snapshot["resolved_tool_roots"]["bundle_root"].endswith("source-bundle"))

    def test_runtime_snapshot_does_not_scan_unknown_anchor_ancestors(self):
        import embedagent_host.runtime.tools._base as tools_base

        bundle_root = os.path.join(self.workspace, "unknown-layout-bundle")
        workspace_root = os.path.join(bundle_root, "data", "workspace-template")
        os.makedirs(workspace_root)
        fake_module_path = self._touch(bundle_root, "alpha", "beta", "tools", "_base.py")
        self._touch(bundle_root, "app", "embedagent", "__init__.py")
        self._touch(bundle_root, "runtime", "python", "python.exe")
        self._touch(bundle_root, "bin", "rg", "rg.exe")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EMBEDAGENT_BUNDLE_ROOT", None)
            with patch.object(tools_base, "__file__", fake_module_path):
                runtime = ToolRuntime(workspace_root)
                snapshot = runtime.runtime_environment_snapshot()
        self.assertEqual(snapshot["resolved_tool_roots"]["bundle_root"], "")


class TestRuntimeContractAlignment(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("runtime-contract")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _load_contract(self):
        contract_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "scripts",
            "offline-runtime-contract.json",
        )
        with open(contract_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_runtime_contract_matches_managed_tool_keys(self):
        payload = self._load_contract()
        from embedagent_host.runtime.tools._base import MANAGED_RUNTIME_TOOL_KEYS

        self.assertEqual(
            [item["id"] for item in payload["required_tools"]],
            list(MANAGED_RUNTIME_TOOL_KEYS),
        )

    def test_runtime_contract_commands_are_classified_as_managed(self):
        payload = self._load_contract()
        ctx = ToolContext(self.workspace)

        names = []
        for item in payload["required_tools"]:
            names.extend(item.get("command_names") or [])
            for child in item.get("children") or []:
                names.extend(child.get("command_names") or [])

        classified = {name: ctx.classify_managed_command(name) for name in names}
        self.assertEqual(classified["python"], "python")
        self.assertEqual(classified["git"], "git")
        self.assertEqual(classified["bash"], "bash")
        self.assertEqual(classified["bash.exe"], "bash")
        self.assertEqual(classified["sh"], "bash")
        self.assertEqual(classified["sh.exe"], "bash")
        self.assertEqual(classified["rg"], "rg")
        self.assertEqual(classified["ctags"], "ctags")
        self.assertEqual(classified["clang"], "llvm")
        self.assertEqual(classified["clang++"], "llvm")
        self.assertEqual(classified["clang-cl"], "llvm")
        self.assertEqual(classified["clang-tidy"], "llvm")
        self.assertEqual(classified["clang-analyzer"], "llvm")
        self.assertEqual(classified["llvm-profdata"], "llvm")
        self.assertEqual(classified["llvm-cov"], "llvm")


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
        from embedagent_workflow_cpp.workspace_recipes import list_workspace_recipes

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

    def test_list_recipes_marks_cmake_build_not_ready_without_build_dir(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        from embedagent_workflow_cpp.workspace_recipes import list_workspace_recipes

        payload = list_workspace_recipes(self.workspace)
        build = [item for item in payload["items"] if item["id"] == "cmake.build.default"][0]
        self.assertFalse(build["ready"])
        self.assertEqual(build["confidence"], "medium")
        self.assertIn("cmake.configure.default", build["requires"])
        self.assertIn("suggested_next_step", build)

    def test_project_recipe_is_ready_by_default(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"))
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","command":"echo ok","cwd":"."}]'
            )
        from embedagent_host.runtime.workspace_recipes import list_workspace_recipes

        payload = list_workspace_recipes(self.workspace)
        recipe = [item for item in payload["items"] if item["id"] == "custom.build"][0]
        self.assertTrue(recipe["ready"])
        self.assertEqual(recipe["confidence"], "high")

    def test_generic_workspace_recipes_do_not_detect_cmake_or_default_tool_name(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        os.makedirs(os.path.join(self.workspace, ".embedagent", "recipes"))
        with open(
            os.path.join(self.workspace, ".embedagent", "recipes", "custom.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '{"id":"local.custom","recipe_action":"build","command":"echo ok","cwd":"."}'
            )

        from embedagent_host.runtime.workspace_recipes import list_workspace_recipes

        payload = list_workspace_recipes(self.workspace)
        recipe_ids = [item["id"] for item in payload["items"]]
        self.assertNotIn("cmake.build.default", recipe_ids)
        local = [item for item in payload["items"] if item["id"] == "local.custom"][0]
        self.assertEqual(local.get("tool_name", ""), "")

    @unittest.skipIf(sys.platform != "win32", "Windows-only: requires cmd.exe")
    def test_run_recipe_can_run_cmake_build_recipe_id(self):
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
        register_default_c_workflow_tools(runtime, self.workspace)
        obs = runtime.execute("run_recipe", {"recipe_id": "custom.build"})
        self.assertTrue(obs.success)
        self.assertEqual(obs.data["recipe_id"], "custom.build")
        self.assertEqual(obs.data["recipe_source"], "project")
        self.assertIn("build-ok", obs.data["stdout"])

    def test_resolve_cmake_recipe_applies_target_and_profile(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        os.makedirs(os.path.join(self.workspace, "build", "debug"))
        from embedagent_workflow_cpp.workspace_recipes import resolve_workspace_recipe

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

    def test_run_recipe_refuses_cmake_build_without_configure(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        runtime = ToolRuntime(self.workspace)
        register_default_c_workflow_tools(runtime, self.workspace)

        obs = runtime.execute("run_recipe", {"recipe_id": "cmake.build.default"})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "recipe_prerequisite_missing")
        self.assertFalse(obs.data["retryable"])
        self.assertIn("cmake.configure.default", obs.data["requires"])

    def test_run_recipe_unknown_id_returns_available_alternatives(self):
        runtime = ToolRuntime(self.workspace)
        register_default_c_workflow_tools(runtime, self.workspace)

        obs = runtime.execute("run_recipe", {"recipe_id": "missing"})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "recipe_not_found")
        self.assertFalse(obs.data["retryable"])
        self.assertIn("available_recipes", obs.data)

    @unittest.skipIf(sys.platform != "win32", "Windows-only: requires cmd.exe")
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
        register_default_c_workflow_tools(runtime, self.workspace)
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
        from embedagent_workflow_cpp.workspace_recipes import list_workspace_recipes

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
        from embedagent_workflow_cpp.workspace_recipes import list_workspace_recipes

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
