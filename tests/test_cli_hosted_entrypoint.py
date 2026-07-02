import json
from unittest.mock import MagicMock

from embedagent import cli
from embedagent.config import AppConfig


def _use_user_config(tmp_path, monkeypatch):
    user_config_dir = tmp_path / "user-config"
    user_config_dir.mkdir()
    config_path = user_config_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "http://user-config/v1",
                "api_key": "sk-user-config",
                "model": "user-config-model",
                "timeout": 33,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("embedagent.config._USER_CONFIG_DIR", str(user_config_dir))
    monkeypatch.delenv("EMBEDAGENT_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDAGENT_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDAGENT_MODEL", raising=False)
    monkeypatch.delenv("EMBEDAGENT_TIMEOUT", raising=False)
    return str(user_config_dir)


def test_cli_uses_hosted_config_model_for_non_tui_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent_host.hosted.launch_config.load_config",
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


def test_cli_returns_blocked_outcome_exit_code_and_diagnostic(tmp_path, monkeypatch, capsys):
    _use_user_config(tmp_path, monkeypatch)
    runtime = MagicMock()
    runtime.session_host.create_session.return_value = {"session_id": "s1"}
    launch_configs = []

    def submit_user_message(**kwargs):
        handler = kwargs["event_handler"]
        handler(
            "session_finished",
            "s1",
            {
                "final_text": "I stopped before finishing.",
                "turn_experience": {
                    "status": "blocked",
                    "completed": [{"kind": "file_created", "path": "README.md"}],
                    "unverified": [
                        {
                            "kind": "validation_missing",
                            "message": "Created files have not been validated.",
                        }
                    ],
                    "next_steps": ["Run validation for the changed files."],
                    "blocker": {"reason": "guard_stop", "message": "repeated no-progress action"},
                },
                "outcome": {
                    "kind": "blocked",
                    "reason": "guard_stop",
                    "message": "repeated no-progress action",
                    "exit_code": 2,
                    "is_success": False,
                },
            },
        )

    runtime.session_host.submit_user_message.side_effect = submit_user_message
    monkeypatch.setattr(
        "embedagent.cli.create_hosted_runtime",
        lambda launch_config, event_handler=None: launch_configs.append(launch_config) or runtime,
    )

    exit_code = cli.main(["--workspace", str(tmp_path), "--no-stream", "hello"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "I stopped before finishing." in captured.out
    assert "[blocked] guard_stop: repeated no-progress action" in captured.err
    assert "Done:" in captured.err
    assert "file_created README.md" in captured.err
    assert "Unverified:" in captured.err
    assert "validation_missing Created files have not been validated." in captured.err
    assert "Next:" in captured.err
    assert "Run validation for the changed files." in captured.err
    assert launch_configs[0].model == "user-config-model"
    assert launch_configs[0].base_url == "http://user-config/v1"


def test_cli_completed_outcome_returns_success(tmp_path, monkeypatch, capsys):
    _use_user_config(tmp_path, monkeypatch)
    runtime = MagicMock()
    runtime.session_host.create_session.return_value = {"session_id": "s1"}
    launch_configs = []

    def submit_user_message(**kwargs):
        kwargs["event_handler"](
            "session_finished",
            "s1",
            {
                "final_text": "Done.",
                "outcome": {
                    "kind": "completed",
                    "reason": "completed",
                    "message": "",
                    "exit_code": 0,
                    "is_success": True,
                },
            },
        )

    runtime.session_host.submit_user_message.side_effect = submit_user_message
    monkeypatch.setattr(
        "embedagent.cli.create_hosted_runtime",
        lambda launch_config, event_handler=None: launch_configs.append(launch_config) or runtime,
    )

    exit_code = cli.main(["--workspace", str(tmp_path), "--no-stream", "hello"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "Done.\n"
    assert "[completed]" not in captured.err
    assert launch_configs[0].model == "user-config-model"
