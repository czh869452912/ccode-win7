# Phase C AgentKernel Lifecycle Extraction Design

## Purpose

Phase C turns the current session facade and thin loop wrapper into a real lifecycle boundary. The goal is to keep learning Pi's architecture philosophy: a small core, explicit turn frames, durable lifecycle reducers, save points, and replaceable workflow packages.

This phase must preserve current hosted C/C++ behavior, Python 3.8 compatibility, offline operation, and the public frontend/session contracts.

## Current State

`QueryEngine` is already session-scoped, but it still owns too much lifecycle logic:

- schema v2 operation event emission
- turn start, finish, and interruption
- agent step start, finish, and interruption
- context assembly and context snapshot operation wrappers
- provider request operation wrappers
- workflow patch operation persistence
- pending interaction start and finish
- save point creation through `loop_transition`
- compact retry transitions and compact boundary recording
- abort, guard stop, max turns, and failure cleanup

`AgentLoop` currently delegates to `QueryEngine._run_loop_impl` and is not yet a meaningful lifecycle owner.

## Target Shape

Phase C introduces an internal AgentKernel layer in stages:

- `AgentLifecycleJournal` owns durable lifecycle writes and transition save points.
- `AgentKernel` owns turn frames and delegates action execution to `AgentToolActionService`.
- `AgentLoop` becomes a loop owner instead of a thin callable wrapper.
- `QueryEngine` remains the public session facade and transcript/session mutation compatibility surface until later phases remove the remaining direct calls.

The target dependency direction is:

`QueryEngine -> AgentKernel -> AgentLoop / AgentLifecycleJournal / AgentToolActionService / AgentExtensionHost`

`QueryEngine` may still own stores and compatibility wrappers during this phase, but new lifecycle semantics must be added to kernel/journal boundaries rather than directly to the facade.

## Subphases

### C-A: Lifecycle Journal

Create `src/embedagent/agent_lifecycle.py`.

Responsibilities:

- append transcript events through an injected append callback
- emit schema v2 operation lifecycle events
- record turn start, turn finish, and turn interruption
- record pending interaction start and finish
- record agent step finish and interruption
- record transition save points
- keep restore-time and live operation diagnostics semantics unchanged

`QueryEngine._record_transition()` becomes a compatibility delegate to the journal.

Acceptance:

- Existing transcript event ordering for pending interactions, loop transitions, save points, and operation lifecycle remains unchanged.
- Existing tests in `tests/test_query_engine_refactor.py`, `tests/test_session_operation_log.py`, and `tests/test_inprocess_adapter_frontend_api.py` pass.

### C-B: AgentKernel Turn Frame

Create `AgentTurnFrame` and `AgentKernel`.

Responsibilities:

- begin user, command, and resume turn frames
- finish or interrupt turn frames through the journal
- expose a simple internal API for `QueryEngine.submit_user_turn`, `submit_command_turn`, and `resume_interaction`

`QueryEngine` still prepares sessions, initializes workflow state, and owns transcript/session compatibility. The frame ensures turn operation lifecycle always follows one path.

Acceptance:

- User turn, command turn, and resume turn operation lifecycles are emitted through kernel frame helpers.
- `QueryEngine` no longer directly calls turn started, turn finished, or turn interrupted helpers.
- Frontend event payloads still receive the same turn IDs and step IDs.

### C-C: Suspend And Resume Boundary

Move pending interaction lifecycle consistency behind the kernel/journal boundary.

Responsibilities:

- create pending interaction save points atomically with session state
- resolve pending interactions through one path for permissions and user input
- keep command permission wait snapshots and session history atomic

Acceptance:

- Permission and user-input waits produce consistent snapshot/history projections before and after engine return.
- `approve_permission`, `reject_permission`, `reply_user_input`, and `respond_to_interaction` keep existing public behavior.
- No direct pending lifecycle emission is added back to `QueryEngine`.

### C-D: Loop Ownership

Move `_run_loop_impl` responsibilities out of `QueryEngine` into a real loop/kernel implementation.

Responsibilities:

- begin and finish agent steps
- own compact retry loop transitions
- own provider request lifecycle wrapping
- own tool batch interruption and guard-stop terminal transitions
- keep actual non-LLM tool execution in `AgentToolActionService`

Acceptance:

- `AgentLoop` no longer wraps a `runner` callback.
- `QueryEngine._run_loop_impl` is removed or becomes a compatibility shim with no lifecycle decisions.
- Loop behavior and transcript projections remain unchanged.

### C-E: Documentation And Archive Closure

Synchronize durable architecture docs:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/pi-inspired-agent-core-blueprint.md`

Archive completed Phase C working materials under `docs/archive/` if the project convention requires it at closeout.

## Non-Goals

Phase C does not:

- change public extension APIs
- create a plugin marketplace
- add remote registries or online installs
- replace the default C/C++ harness
- move C/C++ workflow package ownership; that is Phase D
- change frontend vocabulary or protocol shape unless needed to preserve existing behavior

## Testing Strategy

Each subphase must run focused tests before commit:

- `uv run pytest tests/test_query_engine_refactor.py -q`
- `uv run pytest tests/test_session_operation_log.py -q`
- `uv run pytest tests/test_inprocess_adapter_frontend_api.py -q`

Before Phase C closeout:

- `uv run ruff check src/ tests/`
- `uv run black --check src/ tests/`
- `uv run pytest tests/ -m "not slow and not gui" -q`

## Risk Controls

- Keep each subphase behavior-preserving.
- Prefer delegates and compatibility shims before deleting old helper names.
- Add characterization tests before moving lifecycle logic.
- Keep Python 3.8 syntax only.
- Keep `QueryEngine` as the public facade until final verification proves kernel boundaries are stable.
