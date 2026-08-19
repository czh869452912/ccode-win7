# Phase 4 C++ Isolated Wheel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the selected `cpp-desktop` bundle exports and installs the Core/Protocol/C++ runtime closure in an isolated wheel-only environment without Host/Product leakage.

**Architecture:** The compiled `bundle-plan.json` is the only closure input. Build/check/smoke scripts consume its application-scoped runtime IDs and reject missing or extra distributions. The probe runs with network resolution disabled and imports only the selected Core/Protocol/C++ package roots.

**Tech Stack:** Python 3.8, existing distribution builder/checker/smoke scripts, wheel metadata inspection, pytest temporary export fixtures, offline runtime contract.

---

### Task 1: Define The Isolated Proof Contract

**Files:**
- Inspect: `scripts/build-python-distributions.py`, `scripts/check-python-distributions.py`, `scripts/smoke-python-distributions.py`, `scripts/offline-runtime-contract.json`, `src/embedagent/bundle_policy.py`
- Test: `tests/test_phase4_cpp_isolated_wheel.py`

- [ ] Add failing tests that a `cpp-desktop` plan carries application-scoped runtime requirements and that a wheel set missing Core/Protocol/C++ or containing Host/Product leakage is rejected.
- [ ] Add a temporary wheelhouse fixture proving network-disabled installation and import isolation.

### Task 2: Enforce Plan-Bound Wheel Closure

**Files:**
- Modify: `scripts/build-python-distributions.py`
- Modify: `scripts/check-python-distributions.py`
- Modify: `scripts/smoke-python-distributions.py`
- Modify only if required: `src/embedagent/bundle_policy.py`, `scripts/offline-runtime-contract.json`

- [ ] Read runtime distribution IDs from the selected plan rather than a fixed list.
- [ ] Validate exact wheel identity, dependency direction, and selected C++ registration entry.
- [ ] Make the isolated probe fail closed when the plan is missing runtime requirements or when an unselected product/Host package is importable.
- [ ] Run focused export/check/smoke tests with network disabled.

### Task 3: Add Release Evidence And Documentation

**Files:**
- Modify: `tests/test_python_distribution_contract.py`, `tests/test_packaging_control_plane.py`, `tests/test_bundle_runtime_policy.py`
- Modify: `docs/product/packaging-and-deployment.md`, `docs/current-status.md`, `docs/implementation-roadmap.md`

- [ ] Add a deterministic test command and evidence shape for the isolated C++ wheel proof.
- [ ] Document that local proof is a prerequisite, not a substitute for Windows 7 clean-machine acceptance.
- [ ] Run packaging, architecture, full regular, lint, and documentation navigation gates.

### Task 4: Commit

- [ ] Commit only isolated wheel proof changes with message `test: prove cpp isolated wheel closure`.

