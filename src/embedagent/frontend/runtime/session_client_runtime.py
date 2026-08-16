from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from embedagent_protocol import (
    CapabilitySnapshot,
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
_SYNC_IDLE = "idle"
_SYNC_BOOTSTRAP = "bootstrap"
_SYNC_RECOVERY = "recovery"
_SYNC_PUBLICATION = "publication"


@dataclass(frozen=True)
class _RuntimeBaseline:
    active_session_id: str
    event_cursor: int
    lifecycle: str
    recovery_attempted: bool
    terminal_outcome: Optional[RuntimeAction]


@dataclass(frozen=True)
class _EventPublication:
    generation: int
    envelope: SessionEventEnvelope
    lifecycle: str
    terminal_outcome: Optional[RuntimeAction]
    action: RuntimeAction


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
        if dispatch is not None and not callable(dispatch):
            raise TypeError("dispatch must be callable")
        self._dispatch = dispatch
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._session_port = None  # type: Optional[FrontendSessionPort]
        self._active_session_id = ""
        self._event_cursor = 0
        self._generation = 0
        self._lifecycle = "idle"
        self._sync_phase = _SYNC_IDLE
        self._recovery_attempted = False
        self._event_queue: List[SessionEventEnvelope] = []
        self._terminal_outcome = None  # type: Optional[RuntimeAction]
        self._transaction_baseline = None  # type: Optional[_RuntimeBaseline]

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

    def bind_dispatch(self, dispatch: Callable[[RuntimeAction], None]) -> None:
        if not callable(dispatch):
            raise TypeError("dispatch must be callable")
        with self._condition:
            self._assert_operable()
            if self._dispatch is not None:
                raise RuntimeError("runtime dispatch is already bound")
            self._dispatch = dispatch

    def list_sessions(self, limit: int = 10) -> List[ThreadShell]:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return port.list_sessions(limit=max(1, int(limit)))

    def load_session_summary(self, reference: str) -> Dict[str, Any]:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return port.load_session_summary(str(reference or ""))

    def get_session_capabilities(self, session_id: str = "") -> CapabilitySnapshot:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return port.get_session_capabilities(str(session_id or ""))

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
        try:
            return self._run_bootstrap_transaction(
                session_id,
                reason,
                lambda: port.get_session_bootstrap(session_id, mode),
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            return None

    def on_session_event(self, envelope: SessionEventEnvelope) -> None:
        if not isinstance(envelope, SessionEventEnvelope):
            raise TypeError("envelope must be a SessionEventEnvelope")
        with self._condition:
            if self._lifecycle in ("closed", "failed"):
                return
            if self._sync_phase in (_SYNC_BOOTSTRAP, _SYNC_RECOVERY):
                self._event_queue.append(envelope)
                return
            if envelope.session_id != self._active_session_id:
                return
            if envelope.sequence <= self._event_cursor:
                return
            self._event_queue.append(envelope)
            if self._sync_phase == _SYNC_PUBLICATION:
                return
            self._sync_phase = _SYNC_PUBLICATION
            generation = self._generation
            session_id = self._active_session_id
        self._drain_event_queue(generation, session_id)

    def _prepare_event_publication_locked(
        self,
        envelope: SessionEventEnvelope,
    ) -> _EventPublication:
        lifecycle = self._event_lifecycle(self._lifecycle, envelope.event_kind)
        terminal_outcome = self._reduce_terminal_outcome(
            self._terminal_outcome,
            envelope,
        )
        return _EventPublication(
            generation=self._generation,
            envelope=envelope,
            lifecycle=lifecycle,
            terminal_outcome=terminal_outcome,
            action=RuntimeAction(
                "session_event",
                {
                    "event": envelope.to_dict(),
                    "lifecycle": lifecycle,
                    "generation": self._generation,
                },
            ),
        )

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
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
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
            self._dispatch_action(
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
        return self._run_bootstrap_transaction(
            "",
            "create",
            lambda: port.create_session(str(mode or "")),
        )

    def resume_session(self, reference: str, mode: str = "") -> SessionBootstrap:
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return self._run_bootstrap_transaction(
            "",
            "resume",
            lambda: port.resume_session(str(reference or ""), str(mode or "")),
        )

    def set_session_mode(self, session_id: str, mode: str) -> SessionBootstrap:
        selected_session_id = _required_session_id(session_id)
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return self._run_bootstrap_transaction(
            selected_session_id,
            "mode_changed",
            lambda: port.set_session_mode(selected_session_id, str(mode or "")),
        )

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> SessionBootstrap:
        selected_session_id = _required_session_id(session_id)
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return self._run_bootstrap_transaction(
            selected_session_id,
            "interaction_response",
            lambda: port.respond_to_interaction(
                selected_session_id,
                str(interaction_id or ""),
                dict(payload),
            ),
        )

    def cancel_session(self, session_id: str) -> SessionBootstrap:
        selected_session_id = _required_session_id(session_id)
        with self._condition:
            self._assert_operable()
            port = self._require_session_port()
        return self._run_bootstrap_transaction(
            selected_session_id,
            "cancel",
            lambda: port.cancel_session(selected_session_id),
        )

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
            self._sync_phase = _SYNC_IDLE
            self._event_queue = []
            self._transaction_baseline = None
            self._condition.notify_all()
        if port is not None:
            port.close()
        self._dispatch_action(RuntimeAction("runtime_closed", {}))

    def _begin_bootstrap_transaction(self, target_session_id: str) -> int:
        with self._condition:
            self._assert_operable()
            if self._transaction_baseline is None:
                self._transaction_baseline = _RuntimeBaseline(
                    active_session_id=self._active_session_id,
                    event_cursor=self._event_cursor,
                    lifecycle=self._lifecycle,
                    recovery_attempted=self._recovery_attempted,
                    terminal_outcome=self._terminal_outcome,
                )
            self._generation += 1
            generation = self._generation
            self._active_session_id = str(target_session_id or "")
            self._event_cursor = 0
            self._lifecycle = "activating"
            self._sync_phase = _SYNC_BOOTSTRAP
            self._recovery_attempted = False
            self._terminal_outcome = None
            self._condition.notify_all()
            return generation

    def _rollback_bootstrap_transaction(self, generation: int) -> None:
        with self._condition:
            if self._lifecycle == "closed" or generation != self._generation:
                return
            baseline = self._transaction_baseline
            if baseline is None:
                return
            self._active_session_id = baseline.active_session_id
            self._event_cursor = baseline.event_cursor
            self._lifecycle = baseline.lifecycle
            self._sync_phase = _SYNC_BOOTSTRAP
            self._recovery_attempted = baseline.recovery_attempted
            self._terminal_outcome = baseline.terminal_outcome
            self._event_queue = [
                envelope
                for envelope in self._event_queue
                if envelope.session_id == baseline.active_session_id
            ]
            self._condition.notify_all()
        self._drain_event_queue(generation, baseline.active_session_id)

    def _run_bootstrap_transaction(
        self,
        target_session_id: str,
        reason: str,
        request: Callable[[], SessionBootstrap],
    ) -> SessionBootstrap:
        generation = self._begin_bootstrap_transaction(target_session_id)
        try:
            bootstrap = request()
        except (OSError, RuntimeError, TypeError, ValueError):
            self._rollback_bootstrap_transaction(generation)
            raise
        try:
            if not isinstance(bootstrap, SessionBootstrap):
                raise TypeError("session port must return a SessionBootstrap")
            session_id = target_session_id or _required_session_id(bootstrap.thread.id)
            self._validate_bootstrap(bootstrap, session_id)
        except (TypeError, ValueError) as exc:
            self._fail_generation(
                generation,
                target_session_id,
                _failure_for_error(exc),
            )
            raise
        if not self._install_bootstrap(generation, session_id, bootstrap, reason):
            raise RuntimeError("bootstrap_transaction_superseded")
        return bootstrap

    def _recover_generation(self, generation: int, session_id: str) -> None:
        try:
            port = self._require_session_port()
            bootstrap = port.get_session_bootstrap(session_id, "")
            self._validate_bootstrap(bootstrap, session_id)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self._fail_generation(generation, session_id, _failure_for_error(exc))
            return
        self._install_bootstrap(generation, session_id, bootstrap, "recovery")

    def _drain_event_queue(self, generation: int, session_id: str) -> bool:
        while True:
            publication = None  # type: Optional[_EventPublication]
            recover = False
            fail = False
            with self._condition:
                if self._lifecycle == "closed" or generation != self._generation:
                    return False
                matching = sorted(
                    (
                        envelope
                        for envelope in self._event_queue
                        if envelope.session_id == session_id
                    ),
                    key=lambda item: item.sequence,
                )
                pending = [
                    envelope for envelope in matching if envelope.sequence > self._event_cursor
                ]
                self._event_queue = pending
                if not pending:
                    self._sync_phase = _SYNC_IDLE
                    self._transaction_baseline = None
                    self._condition.notify_all()
                    return True
                envelope = pending[0]
                if envelope.sequence != self._event_cursor + 1:
                    if self._recovery_attempted:
                        fail = True
                    else:
                        self._recovery_attempted = True
                        self._sync_phase = _SYNC_RECOVERY
                        recover = True
                else:
                    self._event_queue = pending[1:]
                    publication = self._prepare_event_publication_locked(envelope)
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
                return True
            if recover:
                self._recover_generation(generation, session_id)
                return True
            if publication is None:
                continue
            try:
                self._dispatch_action(publication.action)
            except (OSError, RuntimeError, TypeError, ValueError):
                self._commit_dispatch_failure(publication)
                return True
            with self._condition:
                if self._lifecycle == "closed" or generation != self._generation:
                    return False
                self._event_cursor = publication.envelope.sequence
                self._lifecycle = publication.lifecycle
                self._terminal_outcome = publication.terminal_outcome
                self._condition.notify_all()

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
            matching = sorted(
                (envelope for envelope in self._event_queue if envelope.session_id == session_id),
                key=lambda item: item.sequence,
            )
            terminal_outcome = None  # type: Optional[RuntimeAction]
            for envelope in matching:
                if envelope.sequence <= bootstrap.event_cursor:
                    terminal_outcome = self._reduce_terminal_outcome(
                        terminal_outcome,
                        envelope,
                    )
            self._event_queue = [
                envelope for envelope in matching if envelope.sequence > bootstrap.event_cursor
            ]
            lifecycle = self._bootstrap_lifecycle(bootstrap)
        action = RuntimeAction(
            "session_activated",
            {
                "session_id": session_id,
                "cursor": bootstrap.event_cursor,
                "generation": generation,
                "reason": str(reason or "activate"),
                "bootstrap": bootstrap.to_dict(),
            },
        )
        try:
            self._dispatch_action(action)
        except (OSError, RuntimeError, TypeError, ValueError):
            self._commit_action_failure(generation, session_id)
            return True
        with self._condition:
            if self._lifecycle == "closed" or generation != self._generation:
                return False
            self._active_session_id = session_id
            self._event_cursor = bootstrap.event_cursor
            self._lifecycle = lifecycle
            self._terminal_outcome = terminal_outcome
            self._condition.notify_all()
        return self._drain_event_queue(generation, session_id)

    def _fail_generation(
        self,
        generation: int,
        session_id: str,
        failure: FailureRecord,
    ) -> None:
        with self._condition:
            if self._lifecycle == "closed" or generation != self._generation:
                return
            self._sync_phase = _SYNC_PUBLICATION
            self._event_queue = []
            self._transaction_baseline = None
        action = RuntimeAction(
            "protocol_failed",
            {
                "session_id": session_id,
                "generation": generation,
                "failure": failure.to_dict(),
            },
        )
        try:
            self._dispatch_action(action)
        except (OSError, RuntimeError, TypeError, ValueError):
            pass
        with self._condition:
            if self._lifecycle == "closed" or generation != self._generation:
                return
            self._lifecycle = "failed"
            self._sync_phase = _SYNC_IDLE
            self._event_queue = []
            self._terminal_outcome = self._outcome_action("failed", failure=failure)
            self._condition.notify_all()

    def _commit_dispatch_failure(self, publication: _EventPublication) -> None:
        self._commit_action_failure(
            publication.generation,
            publication.envelope.session_id,
        )

    def _commit_action_failure(self, generation: int, session_id: str) -> None:
        failure = FailureRecord(
            code="protocol_error",
            message="runtime action dispatch failed",
            retryable=False,
            source="client_runtime",
        )
        with self._condition:
            if self._lifecycle == "closed" or generation != self._generation:
                return
            self._active_session_id = session_id
            self._lifecycle = "failed"
            self._sync_phase = _SYNC_IDLE
            self._event_queue = []
            self._transaction_baseline = None
            self._terminal_outcome = self._outcome_action("failed", failure=failure)
            self._condition.notify_all()

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
        if status in ("error", "failed"):
            return "failed"
        if bootstrap.thread.pending_interaction or status in (
            "waiting_permission",
            "waiting_user_input",
        ):
            return "waiting_interaction"
        return "ready"

    def _event_lifecycle(self, current: str, event_kind: str) -> str:
        if event_kind in _INTERACTION_REQUEST_EVENTS:
            return "waiting_interaction"
        if event_kind in _INTERACTION_FINISH_EVENTS or event_kind == "session.finished":
            return "ready"
        if event_kind == "session.error":
            return "failed"
        return current

    def _reduce_terminal_outcome(
        self,
        current: Optional[RuntimeAction],
        envelope: SessionEventEnvelope,
    ) -> Optional[RuntimeAction]:
        if envelope.event_kind in _INTERACTION_FINISH_EVENTS:
            return None
        terminal = self._terminal_from_event(envelope)
        return terminal if terminal is not None else current

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

    def _assert_operable(self) -> None:
        if self._lifecycle == "closed":
            raise RuntimeError("runtime_closed")
        if self._lifecycle == "failed":
            raise RuntimeError("runtime_failed")

    def _dispatch_action(self, action: RuntimeAction) -> None:
        dispatch = self._dispatch
        if dispatch is not None:
            dispatch(action)

    def _require_session_port(self) -> FrontendSessionPort:
        if self._session_port is None:
            raise RuntimeError("session port is not bound")
        return self._session_port
