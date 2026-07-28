from __future__ import annotations

from copy import deepcopy

from embedagent_core.ports import StrictSessionRestorePolicy
from embedagent_core.session_journal import SessionJournal
from embedagent_core.session_reducer import SessionReducer, SessionReducerContext


class StaticSessionLog(object):
    def __init__(self, events):
        self._events = deepcopy(list(events or []))

    def load_events(self, session_id):
        del session_id
        return deepcopy(self._events)


class TrustedEventCountPolicy(object):
    def __init__(self, trusted_event_count):
        self._trusted_event_count = max(0, int(trusted_event_count or 0))

    def trusted_event_count(self, session_id):
        del session_id
        return self._trusted_event_count


def restore_events(events, trusted_event_count=0):
    event_list = list(events or [])
    session_id = (
        str(event_list[0].get("session_id") or "session-empty") if event_list else ("session-empty")
    )
    policy = (
        TrustedEventCountPolicy(trusted_event_count)
        if trusted_event_count > 0
        else StrictSessionRestorePolicy()
    )
    return SessionJournal(StaticSessionLog(event_list), SessionReducer()).restore(
        session_id, policy
    )


def restore_trusted_events(events):
    event_list = list(events or [])
    return restore_events(event_list, trusted_event_count=len(event_list))


def apply_session_event(session, event_type, payload, event_id="test-event"):
    context = SessionReducerContext()
    SessionReducer().apply(
        session,
        context,
        {
            "schema_version": 2,
            "session_id": session.session_id,
            "event_id": event_id,
            "seq": 1,
            "ts": "2026-01-01T00:00:00Z",
            "type": event_type,
            "payload": deepcopy(dict(payload or {})),
        },
    )
    return context
