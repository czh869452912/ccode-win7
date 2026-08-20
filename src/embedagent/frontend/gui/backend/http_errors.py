from __future__ import annotations

from embedagent_host.frontend_errors import FrontendPortError
from embedagent_protocol import FailureRecord
from fastapi import HTTPException


def _http_failure(status_code: int, failure: FailureRecord) -> HTTPException:
    return HTTPException(status_code=status_code, detail=failure.to_dict())


def _failure(code: str, source: str, phase: str, kind: str) -> FailureRecord:
    return FailureRecord(
        code=code,
        source=source,
        phase=phase,
        kind=kind,
        retryable=False,
    )


def frontend_port_http_error(exc: FrontendPortError) -> HTTPException:
    code = exc.failure.code
    if code == "session_not_found":
        return _http_failure(404, exc.failure)
    if code == "interaction_required":
        return _http_failure(409, exc.failure)
    if code in ("permission_denied", "cancelled"):
        return _http_failure(409, exc.failure)
    if code in ("provider_error", "runtime_error"):
        return _http_failure(502, exc.failure)
    return _http_failure(422, exc.failure)


def translate_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip()
    if "session_id 不存在" in detail or detail == "session_not_found":
        return _http_failure(404, _failure("session_not_found", "gui", "session_lookup", "runtime"))
    if (
        "interaction_gone" in detail
        or "interaction_expired" in detail
        or "未找到待处理的交互请求。" in detail
    ):
        return _http_failure(
            410, _failure("interaction_expired", "gui", "interaction", "interaction")
        )
    if "interaction_conflict" in detail:
        return _http_failure(
            409, _failure("interaction_conflict", "gui", "interaction", "interaction")
        )
    if "invalid_interaction_response" in detail:
        return _http_failure(
            422, _failure("invalid_interaction_response", "gui", "interaction", "protocol")
        )
    return _http_failure(422, _failure("invalid_request", "gui", "request", "protocol"))


def workspace_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip()
    if detail == "workspace_not_found":
        return _http_failure(404, _failure(detail, "gui", "workspace", "runtime"))
    if detail == "workspace_path_required":
        return _http_failure(422, _failure(detail, "gui", "workspace", "protocol"))
    return _http_failure(422, _failure("workspace_operation_failed", "gui", "workspace", "runtime"))


def thread_lifecycle_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "thread_lifecycle_failed"
    if "session_id 不存在" in detail or detail == "session_not_found":
        return _http_failure(404, _failure("session_not_found", "gui", "session_lookup", "runtime"))
    if detail == "invalid_thread_title":
        return _http_failure(422, _failure(detail, "gui", "thread_lifecycle", "protocol"))
    if detail == "session_fork_failed":
        return _http_failure(422, _failure(detail, "gui", "thread_lifecycle", "runtime"))
    return _http_failure(
        422, _failure("thread_lifecycle_failed", "gui", "thread_lifecycle", "runtime")
    )


def terminal_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "terminal_failed"
    if detail == "terminal_not_found":
        return _http_failure(404, _failure(detail, "gui", "terminal", "runtime"))
    if detail == "terminal_not_running":
        return _http_failure(409, _failure(detail, "gui", "terminal", "runtime"))
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
        return _http_failure(422, _failure(detail, "gui", "terminal", "protocol"))
    if detail.startswith("terminal_start_failed"):
        return _http_failure(422, _failure("terminal_start_failed", "gui", "terminal", "runtime"))
    return _http_failure(422, _failure("terminal_failed", "gui", "terminal", "runtime"))


def source_control_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "source_control_failed"
    if detail in ("invalid_diff_scope", "path_outside_workspace"):
        return _http_failure(422, _failure(detail, "gui", "source_control", "protocol"))
    return _http_failure(422, _failure("source_control_failed", "gui", "source_control", "runtime"))


def preview_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "preview_failed"
    if detail == "preview_tab_not_found":
        return _http_failure(404, _failure(detail, "gui", "preview", "runtime"))
    if detail in (
        "invalid_session_id",
        "invalid_preview_tab_id",
        "preview_url_required",
        "preview_url_too_long",
        "preview_url_not_local",
    ):
        return _http_failure(422, _failure(detail, "gui", "preview", "protocol"))
    return _http_failure(422, _failure("preview_failed", "gui", "preview", "runtime"))
