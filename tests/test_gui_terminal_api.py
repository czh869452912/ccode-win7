import asyncio
import os
import sys
import tempfile
import unittest

from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.app_host import GUIAppHost
from embedagent.frontend.gui.backend.server import GUIBackend
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry


def route(app, path, method):
    for item in app.routes:
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
            return item
    raise AssertionError("route not found: %s %s" % (method, path))


class FakeFrontend(object):
    def __init__(self):
        self.messages = []

    def _dispatch_message(self, message):
        self.messages.append(message)
        return True


class FakeCore(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.frontend = None

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def list_sessions(self, limit=10):
        return []

    def get_workspace_snapshot(self):
        return {"path": self.workspace}


class FakeTerminalService(object):
    def __init__(self):
        self.calls = []
        self.sink = None

    def set_event_sink(self, sink):
        self.sink = sink

    def list_sessions(self, session_id=None):
        self.calls.append(("list", session_id))
        return [
            {
                "session_id": session_id or "sess-1",
                "terminal_id": "term-1",
                "cwd": "D:/workspace",
                "status": "running",
                "pid": 123,
                "exit_code": None,
                "label": "Terminal 1",
                "updated_at": "2026-06-17T00:00:00Z",
                "capabilities": {"stdin": True, "resize": False, "pty": False},
            }
        ]

    def open_or_attach(self, session_id, terminal_id, cwd="", cols=80, rows=24):
        self.calls.append(("open", session_id, terminal_id, cwd, cols, rows))
        event = {
            "type": "output",
            "session_id": session_id,
            "terminal_id": terminal_id,
            "sequence": 1,
            "chunk": "hello\n",
        }
        if self.sink is not None:
            self.sink(event)
        return {
            "session_id": session_id,
            "terminal_id": terminal_id,
            "cwd": "D:/workspace",
            "status": "running",
            "pid": 123,
            "history": "",
            "exit_code": None,
            "label": "Terminal 1",
            "updated_at": "2026-06-17T00:00:00Z",
            "sequence": 0,
            "cols": cols,
            "rows": rows,
            "capabilities": {"stdin": True, "resize": False, "pty": False},
        }

    def snapshot(self, session_id, terminal_id):
        self.calls.append(("snapshot", session_id, terminal_id))
        return {
            "session_id": session_id,
            "terminal_id": terminal_id,
            "history": "hello\n",
            "status": "running",
            "capabilities": {"stdin": True, "resize": False, "pty": False},
        }

    def write(self, session_id, terminal_id, data):
        self.calls.append(("write", session_id, terminal_id, data))
        return {"session_id": session_id, "terminal_id": terminal_id, "status": "running"}

    def clear(self, session_id, terminal_id):
        self.calls.append(("clear", session_id, terminal_id))
        return {"session_id": session_id, "terminal_id": terminal_id, "history": ""}

    def restart(self, session_id, terminal_id, cwd="", cols=80, rows=24):
        self.calls.append(("restart", session_id, terminal_id, cwd, cols, rows))
        return self.open_or_attach(session_id, terminal_id, cwd=cwd, cols=cols, rows=rows)

    def resize(self, session_id, terminal_id, cols, rows):
        self.calls.append(("resize", session_id, terminal_id, cols, rows))
        return {"cols": cols, "rows": rows, "capabilities": {"resize": False, "pty": False}}

    def close(self, session_id, terminal_id=""):
        self.calls.append(("close", session_id, terminal_id))
        return {"session_id": session_id, "terminal_id": terminal_id, "status": "closed"}

    def shutdown(self):
        self.calls.append(("shutdown",))


class GuiTerminalApiTests(unittest.TestCase):
    def make_backend(self, workspace, terminal_service):
        def factory(path):
            return FakeCore(path)

        static_dir = os.path.join(workspace, "static")
        os.mkdir(static_dir)
        with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
            handle.write("<html><body>ok</body></html>")
        registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
        host = GUIAppHost(core_factory=factory, registry=registry)
        backend = GUIBackend(
            app_host=host,
            static_dir=static_dir,
            terminal_service=terminal_service,
        )
        frontend = FakeFrontend()
        backend.frontend._dispatch_message = frontend._dispatch_message
        backend.app_shell.open_workspace_path(workspace)
        return backend, frontend

    def test_terminal_routes_call_service_and_broadcast_events(self):
        with tempfile.TemporaryDirectory() as workspace:
            terminal = FakeTerminalService()
            backend, frontend = self.make_backend(workspace, terminal)

            opened = asyncio.run(
                route(
                    backend.app,
                    "/api/sessions/{session_id}/terminals/{terminal_id}/open",
                    "POST",
                ).endpoint("sess-1", "term-1", {"cwd": "", "cols": 100, "rows": 30})
            )
            self.assertEqual(opened["terminal"]["terminal_id"], "term-1")
            self.assertEqual(opened["terminal"]["capabilities"]["pty"], False)

            listed = asyncio.run(
                route(backend.app, "/api/sessions/{session_id}/terminals", "GET").endpoint("sess-1")
            )
            self.assertEqual(listed["terminals"][0]["terminal_id"], "term-1")

            snapshot = asyncio.run(
                route(
                    backend.app,
                    "/api/sessions/{session_id}/terminals/{terminal_id}/snapshot",
                    "GET",
                ).endpoint("sess-1", "term-1")
            )
            self.assertEqual(snapshot["terminal"]["history"], "hello\n")

            written = asyncio.run(
                route(
                    backend.app,
                    "/api/sessions/{session_id}/terminals/{terminal_id}/write",
                    "POST",
                ).endpoint("sess-1", "term-1", {"data": "echo hi\n"})
            )
            self.assertEqual(written["terminal"]["status"], "running")

            cleared = asyncio.run(
                route(
                    backend.app,
                    "/api/sessions/{session_id}/terminals/{terminal_id}/clear",
                    "POST",
                ).endpoint("sess-1", "term-1")
            )
            self.assertEqual(cleared["terminal"]["history"], "")

            resized = asyncio.run(
                route(
                    backend.app,
                    "/api/sessions/{session_id}/terminals/{terminal_id}/resize",
                    "POST",
                ).endpoint("sess-1", "term-1", {"cols": 120, "rows": 40})
            )
            self.assertEqual(resized["terminal"]["cols"], 120)

            restarted = asyncio.run(
                route(
                    backend.app,
                    "/api/sessions/{session_id}/terminals/{terminal_id}/restart",
                    "POST",
                ).endpoint("sess-1", "term-1", {"cwd": "", "cols": 90, "rows": 25})
            )
            self.assertEqual(restarted["terminal"]["rows"], 25)

            closed = asyncio.run(
                route(
                    backend.app,
                    "/api/sessions/{session_id}/terminals/{terminal_id}/close",
                    "POST",
                ).endpoint("sess-1", "term-1")
            )
            self.assertEqual(closed["terminal"]["status"], "closed")
            self.assertTrue(
                any(message["type"] == "terminal_event" for message in frontend.messages)
            )
            self.assertIn(("write", "sess-1", "term-1", "echo hi\n"), terminal.calls)
            self.assertIn(("close", "sess-1", "term-1"), terminal.calls)

    def test_terminal_routes_require_active_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            static_dir = os.path.join(workspace, "static")
            os.mkdir(static_dir)
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            terminal = FakeTerminalService()
            registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
            host = GUIAppHost(core_factory=lambda path: FakeCore(path), registry=registry)
            backend = GUIBackend(
                app_host=host,
                static_dir=static_dir,
                terminal_service=terminal,
            )

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    route(
                        backend.app,
                        "/api/sessions/{session_id}/terminals/{terminal_id}/open",
                        "POST",
                    ).endpoint("sess-1", "term-1", {})
                )

            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(raised.exception.detail, "no_active_workspace")

    def test_terminal_value_errors_map_to_http_status(self):
        class ErrorTerminal(FakeTerminalService):
            def open_or_attach(self, *args, **kwargs):
                raise ValueError("terminal_cwd_outside_workspace")

            def write(self, *args, **kwargs):
                raise ValueError("terminal_not_found")

        with tempfile.TemporaryDirectory() as workspace:
            backend, _frontend = self.make_backend(workspace, ErrorTerminal())

            with self.assertRaises(HTTPException) as bad_cwd:
                asyncio.run(
                    route(
                        backend.app,
                        "/api/sessions/{session_id}/terminals/{terminal_id}/open",
                        "POST",
                    ).endpoint("sess-1", "term-1", {})
                )
            with self.assertRaises(HTTPException) as missing:
                asyncio.run(
                    route(
                        backend.app,
                        "/api/sessions/{session_id}/terminals/{terminal_id}/write",
                        "POST",
                    ).endpoint("sess-1", "term-1", {"data": "x"})
                )

            self.assertEqual(bad_cwd.exception.status_code, 422)
            self.assertEqual(missing.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
