# Milestones

## v0.1 — Compile Environment + Framework Improvements

**Shipped:** 2026-05-02
**Phases:** 1-4 (16 plans, ~37 days)
**Tag:** v0.1

### What Shipped

A hardened compile environment integration, codebase hygiene, architecture refactoring, and framework resilience improvements.

### Key Accomplishments

1. **Clean codebase foundation** — Replaced 44 bare `except Exception:` blocks and all `datetime.utcnow()` calls; achieved zero deprecation warnings in test output
2. **Compile environment tooling** — Added compiler detection (`list_compilers`), build configuration (`configure_build_env`), streaming build execution (`run_build`), and enhanced diagnostic parsing for Clang/GCC/MSVC
3. **Architecture refactoring** — Extracted InProcessAdapter into 4 services and QueryEngine into 3 strategies; eliminated global mutable state via manual DI container
4. **Framework resilience** — Implemented Shadow Git snapshots, circuit breaker pattern, 3-tier tool caching, multi-search-replace diff engine (100% success rate), and execution tracing with 14 event types
5. **Comprehensive test coverage** — 37 new characterization/backward-compatibility tests, 8 LLM resilience tests, 6 shadow git tests, 8 tool cache tests, 10 diff engine tests, 6 execution tracer tests
6. **Backward compatibility** — All existing public APIs preserved; 509+ tests passing with only 1 pre-existing flaky GUI test

### Stats

- **Commits:** 328 total
- **Timeline:** 2026-03-27 to 2026-05-02
- **Files changed:** 771 files, 191,899 insertions
- **Python LOC:** ~33,076 (src/ + tests/)

### Audit

**Status:** PASSED (manual audit, 2026-05-03)
**Score:** 21/21 requirements satisfied
**Report:** `.planning/v0.1-MILESTONE-AUDIT.md`

### Known Issues at Close

- Nyquist compliance missing for Phases 2-4 (only Phase 1 has VALIDATION.md)
- L3 projection cache is a placeholder
- QueryEngine remains ~1560 lines (target was <500)

## v0.2 — GUI & Harness Experience Refactor

**Started:** 2026-05-03
**Phases:** 5-7 (10 plans)
**Status:** ACTIVE

### Goal

Transform EmbedAgent's user experience to match industry-leading agent coding tools (Claude Code, Codex, Roo Code) by refactoring session persistence, conversation flow, and mode execution models.

### Target Features

1. **Session Infrastructure** — Typed JSONL transcript, robust resume, flat conversation model
2. **GUI Experience** — Inline tool cards, inline diff preview, real-time streaming, conversation-first layout
3. **Harness Refactor** — Permission-contract-based modes, intent-driven workflow, completion self-assessment

### Reference Engineering

- Research artifacts: `.planning/phases/01-ui-ux-harness-research/01-RESEARCH.md`
- Architecture spec: `.planning/notes/session-architecture-v2-spec.md`

---

*For milestone details, see `.planning/milestones/v0.1-ROADMAP.md`*
