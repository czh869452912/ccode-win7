# Pi/T3 Follow-Up Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Each slice must start with focused failing checks, then implementation, then focused verification, then source-of-truth doc synchronization.

**Goal:** Remove the remaining pre-release compatibility paths and patch-shaped joins after the recent Agent Core and GUI cleanup, while keeping Windows 7, offline deployment, Python 3.8, and the default C/C++ workflow intact.

**Architecture:** Agent Core keeps the Pi-like shape: small session facade, explicit AgentLoop/AgentKernel/AgentExtensionHost boundaries, reducer-backed durable state, and no hidden compatibility shims. GUI keeps moving toward T3-style focused runtime modules and a single session bootstrap/history contract. The plan is deletion-oriented because the product has not shipped and old internal logs do not need compatibility support.

**Tech Stack:** Python 3.8, FastAPI/PyWebView GUI backend, React/Vite GUI webapp, pytest, Node helper tests, bundled offline runtime assets.

## Ground Rules

- Do not add old-log adapters, hidden route aliases, compatibility fields, or migration shims.
- Do not introduce Docker, WSL, VS Code, online services, runtime dependency installation, or Python 3.9+ syntax.
- Treat `transcript.jsonl`, `Session`/`session.turns`, `SessionHistoryAssembler`, and `GET /api/sessions/{id}/bootstrap` as the only session-history line.
- Treat `AgentLoop`, `AgentToolActionService`, `AgentExtensionHost`, and reducer read models as the official Agent Core boundaries.
- Keep GUI runtime state in the focused modules named in `AGENTS.md`; avoid root-level parallel reducer fields.
- When webapp source changes, rebuild `src/embedagent/frontend/gui/static/`.

## Current Debt Map

- Prompt layer still recognizes the legacy `harness_prompt` kind even though new workflow prompt units must use `workflow_prompt`.
- `QueryEngine` still exposes private loop/completion compatibility wrappers used by tests, which weakens the split between facade and `AgentLoop`.
- GUI backend still contains `_ActiveCoreProxy` and `self.core` compatibility routing, so route handlers do not clearly depend on app/session services.
- `GET /api/sessions/{id}/events`, `_timeline_event`, and related tests keep a timeline-shaped vocabulary alive even though the route is only a bootstrap reload signal.
- GUI frontend still derives session runtime through projection helpers with old timeline terminology, then renders T3-like views from that intermediate shape.
- Some reducer tests still validate legacy compact-boundary payloads; active product tests should validate current v2 event contracts only.
- Extension capability projection still carries a field named `legacy_projection`, which is now misleading product vocabulary.
- Validation scripts and manual fixtures still mention old `code`/`todo` vocabulary in active paths, even where production code has moved to `build`/`tasks`.

## Recommended Sequence

Run the slices in this order:

1. S01, S02, and S03 are bounded cleanup slices with clear tests.
2. S04 removes timeline/event route vocabulary before frontend protocol work.
3. S05 and S06 are the main GUI architecture alignment program.
4. S07 and S08 finish stale vocabulary and reducer/test cleanup after the larger contracts settle.

## S01 - Delete `harness_prompt` Prompt Compatibility

**Risk:** Medium  
**Depends on:** current `max_turns` cleanup already landed  
**Target shape:** `workflow_prompt` is the only prompt kind accepted for newly appended workflow package prompt units.

- [ ] Add or adjust a focused test proving prompt assembly only accepts/deduplicates `workflow_prompt`.
- [ ] Replace tests that assert legacy `harness_prompt` acceptance with current-contract tests.
- [ ] Remove `harness_prompt` from `src/embedagent/prompt_assembly_service.py`.
- [ ] Remove active-doc statements that say `harness_prompt` remains recognized for compatibility.
- [ ] Keep archive docs untouched unless they are imported by active docs.

**Likely files:**

- `src/embedagent/prompt_assembly_service.py`
- `tests/test_query_engine_refactor.py`
- `tests/test_workflow_extensions.py`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/frontend-protocol.md`

**Verification:**

```bash
uv run pytest tests/test_query_engine_refactor.py -k workflow_prompt -q
uv run pytest tests/test_workflow_extensions.py -k prompt -q
rg -n "harness_prompt" src tests docs -g "!docs/archive/**"
```

**Done when:** active source no longer accepts `harness_prompt`, tests target `workflow_prompt`, and active docs no longer describe the old prompt kind as supported.

## S02 - Remove QueryEngine Loop Compatibility Wrappers

**Risk:** Medium  
**Depends on:** S01 optional, but recommended first  
**Target shape:** `QueryEngine` remains the session facade; `AgentLoop` owns loop continuation and completion policy.

- [ ] Add a focused guard that `QueryEngine` no longer exposes `_run_loop` or `_is_completion_signal`.
- [ ] Move completion-signal tests to the official completion policy or `AgentLoop` boundary instead of private `QueryEngine` methods.
- [ ] Replace test setup that reaches into `QueryEngine._run_loop` with session-facade level behavior tests.
- [ ] Delete the wrapper methods and any comments describing them as compatibility for old loop wiring.
- [ ] Confirm `QueryEngine` still delegates the normal turn flow through `AgentLoop`.

**Likely files:**

- `src/embedagent/query_engine.py`
- `src/embedagent/agent_loop.py`
- `tests/test_harness_completion_signal.py`
- `tests/test_query_engine_refactor.py`
- `tests/test_agent_loop.py`

**Verification:**

```bash
uv run pytest tests/test_harness_completion_signal.py -q
uv run pytest tests/test_query_engine_refactor.py -k "loop or completion" -q
uv run pytest tests/test_agent_loop.py -q
rg -n "_run_loop|_is_completion_signal|old loop wiring|Compatibility wrapper" src tests -g "!docs/archive/**"
```

**Done when:** no product or test path calls private `QueryEngine` loop wrappers and loop policy is tested at its owning boundary.

## S03 - Replace GUI Backend `_ActiveCoreProxy` With Explicit Services

**Risk:** Medium  
**Depends on:** none  
**Target shape:** GUI route handlers call explicit app/session services; no compatibility proxy pretends to be a core object.

- [ ] Add route/service tests that exercise the affected operations without touching `backend.core`.
- [ ] Inventory current `self.core` uses in `src/embedagent/frontend/gui/backend/server.py`.
- [ ] Replace each route use with explicit `GUIAppHost`, session lifecycle facade, or adapter accessor calls.
- [ ] Delete `_ActiveCoreProxy` and the `self.core = _ActiveCoreProxy(self)` assignment.
- [ ] Update tests that currently monkeypatch or assert through `backend.core`.

**Likely files:**

- `src/embedagent/frontend/gui/backend/server.py`
- `src/embedagent/frontend/gui/backend/app_host.py`
- `tests/test_gui_runtime.py`
- `tests/test_gui_backend_api.py`
- `tests/test_gui_app_host.py`

**Verification:**

```bash
uv run pytest tests/test_gui_runtime.py tests/test_gui_backend_api.py tests/test_gui_app_host.py -q
rg -n "_ActiveCoreProxy|self\\.core|Compatibility for existing route code" src/embedagent/frontend/gui/backend tests -g "!docs/archive/**"
```

**Done when:** backend routes have explicit service dependencies and the compatibility proxy is gone.

## S04 - Delete Timeline/Event Reload Compatibility Vocabulary

**Risk:** Medium-high  
**Depends on:** S03 recommended  
**Target shape:** GUI session activation uses bootstrap and live WebSocket state; any reload-needed signal is transport vocabulary, not history/timeline vocabulary.

- [ ] Decide the final active contract: either remove `GET /api/sessions/{id}/events` entirely or replace it with a clearly named reload-state route used only by transport recovery.
- [ ] Add backend tests that route lists and response payloads do not expose `/events` as a session-history API.
- [ ] Rename or delete `_timeline_event` in GUI live payload helpers.
- [ ] Update frontend transport code/tests to consume bootstrap reload state without timeline terms.
- [ ] Update `docs/frontend-protocol.md` and `AGENTS.md` so the active contract does not preserve the old route name.

**Likely files:**

- `src/embedagent/frontend/gui/backend/server.py`
- `src/embedagent/frontend/gui/backend/session_events.py`
- `src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js`
- `src/embedagent/frontend/gui/webapp/test/session-transport-controller.test.mjs`
- `tests/test_gui_runtime.py`
- `tests/test_gui_backend_api.py`
- `docs/frontend-protocol.md`
- `AGENTS.md`

**Verification:**

```bash
uv run pytest tests/test_gui_runtime.py tests/test_gui_backend_api.py -q
cd src/embedagent/frontend/gui/webapp && npm test
rg -n "/events|_timeline_event|timeline reload|timeline-backed" src tests docs -g "!docs/archive/**"
```

**Done when:** active GUI code no longer uses timeline/event route naming for bootstrap reload or live display state.

## S05 - Introduce A T3-Style Session Activity Read Model

**Risk:** High  
**Depends on:** S04  
**Target shape:** Backend bootstrap returns a T3-like session runtime projection assembled from official transcript/session state, not from a frontend timeline reconstruction layer.

- [ ] Define the current frontend read model names for thread list, active session, messages, operations, tool calls, and workflow tasks.
- [ ] Extend `SessionHistoryAssembler` or a nearby GUI projection module to emit a compact activity/message model directly from official history.
- [ ] Keep operation state reducer-backed; do not infer durable operations from `step_started`, `tool_call`, or live display events.
- [ ] Update protocol tests so `GET /api/sessions/{id}/bootstrap` is the only activation payload the frontend needs.
- [ ] Update active docs with the read-model shape and ownership boundaries.

**Likely files:**

- `src/embedagent/session_history_assembler.py`
- `src/embedagent/protocol/`
- `src/embedagent/frontend/gui/backend/server.py`
- `tests/test_session_history_assembler.py`
- `tests/test_gui_backend_api.py`
- `docs/frontend-protocol.md`
- `docs/overall-solution-architecture.md`

**Verification:**

```bash
uv run pytest tests/test_session_history_assembler.py tests/test_gui_backend_api.py -q
uv run pytest tests/ -m "not slow and not gui" -q
```

**Done when:** bootstrap carries the frontend session activity model directly from official backend projections and no frontend-only timeline reconstruction is needed for activation.

## S06 - Replace Frontend Timeline Projection With Focused Runtime Modules

**Risk:** High  
**Depends on:** S05  
**Target shape:** GUI webapp state follows focused T3-style modules: thread state, transport state, run-output state, composer state, terminal state, and workbench state.

- [ ] Add reducer tests for activating a session from the new bootstrap activity model.
- [ ] Replace `projectSessionRuntime` use in `App.jsx` with focused session-runtime activation actions.
- [ ] Remove `timelineFromEvents` and `summarizeTimelineProjection` from product runtime helpers.
- [ ] Remove or redesign Inspector projection diagnostics so product UI does not expose old timeline-projection internals.
- [ ] Ensure run-output logs remain GUI-local display state and never become session history.
- [ ] Rebuild GUI static assets after source changes.

**Likely files:**

- `src/embedagent/frontend/gui/webapp/src/App.jsx`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/thread-state.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/run-output-state.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
- `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- `src/embedagent/frontend/gui/webapp/test/*.mjs`
- `src/embedagent/frontend/gui/static/`

**Verification:**

```bash
cd src/embedagent/frontend/gui/webapp && npm test
cd src/embedagent/frontend/gui/webapp && npm run build
rg -n "projectSessionRuntime|timelineFromEvents|summarizeTimelineProjection|timeline projection" src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test
```

**Done when:** frontend activation no longer builds T3 views through legacy timeline projection helpers, and generated static assets reflect the new source.

## S07 - Remove Legacy Reducer Fixtures And Old Vocabulary From Active Validation

**Risk:** Low-medium  
**Depends on:** S01 through S06 preferred  
**Target shape:** Active tests and validation scripts validate current event/schema vocabulary only.

- [ ] Replace legacy compact-boundary payload tests with current v1/v2 reducer contract tests that match active transcript events.
- [ ] Audit active scripts for `code`, `todo`, `todos`, legacy mode names, and old task vocabulary.
- [ ] Update or archive validation scripts that only exist to protect old pre-release shapes.
- [ ] Keep negative tests that prove removed APIs stay removed, but rename them to current architecture language.

**Likely files:**

- `tests/test_compaction_state.py`
- `scripts/validate-phase5.py`
- `scripts/validate-phase6.py`
- `tests/manual/playwright_example.py`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

**Verification:**

```bash
uv run pytest tests/test_compaction_state.py -q
uv run --locked python scripts/lint.py
rg -n "\\bcode\\b|\\btodo\\b|\\btodos\\b|legacy compact|legacy payload" scripts tests src docs -g "!docs/archive/**"
```

**Done when:** active tests/scripts speak current product vocabulary unless they are explicit removal guards.

## S08 - Rename Or Remove Extension `legacy_projection`

**Risk:** Medium  
**Depends on:** S05 optional  
**Target shape:** extension/capability diagnostics expose current read-model metadata without a field whose name implies old compatibility.

- [ ] Identify all producers and consumers of `legacy_projection`.
- [ ] Replace it with a current name if the data is still useful, such as `capability_projection` or explicit diagnostic fields.
- [ ] Remove it entirely if it only preserves old capability payload shape.
- [ ] Update capability registry and extension tests to assert provenance, permissions, source metadata, and visibility through official boundaries.

**Likely files:**

- `src/embedagent/extensions.py`
- `src/embedagent/capability_registry.py`
- `tests/test_extensions.py`
- `tests/test_capability_registry.py`
- `docs/tool-contracts.md`
- `docs/overall-solution-architecture.md`

**Verification:**

```bash
uv run pytest tests/test_extensions.py tests/test_capability_registry.py -q
rg -n "legacy_projection" src tests docs -g "!docs/archive/**"
```

**Done when:** extension/capability projections use current vocabulary and no active caller depends on `legacy_projection`.

## Cross-Slice Final Gate

Run this after each high-risk slice and after the full program:

```bash
uv run pytest tests/ -m "not slow and not gui" -q
uv run --locked python scripts/lint.py
git diff --check
```

Run this when GUI webapp source changed:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
cd src/embedagent/frontend/gui/webapp && npm run build
```

Run this before claiming the architecture program is complete:

```bash
rg -n "harness_prompt|_ActiveCoreProxy|_timeline_event|/events|projectSessionRuntime|timelineFromEvents|summarizeTimelineProjection|legacy_projection|_run_loop|_is_completion_signal" src tests docs -g "!docs/archive/**"
```

Every remaining match must be either removed, moved to archive material, or documented as an explicit negative guard proving the old path is absent.
