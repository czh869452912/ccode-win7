from __future__ import annotations

import pytest
from embedagent_core.ports import StrictSessionRestorePolicy
from embedagent_core.session import Session
from embedagent_core.session_journal import EventIntent, SessionJournal
from embedagent_core.session_log import InMemorySessionLog
from embedagent_core.session_reducer import (
    SessionReduceError,
    SessionReducer,
    SessionReducerContext,
)


class FailingSecondAppend(InMemorySessionLog):
    def append_event(self, *args, **kwargs):
        if len(self.load_events(args[0])) == 1:
            raise OSError("append failed")
        return super(FailingSecondAppend, self).append_event(*args, **kwargs)


def test_commit_applies_only_the_durable_event():
    store = InMemorySessionLog()
    session = Session(session_id="session-1")
    journal = SessionJournal(store, SessionReducer())

    result = journal.commit(
        session,
        SessionReducerContext(),
        (EventIntent("session_meta", {"current_mode": "debug"}),),
    )

    assert result.events[0]["seq"] == 1
    assert result.context.current_mode == "debug"


def test_partial_commit_exposes_only_stored_prefix():
    store = FailingSecondAppend()
    session = Session(session_id="session-1")
    context = SessionReducerContext()
    journal = SessionJournal(store, SessionReducer())

    with pytest.raises(OSError, match="append failed"):
        journal.commit(
            session,
            context,
            (
                EventIntent("session_meta", {"current_mode": "debug"}),
                EventIntent("session_meta", {"current_mode": "verify"}),
            ),
        )

    assert len(store.load_events("session-1")) == 1
    assert context.current_mode == "debug"


def test_invalid_intent_is_rejected_before_append():
    store = InMemorySessionLog()
    journal = SessionJournal(store, SessionReducer())

    with pytest.raises(SessionReduceError, match="^unknown_event_type$"):
        journal.commit(
            Session(session_id="session-1"),
            SessionReducerContext(),
            (EventIntent("unknown", {}),),
        )

    assert store.load_events("session-1") == []


class TrustedPrefixPolicy(object):
    def __init__(self, trusted_count):
        self.trusted_count = trusted_count
        self.session_ids = []

    def trusted_event_count(self, session_id):
        self.session_ids.append(session_id)
        return self.trusted_count


def _append_restore_fixture(store):
    store.append_event(
        "session-restore",
        "session_meta",
        {"current_mode": "build", "started_at": "2026-07-27T00:00:00Z"},
        event_id="event-1",
        ts="2026-07-27T00:00:00Z",
    )
    store.append_event(
        "session-restore",
        "user",
        {
            "role": "user",
            "content": "broken",
            "message_id": "message-broken",
            "parent_message_id": "missing-message",
            "turn_id": "turn-broken",
        },
        event_id="event-2",
        ts="2026-07-27T00:00:01Z",
    )
    store.append_event(
        "session-restore",
        "user",
        {
            "role": "user",
            "content": "trusted",
            "message_id": "message-trusted",
            "parent_message_id": "",
            "turn_id": "turn-trusted",
        },
        event_id="event-3",
        ts="2026-07-27T00:00:02Z",
    )


def test_restore_strict_policy_stops_at_first_invalid_event():
    store = InMemorySessionLog()
    _append_restore_fixture(store)
    journal = SessionJournal(store, SessionReducer())

    result = journal.restore("session-restore", StrictSessionRestorePolicy())

    assert result.current_mode == "build"
    assert result.transcript_event_count == 3
    assert result.consumed_event_count == 1
    assert result.stop_reason == "message_parent_missing"
    assert result.skipped_count == 0
    assert result.session.turns == []


def test_restore_trusted_prefix_policy_skips_reducer_error_and_continues():
    store = InMemorySessionLog()
    _append_restore_fixture(store)
    journal = SessionJournal(store, SessionReducer())
    policy = TrustedPrefixPolicy(2)

    result = journal.restore("session-restore", policy)

    assert policy.session_ids == ["session-restore"]
    assert result.consumed_event_count == 3
    assert result.stop_reason == ""
    assert result.skipped_count == 1
    assert result.skip_reasons[0]["event_id"] == "event-2"
    assert [item.user_message for item in result.session.turns] == ["trusted"]


def test_restore_rejects_empty_bound_session_log():
    journal = SessionJournal(InMemorySessionLog(), SessionReducer())

    with pytest.raises(ValueError, match="cannot restore an empty transcript"):
        journal.restore("session-empty", StrictSessionRestorePolicy())
