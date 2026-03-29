"""Tests for embedagent.config module."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.config import AppConfig, load_config, _merge, _load_json_file


class TestAppConfigDefaults(unittest.TestCase):
    def test_all_fields_default_to_none(self):
        cfg = AppConfig()
        for field in ("base_url", "api_key", "model", "timeout",
                      "max_context_tokens", "reserve_output_tokens",
                      "chars_per_token", "max_recent_turns",
                      "max_turns", "default_mode"):
            self.assertIsNone(getattr(cfg, field), "%s should be None" % field)

    def test_mode_writable_globs_default_empty(self):
        cfg = AppConfig()
        self.assertEqual(cfg.mode_writable_globs, {})
        self.assertEqual(cfg.mode_extra_writable_globs, {})

    def test_explicit_values(self):
        cfg = AppConfig(max_context_tokens=32000, model="qwen3")
        self.assertEqual(cfg.max_context_tokens, 32000)
        self.assertEqual(cfg.model, "qwen3")


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
        base = AppConfig(mode_writable_globs={"code": ["**/*.c"]})
        result = _merge(base, {"mode_writable_globs": {"spec": ["**/*.md"]}})
        self.assertIn("code", result.mode_writable_globs)
        self.assertIn("spec", result.mode_writable_globs)

    def test_mode_extra_writable_globs_merged(self):
        base = AppConfig(mode_extra_writable_globs={"code": ["**/*.cmake"]})
        result = _merge(base, {"mode_extra_writable_globs": {"spec": ["**/*.adoc"]}})
        self.assertIn("code", result.mode_extra_writable_globs)
        self.assertIn("spec", result.mode_extra_writable_globs)

    def test_mode_writable_globs_overrides_existing_mode(self):
        base = AppConfig(mode_writable_globs={"code": ["old/*.py"]})
        result = _merge(base, {"mode_writable_globs": {"code": ["new/*.py"]}})
        self.assertEqual(result.mode_writable_globs["code"], ["new/*.py"])

    def test_mode_extra_writable_globs_overrides_existing_mode(self):
        base = AppConfig(mode_extra_writable_globs={"code": ["old/*.py"]})
        result = _merge(base, {"mode_extra_writable_globs": {"code": ["new/*.py"]}})
        self.assertEqual(result.mode_extra_writable_globs["code"], ["new/*.py"])

    def test_numeric_type_coercion(self):
        base = AppConfig()
        result = _merge(base, {"timeout": 60})
        self.assertEqual(result.timeout, 60)


class TestLoadConfig(unittest.TestCase):
    def test_no_config_files_returns_defaults(self):
        with tempfile.TemporaryDirectory() as workspace:
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
            cfg = load_config(workspace)
            self.assertEqual(cfg.model, "project-model")
            self.assertEqual(cfg.max_context_tokens, 16000)

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
            cfg = load_config(workspace)
            self.assertIsNone(cfg.model)

    def test_mode_writable_globs_in_project_config(self):
        with tempfile.TemporaryDirectory() as workspace:
            config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(config_dir)
            config_path = os.path.join(config_dir, "config.json")
            with open(config_path, "w") as f:
                json.dump({"mode_writable_globs": {"code": ["app/**/*.py"]}}, f)
            cfg = load_config(workspace)
            self.assertEqual(cfg.mode_writable_globs["code"], ["app/**/*.py"])

    def test_mode_extra_writable_globs_in_project_config(self):
        with tempfile.TemporaryDirectory() as workspace:
            config_dir = os.path.join(workspace, ".embedagent")
            os.makedirs(config_dir)
            config_path = os.path.join(config_dir, "config.json")
            with open(config_path, "w") as f:
                json.dump({"mode_extra_writable_globs": {"code": ["**/*.cmake"]}}, f)
            cfg = load_config(workspace)
            self.assertEqual(cfg.mode_extra_writable_globs["code"], ["**/*.cmake"])


if __name__ == "__main__":
    unittest.main()
