import unittest

from embedagent_core.context_window import ContextWindowState


class TestContextWindowState(unittest.TestCase):
    def test_auto_threshold_state_projects_boundary_fields(self):
        state = ContextWindowState.from_pipeline_steps(
            ["auto_compact_threshold", "summary/compact"],
            existing_boundary_count=1,
        )

        self.assertEqual(state.trigger, "auto_threshold")
        self.assertEqual(state.phase, "pre_provider")
        self.assertEqual(state.context_window_generation, 2)
        self.assertEqual(
            state.to_boundary_fields(),
            {
                "trigger": "auto_threshold",
                "phase": "pre_provider",
                "context_window_generation": 2,
            },
        )

    def test_reactive_retry_state_projects_provider_retry_phase(self):
        state = ContextWindowState.from_pipeline_steps(
            ["reactive_compact_retry", "summary/compact"],
            existing_boundary_count=0,
        )

        self.assertEqual(state.trigger, "reactive_retry")
        self.assertEqual(state.phase, "provider_retry")
        self.assertEqual(state.context_window_generation, 1)

    def test_metadata_extends_existing_values_without_policy_fields(self):
        state = ContextWindowState.from_pipeline_steps([], existing_boundary_count=0)

        self.assertEqual(state.to_boundary_fields(), {})
        self.assertEqual(
            state.extend_metadata({"pipeline_steps": ["summary/compact"]}),
            {"pipeline_steps": ["summary/compact"]},
        )


if __name__ == "__main__":
    unittest.main()
