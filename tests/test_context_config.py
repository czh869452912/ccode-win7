"""Tests for context configuration and ReducerRegistry changes."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.compacted_history import CompactedHistoryCheckpoint
from embedagent.config import AppConfig
from embedagent.context import (
    ContextConfig,
    ContextManager,
    ReducerRegistry,
    make_context_config,
)
from embedagent.harness.extension import CHarnessWorkflowExtension
from embedagent.session import AssistantReply, Observation, Session


class TestMakeContextConfig(unittest.TestCase):
    def test_none_returns_default_config(self):
        cfg = make_context_config(None)
        self.assertIsInstance(cfg, ContextConfig)
        self.assertEqual(cfg.default_max_context_tokens, 18000)

    def test_empty_app_config_returns_defaults(self):
        cfg = make_context_config(AppConfig())
        self.assertEqual(cfg.default_max_context_tokens, 18000)
        self.assertEqual(cfg.default_reserve_output_tokens, 2000)

    def test_max_context_tokens_override(self):
        cfg = make_context_config(AppConfig(max_context_tokens=32000))
        self.assertEqual(cfg.default_max_context_tokens, 32000)

    def test_reserve_output_tokens_override(self):
        cfg = make_context_config(AppConfig(reserve_output_tokens=4096))
        self.assertEqual(cfg.default_reserve_output_tokens, 4096)

    def test_chars_per_token_override(self):
        cfg = make_context_config(AppConfig(chars_per_token=4.0))
        self.assertAlmostEqual(cfg.estimated_chars_per_token, 4.0)

    def test_max_recent_turns_override(self):
        cfg = make_context_config(AppConfig(max_recent_turns=8))
        self.assertEqual(cfg.default_max_recent_turns, 8)

    def test_auto_compact_threshold_ratio_override(self):
        cfg = make_context_config(AppConfig(auto_compact_threshold_ratio=0.77))
        self.assertAlmostEqual(cfg.auto_compact_threshold_ratio, 0.77)

    def test_unset_fields_use_defaults(self):
        cfg = make_context_config(AppConfig(max_context_tokens=32000))
        # reserve_output_tokens not set → should stay at default
        self.assertEqual(cfg.default_reserve_output_tokens, 2000)

    def test_partial_overrides_preserve_mode_overrides(self):
        cfg = make_context_config(AppConfig(max_context_tokens=32000))
        # mode_overrides should still be present with original values
        self.assertIn("build", cfg.mode_overrides)
        self.assertIn("explore", cfg.mode_overrides)


class TestReducerRegistryTasks(unittest.TestCase):
    def setUp(self):
        self.registry = ReducerRegistry()
        self.policy = ContextConfig().mode_overrides.get("build", {})

    def _make_policy(self):
        from embedagent.context import ContextConfig, ContextPolicy

        cfg = ContextConfig()
        overrides = cfg.mode_overrides.get("build", {})
        return ContextPolicy(
            mode_name="build",
            max_context_tokens=overrides.get("max_context_tokens", cfg.default_max_context_tokens),
            reserve_output_tokens=overrides.get(
                "reserve_output_tokens", cfg.default_reserve_output_tokens
            ),
            reserve_reasoning_tokens=overrides.get(
                "reserve_reasoning_tokens", cfg.default_reserve_reasoning_tokens
            ),
            max_recent_turns=overrides.get("max_recent_turns", cfg.default_max_recent_turns),
            min_recent_turns=cfg.default_min_recent_turns,
            max_summary_turns=overrides.get("max_summary_turns", cfg.default_max_summary_turns),
            recent_message_chars=overrides.get(
                "recent_message_chars", cfg.default_recent_message_chars
            ),
            recent_tool_chars=overrides.get("recent_tool_chars", cfg.default_recent_tool_chars),
            summary_text_chars=overrides.get("summary_text_chars", cfg.default_summary_text_chars),
            summary_tool_chars=overrides.get("summary_tool_chars", cfg.default_summary_tool_chars),
            hard_message_chars=overrides.get("hard_message_chars", cfg.default_hard_message_chars),
            hard_tool_chars=overrides.get("hard_tool_chars", cfg.default_hard_tool_chars),
            project_memory_chars=overrides.get(
                "project_memory_chars", cfg.default_project_memory_chars
            ),
        )

    def _register_default_c_workflow_context(self):
        CHarnessWorkflowExtension().register_context_reducers(self.registry)

    def test_bare_registry_omits_c_workflow_reducers(self):
        self.assertIn("bash", self.registry._reducers)
        self.assertNotIn("run_command", self.registry._reducers)
        self.assertNotIn("list_recipes", self.registry._reducers)
        self.assertNotIn("run_recipe", self.registry._reducers)
        self.assertNotIn("report_quality_v2", self.registry._reducers)
        self.assertNotIn("task_status", self.registry._reducers)
        self.assertNotIn("record_failing_evidence", self.registry._reducers)
        self.assertNotIn("list_compilers", self.registry._reducers)
        self.assertNotIn("configure_build_env", self.registry._reducers)
        self.assertNotIn("run_build", self.registry._reducers)
        self.assertNotIn("manage_todos", self.registry._reducers)

    def test_bare_registry_does_not_define_c_workflow_reducer_methods(self):
        self.assertFalse(hasattr(self.registry, "_reduce_recipe_result"))
        self.assertFalse(hasattr(self.registry, "_reduce_quality"))
        self.assertFalse(hasattr(self.registry, "_reduce_tasks"))

    def test_default_c_workflow_extension_registers_context_reducers(self):
        self._register_default_c_workflow_context()

        self.assertIn("list_recipes", self.registry._reducers)
        self.assertIn("run_recipe", self.registry._reducers)
        self.assertIn("report_quality_v2", self.registry._reducers)
        self.assertIn("task_status", self.registry._reducers)
        self.assertIn("record_failing_evidence", self.registry._reducers)
        self.assertNotIn("list_compilers", self.registry._reducers)
        self.assertNotIn("configure_build_env", self.registry._reducers)
        self.assertNotIn("run_build", self.registry._reducers)

    def test_reduce_task_status_list_action(self):
        self._register_default_c_workflow_context()
        policy = self._make_policy()
        data = {
            "action": "list",
            "count": 2,
            "tasks": [
                {"id": 1, "content": "任务1", "done": False},
                {"id": 2, "content": "任务2", "done": True},
            ],
        }
        result = self.registry.reduce_tool_data("task_status", data, detailed=True, policy=policy)
        self.assertEqual(result["action"], "list")
        self.assertEqual(result["count"], 2)
        self.assertIn("tasks", result)

    def test_reduce_task_status_add_action(self):
        self._register_default_c_workflow_context()
        policy = self._make_policy()
        data = {"action": "add", "id": 3, "content": "新任务"}
        result = self.registry.reduce_tool_data("task_status", data, detailed=True, policy=policy)
        self.assertEqual(result["action"], "add")
        self.assertEqual(result["id"], 3)
        self.assertEqual(result["content"], "新任务")

    def test_reduce_task_status_remove_action(self):
        self._register_default_c_workflow_context()
        policy = self._make_policy()
        data = {"action": "remove", "removed_id": 2, "remaining": 1}
        result = self.registry.reduce_tool_data("task_status", data, detailed=False, policy=policy)
        self.assertEqual(result["removed_id"], 2)
        self.assertEqual(result["remaining"], 1)

    def test_summarize_task_status_observation(self):
        self._register_default_c_workflow_context()
        policy = self._make_policy()
        obs = Observation(
            tool_name="task_status",
            success=True,
            error=None,
            data={"action": "add", "id": 1, "content": "任务1"},
        )
        summary = self.registry.summarize_observation(obs, detailed=False, policy=policy)
        self.assertIn("task_status", summary)
        self.assertIn("success", summary)

    def test_reduce_list_dir_preview(self):
        policy = self._make_policy()
        data = {
            "path": "src",
            "preview": ["main.c", "util.c", "include/"],
            "returned_count": 3,
            "total_count": 8,
            "has_more": True,
            "next_offset": 3,
        }
        result = self.registry.reduce_tool_data("list_dir", data, detailed=True, policy=policy)
        self.assertEqual(result["returned_count"], 3)
        self.assertIn("files", result)
        self.assertIn("main.c", result["files"][0])

    def test_reduce_bash_command_result(self):
        policy = self._make_policy()
        data = {
            "command": "echo ok",
            "exit_code": 0,
            "stdout": "ok\n",
            "stderr": "",
            "stdout_encoding": "utf-8",
            "stderr_encoding": "utf-8",
            "stdout_decode_errors_count": 0,
            "stderr_decode_errors_count": 0,
            "full_output_ref": ".embedagent/memory/command-output/example.txt",
        }
        result = self.registry.reduce_tool_data("bash", data, detailed=True, policy=policy)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout_encoding"], "utf-8")
        self.assertIn("stdout_preview", result)
        self.assertEqual(result["full_output_ref"], data["full_output_ref"])

    def test_reduce_report_quality_v2(self):
        self._register_default_c_workflow_context()
        policy = self._make_policy()
        data = {"passed": False, "error_count": 1, "warning_count": 2, "test_failures": 3}
        result = self.registry.reduce_tool_data(
            "report_quality_v2", data, detailed=False, policy=policy
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["test_failures"], 3)

    def test_bare_registry_has_no_c_workflow_priority_tools(self):
        self.assertNotIn("run_recipe", self.registry.high_priority_tool_names())
        self.assertNotIn("report_quality_v2", self.registry.high_priority_tool_names())

    def test_default_c_workflow_extension_registers_priority_tools(self):
        self._register_default_c_workflow_context()

        self.assertNotIn("run_build", self.registry.high_priority_tool_names())
        self.assertIn("run_recipe", self.registry.high_priority_tool_names())
        self.assertIn("report_quality_v2", self.registry.high_priority_tool_names())
        self.assertNotIn("compile_project", self.registry.high_priority_tool_names())
        self.assertNotIn("report_quality", self.registry.high_priority_tool_names())


class TestContextConfigModeOverrides(unittest.TestCase):
    def test_mode_overrides_all_modes_present(self):
        cfg = ContextConfig()
        for mode in ("explore", "spec", "build", "verify", "debug", "compact"):
            self.assertIn(mode, cfg.mode_overrides)

    def test_compact_has_smaller_budgets(self):
        cfg = ContextConfig()
        compact = cfg.mode_overrides["compact"]
        code = cfg.mode_overrides["build"]
        self.assertLess(compact["max_context_tokens"], code["max_context_tokens"])


class TestContextCompactionSignal(unittest.TestCase):
    def test_old_turns_alone_do_not_mark_compacted(self):
        cfg = ContextConfig()
        cfg.default_max_recent_turns = 1
        cfg.mode_overrides["build"]["max_recent_turns"] = 1
        manager = ContextManager(config=cfg)
        session = Session(session_id="sess-compaction")
        session.add_user_message("first turn", turn_id="turn-1")
        session.add_system_message("assistant one", turn_id="turn-1")
        session.add_user_message("second turn", turn_id="turn-2")
        session.add_system_message("assistant two", turn_id="turn-2")
        with mock.patch.object(manager, "_measure_messages", return_value=100):
            result = manager.build_messages(session, mode_name="build")
        self.assertFalse(result.compacted)

    def test_build_messages_returns_explicit_context_plan(self):
        manager = ContextManager()
        session = Session(session_id="sess-context-plan")
        session.add_system_message("mode: build")
        session.add_user_message("hello", turn_id="turn-1")
        session.add_assistant_reply(
            AssistantReply(content="world", actions=[], finish_reason="stop")
        )

        result = manager.build_messages(session, mode_name="build")

        self.assertTrue(hasattr(result, "plan"))
        self.assertEqual(result.plan.mode_name, result.policy.mode_name)
        self.assertEqual(result.plan.approx_tokens, result.approx_tokens)
        self.assertEqual(result.plan.selected_message_count, len(result.messages))
        self.assertEqual(result.plan.pipeline_steps, result.pipeline_steps)
        self.assertEqual(result.plan.to_boundary_metadata()["approx_tokens"], result.approx_tokens)
        self.assertIn("message_counts", result.plan.to_boundary_payload_fields())

    def test_build_messages_uses_latest_compacted_history_checkpoint_as_base(self):
        manager = ContextManager()
        session = Session(session_id="sess-checkpoint-context")
        session.add_system_message("mode: build", message_id="m-system")
        session.add_user_message("old user", turn_id="turn-old", message_id="m-old-user")
        session.add_assistant_reply(
            AssistantReply(content="old assistant", actions=[], finish_reason="stop"),
            message_id="m-old-assistant",
        )
        session.add_user_message("new user", turn_id="turn-new", message_id="m-new-user")
        session.record_compacted_history(
            CompactedHistoryCheckpoint(
                checkpoint_id="ch-ctx",
                summary_text="Old work was compacted.",
                first_kept_message_id="m-new-user",
                replacement_messages=[
                    {
                        "role": "system",
                        "content": "Compacted history summary:\nOld work was compacted.",
                        "kind": "compacted_history_summary",
                    }
                ],
            )
        )

        result = manager.build_messages(session, mode_name="build")
        contents = [item.get("content") for item in result.messages]

        self.assertIn("Compacted history summary:\nOld work was compacted.", contents)
        self.assertIn("new user", contents)
        self.assertNotIn("old user", contents)
        self.assertNotIn("old assistant", contents)
        self.assertIn("compacted_history_checkpoint", result.pipeline_steps)

    def test_near_full_window_uses_compact_policy_before_provider(self):
        cfg = ContextConfig(auto_compact_threshold_ratio=0.01)
        cfg.mode_overrides["build"].update(
            {
                "max_context_tokens": 50000,
                "reserve_output_tokens": 0,
                "reserve_reasoning_tokens": 0,
                "max_recent_turns": 4,
            }
        )
        cfg.mode_overrides["compact"].update(
            {
                "max_context_tokens": 15000,
                "reserve_output_tokens": 0,
                "reserve_reasoning_tokens": 0,
                "max_recent_turns": 2,
                "max_summary_turns": 6,
            }
        )
        manager = ContextManager(config=cfg)
        session = Session(session_id="sess-auto-compact")
        session.add_system_message("mode: build")
        for index in range(5):
            session.add_user_message("old user %s %s" % (index, "u" * 900))
            session.add_assistant_reply(
                AssistantReply(
                    content="old assistant %s %s" % (index, "a" * 700),
                    actions=[],
                    finish_reason="stop",
                )
            )

        result = manager.build_messages(session, mode_name="build")

        self.assertEqual(result.policy.mode_name, "compact")
        self.assertIn("auto_compact_threshold", result.pipeline_steps)
        self.assertNotIn("reactive_compact_retry", result.pipeline_steps)
        self.assertGreater(result.summarized_turns, 0)

    def test_auto_compact_does_not_use_stale_usage_after_compaction(self):
        cfg = ContextConfig(auto_compact_threshold_ratio=0.01)
        cfg.mode_overrides["build"].update(
            {
                "max_context_tokens": 1000,
                "reserve_output_tokens": 0,
                "reserve_reasoning_tokens": 0,
                "max_recent_turns": 4,
            }
        )
        manager = ContextManager(config=cfg)
        session = Session(session_id="sess-stale-usage")
        session.add_user_message("before compact")
        session.add_assistant_reply(
            AssistantReply(
                content="large response",
                actions=[],
                finish_reason="stop",
                usage={"prompt_tokens": 950, "completion_tokens": 10, "total_tokens": 960},
            )
        )
        boundary = session.add_compact_boundary("summary", 1, "build", {})
        boundary.preserved_tail_message_id = session.messages[-1].message_id

        result = manager.build_messages(session, mode_name="build")

        self.assertNotIn("auto_compact_threshold", result.pipeline_steps)
        self.assertEqual(result.context_usage.source, "unknown_after_compaction")


if __name__ == "__main__":
    unittest.main()
