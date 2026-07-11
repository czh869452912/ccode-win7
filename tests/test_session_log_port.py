from datetime import datetime

import pytest

from embedagent.transcript_store import TranscriptStore
from embedagent_core import session_log
from embedagent_core.session_log import SessionLeaseConflict


def _new_log():
    return session_log.InMemorySessionLog()


@pytest.fixture(params=("memory", "transcript"))
def session_log_implementation(request, tmp_path):
    if request.param == "memory":
        return session_log.InMemorySessionLog()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return TranscriptStore(str(workspace))


def test_same_session_cannot_hold_overlapping_leases():
    log = _new_log()

    with log.acquire_lease("session-one"):
        with pytest.raises(SessionLeaseConflict):
            with log.acquire_lease("session-one"):
                pass


def test_different_sessions_can_hold_nested_leases():
    log = _new_log()

    with log.acquire_lease("session-one"):
        with log.acquire_lease("session-two"):
            pass


def test_lease_is_released_after_exception():
    log = _new_log()

    with pytest.raises(RuntimeError):
        with log.acquire_lease("session-one"):
            raise RuntimeError("stop")

    with log.acquire_lease("session-one"):
        pass


def test_append_builds_complete_schema_v2_events():
    log = _new_log()

    first = log.append_event(
        "session-one",
        "message",
        {"content": "one", "parent_message_id": "message-zero"},
    )
    second = log.append_event("session-one", "message", {"content": "two"})

    assert [first["seq"], second["seq"]] == [1, 2]
    for event in (first, second):
        assert event["schema_version"] == 2
        assert event["session_id"] == "session-one"
        assert event["event_id"].startswith("evt-")
        assert event["ts"].endswith("Z")
        datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
        assert event["type"] == "message"
        assert isinstance(event["payload"], dict)
    assert first["parent_message_id"] == "message-zero"
    assert second["parent_message_id"] == ""


def test_load_and_append_results_are_defensive_deep_copies():
    log = _new_log()
    payload = {"nested": {"values": ["original"]}}

    appended = log.append_event("session-one", "message", payload)
    payload["nested"]["values"].append("payload-mutated")
    appended["payload"]["nested"]["values"].append("return-mutated")

    loaded = log.load_events("session-one")
    assert loaded[0]["payload"]["nested"]["values"] == ["original"]

    loaded[0]["payload"]["nested"]["values"].append("load-mutated")
    assert log.load_events("session-one")[0]["payload"]["nested"]["values"] == ["original"]


def test_append_rejects_non_schema_v2_events():
    log = _new_log()

    with pytest.raises(ValueError, match="schema_version 2"):
        log.append_event("session-one", "message", {}, schema_version=1)


def test_session_log_implementations_isolate_input_payload(session_log_implementation):
    payload = {"nested": {"values": ["original"]}}

    appended = session_log_implementation.append_event("session-one", "message", payload)
    payload["nested"]["values"].append("mutated")

    assert appended["payload"]["nested"]["values"] == ["original"]
    loaded = session_log_implementation.load_events("session-one")
    assert loaded[0]["payload"]["nested"]["values"] == ["original"]


def test_session_log_implementations_reject_blank_session_ids(session_log_implementation):
    with pytest.raises(ValueError, match="^session_id is required$"):
        session_log_implementation.append_event(" \t ", "message", {})
    with pytest.raises(ValueError, match="^session_id is required$"):
        session_log_implementation.load_events(" \t ")
    with pytest.raises(ValueError, match="^session_id is required$"):
        with session_log_implementation.acquire_lease(" \t "):
            pass

    assert session_log_implementation.transcript_exists(" \t ") is False


def test_session_log_implementations_normalize_session_ids(session_log_implementation):
    appended = session_log_implementation.append_event(" session-one ", "message", {})

    assert appended["session_id"] == "session-one"
    assert session_log_implementation.transcript_exists(" session-one ") is True
    assert session_log_implementation.load_events(" session-one ")[0]["seq"] == 1
    with session_log_implementation.acquire_lease(" session-one "):
        with pytest.raises(SessionLeaseConflict):
            with session_log_implementation.acquire_lease("session-one"):
                pass


def test_session_log_implementations_canonicalize_case_aliases(session_log_implementation):
    first = session_log_implementation.append_event(" Mixed-Case-ID ", "message", {})
    second = session_log_implementation.append_event("mixed-case-id", "message", {})

    assert first["session_id"] == "mixed-case-id"
    assert second["session_id"] == "mixed-case-id"
    assert second["seq"] == 2
    assert session_log_implementation.transcript_exists("MIXED-CASE-ID") is True
    assert len(session_log_implementation.load_events("MiXeD-CaSe-Id")) == 2
    with session_log_implementation.acquire_lease("MIXED-CASE-ID"):
        with pytest.raises(SessionLeaseConflict):
            with session_log_implementation.acquire_lease("mixed-case-id"):
                pass


@pytest.mark.parametrize(
    "invalid_session_id",
    (
        123,
        ".",
        "..",
        "../escape",
        "session/child",
        "session\\child",
        "C:session",
        "session.jsonl",
        "-leading",
        "_leading",
        "session.name",
        "sess\N{LATIN SMALL LETTER E WITH ACUTE}",
        "CON",
        "nul",
        "COM1",
        "lpt9",
        "s" * 129,
    ),
)
def test_session_log_implementations_reject_unsafe_session_ids(
    session_log_implementation,
    invalid_session_id,
):
    with pytest.raises(ValueError, match="^session_id is invalid$"):
        session_log_implementation.append_event(invalid_session_id, "message", {})
    with pytest.raises(ValueError, match="^session_id is invalid$"):
        session_log_implementation.load_events(invalid_session_id)
    with pytest.raises(ValueError, match="^session_id is invalid$"):
        with session_log_implementation.acquire_lease(invalid_session_id):
            pass

    assert session_log_implementation.transcript_exists(invalid_session_id) is False
