from __future__ import annotations

from typing import Any, Optional, TextIO

from embedagent_host import FrontendPortError
from embedagent_protocol import FailureRecord

from embedagent.cli.renderer import write_result
from embedagent.cli.result import CliResult
from embedagent.modes import DEFAULT_MODE


def _failure(code: str, source: str) -> FailureRecord:
    return FailureRecord(code=code, message="", retryable=False, source=source)


def _default_mode(context: Any) -> str:
    app_config = getattr(context.launch_config, "app_config", None)
    return str(getattr(app_config, "default_mode", None) or DEFAULT_MODE)


def execute_run(context: Any) -> CliResult:
    options = context.options
    runtime = context.client_runtime
    if not str(options.task or "").strip():
        return CliResult.from_failure("", _failure("usage_error", "cli"))
    try:
        if options.resume:
            bootstrap = runtime.resume_session(options.resume, options.mode)
        else:
            bootstrap = runtime.create_session(options.mode or _default_mode(context))
        session_id = bootstrap.thread.id
        runtime.submit_user_message(session_id, options.task, stream=True)
        return CliResult.from_runtime_outcome(runtime.wait_for_terminal())
    except FrontendPortError as exc:
        return CliResult.from_failure(runtime.active_session_id, exc.failure)
    except (TypeError, ValueError):
        return CliResult.from_failure(
            runtime.active_session_id,
            _failure("protocol_error", "cli"),
        )
    except RuntimeError:
        return CliResult.from_failure(
            runtime.active_session_id,
            _failure("runtime_error", "cli"),
        )


def run_command(
    context: Any,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    result = execute_run(context)
    return write_result(
        result,
        output=context.options.output,
        stdout=stdout,
        stderr=stderr,
    )
