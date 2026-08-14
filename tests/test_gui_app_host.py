from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from embedagent_protocol import CapabilitySnapshot, ShellDescriptor, ThreadShell
from fastapi import HTTPException

from embedagent.frontend.gui.backend.app_host import FrontendPortSet, GUIAppHost
from embedagent.frontend.gui.backend.server import GUIBackend
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry

ROOT = Path(__file__).resolve().parents[1]


class FakeSessionPort(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.closed = False

    def list_sessions(self, limit=10):
        return [
            ThreadShell(
                id="session-" + os.path.basename(self.workspace),
                title="Session",
                archived=False,
                current_mode="explore",
                status="idle",
                updated_at="2026-08-13T00:00:00Z",
            )
        ][:limit]

    def get_session_capabilities(self, session_id=""):
        del session_id
        return CapabilitySnapshot()

    def get_session_bootstrap(self, reference, mode=""):
        del reference, mode
        return None

    def close(self):
        self.closed = True


class FakeWorkspacePort(object):
    def __init__(self, workspace):
        self.workspace = workspace

    def get_workspace_snapshot(self):
        return {"path": self.workspace}


class RecordingSink(object):
    def on_session_event(self, envelope):
        del envelope


def _route(app, path, method):
    for item in app.routes:
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
            return item
    raise AssertionError("route not found: %s %s" % (method, path))


def _backend(registry, created):
    sink = RecordingSink()

    def factory(path, event_sink):
        if created:
            assert created[-1][0].session.closed is True
        ports = FrontendPortSet(FakeSessionPort(path), FakeWorkspacePort(path))
        created.append((ports, event_sink))
        return ports

    static_dir = tempfile.mkdtemp()
    with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
        handle.write("<html><body>ok</body></html>")
    host = GUIAppHost(
        port_factory=factory,
        event_sink=sink,
        registry=registry,
    )
    backend = GUIBackend(
        static_dir=static_dir,
        app_host=host,
        frontend=sink,
        shell_compiler=lambda application_id, capabilities: ShellDescriptor(),
        host_diagnostics={"host": {"platform": "test"}},
    )
    return backend, host, sink


def test_bootstrap_and_workspace_bound_route_without_active_workspace():
    with tempfile.TemporaryDirectory() as root:
        registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
        backend, host, _sink = _backend(registry, [])

        payload = asyncio.run(_route(backend.app, "/api/app/bootstrap", "GET").endpoint())
        with pytest.raises(HTTPException) as raised:
            asyncio.run(_route(backend.app, "/api/sessions", "GET").endpoint(10))

    assert payload["has_active_workspace"] is False
    assert payload["active_workspace"] is None
    assert payload["workspaces"] == []
    assert host.current_ports() is None
    assert raised.value.status_code == 409
    assert raised.value.detail == "no_active_workspace"


def test_open_workspace_constructs_focused_ports_with_bound_event_sink():
    with tempfile.TemporaryDirectory() as root:
        registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
        workspace = os.path.join(root, "project-a")
        os.mkdir(workspace)
        created = []
        backend, host, sink = _backend(registry, created)

        payload = asyncio.run(
            _route(backend.app, "/api/app/workspaces", "POST").endpoint({"path": workspace})
        )

    assert payload["active_workspace"]["path"] == os.path.realpath(workspace)
    assert payload["diagnostics"]["active_core"]["present"] is True
    assert len(created) == 1
    assert created[0][1] is sink
    assert host.current_ports() is created[0][0]


def test_workspace_switch_and_remove_close_the_previous_session_port():
    with tempfile.TemporaryDirectory() as root:
        registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
        first = os.path.join(root, "first")
        second = os.path.join(root, "second")
        os.mkdir(first)
        os.mkdir(second)
        created = []
        backend, host, _sink = _backend(registry, created)
        open_route = _route(backend.app, "/api/app/workspaces", "POST")

        asyncio.run(open_route.endpoint({"path": first}))
        second_payload = asyncio.run(open_route.endpoint({"path": second}))
        removed = asyncio.run(
            _route(backend.app, "/api/app/workspaces/{workspace_id}", "DELETE").endpoint(
                second_payload["active_workspace"]["id"]
            )
        )

    assert created[0][0].session.closed is True
    assert created[1][0].session.closed is True
    assert removed["removed"] is True
    assert host.current_ports() is None


def test_gui_backend_sources_have_no_retired_core_facade():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "src/embedagent/frontend/gui/backend/app_host.py",
            ROOT / "src/embedagent/frontend/gui/backend/app_shell.py",
            ROOT / "src/embedagent/frontend/gui/backend/routes_sessions.py",
            ROOT / "src/embedagent/frontend/gui/backend/server.py",
            ROOT / "src/embedagent/frontend/gui/launcher.py",
        )
    )
    for forbidden in (
        "session_host",
        ".adapter",
        "require_core",
    ):
        assert forbidden not in sources
