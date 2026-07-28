from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple

from embedagent_core.compaction_state import CompactionState, CompactionStateReducer
from embedagent_core.ports import SessionRestorePolicyPort
from embedagent_core.recovery_state import RecoveryState, RecoveryStateReducer
from embedagent_core.runtime_config import RuntimeConfigReducer, RuntimeConfigState
from embedagent_core.session import Session
from embedagent_core.session_log import SessionLogPort
from embedagent_core.session_operation_log import OperationLogReducer, OperationLogState
from embedagent_core.session_reducer import (
    SessionReduceError,
    SessionReducer,
    SessionReducerContext,
)
from embedagent_core.turn_experience import TurnExperienceReducer, TurnExperienceState

_LOG = logging.getLogger(__name__)


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


@dataclass
class SessionRestoreResult:
    session: Session
    current_mode: str
    transcript_event_count: int
    consumed_event_count: int
    stop_reason: str = ""
    skipped_count: int = 0
    skip_reasons: List[Dict[str, Any]] = field(default_factory=list)
    reduction_context: SessionReducerContext = field(default_factory=SessionReducerContext)
    operation_state: OperationLogState = field(default_factory=OperationLogState)
    compaction_state: CompactionState = field(default_factory=CompactionState)
    recovery_state: RecoveryState = field(default_factory=RecoveryState)
    runtime_config: RuntimeConfigState = field(default_factory=RuntimeConfigState)
    turn_experience: TurnExperienceState = field(default_factory=TurnExperienceState)


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

    def restore(
        self,
        session_id: str,
        restore_policy: SessionRestorePolicyPort,
    ) -> SessionRestoreResult:
        events = self._session_log.load_events(session_id)
        if not events:
            raise ValueError("cannot restore an empty transcript")
        trusted_event_count = max(
            0,
            int(restore_policy.trusted_event_count(session_id) or 0),
        )
        return self._fold(events, trusted_event_count)

    def _fold(
        self,
        events: List[Dict[str, Any]],
        trusted_event_count: int,
    ) -> SessionRestoreResult:
        session_id = str(events[0].get("session_id") or "")
        started_at = str(events[0].get("ts") or "")
        session = (
            Session(session_id=session_id, started_at=started_at)
            if started_at
            else Session(session_id=session_id)
        )
        context = SessionReducerContext()
        consumed = len(events)
        stop_reason = ""
        skipped = []  # type: List[Dict[str, Any]]
        for index, event in enumerate(events):
            try:
                self._reducer.apply(session, context, event)
            except SessionReduceError as exc:
                within_prefix = trusted_event_count <= 0 or index < trusted_event_count
                if (
                    trusted_event_count > 0
                    and within_prefix
                    and self._should_skip_error(exc.reason)
                ):
                    skipped.append(
                        {
                            "index": index,
                            "event_type": str(event.get("type") or ""),
                            "reason": exc.reason,
                            "event_id": str(event.get("event_id") or ""),
                        }
                    )
                    _LOG.warning(
                        "Session restore skipped record %d (type=%s, id=%s): %s",
                        index,
                        event.get("type", ""),
                        event.get("event_id", ""),
                        exc.reason,
                    )
                    continue
                consumed = index
                stop_reason = exc.reason
                break
        consumed_events = events[:consumed]
        return SessionRestoreResult(
            session=session,
            current_mode=context.current_mode,
            transcript_event_count=len(events),
            consumed_event_count=consumed,
            stop_reason=stop_reason,
            skipped_count=len(skipped),
            skip_reasons=skipped,
            reduction_context=context,
            operation_state=OperationLogReducer().reduce(consumed_events),
            compaction_state=CompactionStateReducer().reduce(consumed_events),
            recovery_state=RecoveryStateReducer().reduce(consumed_events),
            runtime_config=RuntimeConfigReducer().reduce(consumed_events),
            turn_experience=TurnExperienceReducer().reduce(consumed_events),
        )

    def _should_skip_error(self, error_reason: str) -> bool:
        return error_reason not in {"empty_transcript"}
