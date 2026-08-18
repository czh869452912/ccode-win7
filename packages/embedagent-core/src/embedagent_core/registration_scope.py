from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Callable, Iterator, List, Optional

Disposer = Callable[[], None]


class ScopeStateError(RuntimeError):
    """Raised when a scope operation is attempted after admission closes."""


class ScopeDisposeError(RuntimeError):
    """Raised after disposal has attempted every owned effect."""

    def __init__(self, failures: List[BaseException]) -> None:
        super(ScopeDisposeError, self).__init__("%d scope disposer(s) failed" % len(failures))
        self.failures = tuple(failures)


class _Registration(object):
    def __init__(self, disposer: Disposer) -> None:
        self.disposer = disposer
        self.active = True


class RegistrationScope(object):
    """Small synchronous lifecycle boundary for owned runtime registrations.

    The scope deliberately does not resolve dependencies or retain arbitrary
    services. It only owns reversible registrations and controls admission of
    in-flight operations while the owner is being torn down.
    """

    ACTIVE = "active"
    QUIESCING = "quiescing"
    DISPOSED = "disposed"

    def __init__(self, scope_id: str, parent: Optional["RegistrationScope"] = None) -> None:
        normalized_id = str(scope_id or "").strip()
        if not normalized_id:
            raise ValueError("scope id is required")
        self._scope_id = normalized_id
        self._parent = parent
        self._lock = threading.RLock()
        self._state = self.ACTIVE
        self._registrations = []  # type: List[_Registration]
        self._children = []  # type: List[RegistrationScope]
        self._active_operations = 0
        self._quiescent = threading.Event()
        self._quiescent.set()
        self._dispose_complete = threading.Event()
        self._disposing = False
        self._disposing_thread = None  # type: Optional[int]
        if parent is not None:
            with parent._lock:
                parent._require_active()
                parent._children.append(self)

    @property
    def scope_id(self) -> str:
        return self._scope_id

    @property
    def parent(self) -> Optional["RegistrationScope"]:
        return self._parent

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def register(self, disposer: Disposer) -> Disposer:
        if not callable(disposer):
            raise TypeError("scope disposer must be callable")
        registration = _Registration(disposer)
        with self._lock:
            self._require_active()
            self._registrations.append(registration)

        def dispose_once() -> None:
            with self._lock:
                if not registration.active:
                    return
                registration.active = False
                self._remove_registration(registration)
            registration.disposer()

        return dispose_once

    def create_child(self, scope_id: str) -> "RegistrationScope":
        return RegistrationScope(scope_id, parent=self)

    @contextmanager
    def transaction(self) -> Iterator["RegistrationScope"]:
        """Rollback registrations created in the failed transaction."""

        with self._lock:
            self._require_active()
            checkpoint = len(self._registrations)
        try:
            yield self
        except BaseException as original:
            failures = self._rollback_from(checkpoint)
            if failures:
                raise ScopeDisposeError(failures) from original
            raise

    @contextmanager
    def operation(self) -> Iterator[None]:
        """Admit one in-flight operation until the scope quiesces."""

        with self._lock:
            self._require_active()
            self._active_operations += 1
            self._quiescent.clear()
        try:
            yield None
        finally:
            with self._lock:
                self._active_operations -= 1
                if self._active_operations == 0:
                    self._quiescent.set()

    def quiesce(self) -> None:
        """Stop new admission in this scope and all current child scopes."""

        with self._lock:
            if self._state == self.DISPOSED:
                return
            if self._state == self.ACTIVE:
                self._state = self.QUIESCING
                if self._active_operations == 0:
                    self._quiescent.set()
            children = list(self._children)
        for child in children:
            child.quiesce()

    def wait_for_quiescence(self, timeout: Optional[float] = None) -> bool:
        return self._quiescent.wait(timeout)

    def dispose(self) -> None:
        """Dispose children and registrations in reverse ownership order."""

        current_thread = threading.get_ident()
        with self._lock:
            if self._state == self.DISPOSED:
                return
            if self._disposing:
                if self._disposing_thread == current_thread:
                    return
                wait_for = self._dispose_complete
                owner = False
            else:
                self._disposing = True
                self._disposing_thread = current_thread
                self._state = self.QUIESCING
                if self._active_operations == 0:
                    self._quiescent.set()
                children = list(self._children)
                registrations = list(self._registrations)
                self._registrations = []
                for registration in registrations:
                    registration.active = False
                wait_for = None
                owner = True

        if not owner:
            wait_for.wait()
            return

        failures = []  # type: List[BaseException]
        for child in reversed(children):
            try:
                child.dispose()
            except ScopeDisposeError as error:
                failures.extend(error.failures)
            except BaseException as error:
                failures.append(error)

        self.wait_for_quiescence()
        for registration in reversed(registrations):
            try:
                registration.disposer()
            except BaseException as error:
                failures.append(error)

        with self._lock:
            self._state = self.DISPOSED
            self._disposing = False
            self._disposing_thread = None
            self._dispose_complete.set()
            parent = self._parent
        if parent is not None:
            parent._remove_child(self)
        if failures:
            raise ScopeDisposeError(failures)

    close = dispose

    def _rollback_from(self, checkpoint: int) -> List[BaseException]:
        with self._lock:
            registrations = self._registrations[checkpoint:]
            del self._registrations[checkpoint:]
            for registration in registrations:
                registration.active = False
        failures = []  # type: List[BaseException]
        for registration in reversed(registrations):
            try:
                registration.disposer()
            except BaseException as error:
                failures.append(error)
        return failures

    def _require_active(self) -> None:
        if self._state != self.ACTIVE:
            raise ScopeStateError("scope %s is %s" % (self._scope_id, self._state))

    def _remove_registration(self, registration: _Registration) -> None:
        for index, current in enumerate(self._registrations):
            if current is registration:
                self._registrations.pop(index)
                return

    def _remove_child(self, child: "RegistrationScope") -> None:
        with self._lock:
            self._children = [item for item in self._children if item is not child]
