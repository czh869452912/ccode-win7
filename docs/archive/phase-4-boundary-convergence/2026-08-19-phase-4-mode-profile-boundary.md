# Phase 4 Mode And Profile Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove remaining platform-owned mode/profile and implicit-provider behavior from generic Core/Host/Shell paths while preserving explicit application contributions.

**Architecture:** Generic runtime APIs accept only application-selected contributions and frozen projections. Product semantics remain in application packages; no compatibility aliases, default mode fallback, or generic provider registry is added. Existing `HostedSessionController`, `ApplicationRuntimeContribution`, and selected bundle manifest remain the only composition boundaries.

**Tech Stack:** Python 3.8 stdlib/dataclasses, existing Core/Host/Protocol contracts, pytest architecture guards, offline bundle tests.

---

### Task 1: Inventory And Lock The Boundary

**Files:**
- Inspect: `packages/embedagent-core/src/embedagent_core/application.py`, `packages/embedagent-host/src/embedagent_host/runtime/profiles.py`, `packages/embedagent-host/src/embedagent_host/runtime/context.py`, `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Test: `tests/test_phase4_mode_profile_boundary.py`

- [ ] Add failing architecture tests that generic Host construction has no default mode/provider, application records carry explicit runtime contribution identity, and selected capability projection cannot synthesize a profile.
- [ ] Run the focused tests and record the current fallback paths.

### Task 2: Remove Generic Fallbacks

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/profiles.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-core/src/embedagent_core/application.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`

- [ ] Make missing application semantics a typed, fail-closed configuration error.
- [ ] Keep generic provider tuples empty unless an application contribution supplies them.
- [ ] Remove profile/mode synthesis and update callers to pass the explicit application contribution.
- [ ] Run focused boundary and host facade tests.

### Task 3: Migrate Tests And Durable Documentation

**Files:**
- Modify: `tests/test_current_architecture_boundaries.py`, `tests/test_agent_profiles.py`, `tests/test_modes.py`, and affected Host/application tests
- Modify: `docs/current-status.md`, `docs/implementation-roadmap.md`, `docs/platform/agent-core.md`, `docs/platform/protocol.md`

- [ ] Replace tests that encode retired generic ownership with tests for explicit application contribution and fail-closed generic construction.
- [ ] Update the owning architecture documents without adding compatibility notes for retired internals.
- [ ] Run architecture, full regular, lint, and documentation navigation gates.

### Task 4: Commit

- [ ] Commit only mode/profile boundary changes with message `refactor: close generic mode profile boundary`.

