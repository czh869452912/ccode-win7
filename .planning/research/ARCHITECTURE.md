# Architecture Research: EmbedAgent Compile Environment Integration & Core Refactoring

**Domain:** Agentic coding framework with C/C++ compile environment integration
**Researched:** 2026-05-02
**Overall confidence:** HIGH

---

## 1. Executive Summary

EmbedAgent has a solid infrastructure layer (session model, persistence, protocol, permission, mode) but its execution layer is concentrated in two oversized classes: `InProcessAdapter` (2,446 lines) and `QueryEngine` (1,530 lines). Compile environment integration is currently embedded in `ToolContext` within `tools/_base.py`, which mixes path resolution, process execution, diagnostic parsing, and toolchain discovery in a single 743-line module.

The architecture needs three structural changes:
1. **Extract compile environment concerns** into a dedicated `CompileEnvironment` component owned by the harness layer, not the tool layer
2. **Refactor the monoliths** using Facade + Strategy + Pipeline patterns
3. **Replace the implicit turn loop** with an explicit event-driven state machine

The blueprints in `docs/blueprints/` already describe the target architecture (agent-loop-blueprint, tool-environment-blueprint). This research validates those designs against the existing codebase and identifies the safest refactoring sequence.

---

## 2. Compile Environment Integration Patterns

### 2.1 Where Compile Environment Detection Lives

**Current state:** `ToolContext` in `tools/_base.py` owns:
- `_llvm_root_candidates()` — bundle/workspace/env LLVM discovery
- `resolve_managed_tool_path()` — tool key → absolute path resolution
- `runtime_environment_snapshot()` — full runtime state for frontend
- `build_process_env()` — PATH injection for subprocesses
- `parse_diagnostics()` — Clang/GCC/MSVC regex parsing
- `parse_test_summary()` / `parse_coverage_summary()` — test/coverage regex extraction

**Problem:** Compile environment is currently a **tool implementation detail**. This creates three issues:
1. The harness cannot reason about toolchain state during mode selection
2. Diagnostic parsing is only available to shell tools, not the agent loop
3. Build recipe execution and build result interpretation are coupled in the same tool handler

**Recommended architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                      HARNESS LAYER                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         CompileEnvironment (NEW COMPONENT)          │   │
│  │  - toolchain discovery (bundle → workspace → env)   │   │
│  │  - compiler capability matrix (clang version,       │   │
│  │    target triples, supported warnings)              │   │
│  │  - recipe template resolution (CMake/make/compile   │   │
│  │    commands.json detection)                         │   │
│  │  - build state tracking (clean/dirty/incremental)   │   │
│  └─────────────────────────────────────────────────────┘   │
│                        ▲                                     │
│  ┌─────────────────────┼─────────────────────────────┐     │
│  │    HarnessRunner    │    describe_mode()          │     │
│  │  - injects toolchain│    context into prompts     │     │
│  │    capabilities     │                             │     │
│  └─────────────────────┼─────────────────────────────┘     │
└────────────────────────┼────────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────────┐
│                   TOOL LAYER                                 │
│  ┌─────────────────────┼─────────────────────────────┐     │
│  │   ToolRuntime       │    delegates to             │     │
│  │  - receives PATH    │    CompileEnvironment       │     │
│  │    from harness     │    for env setup            │     │
│  └─────────────────────┼─────────────────────────────┘     │
│                        │                                     │
│  ┌─────────────────────▼─────────────────────────────┐     │
│  │         DiagnosticParser (EXTRACTED)              │     │
│  │  - Clang/GCC/MSVC regex parsers                   │     │
│  │  - Structured diagnostic → Observation enrichment │     │
│  │  - Severity normalization                         │     │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Rationale:** The harness owns workflow semantics. Build/debug modes need to know compiler capabilities to construct accurate prompts (e.g., "you are using Clang 17 targeting x86_64-windows-msvc with `-Werror` enabled"). The tool layer should consume environment state, not discover it.

### 2.2 Build Execution Integration with the Agent Loop

**Current state:** `run_recipe` is a tool like any other. The agent loop calls LLM → LLM emits `run_recipe` action → tool executes → observation returned → loop continues. There is no special handling for build execution.

**Recommended pattern: Structured Build Turn**

Build execution should integrate as a **first-class loop phase**, not just a tool call. This enables:
- Pre-build checkpoint (Shadow Git snapshot)
- Streaming output during compilation
- Post-build diagnostic enrichment
- Automatic quality gate evaluation

```
Agent Loop Build Turn:

1. LLM emits build intent (run_recipe with recipe_id)
2. AgentLoop enters BUILD_EXECUTING sub-state
3. CompileEnvironment validates recipe exists and is executable
4. Shadow Git checkpoint_before() captured
5. ShellRuntime executes with streaming progress
6. DiagnosticParser consumes stdout/stderr in real-time
7. Build completes → Observation enriched with:
   - structured diagnostics (file/line/column/level/message)
   - build summary (errors, warnings, duration)
   - next suggested action (fix error X, run tests, etc.)
8. If build failed and auto-approve is on:
   - AgentLoop transitions directly to THINKING with diagnostic context
   - No user interaction required for pure-error-fix cycles
```

**Key insight from sota-alignment-master-plan:** Claude Code and Roo-Code treat build execution as a **privileged operation** with its own error recovery strategy. EmbedAgent should adopt this pattern rather than treating `run_recipe` as a generic shell command.

### 2.3 Error Diagnostic Flow

**Current state:** Diagnostics are parsed in `ToolContext.parse_diagnostics()` and attached to the Observation data dict. The agent loop treats them as opaque structured data.

**Recommended flow:**

```
Compiler stdout/stderr
        │
        ▼
┌───────────────┐
│ StreamReader  │ (threading, Windows 7 compatible)
│ - reads pipes │
│ - emits chunks│
└───────┬───────┘
        │
        ▼
┌───────────────┐
│DiagnosticParser│
│ - regex match  │
│ - normalize    │
│ - deduplicate  │
│ - limit (200)  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ BuildObserver │
│ - enriches    │
│   Observation │
│ - computes    │
│   quality gate│
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Agent Loop   │
│ - if errors:  │
│   inject      │
│   diagnostic  │
│   summary into│
│   context     │
└───────────────┘
```

**Implementation note:** The existing `CLANG_DIAGNOSTIC_RE` and `MSVC_DIAGNOSTIC_RE` regexes are correct and should be preserved. The change is architectural — moving parsing from tool execution time to a dedicated pipeline stage.

---

## 3. Refactoring Patterns for Large Classes

### 3.1 InProcessAdapter (2,446 lines) — Facade + Coordinator Pattern

**Current responsibilities:**
- Session lifecycle (create, resume, list, snapshot)
- Event emission and status notification
- Slash command dispatch (14 command handlers)
- Workspace file operations (read, write, tree listing)
- Permission and user input ticket management
- Tool execution from commands
- Timeline and history assembly
- Plan management
- Recipe listing and execution

**Refactoring strategy:**

```
┌─────────────────────────────────────────────────────────────┐
│              InProcessAdapter (Facade, ~400 lines)          │
│  - owns ManagedSession registry                             │
│  - routes public API calls to delegates                     │
│  - emits events                                             │
│  - no business logic                                        │
└─────────────────────────────────────────────────────────────┘
        │
        ├──► SessionLifecycleService (extracted, ~300 lines)
        │    - create_session, resume_session, list_sessions
        │    - session restoration from transcript
        │
        ├──► CommandDispatchService (extracted, ~400 lines)
        │    - slash command parsing and routing
        │    - command handler registry
        │
        ├──► WorkspaceService (extracted, ~250 lines)
        │    - file read/write/tree/list operations
        │    - path resolution and validation
        │
        ├──► InteractionService (extracted, ~200 lines)
        │    - permission ticket management
        │    - user input ticket management
        │    - pending interaction resolution
        │
        └──► ProjectionService (extracted, ~150 lines)
             - snapshot assembly
             - history assembly
             - bootstrap payload construction
```

**Why Facade:** The adapter is the public API boundary. Frontends (CLI/TUI/GUI) depend on it. Keeping it as a thin facade preserves API stability while allowing internal reorganization.

**Why not just split into modules:** Because the adapter has **stateful coupling** between services (e.g., command execution needs session state, which needs permission context). A pure module split would require passing 5+ dependencies to every function. The service pattern encapsulates those dependencies.

### 3.2 QueryEngine (1,530 lines) — Strategy + Pipeline Pattern

**Current responsibilities:**
- LLM calling with retry logic
- Context assembly and compaction
- Tool execution orchestration (serial + parallel batches)
- Permission evaluation inline
- User input handling inline
- Transcript event appending
- Session summary persistence
- Memory maintenance triggering
- Interaction checkpointing
- Mode switching

**Refactoring strategy:**

```
┌─────────────────────────────────────────────────────────────┐
│              QueryEngine (Orchestrator, ~400 lines)         │
│  - owns the agent turn loop                                 │
│  - delegates to strategies for each phase                   │
│  - no direct LLM/tool/permission logic                      │
└─────────────────────────────────────────────────────────────┘
        │
        ├──► LLMStrategy (~200 lines)
        │    - call_llm_with_retry
        │    - stream handling
        │    - error classification
        │    - token usage tracking
        │
        ├──► ContextStrategy (~250 lines)
        │    - build_context
        │    - compaction logic
        │    - boundary recording
        │    - schema filtering
        │
        ├──► ExecutionStrategy (~300 lines)
        │    - tool batch partitioning
        │    - StreamingToolExecutor management
        │    - parallel vs serial dispatch
        │    - observation recording
        │
        ├──► InteractionStrategy (~200 lines)
        │    - permission evaluation flow
        │    - user input request/response
        │    - pending interaction checkpointing
        │    - resume logic
        │
        └──► PersistenceStrategy (~150 lines)
             - transcript append
             - summary persist
             - memory maintenance trigger
```

**Critical constraint:** The existing `Session` / `Turn` / `Step` / `ToolCallRecord` hierarchy is excellent and must be preserved. Strategies operate on these types, they don't replace them.

**Migration path:**
1. Extract `LLMStrategy` first — it has the clearest boundary (takes messages+schemas, returns AssistantReply)
2. Extract `InteractionStrategy` second — it has complex state but clear inputs/outputs
3. Extract `ExecutionStrategy` third — depends on the first two
4. Extract `ContextStrategy` last — it touches the most session state

### 3.3 Dependency Injection vs Global State

**Current state:** Heavy use of default constructors that create dependencies inline:

```python
self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
self.summary_store = summary_store or SessionSummaryStore(self.tools.workspace)
```

This makes testing difficult and hides dependency graphs.

**Recommendation:** Use **constructor injection with factories**:

```python
class QueryEngine:
    def __init__(
        self,
        client: OpenAICompatibleClient,
        tools: ToolRuntime,
        strategies: QueryStrategies,  # dataclass grouping all strategies
        config: EngineConfig,
    ) -> None:
        self.client = client
        self.tools = tools
        self.strategies = strategies
        self.config = config
```

**Why not a full DI framework:** Python 3.8 + offline constraint means no `injector`, `dependency-injector`, or similar libraries. Manual constructor injection is verbose but transparent and testable.

**Factory pattern for complex construction:**

```python
@dataclass
class QueryStrategies:
    llm: LLMStrategy
    context: ContextStrategy
    execution: ExecutionStrategy
    interaction: InteractionStrategy
    persistence: PersistenceStrategy

class QueryEngineFactory:
    @classmethod
    def create_default(cls, client, tools, config) -> QueryEngine:
        strategies = QueryStrategies(
            llm=LLMStrategy(client, config.llm),
            context=ContextStrategy(tools, config.context),
            execution=ExecutionStrategy(tools, config.execution),
            interaction=InteractionStrategy(tools.config.permissions, config.interaction),
            persistence=PersistenceStrategy(tools.workspace, config.persistence),
        )
        return QueryEngine(client, tools, strategies, config)
```

---

## 4. Agent Loop Clarity Patterns

### 4.1 Explicit State Machine for Turn Execution

**Current state:** The agent loop in `QueryEngine._run_loop()` is an implicit state machine encoded in nested `if` statements and `while` loops. States include:
- `THINKING` (calling LLM)
- `PRESENTING` (parsing reply)
- `TOOL_PENDING` (executing tools)
- `PAUSED_PERMISSION` / `PAUSED_INPUT` (waiting for user)
- `ERROR_RECOVERY` (retry after failure)

**Problem:** State transitions are scattered across 500+ lines. It's hard to verify that `THINKING` and `TOOL_PENDING` are truly mutually exclusive.

**Recommended pattern: Enum-based state machine with explicit transitions**

The `docs/blueprints/agent-loop-blueprint.md` already defines this precisely. Key design decisions:

```python
class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    PRESENTING = "presenting"
    TOOL_PENDING = "tool_pending"
    PAUSED_PERMISSION = "paused_permission"
    PAUSED_INPUT = "paused_input"
    ERROR_RECOVERY = "error_recovery"
    COMPLETED = "completed"

class AgentLoop:
    def __init__(self):
        self.state = AgentState.IDLE
        self.pending_actions = Queue()
        self.pending_interaction = None
        self.retry_count = 0

    def _transition_to(self, new_state: AgentState):
        old_state = self.state
        self.state = new_state
        self._record_transition(old_state, new_state)

    def run_turn(self):
        # State machine dispatch — one method per state
        handlers = {
            AgentState.IDLE: self._idle_tick,
            AgentState.THINKING: self._thinking_tick,
            AgentState.PRESENTING: self._presenting_tick,
            AgentState.TOOL_PENDING: self._tool_pending_tick,
            AgentState.PAUSED_PERMISSION: self._paused_permission_tick,
            AgentState.PAUSED_INPUT: self._paused_input_tick,
            AgentState.ERROR_RECOVERY: self._error_recovery_tick,
        }
        handler = handlers.get(self.state)
        if handler:
            handler()
```

**Why this matters:**
- Each state's invariants are documented in one place
- Adding a new state requires adding one method and updating the dispatch table
- State transitions can be logged and replayed for debugging
- Resume logic is simplified: restore state, call the corresponding tick handler

### 4.2 Interaction Checkpointing Best Practices

**Current state:** `InteractionCheckpoint` captures action, turn_id, step_id, interaction_id, kind, and request_data. It is stored in `PendingInteraction.request_payload`.

**Strengths:** The existing checkpoint captures enough context to resume accurately.

**Gaps:**
1. No timeout on pending interactions (can hang indefinitely)
2. No versioning on checkpoint schema (future migrations)
3. No validation that resumed action is still valid (e.g., file may have been deleted)

**Recommendations:**

```python
@dataclass
class InteractionCheckpoint:
    version: int = 1  # schema version for future migrations
    action: Dict[str, Any]
    turn_id: str
    step_id: str
    interaction_id: str
    kind: str
    request_data: Dict[str, Any]
    created_at: str  # ISO timestamp
    expires_at: Optional[str] = None  # auto-expire pending interactions

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.utcnow().isoformat() > self.expires_at
```

**Checkpoint validation on resume:**
- For `permission` resume: re-evaluate permission policy (rules may have changed)
- For `user_input` resume: validate that the original question is still relevant
- For file-related actions: verify target file still exists and is writable

### 4.3 Suspend/Resume Semantics

**Current state:** Resume is implemented in `QueryEngine._resume_interaction()` and `InProcessAdapter.resume_session()`. The flow is:
1. Load transcript events
2. Restore session state
3. Reconstruct pending interaction
4. Replay the action through the same pipeline

**Problem:** Resume logic is split between adapter and engine. The adapter knows about tickets; the engine knows about interactions. This creates duplication.

**Recommended unified model:**

```
Suspend:
  AgentLoop.state ──► PAUSED_*
  Session.pending_interaction ──► InteractionCheckpoint
  TranscriptStore.append("pending_interaction", checkpoint)

Resume:
  SessionRestorer.load(checkpoint) ──► Session with pending_interaction
  AgentLoop.state ──► TOOL_PENDING (if permission granted) or THINKING (if denied)
  Action replayed through ToolExecutor with same progress callbacks
```

**Key principle:** Resume should be indistinguishable from fresh execution from the tool's perspective. The only difference is that the permission/user-input gate is pre-resolved.

---

## 5. Storage and Caching Patterns

### 5.1 Session Compression Strategies

**Current state:** `ContextManager.build_messages()` performs context compaction based on token budgets. `QueryEngine._maybe_record_compact_boundary()` records compaction events in the session.

**Current approach:** Character-count-based truncation + summary generation. This is functional but not semantic.

**Recommended layered strategy (from sota-alignment-master-plan P1.1):**

```
Layer 1: ConversationWindowCondenser
  - Sliding window: keep system messages + first user message + last N turns
  - O(1) computation, deterministic
  - Use as default

Layer 2: LLMSummarizingCondenser
  - When window condenser insufficient, use LLM to generate summary
  - Mark summarized turns with forgotten_ids
  - Keep transcript append-only
  - Use when window condenser would discard >50% of history

Layer 3: EmergencyTruncationCondenser
  - On context window error: force-remove 25% of oldest messages
  - Auto-retry LLM call
  - Record emergency truncation in transcript
  - Use as last resort
```

**Implementation constraint:** Must work with Python 3.8 and no external embedding libraries. Semantic relevance scoring (if needed in P2) should use ctags-based symbol frequency, not neural embeddings.

### 5.2 Tool Result Caching Architectures

**Current state:** `ToolResultStore` persists tool results to disk. `ProjectionDb` stores projections. There is no in-memory cache layer.

**Recommended architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    ToolResultCache                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Memory L1  │  │  Disk L2    │  │  Projection L3      │ │
│  │  (session)  │  │  (workspace)│  │  (indexed)          │ │
│  │             │  │             │  │                     │ │
│  │ - read_file │  │ - full tool │  │ - grep results      │ │
│  │   results   │  │   outputs   │  │ - file listings     │ │
│  │ - last 10   │  │ - stored in │  │ - structured        │ │
│  │   per type  │  │   .embedagent│  │   diagnostics      │ │
│  └─────────────┘  │   /results   │  └─────────────────────┘ │
│                   └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

**Caching rules:**
- `read_file`: Cache by (path, mtime, size). Invalidate on file change.
- `list_dir` / `glob_files`: Cache by (path, dir_mtime). Invalidate on directory change.
- `grep_text`: Do not cache (queries are highly variable).
- `run_recipe`: Do not cache (build results change frequently).
- `git_status` / `git_diff`: Cache for 2 seconds (frequently polled by frontend).

**Why not a general memoization decorator:** Different tools have different invalidation semantics. Explicit cache policies are more maintainable than magic decorators.

### 5.3 Schema Migration Approaches

**Current state:** Session restoration from transcript assumes the current schema. There is no migration framework.

**Risk:** As the event schema evolves (new fields, renamed fields, new event types), old transcripts will fail to restore correctly.

**Recommended minimal migration approach:**

```python
class TranscriptMigration:
    MIGRATIONS = {
        1: "baseline",
        2: "add_reasoning_content",
        3: "add_tool_presentation",
        # etc.
    }

    @classmethod
    def migrate_event(cls, event: Dict[str, Any]) -> Dict[str, Any]:
        version = event.get("schema_version", 1)
        for target_version in range(version + 1, cls.CURRENT_VERSION + 1):
            event = cls._apply_migration(event, target_version)
        return event

    @classmethod
    def _apply_migration(cls, event: Dict[str, Any], version: int) -> Dict[str, Any]:
        if version == 2:
            # Add empty reasoning_content if missing
            if "reasoning_content" not in event.get("payload", {}):
                event.setdefault("payload", {})["reasoning_content"] = ""
        # etc.
        event["schema_version"] = version
        return event
```

**Scope:** Only transcript events need migration. Session in-memory state is reconstructed from events, so migrating events is sufficient.

---

## 6. Component Boundaries

### 6.1 Proposed Component Map

| Component | Lines (est.) | Responsibility | Communicates With |
|-----------|-------------|----------------|-------------------|
| `InProcessAdapter` | 400 | Public API facade, event routing | All services |
| `SessionLifecycleService` | 300 | Create, resume, persist sessions | TranscriptStore, SessionRestorer |
| `CommandDispatchService` | 400 | Slash command parsing and execution | WorkspaceService, InteractionService |
| `WorkspaceService` | 250 | File operations, tree listing | ToolContext |
| `InteractionService` | 200 | Permission/user input tickets | PermissionPolicy, QueryEngine |
| `ProjectionService` | 150 | Snapshot, history, bootstrap assembly | SessionSnapshotProjector, SessionHistoryAssembler |
| `QueryEngine` | 400 | Turn loop orchestration | All strategies |
| `LLMStrategy` | 200 | LLM calls, retries, streaming | OpenAICompatibleClient |
| `ContextStrategy` | 250 | Message assembly, compaction | ContextManager, WorkspaceIntelligenceBroker |
| `ExecutionStrategy` | 300 | Tool dispatch, parallel/serial | StreamingToolExecutor, ToolRuntime |
| `InteractionStrategy` | 200 | Permission flow, user input flow | PermissionPolicy, InteractionService |
| `PersistenceStrategy` | 150 | Transcript append, summary, memory | TranscriptStore, SessionSummaryStore, MemoryMaintenance |
| `CompileEnvironment` | 300 | Toolchain discovery, capability matrix | HarnessRunner, ToolRuntime |
| `DiagnosticParser` | 150 | Compiler output parsing | ExecutionStrategy |
| `ToolResultCache` | 200 | Multi-tier caching | ToolRuntime, ProjectionDb |
| `AgentLoop` (future) | 400 | Event-driven state machine | Replaces QueryEngine._run_loop() |

**Total after refactoring:** ~4,650 lines vs. current ~4,500 lines in just Adapter+Engine. The increase is intentional — clarity and testability justify the modest growth.

### 6.2 Data Flow

```
Frontend Request
       │
       ▼
InProcessAdapter (Facade)
       │
       ├──► SessionLifecycleService ──► ManagedSession + Session
       │
       └──► CommandDispatchService ──► Action or QueryEngine.turn()
                │
                ▼
         QueryEngine (Orchestrator)
                │
                ├──► ContextStrategy ──► ContextAssemblyResult
                │           │
                │           ▼
                │      LLMStrategy ──► AssistantReply
                │           │
                │           ▼
                │      ExecutionStrategy ──► Observations
                │           │
                │           ▼
                │      InteractionStrategy ──► PendingInteraction or Observation
                │           │
                │           ▼
                │      PersistenceStrategy ──► Transcript + Summary
                │
                ▼
         Event callbacks ──► Frontend
```

---

## 7. Suggested Build Order

### Phase 1: Foundation (Low Risk, High Clarity)
1. **Extract DiagnosticParser** from `ToolContext` — pure function, no state risk
2. **Extract WorkspaceService** from `InProcessAdapter` — clear API boundary
3. **Add ToolResultCache** — additive, can be disabled

### Phase 2: Engine Restructuring (Medium Risk)
4. **Extract LLMStrategy** from `QueryEngine` — isolated, well-tested
5. **Extract PersistenceStrategy** from `QueryEngine` — mostly append operations
6. **Extract InteractionStrategy** from `QueryEngine` — complex but bounded

### Phase 3: Loop Modernization (High Risk, High Impact)
7. **Introduce AgentLoop state machine** — replace `QueryEngine._run_loop()`
8. **Implement _pending_action mutual exclusion** — prevents concurrent LLM calls
9. **Add should_step() filtering** — only observations and user messages trigger steps

### Phase 4: Compile Environment Integration (Domain-Specific)
10. **Create CompileEnvironment component** — move discovery from ToolContext
11. **Integrate diagnostic streaming** — real-time parser during build execution
12. **Add build state tracking** — clean/dirty/incremental awareness

### Phase 5: Polish (Low Risk)
13. **Extract CommandDispatchService** — mostly moving code
14. **Add schema migration** — defensive for future changes
15. **Add interaction checkpoint timeouts** — safety improvement

---

## 8. Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Instead |
|-------------|---------|---------|
| **Async/await in agent loop** | Python 3.8 + Windows 7 = ProactorEventLoop bugs; breaks existing sync architecture | Stick to threading + queue-based streaming |
| **Replacing Session model** | Existing Turn/Step/ToolCallRecord hierarchy is a strength | Preserve it; strategies operate on it |
| **Global state for engine config** | Makes testing impossible, hides dependencies | Constructor injection with factories |
| **Caching everything** | Build results, git status, and user input must never be cached | Tool-specific cache policies |
| **Event-driven = micro-threads everywhere** | Hard to debug, race conditions | Single event loop thread + thread pool for I/O |
| **Generic migration framework** | Over-engineered for current needs | Versioned event migrations only |

---

## 9. Confidence Assessment

| Area | Confidence | Notes |
|------|-----------|-------|
| Compile Environment Architecture | HIGH | Existing `ToolContext` already has discovery logic; extraction is mechanical |
| Refactoring Patterns | HIGH | Facade/Strategy/Pipeline are standard patterns; blueprints validate approach |
| Agent Loop State Machine | MEDIUM-HIGH | Blueprint is detailed; risk is in migration, not design |
| Storage/Caching | MEDIUM | Current system works; improvements are additive but need profiling |
| Build Order | MEDIUM | Dependencies between phases are clear, but phase 3 (loop) has regression risk |

## 10. Sources

- `docs/overall-solution-architecture.md` — official architecture baseline
- `docs/blueprints/agent-loop-blueprint.md` — event-driven loop design
- `docs/blueprints/tool-environment-blueprint.md` — tool execution pipeline
- `docs/sota-alignment-master-plan.md` — gap analysis and SOTA alignment
- `src/embedagent/inprocess_adapter.py` (2,446 lines) — current adapter implementation
- `src/embedagent/query_engine.py` (1,530 lines) — current engine implementation
- `src/embedagent/tools/_base.py` (743 lines) — tool context and compile env
- `src/embedagent/session.py` (620 lines) — session data model
- `src/embedagent/harness/runner.py` (121 lines) — harness runner
- `src/embedagent/tool_execution.py` (251 lines) — streaming executor
- `docs/archive/clang-integration/clang-integration-plan.md` — historical compile env work
