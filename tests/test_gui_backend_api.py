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


class _ModeCaptureCore(_FakeCore):
    def __init__(self):
        super().__init__()
        self.create_modes = []
        self.resume_modes = []

    def create_session(self, mode):
        self.create_modes.append(mode)
        return {
            "session_id": "sess-new",
            "status": "idle",
            "current_mode": mode,
        }

    def resume_session(self, session_id, mode):
        self.resume_modes.append((session_id, mode))
        return {
            "session_id": session_id,
            "status": "idle",
            "current_mode": mode or "restored",
        }


class _FakeCoreWithTimeline(_FakeCore):
    def get_session_bootstrap(self, session_id):
        return {
            "snapshot": {
                "session_id": session_id,
                "status": "idle",
                "current_mode": "build",
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
                "timeline_replay_status": "healthy",
                "timeline_first_seq": 1,
                "timeline_last_seq": 4,
                "timeline_integrity": "healthy",
                "pending_interaction_valid": False,
                "restore_stop_reason": "",
                "current_phase": "implement",
                "discipline_profile": "lite_spec_tdd",
                "current_activity": "build harness active (implement)",
                "task_summary": "in_progress build:implement",
                "task_items": [
                    {"id": 1, "content": "build:implement", "status": "in_progress", "done": False}
                ],
            },
            "history": {
                "session_id": session_id,
                "history_source": "session_state",
                "turns": [],
                "current_interaction": None,
                "integrity": {
                    "status": "healthy",
                    "restore_stop_reason": "",
                    "consumed_event_count": 0,
                    "transcript_event_count": 0,
                },
            },
            "plan": None,
            "permission_context": {
                "session_id": session_id,
                "rules_path": "",
                "categories": [],
                "rules": [],
                "remembered_categories": [],
                "auto_approve_all": True,
                "auto_approve_writes": False,
                "auto_approve_commands": False,
            },
            "replay": {
                "status": "replay",
                "first_seq": 3,
                "last_seq": 4,
                "reason": "",
                "events": [],
            },
        }

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


class _ResourceReloadCore(_FakeCore):
    def __init__(self):
        super().__init__()
        self.reload_calls = []

    def reload_resources(self, session_id, reason="api"):
        self.reload_calls.append((session_id, reason))
        return {
            "workspace": "D:/workspace",
            "reason": reason,
            "counts": {"skills": 1, "prompts": 0, "recipes": 2},
            "diagnostics": [],
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
                "current_mode": "build",
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
                "current_phase": "implement",
                "discipline_profile": "lite_spec_tdd",
                "current_activity": "build harness active (implement)",
                "task_summary": "in_progress build:implement",
                "task_items": [
                    {"id": 1, "content": "build:implement", "status": "in_progress", "done": False}
                ],
            },
        )()


class TestGuiBackendApi(unittest.TestCase):
    def test_create_session_defaults_to_explore_mode(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _ModeCaptureCore()
            backend = GUIBackend(core, static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/sessions" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            payload = asyncio.run(route.endpoint())
        self.assertEqual(core.create_modes, ["explore"])
        self.assertEqual(payload["current_mode"], "explore")

    def test_resume_session_does_not_override_restored_mode_by_default(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _ModeCaptureCore()
            backend = GUIBackend(core, static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/resume" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            payload = asyncio.run(route.endpoint("sess-old"))
        self.assertEqual(core.resume_modes, [("sess-old", "")])
        self.assertEqual(payload["current_mode"], "restored")

    def test_post_interaction_response_uses_unified_endpoint(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_FakeCore(), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/interactions/{interaction_id}/respond" and "POST" in getattr(
                    item, "methods", set()
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

    def test_post_interaction_response_resolves_frontend_pending_input_before_core_fallback(self):
        from embedagent.frontend.gui.backend.bridge import BlockingResult

        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _SnapshotCore("")
            backend = GUIBackend(core, static_dir=static_dir)
            backend.frontend._pending_inputs["int-1"] = BlockingResult(None)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/interactions/{interaction_id}/respond" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            response = asyncio.run(
                route.endpoint(
                    "sess-1",
                    "int-1",
                    {
                        "response_kind": "answer",
                        "answer": "继续",
                        "selected_option_text": "继续",
                    },
                )
            )
        self.assertEqual(core.respond_calls, [])
        self.assertEqual(response["interaction_id"], "int-1")
        self.assertEqual(response["status"], "resolved")

    def test_post_interaction_response_resolves_frontend_pending_permission_before_core_fallback(
        self,
    ):
        from embedagent.frontend.gui.backend.bridge import BlockingResult

        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _SnapshotCore("")
            backend = GUIBackend(core, static_dir=static_dir)
            backend.frontend._pending_permissions["perm-1"] = BlockingResult(False)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/interactions/{interaction_id}/respond" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            response = asyncio.run(
                route.endpoint(
                    "sess-1",
                    "perm-1",
                    {
                        "response_kind": "approve",
                        "decision": True,
                    },
                )
            )
        self.assertEqual(core.respond_calls, [])
        self.assertEqual(response["interaction_id"], "perm-1")
        self.assertEqual(response["status"], "resolved")

    def test_get_session_events_replays_only_entries_after_seq(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_FakeCoreWithTimeline(), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/events" and "GET" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            response = asyncio.run(route.endpoint("sess-1", 2, 200))
        self.assertEqual(response["status"], "replay")
        self.assertEqual([item["seq"] for item in response["events"]], [3, 4])

    def test_bootstrap_endpoint_returns_snapshot_history_plan_and_permissions(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_FakeCoreWithTimeline(), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/bootstrap" and "GET" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            payload = asyncio.run(route.endpoint("sess-1"))
        self.assertIn("snapshot", payload)
        self.assertIn("history", payload)
        self.assertIn("plan", payload)
        self.assertIn("permission_context", payload)

    def test_reload_resources_endpoint_calls_core_with_session_context(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _ResourceReloadCore()
            backend = GUIBackend(core, static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/resources/reload" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            payload = asyncio.run(route.endpoint("sess-1"))
        self.assertEqual(core.reload_calls, [("sess-1", "api")])
        self.assertEqual(payload["reason"], "api")
        self.assertEqual(payload["counts"]["skills"], 1)

    def test_session_lookup_errors_return_404_instead_of_500(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_ErrorCore("session_id 不存在：sess-404"), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/sessions/{session_id}" and "GET" in getattr(
                    item, "methods", set()
                ):
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
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/interactions/{interaction_id}/respond" and "POST" in getattr(
                    item, "methods", set()
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
                if getattr(item, "path", "") == "/api/sessions/{session_id}" and "GET" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            payload = asyncio.run(route.endpoint("sess-1"))
        self.assertEqual(payload["timeline_replay_status"], "degraded")
        self.assertEqual(payload["current_phase"], "implement")
        self.assertEqual(payload["discipline_profile"], "lite_spec_tdd")
        self.assertEqual(payload["task_items"][0]["content"], "build:implement")


if __name__ == "__main__":
    unittest.main()
