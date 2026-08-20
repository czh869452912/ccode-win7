from __future__ import annotations

from typing import Any, Optional, TextIO, Tuple

from embedagent_host import FrontendPortError
from embedagent_protocol import FailureRecord, ThreadShell

from embedagent.cli.renderer import (
    write_command_failure,
    write_json_projection,
    write_session_list,
    write_session_summary,
    write_thread_shell,
)


def _failure(code: str) -> FailureRecord:
    return FailureRecord(code=code, message="", retryable=False, source="cli")


def _resolved_session_id(context: Any) -> str:
    reference = str(context.options.reference or "").strip()
    if not reference:
        raise ValueError("session reference is required")
    summary = context.client_runtime.load_session_summary(reference)
    if not isinstance(summary, dict):
        raise TypeError("session summary must be a mapping")
    session_id = summary.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise TypeError("session summary must contain session_id")
    return session_id.strip()


def _execute(context: Any) -> Tuple[str, Any]:
    options = context.options
    runtime = context.client_runtime
    if options.sessions_action == "list":
        threads = runtime.list_sessions(limit=options.limit)
        if not isinstance(threads, list) or not all(
            isinstance(thread, ThreadShell) for thread in threads
        ):
            raise TypeError("session port must return ThreadShell items")
        return "threads", threads
    if options.sessions_action == "show":
        reference = str(options.reference or "").strip()
        if not reference:
            raise ValueError("session reference is required")
        summary = runtime.load_session_summary(reference)
        if not isinstance(summary, dict):
            raise TypeError("session summary must be a mapping")
        return "summary", dict(summary)
    if options.sessions_action == "rename":
        title = str(options.title or "").strip()
        if not title:
            return "failure", _failure("usage_error")
        return "thread", runtime.rename_session(_resolved_session_id(context), title)
    if options.sessions_action == "archive":
        return "thread", runtime.archive_session(_resolved_session_id(context))
    if options.sessions_action == "fork":
        title = str(options.title or "").strip()
        return "thread", runtime.fork_session(_resolved_session_id(context), title)
    return "failure", _failure("usage_error")


def run_sessions_command(
    context: Any,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    try:
        kind, value = _execute(context)
        if kind == "failure":
            return write_command_failure(
                value,
                output=context.options.output,
                stdout=stdout,
                stderr=stderr,
            )
        if kind == "threads":
            if context.options.output == "json":
                return write_json_projection(
                    [thread.to_dict() for thread in value],
                    stdout=stdout,
                )
            return write_session_list(value, stdout=stdout)
        if kind == "summary":
            if context.options.output == "json":
                return write_json_projection(value, stdout=stdout)
            return write_session_summary(value, stdout=stdout)
        if not isinstance(value, ThreadShell):
            raise TypeError("session mutation must return a ThreadShell")
        if context.options.output == "json":
            return write_json_projection(value.to_dict(), stdout=stdout)
        return write_thread_shell(value, stdout=stdout)
    except FrontendPortError as exc:
        failure = exc.failure
    except ValueError:
        failure = _failure("usage_error")
    except (RuntimeError, TypeError):
        failure = _failure("protocol_error")
    return write_command_failure(
        failure,
        output=context.options.output,
        stdout=stdout,
        stderr=stderr,
    )
