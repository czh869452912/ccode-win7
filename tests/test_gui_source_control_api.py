import asyncio
import os
import sys
import tempfile
import unittest

from embedagent_protocol import ShellDescriptor
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.app_host import GUIAppHost
from embedagent.frontend.gui.backend.server import GUIBackend as _GUIBackend
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry


def GUIBackend(*args, **kwargs):
    kwargs.setdefault(
        "shell_compiler",
        lambda application_id, capabilities: ShellDescriptor(schema_version=1),
    )
    return _GUIBackend(*args, **kwargs)


def route(app, path, method):
    for item in app.routes:
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
            return item
    raise AssertionError("route not found: %s %s" % (method, path))


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


class FakeSourceControlService(object):
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append(("status",))
        return {
            "workspace_root": "D:/workspace",
            "git_available": True,
            "is_repo": True,
            "branch": "main",
            "files": [],
            "counts": {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0, "total": 0},
        }

    def diff(self, path, scope="unstaged"):
        self.calls.append(("diff", path, scope))
        return {
            "workspace_root": "D:/workspace",
            "path": path,
            "scope": scope,
            "available": True,
            "binary": False,
            "diff": "diff --git a/%s b/%s\n" % (path, path),
            "file_count": 1,
            "line_count": 1,
            "truncated": False,
            "reason": "",
        }


class GuiSourceControlApiTests(unittest.TestCase):
    def make_backend(self, workspace, service):
        static_dir = os.path.join(workspace, "static")
        os.mkdir(static_dir)
        with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
            handle.write("<html><body>ok</body></html>")
        registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
        host = GUIAppHost(core_factory=lambda path: FakeCore(path), registry=registry)
        backend = GUIBackend(
            app_host=host,
            static_dir=static_dir,
            source_control_service=service,
        )
        backend.app_shell.open_workspace_path(workspace)
        return backend

    def test_routes_call_source_control_service(self):
        with tempfile.TemporaryDirectory() as workspace:
            service = FakeSourceControlService()
            backend = self.make_backend(workspace, service)

            status = asyncio.run(
                route(backend.app, "/api/app/source-control/status", "GET").endpoint()
            )
            self.assertEqual(status["source_control"]["branch"], "main")

            refreshed = asyncio.run(
                route(backend.app, "/api/app/source-control/refresh", "POST").endpoint()
            )
            self.assertEqual(refreshed["source_control"]["is_repo"], True)

            diff = asyncio.run(
                route(backend.app, "/api/app/source-control/diff", "GET").endpoint(
                    path="src/main.c",
                    scope="staged",
                )
            )
            self.assertEqual(diff["diff"]["path"], "src/main.c")
            self.assertIn(("diff", "src/main.c", "staged"), service.calls)

    def test_routes_require_active_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            static_dir = os.path.join(workspace, "static")
            os.mkdir(static_dir)
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
            host = GUIAppHost(core_factory=lambda path: FakeCore(path), registry=registry)
            backend = GUIBackend(
                app_host=host,
                static_dir=static_dir,
                source_control_service=FakeSourceControlService(),
            )

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route(backend.app, "/api/app/source-control/status", "GET").endpoint())

            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(raised.exception.detail, "no_active_workspace")

    def test_error_mapping_for_invalid_diff(self):
        class FailingService(FakeSourceControlService):
            def diff(self, path, scope="unstaged"):
                raise ValueError("invalid_diff_scope")

        with tempfile.TemporaryDirectory() as workspace:
            backend = self.make_backend(workspace, FailingService())

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    route(backend.app, "/api/app/source-control/diff", "GET").endpoint(
                        path="src/main.c",
                        scope="remote",
                    )
                )

            self.assertEqual(raised.exception.status_code, 422)
            self.assertEqual(raised.exception.detail, "invalid_diff_scope")


if __name__ == "__main__":
    unittest.main()
