from __future__ import annotations

import shlex
import sys
from typing import Any, Optional, TextIO

from embedagent_host import FrontendPortError
from embedagent_protocol import FailureRecord, SessionEventEnvelope

from embedagent.cli.interaction import (
    InteractionPrompt,
    InteractionResponseError,
    build_interaction_response,
    resolve_interaction,
)
from embedagent.cli.renderer import ChatRenderer
from embedagent.cli.result import CliResult, exit_code_for_failure
from embedagent.frontend.runtime import RuntimeAction
from embedagent.frontend.runtime.commands import resolve_command
from embedagent.modes import DEFAULT_MODE

_INTERACTION_REQUEST_EVENTS = frozenset(("approval.requested", "user-input.requested"))
_INTERACTION_RESOLVED_EVENTS = frozenset(("approval.resolved", "user-input.resolved"))


def _failure(code: str) -> FailureRecord:
    return FailureRecord(code=code, message="", retryable=False, source="cli")


class CliChat(object):
    def __init__(
        self,
        context: Any,
        input_stream: Optional[TextIO] = None,
        stdout: Optional[TextIO] = None,
        stderr: Optional[TextIO] = None,
    ) -> None:
        self._runtime = context.client_runtime
        self._shell = context.shell_descriptor
        self._resume = str(context.options.resume or "")
        self._mode = str(context.options.mode or "")
        self._has_workspace = bool(context.options.launch.workspace)
        self._app_config = getattr(context.launch_config, "app_config", None)
        self._input = input_stream if input_stream is not None else sys.stdin
        self._renderer = ChatRenderer(stdout=stdout, stderr=stderr)
        self._active_interaction: Optional[InteractionPrompt] = None
        self._running = False
        self._interrupt_armed = False
        self._fatal_exit = 0

    def run(self) -> int:
        try:
            self._runtime.bind_dispatch(self.on_runtime_action)
            if self._resume:
                self._runtime.resume_session(self._resume, self._mode)
            else:
                configured = getattr(self._app_config, "default_mode", None)
                mode = self._mode or str(configured or DEFAULT_MODE)
                self._runtime.create_session(mode)
            return self._input_loop()
        except FrontendPortError as exc:
            failure = exc.failure
        except (TypeError, ValueError):
            failure = _failure("protocol_error")
        except RuntimeError:
            failure = _failure("runtime_error")
        except KeyboardInterrupt:
            self._renderer.write_interrupt(running=False)
            return 130
        self._renderer.write_failure(failure)
        return exit_code_for_failure(failure.code)

    def on_runtime_action(self, action: RuntimeAction) -> None:
        self._renderer.on_runtime_action(action)
        value = action.to_dict()
        if action.kind == "session_activated":
            bootstrap = value.get("bootstrap")
            bootstrap = bootstrap if isinstance(bootstrap, dict) else {}
            snapshot = bootstrap.get("snapshot")
            snapshot = snapshot if isinstance(snapshot, dict) else {}
            pending = snapshot.get("pending_interaction")
            if bool(snapshot.get("pending_interaction_valid")) and isinstance(pending, dict):
                self._set_interaction("", pending)
            else:
                self._active_interaction = None
            return
        if action.kind == "protocol_failed":
            self._fatal_exit = 4
            return
        if action.kind != "session_event":
            return
        envelope = SessionEventEnvelope.from_dict(value.get("event") or {})
        if envelope.event_kind in _INTERACTION_REQUEST_EVENTS:
            self._set_interaction(envelope.event_kind, envelope.payload)
        elif envelope.event_kind in _INTERACTION_RESOLVED_EVENTS:
            interaction_id = str(
                envelope.payload.get("interaction_id") or envelope.payload.get("request_id") or ""
            )
            current = self._active_interaction
            if current is not None and current.interaction_id == interaction_id:
                self._active_interaction = None
        elif envelope.event_kind in ("session.finished", "session.error"):
            self._running = False

    def _set_interaction(self, event_kind: str, payload: Any) -> None:
        try:
            self._active_interaction = resolve_interaction(
                self._shell,
                event_kind,
                payload,
            )
        except (TypeError, ValueError):
            self._renderer.write_failure(_failure("protocol_error"))
            self._fatal_exit = 4

    def _input_loop(self) -> int:
        while True:
            if self._fatal_exit:
                return self._fatal_exit
            if self._active_interaction is not None:
                self._renderer.write_interaction_prompt(self._active_interaction)
            else:
                self._renderer.write_input_prompt()
            try:
                line = self._input.readline()
            except KeyboardInterrupt:
                if self._interrupt_armed:
                    return 130
                self._interrupt_armed = True
                self._renderer.write_interrupt(running=False)
                continue
            if line == "":
                return 0
            self._interrupt_armed = False
            text = str(line).strip()
            if text == "/exit":
                return 0
            elif text == "/help":
                self._renderer.write_help(self._shell)
                continue
            elif self._active_interaction is not None:
                exit_code = self._respond_to_interaction(text)
            elif not text:
                continue
            elif text.startswith("/"):
                exit_code = self._dispatch_command(text)
            else:
                exit_code = self._submit(text)
            if exit_code is not None:
                return exit_code

    def _submit(self, text: str) -> Optional[int]:
        self._running = True
        try:
            self._runtime.submit_user_message(
                self._runtime.active_session_id,
                text,
                stream=True,
            )
        except KeyboardInterrupt:
            return self._cancel_running_turn()
        return self._wait_for_turn()

    def _dispatch_command(self, text: str) -> Optional[int]:
        try:
            parts = shlex.split(text)
            name = parts[0].lstrip("/") if parts else ""
            args = parts[1:]
            availability = self._availability()
            command = resolve_command(self._shell, name, availability)
            self._runtime.dispatch_command(
                self._shell,
                command.id,
                args,
                availability=availability,
                default_mode=self._initial_mode(),
            )
            if command.dispatch.get("kind") == "session.command":
                self._running = True
                return self._wait_for_turn()
        except KeyboardInterrupt:
            return self._cancel_running_turn()
        except (TypeError, ValueError):
            self._renderer.write_usage_error()
        return None

    def _respond_to_interaction(self, text: str) -> Optional[int]:
        prompt = self._active_interaction
        if prompt is None:
            return None
        try:
            payload = build_interaction_response(prompt, text)
        except InteractionResponseError:
            self._renderer.write_usage_error()
            return None
        try:
            self._running = True
            self._runtime.respond_to_interaction(
                self._runtime.active_session_id,
                prompt.interaction_id,
                payload,
            )
            return self._wait_for_turn()
        except KeyboardInterrupt:
            return self._cancel_running_turn()
        except FrontendPortError as exc:
            self._running = False
            self._renderer.write_failure(exc.failure)
            return None

    def _wait_for_turn(self) -> Optional[int]:
        try:
            outcome = self._runtime.wait_for_terminal()
        except KeyboardInterrupt:
            return self._cancel_running_turn()
        self._running = False
        result = CliResult.from_runtime_outcome(outcome)
        if result.status == "failed":
            return result.exit_code
        return None

    def _cancel_running_turn(self) -> Optional[int]:
        try:
            self._runtime.cancel_session(self._runtime.active_session_id)
        except FrontendPortError as exc:
            self._running = False
            self._renderer.write_failure(exc.failure)
            return exit_code_for_failure(exc.failure.code)
        self._running = False
        self._interrupt_armed = True
        self._renderer.write_interrupt(running=True)
        return None

    def _availability(self) -> dict:
        return {
            "has_session": bool(self._runtime.active_session_id),
            "has_workspace": self._has_workspace,
            "running": self._running,
            "has_interaction": self._active_interaction is not None,
        }

    def _initial_mode(self) -> str:
        configured = getattr(self._app_config, "default_mode", None)
        return self._mode or str(configured or DEFAULT_MODE)


def run_chat_command(
    context: Any,
    input_stream: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    return CliChat(
        context,
        input_stream=input_stream,
        stdout=stdout,
        stderr=stderr,
    ).run()
