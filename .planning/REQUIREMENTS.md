# Requirements: Milestone v0.2 — GUI & Harness Experience Refactor

## Session Infrastructure (SESS)

### SESS-01: Typed JSONL Transcript
**User need:** Session history must be durable, inspectable, and recoverable across restarts.
**Requirement:** Transcript events use schema_version=2 with explicit message types (user, assistant, tool_use, tool_result, command_execution, file_change, compact, interaction).
**Acceptance:**
- [ ] New sessions write schema_version=2 transcript
- [ ] Old schema_version=1 transcripts remain readable
- [ ] Each message has explicit `type` field
- [ ] `parent_message_id` forms complete parent chain

### SESS-02: Parent Message Chain
**User need:** Session resume must reconstruct conversation context correctly.
**Requirement:** Messages link via `parent_message_id` forming an unbroken chain from session start to latest message.
**Acceptance:**
- [ ] Every message has a `parent_message_id` (empty string for first message)
- [ ] Resume validates parent chain integrity
- [ ] Broken parent chain is detectable and reportable

### SESS-03: Item Lifecycle Events
**User need:** Real-time visibility into tool execution progress.
**Requirement:** Tool and command execution emit lifecycle events: started → [updated] → completed|failed|rejected.
**Acceptance:**
- [ ] `item.started` event emitted when tool execution begins
- [ ] `item.updated` event emitted for incremental output (commands)
- [ ] `item.completed` event emitted on success
- [ ] `item.failed` event emitted on error
- [ ] `item.rejected` event emitted when user denies permission

### SESS-04: Best-Effort Session Restore
**User need:** A single corrupted record should not destroy an entire session.
**Requirement:** Session restore supports best_effort mode that skips corrupted/mismatched records and continues recovery.
**Acceptance:**
- [x] `SessionRestorer.restore()` accepts `best_effort=True` parameter
- [x] Corrupted single record is skipped with warning logged
- [x] Recovery continues with subsequent valid records
- [x] Restore result reports: consumed_count, skipped_count, skip_reasons
- [x] Strict mode (`best_effort=False`) preserves old behavior for tests

### SESS-05: Flat Conversation Model
**User need:** Conversation history should be easy to consume by frontend without deep nested parsing.
**Requirement:** `SessionHistoryAssembler` produces flat `items[]` array where each item is a self-contained message with type, id, parent_id, status, and content.
**Acceptance:**
- [ ] `build_flat_timeline()` returns flat items array
- [ ] Each item has: type, id, content, status, parent_id, turn_id
- [ ] Tool items have: tool_name, call_id, arguments, data
- [ ] Old `build()` method remains available for backward compatibility
- [ ] Frontend Timeline can render directly from items[] without nested parsing

## GUI Experience (GUI)

### GUI-01: Inline Tool Cards
**User need:** Tool execution should be visible inline in the conversation, not hidden in collapsible panels.
**Requirement:** Timeline renders tool calls as inline cards showing tool name, arguments, status, and result/error.
**Acceptance:**
- [ ] Tool calls display inline (not in nested step panels)
- [ ] Card shows tool name and key arguments (truncated)
- [ ] Status indicator: queued → in_progress → completed|failed|rejected
- [ ] Result/error expandable inline
- [ ] Long outputs truncated with "...N more lines" indicator

### GUI-02: Inline Diff Preview
**User need:** File edits should be reviewable directly in the conversation flow.
**Requirement:** File changes render as inline diff blocks with line numbers, gutter markers, and syntax highlighting.
**Acceptance:**
- [ ] Diff shows line numbers (old and new)
- [ ] Gutter markers: `+` for additions, `-` for deletions, ` ` for context
- [ ] Syntax highlighting for recognized file types
- [ ] Dark/light theme adaptive coloring
- [ ] Diff is collapsible (show first N hunks, expand for rest)

### GUI-03: Real-Time Streaming
**User need:** Long-running commands should show progress in real-time.
**Requirement:** Command execution output streams incrementally to the UI via `item.updated` events.
**Acceptance:**
- [ ] Command output streams line-by-line as it executes
- [ ] UI updates without requiring command completion
- [ ] Streaming indicator visible while command runs
- [ ] Final exit code displayed on completion

### GUI-04: Conversation-First Layout
**User need:** The primary focus should be the conversation, not auxiliary panels.
**Requirement:** Main layout is Sidebar (file tree + status) + Chat (conversation), with Inspector content moved inline or simplified.
**Acceptance:**
- [ ] Main chat area occupies majority of screen width
- [ ] Sidebar shows file tree and brief status
- [ ] Tool results, diffs, and interactions display inline in chat
- [ ] Inspector panel either removed or simplified to essentials
- [ ] Composer remains at bottom with mode indicator

## Harness Execution (HARN)

### HARN-01: Mode Permission Contract
**User need:** Entering a mode should not trigger unwanted workflow execution.
**Requirement:** Mode controls only system prompt, allowed tools, and writable paths. Workflow/task graph is generated only when user explicitly requests work.
**Acceptance:**
- [x] Entering build mode and saying "hi" produces normal chat response
- [x] No fixed phase track injected unconditionally
- [x] Task graph generated only on explicit user work request
- [x] Mode system prompt describes permissions, not workflow steps

### HARN-02: Intent-Driven Workflow
**User need:** The agent should understand when to start working vs. just chatting.
**Requirement:** Agent distinguishes between casual conversation and explicit work requests, generating task graph only for the latter.
**Acceptance:**
- [x] "Explain this code" → explore/spec response, no task graph
- [x] "Fix this bug" → generates debug task graph
- [x] "Implement X" → generates build task graph
- [x] "Run tests" → generates verify task graph
- [x] Task graph dynamically created based on user intent, not mode preset

### HARN-03: Completion Signal
**User need:** The agent should know when to stop, not be cut off by arbitrary limits.
**Requirement:** Agent outputs explicit completion signal when task is done; system recognizes signal and terminates gracefully.
**Acceptance:**
- [ ] Agent trained/prompted to output completion signal (`<task_complete>` or equivalent)
- [ ] System detects completion signal and stops turn
- [ ] Completion signal includes summary of what was done
- [ ] No fixed max_turns limit enforced

### HARN-04: Guard-Based Safety
**User need:** The agent should not loop infinitely when completion signal is missed.
**Requirement:** Guard detects runaway behavior (repeated identical tool calls, consecutive failures) and stops execution.
**Acceptance:**
- [ ] Guard detects N consecutive identical tool calls (default 3)
- [ ] Guard detects N consecutive tool failures (default 3)
- [ ] Guard stops execution with explanatory message
- [ ] User can override and continue if needed

## Traceability

| Requirement | Phase | Plans |
|-------------|-------|-------|
| SESS-01 | 5 | 5-01 |
| SESS-02 | 5 | 5-01 |
| SESS-03 | 5 | 5-01 |
| SESS-04 | 5 | 5-02 |
| SESS-05 | 5 | 5-03 |
| GUI-01 | 6 | 6-01 |
| GUI-02 | 6 | 6-02 |
| GUI-03 | 6 | 6-03 |
| GUI-04 | 6 | 6-01 |
| HARN-01 | 7 | 7-01 |
| HARN-02 | 7 | 7-01 |
| HARN-03 | 7 | 7-02 |
| HARN-04 | 7 | 7-03 |

## Out of Scope

- Browser automation (not a web agent)
- Web search (offline deployment mandatory)
- Cloud service integration (offline mandatory)
- Multi-agent orchestration (single agent focus)
- Mobile/responsive GUI (Windows 7 desktop only)
- Database-backed session storage (JSONL mandate)
