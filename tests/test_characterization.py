"""Characterization tests for extracted components from Phase 3 architecture refactor.

These tests capture current behavior to detect unintended changes during
future refactoring.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from embedagent_core.strategies.llm_retry_wrapper import LLMClientRetryWrapper
from embedagent_host.providers.openai_compatible import OpenAICompatibleClient
from embedagent_host.runtime.services.event_emitter import EventEmitter
from embedagent_host.runtime.services.session_lifecycle import SessionLifecycleManager
from embedagent_host.runtime.services.workspace_file_service import WorkspaceFileService
from embedagent_host.runtime.tools import ToolRuntime


class TestServiceDelegation(object):
    """Characterization tests verifying services are properly wired."""

    def _make_adapter(self, fresh_container, tmp_path):
        """Helper to create an InProcessAdapter with mocked dependencies."""
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.runtime.agent_applications import base_agent_application_registry

        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        tools.workspace = str(workspace)
        tools.tool_result_store = MagicMock()
        return InProcessAdapter(
            client=client,
            tools=tools,
            agent_application_id="embedagent.generic",
            agent_application_registry=base_agent_application_registry(),
        )

    def test_inprocess_adapter_has_session_lifecycle(self, fresh_container, tmp_path):
        adapter = self._make_adapter(fresh_container, tmp_path)
        assert hasattr(adapter, "_session_lifecycle")
        assert isinstance(adapter._session_lifecycle, SessionLifecycleManager)

    def test_inprocess_adapter_exposes_thread_lifecycle_facade(self, fresh_container, tmp_path):
        adapter = self._make_adapter(fresh_container, tmp_path)

        assert callable(adapter.rename_session)
        assert callable(adapter.archive_session)
        assert callable(adapter.fork_session)

    def test_inprocess_adapter_has_event_emitter(self, fresh_container, tmp_path):
        adapter = self._make_adapter(fresh_container, tmp_path)
        assert hasattr(adapter, "_event_emitter")
        assert isinstance(adapter._event_emitter, EventEmitter)

    def test_inprocess_adapter_has_workspace_service(self, fresh_container, tmp_path):
        adapter = self._make_adapter(fresh_container, tmp_path)
        assert hasattr(adapter, "_workspace_files")
        assert isinstance(adapter._workspace_files, WorkspaceFileService)

    def test_inprocess_adapter_does_not_own_harness_sync(self, fresh_container, tmp_path):
        adapter = self._make_adapter(fresh_container, tmp_path)
        assert not hasattr(adapter, "_harness_sync")


class TestEventEmissionChain(object):
    """Characterization tests for event emission behavior."""

    def test_emit_calls_handlers(self, fresh_container):
        called_with = []

        emitter = EventEmitter(SimpleNamespace(on_session_event=called_with.append))
        emitter.emit("test_event", "sess-1", {"key": "value"})

        assert len(called_with) == 1
        assert called_with[0].event_kind == "test.event"
        assert called_with[0].session_id == "sess-1"
        assert called_with[0].payload == {"key": "value"}

    def test_handler_exception_propagates(self, fresh_container):
        def bad_handler(envelope):
            del envelope
            raise RuntimeError("boom")

        emitter = EventEmitter(SimpleNamespace(on_session_event=bad_handler))
        with pytest.raises(RuntimeError, match="boom"):
            emitter.emit("test_event", "sess-1", {})


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
                from embedagent_core.model import ModelClientError

                raise ModelClientError("HTTP 500: internal server error")
            from embedagent_core.session import AssistantReply

            return AssistantReply(content="ok", actions=[])

        wrapper.client.generate = side_effect
        result = wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        assert call_count[0] == 2
        assert result.content == "ok"

    def test_max_retries_exhausted(self):
        from embedagent_core.model import ModelClientError

        wrapper = LLMClientRetryWrapper(
            client=MagicMock(),
            max_retries=2,
            base_delay=0.01,
        )
        wrapper.client.generate = MagicMock(side_effect=ModelClientError("HTTP 500: always fails"))

        with pytest.raises(ModelClientError):
            wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])

        assert wrapper.client.generate.call_count == 2  # 2 attempts (max_retries=2)
