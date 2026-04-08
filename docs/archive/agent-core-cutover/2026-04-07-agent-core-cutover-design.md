# Agent Core Ownership Cutover Design

## 1. Goal

This design defines a single-path refactor of the EmbedAgent agent core so that:

- `QueryEngine` becomes the only execution owner of a session
- `Session` becomes the only durable conversation truth
- `TaskGraph` becomes the only workflow-task truth
- `transcript.jsonl` remains the only durable history ledger
- adapters and frontends become projection/transport layers only

The purpose of this cutover is not to add features. It is to eliminate split ownership, duplicated state transitions, and protocol drift in the current agent design.

## 2. Assumptions

This design is intentionally strict.

- No legacy session compatibility is required.
- No legacy mode compatibility is required.
- No legacy `todo` compatibility is required.
- No long-lived dual-path migration is allowed.
- Unknown or invalid persisted state should fail fast instead of silently falling back.

## 3. Product Constraints

The cutover must continue to respect the project constitution:

- Windows 7 compatibility remains mandatory.
- Offline deployment remains mandatory.
- Python runtime remains `>=3.8,<3.9`.
- Runtime dependencies must stay minimal.
- The official product vocabulary remains:
  - modes: `explore`, `spec`, `build`, `debug`, `verify`
  - task truth: `TaskGraph`, `task_status`, session task snapshots
  - session-history truth: `transcript.jsonl -> Session -> SessionHistoryAssembler -> bootstrap`

This design does not change those contracts. It changes which subsystem owns them.

## 4. Current Design Problems

The current implementation has already promoted the new vocabulary, but the runtime architecture still has several structural problems.

### 4.1 Split execution ownership

`InProcessAdapter` and `QueryEngine` both own pieces of session execution:

- both inject harness/system messages
- both participate in transcript-related behavior
- both derive or emit step/turn metadata
- `QueryEngine` is recreated per turn rather than owned per session

This produces duplicated logic and inconsistent execution identity.

### 4.2 Parallel step identity

The engine records one `step_id` into transcript/session state, while the adapter emits a separate `step_id` into frontend events. This makes it impossible to guarantee that transcript, event stream, session history, and frontend timeline are projections of the same execution object.

### 4.3 Permission resume side path

Normal execution goes through `_execute_action()`, which applies:

- mode tool checks
- permission checks
- mode write checks
- path checks

But resumed permission execution bypasses that path and calls the tool runtime directly. This creates two different execution semantics for the same action.

### 4.4 `TaskGraph` is not yet runtime truth

The current `TaskGraph` mainly mirrors phase progression. It is a useful harness aid, but it does not yet behave like a durable runtime task system with explicit task identity, evidence linkage, or reliable projection semantics.

### 4.5 Multiple tool/mode truth sources

Mode and tool behavior is currently determined by a combination of:

- `modes.py`
- `harness/registry.py`
- `tooling/packs.py`
- `tools/harness_runtime.py`
- `tools/runtime.py`

This is workable only while the system is small. It becomes fragile once behavior evolves.

### 4.6 Persistence hot path is too expensive

Both transcript and timeline append paths rescan their files to determine the next sequence number. This produces unnecessary growth in write cost as sessions get longer.

### 4.7 Old `todo` vocabulary still leaks

The official architecture says `tasks`, but some reducers, UI renderer keys, and helper files still carry `todo` semantics. That keeps the conceptual cutover incomplete.

## 5. Design Principles

The cutover follows these rules:

1. One owner per state domain.
2. Durable truth and UI projection must be different concepts.
3. Execution resume must re-enter the same state machine, not a shortcut.
4. Session lifecycle and frontend transport must be loosely coupled.
5. New architecture must become the only architecture.

## 6. Target Architecture

The target runtime spine is:

`Frontend -> Core Adapter -> SessionRuntimeManager -> QueryEngine -> Session + Harness + ToolRuntime + Context + Permission + Transcript`

### 6.1 Responsibility map

- `Frontend`
  - displays projected state
  - sends user actions
  - owns no workflow truth

- `Core Adapter`
  - protocol translation only
  - frontend callback bridge only
  - no business-state derivation

- `SessionRuntimeManager`
  - owns live session registry
  - owns worker thread lifecycle
  - owns stop/cancel plumbing
  - owns no conversation semantics

- `QueryEngine`
  - owns turn loop
  - owns step loop
  - owns suspend/resume
  - owns action execution state machine
  - owns transcript append behavior
  - is the only mutator of `Session`

- `Session`
  - owns durable conversation state only
  - is the canonical in-memory model restored from transcript

- `SessionHistoryAssembler`
  - projects `Session` into frontend history format

- `SessionSnapshotProjector`
  - projects live runtime state into `SessionSnapshot`

## 7. Ownership Model

### 7.1 Session ownership

One live session has exactly one engine instance.

- `ManagedSession` will keep a stable `engine` reference.
- `QueryEngine` will no longer be created per turn.
- session-scoped state that logically belongs to execution will remain inside the engine.
- counters, caches, and rolling execution trackers that previously reset per turn must be re-audited under session-scoped lifetime.

Examples of state that must be reviewed during this cutover include:

- maintenance counters
- loop-level caches
- any state whose current behavior accidentally depends on per-turn engine construction

Recommended scope classification for the initial audit:

| State | Recommended scope | Reason |
|---|---|---|
| maintenance counters | session-scoped | must accumulate across turns to mean anything |
| context or file-read caches | session-scoped | avoids repeated reads and repeated prompt inflation |
| permission denial history | session-scoped | useful for repeated tool-use guidance within one session |
| loop guard state | turn-scoped | guards one turn against local recursion or tool loops |
| LLM retry counters | turn-scoped | retries are per request/turn, not cross-session state |
| aggregate usage or budget tracking | session-scoped | reflects whole-session spend and budget exhaustion |

### 7.2 What stays in `ManagedSession`

`ManagedSession` should become a runtime host object only.

It should retain:

- `session`
- `engine`
- `status`
- `last_error`
- `active_thread`
- `stop_event`
- `updated_at`
- runtime-only pending ticket handles if the adapter still needs them for frontend blocking flows

It should stop owning derived workflow fields such as:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

Those become projection output, not stored runtime truth.

### 7.3 What stays in `Session`

`Session` remains the durable restored conversation object and keeps:

- `messages`
- `turns`
- `compact_boundaries`
- `pending_interaction`
- `content_replacements`
- `latest_context_snapshot`
- `task_graph`

`Session` must not own:

- threads
- locks
- UI ticket objects
- event handlers
- transport replay status

## 8. QueryEngine Design

### 8.1 Engine lifetime

`QueryEngine` becomes session-scoped:

- created once during session creation or session resume
- reused for all subsequent user turns and interaction resumes
- disposed only when the runtime manager drops the session

### 8.2 Engine API

The public engine API should be reduced to three session-oriented entry points:

- `initialize_session(...)`
- `submit_user_turn(...)`
- `resume_interaction(...)`

Recommended responsibilities:

- `initialize_session(session, mode, workflow_state="chat")`
  - inject workspace profile message
  - inject mode system prompt
  - inject harness prompt units
  - establish any engine-owned session bootstrap state
- `submit_user_turn(session, user_text, ...)`
  - execute one user-authored turn
- `resume_interaction(session, resolution, ...)`
  - continue a suspended execution checkpoint

`submit_user_turn(...)` and `resume_interaction(...)` must enter the same internal action/step state machine. `initialize_session(...)` is not a turn runner; it is a session bootstrap entry point.

### 8.3 Turn and step identity

The engine is the only source of:

- `turn_id`
- `step_id`
- `interaction_id`

Adapters must stop generating these IDs independently.

Frontend events, transcript events, session history, and bootstrap history must all refer to the same IDs that were generated by the engine.

### 8.4 Engine callbacks

Engine callbacks are reporting hooks only.

Examples:

- `on_step_start(step_id: str, step_index: int)`
- `on_step_finish`
- `on_tool_start`
- `on_tool_finish`
- `on_text_delta`
- `on_reasoning_delta`

These callbacks must receive engine-generated IDs. They must never synthesize new workflow identifiers.

In particular, callbacks that currently receive only ordinal information must be upgraded to receive engine-generated workflow identity explicitly. For example, `on_step_start` must receive both `step_id` and `step_index`, so the adapter cannot synthesize a second step identifier for frontend events.

### 8.5 Session initialization

Session initialization becomes an engine-owned concern.

That includes initial injection of:

- workspace profile message
- mode system prompt
- harness prompt units

The adapter may request session creation, but it must not inject workflow-defining messages itself.

## 9. Unified Action State Machine

The design requires one execution path for all actions.

### 9.1 Internal stages

Every action should go through the same stages:

1. mode availability validation
2. interaction-tool handling
3. permission evaluation
4. mode/path write validation
5. runtime execution
6. transcript/session commit

### 9.2 Resume semantics

When a permission or user-input interaction is resumed:

- the resolution is first recorded into transcript/session state
- the pending action is reconstructed
- the action re-enters the same action pipeline

Resume must not directly invoke the tool runtime.

To avoid re-suspending on the same permission checkpoint, resume execution must wrap the ordinary permission callback with a synthetic resolver that returns the already-known decision for the pending interaction.

That synthetic resolver must:

- match the reconstructed pending action
- return the pre-resolved approval or rejection without prompting again
- allow the resumed action to traverse the full validation pipeline without creating a second pending interaction for the same checkpoint

### 9.3 Interaction payload contract

`PendingInteraction.request_payload` becomes a strict execution checkpoint. It must contain:

- serialized original action
- `turn_id`
- `step_id`
- `interaction_id`
- interaction kind
- interaction-specific request data

That makes transcript replay and live resume use the same information model.

Adapter-facing permission or user-input tickets must not create a second workflow identity namespace.

The external ticket identifier should either:

- equal `PendingInteraction.interaction_id`, or
- be a deterministic 1:1 alias of it

The rule is that transcript, session state, history projection, event stream, and frontend response routing all refer to the same underlying interaction object.

## 10. Permission Model Design

The permission model remains structured-data driven, but the runtime behavior becomes stricter.

### 10.1 Permission policy responsibilities

`PermissionPolicy` should continue to do:

- category derivation
- rule loading
- rule matching
- explanation rendering

It should not execute actions or change session state.

### 10.2 Permission runtime responsibilities

The engine should own:

- creating pending permission interactions
- suspending execution
- resuming from user approval/rejection
- converting approval decisions back into action execution

### 10.3 No resume bypass

Approval can no longer imply "execute now via direct tool call".

Approval only changes the pending interaction resolution. The engine must still run the pending action through:

- current mode checks
- current write policy checks
- runtime execution

This keeps approval-time behavior identical to first-pass behavior.

## 11. TaskGraph Design

### 11.1 New role of `TaskGraph`

`TaskGraph` becomes session task truth, not just harness scaffolding.

It must represent:

- current phase-derived tasks
- explicit verification tasks
- explicit blocking states
- task notes/evidence

### 11.2 Task node shape

Recommended fields:

- `task_id`
- `kind`
  - `phase`
  - `verification`
  - `manual`
- `title`
- `status`
  - `pending`
  - `in_progress`
  - `blocked`
  - `completed`
  - `failed`
- `source`
  - `harness`
  - `runtime`
  - `user`
- `note`
- `evidence_refs`
- `updated_at`

### 11.3 Projection model

`task_status` no longer constructs summary strings ad hoc from mode context.

Instead:

- `Session.task_graph` is truth
- `task_status` reads from `Session.task_graph`
- `SessionSnapshot.task_summary` and `task_items` are projections of the same graph

### 11.4 Harness relationship

Harness still defines:

- phase tracks
- discipline defaults
- phase advancement logic

But harness no longer acts as the task truth itself. It only updates `TaskGraph`.

To keep ownership explicit, harness responsibilities should be split into:

- `describe_mode(...)`
  - read-only
  - produces prompt units and mode-facing guidance
- `update_task_graph(...)`
  - mutates `Session.task_graph` in place
  - applies phase advancement and evidence-linked task status transitions

`describe_mode(...)` must not remain a hidden source of workflow truth after the cutover.

Recommended contract:

```python
def update_task_graph(
    session: Session,
    current_mode: str,
    observations: List[Observation],
) -> None:
    """Mutate session.task_graph in place based on the latest turn observations.

    Called by the engine at the end of each turn, immediately before
    session persistence and snapshot emission.
    """
```

The engine is the caller. The call frequency is once per completed turn. This keeps task mutation aligned with the same persistence boundary used for transcript and snapshot updates.

## 12. Mode and Tool Truth Design

### 12.1 Single direction of truth

The target dependency direction is:

- `modes.py`
  - mode contract
  - write policy
  - mode prompt
- `harness/registry.py`
  - phase tracks
  - discipline defaults
- `tooling/packs.py`
  - tool pack membership
- `tools/harness_runtime.py`
  - mapping from `(mode, workflow_state)` to effective pack
- `tools/runtime.py`
  - final runtime schema and execution surface

### 12.2 Rule

Display metadata may appear in many places.

Behavior truth may not.

The runtime must calculate executable tool membership from one place only.

### 12.3 Unknown mode behavior

Unknown modes must fail immediately.

The current silent fallback to `explore` should be removed. With no legacy compatibility requirement, silent fallback is a bug, not a safety net.

## 13. Persistence Design

### 13.1 Durable ledger vs projections

The design keeps these categories strict:

- durable ledger
  - `transcript.jsonl`
- replay transport
  - `timeline.jsonl`
- projections
  - `summary.json`
  - session projection DB rows
  - task snapshot JSON

### 13.2 Transcript contract

`transcript.jsonl` remains the only durable history ledger.

All restorable workflow state must be derivable from transcript plus current code.

### 13.3 Timeline contract

`timeline.jsonl` is transport only.

If it is missing, truncated, or degraded:

- the session remains resumable from transcript
- frontend replay may require reload
- history reconstruction must not depend on timeline

### 13.4 Sequence-number optimization

Both `TranscriptStore` and `SessionTimelineStore` should stop rescanning full files on every append.

Recommended design:

- open or restore session file
- scan once
- cache `last_seq` in process
- increment in memory on append

This preserves the JSONL format while fixing the write amplification problem.

This optimization is behavior-preserving and may land earlier than the broader persistence cutover if needed, as long as it does not reintroduce a second history truth path.

### 13.5 Strict restore

`SessionRestorer` should restore only the official transcript schema.

It should:

- validate ordering
- validate step/tool/interaction identity
- fail early on corruption or schema mismatch

It should not attempt legacy inference.

## 14. Snapshot and Bootstrap Design

### 14.1 Snapshot projector

Introduce a dedicated `SessionSnapshotProjector`.

Inputs:

- `ManagedSession`
- `Session`
- runtime environment
- replay state

Outputs:

- `SessionSnapshot`

The projector must be side-effect free.

It may derive and normalize fields, but it must not mutate:

- `ManagedSession`
- `Session`
- transcript state
- replay state

This projector is the only place allowed to derive:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `pending_interaction_valid`
- replay health metadata

### 14.2 History projector

`SessionHistoryAssembler` remains the only session-history serializer.

Its input is restored or live `Session`, not timeline.

### 14.3 Bootstrap payload

Bootstrap stays externally stable:

- `snapshot`
- `history`
- `plan`
- `permission_context`
- `replay`

But all components become projections from the single runtime truth instead of stitched fragments from adapter-owned state.

## 15. File-Level Structural Changes

### 15.1 Keep and refactor

- `src/embedagent/query_engine.py`
- `src/embedagent/session.py`
- `src/embedagent/session_history.py`
- `src/embedagent/session_restore.py`
- `src/embedagent/permissions.py`
- `src/embedagent/tools/runtime.py`
- `src/embedagent/harness/*`

### 15.2 Shrink heavily

- `src/embedagent/inprocess_adapter.py`

After cutover this file should contain:

- session registry
- worker-thread lifecycle
- slash command dispatch
- callback bridging
- calls into projectors

It should not duplicate engine state mutation or execution semantics.

### 15.3 Add

- `src/embedagent/session_runtime.py`
  - live runtime host structures
- `src/embedagent/session_projector.py`
  - snapshot/bootstrap projection
- `src/embedagent/interaction_runtime.py`
  - minimal interaction response routing glue only
  - must not create identifiers
  - must not cache interaction state
  - must not perform broader protocol translation beyond unpacking frontend responses and forwarding them to session runtime

If this logic remains trivial after the cutover, it should be merged into `session_runtime.py` instead of remaining as a standalone module.

### 15.4 Delete

- `src/embedagent/todos.py`

Any remaining `todos` compatibility hooks should be deleted at the same time.

## 16. Cutover Phases

### Phase 1: Engine ownership cutover

Goals:

- one engine per session
- one source of `turn_id` and `step_id`
- no duplicate harness injection
- stable session-oriented engine entry points

Done when:

- adapter no longer creates independent step IDs
- engine is stored on the live session runtime object
- transcript and frontend events agree on step identity
- engine lifetime is session-scoped rather than turn-scoped
- public execution entry points are session-oriented rather than turn-reconstructing

### Phase 2: Interaction and permission cutover

Goals:

- one action execution state machine
- no resume bypass
- no repeated ask on resumed permission checkpoints

Done when:

- permission approval resumes the same pipeline
- user-input resume resumes the same pipeline
- direct tool-runtime execution on resume is removed
- resumed permission execution uses a synthetic pre-resolved permission callback rather than opening a second identical permission interaction

### Phase 3: Task truth cutover

Goals:

- `TaskGraph` is session truth
- `task_status` and snapshot task fields are projections
- old `todo` semantics are removed

Done when:

- `todos.py` is deleted
- no reducer or helper reads `todos`
- harness updates task graph instead of returning task strings only

### Phase 4: Persistence cutover

Goals:

- transcript remains sole durable ledger
- timeline is transport only
- append hot path is fixed

Done when:

- transcript/timeline append do not rescan whole files each write
- history reconstruction uses session restoration only
- timeline degradation does not affect resume
- `SessionRestorer` and `SessionHistoryAssembler` are verified to read from `transcript.jsonl` only, with no fallback dependency on `timeline.jsonl`

## 17. Acceptance Criteria

The cutover is complete only if all of the following are true:

1. One live session owns one stable `QueryEngine`.
2. Transcript, session history, event stream, and frontend timeline use the same `turn_id` and `step_id`.
3. Permission resume and normal execution use the same action pipeline.
4. `TaskGraph` is the only workflow-task truth.
5. No `todo` vocabulary remains in runtime behavior.
6. Unknown mode values fail immediately.
7. `transcript.jsonl` is the only durable history ledger.
8. Timeline degradation never prevents session resume.
9. Frontend bootstrap contract remains stable.

## 18. Non-Goals

This cutover does not attempt to introduce:

- multi-agent orchestration
- remote/cloud execution
- browser automation
- plugin marketplace behavior
- a new frontend protocol

It is a core-architecture consolidation only.

## 19. Recommendation

Proceed with the cutover exactly in the phase order above.

Do not start by redesigning the frontend.
Do not start by expanding features.
Do not keep compatibility shims for old runtime paths.

The first and most important milestone is simple:

`QueryEngine` must become the only execution owner of a session.
