from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from embedagent_host.hosted.launch_config import (
    LaunchConfig,
    LaunchOverrides,
)
from embedagent_host.hosted.runtime import create_hosted_runtime
from embedagent_host.runtime.command_sanitizer import CommandSanitizer
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_protocol import FrontendSessionPort, FrontendWorkspacePort

from embedagent.config import AppConfig
from embedagent.hosted import resolve_launch_config as resolve_product_launch_config


@pytest.fixture(autouse=True)
def isolate_user_config(monkeypatch, tmp_path):
    monkeypatch.setattr("embedagent.config._USER_CONFIG_DIR", str(tmp_path / "user"))


def _config(tmp_path):
    return LaunchConfig(
        workspace=str(tmp_path),
        app_config=AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
        base_url="http://configured/v1",
        api_key="sk-configured",
        model="configured-model",
        timeout=45,
        max_turns=None,
        approve_all=True,
        approve_writes=False,
        approve_commands=False,
        permission_rules="",
        agent_application_id="tests.python",
    )


def test_create_hosted_runtime_builds_frontend_port_set(tmp_path, monkeypatch):
    client_cls = MagicMock(return_value=MagicMock(name="client"))
    tools_cls = MagicMock(return_value=MagicMock(name="tools"))
    context_cls = MagicMock(return_value=MagicMock(name="context_manager"))
    policy_cls = MagicMock(return_value=MagicMock(name="permission_policy"))
    adapter_cls = MagicMock(return_value=MagicMock(name="adapter"))
    monkeypatch.setattr("embedagent_host.hosted.runtime.OpenAICompatibleClient", client_cls)
    monkeypatch.setattr("embedagent_host.hosted.runtime.ToolRuntime", tools_cls)
    monkeypatch.setattr("embedagent_host.hosted.runtime.ContextManager", context_cls)
    monkeypatch.setattr("embedagent_host.hosted.runtime.PermissionPolicy", policy_cls)
    monkeypatch.setattr("embedagent_host.hosted.runtime.InProcessAdapter", adapter_cls)

    sink = MagicMock()
    runtime = create_hosted_runtime(_config(tmp_path), event_sink=sink)

    assert isinstance(runtime.session, FrontendSessionPort)
    assert isinstance(runtime.workspace, FrontendWorkspacePort)
    assert not hasattr(runtime.session, "adapter")
    assert not hasattr(runtime.workspace, "adapter")
    assert not hasattr(runtime, "session_host")
    client_cls.assert_called_once_with(
        base_url="http://configured/v1",
        api_key="sk-configured",
        model="configured-model",
        timeout=45,
    )
    tools_cls.assert_called_once()
    context_cls.assert_called_once()
    policy_cls.assert_called_once()
    adapter_cls.assert_called_once()
    assert adapter_cls.call_args.kwargs["agent_application_id"] == "tests.python"
    assert adapter_cls.call_args.kwargs["event_sink"] is sink


def test_generic_tool_runtime_preserves_permanent_command_denials(tmp_path):
    tools = ToolRuntime(str(tmp_path), app_config=SimpleNamespace())

    for command in ("init 0", "init 6", "su -l", "su - root", "rm -rf build"):
        observation = tools.execute(
            "bash",
            {"command": command},
        )
        assert observation.success is False
        assert "禁止" in str(observation.error or "")


def test_command_sanitizer_does_not_treat_unrelated_names_as_su_invocations():
    sanitizer = CommandSanitizer()

    for command in ("resume -l", "issue -l", "suited -l", "su local-user"):
        blocked, _reason = sanitizer.is_blocked(command)
        assert blocked is False


def test_resolve_launch_config_projects_agent_application_id(tmp_path, monkeypatch):
    config_dir = tmp_path / ".embedagent"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        '{"model": "configured-model", "agent_application_id": "config.python"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("EMBEDAGENT_AGENT_APPLICATION_ID", "env.python")

    launch_config = resolve_product_launch_config(
        str(tmp_path),
        LaunchOverrides(agent_application_id="override.python"),
    )

    assert launch_config.agent_application_id == "override.python"
