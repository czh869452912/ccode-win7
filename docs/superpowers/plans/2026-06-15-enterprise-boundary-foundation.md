# Enterprise Boundary Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add code-level guardrails for optional enterprise/intranet tools and safe telemetry envelopes without adding real network integrations.

**Architecture:** Permission categories are centralized in `embedagent.permissions` and reused by tool runtime, project extension loading, and self-extension authoring. `embedagent.telemetry` provides local-only safe envelope construction for future sinks.

**Tech Stack:** Python 3.8, stdlib only, pytest.

---

### Task 1: Permission And Manifest Categories

**Files:**
- Modify: `src/embedagent/permissions.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/project_extensions.py`
- Modify: `src/embedagent/self_extension_authoring.py`
- Test: `tests/test_permissions.py`
- Test: `tests/test_dynamic_tool_registration.py`
- Test: `tests/test_project_extensions.py`
- Test: `tests/test_self_extension_authoring.py`

- [ ] Write failing tests for `network` and `telemetry` category behavior.
- [ ] Run targeted tests and verify the failures are category rejection/default behavior failures.
- [ ] Centralize official categories and update runtime/manifest/authoring imports.
- [ ] Run targeted tests and verify they pass.

### Task 2: Safe Telemetry Envelope

**Files:**
- Create: `src/embedagent/telemetry.py`
- Test: `tests/test_telemetry.py`

- [ ] Write failing tests for safe field preservation and sensitive field redaction.
- [ ] Run targeted tests and verify `embedagent.telemetry` is missing.
- [ ] Implement minimal local-only envelope builder.
- [ ] Run targeted tests and verify they pass.

### Task 3: Documentation Sync And Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/design-change-log.md`

- [ ] Update docs from planned boundary to implemented foundation.
- [ ] Run `uv run pytest` targeted tests with `--basetemp build/pytest-tmp`.
- [ ] Run fast subset with `--ignore=tests/test_hygn_03_warning_cleanup.py --basetemp build/pytest-tmp`.
- [ ] Commit the implementation.
