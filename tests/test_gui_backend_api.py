from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
from embedagent_host.frontend_errors import FrontendPortError
from embedagent_protocol import (
    CapabilitySnapshot,
    FailureRecord,
    SessionBootstrap,
    ShellDescriptor,
    ThreadShell,
)
from fastapi import HTTPException

from embedagent.frontend.gui.backend.app_host import FrontendPortSet, SingleWorkspaceAppHost
from embedagent.frontend.gui.backend.server import GUIBackend


def _thread(session_id="session-1", mode="build"):
    return ThreadShell(
        id=session_id,
        title="Session",
        archived=False,
        current_mode=mode,
        status="idle",
        updated_at="2026-08-13T00:00:00Z",
    )


def _bootstrap(session_id="session-1", mode="build"):
    return SessionBootstrap(
        schema_version=2,
        event_cursor=4,
        thread=_thread(session_id, mode),
        snapshot={
            "session_id": session_id,
            "current_mode": mode,
            "status": "idle",
            "pending_interaction_valid": False,
        },
        activities=[{"kind": "assistant", "content": "Ready."}],
        capabilities=CapabilitySnapshot(),
        integrity={"status": "healthy"},
        plan={"title": "Plan"},
        permission_context={"session_id": session_id},
    )


class FakeSessionPort(object):
    def __init__(self):
        self.calls = []
        self.closed = False
        self.error = None

    def _raise(self):
        if self.error is not None:
            raise self.error

    def list_sessions(self, limit=10):
        self._raise()
        self.calls.append(("list", limit))
        return [_thread()]

    def get_session_capabilities(self, session_id=""):
        self._raise()
        self.calls.append(("capabilities", session_id))
        return CapabilitySnapshot()

    def get_session_bootstrap(self, reference, mode=""):
        self._raise()
        self.calls.append(("bootstrap", reference, mode))
        return _bootstrap(reference, mode or "build")

    def create_session(self, mode):
        self._raise()
        self.calls.append(("create", mode))
        return _bootstrap("session-new", mode)

    def resume_session(self, reference, mode):
        self._raise()
        self.calls.append(("resume", reference, mode))
        return _bootstrap(reference, mode or "restored")

    def submit_user_message(self, session_id, text, stream):
        self._raise()
        self.calls.append(("submit", session_id, text, stream))

    def cancel_session(self, session_id):
        self._raise()
        self.calls.append(("cancel", session_id))
        return _bootstrap(session_id)

    def set_session_mode(self, session_id, mode):
        self._raise()
        self.calls.append(("mode", session_id, mode))
        return _bootstrap(session_id, mode)

    def respond_to_interaction(self, session_id, interaction_id, payload):
        self._raise()
        self.calls.append(("respond", session_id, interaction_id, payload))
        return _bootstrap(session_id)

    def rename_session(self, session_id, title):
        self._raise()
        self.calls.append(("rename", session_id, title))
        return _thread(session_id)

    def archive_session(self, session_id):
        self._raise()
        self.calls.append(("archive", session_id))
        return ThreadShell(
            id=session_id,
            title="Session",
            archived=True,
            current_mode="build",
            status="idle",
            updated_at="2026-08-13T00:00:00Z",
        )

    def fork_session(self, session_id, title=""):
        self._raise()
        self.calls.append(("fork", session_id, title))
        return _thread("session-fork")

    def close(self):
        self.closed = True


class FakeWorkspacePort(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.calls = []

    def get_workspace_snapshot(self):
        self.calls.append(("snapshot",))
        return {"path": self.workspace}

    def list_workspace_tree(self, path=".", max_depth=3, limit=200):
        self.calls.append(("tree", path, max_depth, limit))
        return {"root": path, "items": [{"kind": "file", "path": "src/main.c"}]}

    def list_file_children(self, path=".", limit=200):
        self.calls.append(("children", path, limit))
        return [{"kind": "file", "path": "src/main.c"}]

    def read_file(self, path):
        self.calls.append(("read", path))
        return {"path": path, "content": "int main(void) {}"}

    def write_file(self, path, content):
        self.calls.append(("write", path, content))
        return {"path": path}

    def get_diff_preview(self, path, new_content):
        self.calls.append(("diff", path, new_content))
        return {
            "path": path,
            "old_content": "old",
            "new_content": new_content,
            "unified_diff": "diff",
        }

    def reload_resources(self, session_id="", reason="api"):
        self.calls.append(("reload", session_id, reason))
        return {"session_id": session_id, "reason": reason}


def _route(app, path, method):
    for item in app.routes:
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
            return item
    raise AssertionError("route not found: %s %s" % (method, path))


def _backend():
    static_dir = tempfile.mkdtemp()
    with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
        handle.write("<html><body>ok</body></html>")
    session = FakeSessionPort()
    workspace = FakeWorkspacePort(static_dir)
    ports = FrontendPortSet(session, workspace)
    backend = GUIBackend(
        static_dir=static_dir,
        app_host=SingleWorkspaceAppHost(ports),
        shell_compiler=lambda application_id, capabilities: ShellDescriptor(),
    )
    return backend, session, workspace


def test_session_routes_forward_strict_protocol_dtos_without_reshaping():
    backend, session, _workspace = _backend()

    listed = asyncio.run(_route(backend.app, "/api/sessions", "GET").endpoint(10))
    capabilities = asyncio.run(_route(backend.app, "/api/sessions/capabilities", "GET").endpoint())
    bootstrap = asyncio.run(
        _route(backend.app, "/api/sessions/{session_id}/bootstrap", "GET").endpoint("session-1")
    )
    created = asyncio.run(_route(backend.app, "/api/sessions", "POST").endpoint("debug"))
    resumed = asyncio.run(
        _route(backend.app, "/api/sessions/{session_id}/resume", "POST").endpoint("session-1", "")
    )

    assert listed == {"sessions": [_thread().to_dict()]}
    assert capabilities == CapabilitySnapshot().to_dict()
    assert bootstrap == _bootstrap().to_dict()
    assert created == _bootstrap("session-new", "debug").to_dict()
    assert resumed == _bootstrap("session-1", "restored").to_dict()
    assert ("bootstrap", "session-1", "") in session.calls


def test_session_mutations_call_only_the_focused_session_port():
    backend, session, _workspace = _backend()

    asyncio.run(
        _route(backend.app, "/api/sessions/{session_id}/message", "POST").endpoint(
            "session-1", {"text": "hi"}
        )
    )
    mode = asyncio.run(
        _route(backend.app, "/api/sessions/{session_id}/mode", "POST").endpoint(
            "session-1", {"mode": "verify"}
        )
    )
    interaction = asyncio.run(
        _route(
            backend.app,
            "/api/sessions/{session_id}/interactions/{interaction_id}/respond",
            "POST",
        ).endpoint("session-1", "interaction-1", {"decision": "accept"})
    )
    renamed = asyncio.run(
        _route(backend.app, "/api/sessions/{session_id}/rename", "POST").endpoint(
            "session-1", {"title": "Renamed"}
        )
    )
    archived = asyncio.run(
        _route(backend.app, "/api/sessions/{session_id}/archive", "POST").endpoint("session-1")
    )
    forked = asyncio.run(
        _route(backend.app, "/api/sessions/{session_id}/fork", "POST").endpoint(
            "session-1", {"title": "Copy"}
        )
    )

    assert ("submit", "session-1", "hi", True) in session.calls
    assert mode == _bootstrap("session-1", "verify").to_dict()
    assert interaction == _bootstrap("session-1").to_dict()
    assert renamed == _thread("session-1").to_dict()
    assert archived["archived"] is True
    assert forked == _thread("session-fork").to_dict()


def test_workspace_routes_call_only_the_focused_workspace_port():
    backend, _session, workspace = _backend()

    snapshot = asyncio.run(_route(backend.app, "/api/workspace", "GET").endpoint())
    tree = asyncio.run(_route(backend.app, "/api/files", "GET").endpoint("src", 2))
    children = asyncio.run(_route(backend.app, "/api/files/tree", "GET").endpoint("src", 20))
    file_payload = asyncio.run(
        _route(backend.app, "/api/files/{path:path}", "GET").endpoint("src/main.c")
    )
    diff = asyncio.run(
        _route(backend.app, "/api/diff", "POST").endpoint(
            {"path": "src/main.c", "new_content": "new"}
        )
    )
    reload = asyncio.run(
        _route(
            backend.app,
            "/api/sessions/{session_id}/resources/reload",
            "POST",
        ).endpoint("session-1")
    )

    assert snapshot == {"path": workspace.workspace}
    assert tree["root"] == "src"
    assert children == {"items": [{"kind": "file", "path": "src/main.c"}]}
    assert file_payload["path"] == "src/main.c"
    assert diff["unified_diff"] == "diff"
    assert reload == {"session_id": "session-1", "reason": "api"}


def test_structured_frontend_port_failure_maps_to_http_status():
    backend, session, _workspace = _backend()
    session.error = FrontendPortError(
        FailureRecord(
            code="session_not_found",
            message="missing",
            retryable=False,
            source="session",
        )
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            _route(backend.app, "/api/sessions/{session_id}/bootstrap", "GET").endpoint("missing")
        )

    assert raised.value.status_code == 404
    assert raised.value.detail["code"] == "session_not_found"
    assert raised.value.detail["safe_message"]


def test_file_write_route_remains_disabled():
    backend, _session, _workspace = _backend()

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            _route(backend.app, "/api/files/{path:path}", "POST").endpoint(
                "src/main.c", {"content": "new"}
            )
        )

    assert raised.value.status_code == 405
