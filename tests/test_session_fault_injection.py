import json
import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.session_restore import SessionRestorer
from embedagent.transcript_store import TranscriptStore

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


class TestSessionFaultInjection(unittest.TestCase):
    """Fault injection tests for session restore resilience."""
    
    def setUp(self):
        self.workspace = _make_workspace("session-fault")
        self.store = TranscriptStore(self.workspace)
        self.restorer = SessionRestorer()

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write_raw_events(self, session_id, events):
        """Write raw events directly to transcript file."""
        path = self.store.resolve_transcript_path(session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def test_repair_truncated_json_at_end(self):
        """TranscriptStore._repair_tail should handle truncated final line."""
        session_id = "sess-trunc"
        self.store.append_event(session_id, "session_meta", {"current_mode": "build"})
        self.store.append_event(session_id, "message", {"role": "user", "content": "hi"})
        
        # Append truncated JSON
        path = self.store.resolve_transcript_path(session_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"bad json')
        
        # Should load valid events and ignore truncated tail
        events = self.store.load_events(session_id)
        self.assertEqual(len(events), 2)

    def test_repair_corrupted_middle_record(self):
        """Best-effort restore should skip corrupted middle record."""
        session_id = "sess-corrupt-mid"
        events = [
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-1",
                "seq": 1,
                "ts": "2026-04-02T00:00:00Z",
                "type": "session_meta",
                "payload": {"current_mode": "build"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-2",
                "seq": 2,
                "ts": "2026-04-02T00:00:01Z",
                "type": "message",
                "payload": {"role": "user", "content": "first", "message_id": "m-1", "turn_id": "t-1"},
            },
            # Corrupted: bad parent message id
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-3",
                "seq": 3,
                "ts": "2026-04-02T00:00:02Z",
                "type": "message",
                "payload": {"role": "user", "content": "corrupted", "message_id": "m-bad", "parent_message_id": "nonexistent", "turn_id": "t-bad"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-4",
                "seq": 4,
                "ts": "2026-04-02T00:00:03Z",
                "type": "message",
                "payload": {"role": "user", "content": "second", "message_id": "m-2", "parent_message_id": "m-1", "turn_id": "t-2"},
            },
        ]
        
        result = self.restorer.restore(events, best_effort=True)
        
        # Should have processed events 1, 2, and 4; skipped 3
        self.assertTrue(result.consumed_event_count >= 3)
        self.assertEqual(result.skipped_count, 1)
        self.assertTrue(len(result.session.turns) >= 1)

    def test_restore_with_duplicate_turn_id(self):
        """Best-effort should skip duplicate turn ids."""
        session_id = "sess-dup-turn"
        events = [
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-1",
                "seq": 1,
                "type": "session_meta",
                "payload": {"current_mode": "build"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-2",
                "seq": 2,
                "type": "message",
                "payload": {"role": "user", "content": "first", "message_id": "m-1", "turn_id": "t-1"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-3",
                "seq": 3,
                "type": "message",
                "payload": {"role": "user", "content": "dup", "message_id": "m-2", "turn_id": "t-1"},  # DUPLICATE turn_id
            },
        ]
        
        result = self.restorer.restore(events, best_effort=True)
        self.assertEqual(result.skipped_count, 1)
        # Note: duplicate turn_id is detected by _apply_message

    def test_restore_with_missing_parent_in_chain(self):
        """Best-effort should skip message with missing parent."""
        session_id = "sess-missing-parent"
        events = [
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-1",
                "seq": 1,
                "type": "session_meta",
                "payload": {"current_mode": "build"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-2",
                "seq": 2,
                "type": "message",
                "payload": {
                    "role": "user",
                    "content": "first",
                    "message_id": "m-1",
                    "turn_id": "t-1",
                },
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-3",
                "seq": 3,
                "type": "message",
                "payload": {
                    "role": "assistant",
                    "content": "reply",
                    "message_id": "m-2",
                    "parent_message_id": "nonexistent",  # BAD PARENT
                    "turn_id": "t-1",
                    "step_id": "s-1",
                },
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-4",
                "seq": 4,
                "type": "message",
                "payload": {
                    "role": "user",
                    "content": "second",
                    "message_id": "m-3",
                    "parent_message_id": "m-1",
                    "turn_id": "t-2",
                },
            },
        ]
        
        result = self.restorer.restore(events, best_effort=True)
        
        # Should skip the assistant message with bad parent
        self.assertEqual(result.skipped_count, 1)
        # But should continue to process user message m-3
        self.assertTrue(result.consumed_event_count >= 3)

    def test_restore_with_stale_interaction(self):
        """Best-effort should skip stale interaction."""
        session_id = "sess-stale"
        events = [
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-1",
                "seq": 1,
                "type": "session_meta",
                "payload": {"current_mode": "build"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-2",
                "seq": 2,
                "type": "message",
                "payload": {"role": "user", "content": "do something", "message_id": "m-1", "turn_id": "t-1"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-3",
                "seq": 3,
                "type": "step_started",
                "payload": {"turn_id": "t-1", "step_id": "s-1"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-4",
                "seq": 4,
                "type": "tool_call",
                "payload": {"turn_id": "t-1", "step_id": "s-1", "call_id": "c1", "tool_name": "write_file"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-5",
                "seq": 5,
                "type": "pending_interaction",
                "payload": {
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "interaction_id": "pi-1",
                    "kind": "permission",
                    "tool_name": "write_file",
                    "created_at": "2020-01-01T00:00:00Z",  # VERY OLD
                },
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-6",
                "seq": 6,
                "type": "message",
                "payload": {"role": "user", "content": "continue", "message_id": "m-2", "parent_message_id": "m-1", "turn_id": "t-2"},
            },
        ]
        
        result = self.restorer.restore(events, best_effort=True)
        
        # Should skip stale interaction
        self.assertEqual(result.skipped_count, 1)
        self.assertTrue(result.consumed_event_count >= 5)

    def test_restore_empty_events_raises(self):
        """Even best_effort should raise on empty events."""
        with self.assertRaises(ValueError):
            self.restorer.restore([], best_effort=True)

    def test_strict_mode_fails_fast(self):
        """Strict mode should stop at first error."""
        session_id = "sess-strict"
        events = [
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-1",
                "seq": 1,
                "type": "session_meta",
                "payload": {"current_mode": "build"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-2",
                "seq": 2,
                "type": "message",
                "payload": {"role": "user", "content": "first", "message_id": "m-1", "turn_id": "t-1"},
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-3",
                "seq": 3,
                "type": "message",
                "payload": {
                    "role": "assistant",
                    "content": "bad",
                    "message_id": "m-2",
                    "parent_message_id": "nonexistent",
                    "turn_id": "t-1",
                    "step_id": "s-1",
                },
            },
            {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": "evt-4",
                "seq": 4,
                "type": "message",
                "payload": {"role": "user", "content": "second", "message_id": "m-3", "parent_message_id": "m-1", "turn_id": "t-2"},
            },
        ]
        
        result = self.restorer.restore(events, best_effort=False)
        
        self.assertEqual(result.consumed_event_count, 2)  # Stopped before bad event
        self.assertEqual(result.skipped_count, 0)
        self.assertTrue(len(result.stop_reason) > 0)

    def test_corrupted_transcript_file_loads_valid_prefix(self):
        """TranscriptStore should load valid prefix when file has corruption."""
        session_id = "sess-file-corrupt"
        self.store.append_event(session_id, "session_meta", {"current_mode": "build"})
        self.store.append_event(session_id, "message", {"role": "user", "content": "first"})
        
        # Corrupt by adding bad line in middle
        path = self.store.resolve_transcript_path(session_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write("this is not json\n")
        
        # Should load events before corruption
        events = self.store.load_events(session_id)
        self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
