import json
import unittest

from embedagent.compaction_state import CompactionStateReducer


class TestCompactionStateReducer(unittest.TestCase):
    def test_reducer_projects_structured_boundary(self):
        events = [
            {
                "type": "compact_boundary",
                "event_id": "evt-1",
                "seq": 7,
                "ts": "2026-06-14T00:00:00Z",
                "payload": {
                    "boundary_id": "cb-1",
                    "summary_text": "Earlier work summary",
                    "compacted_turn_count": 4,
                    "created_at": "2026-06-14T00:00:00Z",
                    "mode_name": "build",
                    "preserved_head_message_id": "m-head",
                    "preserved_tail_message_id": "m-tail",
                    "trigger": "auto_threshold",
                    "phase": "pre_provider",
                    "context_window_generation": 2,
                    "metadata": {"pipeline_steps": ["select", "compact"]},
                    "token_counts": {"approx_before": 1800, "approx_after": 520},
                    "message_counts": {
                        "before": 12,
                        "after": 5,
                        "summarized_turns": 4,
                        "recent_turns": 2,
                    },
                    "file_activity": {
                        "read_files": ["src/demo.c", "src/demo.c", "include/demo.h"],
                        "modified_files": ["src/demo.c"],
                    },
                    "evidence_refs": [
                        ".embedagent/memory/sessions/sess/tool-results/read-1/content.txt",
                        ".embedagent/memory/sessions/sess/tool-results/read-1/content.txt",
                    ],
                    "extension_summary": False,
                },
            }
        ]

        state = CompactionStateReducer().reduce(events)
        payload = state.to_dict()

        self.assertEqual(payload["boundary_count"], 1)
        self.assertEqual(payload["latest_boundary_id"], "cb-1")
        self.assertEqual(payload["latest_boundary"]["summary_text"], "Earlier work summary")
        self.assertEqual(payload["latest_boundary"]["token_counts"]["approx_before"], 1800)
        self.assertEqual(payload["latest_boundary"]["token_counts"]["approx_after"], 520)
        self.assertEqual(payload["latest_boundary"]["message_counts"]["summarized_turns"], 4)
        self.assertEqual(payload["latest_boundary"]["message_counts"]["recent_turns"], 2)
        self.assertEqual(payload["latest_boundary"]["trigger"], "auto_threshold")
        self.assertEqual(payload["latest_boundary"]["phase"], "pre_provider")
        self.assertEqual(payload["latest_boundary"]["context_window_generation"], 2)
        self.assertEqual(
            payload["latest_boundary"]["file_activity"]["read_files"],
            ["include/demo.h", "src/demo.c"],
        )
        self.assertEqual(
            payload["latest_boundary"]["file_activity"]["modified_files"], ["src/demo.c"]
        )
        self.assertEqual(
            payload["latest_boundary"]["evidence_refs"],
            [".embedagent/memory/sessions/sess/tool-results/read-1/content.txt"],
        )
        self.assertEqual(payload["diagnostics"], [])
        json.dumps(payload, sort_keys=True)

    def test_reducer_accepts_legacy_boundary_payload(self):
        events = [
            {
                "type": "compact_boundary",
                "event_id": "evt-legacy",
                "seq": 3,
                "ts": "2026-06-14T00:00:00Z",
                "payload": {
                    "boundary_id": "cb-legacy",
                    "summary_text": "Legacy summary",
                    "compacted_turn_count": 9,
                    "created_at": "2026-06-14T00:00:00Z",
                    "mode_name": "build",
                    "preserved_head_message_id": "m-head",
                    "preserved_tail_message_id": "m-tail",
                    "metadata": {"approx_tokens": 700, "replacements": 2},
                },
            }
        ]

        payload = CompactionStateReducer().reduce(events).to_dict()

        self.assertEqual(payload["boundary_count"], 1)
        self.assertEqual(payload["latest_boundary_id"], "cb-legacy")
        self.assertEqual(payload["latest_boundary"]["token_counts"]["approx_after"], 700)
        self.assertEqual(payload["latest_boundary"]["message_counts"]["summarized_turns"], 9)
        self.assertEqual(payload["latest_boundary"]["file_activity"]["read_files"], [])
        self.assertEqual(payload["latest_boundary"]["evidence_refs"], [])

    def test_reducer_deduplicates_boundary_id(self):
        events = [
            {
                "type": "compact_boundary",
                "event_id": "evt-1",
                "seq": 1,
                "payload": {
                    "boundary_id": "cb-dup",
                    "summary_text": "First",
                    "compacted_turn_count": 1,
                },
            },
            {
                "type": "compact_boundary",
                "event_id": "evt-2",
                "seq": 2,
                "payload": {
                    "boundary_id": "cb-dup",
                    "summary_text": "Second",
                    "compacted_turn_count": 2,
                },
            },
        ]

        payload = CompactionStateReducer().reduce(events).to_dict()

        self.assertEqual(payload["boundary_count"], 1)
        self.assertEqual(payload["boundaries"][0]["summary_text"], "First")
        self.assertEqual(len(payload["diagnostics"]), 1)
        self.assertEqual(payload["diagnostics"][0]["reason"], "duplicate_boundary_id")
        self.assertEqual(payload["diagnostics"][0]["boundary_id"], "cb-dup")


if __name__ == "__main__":
    unittest.main()
