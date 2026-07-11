from datetime import datetime

import pytest

from embedagent_core import session_log
from embedagent_core.session_log import SessionLeaseConflict


def _new_log():
    return session_log.InMemorySessionLog()


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
