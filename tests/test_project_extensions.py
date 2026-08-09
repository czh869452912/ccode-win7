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

    from embedagent_host.runtime.project_extensions import load_project_extensions

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

    from embedagent_host.runtime.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["failed"] == 1
    assert payload["extensions"][0]["status"] == "failed"
    assert "permissions" in payload["diagnostics"][0]["error"]


def test_enabled_manifest_accepts_network_and_telemetry_permissions(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "enterprise"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "enterprise_extension", "enabled": true, "permissions": ["network", "telemetry"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    class EnterpriseExtension(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "    return EnterpriseExtension()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent_host.runtime.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["loaded"] == 1
    assert payload["extensions"][0]["permissions"] == ["network", "telemetry"]
    assert payload["diagnostics"] == []


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
                "        def extension_capabilities(self):",
                "            return [api.ExtensionCapability('resources_discover', self.resources_discover)]",
                "        def resources_discover(self, event, context):",
                "            assert api.read_text('.embedagent/extensions/sample/data.txt') == 'hello'",
                "            return api.ResourcesDiscoverResult(skill_paths=['.embedagent/skills'])",
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent_core.extensions import ExtensionManager
    from embedagent_host.runtime.project_extensions import load_project_extensions

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

    from embedagent_host.runtime.project_extensions import load_project_extensions

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
                "        def extension_capabilities(self):",
                "            return [api.ExtensionCapability('allowed_tool_names', self.allowed_tool_names)]",
                "        def allowed_tool_names(self, mode_name, workflow_state='chat'):",
                "            return {'project_echo'} if mode_name == 'build' else set()",
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent_host.inprocess_adapter import InProcessAdapter
    from embedagent_host.runtime.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    snapshot = adapter.create_session(mode="build")

    assert adapter.project_extension_state["counts"]["loaded"] == 1
    extensions = snapshot["workflow_state"]["extensions"]
    assert "project_extensions" in extensions
    assert extensions["project_extensions"]["state"]["counts"]["loaded"] == 1
    assert "extensions" not in snapshot
    assert "project_echo" in adapter.extension_manager.allowed_tool_names("build")


def test_project_extension_import_failure_appears_in_adapter_diagnostics(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "broken"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "broken_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "raise RuntimeError('boom')",
        encoding="utf-8",
    )

    from embedagent_host.inprocess_adapter import InProcessAdapter
    from embedagent_host.runtime.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    snapshot = adapter.create_session(mode="build")

    assert adapter.project_extension_state["counts"]["failed"] == 1
    assert snapshot["extension_diagnostics"]
    assert snapshot["extension_diagnostics"][0]["extension_id"] == "broken_extension"
    assert "boom" in snapshot["extension_diagnostics"][0]["error"]


def test_project_extension_dynamic_tool_uses_existing_catalog_and_permission_flow(
    tmp_path,
):
    root = tmp_path / ".embedagent" / "extensions" / "tools"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "project_tools", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    def handler(arguments):",
                "        return api.Observation('project_echo', True, None, {'echo': arguments.get('message', '')})",
                "    class ProjectTools(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "        def extension_capabilities(self):",
                "            return [",
                "                api.ExtensionCapability('register_tools', self.register_tools),",
                "                api.ExtensionCapability('allowed_tool_names', self.allowed_tool_names),",
                "            ]",
                "        def register_tools(self, event, context):",
                "            tool = api.ToolDefinition(",
                "                name='project_echo',",
                "                description='Echo from project extension.',",
                "                parameters={'type': 'object', 'properties': {'message': {'type': 'string'}}},",
                "                handler=handler,",
                "                metadata={",
                "                    'permission_category': 'read',",
                "                    'mode_visibility': ['build'],",
                "                    'workflow_visibility': ['chat'],",
                "                    'user_label': 'Project Echo',",
                "                    'progress_renderer_key': 'default',",
                "                    'result_renderer_key': 'default',",
                "                    'supports_diff_preview': False,",
                "                    'context_reducer_key': 'project_echo',",
                "                    'read_only': True,",
                "                    'concurrency_safe': True,",
                "                    'interrupt_behavior': 'block',",
                "                    'result_budget_policy': 'compact-preview',",
                "                    'activity_kind': 'tool',",
                "                    'context_priority': 50,",
                "                },",
                "            )",
                "            return api.ToolRegistrationResult(tools=[tool], source_id=api.extension_id)",
                "        def allowed_tool_names(self, mode_name, workflow_state='chat'):",
                "            return {'project_echo'} if mode_name == 'build' else set()",
                "    return ProjectTools()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent_host.inprocess_adapter import InProcessAdapter
    from embedagent_host.runtime.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    catalog = adapter.get_tool_catalog()
    result = adapter.tools.execute("project_echo", {"message": "hi"})

    entry = adapter.tools.tool_catalog_entry("project_echo")
    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "project_tools"
    assert any(item["name"] == "project_echo" for item in catalog)
    assert result.data["echo"] == "hi"


def test_project_extension_network_tool_is_visible_only_after_allowed_activation(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "tools"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "project_network_tools", "enabled": true, "permissions": ["network"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    def handler(arguments):",
                "        return api.Observation('project_intranet_fetch', True, None, {'url': arguments.get('url', '')})",
                "    class ProjectNetworkTools(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "        active = False",
                "        def extension_capabilities(self):",
                "            return [",
                "                api.ExtensionCapability('register_tools', self.register_tools),",
                "                api.ExtensionCapability('allowed_tool_names', self.allowed_tool_names),",
                "            ]",
                "        def register_tools(self, event, context):",
                "            tool = api.ToolDefinition(",
                "                name='project_intranet_fetch',",
                "                description='Fetch from a trusted intranet service.',",
                "                parameters={'type': 'object', 'properties': {'url': {'type': 'string'}}},",
                "                handler=handler,",
                "                metadata={",
                "                    'permission_category': 'network',",
                "                    'mode_visibility': ['build'],",
                "                    'workflow_visibility': ['chat'],",
                "                    'read_only': False,",
                "                },",
                "                read_only=False,",
                "            )",
                "            return api.ToolRegistrationResult(tools=[tool], source_id=api.extension_id)",
                "        def allowed_tool_names(self, mode_name, workflow_state='chat'):",
                "            return {'project_intranet_fetch'} if self.active and mode_name == 'build' else set()",
                "    return ProjectNetworkTools()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent_core.extensions import (
        ExtensionContext,
        ExtensionManager,
        ToolRegistrationEvent,
    )
    from embedagent_host.runtime.project_extensions import load_project_extensions
    from embedagent_host.runtime.tools import ToolRuntime

    payload = load_project_extensions(str(tmp_path))
    loaded_extension = payload["loaded_extensions"][0]
    runtime = ToolRuntime(str(tmp_path))
    manager = ExtensionManager([loaded_extension])
    manager.register_tools(
        ToolRegistrationEvent(current_mode="build", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )

    inactive_names = manager.allowed_tool_names("build", workflow_state="chat")
    loaded_extension.active = True
    active_names = manager.allowed_tool_names("build", workflow_state="chat")
    entry = runtime.tool_catalog_entry("project_intranet_fetch")

    assert payload["counts"]["loaded"] == 1
    assert entry["permission_category"] == "network"
    assert "project_intranet_fetch" not in inactive_names
    assert "project_intranet_fetch" in active_names


def test_project_extension_loading_does_not_invoke_dependency_installers(tmp_path, monkeypatch):
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
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    calls = []

    def blocked(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("extension loader must not invoke subprocess installers")

    import subprocess

    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)

    from embedagent_host.runtime.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["loaded"] == 1
    assert calls == []
