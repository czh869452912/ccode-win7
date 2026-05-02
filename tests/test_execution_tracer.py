"""Tests for ExecutionTracer."""

import os
import tempfile
import time
import unittest

from embedagent.strategies.execution_tracer import ExecutionTracer, TraceEventType


class TestExecutionTracer(unittest.TestCase):
    def test_record_creates_trace_event(self):
        tracer = ExecutionTracer()
        event = tracer.record(
            TraceEventType.TURN_START,
            "session_1",
            "turn_1",
            data={"mode": "build"},
        )
        self.assertEqual(event.event_type, TraceEventType.TURN_START)
        self.assertEqual(event.session_id, "session_1")
        self.assertEqual(event.turn_id, "turn_1")
        self.assertEqual(event.data["mode"], "build")
        self.assertIsNotNone(event.timestamp)

    def test_start_span_records_duration(self):
        tracer = ExecutionTracer()
        with tracer.start_span(TraceEventType.LLM_CALL_START, "session_1", "turn_1"):
            time.sleep(0.05)

        traces = tracer.get_traces(session_id="session_1")
        # Should have start and end events
        self.assertEqual(len(traces), 2)
        end_event = traces[1]
        self.assertEqual(end_event.event_type, TraceEventType.LLM_CALL_END)
        self.assertIsNotNone(end_event.duration_ms)
        self.assertGreaterEqual(end_event.duration_ms, 50)

    def test_span_captures_exception(self):
        tracer = ExecutionTracer()
        with self.assertRaises(RuntimeError):
            with tracer.start_span(TraceEventType.LLM_CALL_START, "session_1", "turn_1"):
                raise RuntimeError("test error")

        traces = tracer.get_traces(session_id="session_1")
        error_events = [e for e in traces if e.event_type == TraceEventType.ERROR]
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0].data["error_type"], "RuntimeError")

    def test_flush_writes_to_disk(self):
        output_dir = tempfile.mkdtemp()
        tracer = ExecutionTracer(output_dir=output_dir)
        tracer.record(TraceEventType.TURN_START, "session_1", "turn_1")
        tracer.record(TraceEventType.TURN_END, "session_1", "turn_1")
        tracer.flush()

        files = os.listdir(output_dir)
        self.assertEqual(len(files), 1)
        filepath = os.path.join(output_dir, files[0])
        with open(filepath, "r") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

    def test_get_traces_filters_by_session(self):
        tracer = ExecutionTracer()
        tracer.record(TraceEventType.TURN_START, "session_1", "turn_1")
        tracer.record(TraceEventType.TURN_START, "session_2", "turn_2")

        traces = tracer.get_traces(session_id="session_1")
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].session_id, "session_1")

    def test_summary_aggregates_stats(self):
        tracer = ExecutionTracer()
        tracer.record(TraceEventType.TURN_START, "session_1", "turn_1")
        tracer.record(TraceEventType.TURN_END, "session_1", "turn_1", duration_ms=100)
        tracer.record(TraceEventType.LLM_CALL_START, "session_1", "turn_1")
        tracer.record(TraceEventType.TOOL_EXECUTION_START, "session_1", "turn_1")
        tracer.record(TraceEventType.ERROR, "session_1", "turn_1")

        stats = tracer.summary("session_1")
        self.assertEqual(stats["turn_count"], 1)
        self.assertEqual(stats["total_llm_calls"], 1)
        self.assertEqual(stats["total_tool_calls"], 1)
        self.assertEqual(stats["error_count"], 1)
        self.assertEqual(stats["avg_turn_duration_ms"], 100)


if __name__ == "__main__":
    unittest.main()
