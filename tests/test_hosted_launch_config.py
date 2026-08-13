import os

import pytest
from embedagent_host.hosted.launch_config import LaunchOverrides, resolve_launch_config

from embedagent.config import AppConfig


def _clear_runtime_env(monkeypatch):
    monkeypatch.delenv("EMBEDAGENT_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDAGENT_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDAGENT_MODEL", raising=False)
    monkeypatch.delenv("EMBEDAGENT_TIMEOUT", raising=False)
    monkeypatch.delenv("EMBEDAGENT_AGENT_APPLICATION_ID", raising=False)
    monkeypatch.delenv("EMBEDAGENT_MAX_CONTEXT_TOKENS", raising=False)
    monkeypatch.delenv("EMBEDAGENT_RESERVE_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("EMBEDAGENT_CHARS_PER_TOKEN", raising=False)
    monkeypatch.delenv("EMBEDAGENT_APPROVE_ALL", raising=False)
    monkeypatch.delenv("EMBEDAGENT_APPROVE_WRITES", raising=False)
    monkeypatch.delenv("EMBEDAGENT_APPROVE_COMMANDS", raising=False)
    monkeypatch.delenv("EMBEDAGENT_PERMISSION_RULES", raising=False)


def test_resolve_launch_config_uses_overrides_before_config(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)

    def config_loader(_workspace):
        return AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        )

    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(
            base_url="http://override/v1",
            api_key="sk-override",
            model="override-model",
            timeout=12,
        ),
        config_loader=config_loader,
    )

    assert result.workspace == os.path.realpath(str(tmp_path))
    assert result.base_url == "http://override/v1"
    assert result.api_key == "sk-override"
    assert result.model == "override-model"
    assert result.timeout == 12


def test_resolve_launch_config_uses_config_when_overrides_are_empty(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)

    def config_loader(_workspace):
        return AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        )

    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(),
        config_loader=config_loader,
    )

    assert result.base_url == "http://configured/v1"
    assert result.api_key == "sk-configured"
    assert result.model == "configured-model"
    assert result.timeout == 45


def test_resolve_launch_config_uses_environment_before_config(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("EMBEDAGENT_BASE_URL", "http://environment/v1")
    monkeypatch.setenv("EMBEDAGENT_API_KEY", "sk-environment")
    monkeypatch.setenv("EMBEDAGENT_MODEL", "environment-model")
    monkeypatch.setenv("EMBEDAGENT_TIMEOUT", "27")
    monkeypatch.setenv("EMBEDAGENT_AGENT_APPLICATION_ID", "environment.application")
    monkeypatch.setenv("EMBEDAGENT_MAX_CONTEXT_TOKENS", "24000")
    monkeypatch.setenv("EMBEDAGENT_RESERVE_OUTPUT_TOKENS", "2400")
    monkeypatch.setenv("EMBEDAGENT_CHARS_PER_TOKEN", "3.25")
    monkeypatch.setenv("EMBEDAGENT_APPROVE_ALL", "true")
    monkeypatch.setenv("EMBEDAGENT_APPROVE_WRITES", "0")
    monkeypatch.setenv("EMBEDAGENT_APPROVE_COMMANDS", "yes")
    monkeypatch.setenv("EMBEDAGENT_PERMISSION_RULES", "environment-rules.json")

    def config_loader(_workspace):
        return AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
            agent_application_id="configured.application",
            max_context_tokens=16000,
            reserve_output_tokens=1600,
            chars_per_token=4.0,
            approve_all=False,
            approve_writes=True,
            approve_commands=False,
            permission_rules="configured-rules.json",
        )

    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(),
        config_loader=config_loader,
    )

    assert result.base_url == "http://environment/v1"
    assert result.api_key == "sk-environment"
    assert result.model == "environment-model"
    assert result.timeout == 27
    assert result.agent_application_id == "environment.application"
    assert result.app_config.max_context_tokens == 24000
    assert result.app_config.reserve_output_tokens == 2400
    assert result.app_config.chars_per_token == 3.25
    assert result.approve_all is True
    assert result.approve_writes is False
    assert result.approve_commands is True
    assert result.permission_rules == "environment-rules.json"


def test_resolve_launch_config_uses_explicit_values_before_environment(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("EMBEDAGENT_MODEL", "environment-model")
    monkeypatch.setenv("EMBEDAGENT_APPROVE_ALL", "true")
    monkeypatch.setenv("EMBEDAGENT_MAX_CONTEXT_TOKENS", "24000")

    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(
            model="override-model",
            approve_all=False,
            max_context_tokens=32000,
        ),
        config_loader=lambda _workspace: AppConfig(model="configured-model"),
    )

    assert result.model == "override-model"
    assert result.approve_all is False
    assert result.app_config.max_context_tokens == 32000


def test_resolve_launch_config_rejects_invalid_environment_boolean(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("EMBEDAGENT_APPROVE_ALL", "sometimes")

    with pytest.raises(ValueError, match="EMBEDAGENT_APPROVE_ALL"):
        resolve_launch_config(
            workspace=str(tmp_path),
            overrides=LaunchOverrides(model="model"),
            config_loader=lambda _workspace: AppConfig(),
        )


def test_resolve_launch_config_ignores_persistent_max_turns(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)

    def config_loader(_workspace):
        return AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
            max_turns=8,
        )

    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(),
        config_loader=config_loader,
    )

    assert result.max_turns is None


def test_resolve_launch_config_accepts_explicit_max_turns_safety_fuse(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)

    def config_loader(_workspace):
        return AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
            max_turns=8,
        )

    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(max_turns=3),
        config_loader=config_loader,
    )

    assert result.max_turns == 3


def test_resolve_launch_config_rejects_missing_model(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)

    def config_loader(_workspace):
        return AppConfig(base_url="http://configured/v1", api_key="sk-configured")

    try:
        resolve_launch_config(
            workspace=str(tmp_path),
            overrides=LaunchOverrides(),
            config_loader=config_loader,
        )
    except ValueError as exc:
        assert "model" in str(exc).lower() or "模型" in str(exc)
    else:
        raise AssertionError("missing model should fail")
