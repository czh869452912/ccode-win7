# Pi/T3 Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the next layer of pre-release architecture drift that conflicts with the Pi-inspired Agent Core and T3-style GUI/runtime contracts.

**Architecture:** This cleanup favors deletion and contract alignment over compatibility shims. Agent Core behavior must route through the documented mode registry, extension host, tool runtime schema projection, and transcript/bootstrap reducers; GUI work must continue moving state ownership into focused T3-style modules rather than expanding root reducer glue.

**Tech Stack:** Python 3.8, pytest, React/Vite source under `src/embedagent/frontend/gui/webapp/src`, local/offline Windows 7-compatible runtime only.

---

### Task 1: Align Pre-Release Default Configuration

**Files:**
- Modify: `config/config.json.template`
- Modify: `src/embedagent/config.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Test: `tests/test_config.py`
- Test: `tests/test_backward_compatibility.py`

- [x] **Step 1: Write failing config-template test**

```python
def test_config_template_uses_current_architecture_defaults(self):
    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "config",
        "config.json.template",
    )
    with open(template_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    self.assertIsNone(payload.get("max_turns"))
    self.assertEqual(payload.get("default_mode"), "explore")
```

- [x] **Step 2: Write failing protocol-fallback test**

```python
def test_core_adapter_snapshot_falls_back_to_default_mode(self):
    from embedagent.core.adapter import _session_snapshot_from_dict
    from embedagent.modes import DEFAULT_MODE

    snapshot = _session_snapshot_from_dict({})

    assert snapshot.current_mode == DEFAULT_MODE
```

- [x] **Step 3: Verify the tests fail before implementation**

Run: `uv run pytest tests/test_config.py::TestAppConfigDefaults::test_config_template_uses_current_architecture_defaults tests/test_backward_compatibility.py::TestPublicImports::test_core_adapter_snapshot_falls_back_to_default_mode -v`

Expected: FAIL because the template still uses `code`/`8` and the adapter fallback still uses `build`.

- [x] **Step 4: Implement the minimal alignment**

Change `config/config.json.template` to:

```json
{
  "_comment": "EmbedAgent 内网环境配置文件模板 - 复制到 ~/.embedagent/config.json 并修改",
  "base_url": "http://192.168.1.100:8000/v1",
  "api_key": "sk-internal",
  "model": "qwen3.5-coder",
  "timeout": 120,
  "max_context_tokens": 32000,
  "reserve_output_tokens": 3000,
  "chars_per_token": 3.0,
  "max_turns": null,
  "default_mode": "explore"
}
```

Import `DEFAULT_MODE` in `src/embedagent/core/adapter.py` and use it in `_session_snapshot_from_dict`. Update the config docstring example from `build` to `explore`. Set GUI initial `maxTurns` to `null`.

- [x] **Step 5: Verify Task 1 passes**

Run: `uv run pytest tests/test_config.py::TestAppConfigDefaults::test_config_template_uses_current_architecture_defaults tests/test_backward_compatibility.py::TestPublicImports::test_core_adapter_snapshot_falls_back_to_default_mode -v`

Expected: PASS.

### Task 2: Delete Misleading Mode-Aware Tool Runtime Shortcut

**Files:**
- Modify: `src/embedagent/tools/runtime.py`
- Test: `tests/test_tools_package.py`

- [x] **Step 1: Write failing boundary test**

```python
def test_mode_aware_execution_shortcut_removed(self):
    self.assertFalse(hasattr(ToolRuntime, "execute_for_mode"))
```

- [x] **Step 2: Verify the boundary test fails before implementation**

Run: `uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute::test_mode_aware_execution_shortcut_removed -v`

Expected: FAIL while `ToolRuntime.execute_for_mode` still exists.

- [x] **Step 3: Delete the shortcut**

Remove `ToolRuntime.execute_for_mode`. Mode/tool activation remains owned by `ExtensionManager`/`AgentExtensionHost`; `ToolRuntime.schemas_for(...)` stays the schema projection boundary, and execution remains the low-level runtime dispatch behind `AgentToolActionService`.

- [x] **Step 4: Verify Task 2 passes**

Run: `uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute::test_mode_aware_execution_shortcut_removed -v`

Expected: PASS.

### Task 3: Keep the Next Cleanup Slices Explicit

**Files:**
- Modify later: `src/embedagent/inprocess_adapter.py`
- Modify later: `src/embedagent/query_engine.py`
- Modify later: `src/embedagent/session_runtime.py`
- Modify later: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify later: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify later: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Modify later: `src/embedagent/frontend/gui/backend/server.py`

- [x] **Step 1: Treat the remaining debt as separate slices**

Do not patch around the large files. Extract activation/resume/bootstrap services from `InProcessAdapter`, keep `QueryEngine` as session facade rather than hook dispatcher, move GUI live event folding into typed thread-runtime reducers, and split GUI backend route groups by hosted surface.

- [x] **Step 2: Add tests before each extraction**

For each slice, write regression tests against the intended boundary first. Prefer tests that assert removed paths stay absent, because this project is pre-release and should delete stale compatibility scaffolding.

- [x] **Step 3: Verify the focused cleanup slice before broad CI**

Run: `uv run pytest tests/test_config.py tests/test_backward_compatibility.py tests/test_tools_package.py -v`

Expected: PASS.

Run: `uv run --locked python scripts/lint.py`

Expected: exit code 0.

### Task 4: Collapse the Pre-Release Turn Runner Wrapper

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_backward_compatibility.py`

- [x] **Step 1: Write failing single-entrypoint boundary test**

Assert `InProcessAdapter` still has `_run_turn` but no longer exposes `_run_turn_v2`.

- [x] **Step 2: Verify the boundary test fails before implementation**

Run: `uv run pytest tests/test_backward_compatibility.py::TestInProcessAdapterCompatibility::test_turn_runner_has_single_internal_entrypoint -v`

Expected: FAIL while `_run_turn_v2` still exists.

- [x] **Step 3: Rename the implementation to the official single entrypoint**

Move the real turn-runner implementation into `_run_turn`, update permission/user-input resume paths to use keyword arguments, and use keyword `threading.Thread(..., kwargs=...)` for the async submit path so optional continuation parameters are explicit.

- [x] **Step 4: Verify Task 4 passes**

Run: `uv run pytest tests/test_backward_compatibility.py::TestInProcessAdapterCompatibility::test_turn_runner_has_single_internal_entrypoint tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_resume_session_restores_waiting_permission_from_transcript tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_cancel_session_does_not_mark_idle_before_worker_exits -v`

Expected: PASS.

### Task 5: Move Resource Slash Command Specs Out of the Adapter

**Files:**
- Modify: `src/embedagent/slash_commands.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_capability_registry.py`
- Test: `tests/test_backward_compatibility.py`

- [x] **Step 1: Write failing resource command projection test**

Assert `resource_command_specs(resources)` projects visible local skills and prompts into slash command specs in one place.

- [x] **Step 2: Write failing adapter boundary test**

Assert `InProcessAdapter` no longer exposes `_resource_command_specs` or `_skill_command_specs`.

- [x] **Step 3: Implement the command registry boundary**

Add `resource_command_specs(resources)` to `slash_commands.py` and make adapter capability/help projection consume it directly.

- [x] **Step 4: Verify Task 5 passes**

Run: `uv run pytest tests/test_capability_registry.py::test_resource_command_specs_project_visible_skills_and_prompts tests/test_backward_compatibility.py::TestInProcessAdapterCompatibility::test_resource_command_specs_live_outside_adapter -v`

Expected: PASS.

### Task 6: Move GUI Event Log State Into Session Runtime

**Files:**
- Add: `src/embedagent/frontend/gui/webapp/src/session-runtime/event-log-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
- Test: `src/embedagent/frontend/gui/webapp/test/event-log-state.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [x] **Step 1: Write failing event-log reducer test**

Assert event log creation, append, 200-entry cap, session activation reset, and workspace reset live in a focused session-runtime module.

- [x] **Step 2: Verify the test fails before implementation**

Run: `npm test` under `src/embedagent/frontend/gui/webapp`.

Expected: FAIL while `session-runtime/event-log-state.js` does not exist.

- [x] **Step 3: Implement the focused event-log state module**

Add `createEventLogState`, `readEventLogEntries`, and `reduceEventLogState`; wire `store.js` and `app-workspaces.js` to consume it instead of hard-coded root reducer event-log rules.

- [x] **Step 4: Verify Task 6 passes**

Run: `npm test` under `src/embedagent/frontend/gui/webapp`.

Expected: PASS.

### Task 7: Move Transport Replay Projection Out of the Runtime Projector

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Test: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`

- [x] **Step 1: Write failing transport view test**

Assert `projectTransportView({ snapshot, eventLog })` owns replay-state normalization, connection state, and last applied sequence projection.

- [x] **Step 2: Verify the test fails before implementation**

Run: `npm test` under `src/embedagent/frontend/gui/webapp`.

Expected: FAIL while `event-log.js` does not export `projectTransportView`.

- [x] **Step 3: Move transport replay projection to event-log state**

Export `projectTransportView` from `event-log.js`, make `projectSessionRuntime` consume it, and delete duplicated replay-state normalization from `projector.js`.

- [x] **Step 4: Verify Task 7 passes**

Run: `npm test` under `src/embedagent/frontend/gui/webapp`.

Expected: PASS.
