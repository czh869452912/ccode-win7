import json
import threading

import pytest
from embedagent_host.runtime.services.event_emitter import EventEmitter
from embedagent_host.runtime.session_event_protocol import SessionEventEncoder
from embedagent_protocol import (
    FRONTEND_FAILURE_CODES,
    FailureRecord,
    SessionEventEnvelope,
)


class RecordingSink(object):
    def __init__(self):
        self.events = []

    def on_session_event(self, envelope):
        self.events.append(envelope)


def test_frontend_failure_codes_are_closed():
    assert set(FRONTEND_FAILURE_CODES) == {
        "usage_error",
        "configuration_error",
        "session_not_found",
        "interaction_required",
        "permission_denied",
        "provider_error",
        "runtime_error",
        "cancelled",
        "protocol_error",
    }


def test_session_event_envelope_is_json_safe():
    envelope = SessionEventEnvelope(
        schema_version=1,
        event_id="evt-1",
        session_id="s-1",
        sequence=1,
        event_kind="tool.finished",
        timestamp="2026-07-26T00:00:00Z",
        payload={
            "failure": FailureRecord(
                "path_missing",
                "missing",
                False,
                "tool",
            ).to_dict()
        },
    )

    encoded = envelope.to_dict()

    json.dumps(encoded)
    assert SessionEventEnvelope.from_dict(encoded).to_dict() == encoded


@pytest.mark.parametrize(
    "field,value",
    (
        ("schema_version", 0),
        ("event_id", ""),
        ("session_id", ""),
        ("sequence", 0),
        ("event_kind", ""),
        ("timestamp", ""),
        ("payload", []),
    ),
)
def test_session_event_envelope_rejects_invalid_wire_fields(field, value):
    values = {
        "schema_version": 1,
        "event_id": "evt-1",
        "session_id": "s-1",
        "sequence": 1,
        "event_kind": "turn.started",
        "timestamp": "2026-07-26T00:00:00Z",
        "payload": {},
    }
    values[field] = value

    with pytest.raises((TypeError, ValueError)):
        SessionEventEnvelope(**values)


def test_host_encoder_sequences_each_session_independently():
    encoder = SessionEventEncoder()

    first = encoder.encode("s-1", "turn_start", {})
    second = encoder.encode("s-1", "turn_end", {})
    other = encoder.encode("s-2", "turn_start", {})

    assert [first.sequence, second.sequence, other.sequence] == [1, 2, 1]


def test_host_encoder_normalizes_interaction_and_failed_tool_payloads():
    encoder = SessionEventEncoder()

    interaction = encoder.encode(
        "s-1",
        "permission_required",
        {"permission": {"interaction_id": "perm-1", "tool_name": "edit_file"}},
    )
    failed = encoder.encode(
        "s-1",
        "tool_finished",
        {
            "tool_name": "edit_file",
            "success": False,
            "error": "missing",
            "data": {"error_kind": "path_missing", "retryable": False},
        },
    )

    assert interaction.event_kind == "approval.requested"
    assert interaction.payload["request_id"] == "perm-1"
    assert interaction.payload["interaction_id"] == "perm-1"
    assert failed.event_kind == "tool.finished"
    assert failed.payload["failure"] == {
        "code": "path_missing",
        "message": "missing",
        "retryable": False,
        "source": "edit_file",
    }


def test_event_emitter_sends_one_envelope_to_bound_sink():
    sink = RecordingSink()
    emitter = EventEmitter(sink)

    emitter.emit(
        "turn_start",
        "s-1",
        {"turn_id": "turn-1"},
    )

    assert len(sink.events) == 1
    assert sink.events[0].event_kind == "turn.started"


def test_event_emitter_capture_returns_projection_and_current_cursor_atomically():
    sink = RecordingSink()
    emitter = EventEmitter(sink)
    emitter.emit("turn_start", "s-1", {"turn_id": "turn-1"})

    captured = emitter.capture("s-1", lambda: {"snapshot": {"status": "idle"}})

    assert captured["event_cursor"] == 1
    assert captured["snapshot"] == {"status": "idle"}


def test_event_emitter_capture_excludes_publication_blocked_behind_capture():
    emitter = EventEmitter()
    entered = threading.Event()
    release = threading.Event()
    captured = []

    def load_projection():
        entered.set()
        assert release.wait(1.0)
        return {"snapshot": {"status": "running"}}

    capture_thread = threading.Thread(
        target=lambda: captured.append(emitter.capture("s-1", load_projection))
    )
    capture_thread.start()
    assert entered.wait(1.0)
    event_thread = threading.Thread(
        target=lambda: emitter.emit(
            "turn_start",
            "s-1",
            {"turn_id": "turn-1"},
        )
    )
    event_thread.start()
    release.set()
    capture_thread.join(1.0)
    event_thread.join(1.0)

    assert captured[0]["event_cursor"] == 0
    assert emitter.current_cursor("s-1") == 1


def test_session_error_keeps_structured_failure_payload():
    encoder = SessionEventEncoder()

    event = encoder.encode(
        "s-1",
        "session_error",
        {
            "status": "error",
            "failure": FailureRecord(
                code="provider_error",
                message="service unavailable",
                retryable=True,
                source="provider",
            ).to_dict(),
        },
    )

    assert event.event_kind == "session.error"
    assert event.payload["status"] == "error"
    assert event.payload["failure"]["code"] == "provider_error"
