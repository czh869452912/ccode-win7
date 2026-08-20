from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from embedagent_host.frontend_errors import FrontendPortError
from embedagent_protocol import FailureRecord, SessionBootstrap, SessionEventEnvelope, ThreadShell

from embedagent.frontend.runtime import RuntimeAction, SessionClientRuntime

CONTRACT_PATH = Path(__file__).parent / "fixtures" / "session_client_runtime" / "contract.json"


class FakeSessionPort(object):
    def __init__(self, runtime):
        self.runtime = runtime
        self.responses = []
        self.during_bootstrap = None
        self.bootstrap_calls = []
        self.message_calls = []
        self.fork_calls = []
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

    def submit_user_message(self, session_id, text, stream):
        self.message_calls.append((session_id, text, stream))
        return self._take_response(("message", session_id, text, stream))

    def respond_to_interaction(self, session_id, interaction_id, payload):
        return self._take_response(("interaction_response", session_id, interaction_id, payload))

    def fork_session(self, session_id, title=""):
        self.fork_calls.append((session_id, title))
        return self._take_response(("fork", session_id, title))

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
    observations = []
    dispatch_injections = []
    runtime = None

    def dispatch(action):
        actions.append(action)
        observed = _observable(action)
        for injection in dispatch_injections:
            if injection["used"]:
                continue
            if all(observed.get(key) == value for key, value in injection["match"].items()):
                injection["used"] = True
                if injection["observation"]:
                    terminal = runtime._terminal_outcome
                    observations.append(
                        {
                            "name": injection["observation"],
                            "cursor": runtime.event_cursor,
                            "lifecycle": runtime.lifecycle,
                            "terminal_status": (
                                None if terminal is None else terminal.to_dict()["status"]
                            ),
                        }
                    )
                for event_name in injection["events"]:
                    runtime.on_session_event(_event(contract, event_name))
                if injection["error"]:
                    raise RuntimeError(injection["error"])

    runtime = SessionClientRuntime(dispatch=dispatch)
    port = FakeSessionPort(runtime)
    runtime.bind_session_port(port)
    assert runtime.lifecycle == case["initial"]["lifecycle"]
    assert runtime.generation == case["initial"]["generation"]
    assert runtime.event_cursor == case["initial"]["cursor"]

    for operation in case["operations"]:
        dispatch_injections[:] = [
            {
                "match": dict(item["match"]),
                "events": list(item["events"]),
                "observation": str(item.get("observation") or ""),
                "error": str(item.get("error") or ""),
                "used": False,
            }
            for item in operation.get("dispatch_injections", [])
        ]
        kind = operation["kind"]
        if kind in ("activate", "activate_raw"):
            strict = kind == "activate"
            if operation.get("request_error"):
                port.responses.append(_port_error(operation["request_error"], "activation failed"))
            else:
                port.responses.append(_bootstrap(contract, operation["bootstrap"], strict=strict))
            if operation.get("during_event"):
                port.during_bootstrap = lambda name=operation["during_event"]: (
                    runtime.on_session_event(_event(contract, name))
                )
            nested = operation.get("during_activation")
            if nested:
                if nested.get("request_error"):
                    port.responses.append(_port_error(nested["request_error"], "activation failed"))
                else:
                    port.responses.append(_bootstrap(contract, nested["bootstrap"]))
                port.during_bootstrap = lambda value=nested: runtime.activate_session(
                    value["session_id"]
                )
            try:
                runtime.activate_session(operation["session_id"])
            except (FrontendPortError, TypeError, ValueError):
                pass
            continue
        if kind in ("bootstrap_operation", "bootstrap_operation_raw"):
            if operation.get("request_error"):
                port.responses.append(_port_error(operation["request_error"], "request failed"))
            else:
                port.responses.append(
                    _bootstrap(
                        contract,
                        operation["bootstrap"],
                        strict=kind == "bootstrap_operation",
                    )
                )
            if operation.get("recovery_bootstrap"):
                port.responses.append(_bootstrap(contract, operation["recovery_bootstrap"]))

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
                        port.responses.append(_bootstrap(contract, nested["bootstrap"]))
                    runtime.activate_session(nested["session_id"])
                if value.get("during_close"):
                    runtime.close()

            port.during_bootstrap = during_request
            operation_name = operation["operation"]
            if operation_name not in (
                "interaction_response",
                "create",
                "mode",
                "cancel",
            ):
                raise AssertionError("unknown bootstrap fixture operation: %s" % operation_name)

            def invoke():
                if operation_name == "interaction_response":
                    return runtime.respond_to_interaction(
                        "approval-1",
                        {"decision": "accept"},
                    )
                if operation_name == "create":
                    return runtime.create_session("explore")
                if operation_name == "mode":
                    return runtime.set_session_mode(operation["session_id"], "verify")
                return runtime.cancel_session(operation["session_id"])

            if operation.get("expect_stale"):
                with pytest.raises(RuntimeError, match="bootstrap_transaction_superseded"):
                    invoke()
            elif operation.get("expect_error"):
                expected_error = (
                    FrontendPortError if operation.get("request_error") else (TypeError, ValueError)
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
            recovery_events = list(operation.get("recovery_during_events", []))
            if recovery_events:
                port.during_bootstrap = lambda names=recovery_events: [
                    runtime.on_session_event(_event(contract, name)) for name in names
                ]
            runtime.on_session_event(_event(contract, operation["event"]))
            continue
        if kind == "close":
            runtime.close()
            continue
        raise AssertionError("unknown fixture operation: %s" % kind)

    return runtime, port, [_observable(action) for action in actions], observations


def test_python_runtime_matches_cross_language_contract():
    contract = _load_contract()

    assert contract["schema_version"] == 2
    for case in contract["cases"]:
        runtime, _port, actions, observations = _run_case(contract, case)
        assert actions == case["actions"], case["name"]
        assert observations == case.get("observations", []), case["name"]
        if "final" in case:
            terminal = runtime._terminal_outcome
            actual = {
                "session_id": runtime.active_session_id,
                "cursor": runtime.event_cursor,
                "generation": runtime.generation,
                "lifecycle": runtime.lifecycle,
                "terminal_status": (None if terminal is None else terminal.to_dict()["status"]),
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


def test_active_message_and_interaction_use_runtime_session_owner():
    contract = _load_contract()
    actions = []
    runtime = SessionClientRuntime(dispatch=actions.append)
    port = FakeSessionPort(runtime)
    runtime.bind_session_port(port)
    port.responses.append(_bootstrap(contract, "session_1_cursor_1"))
    runtime.activate_session("session-1")

    port.responses.append(_bootstrap(contract, "session_1_cursor_2"))
    runtime.submit_active_message("hello", stream=False)
    assert port.message_calls == [("session-1", "hello", False)]

    port.responses.append(_bootstrap(contract, "session_1_cursor_3"))
    runtime.respond_to_interaction("approval-1", {"decision": "accept"})
    assert port.bootstrap_calls[-1] == (
        "interaction_response",
        "session-1",
        "approval-1",
        {"decision": "accept"},
    )


def test_activation_failure_is_structured_and_rethrown():
    contract = _load_contract()
    actions = []
    runtime = SessionClientRuntime(dispatch=actions.append)
    port = FakeSessionPort(runtime)
    runtime.bind_session_port(port)
    error = _port_error("configuration_error", "composition rejected")
    port.responses.append(error)

    with pytest.raises(FrontendPortError) as raised:
        runtime.activate_session("session-1")

    assert raised.value.failure.code == "configuration_error"
    assert [item.kind for item in actions] == ["protocol_failed"]
    assert actions[0].payload["failure"]["code"] == "configuration_error"
    assert runtime.lifecycle == "failed"


def test_nested_activation_is_deferred_until_publication_commits():
    contract = _load_contract()
    actions = []
    runtime = None
    port = None

    def dispatch(action):
        actions.append(action)
        if action.kind == "session_activated" and action.payload["session_id"] == "session-1":
            port.responses.append(_bootstrap(contract, "session_2_cursor_0"))
            runtime.activate_session("session-2")

    runtime = SessionClientRuntime(dispatch=dispatch)
    port = FakeSessionPort(runtime)
    runtime.bind_session_port(port)
    port.responses.append(_bootstrap(contract, "session_1_cursor_1"))
    runtime.activate_session("session-1")

    assert [item.payload.get("session_id") for item in actions] == [
        "session-1",
        "session-2",
    ]
    assert runtime.active_session_id == "session-2"
    assert runtime.event_cursor == 0
    assert runtime.lifecycle == "ready"


def test_fork_result_is_separate_from_fork_and_activate():
    contract = _load_contract()
    runtime = SessionClientRuntime()
    port = FakeSessionPort(runtime)
    runtime.bind_session_port(port)
    port.responses.append(
        ThreadShell(
            id="session-2",
            title="Fork",
            archived=False,
            current_mode="explore",
            status="idle",
            updated_at="now",
        )
    )
    thread = runtime.fork_session("session-1", "Fork")
    assert isinstance(thread, ThreadShell)
    assert runtime.active_session_id == ""

    port.responses.append(ThreadShell.from_dict(contract["bootstraps"]["session_2_cursor_0"]["thread"]))
    port.responses.append(_bootstrap(contract, "session_2_cursor_0"))
    activated = runtime.fork_and_activate_session("session-1", "Fork")
    assert isinstance(activated, SessionBootstrap)
    assert runtime.active_session_id == "session-2"
