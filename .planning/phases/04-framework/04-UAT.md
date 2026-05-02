---
status: testing
phase: 04-framework
source:
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
  - 04-03-SUMMARY.md
  - 04-04-SUMMARY.md
  - 04-05-SUMMARY.md
started: '2026-05-03T00:00:00Z'
updated: '2026-05-03T00:00:00Z'
---

## Current Test

number: 3
name: Shadow Git - Automatic Pre-Edit Snapshots
expected: |
  When edit_file tool modifies an existing file, a pre-edit snapshot
  is automatically created via git stash before the modification.
awaiting: user response

## Tests

### 1. Shadow Git - Create and List Snapshots
expected: ShadowGitSnapshot service creates snapshots with metadata JSON files, lists them sorted by created_at descending, and handles non-git repos with ToolError
result: pass

### 2. Shadow Git - Restore and Delete Snapshots
expected: Restoring a snapshot recovers the original file content. Deleting a snapshot removes metadata and drops the stash entry.
result: pending

### 2. Shadow Git - Restore and Delete Snapshots
expected: Restoring a snapshot recovers the original file content. Deleting a snapshot removes metadata and drops the stash entry.
result: pass

### 3. Shadow Git - Automatic Pre-Edit Snapshots
expected: When edit_file tool modifies an existing file, a pre-edit snapshot is automatically created via git stash before the modification
result: pass

### 4. Shadow Git - Git Snapshot Tool
expected: The git_snapshot tool is available in the tool catalog with actions create, list, restore, delete, cleanup
result: pass

### 5. Circuit Breaker - State Transitions
expected: CircuitBreaker starts CLOSED, opens after threshold failures, enters HALF_OPEN after timeout, and closes after successful calls
result: pass

### 6. Circuit Breaker - LLM Integration
expected: LLMClientRetryWrapper with circuit breaker stops calling LLM after repeated failures and raises CircuitBreakerOpenError
result: pass

### 7. Token Tracking
expected: Successful LLM calls track token usage (prompt_tokens, completion_tokens, total_tokens) in AssistantReply
result: pass

### 8. Tool Cache - L1 Memory Hit
expected: ToolResultCache returns cached results from L1 memory for repeated identical tool calls within the same session
result: pass

### 9. Tool Cache - TTL Expiration
expected: Cached results expire after TTL seconds and trigger fresh tool execution
result: pass

### 10. Tool Cache - LRU Eviction
expected: When L1 cache exceeds max_memory_entries, oldest entries are evicted while newer ones remain
result: pass

### 11. Diff Engine - Single Replacement
expected: MultiSearchReplaceDiffEngine applies single exact match replacements correctly
result: pass

### 12. Diff Engine - Multiple Blocks
expected: Multiple non-overlapping DiffBlocks are applied in a single operation
result: pass

### 13. Diff Engine - Fuzzy Matching
expected: Fuzzy matching handles whitespace variations and minor context differences (similarity >= 0.85)
result: pass

### 14. Diff Engine - Backward Compatibility
expected: edit_file tool still works with single old_text/new_text parameters (backward compatible)
result: pass

### 15. Execution Tracer - Event Recording
expected: ExecutionTracer records trace events with correct type, timestamp, session_id, and metadata
result: pass

### 16. Execution Tracer - Span Duration
expected: start_span context manager measures and records duration between start and end events
result: pass

### 17. Execution Tracer - Flush to Disk
expected: Buffered trace events are written to JSONL files on disk when flush() is called
result: pass

### 18. Execution Tracer - State Machine Documentation
expected: docs/agent-state-machine.md exists with session states, turn states, and transition descriptions
result: pass

### 19. Test Suite - No Regressions
expected: Full test suite passes (584 tests) with only 1 pre-existing GUI failure
result: pass

### 20. Test Suite - No New Deprecation Warnings
expected: No new DeprecationWarnings introduced by Phase 4 code
result: pass

## Summary

total: 20
passed: 20
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

none
