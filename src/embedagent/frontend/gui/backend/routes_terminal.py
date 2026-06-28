from __future__ import annotations

from typing import Any, Dict

from embedagent.frontend.gui.backend.http_errors import terminal_http_error


def register_terminal_routes(app: Any, backend: Any) -> None:
    @app.get("/api/sessions/{session_id}/terminals")
    async def list_session_terminals(session_id: str):
        terminal = backend._terminal()
        return {"terminals": terminal.list_sessions(session_id)}

    @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/open")
    async def open_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
        terminal = backend._terminal()
        try:
            snapshot = terminal.open_or_attach(
                session_id,
                terminal_id,
                cwd=str(request.get("cwd") or ""),
                cols=int(request.get("cols") or 80),
                rows=int(request.get("rows") or 24),
            )
        except ValueError as exc:
            raise terminal_http_error(exc)
        return {"terminal": snapshot}

    @app.get("/api/sessions/{session_id}/terminals/{terminal_id}/snapshot")
    async def get_terminal_snapshot(session_id: str, terminal_id: str):
        terminal = backend._terminal()
        try:
            snapshot = terminal.snapshot(session_id, terminal_id)
        except ValueError as exc:
            raise terminal_http_error(exc)
        return {"terminal": snapshot}

    @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/write")
    async def write_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
        terminal = backend._terminal()
        try:
            snapshot = terminal.write(session_id, terminal_id, str(request.get("data") or ""))
        except ValueError as exc:
            raise terminal_http_error(exc)
        return {"terminal": snapshot}

    @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/clear")
    async def clear_terminal(session_id: str, terminal_id: str):
        terminal = backend._terminal()
        try:
            snapshot = terminal.clear(session_id, terminal_id)
        except ValueError as exc:
            raise terminal_http_error(exc)
        return {"terminal": snapshot}

    @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/restart")
    async def restart_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
        terminal = backend._terminal()
        try:
            snapshot = terminal.restart(
                session_id,
                terminal_id,
                cwd=str(request.get("cwd") or ""),
                cols=int(request.get("cols") or 80),
                rows=int(request.get("rows") or 24),
            )
        except ValueError as exc:
            raise terminal_http_error(exc)
        return {"terminal": snapshot}

    @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/resize")
    async def resize_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
        terminal = backend._terminal()
        try:
            snapshot = terminal.resize(
                session_id,
                terminal_id,
                cols=int(request.get("cols") or 80),
                rows=int(request.get("rows") or 24),
            )
        except ValueError as exc:
            raise terminal_http_error(exc)
        return {"terminal": snapshot}

    @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/close")
    async def close_terminal(session_id: str, terminal_id: str):
        terminal = backend._terminal()
        try:
            snapshot = terminal.close(session_id, terminal_id)
        except ValueError as exc:
            raise terminal_http_error(exc)
        return {"terminal": snapshot}
