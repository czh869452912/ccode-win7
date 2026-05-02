# Feature Landscape

**Domain:** Agentic coding framework with compile environment integration (C/C++, offline, Windows 7)
**Researched:** 2026-05-02
**Confidence:** HIGH (based on direct codebase analysis + SOTA alignment master plan)

---

## Executive Summary

EmbedAgent's compile environment integration is at a **functional but basic** level. The codebase already has compiler detection (LLVM/Clang), a recipe system with CMake support, diagnostic parsing for Clang and MSVC, and build directory management. However, compared to SOTA agentic coding frameworks (Claude Code, Roo-Code, OpenHands, Codex CLI), the compile environment layer lacks streaming build output, incremental build awareness, cross-compilation support, and deep compiler integration.

The framework improvement layer is more mature: parallel tool execution, permission system, context management, and transcript-backed sessions are already implemented. The main gaps are in agent loop observability, tool result caching, LLM resilience, and error recovery patterns.

**Recommendation:** Prioritize table stakes compile features that close the "vibe coding" gap, then invest in differentiating features that leverage the offline/C-centric positioning.

---

## Table Stakes

Features users expect from any agentic coding framework with compile environment integration. Missing these makes the product feel broken or incomplete.

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| **Compiler detection and version reporting** | Agent must know what compiler is available to give correct advice | Low | **Partial** | `ToolContext.resolve_managed_tool_path("llvm")` detects bundled LLVM; no version extraction (`clang --version`) yet |
| **Build directory management** | C/C++ projects need out-of-source builds; agent must not pollute source tree | Low | **Exists** | CMake recipes already use `-B build/` pattern; `workspace_recipes.py` handles profile-specific build dirs |
| **Compilation with error parsing** | Core loop: edit -> compile -> fix errors. Without structured diagnostics, agent is blind | Medium | **Exists** | `CLANG_DIAGNOSTIC_RE` and `MSVC_DIAGNOSTIC_RE` parse errors/warnings/notes into structured JSON; `parse_diagnostics()` returns file/line/column/level/message |
| **Diagnostic reporting (warnings, errors, suggestions)** | Agent needs counts and structured lists to make repair decisions | Low | **Exists** | `diagnostic_counts()` returns error_count/warning_count/note_count; `report_quality_v2` tool consumes these |
| **Recipe discovery and execution** | Agent must find and run build/test commands without hand-holding | Medium | **Exists** | `list_recipes` + `run_recipe` support project recipes, detected recipes (CMake), and history recipes |
| **Basic test result parsing** | After build, agent needs to know if tests passed/failed/skipped | Low | **Exists** | `parse_test_summary()` extracts passed/failed/skipped from test output |
| **Toolchain PATH injection** | Bundled tools must be found without system dependencies | Low | **Exists** | `build_process_env()` prepends managed tool directories to PATH; `EMBEDAGENT_LLVM_ROOT` env var set |
| **Shell command execution with timeout** | Agent needs to run arbitrary build commands safely | Low | **Exists** | `run_shell_tool()` with configurable timeout, interrupt support, and output truncation |
| **Build output truncation** | Long builds produce megabytes of output; agent context is limited | Low | **Exists** | `MAX_COMMAND_OUTPUT_CHARS = 40000` truncates stdout/stderr; truncation flags preserved |
| **Parallel read-only tool execution** | File discovery should not block on compilation | Medium | **Exists** | `StreamingToolExecutor` with `partition_tool_actions()` runs read-only tools in parallel threads |

### Table Stakes Gap Analysis

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| Compiler version extraction (`clang --version`) | Agent cannot reason about compiler capabilities or flag compatibility | Low | P1 |
| Streaming build output (real-time stdout/stderr) | Users think build hung during long compilation; no progress visibility | Medium | P0 |
| Build artifact size reporting | Agent cannot detect binary bloat or linking issues | Low | P2 |
| Makefile/Ninja recipe detection | Only CMake auto-detected; many C projects use Make | Low | P1 |

---

## Differentiators

Features that set the product apart. Not universally expected, but create competitive advantage especially in the offline/C-development niche.

| Feature | Value Proposition | Complexity | Status | Notes |
|---------|-------------------|------------|--------|-------|
| **Incremental build support** | Agent understands what changed and can run partial rebuilds instead of clean builds | Medium | **Not built** | Currently no tracking of file modification times vs build artifacts; agent always runs full recipe |
| **Cross-compilation support** | Target embedded platforms from Windows 7 host with bundled toolchain | High | **Not built** | Would require target triple detection, sysroot management, and cross-compiler discovery in bundle |
| **Build cache integration (ccache/sccache)** | Dramatically speeds up repeated builds in long debug sessions | Medium | **Not built** | ccache is compiler-agnostic and could be bundled; requires cache hit/miss reporting to agent |
| **Parallel compilation orchestration** | Agent controls `-j` flags based on CPU cores and workload | Low | **Partial** | CMake recipes don't auto-inject `-j`; agent could set `CMAKE_BUILD_PARALLEL_LEVEL` |
| **Coverage summary parsing** | Agent tracks code coverage trends across iterations | Low | **Exists** | `parse_coverage_summary()` extracts line/function/branch/region coverage from llvm-cov output |
| **Shadow Git Checkpointing** | Automatic snapshots before each build/edit enable safe auto-approve and rollback | Medium | **Not built** | Identified in SOTA plan P0.4; bundled MinGit already available |
| **Tool result caching** | Avoid re-running identical commands (e.g., `git status`, `list_recipes`) | Medium | **Partial** | `ToolResultStore` exists but no semantic cache key deduplication |
| **LLM Resilience Layer** | Retry/backoff, token tracking, local LLM profiles for offline reliability | Medium | **Not built** | Identified in SOTA plan P0.3; `ModelClientError` is currently fatal with no retry |
| **Event-driven agent loop** | Explicit Action -> Observation -> should_step() model prevents race conditions | High | **Partial** | Current loop in `query_engine.py` is turn-based; `_pending_action` mutual exclusion not yet implemented |
| **Multi-search-replace diff tool** | Reliable code editing (>95% success) instead of fragile string replacement | Medium | **Not built** | Identified in SOTA plan P0.1; current `edit_file` uses naive string replace |
| **Context condenser strategy** | Smart context compression for long debug sessions without "amnesia" | High | **Not built** | Identified in SOTA plan P1.1; current compaction is truncation-based |
| **Codebase symbol search** | Ctags-based symbol indexing for large C project navigation | Medium | **Not built** | Identified in SOTA plan P2.2; bundled ctags already available but not consumed for indexing |

### Differentiator Prioritization Rationale

**Build P0 (Immediate):**
1. **Streaming build output** — Highest user-perceived impact. A 2-minute compile with no feedback feels broken.
2. **Shadow Git Checkpointing** — Unlocks auto-approve mode, which is the defining "vibe coding" experience.
3. **LLM Resilience Layer** — Offline LLMs (Ollama/vLLM) are unreliable; without retry, the agent crashes.

**Build P1 (After P0):**
4. **Multi-search-replace diff** — 30% edit failure rate is a major vibe-killer.
5. **Incremental build support** — Saves time in iterative debug loops; relatively easy to implement with file mtime tracking.
6. **Tool result caching** — Cheap win; reduces redundant tool calls and token consumption.

**Build P2 (Architectural runway):**
7. **Cross-compilation support** — Aligns with embedded C target market; high complexity but strong differentiation.
8. **Build cache integration** — Nice-to-have for large projects; ccache is mature and bundlable.
9. **Codebase symbol search** — Differentiator for large C codebases where grep is insufficient.

---

## Anti-Features

Features to explicitly NOT build. These either conflict with constraints, add complexity without value, or are scope creep.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Docker/WSL integration** | Violates Windows 7 compatibility and offline-only constraints | Use bundled native toolchains (LLVM, MinGit) exclusively |
| **Cloud-based build farms** | Violates offline deployment mandate; adds network dependency | Parallel compilation via local `-j` and ccache |
| **CMake GUI/configuration wizard** | Scope creep — this is an agent IDE, not a CMake frontend | Agent uses `run_recipe` with detected CMake recipes |
| **IDE-style code completion** | Requires LSP integration, massive dependency surface, conflicts with offline bundle size | Agent uses `read_file` + `grep_text` for context; defer to dedicated editors |
| **Package manager integration (conan/vcpkg)** | Adds network dependency and complexity; not core to C development workflow | Document recipes for manual dependency management |
| **Multi-language support (Rust, Go, etc.)** | Dilutes focus; product is C/C++ centered | Keep toolchain detection LLVM-centric; reject scope expansion |
| **Remote debugging/GDB server** | Complex, niche, conflicts with offline simplicity | Local debugging via `run_command` with bundled tools |
| **Auto-fix without human review** | Dangerous for production C code; liability issue | Shadow Git checkpoints + permission system with cost ceiling |
| **Real-time collaboration/multi-user** | Massive complexity, not requested by target users | Single-user offline focus |
| **Plugin marketplace / MCP servers at runtime** | Violates offline constraint; security risk | P2 reserved interface only; no dynamic loading in bundle |

---

## Feature Dependencies

```
Streaming build output
  → Requires: Protocol extension for progress events
  → Enables: Real-time user feedback during long compiles

Shadow Git Checkpointing
  → Requires: Bundled MinGit (already available)
  → Enables: Safe auto-approve mode, rollback, "vibe coding"
  → Enables: Error recovery (restore last known good state)

LLM Resilience Layer
  → Requires: Config extension for base_url, retries, profiles
  → Enables: Local LLM usage (Ollama, vLLM)
  → Enables: Token budget-aware decisions

Incremental build support
  → Requires: File modification time tracking
  → Requires: Build artifact inventory
  → Enables: Faster iterative debug loops

Build cache integration
  → Requires: Bundled ccache binary
  → Enables: Speedup on repeated builds
  → Conflicts with: None (optional, degrades gracefully)

Tool result caching
  → Requires: Semantic cache key generation
  → Requires: Cache invalidation on file writes
  → Enables: Reduced redundant tool calls

Event-driven agent loop
  → Requires: Refactoring query_engine.py turn logic
  → Enables: Better error recovery, cleaner state machine
  → Enables: Sub-agent delegation (P2)
```

---

## MVP Recommendation

For the next milestone focusing on compile environment integration + framework improvements, prioritize:

1. **Streaming build output** (P0) — Transform `run_shell_tool` to emit progress events; add `tool_progress` transcript event type; update frontend to render streaming output.
2. **Compiler version reporting** (P0) — Add `compiler_info` tool that runs `clang --version` and reports capabilities; inject into workspace profile message.
3. **LLM Resilience Layer** (P0) — Add retry/backoff to `llm.py`, `base_url` support, token usage tracking, local LLM profiles.
4. **Shadow Git Checkpointing** (P0) — Auto-commit before writes, `checkpoint_restore` tool, transcript truncation parent markers.
5. **Makefile/Ninja auto-detection** (P1) — Extend `workspace_recipes.py` to detect `Makefile`, `makefile`, `build.ninja` and generate recipes.

Defer:
- **Cross-compilation support**: Requires embedded target research and toolchain bundling decisions.
- **Build cache integration**: Nice-to-have; ccache can be added later without architecture changes.
- **Codebase symbol search**: Large project navigation; ctags indexing is P2 in SOTA plan.
- **Context condenser**: Important for long sessions but higher complexity; defer to P1 after P0 stabilization.

---

## Framework Improvement Features

### Agent Loop Observability (Tracing, Logging)

| Aspect | Current State | Gap | Priority |
|--------|--------------|-----|----------|
| Transcript events | `transcript.jsonl` with `step_started`, `tool_call`, `context_snapshot`, `loop_transition`, `message` events | **Good** — industry-leading durability model | — |
| Structured logging | Basic Python `logging` module | No structured JSON logging for external observability | P2 |
| Execution trace | Turn/step/tool_call hierarchy in transcript | No visual trace export or flamegraph-style view | P2 |
| Token usage tracking | Not implemented | `llm.py` discards `usage` field; no per-session cost metrics | P0 |
| Loop guard telemetry | `LoopGuard` records action/observation pairs | No export of guard decisions or loop health metrics | P1 |

### Tool Result Caching

| Aspect | Current State | Gap | Priority |
|--------|--------------|-----|----------|
| Tool result store | `ToolResultStore` persists results to `.embedagent/memory/tool-results/` | No semantic deduplication; identical calls re-run | P1 |
| Cache invalidation | Not implemented | File reads should cache-bust on file modifications | P1 |
| Cache TTL | Not implemented | Some results (git status) change frequently | P2 |
| Cache scope | Per-workspace | No cross-session cache sharing | P2 |

### Session Storage Optimization

| Aspect | Current State | Gap | Priority |
|--------|--------------|-----|----------|
| Transcript append-only | `transcript.jsonl` is append-only; durable and replayable | **Good** — best practice | — |
| Session snapshot | `SessionSnapshotProjector` builds bootstrap payload | Snapshots could be cached to avoid recomputation | P2 |
| Context assembly | `ContextManager` assembles messages with budget checks | No incremental context updates; full rebuild each turn | P2 |
| Memory maintenance | `MemoryMaintenance` runs every N turns | Could be event-driven instead of counter-driven | P2 |

### Error Recovery and Retry Patterns

| Aspect | Current State | Gap | Priority |
|--------|--------------|-----|----------|
| LLM retry | `_call_llm_with_retry` exists with compact retry on context length errors | No exponential backoff; no 429/5xx retry; no model fallback | P0 |
| Tool retry | Tool errors marked `retryable: True` in observation data | No automatic retry loop; agent must decide to retry | P1 |
| Context length recovery | Compact boundary recorded, force_compact triggered | No "remove 25% of history and retry" strategy (Roo-Code pattern) | P1 |
| Build failure recovery | Agent sees exit_code and diagnostics | No automatic "clean build" fallback on incremental build failure | P2 |
| Checkpoint rollback | Not implemented | No `checkpoint_restore` tool; no automatic rollback on critical errors | P0 |

### State Machine Clarity

| Aspect | Current State | Gap | Priority |
|--------|--------------|-----|----------|
| Mode definitions | `modes.py` with 5 official modes; strict vocabulary | **Good** — clear product contracts | — |
| Phase engine | `phase_engine.py` advances phases based on artifact flags | Phase transitions are deterministic; could benefit from probabilistic/intelligent advancement | P2 |
| Task graph | `TaskGraph` with structured items and summary | Task items are static; no dynamic task creation based on build results | P2 |
| Pending interactions | `PendingInteraction` for permission/user input suspend/resume | Interaction resolution re-enters same pipeline (good) | — |
| Action/Observation causality | Observations record tool_name but not explicit `cause = action.id` | Missing causal link for debugging and visualization | P1 |

---

## Sources

- Direct codebase analysis: `src/embedagent/tools/_base.py`, `src/embedagent/tools/recipe_ops.py`, `src/embedagent/tools/shell_ops.py`, `src/embedagent/workspace_recipes.py`, `src/embedagent/query_engine.py`, `src/embedagent/tool_execution.py`, `src/embedagent/llm.py`
- `docs/sota-alignment-master-plan.md` — Gap analysis vs Claude Code, Roo-Code, OpenHands, Codex CLI
- `docs/implementation-roadmap.md` — Current sequencing and priorities
- `docs/overall-solution-architecture.md` — Architecture constraints and design rules
- Roo-Code GitHub repository (github.com/RooCodeInc/Roo-Code) — Feature reference for checkpoints, diff strategies, context management
- OpenHands GitHub repository (github.com/OpenHands/OpenHands) — Feature reference for event-driven loops, condenser strategies, tool interfaces
