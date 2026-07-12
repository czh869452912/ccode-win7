from embedagent_host.hosted.launch_config import LaunchOverrides

from embedagent.hosted import create_hosted_runtime, resolve_launch_config


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
