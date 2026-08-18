import threading

import pytest
from embedagent_core.registration_scope import (
    RegistrationScope,
    ScopeDisposeError,
    ScopeStateError,
)


def test_scope_disposes_owned_effects_in_reverse_registration_order_once():
    calls = []
    scope = RegistrationScope("runtime")

    scope.register(lambda: calls.append("first"))
    scope.register(lambda: calls.append("second"))
    scope.register(lambda: calls.append("third"))

    scope.dispose()
    scope.dispose()

    assert calls == ["third", "second", "first"]
    assert scope.state == RegistrationScope.DISPOSED


def test_child_scope_is_disposed_before_parent_scope():
    calls = []
    parent = RegistrationScope("runtime")
    child = parent.create_child("session")

    parent.register(lambda: calls.append("parent"))
    child.register(lambda: calls.append("child"))

    parent.dispose()

    assert calls == ["child", "parent"]
    assert child.state == RegistrationScope.DISPOSED
    assert parent.state == RegistrationScope.DISPOSED


def test_scope_rejects_new_registration_and_operations_after_quiescence():
    scope = RegistrationScope("runtime")

    scope.quiesce()

    with pytest.raises(ScopeStateError):
        scope.register(lambda: None)
    with pytest.raises(ScopeStateError):
        with scope.operation():
            pass

    assert scope.state == RegistrationScope.QUIESCING
    scope.dispose()


def test_scope_waits_for_admitted_operations_before_disposal():
    entered = threading.Event()
    release = threading.Event()
    calls = []
    scope = RegistrationScope("runtime")

    def worker():
        with scope.operation():
            entered.set()
            release.wait(2.0)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(1.0)

    scope.quiesce()
    assert scope.wait_for_quiescence(0.01) is False

    release.set()
    thread.join(1.0)
    assert not thread.is_alive()
    assert scope.wait_for_quiescence(1.0) is True

    scope.dispose()
    assert calls == []


def test_scope_transaction_rolls_back_only_new_effects():
    calls = []
    scope = RegistrationScope("runtime")
    scope.register(lambda: calls.append("before"))

    with pytest.raises(ValueError):
        with scope.transaction():
            scope.register(lambda: calls.append("new-first"))
            scope.register(lambda: calls.append("new-second"))
            raise ValueError("setup failed")

    assert calls == ["new-second", "new-first"]
    scope.dispose()
    assert calls == ["new-second", "new-first", "before"]


def test_scope_dispose_continues_after_a_disposer_failure():
    calls = []
    scope = RegistrationScope("runtime")

    def broken():
        calls.append("broken")
        raise RuntimeError("close failed")

    scope.register(lambda: calls.append("last"))
    scope.register(broken)
    scope.register(lambda: calls.append("first"))

    with pytest.raises(ScopeDisposeError) as error:
        scope.dispose()

    assert calls == ["first", "broken", "last"]
    assert len(error.value.failures) == 1
    assert scope.state == RegistrationScope.DISPOSED
    scope.dispose()


def test_event_bus_registration_returns_an_idempotent_disposer():
    from embedagent_core.agent_event_bus import AgentEvent, AgentEventBus

    calls = []
    bus = AgentEventBus()
    dispose = bus.register_reducer(
        "extension.context",
        "test-extension",
        "project",
        lambda event, context: calls.append((event.event_type, context)),
    )

    assert callable(dispose)
    dispose()
    dispose()
    bus.dispatch(AgentEvent("extension.context"), context={"workspace": "."})

    assert calls == []
