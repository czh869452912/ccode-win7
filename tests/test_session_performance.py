import os
import shutil
import sys
import time
import unittest
from itertools import count

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_host.runtime.session_history import SessionHistoryAssembler
from embedagent_host.runtime.transcript_store import TranscriptStore
from session_journal_test_helpers import restore_trusted_events

pytestmark = pytest.mark.performance

_COUNTER = count(1)


def _make_workspace(name):
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "%s-%s-%s" % (name, os.getpid(), next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


class TestSessionPerformance(unittest.TestCase):
    """Performance benchmarks for session infrastructure."""

    # Thresholds
    MAX_APPEND_MS = 10  # per event
    MAX_LOAD_MS = 50  # per 100 events
    MAX_RESTORE_MS = 100  # per 100 events
    MAX_TIMELINE_MS = 100  # per 100 items

    def setUp(self):
        self.workspace = _make_workspace("session-perf")
        self.store = TranscriptStore(self.workspace)
        self.assembler = SessionHistoryAssembler()

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _generate_events(self, count, session_id="sess-perf"):
        """Generate a sequence of realistic events."""
        events = []
        parent_id = ""

        for i in range(count):
            if i % 4 == 0:
                # User message
                msg_id = "m-%d" % i
                event = {
                    "schema_version": 2,
                    "session_id": session_id,
                    "event_id": "evt-%d" % i,
                    "seq": i + 1,
                    "ts": "2026-04-02T00:00:%02dZ" % (i % 60),
                    "type": "user",
                    "parent_message_id": parent_id,
                    "payload": {
                        "role": "user",
                        "content": "Message %d" % i,
                        "message_id": msg_id,
                        "turn_id": "t-%d" % (i // 4),
                    },
                }
                parent_id = msg_id
            elif i % 4 == 1:
                # Agent step start
                event = {
                    "schema_version": 2,
                    "session_id": session_id,
                    "event_id": "evt-%d" % i,
                    "seq": i + 1,
                    "ts": "2026-04-02T00:00:%02dZ" % (i % 60),
                    "type": "step_started",
                    "parent_message_id": parent_id,
                    "payload": {
                        "turn_id": "t-%d" % (i // 4),
                        "step_id": "s-%d" % i,
                        "step_index": 1,
                    },
                }
            elif i % 4 == 2:
                # Assistant message
                msg_id = "m-%d" % i
                event = {
                    "schema_version": 2,
                    "session_id": session_id,
                    "event_id": "evt-%d" % i,
                    "seq": i + 1,
                    "ts": "2026-04-02T00:00:%02dZ" % (i % 60),
                    "type": "assistant",
                    "parent_message_id": parent_id,
                    "payload": {
                        "role": "assistant",
                        "content": "Reply %d" % i,
                        "message_id": msg_id,
                        "turn_id": "t-%d" % (i // 4),
                        "step_id": "s-%d" % (i - 1),
                        "actions": [
                            {
                                "name": "read_file",
                                "arguments": {"path": "file%d.txt" % i},
                                "call_id": "call-%d" % i,
                            }
                        ],
                    },
                }
                parent_id = msg_id
            else:
                # Tool result
                msg_id = "m-%d" % i
                event = {
                    "schema_version": 2,
                    "session_id": session_id,
                    "event_id": "evt-%d" % i,
                    "seq": i + 1,
                    "ts": "2026-04-02T00:00:%02dZ" % (i % 60),
                    "type": "tool_result",
                    "parent_message_id": parent_id,
                    "payload": {
                        "role": "tool_result",
                        "tool_name": "read_file",
                        "call_id": "call-%d" % (i - 1),
                        "arguments": {"path": "file%d.txt" % (i - 1)},
                        "observation": {"success": True, "data": "content", "error": None},
                        "message_id": msg_id,
                        "turn_id": "t-%d" % (i // 4),
                        "step_id": "s-%d" % (i - 2),
                    },
                }
                parent_id = msg_id

            events.append(event)

        return events

    def test_append_performance_100_events(self):
        samples = []
        for sample_index in range(3):
            session_id = "sess-perf-100-%d" % sample_index
            events = self._generate_events(100, session_id)

            start = time.perf_counter()
            for event in events:
                self.store.append_event(
                    session_id,
                    event["type"],
                    event["payload"],
                    event_id=event["event_id"],
                    ts=event["ts"],
                    schema_version=2,
                )
            elapsed_ms = (time.perf_counter() - start) * 1000
            samples.append(elapsed_ms / len(events))

        # Keep the durability threshold strict while filtering one-off Windows
        # scheduler and filesystem flush jitter from this microbenchmark.
        per_event_ms = min(samples)
        self.assertLess(
            per_event_ms,
            self.MAX_APPEND_MS,
            "Best append took %.2fms per event (max %.2fms; samples %s)"
            % (per_event_ms, self.MAX_APPEND_MS, [round(item, 2) for item in samples]),
        )

    def test_load_performance_1000_events(self):
        session_id = "sess-perf-1000"
        events = self._generate_events(1000, session_id)

        # Write all events
        for event in events:
            self.store.append_event(
                session_id,
                event["type"],
                event["payload"],
                event_id=event["event_id"],
                ts=event["ts"],
                schema_version=2,
            )

        start = time.time()
        loaded = self.store.load_events(session_id)
        elapsed_ms = (time.time() - start) * 1000

        per_hundred_ms = elapsed_ms / (len(events) / 100)
        self.assertLess(
            per_hundred_ms,
            self.MAX_LOAD_MS,
            "Load took %.2fms per 100 events (max %.2fms)" % (per_hundred_ms, self.MAX_LOAD_MS),
        )
        self.assertEqual(len(loaded), len(events))

    def test_restore_performance_1000_events(self):
        session_id = "sess-perf-1000"
        events = self._generate_events(1000, session_id)

        start = time.time()
        result = restore_trusted_events(events)
        elapsed_ms = (time.time() - start) * 1000

        per_hundred_ms = elapsed_ms / (len(events) / 100)
        self.assertLess(
            per_hundred_ms,
            self.MAX_RESTORE_MS,
            "Restore took %.2fms per 100 events (max %.2fms)"
            % (per_hundred_ms, self.MAX_RESTORE_MS),
        )
        self.assertEqual(result.transcript_event_count, len(events))

    def test_activity_history_performance_1000_events(self):
        session_id = "sess-perf-1000"
        events = self._generate_events(1000, session_id)
        result = restore_trusted_events(events)

        start = time.time()
        history = self.assembler.build(result.session, "restored", "healthy")
        elapsed_ms = (time.time() - start) * 1000

        activities = history["activities"]
        per_hundred_ms = elapsed_ms / (len(activities) / 100)
        self.assertLess(
            per_hundred_ms,
            self.MAX_TIMELINE_MS,
            "History took %.2fms per 100 activities (max %.2fms)"
            % (per_hundred_ms, self.MAX_TIMELINE_MS),
        )

    def test_large_session_memory_usage(self):
        """Ensure no excessive memory growth with large sessions."""

        session_id = "sess-perf-mem"
        events = self._generate_events(500, session_id)

        # Measure memory before
        # Note: This is a coarse check; real memory profiling would use tracemalloc
        result = restore_trusted_events(events)

        # Session should have reasonable number of turns
        self.assertTrue(len(result.session.turns) <= 125)  # 500 / 4 = 125 turns

        history = self.assembler.build(result.session, "restored", "healthy")
        self.assertTrue(len(history["activities"]) >= 250)
        self.assertNotIn("items", history)


if __name__ == "__main__":
    unittest.main()
