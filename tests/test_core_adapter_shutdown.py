import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.core.adapter import AgentCoreAdapter


class _RuntimeAdapterWithoutShutdown(object):
    def __init__(self):
        self.cancelled = []

    def list_sessions(self, limit=10):
        del limit
        return [
            {"session_id": "session-a"},
            {"session_id": "session-b"},
        ]

    def cancel_session(self, session_id):
        self.cancelled.append(session_id)
        return {"session_id": session_id}


class _RuntimeAdapterWithFailingShutdown(object):
    def __init__(self):
        self.shutdown_calls = 0

    def shutdown(self):
        self.shutdown_calls += 1
        raise RuntimeError("shutdown failed")


class TestAgentCoreAdapterShutdown(unittest.TestCase):
    def test_shutdown_cancels_sessions_and_detaches_frontend_state(self):
        runtime = _RuntimeAdapterWithoutShutdown()
        adapter = AgentCoreAdapter("workspace")
        adapter._adapter = runtime
        adapter._frontend = object()
        adapter._callback_bridge = object()

        adapter.shutdown()

        self.assertEqual(runtime.cancelled, ["session-a", "session-b"])
        self.assertIsNone(adapter._adapter)
        self.assertIsNone(adapter._frontend)
        self.assertIsNone(adapter._callback_bridge)

    def test_shutdown_swallows_runtime_shutdown_errors(self):
        runtime = _RuntimeAdapterWithFailingShutdown()
        adapter = AgentCoreAdapter("workspace")
        adapter._adapter = runtime

        adapter.shutdown()

        self.assertEqual(runtime.shutdown_calls, 1)
        self.assertIsNone(adapter._adapter)


if __name__ == "__main__":
    unittest.main()
