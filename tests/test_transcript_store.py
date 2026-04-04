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
            {"current_mode": "code", "started_at": "2026-04-02T00:00:00Z"},
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
        first = store.append_event("sess-seq", "session_meta", {"current_mode": "code"})
        second = store.append_event("sess-seq", "loop_transition", {"reason": "completed"})
        self.assertEqual(first["seq"], 1)
        self.assertEqual(second["seq"], 2)

    def test_append_event_serializes_concurrent_writers(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-race", "session_meta", {"current_mode": "code"})

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


if __name__ == "__main__":
    unittest.main()
