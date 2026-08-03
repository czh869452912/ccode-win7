# Standalone Agent Platform Extraction Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Synchronize the tool execution authority and make the standalone Core public surface, example, and isolated wheel acceptance executable without Host, Protocol, product, GUI, or workflow packages.

**Architecture:** Keep `Agent` / `AgentSession` as the only high-level standalone entry and keep `AgentPorts` explicit. Re-export only the existing contracts and safe stdlib defaults required to construct and drive that API; run one repository example as the `core_only` wheel probe so documentation, sample code, and distribution acceptance cannot drift.

**Tech Stack:** Python 3.8, stdlib protocols/dataclasses, pytest, uv workspace wheel builder and smoke runner.

---

### Task 1: Synchronize The Tool Execution Authority

**Files:**
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `docs/platform/tools-and-extensions.md`

- [ ] **Step 1: Write the failing documentation boundary test**
- [ ] **Step 2: Run `uv run python scripts/test-suite.py tdd tests/test_current_architecture_boundaries.py` and verify RED**
- [ ] **Step 3: Document serial preparation, durable start commit, prepared execution, source-order materialization, and Kernel/Loop checkpoint resume**
- [ ] **Step 4: Run the focused test and verify GREEN**

### Task 2: Stabilize The Standalone Root Public Surface

**Files:**
- Modify: `tests/test_agent_core_public_api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/__init__.py`
- Modify: `docs/platform/agent-core.md`

- [ ] **Step 1: Write a failing root-import contract test for construction ports, provider/tool DTOs, safe defaults, and public execution errors**
- [ ] **Step 2: Run `uv run python scripts/test-suite.py tdd tests/test_agent_core_public_api.py` and verify RED**
- [ ] **Step 3: Re-export existing contracts without wrappers or implicit ports**
- [ ] **Step 4: Run the public API test and verify GREEN**

### Task 3: Add One Executable Standalone SDK Example

**Files:**
- Create: `examples/standalone_agent.py`
- Create: `tests/test_standalone_agent_example.py`

- [ ] **Step 1: Write a failing contract for a Core-root-only, explicit-ports, suspend/resume example**
- [ ] **Step 2: Run `uv run python scripts/test-suite.py tdd tests/test_standalone_agent_example.py` and verify RED**
- [ ] **Step 3: Implement the deterministic offline example without Host, Protocol, product, GUI, workflow, network, or filesystem side effects**
- [ ] **Step 4: Run the example test and verify GREEN**

### Task 4: Make The Core-Only Wheel Run The Example

**Files:**
- Modify: `tests/test_python_distribution_smoke.py`
- Modify: `scripts/smoke-python-distributions.py`

- [ ] **Step 1: Write a failing smoke contract requiring `core_only` to run the repository example and check forbidden distributions**
- [ ] **Step 2: Run `uv run python scripts/test-suite.py tdd tests/test_python_distribution_smoke.py` and verify RED**
- [ ] **Step 3: Reuse the example in the existing offline wheel runner without duplicating install or environment policy**
- [ ] **Step 4: Run the smoke test and verify GREEN**

### Task 5: Close The Extraction-Readiness Slice

**Files:**
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/superpowers/README.md`
- Move: this plan into `docs/archive/agent-platform-extraction-readiness/`

- [ ] **Step 1: Run focused tests, architecture guards, full regular tests, lint, and six-wheel build/check/smoke**
- [ ] **Step 2: Replace current status and roadmap state in place while keeping physical migration out of scope**
- [ ] **Step 3: Update durable ownership, create the archive index, move this plan, and remove it from the active slice index**
