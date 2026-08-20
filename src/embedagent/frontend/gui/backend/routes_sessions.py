from __future__ import annotations

from typing import Any, Dict

from embedagent_protocol import CapabilitySnapshot, SessionBootstrap, ThreadShell
from fastapi import HTTPException


def _bootstrap(value: Any) -> SessionBootstrap:
    if not isinstance(value, SessionBootstrap):
        raise TypeError("session port must return a SessionBootstrap")
    return value


def _thread(value: Any) -> ThreadShell:
    if not isinstance(value, ThreadShell):
        raise TypeError("session port must return a ThreadShell")
    return value


def register_session_routes(app: Any, backend: Any) -> None:
    @app.get("/api/sessions")
    async def list_sessions(limit: int = 10):
        session = backend._require_session_port()
        threads = backend._call_port(session.list_sessions, limit)
        return {"sessions": [_thread(item).to_dict() for item in threads]}

    @app.get("/api/sessions/capabilities")
    async def get_session_capabilities():
        session = backend._require_session_port()
        capabilities = backend._call_port(session.get_session_capabilities, "")
        if not isinstance(capabilities, CapabilitySnapshot):
            raise TypeError("session port must return a CapabilitySnapshot")
        return capabilities.to_dict()

    @app.get("/api/sessions/{session_id}/bootstrap")
    async def get_session_bootstrap(session_id: str):
        session = backend._require_session_port()
        value = backend._call_port(session.get_session_bootstrap, session_id, "")
        return _bootstrap(value).to_dict()

    @app.post("/api/sessions")
    async def create_session(mode: str = ""):
        session = backend._require_session_port()
        value = _bootstrap(backend._call_port(session.create_session, mode))
        backend._current_session_id = value.thread.id
        return value.to_dict()

    @app.post("/api/sessions/{session_id}/resume")
    async def resume_session(session_id: str, mode: str = ""):
        session = backend._require_session_port()
        value = _bootstrap(backend._call_port(session.resume_session, session_id, mode))
        backend._current_session_id = value.thread.id
        return value.to_dict()

    @app.post("/api/sessions/{session_id}/rename")
    async def rename_session(session_id: str, request: Dict[str, Any]):
        session = backend._require_session_port()
        value = backend._call_port(
            session.rename_session,
            session_id,
            str(request.get("title") or ""),
        )
        return _thread(value).to_dict()

    @app.post("/api/sessions/{session_id}/archive")
    async def archive_session(session_id: str):
        session = backend._require_session_port()
        value = backend._call_port(session.archive_session, session_id)
        return _thread(value).to_dict()

    @app.post("/api/sessions/{session_id}/fork")
    async def fork_session(session_id: str, request: Dict[str, Any]):
        session = backend._require_session_port()
        value = backend._call_port(
            session.fork_session,
            session_id,
            str(request.get("title") or ""),
        )
        return _thread(value).to_dict()

    @app.post("/api/sessions/{session_id}/message")
    async def send_message(session_id: str, request: Dict[str, Any]):
        backend._current_session_id = session_id
        session = backend._require_session_port()
        backend._call_port(
            session.submit_user_message,
            session_id,
            str(request.get("text") or ""),
            True,
        )
        return {"status": "submitted"}

    @app.post("/api/sessions/{session_id}/cancel")
    async def cancel_session(session_id: str):
        session = backend._require_session_port()
        value = backend._call_port(session.cancel_session, session_id)
        return _bootstrap(value).to_dict()

    @app.post("/api/sessions/{session_id}/mode")
    async def set_mode(session_id: str, request: Dict[str, Any]):
        session = backend._require_session_port()
        value = backend._call_port(
            session.set_session_mode,
            session_id,
            str(request.get("mode") or ""),
        )
        return _bootstrap(value).to_dict()

    @app.post("/api/sessions/{session_id}/interactions/{interaction_id}/respond")
    async def respond_to_interaction(session_id: str, interaction_id: str, request: Dict[str, Any]):
        backend._current_session_id = session_id
        session = backend._require_session_port()
        value = backend._call_port(
            session.respond_to_interaction,
            session_id,
            interaction_id,
            request,
        )
        return _bootstrap(value).to_dict()

    @app.get("/api/workspace")
    async def get_workspace():
        workspace = backend._require_workspace_port()
        return backend._call_port(workspace.get_workspace_snapshot)

    @app.post("/api/sessions/{session_id}/resources/reload")
    async def reload_session_resources(session_id: str):
        workspace = backend._require_workspace_port()
        return backend._call_port(workspace.reload_resources, session_id, reason="api")

    @app.get("/api/files")
    async def list_workspace_tree(path: str = ".", max_depth: int = 3):
        workspace = backend._require_workspace_port()
        return backend._call_port(
            workspace.list_workspace_tree,
            path=path,
            max_depth=max_depth,
            limit=200,
        )

    @app.get("/api/files/tree")
    async def list_file_children(path: str = ".", limit: int = 200):
        workspace = backend._require_workspace_port()
        items = backend._call_port(workspace.list_file_children, path, limit)
        return {"items": items}

    @app.get("/api/files/{path:path}")
    async def read_file(path: str):
        workspace = backend._require_workspace_port()
        return backend._call_port(workspace.read_file, path)

    @app.post("/api/files/{path:path}")
    async def write_file(path: str, request: Dict[str, Any]):
        del path, request
        raise HTTPException(status_code=405, detail="file_write_disabled")

    @app.post("/api/diff")
    async def get_diff(request: Dict[str, Any]):
        workspace = backend._require_workspace_port()
        return backend._call_port(
            workspace.get_diff_preview,
            str(request.get("path") or ""),
            str(request.get("new_content") or ""),
        )
