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
    adapter_cls = MagicMock(return_value=MagicMock(name="adapter"))
    monkeypatch.setattr("embedagent_host.hosted.runtime.InProcessAdapter", adapter_cls)

    sink = MagicMock()
    client = MagicMock(name="client")
    tools = MagicMock(name="tools")
    context = MagicMock(name="context_manager")
    policy = MagicMock(name="permission_policy")
    summary = MagicMock(name="summary_store")
    runtime = create_hosted_runtime(
        _config(tmp_path),
        model_client=client,
        tool_runtime=tools,
        context_manager=context,
        permission_policy=policy,
        summary_store=summary,
        event_sink=sink,
    )

    assert isinstance(runtime.session, FrontendSessionPort)
    assert isinstance(runtime.workspace, FrontendWorkspacePort)
    assert not hasattr(runtime.session, "adapter")
    assert not hasattr(runtime.workspace, "adapter")
    assert not hasattr(runtime, "session_host")
    adapter_cls.assert_called_once()
    assert adapter_cls.call_args.kwargs["client"] is client
    assert adapter_cls.call_args.kwargs["tools"] is tools
    assert adapter_cls.call_args.kwargs["context_manager"] is context
    assert adapter_cls.call_args.kwargs["permission_policy"] is policy
    assert adapter_cls.call_args.kwargs["summary_store"] is summary
    assert adapter_cls.call_args.kwargs["agent_application_id"] == "tests.python"
    assert adapter_cls.call_args.kwargs["event_sink"] is sink


def test_hosted_runtime_close_forwards_to_adapter_shutdown(tmp_path, monkeypatch):
    adapter_cls = MagicMock(return_value=MagicMock(name="adapter"))
    monkeypatch.setattr("embedagent_host.hosted.runtime.InProcessAdapter", adapter_cls)

    runtime = create_hosted_runtime(
        _config(tmp_path),
        model_client=MagicMock(),
        tool_runtime=MagicMock(),
        context_manager=MagicMock(),
        permission_policy=MagicMock(),
        summary_store=MagicMock(),
    )
    runtime.close()

    adapter_cls.return_value.shutdown.assert_called_once_with()


def test_generic_hosted_runtime_requires_explicit_collaborators(tmp_path):
    with pytest.raises(ValueError, match="model_client"):
        create_hosted_runtime(_config(tmp_path))


def test_inprocess_adapter_shutdown_is_idempotent_and_releases_sessions(tmp_path):
    from embedagent_host.inprocess_adapter import InProcessAdapter
    from embedagent_host.runtime.agent_applications import base_agent_application_registry

    adapter = InProcessAdapter(
        client=MagicMock(),
        tools=ToolRuntime(str(tmp_path)),
        agent_application_id="embedagent.generic",
        agent_application_registry=base_agent_application_registry(),
    )
    snapshot = adapter.create_session(mode="build")
    assert snapshot["session_id"] in adapter._sessions

    adapter.shutdown()
    adapter.shutdown()

    assert adapter._sessions == {}
    with pytest.raises(RuntimeError, match="closed"):
        adapter.create_session(mode="build")


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
