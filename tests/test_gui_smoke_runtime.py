import asyncio
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-gui-smoke.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("validate_gui_smoke", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeProcess:
    def __init__(self, returncode=None):
        self.returncode = returncode


class FakeWebSocket:
    def __init__(self, payloads):
        self.payloads = [json.dumps(payload) for payload in payloads]

    async def recv(self):
        return self.payloads.pop(0)


def test_consume_collects_assistant_delta_from_canonical_session_event():
    smoke = _load_smoke_module()
    summary = {
        "stream_deltas": [],
        "session_statuses": [],
        "tool_events": [],
        "command_results": [],
        "permission_requests": 0,
        "user_input_requests": 0,
        "session_transitions": [],
    }
    websocket = FakeWebSocket(
        [
            {
                "type": "session_event",
                "data": {
                    "session_id": "session-1",
                    "event_kind": "assistant.delta",
                    "payload": {"text": "canonical reply"},
                },
            },
            {
                "type": "session_event",
                "data": {
                    "session_id": "session-1",
                    "event_kind": "session.finished",
                    "payload": {},
                },
            },
        ]
    )

    asyncio.run(smoke._consume_until_idle(websocket, "session-1", summary, ""))

    assert summary["stream_deltas"] == ["canonical reply"]


def test_consume_collects_command_result_from_canonical_session_event():
    smoke = _load_smoke_module()
    summary = {
        "stream_deltas": [],
        "session_statuses": [],
        "tool_events": [],
        "command_results": [],
        "permission_requests": 0,
        "user_input_requests": 0,
        "session_transitions": [],
    }
    websocket = FakeWebSocket(
        [
            {
                "type": "session_event",
                "data": {
                    "session_id": "session-1",
                    "event_kind": "command.result",
                    "payload": {
                        "command_name": "review",
                        "success": True,
                        "message": "review complete",
                        "data": {"review": {}},
                    },
                },
            },
            {
                "type": "session_event",
                "data": {
                    "session_id": "session-1",
                    "event_kind": "transition.recorded",
                    "payload": {"reason": "command_result"},
                },
            },
        ]
    )

    asyncio.run(smoke._consume_until_idle(websocket, "session-1", summary, ""))

    assert summary["command_results"] == [
        {
            "command_name": "review",
            "success": True,
            "message": "review complete",
            "data": {"review": {}},
        }
    ]


def test_failure_payload_contains_exit_and_log_tails(tmp_path):
    smoke = _load_smoke_module()
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("ready\nfailed\n", encoding="utf-8")
    stderr.write_text("trace\n", encoding="utf-8")
    failure = smoke.SmokeFailure("launcher_exit", "http", {"returncode": 3})

    payload = smoke._failure_payload(failure, FakeProcess(3), stdout, stderr, ["process"])

    assert payload["ok"] is False
    assert payload["failure"]["category"] == "launcher_exit"
    assert payload["failure"]["stage"] == "http"
    assert payload["process"]["returncode"] == 3
    assert payload["stdout_tail"] == ["ready", "failed"]
    assert payload["stderr_tail"] == ["trace"]
    assert payload["checks"] == ["process"]


def test_process_exit_details_short_circuits_running_process():
    smoke = _load_smoke_module()

    assert smoke._process_exit_details(FakeProcess(None)) is None
    assert smoke._process_exit_details(FakeProcess(7)) == 7


def test_failure_payload_redacts_sensitive_details(tmp_path):
    smoke = _load_smoke_module()
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("safe\n", encoding="utf-8")
    stderr.write_text("safe\n", encoding="utf-8")
    failure = smoke.SmokeFailure(
        "protocol_failure",
        "exercise",
        {
            "api_key": "secret",
            "prompt": "private prompt",
            "raw_output": "private output",
            "message": "visible failure",
        },
    )

    payload = smoke._failure_payload(failure, FakeProcess(1), stdout, stderr, ["process"])
    text = str(payload)

    assert "api_key" not in text
    assert "prompt" not in text
    assert "raw_output" not in text
    assert "visible failure" in text


def test_http_wait_raises_launcher_exit_for_exited_process():
    smoke = _load_smoke_module()

    try:
        smoke._wait_for_http(
            "http://127.0.0.1:1/",
            timeout=0.1,
            process=FakeProcess(9),
            stage="http",
            checks=[],
        )
    except smoke.SmokeFailure as failure:
        assert failure.category == "launcher_exit"
        assert failure.stage == "http"
        assert failure.details["returncode"] == 9
    else:
        raise AssertionError("expected launcher_exit")
