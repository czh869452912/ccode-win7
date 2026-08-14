from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from embedagent_protocol import CapabilitySnapshot, ShellDescriptor


def _capabilities():
    return CapabilitySnapshot(
        schema_version=1,
        modes=[],
        commands=[],
        tools=[],
        workflow_packages=[],
        agent_application=None,
        agent_applications=[],
        resources=[],
        model_profiles=[],
        empty_state={},
    )


class FakeSessionPort(object):
    def __init__(self):
        self.closed = False

    def get_session_bootstrap(self, reference, mode=""):
        raise AssertionError("bootstrap must not load during composition")

    def get_session_capabilities(self, session_id=""):
        assert session_id == ""
        return _capabilities()

    def close(self):
        self.closed = True


def test_cli_application_composes_focused_ports_and_shared_runtime(tmp_path, monkeypatch):
    from embedagent.cli.app import CliApplication
    from embedagent.cli.parser import build_parser

    options = build_parser().parse_args(
        ["run", "--workspace", str(tmp_path), "--model", "test-model", "hello"]
    )
    policy = MagicMock()
    policy.bundled = False
    policy.allowed_agent_application_ids = ()
    launch_config = SimpleNamespace(
        workspace=str(tmp_path),
        agent_application_id="tests.python",
    )
    session = FakeSessionPort()
    hosted = SimpleNamespace(session=session, workspace=object())
    created = []
    compiler = MagicMock(return_value=ShellDescriptor(schema_version=1))
    registry = MagicMock()
    registry.record_by_id.return_value = SimpleNamespace(application_id="tests.python")

    monkeypatch.setattr("embedagent.cli.app.load_current_bundle_policy", lambda path: policy)
    monkeypatch.setattr(
        "embedagent.cli.app.resolve_launch_config",
        lambda workspace, overrides: launch_config,
    )
    monkeypatch.setattr(
        "embedagent.cli.app.create_hosted_runtime",
        lambda config, event_sink: created.append((config, event_sink)) or hosted,
    )
    monkeypatch.setattr(
        "embedagent.cli.app.product_agent_application_registry", lambda ids: registry
    )
    monkeypatch.setattr("embedagent.cli.app.product_shell_compiler", lambda: compiler)

    application = CliApplication.from_options(options)

    policy.require_shell.assert_called_once_with("cli")
    assert created == [(launch_config, application.client_runtime)]
    assert application.session_port is session
    assert application.workspace_port is hosted.workspace
    assert application.shell_descriptor == ShellDescriptor(schema_version=1)
    compiler.assert_called_once_with("tests.python", _capabilities().to_dict())
    with pytest.raises(FrozenInstanceError):
        application.options = options

    application.close()
    assert session.closed is True


def test_cli_checks_bundle_policy_before_resolving_config(tmp_path, monkeypatch):
    from embedagent.cli.app import CliApplication
    from embedagent.cli.parser import build_parser

    options = build_parser().parse_args(["sessions", "list", "--workspace", str(tmp_path)])
    policy = MagicMock()
    policy.require_shell.side_effect = ValueError("cli unavailable")
    resolve = MagicMock()
    monkeypatch.setattr("embedagent.cli.app.load_current_bundle_policy", lambda path: policy)
    monkeypatch.setattr("embedagent.cli.app.resolve_launch_config", resolve)

    with pytest.raises(ValueError, match="cli unavailable"):
        CliApplication.from_options(options)

    policy.require_shell.assert_called_once_with("cli")
    resolve.assert_not_called()


def test_cli_sources_do_not_import_other_shells_or_construct_host_internals():
    from pathlib import Path

    source = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("src/embedagent/cli").glob("*.py")
    )
    for forbidden in (
        "embedagent.frontend.tui",
        "embedagent.frontend.gui",
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
        "InProcessAdapter(",
        "session_host",
        "load_config(",
    ):
        assert forbidden not in source
