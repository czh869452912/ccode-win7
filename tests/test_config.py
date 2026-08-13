"""Tests for embedagent.config module."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.config import AppConfig, _load_json_file, _merge, load_config


class TestAppConfigDefaults(unittest.TestCase):
    def test_all_fields_default_to_none(self):
        cfg = AppConfig()
        for field in (
            "base_url",
            "api_key",
            "model",
            "timeout",
            "max_context_tokens",
            "reserve_output_tokens",
            "chars_per_token",
            "max_recent_turns",
            "max_turns",
            "default_mode",
            "agent_application_id",
        ):
            self.assertIsNone(getattr(cfg, field), "%s should be None" % field)

    def test_mode_writable_globs_default_empty(self):
        cfg = AppConfig()
        self.assertEqual(cfg.mode_writable_globs, {})
        self.assertEqual(cfg.mode_extra_writable_globs, {})

    def test_explicit_values(self):
        cfg = AppConfig(max_context_tokens=32000, model="qwen3")
        self.assertEqual(cfg.max_context_tokens, 32000)
        self.assertEqual(cfg.model, "qwen3")

    def test_config_template_uses_current_architecture_defaults(self):
        template_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "config.json.template",
        )
        with open(template_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        self.assertIsNone(payload.get("max_turns"))
        self.assertEqual(payload.get("default_mode"), "explore")
        self.assertNotIn("agent_application_id", payload)
        self.assertNotIn("embedagent.default_c_cpp", json.dumps(payload))

    def test_current_config_docs_do_not_show_removed_defaults(self):
        repo_root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
        paths = [
            os.path.join(repo_root, "src", "embedagent", "config.py"),
            os.path.join(repo_root, "config", "config.json.template"),
            os.path.join(repo_root, "docs", "guides", "configuration-guide.md"),
            os.path.join(repo_root, "docs", "guides", "intranet-deployment.md"),
        ]
        stale_markers = (
            '"default_mode": "code"',
            '"default_mode": "build"',
            '"max_turns": 8',
            '"agent_application_id": "embedagent.default_c_cpp"',
            "CMakeLists.txt",
        )
        for path in paths:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            for marker in stale_markers:
                self.assertNotIn(marker, text, "%s leaked in %s" % (marker, path))


class TestLoadJsonFile(unittest.TestCase):
    def test_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"model": "test-model", "max_context_tokens": 8000}, f)
            path = f.name
        try:
            data = _load_json_file(path)
            self.assertEqual(data["model"], "test-model")
            self.assertEqual(data["max_context_tokens"], 8000)
        finally:
            os.unlink(path)

    def test_missing_file_returns_empty(self):
        self.assertEqual(_load_json_file("/nonexistent/path.json"), {})

    def test_invalid_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            path = f.name
        try:
            self.assertEqual(_load_json_file(path), {})
        finally:
            os.unlink(path)

    def test_json_array_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([1, 2, 3], f)
            path = f.name
        try:
            self.assertEqual(_load_json_file(path), {})
        finally:
            os.unlink(path)


class TestMerge(unittest.TestCase):
    def test_simple_field_override(self):
        base = AppConfig(model="old-model", max_context_tokens=8000)
        result = _merge(base, {"model": "new-model"})
        self.assertEqual(result.model, "new-model")
        self.assertEqual(result.max_context_tokens, 8000)  # preserved

    def test_none_value_not_overriding(self):
        base = AppConfig(model="my-model")
        result = _merge(base, {"model": None})
        self.assertEqual(result.model, "my-model")

    def test_mode_writable_globs_merged(self):
        base = AppConfig(mode_writable_globs={"build": ["**/*.c"]})
        result = _merge(base, {"mode_writable_globs": {"spec": ["**/*.md"]}})
        self.assertIn("build", result.mode_writable_globs)
        self.assertIn("spec", result.mode_writable_globs)

    def test_mode_extra_writable_globs_merged(self):
        base = AppConfig(mode_extra_writable_globs={"build": ["**/*.cmake"]})
        result = _merge(base, {"mode_extra_writable_globs": {"spec": ["**/*.adoc"]}})
        self.assertIn("build", result.mode_extra_writable_globs)
        self.assertIn("spec", result.mode_extra_writable_globs)

    def test_mode_writable_globs_overrides_existing_mode(self):
        base = AppConfig(mode_writable_globs={"build": ["old/*.py"]})
        result = _merge(base, {"mode_writable_globs": {"build": ["new/*.py"]}})
        self.assertEqual(result.mode_writable_globs["build"], ["new/*.py"])

    def test_mode_extra_writable_globs_overrides_existing_mode(self):
        base = AppConfig(mode_extra_writable_globs={"build": ["old/*.py"]})
        result = _merge(base, {"mode_extra_writable_globs": {"build": ["new/*.py"]}})
        self.assertEqual(result.mode_extra_writable_globs["build"], ["new/*.py"])

    def test_numeric_type_coercion(self):
        base = AppConfig()
        result = _merge(base, {"timeout": 60})
        self.assertEqual(result.timeout, 60)

    def test_nested_sections_are_merged(self):
        base = AppConfig()
        result = _merge(
            base,
            {
                "llm": {
                    "base_url": "http://internal/v1",
                    "api_key": "sk-test",
                    "model": "qwen3.5-coder",
                    "timeout": 45,
                },
                "context": {
                    "max_context_tokens": 32000,
                    "reserve_output_tokens": 3000,
                    "chars_per_token": 3.5,
                    "max_recent_turns": 4,
                },
                "session": {"max_turns": 12},
            },
        )
        self.assertEqual(result.base_url, "http://internal/v1")
        self.assertEqual(result.api_key, "sk-test")
        self.assertEqual(result.model, "qwen3.5-coder")
        self.assertEqual(result.timeout, 45)
        self.assertEqual(result.max_context_tokens, 32000)
        self.assertEqual(result.reserve_output_tokens, 3000)
        self.assertEqual(result.chars_per_token, 3.5)
        self.assertEqual(result.max_recent_turns, 4)
        self.assertIsNone(result.max_turns)

    def test_persistent_max_turns_is_ignored(self):
        base = AppConfig(max_turns=None)

        result = _merge(base, {"max_turns": 8, "session": {"max_turns": 12}})

        self.assertIsNone(result.max_turns)


class TestLoadConfig(unittest.TestCase):
    def test_user_config_is_loaded_before_project_config(self):
        with tempfile.TemporaryDirectory() as root:
            user_home = os.path.join(root, "user")
            workspace = os.path.join(root, "workspace")
            user_config_dir = os.path.join(user_home, ".embedagent")
            project_config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(user_config_dir)
            os.makedirs(project_config_dir)
            with open(os.path.join(user_config_dir, "config.json"), "w") as handle:
                json.dump(
                    {
                        "model": "user-model",
                        "base_url": "http://user/v1",
                        "approve_writes": True,
                    },
                    handle,
                )
            with open(os.path.join(project_config_dir, "config.json"), "w") as handle:
                json.dump({"model": "project-model"}, handle)

            with patch("embedagent.config.os.path.expanduser", return_value=user_home):
                cfg = load_config(workspace)

            self.assertEqual(cfg.model, "project-model")
            self.assertEqual(cfg.base_url, "http://user/v1")
            self.assertTrue(cfg.approve_writes)

    def test_no_config_files_returns_defaults(self):
        with tempfile.TemporaryDirectory() as workspace:
            with tempfile.TemporaryDirectory() as user_config_dir, patch(
                "embedagent.config._USER_CONFIG_DIR", user_config_dir
            ):
                cfg = load_config(workspace)
            self.assertIsNone(cfg.model)
            self.assertEqual(cfg.mode_writable_globs, {})
            self.assertEqual(cfg.mode_extra_writable_globs, {})

    def test_project_config_loaded(self):
        with tempfile.TemporaryDirectory() as workspace:
            config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(config_dir)
            config_path = os.path.join(config_dir, "config.json")
            with open(config_path, "w") as f:
                json.dump({"model": "project-model", "max_context_tokens": 16000}, f)
            with tempfile.TemporaryDirectory() as user_config_dir, patch(
                "embedagent.config._USER_CONFIG_DIR", user_config_dir
            ):
                cfg = load_config(workspace)
            self.assertEqual(cfg.model, "project-model")
            self.assertEqual(cfg.max_context_tokens, 16000)

    def test_load_config_ignores_legacy_user_max_turns(self):
        with tempfile.TemporaryDirectory() as workspace:
            with tempfile.TemporaryDirectory() as user_config_dir, patch(
                "embedagent.config._USER_CONFIG_DIR", user_config_dir
            ):
                with open(os.path.join(user_config_dir, "config.json"), "w") as f:
                    json.dump({"model": "user-model", "max_turns": 8}, f)

                cfg = load_config(workspace)

            self.assertEqual(cfg.model, "user-model")
            self.assertIsNone(cfg.max_turns)

    def test_project_config_overrides_user_config(self):
        # We can't easily test user config (~/.embedagent) without side effects,
        # so we test the merge priority logic via _merge directly instead.
        base = AppConfig(model="user-model", max_context_tokens=8000)
        project_override = {"model": "project-model"}
        result = _merge(base, project_override)
        self.assertEqual(result.model, "project-model")
        self.assertEqual(result.max_context_tokens, 8000)

    def test_invalid_project_config_silently_ignored(self):
        with tempfile.TemporaryDirectory() as workspace:
            config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(config_dir)
            config_path = os.path.join(config_dir, "config.json")
            with open(config_path, "w") as f:
                f.write("{ invalid json }")
            with tempfile.TemporaryDirectory() as user_config_dir, patch(
                "embedagent.config._USER_CONFIG_DIR", user_config_dir
            ):
                cfg = load_config(workspace)
            self.assertIsNone(cfg.model)

    def test_mode_writable_globs_in_project_config(self):
        with tempfile.TemporaryDirectory() as workspace:
            config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(config_dir)
            config_path = os.path.join(config_dir, "config.json")
            with open(config_path, "w") as f:
                json.dump({"mode_writable_globs": {"build": ["app/**/*.py"]}}, f)
            with tempfile.TemporaryDirectory() as user_config_dir, patch(
                "embedagent.config._USER_CONFIG_DIR", user_config_dir
            ):
                cfg = load_config(workspace)
            self.assertEqual(cfg.mode_writable_globs["build"], ["app/**/*.py"])

    def test_mode_extra_writable_globs_in_project_config(self):
        with tempfile.TemporaryDirectory() as workspace:
            config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(config_dir)
            config_path = os.path.join(config_dir, "config.json")
            with open(config_path, "w") as f:
                json.dump({"mode_extra_writable_globs": {"build": ["**/*.cmake"]}}, f)
            with tempfile.TemporaryDirectory() as user_config_dir, patch(
                "embedagent.config._USER_CONFIG_DIR", user_config_dir
            ):
                cfg = load_config(workspace)
            self.assertEqual(cfg.mode_extra_writable_globs["build"], ["**/*.cmake"])

    def test_nested_project_config_loaded(self):
        with tempfile.TemporaryDirectory() as workspace:
            config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(config_dir)
            config_path = os.path.join(config_dir, "config.json")
            with open(config_path, "w") as f:
                json.dump(
                    {
                        "llm": {
                            "base_url": "http://nested/v1",
                            "api_key": "nested-key",
                            "model": "nested-model",
                            "timeout": 90,
                        },
                        "context": {
                            "max_context_tokens": 24000,
                            "reserve_output_tokens": 2500,
                        },
                    },
                    f,
                )
            with tempfile.TemporaryDirectory() as user_config_dir, patch(
                "embedagent.config._USER_CONFIG_DIR", user_config_dir
            ):
                cfg = load_config(workspace)
            self.assertEqual(cfg.base_url, "http://nested/v1")
            self.assertEqual(cfg.api_key, "nested-key")
            self.assertEqual(cfg.model, "nested-model")
            self.assertEqual(cfg.timeout, 90)
            self.assertEqual(cfg.max_context_tokens, 24000)
            self.assertEqual(cfg.reserve_output_tokens, 2500)


if __name__ == "__main__":
    unittest.main()
