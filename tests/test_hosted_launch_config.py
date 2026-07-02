import os

from embedagent.config import AppConfig
from embedagent_host.hosted.launch_config import LaunchOverrides, resolve_launch_config


def _clear_runtime_env(monkeypatch):
    monkeypatch.delenv("EMBEDAGENT_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDAGENT_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDAGENT_MODEL", raising=False)
    monkeypatch.delenv("EMBEDAGENT_TIMEOUT", raising=False)


def test_resolve_launch_config_uses_overrides_before_config(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(
        "embedagent_host.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
    )

    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(
            base_url="http://override/v1",
            api_key="sk-override",
            model="override-model",
            timeout=12,
        ),
    )

    assert result.workspace == os.path.realpath(str(tmp_path))
    assert result.base_url == "http://override/v1"
    assert result.api_key == "sk-override"
    assert result.model == "override-model"
    assert result.timeout == 12


def test_resolve_launch_config_uses_config_when_overrides_are_empty(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(
        "embedagent_host.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
    )

    result = resolve_launch_config(workspace=str(tmp_path), overrides=LaunchOverrides())

    assert result.base_url == "http://configured/v1"
    assert result.api_key == "sk-configured"
    assert result.model == "configured-model"
    assert result.timeout == 45


def test_resolve_launch_config_ignores_persistent_max_turns(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(
        "embedagent_host.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
            max_turns=8,
        ),
    )

    result = resolve_launch_config(workspace=str(tmp_path), overrides=LaunchOverrides())

    assert result.max_turns is None


def test_resolve_launch_config_accepts_explicit_max_turns_safety_fuse(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(
        "embedagent_host.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
            max_turns=8,
        ),
    )

    result = resolve_launch_config(workspace=str(tmp_path), overrides=LaunchOverrides(max_turns=3))

    assert result.max_turns == 3


def test_resolve_launch_config_rejects_missing_model(tmp_path, monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setattr(
        "embedagent_host.hosted.launch_config.load_config",
        lambda workspace: AppConfig(base_url="http://configured/v1", api_key="sk-configured"),
    )

    try:
        resolve_launch_config(workspace=str(tmp_path), overrides=LaunchOverrides())
    except ValueError as exc:
        assert "model" in str(exc).lower() or "模型" in str(exc)
    else:
        raise AssertionError("missing model should fail")
