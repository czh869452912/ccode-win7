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

    def _take_response(self, operation):
        self.bootstrap_calls.append(operation)
        response = self.responses.pop(0)
        callback, self.during_bootstrap = self.during_bootstrap, None
        if callback is not None:
            callback()
        if isinstance(response, BaseException):
            raise response
        return response

    def get_session_bootstrap(self, reference, mode=""):
        return self._take_response(("activate", reference, mode))

    def create_session(self, mode=""):
        return self._take_response(("create", mode))

    def set_session_mode(self, session_id, mode):
        return self._take_response(("mode", session_id, mode))

    def cancel_session(self, session_id):
        return self._take_response(("cancel", session_id))

    def respond_to_interaction(self, session_id, interaction_id, payload):
        return self._take_response(
            ("interaction_response", session_id, interaction_id, payload)
        )

    def close(self):
        self.closed = True


def _load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _bootstrap(contract, name, strict=True):
    value = contract["bootstraps"][name]
    return SessionBootstrap.from_dict(value) if strict else dict(value)


def _event(contract, name):
    return SessionEventEnvelope.from_dict(contract["events"][name])


def _port_error(code, message):
    return FrontendPortError(
        FailureRecord(
            code=code,
            message=message,
            retryable=False,
            source="session",
        )
    )


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
                if nested.get("request_error"):
                    port.responses.append(
                        _port_error(nested["request_error"], "activation failed")
                    )
                else:
                    port.responses.append(_bootstrap(contract, nested["bootstrap"]))
                port.during_bootstrap = lambda value=nested: runtime.activate_session(
                    value["session_id"]
                )
            runtime.activate_session(operation["session_id"])
            continue
        if kind in ("bootstrap_operation", "bootstrap_operation_raw"):
            if operation.get("request_error"):
                port.responses.append(
                    _port_error(operation["request_error"], "request failed")
                )
            else:
                port.responses.append(
                    _bootstrap(
                        contract,
                        operation["bootstrap"],
                        strict=kind == "bootstrap_operation",
                    )
                )

            def during_request(value=operation):
                for event_name in value.get("during_events", []):
                    runtime.on_session_event(_event(contract, event_name))
                nested = value.get("during_activation")
                if nested:
                    if nested.get("request_error"):
                        port.responses.append(
                            _port_error(
                                nested["request_error"],
                                "activation failed",
                            )
                        )
                    else:
                        port.responses.append(
                            _bootstrap(contract, nested["bootstrap"])
                        )
                    runtime.activate_session(nested["session_id"])
                if value.get("during_close"):
                    runtime.close()

            port.during_bootstrap = during_request
            operation_name = operation["operation"]
            if operation_name == "interaction_response":
                invoke = lambda: runtime.respond_to_interaction(
                    operation["session_id"],
                    "approval-1",
                    {"decision": "accept"},
                )
            elif operation_name == "create":
                invoke = lambda: runtime.create_session("explore")
            elif operation_name == "mode":
                invoke = lambda: runtime.set_session_mode(
                    operation["session_id"], "verify"
                )
            elif operation_name == "cancel":
                invoke = lambda: runtime.cancel_session(operation["session_id"])
            else:
                raise AssertionError(
                    "unknown bootstrap fixture operation: %s" % operation_name
                )

            if operation.get("expect_stale"):
                with pytest.raises(
                    RuntimeError, match="bootstrap_transaction_superseded"
                ):
                    invoke()
            elif operation.get("expect_error"):
                expected_error = (
                    FrontendPortError
                    if operation.get("request_error")
                    else (TypeError, ValueError)
                )
                with pytest.raises(expected_error):
                    invoke()
            else:
                invoke()
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
        runtime, _port, actions = _run_case(contract, case)
        assert actions == case["actions"], case["name"]
        if "final" in case:
            terminal = runtime._terminal_outcome
            actual = {
                "session_id": runtime.active_session_id,
                "cursor": runtime.event_cursor,
                "generation": runtime.generation,
                "lifecycle": runtime.lifecycle,
                "terminal_status": (
                    None if terminal is None else terminal.to_dict()["status"]
                ),
            }
            assert actual == case["final"], case["name"]


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
