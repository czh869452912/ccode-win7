import os
import shutil
import sys
import threading
import time
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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


class TestTranscriptStore(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("transcript-store")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_append_and_load_roundtrip(self):
        store = TranscriptStore(self.workspace)
        store.append_event(
            "sess-roundtrip",
            "session_meta",
            {"current_mode": "build", "started_at": "2026-04-02T00:00:00Z"},
        )
        store.append_event(
            "sess-roundtrip",
            "message",
            {
                "role": "user",
                "message_id": "m-user-1",
                "turn_id": "t-1",
                "step_id": "",
                "content": "continue",
            },
        )
        events = store.load_events("sess-roundtrip")
        self.assertEqual([item["seq"] for item in events], [1, 2])
        self.assertEqual(events[0]["type"], "session_meta")
        self.assertEqual(events[1]["payload"]["content"], "continue")

    def test_load_events_ignores_damaged_tail(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-tail", "session_meta", {"current_mode": "debug"})
        path = store.resolve_transcript_path("sess-tail")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{bad-json")
        events = store.load_events("sess-tail")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "session_meta")

    def test_load_events_stops_at_sequence_gap(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-gap", "session_meta", {"current_mode": "debug"})
        store.append_event(
            "sess-gap",
            "message",
            {
                "role": "user",
                "message_id": "m-user-1",
                "turn_id": "t-1",
                "step_id": "",
                "content": "continue",
            },
        )
        path = store.resolve_transcript_path("sess-gap")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                '{"schema_version":1,"session_id":"sess-gap","event_id":"evt-gap","seq":5,"ts":"2026-04-04T00:00:00Z","type":"loop_transition","payload":{"reason":"completed"}}\n'
            )
        events = store.load_events("sess-gap")
        self.assertEqual([item["seq"] for item in events], [1, 2])

    def test_append_event_truncates_damaged_tail_before_continuing(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-recover", "session_meta", {"current_mode": "debug"})
        path = store.resolve_transcript_path("sess-recover")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{bad-json")

        store.append_event(
            "sess-recover",
            "message",
            {
                "role": "user",
                "message_id": "m-user-1",
                "turn_id": "t-1",
                "step_id": "",
                "content": "recovered",
            },
        )

        events = store.load_events("sess-recover")
        self.assertEqual([item["seq"] for item in events], [1, 2])
        self.assertEqual(events[-1]["payload"]["content"], "recovered")

    def test_append_event_keeps_seq_monotonic(self):
        store = TranscriptStore(self.workspace)
        first = store.append_event("sess-seq", "session_meta", {"current_mode": "build"})
        second = store.append_event("sess-seq", "loop_transition", {"reason": "completed"})
        self.assertEqual(first["seq"], 1)
        self.assertEqual(second["seq"], 2)

    def test_append_event_uses_cached_seq_after_first_write(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-cache", "session_meta", {"current_mode": "build"})
        original_scan = store._scan_events

        def fail_scan(path):
            raise AssertionError("unexpected transcript rescan for cached append: %s" % path)

        store._scan_events = fail_scan
        try:
            second = store.append_event(
                "sess-cache",
                "message",
                {
                    "role": "user",
                    "message_id": "m-cache",
                    "turn_id": "t-1",
                    "step_id": "",
                    "content": "cached",
                },
            )
        finally:
            store._scan_events = original_scan
        self.assertEqual(second["seq"], 2)

    def test_append_event_serializes_concurrent_writers(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-race", "session_meta", {"current_mode": "build"})

        original_next_seq = store._next_seq
        first_seq_started = threading.Event()
        first_call_seen = [False]

        def delayed_next_seq(path):
            seq = original_next_seq(path)
            if not first_call_seen[0]:
                first_call_seen[0] = True
                first_seq_started.set()
                time.sleep(0.2)
            return seq

        store._next_seq = delayed_next_seq
        errors = []

        def writer(index):
            try:
                store.append_event(
                    "sess-race",
                    "message",
                    {
                        "role": "user",
                        "message_id": "m-%s" % index,
                        "turn_id": "t-1",
                        "step_id": "",
                        "content": "message-%s" % index,
                    },
                )
            except Exception as exc:  # pragma: no cover - surfaced by assertion below
                errors.append(exc)

        thread_a = threading.Thread(target=writer, args=(1,))
        thread_b = threading.Thread(target=writer, args=(2,))
        thread_a.start()
        self.assertTrue(first_seq_started.wait(1.0))
        thread_b.start()
        thread_a.join()
        thread_b.join()

        self.assertEqual(errors, [])
        events = store.load_events("sess-race")
        self.assertEqual([item["seq"] for item in events], [1, 2, 3])
        self.assertEqual(events[-2]["payload"]["content"], "message-1")
        self.assertEqual(events[-1]["payload"]["content"], "message-2")

    def test_append_event_schema_v2_format(self):
        store = TranscriptStore(self.workspace)
        event = store.append_event(
            "sess-v2",
            "user",
            {"role": "user", "content": "hi", "parent_message_id": ""},
            schema_version=2,
        )
        self.assertEqual(event["schema_version"], 2)
        self.assertEqual(event["type"], "user")
        self.assertIn("parent_message_id", event)
        events = store.load_events("sess-v2")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["schema_version"], 2)
        self.assertEqual(events[0]["type"], "user")
        self.assertIn("parent_message_id", events[0])

    def test_load_events_normalizes_schema_v1(self):
        store = TranscriptStore(self.workspace)
        path = store.resolve_transcript_path("sess-v1")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"schema_version":1,"session_id":"sess-v1","event_id":"evt-1","seq":1,"ts":"2026-04-04T00:00:00Z","type":"message","payload":{"role":"user","content":"hello","message_id":"m-1"}}\n'
            )
        events = store.load_events("sess-v1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["schema_version"], 2)
        self.assertEqual(events[0]["type"], "user")

    def test_mixed_schema_v1_and_v2_readable(self):
        store = TranscriptStore(self.workspace)
        path = store.resolve_transcript_path("sess-mixed")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                '{"schema_version":1,"session_id":"sess-mixed","event_id":"evt-1","seq":1,"ts":"2026-04-04T00:00:00Z","type":"message","payload":{"role":"user","content":"v1","message_id":"m-1"}}\n'
            )
            handle.write(
                '{"schema_version":2,"session_id":"sess-mixed","event_id":"evt-2","seq":2,"ts":"2026-04-04T00:00:01Z","type":"assistant","parent_message_id":"m-1","payload":{"role":"assistant","content":"v2","message_id":"m-2"}}\n'
            )
        events = store.load_events("sess-mixed")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["schema_version"], 2)
        self.assertEqual(events[0]["type"], "user")
        self.assertEqual(events[1]["schema_version"], 2)
        self.assertEqual(events[1]["type"], "assistant")
        self.assertEqual(events[1]["parent_message_id"], "m-1")

    def test_validate_transcript_chain_valid(self):
        store = TranscriptStore(self.workspace)
        store.append_event(
            "sess-valid",
            "user",
            {"role": "user", "content": "first", "message_id": "m-1", "parent_message_id": ""},
            schema_version=2,
        )
        store.append_event(
            "sess-valid",
            "assistant",
            {"role": "assistant", "content": "second", "message_id": "m-2", "parent_message_id": "m-1"},
            schema_version=2,
        )
        store.append_event(
            "sess-valid",
            "user",
            {"role": "user", "content": "third", "message_id": "m-3", "parent_message_id": "m-2"},
            schema_version=2,
        )
        result = store.validate_transcript_chain("sess-valid")
        self.assertTrue(result["valid"])
        self.assertEqual(result["breaks"], [])

    def test_validate_transcript_chain_broken(self):
        store = TranscriptStore(self.workspace)
        store.append_event(
            "sess-broken",
            "user",
            {"role": "user", "content": "first", "message_id": "m-1", "parent_message_id": ""},
            schema_version=2,
        )
        store.append_event(
            "sess-broken",
            "assistant",
            {"role": "assistant", "content": "second", "message_id": "m-2", "parent_message_id": "m-nonexistent"},
            schema_version=2,
        )
        result = store.validate_transcript_chain("sess-broken")
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["breaks"]), 1)
        self.assertIn("parent_not_found", result["breaks"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
