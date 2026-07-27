"""Boundary tests for the current pre-release architecture.

The project does not preserve pre-release compatibility. These tests protect
current public construction paths and verify that stale aliases remain absent.
"""

from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages/embedagent-core/src/embedagent_core"


def _relative(path):
    return path.relative_to(ROOT).as_posix()


def _read(path):
    return path.read_text(encoding="utf-8")


def _source_files_under(*relative_roots, **kwargs):
    suffixes = kwargs.get("suffixes", (".py",))
    files = []
    for relative_root in relative_roots:
        root = ROOT / relative_root
        candidates = [root] if root.is_file() else list(root.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            if path.suffix in suffixes:
                files.append(path)
    return files


def test_c_cpp_workflow_package_replaces_embedagent_harness_package():
    old_package = ROOT / "src" / "embedagent" / "harness"
    new_package = ROOT / "packages" / "embedagent-workflow-cpp" / "src" / "embedagent_workflow_cpp"
    assert not old_package.exists()
    assert (new_package / "extension.py").is_file()

    forbidden_tokens = (
        "embedagent." + "harness",
        "src/embedagent/" + "harness",
    )
    offenders = []
    for relative_root in ("src/embedagent", "tests"):
        for path in (ROOT / relative_root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            for token in forbidden_tokens:
                if token in text:
                    offenders.append("%s contains %s" % (rel, token))
    assert offenders == []


class TestPublicImports(object):
    """Verify public imports and removed-alias boundaries."""

    def test_import_inprocess_adapter(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter

        assert InProcessAdapter is not None

    def test_query_engine_is_not_a_public_core_symbol(self):
        import embedagent_core

        assert not hasattr(embedagent_core, "QueryEngine")

    def test_import_modes(self):
        from embedagent.modes import (
            DEFAULT_MODE,
            allowed_tools_for,
            initialize_modes,
            mode_names,
            require_mode,
        )

        assert DEFAULT_MODE == "explore"
        assert callable(mode_names)
        assert callable(require_mode)
        assert callable(initialize_modes)
        assert callable(allowed_tools_for)

    def test_import_services(self):
        from embedagent_host.runtime.services import (
            EventEmitter,
            SessionLifecycleManager,
            WorkspaceFileService,
        )

        assert EventEmitter is not None
        assert SessionLifecycleManager is not None
        assert WorkspaceFileService is not None

    def test_import_strategies(self):
        from embedagent_host.runtime.strategies import ToolResultCache

        assert ToolResultCache is not None

    def test_legacy_context_compaction_strategy_removed(self):
        import embedagent_host.runtime.strategies as strategies

        assert not hasattr(strategies, "ContextCompactionEngine")

    def test_turn_orchestrator_legacy_strategy_removed(self):
        import embedagent_host.runtime.strategies as strategies

        assert not hasattr(strategies, "TurnOrchestrator")

    def test_import_di_container(self):
        from embedagent.di_container import DIContainer, get_default_container

        assert DIContainer is not None
        assert callable(get_default_container)

    def test_mode_registry_alias_removed(self):
        import embedagent.modes as modes

        assert not hasattr(modes, "MODE" + "_REGISTRY")
        assert "explore" in modes.get_mode_registry()

    def test_core_adapter_legacy_accessor_removed(self):
        import embedagent.core.adapter as adapter

        assert not hasattr(adapter, "_inprocess" + "_adapter")
        assert not hasattr(adapter, "_get_adapter" + "_class")
        assert adapter.get_inprocess_adapter() is not None

    def test_core_adapter_snapshot_does_not_inject_default_mode(self):
        from embedagent.core.adapter import _session_snapshot_from_dict

        snapshot = _session_snapshot_from_dict({})

        assert snapshot.current_mode == ""


class TestInProcessAdapterBoundaries(object):
    """Verify InProcessAdapter construction and removed-alias boundaries."""

    def _make_adapter(self, tmp_path):
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.providers.openai_compatible import OpenAICompatibleClient
        from embedagent_host.runtime.tools import ToolRuntime

        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        tools.workspace = str(workspace)
        tools.tool_result_store = MagicMock()
        return InProcessAdapter(client=client, tools=tools)

    def test_can_instantiate_with_no_args(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter

        adapter = InProcessAdapter()
        assert adapter is not None

    def test_has_create_session_method(self, fresh_container, tmp_path):
        adapter = self._make_adapter(tmp_path)
        assert hasattr(adapter, "create_session")
        assert callable(adapter.create_session)

    def test_has_list_sessions_method(self, fresh_container, tmp_path):
        adapter = self._make_adapter(tmp_path)
        assert hasattr(adapter, "list_sessions")
        assert callable(adapter.list_sessions)

    def test_has_event_emitter(self, fresh_container, tmp_path):
        adapter = self._make_adapter(tmp_path)
        assert hasattr(adapter, "_event_emitter")
        from embedagent_host.runtime.services import EventEmitter

        assert isinstance(adapter._event_emitter, EventEmitter)

    def test_turn_runner_has_single_internal_entrypoint(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter

        assert hasattr(InProcessAdapter, "_run_turn")
        assert not hasattr(InProcessAdapter, "_run_turn_v2")

    def test_resource_command_specs_live_outside_adapter(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter

        assert not hasattr(InProcessAdapter, "_resource_command_specs")
        assert not hasattr(InProcessAdapter, "_skill_command_specs")

    def test_review_evidence_shaping_lives_outside_adapter(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter

        assert not hasattr(InProcessAdapter, "_review_events_from_session")


class TestModesBoundaries(object):
    """Verify current modes module boundaries."""

    def test_mode_names_returns_list(self):
        from embedagent.modes import mode_names

        names = mode_names()
        assert isinstance(names, list)
        assert "explore" in names
        assert "build" in names

    def test_require_mode_returns_dict(self):
        from embedagent.modes import require_mode

        mode = require_mode("explore")
        assert isinstance(mode, dict)
        assert "system_prompt" in mode

    def test_initialize_modes_returns_registry(self):
        from embedagent.modes import initialize_modes

        registry = initialize_modes()
        assert isinstance(registry, dict)
        assert "explore" in registry

    def test_allowed_tools_for_returns_list(self):
        from embedagent.modes import allowed_tools_for

        tools = allowed_tools_for("explore")
        assert isinstance(tools, list)
        assert "read_file" in tools


class TestGlobalStateIsolation(object):
    """Verify tests can get isolated state without affecting global registry."""

    def test_fresh_mode_registry_isolated(self):
        from embedagent.modes import get_mode_registry

        # Get fresh registry and mutate it
        fresh = get_mode_registry(fresh=True)
        fresh["custom_mode"] = {"slug": "custom"}

        # Global registry should be unchanged
        global_names = set(get_mode_registry().keys())
        assert "custom_mode" not in global_names


def test_no_compatibility_reexports_for_core_extraction():
    deleted_paths = [
        ROOT / "src/embedagent/session.py",
        ROOT / "src/embedagent/interaction.py",
        ROOT / "src/embedagent/guard.py",
        ROOT / "src/embedagent/tool_execution.py",
        ROOT / "src/embedagent/compacted_history.py",
        ROOT / "src/embedagent/llm.py",
    ]
    existing = [_relative(path) for path in deleted_paths if path.exists()]
    assert existing == []

    forbidden_reexport_text = (
        "from embedagent_core.session import",
        "from embedagent_core.interaction import",
        "from embedagent_core.guard import",
        "from embedagent_core.tool_execution import",
        "from embedagent_core.compacted_history import",
        "from embedagent_core.model import",
    )
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        text = _read(path)
        rel = _relative(path)
        if rel.startswith("packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/"):
            continue
        for token in forbidden_reexport_text:
            if token in text and path.name in (
                "session.py",
                "interaction.py",
                "guard.py",
                "tool_execution.py",
                "compacted_history.py",
                "llm.py",
            ):
                offenders.append("%s reexports %s" % (rel, token))
    assert offenders == []

    def test_fresh_di_container_isolated(self, fresh_container):
        from embedagent.di_container import DIContainer

        assert isinstance(fresh_container, DIContainer)
        fresh_container.register_factory("test_key", lambda: "test_value")
        result = fresh_container.resolve("test_key")
        assert result == "test_value"

    def test_get_command_sanitizer_fresh(self):
        from embedagent.command_sanitizer import get_command_sanitizer

        s1 = get_command_sanitizer(fresh=True)
        s2 = get_command_sanitizer(fresh=True)
        assert s1 is not s2

    def test_command_sanitizer_legacy_aliases_removed(self):
        import embedagent.command_sanitizer as command_sanitizer

        assert not hasattr(command_sanitizer, "_DEFAULT" + "_SANITIZER")
        assert not hasattr(command_sanitizer, "get_default" + "_sanitizer")
        assert command_sanitizer.get_command_sanitizer() is not None

    def test_get_inprocess_adapter_returns_class(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter

        from embedagent.core.adapter import get_inprocess_adapter

        result = get_inprocess_adapter()
        assert result is InProcessAdapter


def test_product_command_sanitizer_uses_host_runtime_implementation():
    from embedagent.command_sanitizer import get_command_sanitizer

    sanitizer = get_command_sanitizer(fresh=True)
    assert type(sanitizer).__module__ == "embedagent_host.runtime.command_sanitizer"


def test_transcript_store_has_no_schema_v1_compatibility_path():
    checked_files = (
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/transcript_store.py",
        CORE_SOURCE / "agent_lifecycle.py",
        CORE_SOURCE / "query_engine.py",
        CORE_SOURCE / "ports.py",
        ROOT / "tests/test_transcript_store.py",
        ROOT / "tests/test_session_integration.py",
        ROOT / "tests/test_diff_engine.py",
        ROOT / "tests/test_agent_lifecycle.py",
        ROOT / "tests/test_session_restore.py",
        ROOT / "tests/test_session_fault_injection.py",
    )
    forbidden_tokens = (
        "schema_v1",
        "schema v1",
        "schema_version=1",
        "schema_version: int = 1",
        '"schema_version": 1',
        '"schema_version":1',
        "schema_version == 1",
        "backward_compatibility",
    )
    offenders = []
    for path in checked_files:
        text = _read(path)
        rel = _relative(path)
        for token in forbidden_tokens:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert offenders == []


def test_tool_runtime_does_not_import_mode_registry_for_schema_projection():
    runtime_source = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py"
    )
    assert "from embedagent.modes import allowed_tools_for" not in runtime_source
    assert "allowed_tools_for(mode_name)" not in runtime_source


def test_generic_layers_do_not_default_workflow_state_to_chat():
    paths = [
        ROOT / "packages/embedagent-protocol/src/embedagent_protocol/__init__.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/context.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py",
        ROOT / "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py",
    ]
    forbidden = (
        'workflow_state: str = "chat"',
        'workflow_state or "chat"',
        'workflow_state="chat"',
        'state.workflow_state = "chat"',
        'else "chat"',
    )
    for path in paths:
        source = _read(path)
        assert not [token for token in forbidden if token in source], str(path)


def test_c_workflow_tools_are_declared_only_by_c_workflow_package_or_tests():
    c_tools = (
        "list_recipes",
        "run_recipe",
        "report_quality_v2",
        "record_failing_evidence",
        "task_status",
    )
    allowed_prefixes = ("packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/",)
    assert not (
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/tools/recipe_ops.py"
    ).exists()
    offenders = []
    for path in _source_files_under("src", suffixes=(".py", ".js", ".jsx")):
        rel = _relative(path)
        if rel.startswith(allowed_prefixes):
            continue
        text = _read(path)
        for tool_name in c_tools:
            if '"%s"' % tool_name in text or "'%s'" % tool_name in text:
                offenders.append("%s hard-codes %s" % (rel, tool_name))
    assert offenders == []


def test_c_cpp_agent_profile_lives_in_c_workflow_package():
    core_profile = ROOT / "packages/embedagent-core/src/embedagent_core/profile.py"
    base_profile = ROOT / "packages/embedagent-host/src/embedagent_host/runtime/profiles.py"
    c_profile = ROOT / "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/profile.py"
    component = ROOT / "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/component.py"
    loader = ROOT / "packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py"

    assert core_profile.is_file()
    assert base_profile.is_file()
    assert c_profile.is_file()

    core_text = _read(core_profile)
    base_text = _read(base_profile)
    c_text = _read(c_profile)
    assert "class AgentModeDescriptor" in core_text
    assert "class AgentProfile" in core_text
    assert "class AgentModeDescriptor" not in base_text
    assert "class AgentProfile" not in base_text
    assert "from embedagent_core.profile import AgentModeDescriptor, AgentProfile" in base_text
    assert "from embedagent_core.profile import AgentModeDescriptor, AgentProfile" in c_text
    assert "from embedagent_core.profile_runtime import (" in base_text
    assert "from embedagent_core.profile_runtime import (" in c_text
    for duplicate in (
        "BASE_READ_TOOLS =",
        "BASE_DISCUSSION_TOOLS =",
        "BASE_WRITE_TOOLS =",
        "BASE_VERIFY_TOOLS =",
        "SPEC_WRITABLE_GLOBS =",
    ):
        assert duplicate not in base_text
        assert duplicate not in c_text

    forbidden_base_tokens = (
        "default_c_cpp_agent_profile",
        "DEVELOPMENT_WRITABLE_GLOBS",
        "CMakeLists.txt",
        "**/*.cpp",
        "**/*.hpp",
    )
    offenders = []
    for token in forbidden_base_tokens:
        if token in base_text:
            offenders.append(
                "packages/embedagent-host/src/embedagent_host/runtime/profiles.py contains %s"
                % token
            )
    assert offenders == []

    forbidden_core_tokens = (
        "generic_agent_profile",
        "python_agent_profile",
        "html_agent_profile",
        "default_c_cpp_agent_profile",
        "embedagent.generic",
        "embedagent.python",
        "embedagent.html",
        "通用工程",
        "Python 工程",
        "HTML/Web",
        "CMakeLists.txt",
        "**/*.cpp",
        "**/*.hpp",
    )
    for token in forbidden_core_tokens:
        assert token not in core_text
    assert "embedagent_host" not in core_text
    assert "embedagent.workflow_packages" not in core_text

    assert "default_c_cpp_agent_profile" not in _read(loader)
    assert "from embedagent_workflow_cpp.profile import default_cpp_profile" in _read(component)


def test_default_c_cpp_application_record_lives_in_c_workflow_package():
    registry = ROOT / "packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py"
    record = ROOT / "src/embedagent/product_catalog.py"
    product_registry = ROOT / "src/embedagent/product_catalog.py"

    assert record.is_file()
    assert product_registry.is_file()
    registry_text = _read(registry)
    record_text = _read(record)
    product_registry_text = _read(product_registry)

    for token in (
        "_C_CPP_APP_SHELL",
        '"Default C/C++ Agent"',
        '"Path to C/C++ project"',
        '"embedagent.c_workflow"',
        'profile_kind="default_c_cpp"',
        "embedagent_workflow_cpp",
        "default_c_cpp_application_record",
    ):
        assert token not in registry_text
    assert "AgentApplicationRegistry" in registry_text
    assert "default_c_cpp_application_record" in product_registry_text
    assert "DEFAULT_C_CPP_AGENT_APPLICATION_ID" in product_registry_text
    assert "C_WORKFLOW_PACKAGE_ID" in record_text
    assert '"Default C/C++ Agent"' in record_text
    assert "runtime_factory=cpp_runtime_definition" in record_text


def test_hosted_adapter_uses_shared_agent_profile_runtime_policies():
    adapter = ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py"
    profiles = ROOT / "packages/embedagent-host/src/embedagent_host/runtime/profiles.py"
    runtime = ROOT / "packages/embedagent-core/src/embedagent_core/profile_runtime.py"

    assert profiles.is_file()
    assert runtime.is_file()
    adapter_text = _read(adapter)
    profiles_text = _read(profiles)
    runtime_text = _read(runtime)

    assert "AgentProfileRuntimePolicy" in adapter_text
    assert "AgentProfileToolPolicy" in adapter_text
    assert "AgentProfileWritePathPolicy" in adapter_text
    for token in (
        "class _ProductModeToolPolicy",
        "class _ProductWritePathPolicy",
        "class _ProductModeRuntimePolicy",
        "_profile_writable_globs",
        "你是 EmbedAgent 的受控模式原型。",
    ):
        assert token not in adapter_text
    assert "PROFILE_PROMPT_FRAME" not in profiles_text
    assert "PROFILE_PROMPT_FRAME =" in runtime_text
    assert "from embedagent_host" not in runtime_text


def test_base_config_does_not_pin_default_c_cpp_application():
    config_files = (
        ROOT / "src/embedagent/config.py",
        ROOT / "config/config.json.template",
    )
    forbidden_config_tokens = (
        '"agent_application_id": "embedagent.default_c_cpp"',
        "CMakeLists.txt",
    )
    offenders = []
    for path in config_files:
        text = _read(path)
        rel = _relative(path)
        for token in forbidden_config_tokens:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert offenders == []

    guide = _read(ROOT / "docs/guides/configuration-guide.md")
    assert "| `agent_application_id` | string | `embedagent.default_c_cpp` |" not in guide


def test_generic_workspace_profile_uses_workflow_owned_c_cpp_detectors():
    generic = ROOT / "packages/embedagent-host/src/embedagent_host/runtime/workspace_profile.py"
    c_detector = (
        ROOT / "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_profile.py"
    )

    generic_text = _read(generic)
    for token in (
        "CMakeLists.txt",
        "Makefile",
        '".cpp"',
        '".hpp"',
    ):
        assert token not in generic_text

    detector_text = _read(c_detector)
    assert "CMakeLists.txt" in detector_text
    assert '".cpp"' in detector_text
    assert "CCppWorkspaceProfileDetector" in detector_text


def test_product_evidence_helpers_do_not_import_c_cpp_workflow_constants():
    files = (
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/review_command.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/project_memory.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/workspace_intelligence.py",
    )
    forbidden = (
        "embedagent_workflow_cpp",
        "C_WORKFLOW_TOOL_",
        "C_WORKFLOW_DIAGNOSTIC_TOOL_NAMES",
    )
    offenders = []
    for path in files:
        text = _read(path)
        rel = _relative(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s imports %s" % (rel, token))
    assert offenders == []


def test_generic_workspace_recipe_facade_does_not_import_c_cpp_workflow_constants():
    files = (
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/workspace_recipes.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/workspace_profile.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/tools/_base.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py",
    )
    forbidden = (
        "embedagent_workflow_cpp",
        "C_WORKFLOW_TOOL_",
        "run_recipe",
        "list_recipes",
    )
    offenders = []
    for path in files:
        text = _read(path)
        rel = _relative(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert offenders == []


def test_tools_module_docs_keep_workspace_recipes_workflow_neutral():
    text = _read(ROOT / "docs/modules/tools-and-tooling.md")

    assert (
        "聚合与 `run_recipe` 归一化位于 `packages/embedagent-host/src/embedagent_host/runtime/workspace_recipes.py`"
        not in text
    )
    assert "`packages/embedagent-host/src/embedagent_host/runtime/workspace_recipes.py`" in text
    assert "workflow-neutral file-resource/read-model facade" in text
    assert "不做 CMake/Make/Ninja 检测" in text
    assert (
        "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_recipes.py" in text
    )


def test_runtime_service_bag_is_deleted():
    core_root = ROOT / "packages/embedagent-core/src/embedagent_core"
    source = "\n".join(path.read_text(encoding="utf-8") for path in core_root.rglob("*.py"))
    assert "AgentRuntimeServices" not in source


def test_query_engine_has_no_hosted_service_constructor_parameters():
    source = (ROOT / "packages/embedagent-core/src/embedagent_core/query_engine.py").read_text(
        encoding="utf-8"
    )
    constructor = source.split("def __init__", 1)[1].split(") -> None", 1)[0]
    for name in (
        "summary_store",
        "project_memory_store",
        "memory_maintenance",
        "intelligence_broker",
        "tool_commit",
        "workspace_profile",
    ):
        assert name not in constructor


def test_retired_product_tooling_modules_do_not_exist():
    retired = (
        "src/embedagent/tooling/contracts.py",
        "src/embedagent/tooling/result_budget.py",
        "src/embedagent/tooling/__init__.py",
        "src/embedagent/workflow_packages/__init__.py",
    )
    for relative_path in retired:
        assert not (ROOT / relative_path).is_file()


def test_core_profile_prompt_is_product_neutral():
    source = (ROOT / "packages/embedagent-core/src/embedagent_core/profile_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "EmbedAgent" not in source
    assert "优先用中文" not in source
