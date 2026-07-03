import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.session import Action, Observation
from embedagent.tool_execution import StreamingToolExecutor, ToolBatch


class TestStreamingToolExecutor(unittest.TestCase):
    def test_parallel_executor_returns_cancelled_updates_without_hanging(self):
        started = threading.Event()
        cancel_event = threading.Event()

        def execute_action(action):
            started.set()
            threading.Event().wait(10.0)
            return Observation(action.name, True, None, {"call_id": action.call_id})

        executor = StreamingToolExecutor(
            execute_action,
            max_parallel=1,
            cancel_event=cancel_event,
            idle_timeout_seconds=0.1,
            poll_interval_seconds=0.02,
        )
        actions = [
            Action("read_file", {"path": "a.c"}, "call-a"),
            Action("read_file", {"path": "b.c"}, "call-b"),
        ]

        def trigger_cancel():
            self.assertTrue(started.wait(0.5))
            cancel_event.set()

        thread = threading.Thread(target=trigger_cancel)
        thread.start()
        try:
            begin = time.time()
            updates = list(executor.run_batch(ToolBatch(parallel=True, actions=actions)))
            elapsed = time.time() - begin
        finally:
            thread.join(1.0)

        self.assertLess(elapsed, 1.0)
        self.assertEqual(
            [(item.phase, item.action.call_id) for item in updates],
            [
                ("start", "call-a"),
                ("result", "call-a"),
                ("result", "call-b"),
            ],
        )
        self.assertEqual(updates[1].observation.data.get("error_kind"), "interrupted")
        self.assertEqual(updates[2].observation.data.get("error_kind"), "discarded")

    def test_parallel_executor_times_out_idle_started_actions(self):
        release = threading.Event()

        def execute_action(action):
            release.wait(10.0)
            return Observation(action.name, True, None, {"call_id": action.call_id})

        executor = StreamingToolExecutor(
            execute_action,
            max_parallel=2,
            cancel_event=None,
            idle_timeout_seconds=0.1,
            poll_interval_seconds=0.02,
        )
        actions = [
            Action("read_file", {"path": "a.c"}, "call-a"),
            Action("read_file", {"path": "b.c"}, "call-b"),
        ]

        begin = time.time()
        updates = list(executor.run_batch(ToolBatch(parallel=True, actions=actions)))
        elapsed = time.time() - begin
        release.set()

        self.assertLess(elapsed, 1.0)
        self.assertEqual(
            [(item.phase, item.action.call_id) for item in updates],
            [
                ("start", "call-a"),
                ("start", "call-b"),
                ("result", "call-a"),
                ("result", "call-b"),
            ],
        )
        self.assertEqual(updates[2].observation.data.get("error_kind"), "timeout")
        self.assertEqual(updates[3].observation.data.get("error_kind"), "timeout")

    def test_parallel_executor_discards_unstarted_siblings_after_earlier_failure(self):
        slow_release = threading.Event()
        started = []

        def execute_action(action):
            started.append(action.call_id)
            if action.call_id == "call-a":
                slow_release.wait(1.0)
                return Observation(
                    action.name,
                    False,
                    "missing",
                    {"error_kind": "tool_error", "retryable": False},
                )
            return Observation(action.name, True, None, {"call_id": action.call_id})

        executor = StreamingToolExecutor(
            execute_action,
            max_parallel=2,
            idle_timeout_seconds=2.0,
            poll_interval_seconds=0.02,
        )
        actions = [
            Action("read_file", {"path": "missing.c"}, "call-a"),
            Action("read_file", {"path": "fast.c"}, "call-b"),
            Action("read_file", {"path": "late.c"}, "call-c"),
        ]

        def release_failure():
            time.sleep(0.1)
            slow_release.set()

        thread = threading.Thread(target=release_failure)
        thread.start()
        try:
            updates = list(executor.run_batch(ToolBatch(parallel=True, actions=actions)))
        finally:
            thread.join(1.0)

        self.assertEqual(
            [(item.phase, item.action.call_id) for item in updates],
            [
                ("start", "call-a"),
                ("start", "call-b"),
                ("result", "call-a"),
                ("result", "call-b"),
                ("result", "call-c"),
            ],
        )
        self.assertEqual(updates[2].observation.data.get("error_kind"), "tool_error")
        self.assertIsNone(updates[3].observation.data.get("error_kind"))
        self.assertEqual(updates[4].observation.data.get("error_kind"), "discarded")
        self.assertNotIn("call-c", started)


if __name__ == "__main__":
    unittest.main()
