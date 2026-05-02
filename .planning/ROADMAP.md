# Roadmap: EmbedAgent — Compile Environment + Framework Improvements

## Overview

This roadmap delivers a hardened compile environment integration, codebase hygiene, architecture refactoring, and framework resilience improvements to the EmbedAgent agent core. Starting with code hygiene to establish a clean foundation, we integrate compiler detection and build execution, refactor monolithic classes into maintainable services, and finally layer on checkpointing, caching, and resilience features.

## Phases

- [ ] **Phase 1: Foundation** — Clean deprecation warnings and bare except blocks for a warning-free codebase
- [ ] **Phase 2: Compile Environment** — Compiler detection, build configuration, streaming execution, and structured diagnostics
- [ ] **Phase 3: Architecture** — Extract monolithic classes and eliminate global mutable state
- [ ] **Phase 4: Framework** — Shadow git, LLM resilience, tool caching, diff tool, and observability

## Phase Details

### Phase 1: Foundation
**Goal**: Clean, warning-free codebase that passes all tests without deprecation warnings
**Depends on**: Nothing (first phase)
**Requirements**: HYGN-01, HYGN-02, HYGN-03
**Success Criteria** (what must be TRUE):
  1. All `datetime.utcnow()` calls replaced with timezone-aware equivalents (`datetime.now(timezone.utc)`)
  2. All 44 bare `except Exception:` blocks replaced with specific exception handling
  3. Test suite runs with zero deprecation warnings in CI output
**Plans**: 3 plans *(revised with review feedback)*

Plans:
- [ ] `01-01-PLAN.md` — Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` across 9 source files; includes characterization tests and format verification (HYGN-01)
- [ ] `01-02-PLAN.md` — Replace bare `except Exception:` with specific exception handling across 16 source files; includes characterization tests and fallback logging (HYGN-02)
- [ ] `01-03-PLAN.md` — Verify test suite produces zero deprecation warnings with progressive configuration and captured baseline (HYGN-03)

**Wave Structure:**
- **Wave 1**: Plan 01 *(datetime fixes — no dependencies)*
- **Wave 2**: Plan 02 *(except fixes — depends on Wave 1 to avoid file conflicts)*
- **Wave 3**: Plan 03 *(verification — depends on Waves 1 and 2)*

### Phase 2: Compile Environment
**Goal**: Agent can detect, configure, and execute C/C++ compilation with real-time feedback
**Depends on**: Phase 1
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04, COMP-05, COMP-06, COMP-07
**Success Criteria** (what must be TRUE):
  1. Agent detects installed compilers (Clang, GCC, MSVC) and reports their versions
  2. Agent configures build directories, flags, and environment variables per project
  3. Agent executes compilation with real-time streaming output (stdout/stderr)
  4. Agent parses compilation diagnostics into structured error/warning/note reports
  5. Agent auto-detects Makefile/Ninja recipes, reports build artifact sizes, and uses safe subprocess execution with configurable timeouts
**Plans**: 4 plans

Plans:
- [x] `03-01-PLAN.md` — Extract InProcessAdapter (2,446 lines) into 4 focused services: SessionLifecycleManager, EventEmitter, WorkspaceFileService, HarnessStateSynchronizer; thin facade remains (ARCH-01)
- [x] `03-02-PLAN.md` — Extract QueryEngine (1,530 lines) into 3 strategies: LLMClientRetryWrapper, ContextCompactionEngine, TurnOrchestrator; thin orchestrator remains (ARCH-02)
- [x] `03-03-PLAN.md` — Eliminate global mutable state via manual DI container: replace MODE_REGISTRY, _DEFAULT_SANITIZER, _inprocess_adapter with factory functions (ARCH-03)
- [x] `03-04-PLAN.md` — Add characterization tests for all extracted components and backward compatibility tests verifying public API stability; architecture documentation (ARCH-04, ARCH-05)

**Wave Structure:**
- **Wave 1**: Plans 01, 02 *(service extraction and strategy extraction — no dependencies between them)*
- **Wave 2**: Plan 03 *(global state elimination — depends on Wave 1 to avoid conflicts with refactored constructors)*
- **Wave 3**: Plan 04 *(characterization and compatibility tests — depends on Waves 1 and 2)*

### Phase 3: Architecture
**Goal**: Maintainable codebase with clear component boundaries and no global state
**Depends on**: Phase 2
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05
**Success Criteria** (what must be TRUE):
  1. `InProcessAdapter` extracted into focused services (SessionLifecycle, EventEmitter, WorkspaceFileService, HarnessStateSynchronizer)
  2. `QueryEngine` extracted into strategies (LLMClientRetryWrapper, ContextCompactionEngine, TurnOrchestrator)
  3. Global mutable state eliminated via dependency injection (`MODE_REGISTRY`, `_DEFAULT_SANITIZER`, `_inprocess_adapter`)
  4. Characterization tests exist for all extracted components preventing regression
  5. All existing public APIs remain backward compatible
**Plans**: 4 plans

### Phase 4: Framework
**Goal**: Resilient agent framework with checkpointing, caching, and reliable editing
**Depends on**: Phase 3
**Requirements**: FRAM-01, FRAM-02, FRAM-03, FRAM-04, FRAM-05, FRAM-06
**Success Criteria** (what must be TRUE):
  1. Shadow Git automatically snapshots workspace before builds and edits
  2. LLM calls use retry with backoff, circuit breaker, and token tracking for offline reliability
  3. Tool results cached in 3-tier system (memory L1, disk L2, projection L3) with invalidation policies
  4. Multi-search-replace diff tool achieves >95% code editing success rate
  5. Agent loop provides structured logging, execution tracing, and explicit state machine documentation
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-05-02 |
| 2. Compile Environment | 4/4 | Complete | 2026-05-02 |
| 3. Architecture | 4/4 | Complete | 2026-05-02 |
| 4. Framework | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-02*
*Granularity: Standard*
*Coverage: 21/21 v1 requirements mapped*
