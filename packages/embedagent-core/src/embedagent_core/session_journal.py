from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Tuple

from embedagent_core.session import Session
from embedagent_core.session_log import SessionLogPort
from embedagent_core.session_reducer import SessionReducer, SessionReducerContext


@dataclass(frozen=True)
class EventIntent:
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    ts: str = ""


@dataclass(frozen=True)
class CommitResult:
    context: SessionReducerContext
    events: Tuple[Dict[str, Any], ...]


class SessionJournal(object):
    def __init__(self, session_log: SessionLogPort, reducer: SessionReducer) -> None:
        self._session_log = session_log
        self._reducer = reducer

    def commit(
        self,
        session: Session,
        context: SessionReducerContext,
        intents: Iterable[EventIntent],
    ) -> CommitResult:
        intents = tuple(intents)
        staged_session = deepcopy(session)
        staged_context = deepcopy(context)
        for index, intent in enumerate(intents):
            self._reducer.apply(
                staged_session,
                staged_context,
                {
                    "schema_version": 2,
                    "session_id": session.session_id,
                    "event_id": "preflight-%d" % (index + 1),
                    "seq": index + 1,
                    "ts": "1970-01-01T00:00:00Z",
                    "type": intent.event_type,
                    "payload": dict(intent.payload),
                },
            )

        stored_events = []
        for intent in intents:
            stored = self._session_log.append_event(
                session.session_id,
                intent.event_type,
                dict(intent.payload),
                event_id=intent.event_id,
                ts=intent.ts,
                schema_version=2,
            )
            self._reducer.apply(session, context, stored)
            stored_events.append(stored)
        return CommitResult(context=context, events=tuple(stored_events))
