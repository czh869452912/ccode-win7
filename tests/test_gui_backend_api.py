import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.server import GUIBackend


class _FakeCore(object):
    def __init__(self):
        self.frontend = None
        self.respond_calls = []

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def respond_to_interaction(self, session_id, interaction_id, payload):
        self.respond_calls.append((session_id, interaction_id, payload))
        return {
            "session_id": session_id,
            "interaction_id": interaction_id,
            "status": "resolved",
        }


class TestGuiBackendApi(unittest.TestCase):
    def test_post_interaction_response_uses_unified_endpoint(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_FakeCore(), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if (
                    getattr(item, "path", "") == "/api/sessions/{session_id}/interactions/{interaction_id}/respond"
                    and "POST" in getattr(item, "methods", set())
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            response = asyncio.run(
                route.endpoint(
                    "sess-1",
                    "int-1",
                    {
                        "response_kind": "approve",
                        "decision": True,
                        "client_request_id": "cli-1",
                    },
                )
            )
        self.assertEqual(response["interaction_id"], "int-1")


if __name__ == "__main__":
    unittest.main()
