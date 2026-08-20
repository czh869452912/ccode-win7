from __future__ import annotations

import json
import sys
from typing import Any, Mapping, Optional, Sequence, TextIO

from embedagent_protocol import FailureRecord, ThreadShell

from embedagent.cli.result import CliResult, write_failure
from embedagent.frontend.runtime import RuntimeAction
from embedagent.frontend.runtime.interaction_projection import InteractionPrompt


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


class ChatRenderer(object):
    def __init__(
        self,
        stdout: Optional[TextIO] = None,
        stderr: Optional[TextIO] = None,
    ) -> None:
        self._stdout = stdout if stdout is not None else sys.stdout
        self._stderr = stderr if stderr is not None else sys.stderr
        self._assistant_seen = False
        self._assistant_ends_with_newline = True

    def write_help(self, shell: Any) -> None:
        self._stdout.write("/help\tShow commands\n")
        self._stdout.write("/exit\tExit chat\n")
        for command in shell.commands:
            dispatch = dict(command.dispatch)
            if dispatch.get("kind") == "session.command":
                name = str(dispatch.get("command") or command.id).lstrip("/")
            else:
                name = command.id
            detail = str(command.label)
            if command.summary:
                detail += " - " + str(command.summary)
            self._stdout.write("/%s\t%s\n" % (_cell(name), _cell(detail)))

    def write_interaction_prompt(self, prompt: InteractionPrompt) -> None:
        self._stdout.write("%s\n" % _cell(prompt.prompt))
        for choice in prompt.choices:
            self._stdout.write("  %s. %s\n" % (_cell(choice.key), _cell(choice.label)))
        if prompt.default:
            self._stdout.write("  default: %s\n" % _cell(prompt.default))
        self._stdout.write("choice> ")
        self._flush(self._stdout)

    def write_input_prompt(self) -> None:
        self._stdout.write("> ")
        self._flush(self._stdout)

    def write_interrupt(self, running: bool) -> None:
        self._stdout.write("^C%s\n" % (" cancelled" if running else ""))

    def write_usage_error(self) -> None:
        write_failure(
            FailureRecord(
                code="usage_error",
                message="",
                retryable=False,
                source="cli",
            ),
            stream=self._stderr,
        )

    def write_failure(self, failure: FailureRecord) -> None:
        write_failure(failure, stream=self._stderr)

    def on_runtime_action(self, action: RuntimeAction) -> None:
        if not isinstance(action, RuntimeAction):
            raise TypeError("action must be a RuntimeAction")
        value = action.to_dict()
        if action.kind == "session_activated":
            if value.get("reason") in ("activate", "create", "resume", "fork"):
                bootstrap = value.get("bootstrap")
                bootstrap = bootstrap if isinstance(bootstrap, Mapping) else {}
                history = bootstrap.get("history")
                history = history if isinstance(history, Mapping) else {}
                self._write_history(history.get("activities"))
            return
        if action.kind == "protocol_failed":
            self._write_failure_mapping(value.get("failure"))
            return
        if action.kind == "shell_command":
            command = value.get("command")
            command = command if isinstance(command, Mapping) else {}
            self._stdout.write("[shell] %s\n" % _cell(command.get("label")))
            return
        if action.kind != "session_event":
            return
        event = value.get("event")
        event = event if isinstance(event, Mapping) else {}
        self._write_event(str(event.get("event_kind") or ""), event.get("payload"))

    def _write_history(self, records: Any) -> None:
        for item in records if isinstance(records, list) else []:
            if not isinstance(item, Mapping):
                continue
            kind = str(item.get("kind") or "")
            content = _cell(item.get("content"))
            if kind == "user":
                self._stdout.write("user> %s\n" % content)
            elif kind == "assistant":
                self._stdout.write("assistant> %s\n" % content)
            elif kind == "reasoning":
                self._stdout.write("thinking> %s\n" % content)
            elif kind == "tool":
                self._stdout.write(
                    "tool %s [%s]\n"
                    % (_cell(item.get("tool_name") or "tool"), _cell(item.get("status")))
                )
            elif kind == "interaction":
                self._stdout.write("interaction [%s]\n" % _cell(item.get("status")))

    def _write_event(self, event_kind: str, payload: Any) -> None:
        data = payload if isinstance(payload, Mapping) else {}
        if event_kind == "turn.started":
            self._assistant_seen = False
            self._assistant_ends_with_newline = True
        elif event_kind == "assistant.delta":
            text = str(data.get("text") or "")
            if text:
                self._stdout.write(text)
                self._assistant_seen = True
                self._assistant_ends_with_newline = text.endswith("\n")
                self._flush(self._stdout)
        elif event_kind == "tool.started":
            self._stderr.write("tool: %s\n" % _cell(data.get("tool_name")))
        elif event_kind == "tool.finished":
            status = "ok" if bool(data.get("success")) else "failed"
            self._stderr.write("tool: %s %s\n" % (_cell(data.get("tool_name")), status))
        elif event_kind == "command.result":
            self._stdout.write("%s\n" % _cell(data.get("message")))
        elif event_kind in ("approval.resolved", "user-input.resolved"):
            self._stdout.write("[interaction] resolved\n")
        elif event_kind in ("approval.response.failed", "user-input.response.failed"):
            self._stderr.write("error: interaction_required\n")
        elif event_kind == "session.error":
            self._finish_assistant_line()
            self._write_failure_mapping(data.get("failure"))
        elif event_kind == "session.finished":
            final_text = str(data.get("final_text") or "")
            if not self._assistant_seen and final_text:
                self._stdout.write(final_text)
                self._assistant_ends_with_newline = final_text.endswith("\n")
            self._finish_assistant_line()
            self._assistant_seen = False

    def _finish_assistant_line(self) -> None:
        if not self._assistant_ends_with_newline:
            self._stdout.write("\n")
        self._assistant_ends_with_newline = True

    def _write_failure_mapping(self, value: Any) -> None:
        try:
            failure = FailureRecord.from_dict(value)
        except (TypeError, ValueError):
            failure = FailureRecord(
                code="protocol_error",
                message="",
                retryable=False,
                source="cli",
            )
        self.write_failure(failure)

    @staticmethod
    def _flush(stream: TextIO) -> None:
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()
