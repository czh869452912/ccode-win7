import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.transcript_store import TranscriptStore
from embedagent_core.session_operation_log import OperationLogReducer
from embedagent_core.session_restore import SessionRestorer

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


class TestOperationLogReducer(unittest.TestCase):
    def test_unfinished_explicit_tool_operation_is_interrupted_and_not_retryable(self):
        events = [
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-tool",
                "seq": 1,
                "ts": "2026-06-13T00:00:00Z",
                "type": "operation_started",
                "payload": {
                    "operation_id": "tool:call-read",
                    "kind": "tool_call",
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "tool_call_id": "call-read",
                    "metadata": {
                        "tool_name": "read_file",
                        "arguments": {"path": "src/demo.c"},
                    },
                },
            }
        ]

        state = OperationLogReducer().reduce(events)

        record = state.operations["tool:call-read"]
        self.assertEqual(record.status, "interrupted")
        self.assertEqual(record.kind, "tool_call")
        self.assertFalse(record.retryable)
        self.assertEqual(record.interrupted_reason, "restore_incomplete_operation")
        self.assertEqual(state.interrupted_count, 1)

    def test_live_reducer_keeps_unfinished_operation_active(self):
        events = [
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-provider",
                "seq": 1,
                "ts": "2026-06-13T00:00:00Z",
                "type": "operation_started",
                "payload": {
                    "operation_id": "provider:req-1",
                    "kind": "provider_request",
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "retryable": True,
                },
            }
        ]

        state = OperationLogReducer(close_unfinished=False).reduce(events)

        record = state.operations["provider:req-1"]
        self.assertEqual(record.status, "started")
        self.assertEqual(state.started_count, 1)
        self.assertEqual(state.interrupted_count, 0)

    def test_explicit_operation_finished_finishes_matching_tool_operation(self):
        events = [
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-tool",
                "seq": 1,
                "ts": "2026-06-13T00:00:00Z",
                "type": "operation_started",
                "payload": {
                    "operation_id": "tool:call-read",
                    "kind": "tool_call",
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "tool_call_id": "call-read",
                    "metadata": {
                        "tool_name": "read_file",
                        "arguments": {"path": "src/demo.c"},
                    },
                },
            },
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-result",
                "seq": 2,
                "ts": "2026-06-13T00:00:01Z",
                "type": "operation_finished",
                "payload": {
                    "operation_id": "tool:call-read",
                    "kind": "tool_call",
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "tool_call_id": "call-read",
                    "finished_at": "2026-06-13T00:00:01Z",
                    "result": {"success": True, "error": None},
                },
            },
        ]

        state = OperationLogReducer().reduce(events)

        record = state.operations["tool:call-read"]
        self.assertEqual(record.status, "finished")
        self.assertEqual(record.finished_at, "2026-06-13T00:00:01Z")
        self.assertEqual(state.interrupted_count, 0)

    def test_legacy_tool_events_do_not_create_operation_state(self):
        events = [
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-tool",
                "seq": 1,
                "ts": "2026-06-13T00:00:00Z",
                "type": "tool_call",
                "payload": {
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "call_id": "call-read",
                    "tool_name": "read_file",
                    "arguments": {"path": "src/demo.c"},
                },
            },
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-result",
                "seq": 2,
                "ts": "2026-06-13T00:00:01Z",
                "type": "tool_result",
                "payload": {
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "call_id": "call-read",
                    "tool_name": "read_file",
                    "observation": {"success": True, "error": None, "data": {}},
                },
            },
        ]

        state = OperationLogReducer().reduce(events)

        self.assertEqual(state.operations, {})

    def test_explicit_operation_events_override_legacy_events(self):
        events = [
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-start",
                "seq": 1,
                "ts": "2026-06-13T00:00:00Z",
                "type": "operation_started",
                "payload": {
                    "operation_id": "provider:req-1",
                    "kind": "provider_request",
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "retryable": True,
                    "metadata": {"model": "kimi"},
                },
            },
            {
                "schema_version": 2,
                "session_id": "sess-op",
                "event_id": "evt-finish",
                "seq": 2,
                "ts": "2026-06-13T00:00:02Z",
                "type": "operation_finished",
                "payload": {
                    "operation_id": "provider:req-1",
                    "finished_at": "2026-06-13T00:00:02Z",
                    "result": {"finish_reason": "stop"},
                },
            },
        ]

        state = OperationLogReducer().reduce(events)

        record = state.operations["provider:req-1"]
        self.assertEqual(record.status, "finished")
        self.assertTrue(record.retryable)
        self.assertEqual(record.metadata["model"], "kimi")
        self.assertEqual(record.result["finish_reason"], "stop")


class TestOperationLogRestoreIntegration(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("operation-log-restore")
        self.store = TranscriptStore(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_restore_exposes_explicit_interrupted_operation_state(self):
        session_id = "sess-op-restore"
        self.store.append_event(session_id, "session_meta", {"current_mode": "build"})
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "user",
                "content": "读取文件",
                "message_id": "m-user",
                "turn_id": "t-1",
                "step_id": "",
            },
        )
        self.store.append_event(
            session_id,
            "step_started",
            {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
        )
        self.store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "call-read",
                "tool_name": "read_file",
                "arguments": {"path": "src/demo.c"},
            },
        )
        self.store.append_event(
            session_id,
            "operation_started",
            {
                "operation_id": "step:s-1",
                "kind": "agent_step",
                "turn_id": "t-1",
                "step_id": "s-1",
            },
            schema_version=2,
        )
        self.store.append_event(
            session_id,
            "operation_started",
            {
                "operation_id": "tool:call-read",
                "kind": "tool_call",
                "turn_id": "t-1",
                "step_id": "s-1",
                "tool_call_id": "call-read",
            },
            schema_version=2,
        )

        result = SessionRestorer().restore(self.store.load_events(session_id))

        step_record = result.operation_state.operations["step:s-1"]
        tool_record = result.operation_state.operations["tool:call-read"]
        self.assertEqual(step_record.status, "interrupted")
        self.assertEqual(tool_record.status, "interrupted")
        self.assertEqual(result.operation_state.interrupted_count, 2)

    def test_restore_does_not_infer_operation_state_from_legacy_events(self):
        session_id = "sess-op-legacy"
        self.store.append_event(session_id, "session_meta", {"current_mode": "build"})
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "user",
                "content": "读取文件",
                "message_id": "m-user",
                "turn_id": "t-1",
                "step_id": "",
            },
        )
        self.store.append_event(
            session_id,
            "step_started",
            {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
        )
        self.store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "call-read",
                "tool_name": "read_file",
                "arguments": {"path": "src/demo.c"},
            },
        )

        result = SessionRestorer().restore(self.store.load_events(session_id))

        self.assertEqual(result.operation_state.operations, {})


if __name__ == "__main__":
    unittest.main()
