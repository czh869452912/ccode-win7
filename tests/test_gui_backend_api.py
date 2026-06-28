import asyncio
import os
import sys
import tempfile
import unittest

from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.preview_service import PreviewService
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
                "last_error": None,
                "runtime_source": "",
                "bundled_tools_ready": False,
                "fallback_warnings": [],
                "runtime_environment": None,
                "pending_interaction_valid": False,
                "restore_stop_reason": "",
                "compact_summary_text": "summary kept for diagnostics",
                "context_analysis": {"approx_tokens": 1200},
                "compact_boundary_count": 1,
                "workspace_intelligence": [{"kind": "file", "path": "main.c"}],
                "context_pipeline_steps": ["assemble", "compact"],
                "last_transition_reason": "aborted",
                "last_transition_message": "cancelled by user",
                "last_transition_display_reason": "cancelled",
                "recent_transition_reasons": ["permission_wait", "aborted"],
                "recent_transitions": [
                    {
                        "reason": "aborted",
                        "display_reason": "cancelled",
                        "message": "cancelled by user",
                    }
                ],
                "compact_retry_count": 2,
                "restore_consumed_event_count": 7,
                "restore_transcript_event_count": 8,
                "operation_diagnostics": {"active_operations": 0},
                "runtime_config": {"resource_revision": {"revision": 3}},
                "compaction_state": {"boundary_count": 1, "latest_boundary_id": "cb-1"},
                "recovery_state": {"marker_count": 1, "latest_marker_id": "rm-1"},
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


class _FileWriteCore(_FakeCore):
    def __init__(self):
        super().__init__()
        self.write_calls = []

    def write_file(self, path, content):
        self.write_calls.append((path, content))
        return {"path": path, "content": content}


class _ThreadLifecycleCore(_FakeCore):
    def __init__(self):
        super().__init__()
        self.calls = []

    def rename_session(self, session_id, title):
        self.calls.append(("rename", session_id, title))
        return {
            "session_id": session_id,
            "title": title,
            "thread": {
                "title": title,
                "archived": False,
                "archived_at": "",
                "forked_from": "",
                "forked_at": "",
            },
        }

    def archive_session(self, session_id):
        self.calls.append(("archive", session_id))
        return {
            "session_id": session_id,
            "thread": {
                "title": "",
                "archived": True,
                "archived_at": "2026-06-17T00:00:00Z",
                "forked_from": "",
                "forked_at": "",
            },
        }

    def fork_session(self, session_id, title=""):
        self.calls.append(("fork", session_id, title))
        return {
            "session_id": "sess-fork",
            "title": title or "Copy",
            "thread": {
                "title": title or "Copy",
                "archived": False,
                "archived_at": "",
                "forked_from": session_id,
                "forked_at": "2026-06-17T00:00:00Z",
            },
        }


class _ErrorCore(_FakeCore):
    def __init__(self, error_text):
        super().__init__()
        self.error_text = error_text

    def get_session_snapshot(self, session_id):
        raise ValueError(self.error_text)

    def respond_to_interaction(self, session_id, interaction_id, payload):
        raise ValueError(self.error_text)

    def rename_session(self, session_id, title):
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
                "last_error": None,
                "runtime_source": "",
                "bundled_tools_ready": False,
                "fallback_warnings": [],
                "runtime_environment": None,
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
    def _route(self, backend, path, method):
        for item in backend.app.routes:
            if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
                return item
        return None

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

    def test_thread_lifecycle_routes_call_core(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _ThreadLifecycleCore()
            backend = GUIBackend(core, static_dir=static_dir)

            routes = {}
            for item in backend.app.routes:
                path = getattr(item, "path", "")
                if path in (
                    "/api/sessions/{session_id}/rename",
                    "/api/sessions/{session_id}/archive",
                    "/api/sessions/{session_id}/fork",
                ):
                    routes[path] = item

            rename_payload = asyncio.run(
                routes["/api/sessions/{session_id}/rename"].endpoint(
                    "sess-1",
                    {"title": "Renamed"},
                )
            )
            archive_payload = asyncio.run(
                routes["/api/sessions/{session_id}/archive"].endpoint("sess-1")
            )
            fork_payload = asyncio.run(
                routes["/api/sessions/{session_id}/fork"].endpoint(
                    "sess-1",
                    {"title": "Copy"},
                )
            )

        self.assertEqual(
            core.calls,
            [
                ("rename", "sess-1", "Renamed"),
                ("archive", "sess-1"),
                ("fork", "sess-1", "Copy"),
            ],
        )
        self.assertEqual(rename_payload["session"]["title"], "Renamed")
        self.assertTrue(archive_payload["session"]["thread"]["archived"])
        self.assertEqual(fork_payload["session_id"], "sess-fork")
        self.assertEqual(fork_payload["session"]["thread"]["forked_from"], "sess-1")

    def test_thread_lifecycle_errors_map_to_http_status(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_ErrorCore("invalid_thread_title"), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/sessions/{session_id}/rename":
                    route = item
                    break
            self.assertIsNotNone(route)
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint("sess-1", {"title": ""}))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail, "invalid_thread_title")

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

    def test_post_interaction_response_emits_backend_owned_resolved_event(self):
        from embedagent.frontend.gui.backend.bridge import BlockingResult

        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _SnapshotCore("")
            backend = GUIBackend(core, static_dir=static_dir)
            messages = []
            backend.frontend._dispatcher = type(
                "ImmediateDispatcher",
                (),
                {
                    "dispatch": lambda self, callback: (
                        callback(),
                        type("Result", (), {"__bool__": lambda self: True, "reason": ""})(),
                    )[1]
                },
            )()
            backend.frontend.broadcast = lambda message: messages.append(message)
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
                        "kind": "user_input",
                        "response_kind": "answer",
                        "answer": "continue",
                        "selected_option_text": "Continue",
                    },
                )
            )
        self.assertEqual(response["status"], "resolved")
        resolved_events = [
            message
            for message in messages
            if message.get("type") == "session_event"
            and message.get("data", {}).get("event_kind") == "interaction.resolved"
        ]
        self.assertEqual(len(resolved_events), 1)
        event = resolved_events[0]["data"]
        self.assertEqual(event["session_id"], "sess-1")
        self.assertGreater(event["seq"], 0)
        self.assertTrue(event["event_id"])
        self.assertTrue(event["created_at"])
        self.assertEqual(event["payload"]["interaction_id"], "int-1")
        self.assertEqual(event["payload"]["kind"], "user_input")
        self.assertEqual(event["payload"]["answer"], "continue")
        self.assertEqual(event["payload"]["selected_option_text"], "Continue")

    def test_session_events_route_is_not_registered(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_FakeCoreWithTimeline(), static_dir=static_dir)
            matching_routes = []
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/events" and "GET" in getattr(
                    item, "methods", set()
                ):
                    matching_routes.append(item)
            self.assertEqual(matching_routes, [])

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

    def test_bootstrap_snapshot_preserves_agent_diagnostics(self):
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
        snapshot = payload["snapshot"]
        self.assertEqual(snapshot["compact_summary_text"], "summary kept for diagnostics")
        self.assertEqual(snapshot["context_analysis"], {"approx_tokens": 1200})
        self.assertEqual(snapshot["workspace_intelligence"][0]["path"], "main.c")
        self.assertEqual(snapshot["context_pipeline_steps"], ["assemble", "compact"])
        self.assertEqual(snapshot["last_transition_display_reason"], "cancelled")
        self.assertEqual(snapshot["recent_transition_reasons"], ["permission_wait", "aborted"])
        self.assertEqual(snapshot["recent_transitions"][0]["reason"], "aborted")
        self.assertEqual(snapshot["compact_retry_count"], 2)
        self.assertEqual(snapshot["restore_consumed_event_count"], 7)
        self.assertEqual(snapshot["restore_transcript_event_count"], 8)
        self.assertEqual(snapshot["operation_diagnostics"], {"active_operations": 0})
        self.assertEqual(snapshot["runtime_config"]["resource_revision"]["revision"], 3)
        self.assertEqual(snapshot["compaction_state"]["latest_boundary_id"], "cb-1")
        self.assertEqual(snapshot["recovery_state"]["latest_marker_id"], "rm-1")

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

    def test_preview_routes_open_probe_refresh_external_and_close_local_session(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")

            def probe(url, timeout_sec):
                return {
                    "reachable": True,
                    "status_code": 204,
                    "title": "Local App",
                    "error": "",
                }

            opened = []
            service = PreviewService(
                workspace_root=static_dir,
                probe_runner=probe,
                external_opener=lambda url: opened.append(url) or True,
            )
            backend = GUIBackend(_FakeCore(), static_dir=static_dir, preview_service=service)

            open_route = self._route(
                backend,
                "/api/sessions/{session_id}/preview/open",
                "POST",
            )
            list_route = self._route(
                backend,
                "/api/sessions/{session_id}/preview",
                "GET",
            )
            refresh_route = self._route(
                backend,
                "/api/sessions/{session_id}/preview/{tab_id}/refresh",
                "POST",
            )
            external_route = self._route(
                backend,
                "/api/app/preview/open-external",
                "POST",
            )
            close_route = self._route(
                backend,
                "/api/sessions/{session_id}/preview/{tab_id}/close",
                "POST",
            )

            for route in (open_route, list_route, refresh_route, external_route, close_route):
                self.assertIsNotNone(route)

            opened_payload = asyncio.run(open_route.endpoint("sess-1", {"url": "localhost:5173"}))
            tab = opened_payload["preview"]
            listed_payload = asyncio.run(list_route.endpoint("sess-1"))
            refreshed_payload = asyncio.run(refresh_route.endpoint("sess-1", tab["tab_id"]))
            external_payload = asyncio.run(
                external_route.endpoint({"url": "http://localhost:5173"})
            )
            closed_payload = asyncio.run(close_route.endpoint("sess-1", tab["tab_id"]))

        self.assertEqual(tab["thread_id"], "sess-1")
        self.assertEqual(tab["url"], "http://localhost:5173")
        self.assertEqual(tab["status"], "success")
        self.assertEqual(tab["title"], "Local App")
        self.assertEqual(tab["can_go_back"], False)
        self.assertEqual(tab["can_go_forward"], False)
        self.assertEqual(listed_payload["preview"]["active_tab_id"], tab["tab_id"])
        self.assertEqual(refreshed_payload["preview"]["status"], "success")
        self.assertEqual(external_payload["opened"], True)
        self.assertEqual(opened, ["http://localhost:5173"])
        self.assertEqual(closed_payload["preview"]["status"], "closed")

    def test_preview_route_rejects_remote_urls_before_opening_network(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            probe_calls = []
            service = PreviewService(
                workspace_root=static_dir,
                probe_runner=lambda url, timeout_sec: probe_calls.append(url),
            )
            backend = GUIBackend(_FakeCore(), static_dir=static_dir, preview_service=service)
            route = self._route(
                backend,
                "/api/sessions/{session_id}/preview/open",
                "POST",
            )
            self.assertIsNotNone(route)
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint("sess-1", {"url": "https://example.com"}))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail, "preview_url_not_local")
        self.assertEqual(probe_calls, [])

    def test_file_write_route_is_disabled_until_manual_editor_contract(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _FileWriteCore()
            backend = GUIBackend(core, static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/files/{path:path}" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint("README.md", {"content": "changed"}))
        self.assertEqual(raised.exception.status_code, 405)
        self.assertEqual(raised.exception.detail, "file_write_disabled")
        self.assertEqual(core.write_calls, [])

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
        self.assertNotIn("timeline" + "_replay_status", payload)
        self.assertEqual(payload["restore_stop_reason"], "transcript_missing")
        self.assertEqual(payload["current_phase"], "implement")
        self.assertEqual(payload["discipline_profile"], "lite_spec_tdd")
        self.assertEqual(payload["task_items"][0]["content"], "build:implement")


if __name__ == "__main__":
    unittest.main()
