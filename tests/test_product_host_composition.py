import json

import pytest
from embedagent_host.hosted.launch_config import LaunchOverrides
from embedagent_host.runtime.agent_applications import (
    BUILTIN_AGENT_APPLICATION_RECORDS,
    GENERIC_AGENT_APPLICATION_ID,
)

from embedagent.bundle_policy import BundleRuntimePolicy
from embedagent.hosted import create_hosted_runtime, resolve_launch_config
from embedagent.product_catalog import (
    product_agent_application_registry,
    product_shell_registry,
)


@pytest.fixture(autouse=True)
def isolate_user_config(monkeypatch, tmp_path):
    monkeypatch.setattr("embedagent.config._USER_CONFIG_DIR", str(tmp_path / "user"))


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
    assert registry.default_application_id == "embedagent.generic"
    assert captured["model_client"].model == "product-model"
    assert captured["tool_runtime"].workspace == str(tmp_path)
    assert captured["context_manager"] is not None
    assert captured["permission_policy"] is not None
    assert captured["summary_store"] is not None


def test_product_registry_filters_allowed_applications_in_stable_order():
    registry = product_agent_application_registry(
        allowed_application_ids=("embedagent.python", "embedagent.generic")
    )

    assert [record.application_id for record in registry.application_records] == [
        "embedagent.generic",
        "embedagent.python",
    ]
    assert registry.default_application_id == "embedagent.python"

    with pytest.raises(ValueError, match="Unknown allowed agent application"):
        product_agent_application_registry(allowed_application_ids=("tests.unknown",))


def test_product_host_rejects_unplanned_application_before_runtime(tmp_path, monkeypatch):
    config_dir = tmp_path / ".embedagent"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        '{"model": "product-model", "agent_application_id": "embedagent.python"}',
        encoding="utf-8",
    )
    policy = BundleRuntimePolicy(
        bundled=True,
        flavor_id="minimal-cli",
        bundle_plan_sha256="e" * 64,
        allowed_agent_application_ids=("embedagent.generic",),
        shell_ids=("cli",),
    )
    monkeypatch.setattr("embedagent.hosted._current_bundle_policy", lambda: policy)

    with pytest.raises(ValueError, match="not included in bundle flavor minimal-cli"):
        resolve_launch_config(str(tmp_path), LaunchOverrides())


def test_product_runtime_injects_plan_filtered_registry(tmp_path, monkeypatch):
    captured = {}
    policy = BundleRuntimePolicy(
        bundled=True,
        flavor_id="minimal-cli",
        bundle_plan_sha256="e" * 64,
        allowed_agent_application_ids=("embedagent.generic",),
        shell_ids=("cli",),
    )

    def fake_create(launch_config, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("embedagent.hosted._current_bundle_policy", lambda: policy)
    monkeypatch.setattr("embedagent.hosted.create_generic_hosted_runtime", fake_create)
    launch_config = resolve_launch_config(
        str(tmp_path),
        LaunchOverrides(model="product-model"),
    )

    create_hosted_runtime(launch_config)

    assert launch_config.agent_application_id == "embedagent.generic"
    registry = captured["agent_application_registry"]
    assert [record.application_id for record in registry.application_records] == [
        "embedagent.generic"
    ]
    assert registry.default_application_id == "embedagent.generic"
    assert captured["model_client"].model == "product-model"


def test_cpp_runtime_registry_is_loaded_from_selected_plugin_entries(tmp_path, monkeypatch):
    captured = {}
    policy = BundleRuntimePolicy(
        bundled=True,
        flavor_id="cpp-desktop",
        bundle_plan_sha256="e" * 64,
        allowed_agent_application_ids=("embedagent.default_c_cpp",),
        shell_ids=("cli", "tui", "gui"),
        registration_entries=(
            "embedagent.product_catalog:register",
            "embedagent_workflow_cpp.application:register_application",
        ),
    )

    def fake_create(launch_config, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("embedagent.hosted._current_bundle_policy", lambda: policy)
    monkeypatch.setattr("embedagent.hosted.create_generic_hosted_runtime", fake_create)
    launch_config = resolve_launch_config(
        str(tmp_path),
        LaunchOverrides(model="product-model", agent_application_id="embedagent.default_c_cpp"),
    )

    create_hosted_runtime(launch_config)

    registry = captured["agent_application_registry"]
    assert [record.application_id for record in registry.application_records] == [
        "embedagent.generic",
        "embedagent.default_c_cpp",
    ]


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
    assert "session.mode" not in commands
    assert commands["workspace.files"].availability == {"visible_when": "has_workspace"}
