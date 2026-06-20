import unittest

from embedagent.compactor import DeterministicCompactor


class TestDeterministicCompactor(unittest.TestCase):
    def test_build_checkpoint_payload_from_boundary_inputs(self):
        compactor = DeterministicCompactor()
        payload = compactor.build_checkpoint_payload(
            boundary_id="cb-1",
            summary_text="Earlier work",
            created_at="2026-06-20T00:00:00Z",
            first_kept_message_id="m-kept",
            trigger="auto_threshold",
            phase="pre_provider",
            token_counts={"approx_before": 100, "approx_after": 50},
            message_counts={"before": 8, "after": 3, "summarized_turns": 5},
            file_activity={"read_files": ["src/a.c"], "modified_files": []},
            evidence_refs=["ref-a"],
            metadata={"pipeline_steps": ["auto_compact_threshold"]},
        )

        self.assertTrue(payload["checkpoint_id"].startswith("ch-"))
        self.assertEqual(payload["boundary_id"], "cb-1")
        self.assertEqual(payload["summary_text"], "Earlier work")
        self.assertEqual(payload["first_kept_message_id"], "m-kept")
        self.assertEqual(payload["replacement_messages"][0]["role"], "system")
        self.assertIn("Earlier work", payload["replacement_messages"][0]["content"])
        self.assertEqual(payload["token_counts"]["approx_after"], 50)


if __name__ == "__main__":
    unittest.main()
