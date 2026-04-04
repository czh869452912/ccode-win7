import asyncio
import os
import sys
import tempfile
import unittest

from fastapi import HTTPException

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


class _FakeCoreWithTimeline(_FakeCore):
    def load_session_events_after(self, session_id, after_seq, limit=200):
        return {
            "status": "replay",
            "first_seq": 3,
            "last_seq": 4,
            "reason": "",
            "events": [
                {
                    "event_id": "evt-3",
                    "seq": 3,
                    "created_at": "2026-04-04T00:00:03Z",
                    "event_kind": "tool.started",
                    "payload": {"tool_name": "read_file"},
                },
                {
                    "event_id": "evt-4",
                    "seq": 4,
                    "created_at": "2026-04-04T00:00:04Z",
                    "event_kind": "tool.finished",
                    "payload": {"tool_name": "read_file", "success": True},
                },
            ],
        }


class _ErrorCore(_FakeCore):
    def __init__(self, error_text):
        super().__init__()
        self.error_text = error_text

    def get_session_snapshot(self, session_id):
        raise ValueError(self.error_text)

    def respond_to_interaction(self, session_id, interaction_id, payload):
        raise ValueError(self.error_text)


class _SnapshotCore(_FakeCore):
    def __init__(self, stop_reason):
        super().__init__()
        self.stop_reason = stop_reason

    def get_session_snapshot(self, session_id):
        return type(
            "Snapshot",
            (),
            {
                "session_id": session_id,
                "status": type("Status", (), {"value": "idle"})(),
                "current_mode": "code",
                "created_at": "2026-04-04T00:00:00Z",
                "updated_at": "2026-04-04T00:00:00Z",
                "workflow_state": "chat",
                "has_active_plan": False,
                "active_plan_ref": "",
                "current_command_context": "",
                "has_pending_permission": False,
                "has_pending_input": False,
                "pending_permission": None,
                "pending_input": None,
                "last_error": None,
                "runtime_source": "",
                "bundled_tools_ready": False,
                "fallback_warnings": [],
                "runtime_environment": None,
                "timeline_replay_status": "degraded",
                "timeline_first_seq": 0,
                "timeline_last_seq": 0,
                "timeline_integrity": "degraded",
                "pending_interaction_valid": False,
                "restore_stop_reason": self.stop_reason,
            },
        )()


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

    def test_get_session_events_replays_only_entries_after_seq(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_FakeCoreWithTimeline(), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/sessions/{session_id}/events" and "GET" in getattr(item, "methods", set()):
                    route = item
                    break
            self.assertIsNotNone(route)
            response = asyncio.run(route.endpoint("sess-1", 2, 200))
        self.assertEqual(response["status"], "replay")
        self.assertEqual([item["seq"] for item in response["events"]], [3, 4])

    def test_session_lookup_errors_return_404_instead_of_500(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_ErrorCore("session_id 不存在：sess-404"), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/sessions/{session_id}" and "GET" in getattr(item, "methods", set()):
                    route = item
                    break
            self.assertIsNotNone(route)
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint("sess-404"))
        self.assertEqual(raised.exception.status_code, 404)

    def test_interaction_lookup_errors_return_410(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_ErrorCore("interaction_gone"), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if (
                    getattr(item, "path", "") == "/api/sessions/{session_id}/interactions/{interaction_id}/respond"
                    and "POST" in getattr(item, "methods", set())
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint("sess-1", "int-1", {"response_kind": "approve"}))
        self.assertEqual(raised.exception.status_code, 410)

    def test_snapshot_route_reports_transcript_missing_as_degraded_metadata(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_SnapshotCore("transcript_missing"), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/sessions/{session_id}" and "GET" in getattr(item, "methods", set()):
                    route = item
                    break
            self.assertIsNotNone(route)
            payload = asyncio.run(route.endpoint("sess-1"))
        self.assertEqual(payload["timeline_replay_status"], "degraded")


if __name__ == "__main__":
    unittest.main()
