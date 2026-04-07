# GUI Session History Cutover Handoff

## Purpose

This is the single handoff entrypoint for continuing the `gui_session_switch_raw_fallback` work on another machine.

If you are resuming this work in a new Codex session, reference only this file first. It points to the full problem analysis, audit, locked architecture decisions, and the approved implementation plan.

## Current Status

The work has completed the analysis and planning phase.

What is already done:

- The original GUI/session-resume failure was analyzed and reproduced.
- The replay-log-based timeline design was confirmed to be the real root cause.
- The first architecture proposal was audited.
- The architecture proposal was revised and approved.
- A task-by-task inline execution plan was written.

What has **not** started yet:

- No production code for the cutover has been implemented yet.
- No tests have been updated yet.
- No replay-log history path has been removed yet.

## Locked Decisions

These decisions are already made and should be treated as fixed unless the user explicitly reopens them:

1. `transcript.jsonl` is the only durable session-history truth.
2. `Session` / `session.turns` is the only live structured session state.
3. `timeline.jsonl` is transport/replay infrastructure only and must not be used to rebuild history.
4. Do not design for legacy compatibility.
5. Do not preserve dual history sources.
6. Do not keep `raw fallback` as a supported GUI recovery mode.
7. GUI session activation must move to a single bootstrap contract.
8. The implementation should continue via inline execution, not a redesign pass.

## Read In This Order

1. [docs/issues/gui_session_switch_raw_fallback.md](/D:/Project/coding_agent/docs/issues/gui_session_switch_raw_fallback.md)
   Original problem analysis and root-cause writeup.

2. [docs/issues/gui_session_switch_raw_fallback_plan_review.md](/D:/Project/coding_agent/docs/issues/gui_session_switch_raw_fallback_plan_review.md)
   Audit report for the first architecture plan. Read this to understand which gaps were accepted and how they were folded back into the final design.

3. [docs/superpowers/plans/2026-04-07-session-history-single-source-cutover.md](/D:/Project/coding_agent/docs/superpowers/plans/2026-04-07-session-history-single-source-cutover.md)
   Approved architecture plan. This is the source of truth for the target design.

4. [docs/superpowers/plans/2026-04-07-session-history-single-source-cutover-implementation.md](/D:/Project/coding_agent/docs/superpowers/plans/2026-04-07-session-history-single-source-cutover-implementation.md)
   Approved execution plan. This is the source of truth for the implementation sequence.

## What The Next Session Should Do

Resume from the implementation plan, using **inline execution**.

Start at:

- `Task 1: Persist Stable Tool Presentation History`

Then continue in order:

- Task 2: Add Session History Assembler and Integrity Contract
- Task 3: Add Bootstrap API and Replace Split Activation
- Task 4: Make Bootstrap-to-Live Updates Idempotent and Remove Raw Fallback UI
- Task 5: Delete Replay-Log History Paths and Update Docs

Do not skip ahead to frontend cleanup before Task 1 and Task 2 are complete, because the frontend cutover depends on the new history contract.

## Important Implementation Notes

### 1. Partial Restore Is Real, Not A New Feature To Invent

The current code already supports partial transcript restore semantics in practice:

- `TranscriptStore` preserves a valid prefix when the tail is damaged.
- `SessionRestorer` returns a partial materialized session plus `stop_reason`.

The approved design does **not** add a second fallback.
It formalizes this into official history integrity states:

- `healthy`
- `partial`
- `unavailable`

### 2. Idempotent Live Merge Belongs Mainly In The Reducer

If delayed websocket/replay events arrive after bootstrap, the main upsert responsibility is in:

- [src/embedagent/frontend/gui/webapp/src/store.js](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/store.js)

The runtime projector remains useful, but it is not the main fix location for duplicate step/tool cards.

### 3. Stable Historical Tool Metadata Is Required

Do not rely only on current tool catalog state when serializing old history.

The approved plan requires introducing a narrow stable snapshot for history:

- `ToolPresentationSnapshot`

This is for immutable presentation semantics such as:

- `tool_label`
- `permission_category`
- `supports_diff_preview`
- `progress_renderer_key`
- `result_renderer_key`

Volatile runtime/debug metadata should remain separate.

### 4. No Replay-Log Parser Preservation

Do not “temporarily keep” the old `build_structured_timeline()` replay parsing path.

The approved plan is a cutover plan, not a compatibility plan.

## Verification Focus

When implementation starts, keep these regressions in scope the whole time:

- `limit=200` should never determine historical turn correctness again.
- trimming `timeline.jsonl` should not affect GUI history.
- active sessions and resumed sessions should produce the same structured history.
- partial transcript restore should return structured partial history, not raw fallback.
- delayed `step_end` / `tool_finished` after bootstrap should upsert, not duplicate.

## Files That Exist But Are Not Part Of This Handoff Commit

In the current local workspace there are unrelated modified frontend asset files:

- `src/embedagent/frontend/gui/static/assets/app.css`
- `src/embedagent/frontend/gui/static/assets/app.js`

They are intentionally excluded from the handoff documentation commit.
Do not treat them as part of the session-history cutover unless the user explicitly asks you to.

## Suggested Resume Prompt

If you want to minimize context switching on the other machine, use a prompt like:

> Continue the inline execution of the approved session-history cutover plan described in [docs/issues/gui_session_switch_raw_fallback_handoff.md](/D:/Project/coding_agent/docs/issues/gui_session_switch_raw_fallback_handoff.md). Do not redesign the architecture. Read the referenced documents in order, then start from Task 1 of the implementation plan.

## Completion Condition For The Next Session

This handoff is fully consumed once the next session has:

- read the four referenced documents in order
- confirmed the locked decisions
- started inline execution from Task 1 of the implementation plan

