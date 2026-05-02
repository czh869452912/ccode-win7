"""Characterization tests for timestamp behavior — verifies pre/post change equivalence."""
import re
from datetime import datetime, timedelta, timezone

from embedagent.inprocess_adapter import _utc_now as adapter_utc_now
from embedagent.plan_store import _utc_now as plan_utc_now
from embedagent.project_memory import _utc_now as memory_utc_now

# Import modules to test
from embedagent.session import _utc_now
from embedagent.session_runtime import _utc_now as runtime_utc_now
from embedagent.session_store import _utc_now as store_utc_now
from embedagent.session_timeline import _utc_now as timeline_utc_now
from embedagent.transcript_store import _utc_now as transcript_utc_now

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestTimestampFormat:
    """Verify timestamp format matches expected ISO 8601 with Z suffix."""

    def test_session_utc_now_format(self):
        result = _utc_now()
        assert TIMESTAMP_PATTERN.match(result), f"Invalid format: {result}"
        assert result.endswith("Z")

    def test_all_helpers_produce_valid_format(self):
        helpers = [
            store_utc_now, timeline_utc_now, runtime_utc_now,
            memory_utc_now, adapter_utc_now, plan_utc_now, transcript_utc_now,
        ]
        for helper in helpers:
            result = helper()
            assert TIMESTAMP_PATTERN.match(result), f"{helper.__module__} produced invalid format: {result}"


class TestSessionRestoreBehavior:
    """Verify session restore age check behavior."""

    def test_old_session_is_older_than(self):
        # Import the function under test
        from embedagent.session_restore import SessionRestorer
        restore = SessionRestorer()
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        assert restore._interaction_is_stale(old_time.isoformat(), 300) is True

    def test_recent_session_is_not_older_than(self):
        from embedagent.session_restore import SessionRestorer
        restore = SessionRestorer()
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        assert restore._interaction_is_stale(recent_time.isoformat(), 300) is False
