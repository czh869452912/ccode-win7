import asyncio
import os
import sys
import tempfile
import unittest

from embedagent_protocol import ShellDescriptor
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.preview_service import PreviewService
from embedagent.frontend.gui.backend.server import GUIBackend as _GUIBackend


def GUIBackend(*args, **kwargs):
    kwargs.setdefault(
        "shell_compiler",
        lambda application_id, capabilities: ShellDescriptor(schema_version=1),
    )
    return _GUIBackend(*args, **kwargs)


class _FakeCore(object):
    def __init__(self):
        self.frontend = None
        self.respond_calls = []
        self.remember_calls = []

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def cancel_session(self, session_id):
        return {
            "session_id": session_id,
            "status": "idle",
            "current_mode": "build",
            "pending_interaction": None,
            "pending_interaction_valid": False,
        }

    def respond_to_interaction(self, session_id, interaction_id, payload):
        self.respond_calls.append((session_id, interaction_id, payload))
        return {
            "session_id": session_id,
            "interaction_id": interaction_id,
            "status": "resolved",
        }

    def remember_permission_category(self, session_id, category):
        self.remember_calls.append((session_id, category))
        return {
            "session_id": session_id,
            "status": "idle",
            "pending_interaction": None,
            "pending_interaction_valid": False,
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


class _AcceptedInteractionCore(_FakeCore):
    def respond_to_interaction(self, session_id, interaction_id, payload):
        self.respond_calls.append((session_id, interaction_id, payload))
        return {
            "session_id": session_id,
            "interaction_id": interaction_id,
            "status": "accepted",
            "snapshot": None,
        }


class _FakeCoreWithTimeline(_FakeCore):
    def get_session_capabilities(self):
        return {
            "commands": [
                {
                    "name": "help",
                    "usage": "/help",
                    "summary": "Show commands",
                    "source_type": "builtin",
                    "source_id": "slash_commands",
                    "active": True,
                }
            ]
        }

    def get_session_bootstrap(self, session_id):
        return {
            "snapshot": {
                "session_id": session_id,
                "status": "idle",
                "current_mode": "build",
                "created_at": "2026-04-04T00:00:00Z",
                "updated_at": "2026-04-04T00:00:00Z",
                "workflow_state": {
                    "workflow": {
                        "id": "c_harness",
                        "label": "C Harness",
                        "state": "active",
                        "summary": "in_progress build:implement",
                        "activity": "build harness active (implement)",
                        "items": [
                            {
                                "id": 1,
                                "content": "build:implement",
                                "status": "in_progress",
                                "done": False,
                            }
                        ],
                        "metadata": {
                            "current_phase": "implement",
                            "discipline_profile": "lite_spec_tdd",
                        },
                    }
                },
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
                "turn_experience": {
                    "status": "blocked",
                    "completed": [{"kind": "file_created", "path": "README.md"}],
                    "next_steps": ["Run validation for the changed files."],
                },
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
            "capabilities": self.get_session_capabilities(),
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
                "workflow_state": {
                    "workflow": {
                        "id": "c_harness",
                        "label": "C Harness",
                        "state": "active",
                        "summary": "in_progress build:implement",
                        "activity": "build harness active (implement)",
                        "items": [
                            {
                                "id": 1,
                                "content": "build:implement",
                                "status": "in_progress",
                                "done": False,
                            }
                        ],
                        "metadata": {
                            "current_phase": "implement",
                            "discipline_profile": "lite_spec_tdd",
                        },
                    }
                },
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
            },
        )()


class _SnapshotInteractionCore(_SnapshotCore):
    def respond_to_interaction(self, session_id, interaction_id, payload):
        self.respond_calls.append((session_id, interaction_id, payload))
        return self.get_session_snapshot(session_id)


class TestGuiBackendApi(unittest.TestCase):
    def _route(self, backend, path, method):
        for item in backend.app.routes:
            if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
                return item
        return None

    def test_create_session_without_query_leaves_mode_to_core_default(self):
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
        self.assertEqual(core.create_modes, [""])
        self.assertEqual(payload["current_mode"], "")

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

    def test_cancel_session_route_returns_core_snapshot(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _FakeCore()
            backend = GUIBackend(core, static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/cancel" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            payload = asyncio.run(route.endpoint("sess-1"))

        self.assertEqual(payload["session_id"], "sess-1")
        self.assertEqual(payload["status"], "idle")
        self.assertFalse(payload["pending_interaction_valid"])

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
            core = _FakeCore()
            backend = GUIBackend(core, static_dir=static_dir)
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
                        "decision": "accept",
                    },
                )
            )
        self.assertEqual(response["interaction_id"], "int-1")
        self.assertEqual(response["status"], "resolved")
        self.assertIsNone(response["snapshot"])
        self.assertEqual(core.respond_calls, [("sess-1", "int-1", {"decision": "accept"})])

    def test_post_interaction_response_preserves_accepted_without_snapshot(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_AcceptedInteractionCore(), static_dir=static_dir)
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
            response = asyncio.run(route.endpoint("sess-1", "int-accepted", {"decision": "accept"}))

        self.assertEqual(response["session_id"], "sess-1")
        self.assertEqual(response["interaction_id"], "int-accepted")
        self.assertEqual(response["status"], "accepted")
        self.assertIsNone(response["snapshot"])

    def test_post_interaction_response_routes_frontend_pending_input_through_core(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _SnapshotCore("")
            backend = GUIBackend(core, static_dir=static_dir)
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
                        "answers": {"answer": "继续"},
                    },
                )
            )
        self.assertEqual(len(core.respond_calls), 1)
        self.assertEqual(core.respond_calls[0][0], "sess-1")
        self.assertEqual(core.respond_calls[0][1], "int-1")
        self.assertEqual(core.respond_calls[0][2], {"answers": {"answer": "继续"}})
        self.assertEqual(response["interaction_id"], "int-1")
        self.assertEqual(response["status"], "resolved")

    def test_post_interaction_response_routes_frontend_pending_permission_through_core(
        self,
    ):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _SnapshotCore("")
            backend = GUIBackend(core, static_dir=static_dir)
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
                        "decision": "accept",
                    },
                )
            )
        self.assertEqual(len(core.respond_calls), 1)
        self.assertEqual(core.respond_calls[0][0], "sess-1")
        self.assertEqual(core.respond_calls[0][1], "perm-1")
        self.assertEqual(core.respond_calls[0][2], {"decision": "accept"})
        self.assertEqual(response["interaction_id"], "perm-1")
        self.assertEqual(response["status"], "resolved")

    def test_post_interaction_response_does_not_own_permission_remember_side_effect(
        self,
    ):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _FakeCore()
            backend = GUIBackend(core, static_dir=static_dir)
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
                        "decision": "acceptForSession",
                    },
                )
            )

        self.assertEqual(response["interaction_id"], "perm-1")
        self.assertEqual(len(core.respond_calls), 1)
        self.assertEqual(core.respond_calls[0][2], {"decision": "acceptForSession"})
        self.assertEqual(core.remember_calls, [])

    def test_post_interaction_response_wraps_core_snapshot_response(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _SnapshotInteractionCore("")
            backend = GUIBackend(core, static_dir=static_dir)
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
                    {"answers": {"answer": "continue"}},
                )
            )

        self.assertEqual(
            core.respond_calls, [("sess-1", "int-1", {"answers": {"answer": "continue"}})]
        )
        self.assertEqual(response["session_id"], "sess-1")
        self.assertEqual(response["interaction_id"], "int-1")
        self.assertEqual(response["status"], "resolved")
        self.assertEqual(response["snapshot"]["session_id"], "sess-1")
        self.assertEqual(response["snapshot"]["status"], "idle")
        self.assertFalse(response["snapshot"]["pending_interaction_valid"])

    def test_post_interaction_response_maps_lifecycle_errors(self):
        cases = (
            ("interaction_expired", 410, "interaction_expired"),
            ("interaction_conflict", 409, "interaction_conflict"),
            ("invalid_interaction_response", 422, "invalid_interaction_response"),
        )
        for error_text, expected_status, expected_detail in cases:
            with self.subTest(error_text=error_text):
                with tempfile.TemporaryDirectory() as static_dir:
                    with open(
                        os.path.join(static_dir, "index.html"), "w", encoding="utf-8"
                    ) as handle:
                        handle.write("<html><body>ok</body></html>")
                    backend = GUIBackend(_ErrorCore(error_text), static_dir=static_dir)
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
                        asyncio.run(route.endpoint("sess-1", "int-1", {"decision": "accept"}))
                self.assertEqual(raised.exception.status_code, expected_status)
                self.assertEqual(raised.exception.detail, expected_detail)

    def test_post_interaction_response_emits_backend_owned_resolved_event(self):
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
                        "answers": {"answer": "continue"},
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
        self.assertEqual(resolved_events, [])

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
        self.assertEqual(
            set(payload),
            {
                "schema_version",
                "event_cursor",
                "thread",
                "snapshot",
                "history",
                "capabilities",
                "plan",
                "permission_context",
            },
        )
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["capabilities"]["schema_version"], 1)
        self.assertNotIn("turns", payload["history"])
        self.assertEqual(payload["capabilities"]["commands"][0]["label"], "/help")
        self.assertNotIn("protocol", payload)

    def test_session_capabilities_endpoint_returns_slash_commands(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_FakeCoreWithTimeline(), static_dir=static_dir)
            route = self._route(backend, "/api/sessions/capabilities", "GET")
        self.assertIsNotNone(route)
        payload = asyncio.run(route.endpoint())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["commands"][0]["label"], "/help")
        self.assertEqual(payload["modes"], [])
        self.assertEqual(payload["tools"], [])
        self.assertEqual(payload["empty_state"], {})
        self.assertNotIn("protocol", payload)

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
        self.assertEqual(snapshot["turn_experience"]["status"], "blocked")
        self.assertEqual(
            snapshot["turn_experience"]["completed"][0]["path"],
            "README.md",
        )

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
                asyncio.run(route.endpoint("sess-1", "int-1", {"decision": "accept"}))
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
        workflow = payload["workflow_state"]["workflow"]
        self.assertEqual(workflow["metadata"]["current_phase"], "implement")
        self.assertEqual(workflow["metadata"]["discipline_profile"], "lite_spec_tdd")
        self.assertEqual(workflow["items"][0]["content"], "build:implement")
        self.assertNotIn("current_phase", payload)
        self.assertNotIn("task_items", payload)


if __name__ == "__main__":
    unittest.main()
