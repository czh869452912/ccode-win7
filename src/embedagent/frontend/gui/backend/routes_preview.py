from __future__ import annotations

from typing import Any, Dict

from embedagent.frontend.gui.backend.http_errors import preview_http_error


def register_preview_routes(app: Any, backend: Any) -> None:
    @app.get("/api/sessions/{session_id}/preview")
    async def list_preview_sessions(session_id: str):
        preview = backend._preview()
        try:
            payload = preview.list_sessions(session_id)
        except ValueError as exc:
            raise preview_http_error(exc)
        return {"preview": payload}

    @app.post("/api/sessions/{session_id}/preview/open")
    async def open_preview(session_id: str, request: Dict[str, Any]):
        preview = backend._preview()
        try:
            payload = preview.open(session_id, str(request.get("url") or ""))
        except ValueError as exc:
            raise preview_http_error(exc)
        return {"preview": payload}

    @app.post("/api/sessions/{session_id}/preview/{tab_id}/refresh")
    async def refresh_preview(session_id: str, tab_id: str):
        preview = backend._preview()
        try:
            payload = preview.refresh(session_id, tab_id)
        except ValueError as exc:
            raise preview_http_error(exc)
        return {"preview": payload}

    @app.post("/api/sessions/{session_id}/preview/{tab_id}/close")
    async def close_preview(session_id: str, tab_id: str):
        preview = backend._preview()
        try:
            payload = preview.close(session_id, tab_id)
        except ValueError as exc:
            raise preview_http_error(exc)
        return {"preview": payload}
