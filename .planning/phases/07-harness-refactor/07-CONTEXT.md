# Phase 7: Harness Refactor - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Refactor mode and execution model to be permission-contract-based, intent-driven, and free of arbitrary step limits. Ensure entering build/debug mode and saying "hi" produces normal chat, no workflow trigger. Task graph generated only on explicit work requests. Agent outputs completion signal; no fixed max_turns enforced. Guard detects runaway loops.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints:
- Python 3.8.x strictly
- Never use Python 3.9+ syntax features
- Mode is permission contract only (not unconditional workflow injection)
- Agent must signal completion naturally, not via fixed step limits

</decisions>

<code_context>
## Existing Code Insights

Current harness implementation in src/embedagent/:
- modes.py: Mode definitions with allowed tools, system prompts
- query_engine.py: Has max_turns parameter (default 8), runs loop for N turns
- harness/task_graph.py: TaskGraph for tracking execution tasks
- permissions.py: PermissionPolicy for tool approval

Current issues:
- build/debug mode unconditionally injects harness context
- max_turns enforces hard limit regardless of completion
- Task graph created automatically, not on explicit request
- No completion signal from agent

</code_context>

<specifics>
## Specific Ideas

1. Mode should be permission contract only — tools available, not workflow tracks
2. Task graph created only when user explicitly requests work ("build this", "fix that")
3. Agent assesses completion via reply.finish_reason or explicit completion tool
4. Guard monitors for repeated tool calls or consecutive failures
5. User can override guard decisions

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
