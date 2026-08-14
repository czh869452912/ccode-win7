from __future__ import annotations

import json
import sys
from typing import Any, Mapping, Optional, Sequence, TextIO

from embedagent_protocol import FailureRecord, ThreadShell

from embedagent.cli.result import CliResult, write_failure


def write_result(
    result: CliResult,
    output: str = "text",
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    if not isinstance(result, CliResult):
        raise TypeError("result must be a CliResult")
    selected_output = str(output or "text")
    out = stdout if stdout is not None else sys.stdout
    error = stderr if stderr is not None else sys.stderr
    if selected_output == "json":
        out.write(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        return result.exit_code
    if selected_output != "text":
        raise ValueError("unsupported CLI output format")
    if result.final_text:
        out.write(result.final_text)
        if not result.final_text.endswith("\n"):
            out.write("\n")
    if result.failure is not None:
        write_failure(result.failure, stream=error)
    return result.exit_code


def write_command_failure(
    failure: FailureRecord,
    output: str = "text",
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    if output == "json":
        return write_result(
            CliResult.from_failure("", failure),
            output="json",
            stdout=stdout,
            stderr=stderr,
        )
    return write_failure(failure, stream=stderr)


def write_json_projection(value: Any, stdout: Optional[TextIO] = None) -> int:
    target = stdout if stdout is not None else sys.stdout
    target.write(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def _cell(value: Any) -> str:
    return " ".join(str(value or "").split())


def write_session_list(
    threads: Sequence[ThreadShell],
    stdout: Optional[TextIO] = None,
) -> int:
    target = stdout if stdout is not None else sys.stdout
    target.write("ID\tSTATUS\tMODE\tUPDATED\tTITLE\n")
    for thread in threads:
        if not isinstance(thread, ThreadShell):
            raise TypeError("session list items must be ThreadShell instances")
        target.write(
            "%s\t%s\t%s\t%s\t%s\n"
            % (
                _cell(thread.id),
                _cell(thread.status),
                _cell(thread.current_mode),
                _cell(thread.updated_at),
                _cell(thread.title),
            )
        )
    return 0


def write_thread_shell(
    thread: ThreadShell,
    stdout: Optional[TextIO] = None,
) -> int:
    if not isinstance(thread, ThreadShell):
        raise TypeError("thread must be a ThreadShell")
    target = stdout if stdout is not None else sys.stdout
    target.write("ID: %s\n" % _cell(thread.id))
    target.write("Title: %s\n" % _cell(thread.title))
    target.write("Status: %s\n" % _cell(thread.status))
    target.write("Mode: %s\n" % _cell(thread.current_mode))
    target.write("Updated: %s\n" % _cell(thread.updated_at))
    target.write("Archived: %s\n" % ("yes" if thread.archived else "no"))
    return 0


def write_session_summary(
    summary: Mapping[str, Any],
    stdout: Optional[TextIO] = None,
) -> int:
    if not isinstance(summary, Mapping):
        raise TypeError("summary must be a mapping")
    target = stdout if stdout is not None else sys.stdout
    thread = summary.get("thread")
    thread = thread if isinstance(thread, Mapping) else {}
    target.write("ID: %s\n" % _cell(summary.get("session_id")))
    target.write("Title: %s\n" % _cell(summary.get("title") or thread.get("title")))
    target.write("Status: %s\n" % _cell(summary.get("status")))
    target.write("Mode: %s\n" % _cell(summary.get("current_mode")))
    target.write("Updated: %s\n" % _cell(summary.get("updated_at")))
    archived = bool(summary.get("archived", thread.get("archived", False)))
    target.write("Archived: %s\n" % ("yes" if archived else "no"))
    if summary.get("turn_count") is not None:
        target.write("Turns: %s\n" % _cell(summary.get("turn_count")))
    if summary.get("summary_text"):
        target.write("Summary: %s\n" % _cell(summary.get("summary_text")))
    return 0
