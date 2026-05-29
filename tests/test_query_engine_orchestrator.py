"""Backward compatibility tests for QueryEngine after strategy extraction."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from embedagent.context import ContextManager
from embedagent.llm import OpenAICompatibleClient
from embedagent.permissions import PermissionPolicy
from embedagent.query_engine import QueryEngine
from embedagent.tools import ToolRuntime


class TestQueryEngineBackwardCompatibility(unittest.TestCase):
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
        self.assertIsNotNone(engine._compaction)
        self.assertIsNotNone(engine._turn_orchestrator)

    def test_query_engine_run_signature(self):
        """run() accepts same core parameters."""
        client = MagicMock(spec=OpenAICompatibleClient)
        tools = MagicMock(spec=ToolRuntime)
        tools.workspace = "/tmp/test"
        tools.tool_result_store = MagicMock()
        tools.projection_db = MagicMock()
        tools.allowed_tool_names.return_value = []
        tools.schemas_for.return_value = []
        tools.describe_mode.return_value = None

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
        tools.allowed_tool_names.return_value = []
        tools.schemas_for.return_value = []
        tools.describe_mode.return_value = None

        engine = QueryEngine(client=client, tools=tools)

        # stop() should exist
        self.assertTrue(hasattr(engine, "stop"))
        self.assertTrue(callable(engine.stop))

        # Calling stop() should not raise
        engine.stop()
        self.assertTrue(engine._internal_stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
