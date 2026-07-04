from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from embedagent.frontend.gui.backend.http_errors import thread_lifecycle_http_error
from embedagent.frontend.gui.backend.protocol_payloads import (
    read_value,
    serialize_interaction_response,
    serialize_permission_context,
    serialize_plan_snapshot,
    serialize_session_bootstrap,
    serialize_session_capabilities,
    serialize_session_snapshot,
    serialize_session_summary,
)


def register_session_routes(app: Any, backend: Any) -> None:
    @app.get("/api/sessions")
    async def list_sessions(limit: int = 10):
        core = backend._require_core()
        return {"sessions": core.list_sessions(limit)}

    @app.get("/api/sessions/capabilities")
    async def get_session_capabilities():
        core = backend._require_core()
        payload = backend._call_core(core.get_session_capabilities)
        return serialize_session_capabilities(payload)

    @app.get("/api/sessions/{session_id}")
    async def get_session_snapshot(session_id: str):
        core = backend._require_core()
        snapshot = backend._call_core(core.get_session_snapshot, session_id)
        return serialize_session_snapshot(snapshot)

    @app.get("/api/sessions/{session_id}/bootstrap")
    async def get_session_bootstrap(session_id: str):
        core = backend._require_core()
        payload = backend._call_core(core.get_session_bootstrap, session_id)
        return serialize_session_bootstrap(payload)

    @app.post("/api/sessions")
    async def create_session(mode: str = ""):
        core = backend._require_core()
        snapshot = backend._call_core(core.create_session, mode)
        backend._current_session_id = str(read_value(snapshot, "session_id", "") or "")
        return serialize_session_snapshot(snapshot)

    @app.post("/api/sessions/{session_id}/resume")
    async def resume_session(session_id: str, mode: str = ""):
        core = backend._require_core()
        snapshot = backend._call_core(core.resume_session, session_id, mode)
        backend._current_session_id = str(read_value(snapshot, "session_id", "") or "")
        return serialize_session_snapshot(snapshot)

    @app.post("/api/sessions/{session_id}/rename")
    async def rename_session(session_id: str, request: Dict[str, Any]):
        core = backend._require_core()
        try:
            summary = core.rename_session(
                session_id,
                str(request.get("title") or ""),
            )
        except ValueError as exc:
            raise thread_lifecycle_http_error(exc)
        return {"session": serialize_session_summary(summary)}

    @app.post("/api/sessions/{session_id}/archive")
    async def archive_session(session_id: str):
        core = backend._require_core()
        try:
            summary = core.archive_session(session_id)
        except ValueError as exc:
            raise thread_lifecycle_http_error(exc)
        return {"session": serialize_session_summary(summary)}

    @app.post("/api/sessions/{session_id}/fork")
    async def fork_session(session_id: str, request: Dict[str, Any]):
        core = backend._require_core()
        try:
            summary = core.fork_session(
                session_id,
                str(request.get("title") or ""),
            )
        except ValueError as exc:
            raise thread_lifecycle_http_error(exc)
        payload = serialize_session_summary(summary)
        return {"session_id": payload["session_id"], "session": payload}

    @app.post("/api/sessions/{session_id}/message")
    async def send_message(session_id: str, request: Dict[str, Any]):
        text = request.get("text", "")
        backend._current_session_id = session_id
        core = backend._require_core()
        backend._call_core(core.submit_message, session_id, text)
        return {"status": "submitted"}

    @app.post("/api/sessions/{session_id}/cancel")
    async def cancel_session(session_id: str):
        core = backend._require_core()
        snapshot = backend._call_core(core.cancel_session, session_id)
        return serialize_session_snapshot(snapshot)

    @app.post("/api/sessions/{session_id}/mode")
    async def set_mode(session_id: str, request: Dict[str, Any]):
        mode = request.get("mode", "")
        core = backend._require_core()
        backend._call_core(core.set_mode, session_id, mode)
        return {"status": "ok"}

    @app.post("/api/sessions/{session_id}/interactions/{interaction_id}/respond")
    async def respond_to_interaction(session_id: str, interaction_id: str, request: Dict[str, Any]):
        backend._current_session_id = session_id
        core = backend._require_core()
        response = backend._call_core(
            core.respond_to_interaction, session_id, interaction_id, request
        )
        return serialize_interaction_response(
            response,
            session_id=session_id,
            interaction_id=interaction_id,
        )

    @app.get("/api/workspace")
    async def get_workspace():
        core = backend._require_core()
        return core.get_workspace_snapshot()

    @app.post("/api/sessions/{session_id}/resources/reload")
    async def reload_session_resources(session_id: str):
        core = backend._require_core()
        return backend._call_core(core.reload_resources, session_id, reason="api")

    @app.get("/api/sessions/{session_id}/plan")
    async def get_session_plan(session_id: str):
        core = backend._require_core()
        plan = backend._call_core(core.get_session_plan, session_id)
        if plan is None:
            return {"plan": None}
        return {"plan": serialize_plan_snapshot(plan)}

    @app.get("/api/sessions/{session_id}/permissions")
    async def get_permission_context(session_id: str):
        core = backend._require_core()
        context = backend._call_core(core.get_permission_context, session_id)
        return serialize_permission_context(context)

    @app.get("/api/files")
    async def list_workspace_tree(path: str = ".", max_depth: int = 3):
        core = backend._require_core()
        return {"items": core.list_workspace_tree(path, max_depth)}

    @app.get("/api/files/tree")
    async def list_file_children(path: str = ".", limit: int = 200):
        core = backend._require_core()
        return {"items": core.list_file_children(path, limit)}

    @app.get("/api/files/{path:path}")
    async def read_file(path: str):
        try:
            core = backend._require_core()
            return core.read_file(path)
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as e:
            return {"error": str(e)}

    @app.post("/api/files/{path:path}")
    async def write_file(path: str, request: Dict[str, Any]):
        raise HTTPException(status_code=405, detail="file_write_disabled")

    @app.post("/api/diff")
    async def get_diff(request: Dict[str, Any]):
        path = request.get("path", "")
        new_content = request.get("new_content", "")
        core = backend._require_core()
        diff = core.get_diff_preview(path, new_content)
        return {
            "path": diff.path,
            "old_content": diff.old_content,
            "new_content": diff.new_content,
            "unified_diff": diff.unified_diff,
        }
