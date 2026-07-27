from __future__ import annotations

import pytest
from embedagent_core.session import Session
from embedagent_core.session_reducer import (
    SessionReduceError,
    SessionReducer,
    SessionReducerContext,
)
from embedagent_core.session_restore import SessionRestorer


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


def test_conversation_events_match_restored_projection():
    events = [
        event(
            "session_meta",
            {
                "current_mode": "build",
                "started_at": "2026-07-27T00:00:00Z",
            },
            seq=1,
        ),
        event(
            "system",
            {
                "role": "system",
                "content": "system prompt",
                "message_id": "message-system",
                "parent_message_id": "",
                "turn_id": "",
                "step_id": "",
            },
            seq=2,
        ),
        event(
            "user",
            {
                "role": "user",
                "content": "fix the parser",
                "message_id": "message-user",
                "parent_message_id": "message-system",
                "turn_id": "turn-1",
                "step_id": "",
            },
            seq=3,
        ),
        event(
            "step_started",
            {
                "turn_id": "turn-1",
                "step_id": "step-1",
                "step_index": 1,
                "reasoning": "inspect",
            },
            seq=4,
        ),
        event(
            "assistant",
            {
                "role": "assistant",
                "content": "done",
                "message_id": "message-assistant",
                "parent_message_id": "message-user",
                "turn_id": "turn-1",
                "step_id": "step-1",
                "actions": [],
                "finish_reason": "stop",
                "reasoning_content": "checked",
            },
            seq=5,
        ),
        event(
            "loop_transition",
            {
                "turn_id": "turn-1",
                "step_id": "step-1",
                "reason": "completed",
                "message": "complete",
                "next_mode": "verify",
                "turns_used": 1,
                "metadata": {"source": "test"},
            },
            seq=6,
        ),
    ]
    live = Session(session_id="session-1")
    context = SessionReducerContext()
    reducer = SessionReducer()

    for item in events:
        reducer.apply(live, context, item)
    restored = SessionRestorer().restore(events).session

    assert [item.to_api_dict() for item in live.messages] == [
        item.to_api_dict() for item in restored.messages
    ]
    assert live.turns[-1].turn_id == restored.turns[-1].turn_id
    assert live.turns[-1].steps[-1].step_id == restored.turns[-1].steps[-1].step_id
    assert live.turns[-1].transitions[-1].reason == "completed"
    assert context.current_mode == "verify"
