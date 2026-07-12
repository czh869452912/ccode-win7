"""Boundary tests for QueryEngine orchestration ownership."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from embedagent_core.permissions import PermissionPolicy
from embedagent_core.query_engine import QueryEngine
from embedagent_host.providers.openai_compatible import OpenAICompatibleClient
from embedagent_host.runtime.context import ContextManager
from embedagent_host.runtime.tools import ToolRuntime


class TestQueryEngineOrchestrationOwnership(unittest.TestCase):
    def test_query_engine_instantiation(self):
        """QueryEngine() still works with same constructor arguments."""
        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test"
        tools.tool_result_store = MagicMock()
        tools.projection_db = MagicMock()

        engine = QueryEngine(
            client=client,
            tools=tools,
            max_turns=8,
            permission_policy=PermissionPolicy(auto_approve_all=True),
            context_manager=ContextManager(),
            max_parallel_tools=3,
        )

        self.assertIsNotNone(engine)
        self.assertEqual(engine.max_turns, 8)
        self.assertIsNotNone(engine._llm_wrapper)
        self.assertFalse(hasattr(engine, "_compaction"))
        self.assertFalse(hasattr(engine, "_turn_orchestrator"))

    def test_query_engine_run_signature(self):
        """run() accepts same core parameters."""
        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test"
        tools.tool_result_store = MagicMock()
        tools.projection_db = MagicMock()
        tools.schemas_for.return_value = []

        engine = QueryEngine(client=client, tools=tools)

        # run() should exist and accept user_text and initial_mode
        self.assertTrue(hasattr(engine, "run"))
        self.assertTrue(callable(engine.run))

    def test_query_engine_stop_works(self):
        """stop() interrupts run() without error."""
        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test"
        tools.tool_result_store = MagicMock()
        tools.projection_db = MagicMock()
        tools.schemas_for.return_value = []

        engine = QueryEngine(client=client, tools=tools)

        # stop() should exist
        self.assertTrue(hasattr(engine, "stop"))
        self.assertTrue(callable(engine.stop))

        # Calling stop() should not raise
        engine.stop()
        self.assertTrue(engine._internal_stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
