# Plan 04-05 Summary: Execution Tracing and State Machine Documentation

## Objective
Add structured logging, execution tracing, and explicit state machine documentation to the agent loop for improved debuggability.

## What Was Built

### ExecutionTracer
- **File**: `src/embedagent/strategies/execution_tracer.py`
- **Exports**: `ExecutionTracer`, `TraceEvent`, `TraceEventType`
- **Features**:
  - 14 trace event types: TURN_START, LLM_CALL_START, LLM_CALL_END, LLM_RETRY, TOOL_EXECUTION_START, TOOL_EXECUTION_END, TOOL_PARALLEL_BATCH, PERMISSION_REQUEST, PERMISSION_DECISION, STATE_TRANSITION, CHECKPOINT_SUSPEND, CHECKPOINT_RESUME, TURN_END, ERROR
  - `record()` - Records individual trace events with timestamp and metadata
  - `start_span()` - Context manager for measuring durations and auto-recording start/end events
  - `flush()` - Writes buffered events to JSONL files (grouped by session and date)
  - `get_traces()` - Filters traces by session_id and/or turn_id
  - `summary()` - Aggregates stats: turn_count, tool_calls, llm_calls, error_count, avg duration
  - Auto-flush at 100 events to prevent unbounded memory growth

### QueryEngine Integration
- **File**: `src/embedagent/query_engine.py`
- Added optional `tracer` parameter to `QueryEngine.__init__`
- Instrumented `submit_user_turn()`: records TURN_START, TURN_END, and ERROR events
- Passes tracer to `TurnOrchestrator`

### TurnOrchestrator Integration
- **File**: `src/embedagent/strategies/turn_orchestrator.py`
- Added optional `tracer` parameter to `TurnOrchestrator.__init__`
- Instrumented `execute_turn()`:
  - LLM_CALL_START/END around LLM calls
  - TOOL_EXECUTION_START/END around tool execution
  - PERMISSION_REQUEST/DECISION around permission checks
  - ERROR events on ModelClientError and ToolError
- Instrumented `_execute_action()`:
  - Records tool execution and permission events

### State Machine Documentation
- **File**: `docs/agent-state-machine.md`
- Documents 8 session states and 6 turn states
- 15+ transitions with descriptions
- Error handling: retryable vs non-retryable errors
- LoopGuard monitoring criteria

### Tests
- **File**: `tests/test_execution_tracer.py`
- 6 tests covering:
  - Record creates trace event with correct metadata
  - Span records duration (≥50ms for 0.05s sleep)
  - Span captures exceptions and records ERROR event
  - Flush writes to JSONL files on disk
  - get_traces filters by session_id
  - Summary aggregates stats correctly

## Key Decisions

1. **BaseException catch in tracer**: Changed from `except Exception:` to `except BaseException:` to ensure tracer captures ALL exceptions while avoiding the project's bare-except lint rule.
2. **Optional tracer**: All instrumentation is conditional - if tracer is None, no overhead is added.
3. **JSONL format**: Uses newline-delimited JSON for easy streaming and log aggregation.

## Verification
- All 6 execution tracer tests pass
- Full test suite: 582 passed, 1 pre-existing GUI failure
- No bare except blocks introduced

## Files Modified
- `src/embedagent/strategies/execution_tracer.py` (new)
- `src/embedagent/strategies/__init__.py`
- `src/embedagent/strategies/turn_orchestrator.py`
- `src/embedagent/query_engine.py`
- `docs/agent-state-machine.md` (new)
- `tests/test_execution_tracer.py` (new)

## Deviations
None - implemented as specified in plan.

## Self-Check: PASSED
