from __future__ import annotations

from fastapi import HTTPException


def translate_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip()
    if "session_id 不存在" in detail or detail == "session_not_found":
        return HTTPException(status_code=404, detail="session_not_found")
    if detail in ("interaction_gone", "interaction_expired", "未找到待处理的交互请求。"):
        return HTTPException(status_code=410, detail="interaction_expired")
    if detail == "interaction_conflict":
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=422, detail=detail or "invalid_request")


def thread_lifecycle_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "thread_lifecycle_failed"
    if "session_id 不存在" in detail or detail == "session_not_found":
        return HTTPException(status_code=404, detail="session_not_found")
    if detail == "invalid_thread_title":
        return HTTPException(status_code=422, detail=detail)
    if detail == "session_fork_failed":
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail)


def terminal_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "terminal_failed"
    if detail == "terminal_not_found":
        return HTTPException(status_code=404, detail=detail)
    if detail == "terminal_not_running":
        return HTTPException(status_code=409, detail=detail)
    if detail in (
        "invalid_session_id",
        "invalid_terminal_id",
        "terminal_write_empty",
        "terminal_write_too_large",
        "terminal_cwd_outside_workspace",
        "terminal_cwd_not_found",
        "terminal_cwd_not_directory",
        "terminal_shell_unavailable",
    ):
        return HTTPException(status_code=422, detail=detail)
    if detail.startswith("terminal_start_failed"):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail)


def source_control_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "source_control_failed"
    if detail in ("invalid_diff_scope", "path_outside_workspace"):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail or "source_control_failed")


def preview_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "preview_failed"
    if detail == "preview_tab_not_found":
        return HTTPException(status_code=404, detail=detail)
    if detail in (
        "invalid_session_id",
        "invalid_preview_tab_id",
        "preview_url_required",
        "preview_url_too_long",
        "preview_url_not_local",
    ):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail or "preview_failed")
