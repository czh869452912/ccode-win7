import json

from embedagent_host.hosted.launch_config import LaunchOverrides
from embedagent_host.runtime.agent_applications import (
    BUILTIN_AGENT_APPLICATION_RECORDS,
    GENERIC_AGENT_APPLICATION_ID,
)

from embedagent.hosted import create_hosted_runtime, resolve_launch_config
from embedagent.product_catalog import product_shell_registry


def test_product_launch_config_injects_product_config_loader(tmp_path):
    config_dir = tmp_path / ".embedagent"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        '{"model": "product-model", "agent_application_id": "embedagent.python"}',
        encoding="utf-8",
    )

    resolved = resolve_launch_config(str(tmp_path), LaunchOverrides())

    assert resolved.model == "product-model"
    assert resolved.agent_application_id == "embedagent.python"


def test_product_runtime_injects_product_registry(tmp_path, monkeypatch):
    captured = {}

    def fake_create(launch_config, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("embedagent.hosted.create_generic_hosted_runtime", fake_create)
    launch_config = resolve_launch_config(
        str(tmp_path),
        LaunchOverrides(model="product-model"),
    )

    create_hosted_runtime(launch_config)

    registry = captured["agent_application_registry"]
    assert registry.default_application_id == "embedagent.default_c_cpp"
    assert callable(captured["command_sanitizer_factory"])
    assert callable(captured["bundle_root_resolver"])
    assert callable(captured["system_prompt_builder"])


def test_host_application_record_has_no_shell_metadata():
    record = BUILTIN_AGENT_APPLICATION_RECORDS[0]

    assert not hasattr(record, "app_shell")
    assert "appShell" not in json.dumps(record.to_manifest().metadata)


def test_generic_product_shell_has_no_cpp_contribution():
    descriptor = product_shell_registry().compile(
        application_id=GENERIC_AGENT_APPLICATION_ID,
        session_capabilities={"commands": [{"id": "run", "active": True}]},
    )

    ids = {item.id for item in descriptor.commands}
    assert "workflow.run" not in ids


def test_minimal_product_shell_keeps_interactions_out_of_command_palette():
    descriptor = product_shell_registry().compile(
        application_id=GENERIC_AGENT_APPLICATION_ID,
        session_capabilities={"commands": []},
    )

    commands = dict((item.id, item) for item in descriptor.commands)
    assert "interaction.permission.respond" not in commands
    assert "interaction.input.respond" not in commands
    assert commands["session.rename"].availability == {"visible_when": "has_session"}
    assert commands["session.archive"].availability == {"visible_when": "has_session"}
    assert commands["session.fork"].availability == {"visible_when": "has_session"}
    assert commands["session.cancel"].availability == {"visible_when": "running"}
    assert commands["session.mode"].availability == {"visible_when": "has_session"}
    assert commands["workspace.files"].availability == {"visible_when": "has_workspace"}
