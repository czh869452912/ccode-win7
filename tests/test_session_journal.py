from __future__ import annotations

import pytest
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
