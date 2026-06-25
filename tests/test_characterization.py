"""Characterization tests for extracted components from Phase 3 architecture refactor.

These tests capture current behavior to detect unintended changes during
future refactoring.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from embedagent.llm import OpenAICompatibleClient
from embedagent.query_engine import QueryEngine
from embedagent.services.event_emitter import EventEmitter
from embedagent.services.session_lifecycle import SessionLifecycleManager
from embedagent.services.workspace_file_service import WorkspaceFileService
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper
from embedagent.tools import ToolRuntime


class TestInProcessAdapterFacade(object):
    """Characterization tests for the refactored InProcessAdapter facade."""

    def test_constructor_signature_unchanged(self):
        """Verify QueryEngine constructor accepts same parameters."""
        sig = inspect.signature(QueryEngine.__init__)
        params = list(sig.parameters.keys())
        assert "client" in params
        assert "tools" in params
        assert "max_turns" in params
        assert "permission_policy" in params
        assert "context_manager" in params

    def test_query_engine_has_run_method(self):
        """Verify QueryEngine.run() exists and is callable."""
        assert hasattr(QueryEngine, "run")
        assert callable(QueryEngine.run)

    def test_query_engine_has_stop_method(self):
        """Verify QueryEngine.stop() exists and is callable."""
        assert hasattr(QueryEngine, "stop")
        assert callable(QueryEngine.stop)


class TestServiceDelegation(object):
    """Characterization tests verifying services are properly wired."""

    def _make_adapter(self, fresh_container):
        """Helper to create an InProcessAdapter with mocked dependencies."""
        from embedagent.inprocess_adapter import InProcessAdapter

        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test_workspace"
        tools.tool_result_store = MagicMock()
        return InProcessAdapter(client=client, tools=tools)

    def test_inprocess_adapter_has_session_lifecycle(self, fresh_container):
        adapter = self._make_adapter(fresh_container)
        assert hasattr(adapter, "_session_lifecycle")
        assert isinstance(adapter._session_lifecycle, SessionLifecycleManager)

    def test_inprocess_adapter_exposes_thread_lifecycle_facade(self, fresh_container):
        adapter = self._make_adapter(fresh_container)

        assert callable(adapter.rename_session)
        assert callable(adapter.archive_session)
        assert callable(adapter.fork_session)

    def test_inprocess_adapter_has_event_emitter(self, fresh_container):
        adapter = self._make_adapter(fresh_container)
        assert hasattr(adapter, "_event_emitter")
        assert isinstance(adapter._event_emitter, EventEmitter)

    def test_inprocess_adapter_has_workspace_service(self, fresh_container):
        adapter = self._make_adapter(fresh_container)
        assert hasattr(adapter, "_workspace_files")
        assert isinstance(adapter._workspace_files, WorkspaceFileService)

    def test_inprocess_adapter_does_not_own_harness_sync(self, fresh_container):
        adapter = self._make_adapter(fresh_container)
        assert not hasattr(adapter, "_harness_sync")

    def test_query_engine_has_strategies(self, fresh_container):
        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test_workspace"
        tools.tool_result_store = MagicMock()
        tools.projection_db = MagicMock()
        engine = QueryEngine(client=client, tools=tools)

        assert hasattr(engine, "_llm_wrapper")
        assert isinstance(engine._llm_wrapper, LLMClientRetryWrapper)
        assert not hasattr(engine, "_compaction")
        assert not hasattr(engine, "_turn_orchestrator")


class TestEventEmissionChain(object):
    """Characterization tests for event emission behavior."""

    def test_emit_calls_handlers(self, fresh_container):
        emitter = EventEmitter()
        called_with = []

        def handler(event_type, session_id, payload):
            called_with.append((event_type, session_id, payload))

        emitter.add_handler("test_event", handler)
        emitter.emit(None, "test_event", "sess-1", {"key": "value"})

        assert len(called_with) == 1
        assert called_with[0] == ("test_event", "sess-1", {"key": "value"})

    def test_handler_exception_isolated(self, fresh_container):
        emitter = EventEmitter()
        second_called = []

        def bad_handler(event_type, session_id, payload):
            raise RuntimeError("boom")

        def good_handler(event_type, session_id, payload):
            second_called.append(True)

        emitter.add_handler("test_event", bad_handler)
        emitter.add_handler("test_event", good_handler)
        emitter.emit(None, "test_event", "sess-1", {})  # should not raise

        assert len(second_called) == 1


class TestWorkspaceBoundary(object):
    """Characterization tests for workspace file service boundaries."""

    def test_resolve_rejects_escape(self, tmp_path):
        service = WorkspaceFileService(str(tmp_path))
        with pytest.raises(ValueError):
            service.resolve_path("../../../etc/passwd")

    def test_resolve_accepts_subpath(self, tmp_path):
        service = WorkspaceFileService(str(tmp_path))
        result = service.resolve_path("subdir/file.txt", allow_missing=True)
        assert result.startswith(str(tmp_path))
        assert "subdir" in result


class TestLLMRetryBehavior(object):
    """Characterization tests for LLM retry wrapper."""

    def test_retry_on_server_error(self):
        wrapper = LLMClientRetryWrapper(
            client=MagicMock(),
            max_retries=2,
            base_delay=0.01,  # fast for tests
        )

        # Mock client to fail once then succeed
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                from embedagent.llm import ModelClientError

                raise ModelClientError("HTTP 500: internal server error")
            from embedagent.session import AssistantReply

            return AssistantReply(content="ok", actions=[])

        wrapper.client.generate = side_effect
        result = wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        assert call_count[0] == 2
        assert result.content == "ok"

    def test_max_retries_exhausted(self):
        from embedagent.llm import ModelClientError

        wrapper = LLMClientRetryWrapper(
            client=MagicMock(),
            max_retries=2,
            base_delay=0.01,
        )
        wrapper.client.generate = MagicMock(side_effect=ModelClientError("HTTP 500: always fails"))

        with pytest.raises(ModelClientError):
            wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])

        assert wrapper.client.generate.call_count == 2  # 2 attempts (max_retries=2)
