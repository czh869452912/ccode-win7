# Phase H Runtime Configuration Reducer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make active runtime configuration replayable from transcript events and consumable by turn snapshots.

**Architecture:** Add a focused `RuntimeConfigReducer` beside the existing operation reducer. Adapter paths emit and project safe runtime configuration state, while provider requests consume reducer-backed metadata without moving activation, execution, or permission decisions out of their current owners.

**Tech Stack:** Python 3.8, dataclasses, pytest, existing transcript store/session snapshot infrastructure.

---

## Files

- Create: `src/embedagent/runtime_config.py`
- Create: `tests/test_runtime_config.py`
- Modify: `src/embedagent/session_runtime.py`
- Modify: `src/embedagent/session_projector.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_local_resources.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`

## Task 1: Reducer Foundation

- [ ] Write failing tests in `tests/test_runtime_config.py` for `runtime_configured`, `resource_reloaded`, ignored `resource_discovered`, and provider snapshot records.
- [ ] Run `uv run pytest tests/test_runtime_config.py -v` and confirm import failure.
- [ ] Implement `RuntimeConfigReducer`, `RuntimeConfigState`, `ResourceRevision`, and `ProviderRequestSnapshotRecord`.
- [ ] Run `uv run pytest tests/test_runtime_config.py -v` and confirm pass.

## Task 2: Adapter Projection

- [ ] Add `runtime_config` to `ManagedSession`.
- [ ] Write failing tests that `InProcessAdapter.reload_resources()` advances reducer-backed runtime config and session snapshots expose it.
- [ ] Implement adapter helper methods to emit `runtime_configured`, reduce transcript events, and update `state.runtime_config`.
- [ ] Run `uv run pytest tests/test_local_resources.py tests/test_inprocess_adapter_frontend_api.py -v`.

## Task 3: Provider Snapshot Integration

- [ ] Extend query engine tests so provider metadata includes reducer-backed `runtime_config.resource_revision` and no unsafe fields.
- [ ] Add optional `runtime_config_provider` injection to `QueryEngine`.
- [ ] Use reducer state when building model profile and resource revision metadata for `TurnSnapshot`.
- [ ] Run `uv run pytest tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_provider_request_consumes_turn_snapshot_and_records_safe_metadata -v`.

## Task 4: Documentation And Verification

- [ ] Update active source-of-truth docs with Phase H semantics.
- [ ] Run focused tests: `uv run pytest tests/test_runtime_config.py tests/test_turn_snapshot.py tests/test_capability_registry.py tests/test_local_resources.py -v`.
- [ ] Run harness tests: `uv run pytest tests/ -m harness -v`.
- [ ] Run fast suite: `uv run pytest tests/ -m "not slow and not gui" -v`.
- [ ] Run lint: `uv run ruff check src/ tests/` and `uv run black --check src/ tests/`.
- [ ] Commit Phase H changes.
