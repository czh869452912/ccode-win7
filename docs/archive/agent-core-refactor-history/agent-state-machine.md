# Agent Execution State Machine

## States

### Session States
- `UNINITIALIZED` — Session not yet set up
- `INITIALIZED` — Session ready, mode loaded
- `TURN_ACTIVE` — Processing a user turn
- `WAITING_PERMISSION` — Blocked on user permission
- `WAITING_INPUT` — Blocked on user input (ask_user)
- `COMPACTING` — Context compaction in progress
- `ERROR` — Fatal error encountered
- `STOPPED` — Stop signal received

### Turn States (within TURN_ACTIVE)
- `TURN_START` — Turn begun
- `LLM_CALLING` — Awaiting LLM response
- `TOOL_EXECUTING` — Running tool actions
- `PERMISSION_CHECKING` — Evaluating permission policy
- `TURN_END` — Turn completed

## Transitions

| From | Event | To | Description |
|------|-------|-----|-------------|
| UNINITIALIZED | initialize_session | INITIALIZED | Mode loaded, harness context injected |
| INITIALIZED | submit_user_turn | TURN_ACTIVE | User input received |
| TURN_ACTIVE | call_llm | LLM_CALLING | Sending prompt to LLM |
| LLM_CALLING | llm_reply | TOOL_EXECUTING | Got response with tool calls |
| LLM_CALLING | llm_completed | TURN_END | Got response without tool calls |
| TOOL_EXECUTING | all_tools_done | TURN_END | All actions executed |
| TOOL_EXECUTING | permission_needed | WAITING_PERMISSION | Action requires approval |
| WAITING_PERMISSION | approved | TOOL_EXECUTING | User approved, resume |
| WAITING_PERMISSION | denied | TURN_END | User denied, turn ends |
| TURN_ACTIVE | checkpoint_suspend | WAITING_INPUT | ask_user triggered |
| WAITING_INPUT | user_responds | TURN_ACTIVE | User provided input |
| LLM_CALLING | context_length_error | COMPACTING | Prompt too long |
| COMPACTING | compacted | LLM_CALLING | Retry with compacted context |
| TURN_ACTIVE | stop_signal | STOPPED | User cancelled |
| TURN_ACTIVE | error | ERROR | Unrecoverable error |

## Error Handling

### Retryable Errors
- HTTP 429, 500, 502, 503, 504 — LLM retry with backoff
- Context length — Compaction and retry

### Non-Retryable Errors
- HTTP 400, 401, 403 — Fail immediately
- Tool validation errors — Return to LLM as observation
- Permission denied — Return as observation

## Loop Guard

The LoopGuard monitors for:
- Repeated identical tool calls (same name + arguments)
- Excessive turn count (> max_turns)
- Circular state transitions
