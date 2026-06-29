from unittest.mock import MagicMock

from embedagent.config import AppConfig
from embedagent.hosted.launch_config import LaunchConfig
from embedagent.hosted.runtime import create_hosted_runtime
from embedagent.hosted.session_host import HostedSessionHost


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
    )


def test_create_hosted_runtime_builds_session_host(tmp_path, monkeypatch):
    client_cls = MagicMock(return_value=MagicMock(name="client"))
    tools_cls = MagicMock(return_value=MagicMock(name="tools"))
    context_cls = MagicMock(return_value=MagicMock(name="context_manager"))
    policy_cls = MagicMock(return_value=MagicMock(name="permission_policy"))
    adapter_cls = MagicMock(return_value=MagicMock(name="adapter"))
    monkeypatch.setattr("embedagent.hosted.runtime.OpenAICompatibleClient", client_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.ToolRuntime", tools_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.ContextManager", context_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.PermissionPolicy", policy_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.InProcessAdapter", adapter_cls)

    runtime = create_hosted_runtime(_config(tmp_path))

    assert isinstance(runtime.session_host, HostedSessionHost)
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


def test_session_host_delegates_session_operations():
    adapter = MagicMock()
    adapter.list_sessions.return_value = [{"session_id": "s1"}]
    adapter.create_session.return_value = {"session_id": "s2"}
    adapter.resume_session.return_value = {"session_id": "s1"}
    adapter.submit_user_message.return_value = None
    host = HostedSessionHost(adapter=adapter)

    assert host.list_sessions(limit=1) == [{"session_id": "s1"}]
    assert host.create_session(mode="build") == {"session_id": "s2"}
    assert host.resume_session(reference="latest", mode="build") == {"session_id": "s1"}
    host.submit_user_message(session_id="s1", text="hello", stream=False, wait=True)

    adapter.list_sessions.assert_called_once_with(limit=1)
    adapter.create_session.assert_called_once_with("build", event_handler=None)
    adapter.resume_session.assert_called_once_with("latest", "build", event_handler=None)
    adapter.submit_user_message.assert_called_once()
