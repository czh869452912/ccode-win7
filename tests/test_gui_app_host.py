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


class _FakeCore(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.frontend = None
        self.shutdown_calls = 0

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        self.shutdown_calls += 1

    def list_sessions(self, limit=10):
        return [
            {
                "session_id": "sess-" + os.path.basename(self.workspace),
                "current_mode": "explore",
                "updated_at": "2026-06-15T10:00:00Z",
            }
        ]

    def get_workspace_snapshot(self):
        return {"path": self.workspace}


def _route(app, path, method):
    for item in app.routes:
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
            return item
    raise AssertionError("route not found: %s %s" % (method, path))


class TestGuiAppHost(unittest.TestCase):
    def _backend(self, registry, created):
        def factory(path):
            core = _FakeCore(path)
            created.append(core)
            return core

        static_dir = tempfile.mkdtemp()
        with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
            handle.write("<html><body>ok</body></html>")
        host = GUIAppHost(core_factory=factory, registry=registry)
        backend = GUIBackend(core=None, static_dir=static_dir, app_host=host)
        return backend, host

    def test_bootstrap_without_active_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            created = []
            backend, host = self._backend(registry, created)
            route = _route(backend.app, "/api/app/bootstrap", "GET")

            payload = asyncio.run(route.endpoint())

        self.assertEqual(payload["has_active_workspace"], False)
        self.assertEqual(payload["active_workspace"], None)
        self.assertEqual(payload["workspaces"], [])
        self.assertEqual(created, [])
        self.assertIs(host.current_core(), None)

    def test_workspace_bound_route_returns_409_without_active_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            backend, host = self._backend(registry, [])
            route = _route(backend.app, "/api/sessions", "GET")

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint(10))

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "no_active_workspace")
        self.assertIs(host.current_core(), None)

    def test_open_workspace_activates_core_and_registers_frontend(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            backend, host = self._backend(registry, created)
            route = _route(backend.app, "/api/app/workspaces", "POST")

            payload = asyncio.run(route.endpoint({"path": workspace}))

        self.assertEqual(payload["active_workspace"]["path"], os.path.realpath(workspace))
        self.assertEqual(len(created), 1)
        self.assertIs(created[0].frontend, backend.frontend)
        self.assertIs(host.current_core(), created[0])

    def test_activating_second_workspace_shuts_down_first_core(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            first = os.path.join(root, "first")
            second = os.path.join(root, "second")
            os.mkdir(first)
            os.mkdir(second)
            created = []
            backend, host = self._backend(registry, created)
            open_route = _route(backend.app, "/api/app/workspaces", "POST")

            asyncio.run(open_route.endpoint({"path": first}))
            asyncio.run(open_route.endpoint({"path": second}))

        self.assertEqual(len(created), 2)
        self.assertEqual(created[0].shutdown_calls, 1)
        self.assertEqual(created[1].shutdown_calls, 0)
        self.assertIs(host.current_core(), created[1])

    def test_remove_workspace_only_updates_registry(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            backend, host = self._backend(registry, created)
            open_route = _route(backend.app, "/api/app/workspaces", "POST")
            delete_route = _route(backend.app, "/api/app/workspaces/{workspace_id}", "DELETE")
            opened = asyncio.run(open_route.endpoint({"path": workspace}))

            payload = asyncio.run(delete_route.endpoint(opened["active_workspace"]["id"]))

            self.assertEqual(payload["removed"], True)
            self.assertEqual(payload["workspaces"], [])
            self.assertTrue(os.path.isdir(workspace))
            self.assertEqual(created[0].shutdown_calls, 1)
            self.assertIs(host.current_core(), None)


if __name__ == "__main__":
    unittest.main()
