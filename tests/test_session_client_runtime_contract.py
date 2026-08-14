from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from embedagent_host.frontend_errors import FrontendPortError
from embedagent_protocol import FailureRecord, SessionBootstrap, SessionEventEnvelope

from embedagent.frontend.runtime import RuntimeAction, SessionClientRuntime

CONTRACT_PATH = Path(__file__).parent / "fixtures" / "session_client_runtime" / "contract.json"


class FakeSessionPort(object):
    def __init__(self, runtime):
        self.runtime = runtime
        self.responses = []
        self.during_bootstrap = None
        self.bootstrap_calls = []
        self.closed = False

    def get_session_bootstrap(self, reference, mode=""):
        self.bootstrap_calls.append((reference, mode))
        response = self.responses.pop(0)
        callback, self.during_bootstrap = self.during_bootstrap, None
        if callback is not None:
            callback()
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self):
        self.closed = True


def _load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _bootstrap(contract, name, strict=True):
    value = contract["bootstraps"][name]
    return SessionBootstrap.from_dict(value) if strict else dict(value)


def _event(contract, name):
    return SessionEventEnvelope.from_dict(contract["events"][name])


def _observable(action):
    value = action.to_dict()
    kind = value["kind"]
    if kind == "session_activated":
        return {
            "kind": kind,
            "session_id": value["session_id"],
            "cursor": value["cursor"],
            "generation": value["generation"],
            "reason": value["reason"],
        }
    if kind == "session_event":
        event = value["event"]
        return {
            "kind": kind,
            "session_id": event["session_id"],
            "sequence": event["sequence"],
            "event_kind": event["event_kind"],
            "lifecycle": value["lifecycle"],
        }
    if kind == "protocol_failed":
        return {
            "kind": kind,
            "session_id": value["session_id"],
            "generation": value["generation"],
            "code": value["failure"]["code"],
        }
    return {"kind": kind}


def _run_case(contract, case):
    actions = []
    runtime = SessionClientRuntime(dispatch=actions.append)
    port = FakeSessionPort(runtime)
    runtime.bind_session_port(port)
    assert runtime.lifecycle == case["initial"]["lifecycle"]
    assert runtime.generation == case["initial"]["generation"]
    assert runtime.event_cursor == case["initial"]["cursor"]

    for operation in case["operations"]:
        kind = operation["kind"]
        if kind in ("activate", "activate_raw"):
            strict = kind == "activate"
            port.responses.append(_bootstrap(contract, operation["bootstrap"], strict=strict))
            if operation.get("during_event"):
                port.during_bootstrap = lambda name=operation["during_event"]: (
                    runtime.on_session_event(_event(contract, name))
                )
            nested = operation.get("during_activation")
            if nested:
                port.responses.append(_bootstrap(contract, nested["bootstrap"]))
                port.during_bootstrap = lambda value=nested: runtime.activate_session(
                    value["session_id"]
                )
            runtime.activate_session(operation["session_id"])
            continue
        if kind == "event":
            if operation.get("recovery_bootstrap"):
                port.responses.append(_bootstrap(contract, operation["recovery_bootstrap"]))
            if operation.get("recovery_error"):
                port.responses.append(
                    FrontendPortError(
                        FailureRecord(
                            code=operation["recovery_error"],
                            message="recovery failed",
                            retryable=False,
                            source="session",
                        )
                    )
                )
            runtime.on_session_event(_event(contract, operation["event"]))
            continue
        if kind == "close":
            runtime.close()
            continue
        raise AssertionError("unknown fixture operation: %s" % kind)

    return runtime, port, [_observable(action) for action in actions]


def test_python_runtime_matches_cross_language_contract():
    contract = _load_contract()

    assert contract["schema_version"] == 1
    for case in contract["cases"]:
        _runtime, _port, actions = _run_case(contract, case)
        assert actions == case["actions"], case["name"]


def test_runtime_actions_are_deeply_frozen():
    action = RuntimeAction("test", {"nested": {"value": 1}})

    with pytest.raises(FrozenInstanceError):
        action.kind = "changed"
    with pytest.raises(TypeError):
        action.payload["nested"]["value"] = 2


def test_runtime_binds_one_port_and_rejects_operations_after_close():
    runtime = SessionClientRuntime()
    port = FakeSessionPort(runtime)
    runtime.bind_session_port(port)

    with pytest.raises(RuntimeError, match="already bound"):
        runtime.bind_session_port(FakeSessionPort(runtime))

    runtime.close()
    assert port.closed is True
    with pytest.raises(RuntimeError, match="runtime_closed"):
        runtime.activate_session("session-1")
