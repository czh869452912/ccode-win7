from __future__ import annotations


def test_disabled_manifest_is_discovered_but_not_imported(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": false, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "raise RuntimeError('should not import')",
        encoding="utf-8",
    )

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["discovered"] == 1
    assert payload["counts"]["disabled"] == 1
    assert payload["counts"]["loaded"] == 0
    assert payload["extensions"][0]["status"] == "disabled"
    assert payload["loaded_extensions"] == []
    assert payload["diagnostics"] == []


def test_enabled_manifest_requires_permissions(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true}',
        encoding="utf-8",
    )

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["failed"] == 1
    assert payload["extensions"][0]["status"] == "failed"
    assert "permissions" in payload["diagnostics"][0]["error"]


def test_enabled_extension_create_extension_receives_narrow_api(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "data.txt").write_text("hello", encoding="utf-8")
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    class SampleExtension(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "        def resources_discover(self, event, context):",
                "            assert api.read_text('.embedagent/extensions/sample/data.txt') == 'hello'",
                "            return api.ResourcesDiscoverResult(skill_paths=['.embedagent/skills'])",
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent.extensions import ExtensionManager
    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))
    manager = ExtensionManager(payload["loaded_extensions"])
    result = manager.discover_resources(str(tmp_path), reason="test")

    assert payload["counts"]["loaded"] == 1
    assert payload["extensions"][0]["status"] == "loaded"
    assert result.skill_paths == [".embedagent/skills"]


def test_project_extension_api_blocks_path_escape(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    try:",
                "        api.safe_join('..', '..', 'outside.txt')",
                "    except ValueError:",
                "        class SampleExtension(object):",
                "            extension_id = api.extension_id",
                "            builtin_extension = False",
                "        return SampleExtension()",
                "    raise RuntimeError('path escape allowed')",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["loaded"] == 1
    assert payload["diagnostics"] == []


def test_inprocess_adapter_loads_enabled_project_extension_into_shared_manager(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    class SampleExtension(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "        def allowed_tool_names(self, mode_name, workflow_state='chat'):",
                "            return {'project_echo'} if mode_name == 'build' else set()",
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    snapshot = adapter.create_session(mode="build")

    assert adapter.project_extension_state["counts"]["loaded"] == 1
    assert "project_extensions" in snapshot["extensions"]
    assert snapshot["extensions"]["project_extensions"]["state"]["counts"]["loaded"] == 1
    assert "project_echo" in adapter.extension_manager.allowed_tool_names("build")
