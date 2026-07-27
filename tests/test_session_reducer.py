from __future__ import annotations

import pytest
from embedagent_core.session import Session
from embedagent_core.session_reducer import (
    SessionReduceError,
    SessionReducer,
    SessionReducerContext,
)


def event(event_type, payload, seq=1):
    return {
        "schema_version": 2,
        "session_id": "session-1",
        "event_id": "event-%s" % seq,
        "seq": seq,
        "ts": "2026-07-27T00:00:00Z",
        "type": event_type,
        "payload": payload,
    }


def test_session_meta_sets_mode_and_started_at():
    session = Session(session_id="session-1")
    context = SessionReducerContext()

    SessionReducer().apply(
        session,
        context,
        event(
            "session_meta",
            {"current_mode": "debug", "started_at": "2026-07-27T00:00:00Z"},
        ),
    )

    assert context.current_mode == "debug"
    assert session.started_at == "2026-07-27T00:00:00Z"


def test_known_lifecycle_event_is_state_neutral():
    session = Session(session_id="session-1")
    context = SessionReducerContext()

    SessionReducer().apply(
        session,
        context,
        event("operation_started", {"operation_id": "turn:t-1"}),
    )

    assert session.messages == []
    assert session.turns == []


def test_unknown_event_fails_closed():
    with pytest.raises(SessionReduceError, match="^unknown_event_type$"):
        SessionReducer().apply(
            Session(session_id="session-1"),
            SessionReducerContext(),
            event("unknown", {}),
        )
