# PROJECT: EmbedAgent

## What This Is

EmbedAgent is an offline-first Agent IDE core for C/C++ application development on Windows 7. It orchestrates LLM-driven development tasks through a stable harness system with explicit state management, permission controls, durable session history, and a Clang-centered toolchain.

## Core Value

The agent core reliably orchestrates LLM-driven development tasks through a stable harness system with explicit state management, permission controls, and durable session history.

## Requirements

### Validated (v0.1)

- ✓ Code hygiene: zero deprecation warnings, specific exception handling — v0.1
- ✓ Compile environment: compiler detection, build configuration, streaming execution, diagnostic parsing — v0.1
- ✓ Architecture: service extraction, strategy extraction, global state elimination, backward compatibility — v0.1
- ✓ Framework: shadow git, LLM resilience, tool caching, diff engine, observability — v0.1

### Active

- [ ] Multi-file refactoring across translation units
- [ ] Cross-reference generation (call graph, type hierarchy)
- [ ] Integrated debugging workflow (breakpoint, step, variable inspection)
- [ ] Project template scaffolding for C/C++ projects
- [ ] Package manager integration (vcpkg, conan)

### Out of Scope

- Browser automation — not a web agent
- Web search — offline deployment mandatory
- Heavyweight RAG platform — focused on code, not documents
- Plugin marketplace — core product only
- General multi-agent orchestration — single agent focus
- Mobile app development — Windows 7 desktop only
- Cloud service dependencies — offline mandatory

## Context

**Shipped v0.1** with ~33,076 LOC Python across src/ and tests/.

**Tech stack:** Python 3.8.10, pytest, ruff, black, git

**Architecture patterns established:**
- Facade + Strategy decomposition
- Manual dependency injection container
- Service extraction pattern for monolithic classes
- Characterization tests for regression prevention

**Known issues:**
- 1 pre-existing flaky GUI sync test (`test_gui_sync.py`)
- Some workflows reference `gsd-sdk` which is not available in this environment
- Nyquist compliance missing for Phases 2-4

## Key Decisions

| ID | Decision | Status | Notes |
|----|----------|--------|-------|
| D-01 | Code hygiene precedes feature work | ✓ Good | Phase 1 established clean baseline |
| D-02 | Python 3.8 stdlib only for compile tools | ✓ Good | Ensures Windows 7 compatibility |
| D-03 | Facade + Strategy with manual DI | ✓ Good | Enabled testable architecture |
| D-04 | Git stash-based snapshots | ✓ Good | Lightweight, preserves untracked files |
| D-05 | Threading over asyncio for streaming | ✓ Good | Avoids event loop conflicts |
| D-06 | Manual DI over external framework | ✓ Good | Minimal dependencies, Python 3.8 safe |

## Constraints

- **Windows 7 compatibility mandatory** — Python 3.8.x strictly, no 3.9+ syntax
- **Offline deployment mandatory** — no runtime dependencies on external online services
- **Agent Core is the product core** — UI shells are replaceable
- **C/C++ first-class workflow** — Clang-centered toolchain
- **Small dependency surface** — standard library + minimal third-party packages

---

*Last updated: 2026-05-03 after v0.1 milestone completion*
