"""Tests for context configuration and ReducerRegistry changes."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.config import AppConfig
from embedagent.context import ContextConfig, ContextManager, make_context_config, ReducerRegistry
from embedagent.session import Observation, Session


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

    def test_unset_fields_use_defaults(self):
        cfg = make_context_config(AppConfig(max_context_tokens=32000))
        # reserve_output_tokens not set → should stay at default
        self.assertEqual(cfg.default_reserve_output_tokens, 2000)

    def test_partial_overrides_preserve_mode_overrides(self):
        cfg = make_context_config(AppConfig(max_context_tokens=32000))
        # mode_overrides should still be present with original values
        self.assertIn("code", cfg.mode_overrides)
        self.assertIn("ask", cfg.mode_overrides)


class TestReducerRegistryTodos(unittest.TestCase):
    def setUp(self):
        self.registry = ReducerRegistry()
        self.policy = ContextConfig().mode_overrides.get("code", {})

    def _make_policy(self):
        from embedagent.context import ContextConfig, ContextPolicy
        cfg = ContextConfig()
        overrides = cfg.mode_overrides.get("code", {})
        return ContextPolicy(
            mode_name="code",
            max_context_tokens=overrides.get("max_context_tokens", cfg.default_max_context_tokens),
            reserve_output_tokens=overrides.get("reserve_output_tokens", cfg.default_reserve_output_tokens),
            reserve_reasoning_tokens=overrides.get("reserve_reasoning_tokens", cfg.default_reserve_reasoning_tokens),
            max_recent_turns=overrides.get("max_recent_turns", cfg.default_max_recent_turns),
            min_recent_turns=cfg.default_min_recent_turns,
            max_summary_turns=overrides.get("max_summary_turns", cfg.default_max_summary_turns),
            recent_message_chars=overrides.get("recent_message_chars", cfg.default_recent_message_chars),
            recent_tool_chars=overrides.get("recent_tool_chars", cfg.default_recent_tool_chars),
            summary_text_chars=overrides.get("summary_text_chars", cfg.default_summary_text_chars),
            summary_tool_chars=overrides.get("summary_tool_chars", cfg.default_summary_tool_chars),
            hard_message_chars=overrides.get("hard_message_chars", cfg.default_hard_message_chars),
            hard_tool_chars=overrides.get("hard_tool_chars", cfg.default_hard_tool_chars),
            project_memory_chars=overrides.get("project_memory_chars", cfg.default_project_memory_chars),
        )

    def test_todos_reducer_registered(self):
        self.assertIn("manage_todos", self.registry._reducers)

    def test_reduce_list_action(self):
        policy = self._make_policy()
        data = {
            "action": "list",
            "count": 2,
            "todos": [
                {"id": 1, "content": "任务1", "done": False},
                {"id": 2, "content": "任务2", "done": True},
            ],
        }
        result = self.registry.reduce_tool_data("manage_todos", data, detailed=True, policy=policy)
        self.assertEqual(result["action"], "list")
        self.assertEqual(result["count"], 2)
        self.assertIn("todos", result)

    def test_reduce_add_action(self):
        policy = self._make_policy()
        data = {"action": "add", "id": 3, "content": "新任务"}
        result = self.registry.reduce_tool_data("manage_todos", data, detailed=True, policy=policy)
        self.assertEqual(result["action"], "add")
        self.assertEqual(result["id"], 3)
        self.assertEqual(result["content"], "新任务")

    def test_reduce_remove_action(self):
        policy = self._make_policy()
        data = {"action": "remove", "removed_id": 2, "remaining": 1}
        result = self.registry.reduce_tool_data("manage_todos", data, detailed=False, policy=policy)
        self.assertEqual(result["removed_id"], 2)
        self.assertEqual(result["remaining"], 1)

    def test_summarize_todos_observation(self):
        policy = self._make_policy()
        obs = Observation(
            tool_name="manage_todos",
            success=True,
            error=None,
            data={"action": "add", "id": 1, "content": "任务1"},
        )
        summary = self.registry.summarize_observation(obs, detailed=False, policy=policy)
        self.assertIn("manage_todos", summary)
        self.assertIn("success", summary)


class TestContextConfigModeOverrides(unittest.TestCase):
    def test_mode_overrides_all_modes_present(self):
        cfg = ContextConfig()
        for mode in ("ask", "orchestra", "spec", "code", "test", "verify", "debug", "compact"):
            self.assertIn(mode, cfg.mode_overrides)

    def test_compact_has_smaller_budgets(self):
        cfg = ContextConfig()
        compact = cfg.mode_overrides["compact"]
        code = cfg.mode_overrides["code"]
        self.assertLess(compact["max_context_tokens"], code["max_context_tokens"])


class TestContextCompactionSignal(unittest.TestCase):
    def test_old_turns_alone_do_not_mark_compacted(self):
        cfg = ContextConfig()
        cfg.default_max_recent_turns = 1
        cfg.mode_overrides["code"]["max_recent_turns"] = 1
        manager = ContextManager(config=cfg)
        session = Session(session_id="sess-compaction")
        session.add_user_message("first turn", turn_id="turn-1")
        session.add_system_message("assistant one", turn_id="turn-1")
        session.add_user_message("second turn", turn_id="turn-2")
        session.add_system_message("assistant two", turn_id="turn-2")
        with mock.patch.object(manager, "_measure_messages", return_value=100):
            result = manager.build_messages(session, mode_name="code")
        self.assertFalse(result.compacted)


if __name__ == "__main__":
    unittest.main()
