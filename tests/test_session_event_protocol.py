import json

import pytest
from embedagent_host.runtime.services.event_emitter import EventEmitter
from embedagent_host.runtime.session_event_protocol import SessionEventEncoder
from embedagent_protocol import FailureRecord, SessionEventEnvelope


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
        {"permission": {"permission_id": "perm-1", "tool_name": "edit_file"}},
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


def test_event_emitter_sends_one_envelope_instance_to_every_handler():
    emitter = EventEmitter()
    first = []
    second = []
    emitter.add_handler(None, first.append)
    emitter.add_handler("turn_start", second.append)

    emitter.emit(
        None,
        "turn_start",
        "s-1",
        {"turn_id": "turn-1"},
    )

    assert first[0] is second[0]
    assert first[0].event_kind == "turn.started"
