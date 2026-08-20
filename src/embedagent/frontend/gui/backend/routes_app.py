from __future__ import annotations

from typing import Any, Dict

from embedagent_host.frontend_errors import FrontendPortError
from fastapi import HTTPException

from embedagent.frontend.gui.backend.http_errors import (
    frontend_port_http_error,
    preview_http_error,
    workspace_http_error,
)
from embedagent.frontend.gui.backend.protocol_payloads import serialize_app_bootstrap


def register_app_routes(app: Any, backend: Any) -> None:
    @app.get("/api/app/bootstrap")
    async def get_app_bootstrap():
        return serialize_app_bootstrap(backend.app_shell.bootstrap())

    @app.get("/api/app/workspaces")
    async def list_app_workspaces():
        return serialize_app_bootstrap(backend.app_shell.list_workspaces())

    @app.post("/api/app/workspaces")
    async def open_app_workspace(request: Dict[str, Any]):
        path = str(request.get("path") or "").strip()
        label = str(request.get("label") or "").strip()
        if not path:
            raise HTTPException(status_code=422, detail="workspace_path_required")
        try:
            return serialize_app_bootstrap(backend.app_shell.open_workspace_path(path, label=label))
        except FrontendPortError as exc:
            raise frontend_port_http_error(exc)
        except ValueError as exc:
            raise workspace_http_error(exc)

    @app.post("/api/app/workspaces/{workspace_id}/activate")
    async def activate_app_workspace(workspace_id: str):
        try:
            return serialize_app_bootstrap(backend.app_shell.activate_workspace(workspace_id))
        except FrontendPortError as exc:
            raise frontend_port_http_error(exc)
        except ValueError as exc:
            raise workspace_http_error(exc)

    @app.delete("/api/app/workspaces/{workspace_id}")
    async def remove_app_workspace(workspace_id: str):
        return serialize_app_bootstrap(backend.app_shell.remove_workspace(workspace_id))

    @app.post("/api/app/preview/open-external")
    async def open_preview_external(request: Dict[str, Any]):
        preview = backend._preview()
        try:
            payload = preview.open_external(str(request.get("url") or ""))
        except ValueError as exc:
            raise preview_http_error(exc)
        return payload
