# Architecture

**Analysis Date:** 2026-05-02

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      Frontend Layer (Shells Only)                        │
├────────────────────────────┬────────────────────────────────────────────┤
│   TUI (`frontend/tui/`)    │   GUI (`frontend/gui/`)                    │
│   prompt_toolkit + rich    │   PyWebView + FastAPI + WebSocket          │
└────────┬───────────────────┴────────────────────┬───────────────────────┘
         │                                          │
         ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Protocol / Core Layer (Stable Contract Boundary)            │
│         `src/embedagent/protocol/`  |  `src/embedagent/core/`            │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Agent Core Layer (Product Core)                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Host / Bridge          │  `InProcessAdapter` (`inprocess_adapter.py`)   │
│  Session Runtime Owner    │  `QueryEngine` (`query_engine.py`)             │
│  Session State            │  `Session` (`session.py`)                      │
│  Managed Session Host     │  `ManagedSession` (`session_runtime.py`)       │
│  Snapshot Projection      │  `SessionSnapshotProjector` (`session_projector.py`)│
│  History Assembly         │  `SessionHistoryAssembler` (`session_history.py`)│
│  Workflow Harness         │  `HarnessRunner` (`harness/runner.py`)         │
│  Task Graph               │  `TaskGraph` (`harness/task_graph.py`)         │
│  Phase Engine             │  `advance_phase` (`harness/phase_engine.py`)   │
│  Mode Registry            │  `MODE_REGISTRY` (`modes.py`)                  │
│  Permission Engine        │  `PermissionPolicy` (`permissions.py`)         │
│  Context Management       │  `ContextManager` (`context.py`)               │
│  Tool Runtime Facade      │  `ToolRuntime` (`tools/runtime.py`)            │
│  LLM Client               │  `OpenAICompatibleClient` (`llm.py`)           │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Storage / Persistence Layer                          │
│  `SessionSummaryStore`  |  `TranscriptStore`  |  `ToolResultStore`       │
│  `ProjectionDb`         |  `SessionTimelineStore` | `PlanStore`          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI Entry | Argument parsing, mode selection, TUI/GUI dispatch | `src/embedagent/cli.py` |
| TUI Frontend | Terminal UI shell with prompt_toolkit/rich | `src/embedagent/frontend/tui/` |
| GUI Frontend | PyWebView desktop app with FastAPI backend | `src/embedagent/frontend/gui/` |
| Protocol | Dataclass contracts between frontend and core | `src/embedagent/protocol/__init__.py` |
| Core Adapter | Wraps InProcessAdapter as protocol interface | `src/embedagent/core/adapter.py` |
| InProcessAdapter | Host/bridge layer; session lifecycle, slash commands, snapshots | `src/embedagent/inprocess_adapter.py` |
| QueryEngine | Session-scoped engine owning turn/step execution, transcript mutation | `src/embedagent/query_engine.py` |
| Session | Pure dataclass for turns, messages, actions, observations | `src/embedagent/session.py` |
| ManagedSession | Thread/lock/status host for live session reference | `src/embedagent/session_runtime.py` |
| SessionSnapshotProjector | Pure projection from session truth to snapshot dict | `src/embedagent/session_projector.py` |
| SessionHistoryAssembler | Builds structured history from transcript-backed Session | `src/embedagent/session_history.py` |
| HarnessRunner | Mode registry lookup, task graph construction, prompt building | `src/embedagent/harness/runner.py` |
| TaskGraph | Workflow truth: phase track with pending/in_progress/completed tasks | `src/embedagent/harness/task_graph.py` |
| PhaseEngine | Phase advancement rules based on artifact flags | `src/embedagent/harness/phase_engine.py` |
| PermissionPolicy | Structured rule matching, explanation rendering, decision engine | `src/embedagent/permissions.py` |
| ContextManager | Context budget, reducer registry, compaction pipeline | `src/embedagent/context.py` |
| ToolRuntime | Official tool facade: catalog, execution, result storage | `src/embedagent/tools/runtime.py` |
| LLM Client | OpenAI-compatible chat completions with streaming | `src/embedagent/llm.py` |

## Pattern Overview

**Overall:** Layered architecture with a single execution spine. Frontend shells are replaceable; the Agent Core owns all workflow semantics.

**Key Characteristics:**
- One session-scoped `QueryEngine` owns all turn/step/interaction execution and transcript mutation
- `InProcessAdapter` is a host/bridge layer and must not mint duplicate workflow identities
- Frontend shells do not own workflow semantics; they consume projections
- Session truth is distributed across live `Session`, transcript events, and projections
- Tool execution flows through one official facade (`ToolRuntime`)
- Mode switching is exclusively user-driven (`/mode` command or `ask_user` options)

## Layers

**Frontend Layer:**
- Purpose: User interaction shells only
- Location: `src/embedagent/frontend/tui/`, `src/embedagent/frontend/gui/`
- Contains: TUI controller/views/services, GUI launcher/backend/server/webapp
- Depends on: Protocol/Core layer
- Used by: End users

**Protocol / Core Layer:**
- Purpose: Stable contract boundary between UI and Agent Core
- Location: `src/embedagent/protocol/`, `src/embedagent/core/`
- Contains: Dataclass contracts (Message, ToolCall, ToolResult, SessionSnapshot, etc.), CoreInterface ABC, AgentCoreAdapter
- Depends on: Nothing (bottom of frontend stack)
- Used by: TUI, GUI, tests

**Agent Core Layer:**
- Purpose: Product core — execution engine, session management, workflow harness
- Location: `src/embedagent/inprocess_adapter.py`, `src/embedagent/query_engine.py`, `src/embedagent/harness/`, `src/embedagent/tools/`, `src/embedagent/context.py`, `src/embedagent/permissions.py`
- Contains: Session lifecycle, turn/step loop, tool execution, context compaction, permission evaluation, mode harness
- Depends on: Protocol types, LLM client, stores
- Used by: Frontend layer via Core Adapter

**Storage / Persistence Layer:**
- Purpose: Durable state for sessions, transcripts, tool results, plans
- Location: `src/embedagent/session_store.py`, `src/embedagent/transcript_store.py`, `src/embedagent/tool_result_store.py`, `src/embedagent/projection_db.py`, `src/embedagent/plan_store.py`
- Contains: SQLite and JSONL-based persistence
- Depends on: Workspace path
- Used by: Agent Core layer

## Data Flow

### Primary Request Path (User Message)

1. **Frontend receives input** → submits to Core Adapter (`core/adapter.py:178`)
2. **Core Adapter delegates** to InProcessAdapter (`inprocess_adapter.py:162`)
3. **InProcessAdapter locates ManagedSession** and forwards to QueryEngine (`inprocess_adapter.py:390`)
4. **QueryEngine runs turn loop** (`query_engine.py:422`):
   - Assembles context via ContextManager
   - Calls LLM client (`llm.py:36`)
   - Parses assistant reply for tool calls
   - Evaluates permissions via PermissionPolicy
   - Executes tools via ToolRuntime
   - Appends results to Session and TranscriptStore
5. **QueryEngine emits events** back through InProcessAdapter to frontend callbacks
6. **InProcessAdapter projects snapshot** via SessionSnapshotProjector (`session_projector.py:32`)
7. **Frontend receives snapshot + events** and re-renders

### Session Resume Path

1. **CLI/Frontend requests resume** with session_id or "latest"
2. **InProcessAdapter loads summary** from SessionSummaryStore
3. **SessionRestorer replays transcript** from TranscriptStore into new Session
4. **QueryEngine re-attached** to restored ManagedSession
5. **Pending interactions re-enter** the same action pipeline used by first execution

### Tool Execution Path

1. **QueryEngine partitions tool actions** (`tool_execution.py:partition_tool_actions`)
2. **Permissions evaluated** per action by PermissionPolicy
3. **Tools executed** via ToolRuntime.dispatch (up to `max_parallel_tools=3`)
4. **Observations stored** in ToolResultStore and ProjectionDb
5. **Transcript events appended** for each tool start/finish
6. **ToolCommitCoordinator** ensures result store + projection db + transcript consistency

**State Management:**
- Live state: `Session` dataclass inside `ManagedSession`
- Durable history: `transcript.jsonl` via `TranscriptStore`
- Snapshots: projected on-demand by `SessionSnapshotProjector` (not cached truth)
- Task truth: `TaskGraph` attached to `Session`, updated by `HarnessRunner`

## Key Abstractions

**Session:**
- Purpose: The single source of live structured conversation state
- Examples: `src/embedagent/session.py`
- Pattern: Plain dataclass with `Turn`, `AgentStepState`, `TranscriptMessage`, `CompactBoundary`

**ManagedSession:**
- Purpose: Thread-safe host for a Session plus pending interactions
- Examples: `src/embedagent/session_runtime.py`
- Pattern: Dataclass with `threading.RLock`, `threading.Event`, pending permission/input tickets

**TaskGraph:**
- Purpose: Official workflow truth — phase track with status
- Examples: `src/embedagent/harness/task_graph.py`
- Pattern: Dataclass with `TaskNode` list; rebuilt by `HarnessRunner` after each observation batch

**ToolCatalogEntry:**
- Purpose: Rich metadata for every exposed tool
- Examples: `src/embedagent/tools/runtime.py:21`
- Pattern: Dataclass with permission_category, mode_visibility, renderer keys, context reducer keys

**ContextPolicy / ContextBuildResult:**
- Purpose: Token budget enforcement and message compaction
- Examples: `src/embedagent/context.py:27`
- Pattern: Config-driven policy with reducer registry; produces API-ready message list

## Entry Points

**CLI:**
- Location: `src/embedagent/cli.py`
- Triggers: `python -m embedagent` or `embedagent` console script
- Responsibilities: Parse args, init modes, create adapter, run single-turn or TUI/GUI

**TUI:**
- Location: `src/embedagent/frontend/tui/launcher.py`
- Triggers: `embedagent --tui`
- Responsibilities: Launch prompt_toolkit application, connect to Core Adapter

**GUI:**
- Location: `src/embedagent/frontend/gui/launcher.py`
- Triggers: `embedagent-gui` or `embedagent --gui`
- Responsibilities: Launch FastAPI + PyWebView, serve static webapp, bridge WebSocket events

**Core Adapter (Protocol Interface):**
- Location: `src/embedagent/core/adapter.py`
- Triggers: Used by both TUI and GUI backends
- Responsibilities: Wrap InProcessAdapter into stable `CoreInterface` contract

## Architectural Constraints

- **Threading:** `QueryEngine` uses `threading.RLock` for session guard. Tool execution supports up to 3 parallel tools. GUI backend uses `ThreadsafeAsyncDispatcher` for cross-thread event delivery.
- **Global state:** `MODE_REGISTRY` in `src/embedagent/modes.py` is module-level mutable state rebuilt by `initialize_modes()`. `QueryEngine` instances are session-scoped, not global.
- **Circular imports:** `core/adapter.py` uses lazy import (`_get_adapter_class`) to avoid circular dependency with `inprocess_adapter.py`.
- **Python version:** Runtime compatible with `>=3.8,<3.9`. No walrus operator, match statements, or union syntax.
- **Offline bundle:** Must not require Docker, WSL, VS Code, Node.js-at-runtime, or online services. All runtime tools discovered from bundled assets.
- **No parallel V1/V2 paths:** Old `code` mode and `manage_todos` workflow are no longer part of the architecture baseline.

## Anti-Patterns

### Frontend Owning Workflow Truth

**What happens:** A frontend maintains its own task list or mode state separate from session snapshots.
**Why it's wrong:** Violates the single-source-of-truth rule. `transcript.jsonl` is the only durable ledger; `Session` is the only live state.
**Do this instead:** Consume `SessionSnapshot` projections and `TaskGraph` state from the Core Adapter. GUI/TUI only render.

### Bypassing QueryEngine for Session Mutation

**What happens:** Code outside `QueryEngine` directly mutates `session.turns` or mints new `turn_id`/`step_id` values.
**Why it's wrong:** Breaks transcript consistency and event sequencing. Engine-issued IDs are the only official execution anchors.
**Do this instead:** All turn/step/interaction execution flows through `QueryEngine.submit_user_message()` or `QueryEngine.resume_interaction()`.

### Inferring Permission from Mode Name

**What happens:** Frontend or prompt text assumes "build mode can always write files."
**Why it's wrong:** `permissions.py` is the only official permission engine. Mode boundaries and permission decisions are separate concerns.
**Do this instead:** Always call `PermissionPolicy.evaluate(action)` and surface the resulting `PermissionDecision` to the user.

### Rebuilding History from Replay Logs

**What happens:** GUI reconstructs historical turns from `timeline.jsonl` replay tails instead of structured `Session` state.
**Why it's wrong:** `timeline.jsonl` is transport/replay infrastructure only, not a historical database.
**Do this instead:** Use `SessionHistoryAssembler` operating on transcript-backed `Session` state. GUI activation uses `/api/sessions/{id}/bootstrap` payload.

## Error Handling

**Strategy:** Exceptions bubble to the adapter layer where they are captured in `ManagedSession.last_error` and surfaced via event handlers.

**Patterns:**
- Tool errors become `Observation(success=False, error=...)` and are appended to the session transcript
- LLM errors (`ModelClientError`) abort the current turn and emit `session_error` event
- Permission denials emit `permission_required` event and suspend the turn pending user resolution
- Context length errors trigger compaction and retry with reduced window

## Cross-Cutting Concerns

**Logging:** Standard Python `logging` module. GUI backend configures structured format.
**Validation:** Permission rules validated against JSON schema at load time. Mode config validated against built-in defaults.
**Authentication:** API key passed to `OpenAICompatibleClient`; no built-in auth server.
**Session lifecycle:** `InProcessAdapter` owns session creation, resume, and teardown. `QueryEngine` owns per-session execution.

---

*Architecture analysis: 2026-05-02*
