from types import SimpleNamespace
from unittest.mock import MagicMock

from embedagent_host.hosted.launch_config import (
    LaunchConfig,
    LaunchOverrides,
)
from embedagent_host.hosted.runtime import create_hosted_runtime
from embedagent_host.hosted.session_host import HostedSessionHost
from embedagent_host.runtime.command_sanitizer import CommandSanitizer
from embedagent_protocol import FrontendSessionPort, FrontendWorkspacePort

from embedagent.config import AppConfig
from embedagent.hosted import resolve_launch_config as resolve_product_launch_config


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
    handler = adapter_cls.call_args.kwargs["event_handler"]
    assert handler is sink.on_session_event


def test_generic_hosted_runtime_preserves_permanent_command_denials(tmp_path):
    config = LaunchConfig(
        workspace=str(tmp_path),
        app_config=SimpleNamespace(),
        base_url="http://localhost/v1",
        api_key="",
        model="test-model",
        timeout=1,
        max_turns=None,
        approve_all=True,
        approve_writes=False,
        approve_commands=False,
        permission_rules="",
        agent_application_id="",
    )
    runtime = create_hosted_runtime(config)

    for command in ("init 0", "init 6", "su -l", "su - root", "rm -rf build"):
        observation = runtime.session_host.adapter.tools.execute(
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


def test_session_host_delegates_session_operations():
    adapter = MagicMock()
    adapter.summary_store.load_summary.return_value = {"session_id": "s1"}
    adapter.list_sessions.return_value = [{"session_id": "s1"}]
    adapter.create_session.return_value = {"session_id": "s2"}
    adapter.resume_session.return_value = {"session_id": "s1"}
    adapter.get_session_bootstrap.return_value = {"event_cursor": 3}
    adapter.set_session_mode.return_value = {"session_id": "s1", "current_mode": "verify"}
    adapter.respond_to_interaction.return_value = {"session_id": "s1", "status": "running"}
    adapter.cancel_session.return_value = {"session_id": "s1", "status": "idle"}
    adapter.submit_user_message.return_value = {"session_id": "s1", "status": "running"}
    adapter.list_tasks.return_value = {"session_id": "s1", "tasks": []}
    adapter.get_workspace_snapshot.return_value = {"workspace": "D:/work"}
    adapter.list_workspace_tree.return_value = {"root": ".", "items": []}
    adapter.read_workspace_file.return_value = {"path": "README.md", "content": "text"}
    adapter.write_workspace_file.return_value = {"path": "README.md", "content": "changed"}
    host = HostedSessionHost(adapter=adapter)

    assert host.list_sessions(limit=1) == [{"session_id": "s1"}]
    assert host.load_session_summary("latest") == {"session_id": "s1"}
    assert host.create_session(mode="build") == {"session_id": "s2"}
    assert host.resume_session(reference="latest", mode="build") == {"session_id": "s1"}
    assert host.get_session_bootstrap("s1") == {"event_cursor": 3}
    assert host.set_session_mode("s1", "verify")["current_mode"] == "verify"
    assert host.respond_to_interaction("s1", "i1", {"decision": "accept"}) == {
        "session_id": "s1",
        "status": "running",
    }
    assert host.cancel_session("s1") == {"session_id": "s1", "status": "idle"}
    assert host.submit_user_message(
        session_id="s1",
        text="hello",
        stream=False,
        wait=True,
    ) == {"session_id": "s1", "status": "running"}
    assert host.list_tasks("s1") == {"session_id": "s1", "tasks": []}
    assert host.get_workspace_snapshot() == {"workspace": "D:/work"}
    assert host.list_workspace_tree(path=".", max_depth=2, limit=20) == {
        "root": ".",
        "items": [],
    }
    assert host.read_workspace_file("README.md")["content"] == "text"
    assert host.write_workspace_file("README.md", "changed")["content"] == "changed"

    adapter.list_sessions.assert_called_once_with(limit=1)
    adapter.summary_store.load_summary.assert_called_once_with("latest")
    adapter.create_session.assert_called_once_with("build", event_handler=None)
    adapter.resume_session.assert_called_once_with("latest", "build", event_handler=None)
    adapter.get_session_bootstrap.assert_called_once_with("s1")
    adapter.set_session_mode.assert_called_once_with("s1", "verify")
    adapter.respond_to_interaction.assert_called_once_with(
        "s1",
        "i1",
        {"decision": "accept"},
    )
    adapter.cancel_session.assert_called_once_with("s1")
    adapter.submit_user_message.assert_called_once_with(
        session_id="s1",
        text="hello",
        stream=False,
        wait=True,
        permission_resolver=None,
        user_input_resolver=None,
        event_handler=None,
    )
    adapter.list_tasks.assert_called_once_with(session_id="s1")
    adapter.get_workspace_snapshot.assert_called_once_with()
    adapter.list_workspace_tree.assert_called_once_with(
        path=".",
        max_depth=2,
        limit=20,
    )
    adapter.read_workspace_file.assert_called_once_with("README.md")
    adapter.write_workspace_file.assert_called_once_with("README.md", "changed")
