from __future__ import annotations

from typing import Any

from embedagent.frontend.gui.backend.http_errors import source_control_http_error


def register_source_control_routes(app: Any, backend: Any) -> None:
    @app.get("/api/app/source-control/status")
    async def get_source_control_status():
        source_control = backend._source_control()
        return {"source_control": source_control.status()}

    @app.post("/api/app/source-control/refresh")
    async def refresh_source_control_status():
        source_control = backend._source_control()
        return {"source_control": source_control.status()}

    @app.get("/api/app/source-control/diff")
    async def get_source_control_diff(path: str, scope: str = "unstaged"):
        source_control = backend._source_control()
        try:
            payload = source_control.diff(path, scope=scope)
        except ValueError as exc:
            raise source_control_http_error(exc)
        return {"diff": payload}
