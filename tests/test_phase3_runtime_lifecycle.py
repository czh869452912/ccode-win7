import threading
import time

import pytest


def test_registration_scope_exposes_owner_and_immutable_observation():
    from embedagent_core.registration_scope import RegistrationScope

    scope = RegistrationScope("runtime", owner_id="adapter-1")
    child = scope.create_child("session", owner_id="session-1")
    scope.register(lambda: None)

    assert scope.owner_id == "adapter-1"
    assert child.owner_id == "session-1"
    assert scope.snapshot() == {
        "scope_id": "runtime",
        "owner_id": "adapter-1",
        "state": "active",
        "active_operations": 0,
        "registration_count": 1,
        "child_count": 1,
    }

    child.dispose()
    scope.dispose()


def test_concurrent_scope_dispose_waits_for_one_completion_barrier():
    from embedagent_core.registration_scope import RegistrationScope

    entered = threading.Event()
    release = threading.Event()
    calls = []
    scope = RegistrationScope("runtime")

    def disposer():
        entered.set()
        release.wait(2.0)
        calls.append("disposed")

    scope.register(disposer)
    errors = []

    def close():
        try:
            scope.dispose()
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=close)
    second = threading.Thread(target=close)
    first.start()
    assert entered.wait(1.0)
    second.start()
    time.sleep(0.05)
    assert second.is_alive()
    release.set()
    first.join(1.0)
    second.join(1.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert calls == ["disposed"]
    assert scope.state == "disposed"


def test_adapter_shutdown_is_idempotent_and_rejects_new_admission(tmp_path):
    from embedagent_host.inprocess_adapter import InProcessAdapter
    from embedagent_host.runtime.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.create_session("build")

    adapter.shutdown()
    adapter.shutdown()

    assert adapter._runtime_scope.state == "disposed"
    assert adapter._sessions == {}
    with pytest.raises(RuntimeError, match="closed"):
        adapter.create_session("build")


def test_concurrent_adapter_shutdown_shares_completion_barrier(tmp_path):
    from embedagent_host.inprocess_adapter import InProcessAdapter
    from embedagent_host.runtime.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.create_session("build")
    entered = threading.Event()
    release = threading.Event()

    def slow_dispose():
        entered.set()
        release.wait(2.0)

    adapter._runtime_scope.register(slow_dispose)
    errors = []

    def close():
        try:
            adapter.shutdown(timeout=2.0)
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=close)
    second = threading.Thread(target=close)
    first.start()
    assert entered.wait(1.0)
    second.start()
    time.sleep(0.05)
    assert second.is_alive()
    release.set()
    first.join(2.0)
    second.join(2.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert adapter._closed is True
    assert adapter._sessions == {}
