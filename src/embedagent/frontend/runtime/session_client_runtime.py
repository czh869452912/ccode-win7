from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from embedagent_protocol import (
    FailureRecord,
    FrontendSessionPort,
    SessionBootstrap,
    SessionEventEnvelope,
    SessionEventSink,
    ShellDescriptor,
    ThreadShell,
)

from embedagent.frontend.runtime.commands import (
    UnsupportedShellDispatch,
    resolve_command,
)
from embedagent.frontend.runtime.runtime_actions import RuntimeAction

_INTERACTION_REQUEST_EVENTS = frozenset(("approval.requested", "user-input.requested"))
_INTERACTION_FINISH_EVENTS = frozenset(
    (
        "approval.resolved",
        "approval.response.failed",
        "user-input.resolved",
        "user-input.response.failed",
    )
)


def _required_session_id(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("session_id must be a string")
    session_id = value.strip()
    if not session_id:
        raise ValueError("session_id is required")
    return session_id


def _failure_for_error(error: BaseException) -> FailureRecord:
    failure = getattr(error, "failure", None)
    if isinstance(failure, FailureRecord):
        return failure
    if isinstance(error, (TypeError, ValueError)):
        code = "protocol_error"
    else:
        code = "runtime_error"
    return FailureRecord(
        code=code,
        message=str(error),
        retryable=False,
        source="client_runtime",
    )


class SessionClientRuntime(SessionEventSink):
    """Transport-neutral owner of frontend session activation and event ordering."""

    def __init__(
        self,
        dispatch: Optional[Callable[[RuntimeAction], None]] = None,
    ) -> None:
        self._dispatch = dispatch if callable(dispatch) else lambda action: None
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._session_port = None  # type: Optional[FrontendSessionPort]
        self._active_session_id = ""
        self._event_cursor = 0
        self._generation = 0
        self._lifecycle = "idle"
        self._activating = False
        self._recovering = False
        self._recovery_attempted = False
        self._buffered_events: List[SessionEventEnvelope] = []
        self._terminal_outcome = None  # type: Optional[RuntimeAction]

    @property
    def lifecycle(self) -> str:
        with self._lock:
            return self._lifecycle

    @property
    def active_session_id(self) -> str:
        with self._lock:
            return self._active_session_id

    @property
    def event_cursor(self) -> int:
        with self._lock:
            return self._event_cursor

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def bind_session_port(self, session_port: FrontendSessionPort) -> None:
        if not callable(getattr(session_port, "get_session_bootstrap", None)):
            raise TypeError("session port must provide get_session_bootstrap")
        if not callable(getattr(session_port, "close", None)):
            raise TypeError("session port must provide close")
        with self._condition:
            self._assert_operable()
            if self._session_port is not None:
                raise RuntimeError("session port is already bound")
            self._session_port = session_port

    def activate_session(
        self,
        reference: str,
        mode: str = "",
        reason: str = "activate",
    ) -> Optional[SessionBootstrap]:
        session_id = _required_session_id(reference)
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
            self._generation += 1
            generation = self._generation
            self._active_session_id = session_id
            self._event_cursor = 0
            self._lifecycle = "activating"
            self._activating = True
            self._recovering = False
            self._recovery_attempted = False
            self._buffered_events = []
            self._terminal_outcome = None
            self._condition.notify_all()
        try:
            bootstrap = port.get_session_bootstrap(session_id, mode)
            self._validate_bootstrap(bootstrap, session_id)
        except Exception as exc:
            self._fail_generation(generation, session_id, _failure_for_error(exc))
            return None
        if not self._install_bootstrap(generation, session_id, bootstrap, reason):
            return None
        return bootstrap

    def on_session_event(self, envelope: SessionEventEnvelope) -> None:
        if not isinstance(envelope, SessionEventEnvelope):
            raise TypeError("envelope must be a SessionEventEnvelope")
        recover = False
        fail = False
        generation = 0
        session_id = ""
        action = None  # type: Optional[RuntimeAction]
        with self._condition:
            if self._lifecycle in ("closed", "failed"):
                return
            if envelope.session_id != self._active_session_id:
                return
            if self._activating or self._recovering:
                self._buffered_events.append(envelope)
                return
            if envelope.sequence <= self._event_cursor:
                return
            if envelope.sequence != self._event_cursor + 1:
                if self._recovery_attempted:
                    fail = True
                    generation = self._generation
                    session_id = self._active_session_id
                else:
                    self._recovery_attempted = True
                    self._recovering = True
                    self._buffered_events.append(envelope)
                    recover = True
                    generation = self._generation
                    session_id = self._active_session_id
            else:
                self._event_cursor = envelope.sequence
                self._apply_event_lifecycle(envelope.event_kind)
                terminal = self._terminal_from_event(envelope)
                if terminal is not None:
                    self._terminal_outcome = terminal
                action = RuntimeAction(
                    "session_event",
                    {
                        "event": envelope.to_dict(),
                        "lifecycle": self._lifecycle,
                        "generation": self._generation,
                    },
                )
                self._condition.notify_all()
        if fail:
            self._fail_generation(
                generation,
                session_id,
                FailureRecord(
                    code="protocol_error",
                    message="session event sequence gap repeated after recovery",
                    retryable=False,
                    source="client_runtime",
                ),
            )
            return
        if recover:
            self._recover_generation(generation, session_id)
            return
        if action is not None:
            self._dispatch(action)

    def submit_user_message(
        self,
        session_id: str,
        text: str,
        stream: bool = True,
    ) -> None:
        selected_session_id = _required_session_id(session_id)
        with self._condition:
            self._assert_operable()
            if selected_session_id != self._active_session_id:
                raise ValueError("submitted session is not active")
            port = self._require_session_port()
            self._lifecycle = "submitting"
            self._terminal_outcome = None
            self._condition.notify_all()
        try:
            port.submit_user_message(selected_session_id, str(text), bool(stream))
        except Exception as exc:
            failure = _failure_for_error(exc)
            self._fail_generation(self.generation, selected_session_id, failure)
            raise

    def dispatch_command(
        self,
        shell: ShellDescriptor,
        name: str,
        args: Sequence[str],
        availability: Optional[Dict[str, Any]] = None,
        default_mode: str = "",
    ) -> Any:
        command = resolve_command(shell, name, availability)
        values = [str(item) for item in list(args or [])]
        dispatch = dict(command.dispatch)
        kind = str(dispatch.get("kind") or "")
        if kind == "session.command":
            command_name = str(dispatch.get("command") or "").strip().lstrip("/")
            if not command_name:
                raise UnsupportedShellDispatch("invalid_shell_dispatch:%s" % command.id)
            text = "/" + command_name
            if values:
                text += " " + " ".join(values)
            self.submit_user_message(self.active_session_id, text, stream=True)
            return command
        if kind == "session.create":
            return self.create_session(values[0] if values else default_mode)
        if kind == "session.select":
            return self.resume_session(
                values[0] if values else "latest",
                default_mode,
            )
        if kind == "session.cancel":
            return self.cancel_session(self.active_session_id)
        if kind == "session.rename":
            title = " ".join(values).strip()
            if not title:
                raise ValueError("shell_command_argument_required:title")
            return self.rename_session(self.active_session_id, title)
        if kind == "session.archive":
            return self.archive_session(self.active_session_id)
        if kind == "session.fork":
            return self.fork_session(self.active_session_id, " ".join(values).strip())
        if kind == "session.mode":
            if not values:
                raise ValueError("shell_command_argument_required:mode")
            return self.set_session_mode(self.active_session_id, values[0])
        if kind in ("shell.surface", "workspace.open", "interaction.respond"):
            self._dispatch(
                RuntimeAction(
                    "shell_command",
                    {
                        "command": command.to_dict(),
                        "dispatch": dispatch,
                        "args": values,
                    },
                )
            )
            return command
        raise UnsupportedShellDispatch("unsupported_shell_dispatch:%s" % kind)

    def wait_for_terminal(self, timeout_s: Optional[float] = None) -> RuntimeAction:
        if timeout_s is not None and timeout_s < 0:
            raise ValueError("timeout_s must be non-negative")
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        with self._condition:
            while self._terminal_outcome is None:
                if self._lifecycle == "closed":
                    raise RuntimeError("runtime_closed")
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return self._outcome_action(
                        "timeout",
                        failure=FailureRecord(
                            code="runtime_error",
                            message="session wait timed out",
                            retryable=True,
                            source="client_runtime",
                        ),
                    )
                self._condition.wait(remaining)
            return self._terminal_outcome

    def create_session(self, mode: str) -> SessionBootstrap:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        bootstrap = port.create_session(str(mode or ""))
        return self._install_returned_bootstrap(bootstrap, "create")

    def resume_session(self, reference: str, mode: str = "") -> SessionBootstrap:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        bootstrap = port.resume_session(str(reference or ""), str(mode or ""))
        return self._install_returned_bootstrap(bootstrap, "resume")

    def set_session_mode(self, session_id: str, mode: str) -> SessionBootstrap:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        bootstrap = port.set_session_mode(_required_session_id(session_id), str(mode or ""))
        return self._install_returned_bootstrap(bootstrap, "mode_changed")

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> SessionBootstrap:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        bootstrap = port.respond_to_interaction(
            _required_session_id(session_id),
            str(interaction_id or ""),
            dict(payload),
        )
        return self._install_returned_bootstrap(bootstrap, "interaction_response")

    def cancel_session(self, session_id: str) -> SessionBootstrap:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        bootstrap = port.cancel_session(_required_session_id(session_id))
        return self._install_returned_bootstrap(bootstrap, "cancel")

    def rename_session(self, session_id: str, title: str) -> ThreadShell:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return port.rename_session(_required_session_id(session_id), str(title or ""))

    def archive_session(self, session_id: str) -> ThreadShell:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return port.archive_session(_required_session_id(session_id))

    def fork_session(self, session_id: str, title: str = "") -> SessionBootstrap:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        thread = port.fork_session(_required_session_id(session_id), str(title or ""))
        if not isinstance(thread, ThreadShell):
            raise TypeError("session port must return a ThreadShell")
        activated = self.activate_session(thread.id, reason="fork")
        if activated is None:
            raise RuntimeError("forked session activation failed")
        return activated

    def close(self) -> None:
        with self._condition:
            if self._lifecycle == "closed":
                return
            port = self._session_port
            self._generation += 1
            self._lifecycle = "closed"
            self._activating = False
            self._recovering = False
            self._buffered_events = []
            self._condition.notify_all()
        if port is not None:
            port.close()
        self._dispatch(RuntimeAction("runtime_closed", {}))

    def _recover_generation(self, generation: int, session_id: str) -> None:
        try:
            port = self._require_session_port()
            bootstrap = port.get_session_bootstrap(session_id, "")
            self._validate_bootstrap(bootstrap, session_id)
        except Exception as exc:
            self._fail_generation(generation, session_id, _failure_for_error(exc))
            return
        self._install_bootstrap(generation, session_id, bootstrap, "recovery")

    def _install_bootstrap(
        self,
        generation: int,
        session_id: str,
        bootstrap: SessionBootstrap,
        reason: str,
    ) -> bool:
        with self._condition:
            if self._lifecycle == "closed" or generation != self._generation:
                return False
            self._event_cursor = bootstrap.event_cursor
            self._lifecycle = self._bootstrap_lifecycle(bootstrap)
            self._terminal_outcome = None
            self._activating = False
            self._recovering = False
            buffered = sorted(self._buffered_events, key=lambda item: item.sequence)
            self._buffered_events = []
            self._condition.notify_all()
        self._dispatch(
            RuntimeAction(
                "session_activated",
                {
                    "session_id": session_id,
                    "cursor": bootstrap.event_cursor,
                    "generation": generation,
                    "reason": str(reason or "activate"),
                    "bootstrap": bootstrap.to_dict(),
                },
            )
        )
        for envelope in buffered:
            self.on_session_event(envelope)
        return True

    def _fail_generation(
        self,
        generation: int,
        session_id: str,
        failure: FailureRecord,
    ) -> None:
        with self._condition:
            if self._lifecycle == "closed" or generation != self._generation:
                return
            self._lifecycle = "failed"
            self._activating = False
            self._recovering = False
            self._buffered_events = []
            self._terminal_outcome = self._outcome_action("failed", failure=failure)
            self._condition.notify_all()
        self._dispatch(
            RuntimeAction(
                "protocol_failed",
                {
                    "session_id": session_id,
                    "generation": generation,
                    "failure": failure.to_dict(),
                },
            )
        )

    def _validate_bootstrap(self, bootstrap: Any, session_id: str) -> None:
        if not isinstance(bootstrap, SessionBootstrap):
            raise TypeError("session port must return a SessionBootstrap")
        if bootstrap.schema_version != 1:
            raise ValueError("unsupported session bootstrap schema")
        snapshot_session_id = _required_session_id(bootstrap.snapshot.get("session_id"))
        if bootstrap.thread.id != session_id or snapshot_session_id != session_id:
            raise ValueError("session bootstrap id mismatch")

    def _bootstrap_lifecycle(self, bootstrap: SessionBootstrap) -> str:
        status = str(bootstrap.snapshot.get("status") or "")
        if bootstrap.thread.pending_interaction or status in (
            "waiting_permission",
            "waiting_user_input",
        ):
            return "waiting_interaction"
        return "ready"

    def _apply_event_lifecycle(self, event_kind: str) -> None:
        if event_kind in _INTERACTION_REQUEST_EVENTS:
            self._lifecycle = "waiting_interaction"
        elif event_kind in _INTERACTION_FINISH_EVENTS:
            self._lifecycle = "ready"
        elif event_kind == "session.error":
            self._lifecycle = "failed"

    def _terminal_from_event(
        self,
        envelope: SessionEventEnvelope,
    ) -> Optional[RuntimeAction]:
        payload = dict(envelope.payload)
        if envelope.event_kind in _INTERACTION_REQUEST_EVENTS:
            return self._outcome_action(
                "blocked",
                failure=FailureRecord(
                    code="interaction_required",
                    message="session interaction is required",
                    retryable=False,
                    source="session",
                ),
            )
        if envelope.event_kind == "session.error":
            try:
                failure = FailureRecord.from_dict(payload.get("failure"))
            except (TypeError, ValueError):
                failure = FailureRecord(
                    code="protocol_error",
                    message="session.error did not contain a valid failure",
                    retryable=False,
                    source="client_runtime",
                )
            return self._outcome_action("failed", failure=failure)
        if envelope.event_kind != "session.finished":
            return None
        outcome = payload.get("outcome") if isinstance(payload.get("outcome"), dict) else {}
        kind = str(outcome.get("kind") or "")
        reason = str(outcome.get("reason") or payload.get("termination_reason") or "")
        if kind == "completed" or outcome.get("is_success") is True:
            status = "completed"
            failure = None
        elif kind == "blocked":
            status = "blocked"
            failure = FailureRecord(
                code="interaction_required",
                message=str(outcome.get("message") or "session is blocked"),
                retryable=False,
                source="session",
            )
        elif kind == "cancelled" or reason in ("aborted", "cancelled"):
            status = "cancelled"
            failure = FailureRecord(
                code="cancelled",
                message=str(outcome.get("message") or "session was cancelled"),
                retryable=False,
                source="session",
            )
        else:
            status = "failed"
            failure = FailureRecord(
                code="runtime_error",
                message=str(outcome.get("message") or "session failed"),
                retryable=False,
                source="session",
            )
        return self._outcome_action(
            status,
            final_text=str(payload.get("final_text") or ""),
            outcome=outcome,
            failure=failure,
        )

    def _outcome_action(
        self,
        status: str,
        final_text: str = "",
        outcome: Optional[Dict[str, Any]] = None,
        failure: Optional[FailureRecord] = None,
    ) -> RuntimeAction:
        return RuntimeAction(
            "terminal_outcome",
            {
                "session_id": self._active_session_id,
                "status": status,
                "final_text": final_text,
                "outcome": dict(outcome or {}),
                "failure": failure.to_dict() if failure is not None else None,
            },
        )

    def _install_returned_bootstrap(
        self,
        bootstrap: SessionBootstrap,
        reason: str,
    ) -> SessionBootstrap:
        if not isinstance(bootstrap, SessionBootstrap):
            raise TypeError("session port must return a SessionBootstrap")
        session_id = _required_session_id(bootstrap.thread.id)
        self._validate_bootstrap(bootstrap, session_id)
        with self._condition:
            self._assert_operable()
            self._generation += 1
            generation = self._generation
            self._active_session_id = session_id
            self._event_cursor = 0
            self._lifecycle = "activating"
            self._activating = True
            self._recovering = False
            self._recovery_attempted = False
            self._buffered_events = []
            self._terminal_outcome = None
        self._install_bootstrap(generation, session_id, bootstrap, reason)
        return bootstrap

    def _assert_operable(self) -> None:
        if self._lifecycle == "closed":
            raise RuntimeError("runtime_closed")
        if self._lifecycle == "failed":
            raise RuntimeError("runtime_failed")

    def _require_session_port(self) -> FrontendSessionPort:
        if self._session_port is None:
            raise RuntimeError("session port is not bound")
        return self._session_port
