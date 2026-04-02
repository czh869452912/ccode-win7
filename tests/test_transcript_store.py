import os
import shutil
import sys
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

    def test_append_event_keeps_seq_monotonic(self):
        store = TranscriptStore(self.workspace)
        first = store.append_event("sess-seq", "session_meta", {"current_mode": "code"})
        second = store.append_event("sess-seq", "loop_transition", {"reason": "completed"})
        self.assertEqual(first["seq"], 1)
        self.assertEqual(second["seq"], 2)


if __name__ == "__main__":
    unittest.main()
