from unittest.mock import MagicMock

from embedagent import cli
from embedagent.config import AppConfig


def test_cli_uses_hosted_config_model_for_non_tui_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
    )
    runtime = MagicMock()
    runtime.session_host.create_session.return_value = {"session_id": "s1"}
    launch_configs = []

    def fake_create_hosted_runtime(launch_config, event_handler=None):
        launch_configs.append(launch_config)
        return runtime

    monkeypatch.setattr(
        "embedagent.cli.create_hosted_runtime",
        fake_create_hosted_runtime,
    )

    exit_code = cli.main(["--workspace", str(tmp_path), "--no-stream", "hello"])

    assert exit_code == 0
    assert launch_configs[0].base_url == "http://configured/v1"
    assert launch_configs[0].api_key == "sk-configured"
    assert launch_configs[0].model == "configured-model"
    assert launch_configs[0].timeout == 45
    runtime.session_host.create_session.assert_called_once()
    runtime.session_host.submit_user_message.assert_called_once()


def test_cli_architecture_guard_blocks_direct_runtime_construction():
    with open("src/embedagent/cli.py", "r", encoding="utf-8") as fh:
        text = fh.read()
    blocked = [
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
        "InProcessAdapter(",
    ]
    for needle in blocked:
        assert needle not in text
