"""Characterization tests for timestamp behavior — verifies pre/post change equivalence."""

import re
from datetime import datetime, timedelta, timezone

import pytest

# Import modules to test
from embedagent_core.session import Session, _utc_now
from embedagent_core.session_reducer import (
    SessionReduceError,
    SessionReducer,
    SessionReducerContext,
)
from embedagent_host.inprocess_adapter import _utc_now as adapter_utc_now
from embedagent_host.runtime.plan_store import _utc_now as plan_utc_now
from embedagent_host.runtime.project_memory import _utc_now as memory_utc_now
from embedagent_host.runtime.session_runtime import _utc_now as runtime_utc_now
from embedagent_host.runtime.session_store import _utc_now as store_utc_now
from embedagent_host.runtime.transcript_store import _utc_now as transcript_utc_now

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestTimestampFormat:
    """Verify timestamp format matches expected ISO 8601 with Z suffix."""

    def test_session_utc_now_format(self):
        result = _utc_now()
        assert TIMESTAMP_PATTERN.match(result), f"Invalid format: {result}"
        assert result.endswith("Z")

    def test_all_helpers_produce_valid_format(self):
        helpers = [
            store_utc_now,
            runtime_utc_now,
            memory_utc_now,
            adapter_utc_now,
            plan_utc_now,
            transcript_utc_now,
        ]
        for helper in helpers:
            result = helper()
            assert TIMESTAMP_PATTERN.match(
                result
            ), f"{helper.__module__} produced invalid format: {result}"


def _pending_interaction_event(created_at):
    return {
        "schema_version": 2,
        "session_id": "session-age",
        "event_id": "event-pending",
        "seq": 1,
        "ts": created_at,
        "type": "pending_interaction",
        "payload": {
            "turn_id": "turn-age",
            "step_id": "step-age",
            "kind": "permission",
            "tool_name": "write_file",
            "interaction_id": "interaction-age",
            "request_payload": {"path": "src/main.c"},
            "created_at": created_at,
        },
    }


def _session_with_active_step():
    session = Session(session_id="session-age")
    session.add_user_message("continue", turn_id="turn-age")
    session.begin_step(step_id="step-age")
    return session


class TestSessionReducerBehavior:
    """Verify pending-interaction age reduction behavior."""

    def test_old_session_is_older_than(self):
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        with pytest.raises(SessionReduceError, match="^interaction_expired$"):
            SessionReducer().apply(
                _session_with_active_step(),
                SessionReducerContext(),
                _pending_interaction_event(old_time.isoformat()),
            )

    def test_recent_session_is_not_older_than(self):
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        session = _session_with_active_step()
        SessionReducer().apply(
            session,
            SessionReducerContext(),
            _pending_interaction_event(recent_time.isoformat()),
        )
        assert session.pending_interaction is not None
