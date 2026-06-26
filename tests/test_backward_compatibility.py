"""Compatibility and boundary tests for architecture refactors.

These tests verify that current public APIs remain usable while stale
compatibility aliases stay removed.
"""

from unittest.mock import MagicMock


class TestPublicImports(object):
    """Verify public imports and removed-alias boundaries."""

    def test_import_inprocess_adapter(self):
        from embedagent.inprocess_adapter import InProcessAdapter

        assert InProcessAdapter is not None

    def test_import_query_engine(self):
        from embedagent.query_engine import QueryEngine

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
        from embedagent.strategies import (
            ContextCompactionEngine,
            LLMClientRetryWrapper,
        )

        assert ContextCompactionEngine is not None
        assert LLMClientRetryWrapper is not None

    def test_turn_orchestrator_legacy_strategy_removed(self):
        import embedagent.strategies as strategies

        assert not hasattr(strategies, "TurnOrchestrator")

    def test_import_di_container(self):
        from embedagent.di_container import DIContainer, get_default_container

        assert DIContainer is not None
        assert callable(get_default_container)

    def test_mode_registry_alias_removed(self):
        import embedagent.modes as modes

        assert not hasattr(modes, "MODE_REGISTRY")
        assert "explore" in modes.get_mode_registry()

    def test_core_adapter_legacy_accessor_removed(self):
        import embedagent.core.adapter as adapter

        assert not hasattr(adapter, "_inprocess_adapter")
        assert not hasattr(adapter, "_get_adapter_class")
        assert adapter.get_inprocess_adapter() is not None

    def test_core_adapter_snapshot_falls_back_to_default_mode(self):
        from embedagent.core.adapter import _session_snapshot_from_dict
        from embedagent.modes import DEFAULT_MODE

        snapshot = _session_snapshot_from_dict({})

        assert snapshot.current_mode == DEFAULT_MODE


class TestInProcessAdapterCompatibility(object):
    """Verify InProcessAdapter public API unchanged."""

    def _make_adapter(self):
        from embedagent.inprocess_adapter import InProcessAdapter
        from embedagent.llm import OpenAICompatibleClient
        from embedagent.tools import ToolRuntime

        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test_workspace"
        tools.tool_result_store = MagicMock()
        return InProcessAdapter(client=client, tools=tools)

    def test_can_instantiate_with_no_args(self):
        from embedagent.inprocess_adapter import InProcessAdapter

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
        from embedagent.inprocess_adapter import InProcessAdapter

        assert hasattr(InProcessAdapter, "_run_turn")
        assert not hasattr(InProcessAdapter, "_run_turn_v2")

    def test_resource_command_specs_live_outside_adapter(self):
        from embedagent.inprocess_adapter import InProcessAdapter

        assert not hasattr(InProcessAdapter, "_resource_command_specs")
        assert not hasattr(InProcessAdapter, "_skill_command_specs")


class TestQueryEngineCompatibility(object):
    """Verify QueryEngine public API unchanged."""

    def test_can_instantiate_with_minimal_args(self, fresh_container):
        from embedagent.llm import OpenAICompatibleClient
        from embedagent.query_engine import QueryEngine
        from embedagent.tools import ToolRuntime

        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test_workspace"
        tools.tool_result_store = MagicMock()
        tools.projection_db = MagicMock()
        engine = QueryEngine(client=client, tools=tools)
        assert engine is not None

    def test_has_run_method(self):
        from embedagent.query_engine import QueryEngine

        assert hasattr(QueryEngine, "run")
        assert callable(QueryEngine.run)

    def test_has_stop_method(self):
        from embedagent.query_engine import QueryEngine

        assert hasattr(QueryEngine, "stop")
        assert callable(QueryEngine.stop)

    def test_has_submit_user_turn_method(self):
        from embedagent.query_engine import QueryEngine

        assert hasattr(QueryEngine, "submit_user_turn")
        assert callable(QueryEngine.submit_user_turn)


class TestModesCompatibility(object):
    """Verify modes module public API unchanged."""

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

        assert not hasattr(command_sanitizer, "_DEFAULT_SANITIZER")
        assert not hasattr(command_sanitizer, "get_default_sanitizer")
        assert command_sanitizer.get_command_sanitizer() is not None

    def test_get_inprocess_adapter_returns_class(self):
        from embedagent.core.adapter import get_inprocess_adapter
        from embedagent.inprocess_adapter import InProcessAdapter

        result = get_inprocess_adapter()
        assert result is InProcessAdapter
