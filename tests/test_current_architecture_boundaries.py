"""Boundary tests for the current pre-release architecture.

The project does not preserve pre-release compatibility. These tests protect
current public construction paths and verify that stale aliases remain absent.
"""

from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]


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
    new_package = ROOT / "src" / "embedagent" / "workflow_packages" / "c_cpp"
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

    def test_import_query_engine(self):
        from embedagent_core.query_engine import QueryEngine

        assert QueryEngine is not None

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
        from embedagent.services import (
            EventEmitter,
            SessionLifecycleManager,
            WorkspaceFileService,
        )

        assert EventEmitter is not None
        assert SessionLifecycleManager is not None
        assert WorkspaceFileService is not None

    def test_import_strategies(self):
        from embedagent.strategies import ToolResultCache

        assert ToolResultCache is not None

    def test_legacy_context_compaction_strategy_removed(self):
        import embedagent.strategies as strategies

        assert not hasattr(strategies, "ContextCompactionEngine")

    def test_turn_orchestrator_legacy_strategy_removed(self):
        import embedagent.strategies as strategies

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

    def _make_adapter(self):
        from embedagent.tools import ToolRuntime
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.providers.openai_compatible import OpenAICompatibleClient

        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test_workspace"
        tools.tool_result_store = MagicMock()
        return InProcessAdapter(client=client, tools=tools)

    def test_can_instantiate_with_no_args(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter

        adapter = InProcessAdapter()
        assert adapter is not None

    def test_has_create_session_method(self, fresh_container):
        adapter = self._make_adapter()
        assert hasattr(adapter, "create_session")
        assert callable(adapter.create_session)

    def test_has_list_sessions_method(self, fresh_container):
        adapter = self._make_adapter()
        assert hasattr(adapter, "list_sessions")
        assert callable(adapter.list_sessions)

    def test_has_event_emitter(self, fresh_container):
        adapter = self._make_adapter()
        assert hasattr(adapter, "_event_emitter")
        from embedagent.services import EventEmitter

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


class TestQueryEngineBoundaries(object):
    """Verify QueryEngine construction boundaries."""

    def test_can_instantiate_with_minimal_args(self, fresh_container):
        from embedagent.tools import ToolRuntime
        from embedagent_core.query_engine import QueryEngine
        from embedagent_host.providers.openai_compatible import OpenAICompatibleClient

        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test_workspace"
        tools.tool_result_store = MagicMock()
        tools.projection_db = MagicMock()
        engine = QueryEngine(client=client, tools=tools)
        assert engine is not None

    def test_has_run_method(self):
        from embedagent_core.query_engine import QueryEngine

        assert hasattr(QueryEngine, "run")
        assert callable(QueryEngine.run)

    def test_has_stop_method(self):
        from embedagent_core.query_engine import QueryEngine

        assert hasattr(QueryEngine, "stop")
        assert callable(QueryEngine.stop)

    def test_has_submit_user_turn_method(self):
        from embedagent_core.query_engine import QueryEngine

        assert hasattr(QueryEngine, "submit_user_turn")
        assert callable(QueryEngine.submit_user_turn)

    def test_workflow_prompt_assembly_lives_outside_query_engine(self):
        from embedagent_core.query_engine import QueryEngine

        assert not hasattr(QueryEngine, "_append_workflow_prompt_messages")
        assert not hasattr(QueryEngine, "_should_inject_workflow_prompt")


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
        if rel.startswith("src/embedagent/workflow_packages/c_cpp/"):
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
        from embedagent.core.adapter import get_inprocess_adapter
        from embedagent_host.inprocess_adapter import InProcessAdapter

        result = get_inprocess_adapter()
        assert result is InProcessAdapter


def test_tool_runtime_does_not_import_mode_registry_for_schema_projection():
    runtime_source = _read(ROOT / "src/embedagent/tools/runtime.py")
    assert "from embedagent.modes import allowed_tools_for" not in runtime_source
    assert "allowed_tools_for(mode_name)" not in runtime_source


def test_c_workflow_tools_are_declared_only_by_c_workflow_package_or_tests():
    c_tools = (
        "list_recipes",
        "run_recipe",
        "report_quality_v2",
        "record_failing_evidence",
        "task_status",
    )
    allowed_prefixes = ("src/embedagent/workflow_packages/c_cpp/",)
    assert not (ROOT / "src/embedagent/tools/recipe_ops.py").exists()
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
    base_profile = ROOT / "src/embedagent/agent_profiles.py"
    c_profile = ROOT / "src/embedagent/workflow_packages/c_cpp/agent_profile.py"
    application = ROOT / "src/embedagent/workflow_packages/c_cpp/application.py"
    loader = ROOT / "src/embedagent/agent_applications.py"

    assert c_profile.is_file()

    base_text = _read(base_profile)
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
            offenders.append("src/embedagent/agent_profiles.py contains %s" % token)
    assert offenders == []

    assert "default_c_cpp_agent_profile" not in _read(loader)
    assert "embedagent.workflow_packages.c_cpp.agent_profile" in _read(application)


def test_product_evidence_helpers_do_not_import_c_cpp_workflow_constants():
    files = (
        ROOT / "src/embedagent/review_command.py",
        ROOT / "src/embedagent/project_memory.py",
        ROOT / "src/embedagent/workspace_intelligence.py",
    )
    forbidden = (
        "embedagent.workflow_packages.c_cpp",
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
        ROOT / "src/embedagent/workspace_recipes.py",
        ROOT / "src/embedagent/workspace_profile.py",
        ROOT / "src/embedagent/tools/_base.py",
        ROOT / "src/embedagent/tools/runtime.py",
    )
    forbidden = (
        "embedagent.workflow_packages.c_cpp",
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

    assert "聚合与 `run_recipe` 归一化位于 `src/embedagent/workspace_recipes.py`" not in text
    assert "`src/embedagent/workspace_recipes.py`" in text
    assert "workflow-neutral file-resource/read-model facade" in text
    assert "不做 CMake/Make/Ninja 检测" in text
    assert "src/embedagent/workflow_packages/c_cpp/workspace_recipes.py" in text
