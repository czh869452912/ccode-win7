# GUI App Runtime Controller Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract GUI-only socket message interpretation and visual debug fixtures from `App.jsx` into a small `app-runtime` boundary while keeping Agent Core and backend contracts unchanged.

**Architecture:** Add pure frontend modules under `webapp/src/app-runtime/`. `socket-message-effects.js` derives plain `{ actions, eventLogEntries, loaderRequests }` descriptors from WebSocket messages; `App.jsx` executes those descriptors with existing dispatch, session event-log, and loader functions. `visual-debug-fixtures.js` owns deterministic dev-only fixture actions and gated hook installation.

**Tech Stack:** React 18, plain JavaScript ES modules, existing Node webapp tests, existing Vite build, existing Python GUI backend tests, existing Playwright visual debug harness.

---

## File Structure

- Create `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - Pure WebSocket message-to-effect derivation.
  - Imports only pure webapp helpers: `normalizeSessionPayload`, `makeEventId`, `normalizeAppBootstrap`, and `createDiffSurfaceState`.
  - No React, DOM, WebSocket, fetch, loader calls, backend imports, or Agent Core imports.
- Create `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - Deterministic fixture action builders.
  - Gated `installVisualDebugFixtures(...)` helper for `window.__EMBEDAGENT_VISUAL_DEBUG__`.
  - No backend calls and no session-history writes.
- Create `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
  - Unit tests for descriptor shape and representative message mappings.
- Create `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
  - Unit tests for fixture action contracts and visual debug hook gating.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Import and run the two new tests.
  - Move source-level fixture assertions from `App.jsx` to the new `app-runtime` source files.
  - Keep source-level assertions that `App.jsx` wires the runtime boundary.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Import the two `app-runtime` modules.
  - Replace inline visual fixture builders with `installVisualDebugFixtures(...)`.
  - Replace the long `handleSocketMessage(...)` branch chain with `deriveSocketMessageEffects(...)` and a local descriptor executor.
  - Keep existing HTTP loader functions, WebSocket lifecycle, terminal handlers, source-control handlers, and rendering composition in `App.jsx` for this slice.
- Modify docs after implementation:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`

## Constraints For Every Task

- Do not modify Agent Core, provider code, tool execution, permission policy, workflow packages, transcript reducers, operation reducers, runtime reducers, compaction reducers, or recovery reducers.
- Do not add npm or Python dependencies.
- Do not change backend HTTP or WebSocket contracts.
- Do not move terminal execution, source-control execution, or file preview behavior into Agent Core.
- Keep all new descriptors private to the webapp source tree.
- Keep `App.jsx` as the only executor of loader requests in this slice.
- Keep visual debug fixtures gated behind `visual_debug=1`.
- Keep JavaScript syntax compatible with the existing webapp build.

## Task 1: Add Failing Socket Effect Tests

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Create the failing socket effect test file**

Create `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs` with this content:

```js
import assert from "node:assert/strict";

import {
  LOADER_REQUESTS,
  deriveSocketMessageEffects,
} from "../src/app-runtime/socket-message-effects.js";

function makeDeterministicIdFactory() {
  const counts = new Map();
  return (prefix) => {
    const next = (counts.get(prefix) || 0) + 1;
    counts.set(prefix, next);
    return `${prefix}-${next}`;
  };
}

function derive(type, data, options = {}) {
  return deriveSocketMessageEffects({
    type,
    data,
    currentSessionId: options.currentSessionId || "sess-active",
    sessionEventLog: options.sessionEventLog || { lastAppliedSeq: 4 },
    makeId: options.makeId || makeDeterministicIdFactory(),
    nowIso: options.nowIso || (() => "2026-06-18T00:00:00.000Z"),
  });
}

export function runSocketMessageEffectsTests() {
  const workspaceActive = derive("workspace_changed", {
    has_active_workspace: true,
    active_workspace: { id: "ws-1", path: "D:/work/demo", label: "demo" },
    workspaces: [{ id: "ws-1", path: "D:/work/demo", label: "demo" }],
  });
  assert.equal(workspaceActive.actions[0].type, "workspace_switched");
  assert.equal(workspaceActive.actions[0].bootstrap.hasActiveWorkspace, true);
  assert.deepEqual(workspaceActive.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA, sessionId: "", assumeWorkspace: true },
  ]);

  const workspaceInactive = derive("workspace_changed", { has_active_workspace: false });
  assert.equal(workspaceInactive.actions[0].type, "workspace_switched");
  assert.equal(workspaceInactive.actions[1].type, "source_control_reset");
  assert.deepEqual(workspaceInactive.loaderRequests, []);

  const status = derive("session_status", {
    session_id: "sess-1",
    status: "running",
    current_mode: "build",
    timeline_replay_status: "degraded",
  });
  assert.equal(status.actions[0].type, "session_snapshot");
  assert.equal(status.actions[0].snapshot.session_id, "sess-1");
  assert.equal(status.actions[0].replayStatePatch, "degraded");
  assert.deepEqual(status.actions[1], { type: "log_event", label: "session_status", detail: "running" });
  assert.deepEqual(status.loaderRequests, [{ name: LOADER_REQUESTS.LOAD_SESSIONS }]);

  const turnEvent = derive("session_event", {
    event_id: "evt-turn",
    seq: 5,
    event_kind: "turn.started",
    payload: { turn_id: "turn-1", user_text: "inspect parser" },
  });
  assert.equal(turnEvent.eventLogEntries.length, 1);
  assert.equal(turnEvent.eventLogEntries[0].event_id, "evt-turn");
  assert.deepEqual(turnEvent.actions, [
    { type: "turn_started", turnId: "turn-1", userText: "inspect parser" },
  ]);

  const transitionEvent = derive("session_event", {
    event_id: "evt-transition",
    seq: 5,
    event_kind: "transition.recorded",
    payload: {
      termination_reason: "max_turns",
      display_reason: "max turns reached",
      message: "Stopped after max turns.",
      turns_used: 8,
      max_turns: 8,
    },
  });
  assert.equal(transitionEvent.actions[0].type, "turn_ended");
  assert.equal(transitionEvent.actions[0].terminationDisplayReason, "max turns reached");
  assert.equal(transitionEvent.actions[0].turnsUsed, 8);

  const streamDelta = derive("stream_delta", {
    text: "hello",
    turn_id: "turn-1",
    step_id: "step-1",
    step_index: 2,
  });
  assert.deepEqual(streamDelta.actions, [
    {
      type: "assistant_delta",
      text: "hello",
      turnId: "turn-1",
      stepId: "step-1",
      stepIndex: 2,
    },
  ]);

  const toolFinish = derive("tool_finish", {
    call_id: "call-1",
    tool_name: "edit_file",
    tool_label: "Edit File",
    success: true,
    data: { path: "src/main.c" },
    turn_id: "turn-1",
    step_id: "step-1",
    step_index: 1,
  });
  assert.equal(toolFinish.actions[0].type, "tool_finished");
  assert.equal(toolFinish.actions[0].toolName, "edit_file");
  assert.deepEqual(toolFinish.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "." },
  ]);

  const permission = derive("permission_request", {
    permission_id: "perm-1",
    session_id: "sess-active",
    tool_name: "edit_file",
    category: "workspace_write",
    reason: "Allow edit",
    details: { path: "src/main.c" },
    turn_id: "turn-1",
    step_id: "step-2",
    step_index: 2,
  });
  assert.equal(permission.actions[0].type, "permission_request");
  assert.equal(permission.eventLogEntries[0].event_kind, "interaction.created");
  assert.equal(permission.eventLogEntries[0].payload.kind, "permission");
  assert.equal(permission.eventLogEntries[0].seq, 5);
  assert.deepEqual(permission.actions[1], {
    type: "log_event",
    label: "permission_request",
    detail: "Allow edit",
  });

  const userInput = derive("user_input_request", {
    request_id: "input-1",
    session_id: "sess-active",
    tool_name: "ask_user",
    question: "Which parser mode?",
    options: [{ index: 1, text: "Strict" }],
    turn_id: "turn-1",
  });
  assert.equal(userInput.actions[0].type, "user_input_request");
  assert.equal(userInput.eventLogEntries[0].payload.kind, "user_input");
  assert.equal(userInput.eventLogEntries[0].payload.question, "Which parser mode?");

  const commandDiff = derive("command_result", {
    command_name: "diff",
    success: true,
    message: "diff ready",
    data: { diff: "--- a/src/main.c\n+++ b/src/main.c\n@@ -1 +1 @@\n-int a;\n+int b;\n" },
    turn_id: "turn-1",
  });
  assert.equal(commandDiff.actions[0].type, "command_result");
  assert.equal(commandDiff.actions[1].type, "diff_surface_opened");
  assert.equal(commandDiff.actions[1].diffSurface.title, "Git Diff");
  assert.deepEqual(commandDiff.actions[commandDiff.actions.length - 1], {
    type: "log_event",
    label: "command: /diff",
    detail: "ok",
  });

  const commandResume = derive("command_result", {
    command_name: "resume",
    success: true,
    data: { switch_session_id: "sess-next" },
  });
  assert.deepEqual(commandResume.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_SESSION, sessionId: "sess-next" },
  ]);

  const commandWorkspace = derive("command_result", {
    command_name: "workspace",
    success: true,
    data: { active: "D:/work/demo" },
  });
  assert.equal(commandWorkspace.actions[1].type, "preview_loaded");
  assert.equal(commandWorkspace.actions[1].preview.kind, "workspace");

  const commandRecipes = derive("command_result", {
    command_name: "recipes",
    success: true,
    data: { items: [{ id: "build" }] },
  });
  assert.equal(commandRecipes.actions[1].type, "recipes_loaded");
  assert.deepEqual(commandRecipes.actions[2], { type: "set_inspector", value: "run" });

  const finished = derive("session_finished", {
    session_snapshot: { session_id: "sess-active", status: "completed" },
  });
  assert.equal(finished.actions[0].type, "stream_completed");
  assert.equal(finished.actions[1].type, "session_snapshot");
  assert.deepEqual(finished.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_SESSIONS },
    { name: LOADER_REQUESTS.LOAD_TASKS, sessionId: "sess-active" },
  ]);

  const compacted = derive("message", {
    id: "compact-1",
    type: "CONTEXT_COMPACTED",
    content: "Context compacted.",
    metadata: {
      recent_turns: 2,
      summarized_turns: 5,
      approx_tokens_after: 4096,
      turn_id: "turn-1",
      step_id: "step-3",
      step_index: 3,
    },
  });
  assert.equal(compacted.actions[0].type, "context_compacted");
  assert.equal(compacted.actions[0].summarizedTurns, 5);

  const malformed = deriveSocketMessageEffects();
  assert.deepEqual(malformed, { actions: [], eventLogEntries: [], loaderRequests: [] });
  assert.deepEqual(derive("unknown_message", { value: true }), {
    actions: [],
    eventLogEntries: [],
    loaderRequests: [],
  });
}
```

- [ ] **Step 2: Register the failing test in the runner**

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` imports:

```js
import { runSocketMessageEffectsTests } from "./socket-message-effects.test.mjs";
```

Call it near the other frontend runtime tests, after `runWebSocketLifecycleTests()`:

```js
  runWebSocketLifecycleTests();
  runSocketMessageEffectsTests();
  await runVisualDebugRunnerTests();
```

- [ ] **Step 3: Run the test and verify it fails for the right reason**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with a module-not-found error for `../src/app-runtime/socket-message-effects.js`.

- [ ] **Step 4: Commit the failing test**

```bash
git add src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: cover gui socket effect derivation"
```

## Task 2: Implement Socket Message Effect Derivation

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`

- [ ] **Step 1: Add the app runtime directory and module**

Create `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js` with this content:

```js
import { normalizeAppBootstrap } from "../app-workspaces.js";
import { createDiffSurfaceState } from "../session-runtime/diff-model.js";
import { makeEventId, normalizeSessionPayload } from "../state-helpers.js";

export const LOADER_REQUESTS = Object.freeze({
  LOAD_APP_BOOTSTRAP: "load_app_bootstrap",
  LOAD_ACTIVE_WORKSPACE_DATA: "load_active_workspace_data",
  LOAD_SESSIONS: "load_sessions",
  LOAD_SESSION: "load_session",
  LOAD_TASKS: "load_tasks",
  LOAD_ARTIFACTS: "load_artifacts",
  LOAD_PERMISSION_CONTEXT: "load_permission_context",
  LOAD_FILE_CHILDREN: "load_file_children",
});

const FS_REFRESH_TOOLS = new Set(["write_file", "edit_file", "git_commit", "git_reset"]);

function emptyEffects() {
  return { actions: [], eventLogEntries: [], loaderRequests: [] };
}

function eventId(makeId, prefix) {
  return typeof makeId === "function" ? makeId(prefix) : makeEventId(prefix);
}

function nowValue(nowIso) {
  return typeof nowIso === "function" ? nowIso() : new Date().toISOString();
}

function logAction(label, detail = "") {
  return { type: "log_event", label, detail };
}

function nextSeq(sessionEventLog) {
  return Number(sessionEventLog?.lastAppliedSeq || 0) + 1;
}

function currentSession(options) {
  return options.currentSessionId || "";
}

function interactionEvent({ data, options, interactionId, kind, payload }) {
  return {
    session_id: data?.session_id || currentSession(options),
    event_id: interactionId || eventId(options.makeId, "evt"),
    seq: nextSeq(options.sessionEventLog),
    created_at: nowValue(options.nowIso),
    event_kind: "interaction.created",
    payload,
  };
}

function commandResultEffects(data, options) {
  const effects = emptyEffects();
  const commandName = data?.command_name || "";
  effects.actions.push({
    type: "command_result",
    id: eventId(options.makeId, "cmd"),
    commandName,
    success: Boolean(data?.success),
    message: data?.message || "",
    data: data?.data || {},
    turnId: data?.turn_id || "",
    stepId: data?.step_id || "",
    stepIndex: data?.step_index || 0,
  });
  if (commandName === "resume" && data?.data?.switch_session_id) {
    effects.loaderRequests.push({
      name: LOADER_REQUESTS.LOAD_SESSION,
      sessionId: data.data.switch_session_id,
    });
  }
  if (commandName === "diff" && typeof data?.data?.diff === "string" && data.data.diff) {
    effects.actions.push({
      type: "diff_surface_opened",
      diffSurface: createDiffSurfaceState({
        title: "Git Diff",
        diff: data.data.diff,
        source: "command",
        turnId: data?.turn_id || "",
      }),
    });
  }
  if (commandName === "workspace") {
    effects.actions.push({
      type: "preview_loaded",
      preview: {
        kind: "workspace",
        title: "Workspace",
        content: JSON.stringify(data?.data || {}, null, 2),
      },
      inspectorTab: "preview",
    });
  }
  if (commandName === "recipes") {
    effects.actions.push({ type: "recipes_loaded", items: data?.data?.items || [] });
    effects.actions.push({ type: "set_inspector", value: "run" });
  }
  if (commandName === "run") {
    effects.actions.push({ type: "set_inspector", value: "problems" });
  }
  if (commandName === "permissions") {
    effects.actions.push({
      type: "permission_context_loaded",
      context: data?.data || {},
      inspectorTab: "permissions",
    });
  }
  if (commandName === "review" && data?.data?.review) {
    effects.actions.push({
      type: "review_loaded",
      review: data.data.review,
      inspectorTab: "review",
    });
  }
  effects.actions.push(logAction(`command: /${commandName || "?"}`, data?.success ? "ok" : "error"));
  return effects;
}

export function deriveSocketMessageEffects({
  type = "",
  data = {},
  currentSessionId = "",
  sessionEventLog = null,
  makeId = makeEventId,
  nowIso = () => new Date().toISOString(),
} = {}) {
  const options = { currentSessionId, sessionEventLog, makeId, nowIso };
  const payload = data || {};
  const effects = emptyEffects();

  if (type === "workspace_changed") {
    const bootstrap = normalizeAppBootstrap(payload);
    effects.actions.push({ type: "workspace_switched", bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      effects.loaderRequests.push({
        name: LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA,
        sessionId: "",
        assumeWorkspace: true,
      });
    } else {
      effects.actions.push({ type: "source_control_reset" });
    }
    return effects;
  }

  if (type === "terminal_event") {
    effects.actions.push({ type: "terminal_event", event: payload?.event || payload || {} });
    return effects;
  }

  if (type === "session_event") {
    effects.eventLogEntries.push(payload);
    if (payload?.event_kind === "turn.started") {
      effects.actions.push({
        type: "turn_started",
        turnId: payload.payload?.turn_id || "",
        userText: payload.payload?.user_text || "",
      });
    } else if (payload?.event_kind === "transition.recorded") {
      effects.actions.push({
        type: "turn_ended",
        terminationReason: payload.payload?.termination_reason || "",
        terminationDisplayReason:
          payload.payload?.display_reason || payload.payload?.termination_reason || "",
        terminationMessage: payload.payload?.message || payload.payload?.error || "",
        turnsUsed: payload.payload?.turns_used || 0,
        maxTurns: payload.payload?.max_turns || 8,
      });
    }
    return effects;
  }

  if (type === "session_status") {
    const snap = payload.session_snapshot || payload;
    const action = {
      type: "session_snapshot",
      snapshot: normalizeSessionPayload(snap),
    };
    if (snap?.timeline_replay_status && snap.timeline_replay_status !== "replay") {
      action.replayStatePatch = snap.timeline_replay_status;
    }
    effects.actions.push(action);
    if (snap?.session_id) effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSIONS });
    effects.actions.push(logAction("session_status", snap?.status || ""));
    return effects;
  }

  if (type === "stream_delta") {
    effects.actions.push({
      type: "assistant_delta",
      text: payload?.text || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    return effects;
  }

  if (type === "reasoning_delta") {
    effects.actions.push({
      type: "reasoning_delta",
      text: payload?.text || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    return effects;
  }

  if (type === "thinking_state") {
    effects.actions.push({ type: "thinking_state", active: payload?.active });
    effects.actions.push(logAction("thinking", payload?.active ? "started" : "stopped"));
    return effects;
  }

  if (type === "tool_start") {
    effects.actions.push({
      type: "tool_started",
      callId: payload?.call_id || eventId(makeId, "tool"),
      toolName: payload?.tool_name || "",
      label: payload?.tool_label || payload?.tool_name || "",
      arguments: payload?.arguments || {},
      permissionCategory: payload?.permission_category || "",
      supportsDiffPreview: Boolean(payload?.supports_diff_preview),
      progressRendererKey: payload?.progress_renderer_key || "",
      resultRendererKey: payload?.result_renderer_key || "",
      runtimeSource: payload?.runtime_source || "",
      resolvedToolRoots: payload?.resolved_tool_roots || {},
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    effects.actions.push(
      logAction(`tool: ${payload?.tool_name || "?"}`, JSON.stringify(payload?.arguments || {}).slice(0, 80)),
    );
    return effects;
  }

  if (type === "tool_finish") {
    effects.actions.push({
      type: "tool_finished",
      callId: payload?.call_id || "",
      toolName: payload?.tool_name || "",
      success: Boolean(payload?.success),
      error: payload?.error || "",
      data: payload?.data || {},
      label: payload?.tool_label || payload?.tool_name || "",
      permissionCategory: payload?.permission_category || "",
      supportsDiffPreview: Boolean(payload?.supports_diff_preview),
      progressRendererKey: payload?.progress_renderer_key || "",
      resultRendererKey: payload?.result_renderer_key || "",
      runtimeSource: payload?.runtime_source || "",
      resolvedToolRoots: payload?.resolved_tool_roots || {},
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    effects.actions.push(
      logAction(
        `tool done: ${payload?.call_id || "?"}`,
        payload?.success ? "success" : `error: ${payload?.error || ""}`,
      ),
    );
    if (FS_REFRESH_TOOLS.has(payload?.tool_name || "")) {
      effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "." });
    }
    return effects;
  }

  if (type === "permission_request") {
    effects.actions.push({
      type: "permission_request",
      permission: {
        ...payload,
        turn_id: payload?.turn_id || "",
        step_id: payload?.step_id || "",
        step_index: payload?.step_index || 0,
      },
      inspectorTab: "interaction",
    });
    effects.eventLogEntries.push(
      interactionEvent({
        data: payload,
        options,
        interactionId: payload?.permission_id || "",
        kind: "permission",
        payload: {
          interaction_id: payload?.permission_id || "",
          kind: "permission",
          tool_name: payload?.tool_name || "",
          category: payload?.category || "",
          reason: payload?.reason || "",
          details: payload?.details || {},
          turn_id: payload?.turn_id || "",
          step_id: payload?.step_id || "",
          step_index: payload?.step_index || 0,
        },
      }),
    );
    effects.actions.push(logAction("permission_request", payload?.reason || ""));
    return effects;
  }

  if (type === "user_input_request") {
    effects.actions.push({
      type: "user_input_request",
      request: {
        ...payload,
        turn_id: payload?.turn_id || "",
        step_id: payload?.step_id || "",
        step_index: payload?.step_index || 0,
      },
      resetUserAnswer: true,
    });
    effects.eventLogEntries.push(
      interactionEvent({
        data: payload,
        options,
        interactionId: payload?.request_id || "",
        kind: "user_input",
        payload: {
          interaction_id: payload?.request_id || "",
          kind: "user_input",
          tool_name: payload?.tool_name || "",
          question: payload?.question || "",
          options: payload?.options || [],
          turn_id: payload?.turn_id || "",
          step_id: payload?.step_id || "",
          step_index: payload?.step_index || 0,
        },
      }),
    );
    effects.actions.push(logAction("user_input_request", payload?.question || ""));
    return effects;
  }

  if (type === "command_result") return commandResultEffects(payload, options);

  if (type === "session_error") {
    effects.actions.push({
      type: "session_error",
      id: payload?.event_id || eventId(makeId, "error"),
      error: payload?.error || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    effects.actions.push(logAction("session_error", payload?.error || ""));
    return effects;
  }

  if (type === "plan_updated") {
    effects.actions.push({ type: "plan_loaded", plan: payload?.plan || null, inspectorTab: "plan" });
    effects.actions.push(logAction("plan_updated", payload?.plan?.title || ""));
    return effects;
  }

  if (type === "turn_end") {
    effects.actions.push({
      type: "turn_ended",
      terminationReason: payload?.termination_reason || "",
      terminationDisplayReason: payload?.display_reason || payload?.termination_reason || "",
      terminationMessage: payload?.message || "",
      turnsUsed: payload?.turns_used || 0,
      maxTurns: payload?.max_turns || 8,
    });
    effects.actions.push(logAction("turn_end", `reason=${payload?.termination_reason} turns=${payload?.turns_used}`));
    return effects;
  }

  if (type === "turn_start") {
    effects.actions.push({ type: "turn_started", turnId: payload?.turn_id || "", userText: payload?.user_text || "" });
    effects.actions.push(logAction("turn_start", payload?.turn_id || ""));
    return effects;
  }

  if (type === "step_start") {
    effects.actions.push({
      type: "step_started",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    effects.actions.push(logAction("step_start", payload?.step_id || ""));
    return effects;
  }

  if (type === "step_end") {
    effects.actions.push({
      type: "step_ended",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      assistantText: payload?.assistant_text || "",
      status: payload?.status || "",
    });
    effects.actions.push(logAction("step_end", payload?.step_id || ""));
    return effects;
  }

  if (type === "session_finished") {
    effects.actions.push({ type: "stream_completed" });
    if (payload?.session_snapshot) {
      effects.actions.push({
        type: "session_snapshot",
        snapshot: normalizeSessionPayload(payload.session_snapshot),
      });
    }
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSIONS });
    if (currentSession(options)) {
      effects.loaderRequests.push({
        name: LOADER_REQUESTS.LOAD_TASKS,
        sessionId: currentSession(options),
      });
    }
    effects.actions.push(logAction("session_finished", ""));
    return effects;
  }

  if (type === "tasks_refresh") {
    if (currentSession(options)) {
      effects.loaderRequests.push({
        name: LOADER_REQUESTS.LOAD_TASKS,
        sessionId: currentSession(options),
      });
    }
    return effects;
  }

  if (type === "artifacts_refresh") {
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_ARTIFACTS });
    return effects;
  }

  if (type === "message" && payload?.type === "ERROR") {
    effects.actions.push({
      type: "session_error",
      id: payload?.id || eventId(makeId, "error"),
      error: payload?.content || "Error",
      turnId: payload?.metadata?.turn_id || "",
      stepId: payload?.metadata?.step_id || "",
      stepIndex: payload?.metadata?.step_index || 0,
    });
    effects.actions.push(logAction("error", payload?.content || ""));
    return effects;
  }

  if (type === "message" && payload?.type === "CONTEXT_COMPACTED") {
    const metadata = payload?.metadata || {};
    effects.actions.push({
      type: "context_compacted",
      id: payload?.id || eventId(makeId, "context"),
      content: payload?.content || "",
      recentTurns: metadata.recent_turns,
      summarizedTurns: metadata.summarized_turns,
      approxTokensAfter: metadata.approx_tokens_after,
      turnId: metadata.turn_id || "",
      stepId: metadata.step_id || "",
      stepIndex: metadata.step_index || 0,
    });
    effects.actions.push(logAction("context_compacted", payload?.content || ""));
    return effects;
  }

  return effects;
}
```

- [ ] **Step 2: Run the socket tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS for the newly added socket tests. Existing source-level `App.jsx` assertions may still pass because `App.jsx` is not wired yet.

- [ ] **Step 3: Commit the socket effect module**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js
git commit -m "feat: add gui socket effect derivation"
```

## Task 3: Add Failing Visual Fixture Tests

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Create the failing visual fixture test file**

Create `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs` with this content:

```js
import assert from "node:assert/strict";

import {
  buildInteractionFixtureAction,
  buildThreadLifecycleFixtureAction,
  buildTimelineFixtureAction,
  installVisualDebugFixtures,
} from "../src/app-runtime/visual-debug-fixtures.js";

export function runVisualDebugFixturesTests() {
  const timelineAction = buildTimelineFixtureAction({ currentMode: "build" });
  assert.equal(timelineAction.type, "visual_timeline_fixture_loaded");
  assert.equal(timelineAction.sessionId, "visual-debug-timeline");
  assert.equal(timelineAction.snapshot.current_mode, "build");
  assert.equal(timelineAction.thinkingActive, true);
  assert.equal(timelineAction.timeline.some((item) => item.kind === "reasoning"), true);
  assert.equal(timelineAction.timeline.some((item) => item.kind === "compact"), true);
  assert.equal(
    timelineAction.timeline.some((item) => item.kind === "command_result" && item.commandName === "review"),
    true,
  );

  const permissionAction = buildInteractionFixtureAction("permission");
  assert.equal(permissionAction.type, "visual_interaction_fixture_loaded");
  assert.equal(permissionAction.permission.kind, "permission");
  assert.equal(permissionAction.userInput, null);

  const userInputAction = buildInteractionFixtureAction("user_input");
  assert.equal(userInputAction.permission, null);
  assert.equal(userInputAction.userInput.kind, "user_input");
  assert.equal(userInputAction.userInput.options.length, 2);

  const threadAction = buildThreadLifecycleFixtureAction();
  assert.equal(threadAction.type, "visual_thread_lifecycle_fixture_loaded");
  assert.equal(threadAction.sessionId, "visual-thread-active");
  assert.equal(threadAction.sessions.length, 3);

  const skippedWindow = {};
  const skippedCleanup = installVisualDebugFixtures({
    windowObject: skippedWindow,
    locationSearch: "?visual_debug=0",
    dispatch: () => {
      throw new Error("dispatch should not run while disabled");
    },
    openDiffFixture: () => {},
    currentMode: "build",
  });
  assert.equal(skippedCleanup, undefined);
  assert.equal(skippedWindow.__EMBEDAGENT_VISUAL_DEBUG__, undefined);

  const dispatched = [];
  const opened = [];
  const windowObject = {};
  const cleanup = installVisualDebugFixtures({
    windowObject,
    locationSearch: "?visual_debug=1",
    dispatch: (action) => dispatched.push(action),
    openDiffFixture: (payload) => opened.push(payload),
    currentMode: "verify",
  });
  assert.equal(typeof cleanup, "function");
  assert.equal(typeof windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadTimelineFixture, "function");
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadTimelineFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadInteractionFixture("user_input");
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadThreadLifecycleFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.openDiffFixture({
    title: "Debug Diff",
    diff: "--- a/a.c\n+++ b/a.c\n",
    filePath: "a.c",
  });
  assert.deepEqual(
    dispatched.map((action) => action.type),
    [
      "visual_timeline_fixture_loaded",
      "visual_interaction_fixture_loaded",
      "visual_thread_lifecycle_fixture_loaded",
    ],
  );
  assert.equal(dispatched[0].snapshot.current_mode, "verify");
  assert.equal(opened[0].title, "Debug Diff");
  cleanup();
  assert.equal(windowObject.__EMBEDAGENT_VISUAL_DEBUG__, undefined);
}
```

- [ ] **Step 2: Register the failing test in the runner**

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` imports:

```js
import { runVisualDebugFixturesTests } from "./visual-debug-fixtures.test.mjs";
```

Call it before the visual runner test:

```js
  runSocketMessageEffectsTests();
  runVisualDebugFixturesTests();
  await runVisualDebugRunnerTests();
```

- [ ] **Step 3: Run the test and verify it fails for the right reason**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with a module-not-found error for `../src/app-runtime/visual-debug-fixtures.js`.

- [ ] **Step 4: Commit the failing visual fixture test**

```bash
git add src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: cover gui visual debug fixtures"
```

## Task 4: Implement Visual Debug Fixture Boundary

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`

- [ ] **Step 1: Add the visual debug fixture module**

Create `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js` with this content:

```js
export function buildTimelineFixtureAction({ currentMode = "explore" } = {}) {
  return {
    type: "visual_timeline_fixture_loaded",
    sessionId: "visual-debug-timeline",
    inspectorTab: "tasks",
    timeline: [
      {
        id: "visual-user-1",
        kind: "user",
        content: "Review parser recovery and show the work.",
        turnId: "visual-turn-1",
      },
      {
        id: "visual-compact-1",
        kind: "compact",
        content: "Earlier setup turns were compacted.",
        summarizedTurns: 5,
        recentTurns: 2,
        approxTokensAfter: 3600,
        turnId: "visual-turn-1",
      },
      {
        id: "visual-reasoning-1",
        kind: "reasoning",
        content: "Inspect the parser recovery path, then verify the changed diagnostic flow.",
        streaming: false,
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-read-1",
        kind: "tool",
        toolName: "read_file",
        label: "Read File",
        status: "success",
        arguments: { path: "src/parser.c" },
        data: { summary: "Read parser entry point." },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-edit-1",
        kind: "tool",
        toolName: "edit_file",
        label: "Edit File",
        status: "success",
        arguments: { path: "src/parser.c" },
        data: {
          path: "src/parser.c",
          diff_preview: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1,2 @@\n-int parse(void) { return 0; }\n+int parse(void) { return 1; }\n+int parse_extra(void) { return 2; }\n",
        },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-review-result",
        kind: "command_result",
        commandName: "review",
        success: false,
        content: "Review found one follow-up item.",
        data: {
          review: {
            findings: [
              {
                id: "visual-finding-1",
                severity: "medium",
                priority: 2,
                title: "Add EOF recovery fixture",
                body: "The parser recovery path is not covered by a fixture yet.",
                file: "tests/parser_recovery_test.c",
                line: 18,
              },
            ],
            residual_risks: ["Visual fixture only checks rendering, not parser behavior."],
          },
        },
        turnId: "visual-turn-1",
      },
      {
        id: "visual-assistant-1",
        kind: "assistant",
        content: "Parser recovery was updated and review found one fixture follow-up.",
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-user-2",
        kind: "user",
        content: "Think through the next verification step.",
        turnId: "visual-turn-2",
      },
    ],
    snapshot: {
      session_id: "visual-debug-timeline",
      status: "running",
      current_mode: currentMode || "explore",
      pending_interaction_valid: false,
    },
    activeTurnId: "visual-turn-2",
    activeStepId: "visual-step-2",
    activeStepIndex: 1,
    thinkingActive: true,
  };
}

export function buildInteractionFixtureAction(kind = "permission") {
  const permission =
    kind === "permission"
      ? {
          interaction_id: "visual-permission-1",
          kind: "permission",
          tool_name: "edit_file",
          category: "workspace_write",
          reason: "Allow editing src/parser.c",
          details: { path: "src/parser.c" },
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
  const userInput =
    kind === "user_input"
      ? {
          interaction_id: "visual-input-1",
          request_id: "visual-input-1",
          kind: "user_input",
          tool_name: "ask_user",
          question: "Which parser behavior should be preserved?",
          options: [
            { index: 1, text: "Keep strict parsing" },
            { index: 2, text: "Accept empty input" },
          ],
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
  return {
    type: "visual_interaction_fixture_loaded",
    sessionId: "visual-debug-interaction",
    permission,
    userInput,
  };
}

export function buildThreadLifecycleFixtureAction() {
  return {
    type: "visual_thread_lifecycle_fixture_loaded",
    sessionId: "visual-thread-active",
    sessions: [
      {
        session_id: "visual-thread-active",
        user_goal: "Fix parser recovery",
        current_mode: "build",
        updated_at: "2026-06-16T09:30:00Z",
      },
      {
        session_id: "visual-thread-spec",
        summary_text: "Plan tokenizer cleanup",
        current_mode: "spec",
        updated_at: "2026-06-15T17:10:00Z",
      },
      {
        session_id: "visual-thread-verify",
        user_goal: "Verify offline bundle smoke",
        current_mode: "verify",
        updated_at: "2026-06-14T08:00:00Z",
      },
    ],
  };
}

export function installVisualDebugFixtures({
  windowObject,
  locationSearch = "",
  dispatch,
  openDiffFixture,
  currentMode = "explore",
} = {}) {
  if (!windowObject || typeof dispatch !== "function") return undefined;
  const params = new URLSearchParams(locationSearch || "");
  if (params.get("visual_debug") !== "1") return undefined;
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__ = {
    openDiffFixture({ title = "Visual Debug Diff", diff = "", filePath = "" } = {}) {
      if (typeof openDiffFixture === "function") {
        openDiffFixture({ title, diff, filePath });
      }
    },
    loadTimelineFixture() {
      dispatch(buildTimelineFixtureAction({ currentMode }));
    },
    loadInteractionFixture(kind = "permission") {
      dispatch(buildInteractionFixtureAction(kind));
    },
    loadThreadLifecycleFixture() {
      dispatch(buildThreadLifecycleFixtureAction());
    },
  };
  return () => {
    if (windowObject.__EMBEDAGENT_VISUAL_DEBUG__) {
      delete windowObject.__EMBEDAGENT_VISUAL_DEBUG__;
    }
  };
}
```

- [ ] **Step 2: Run the visual fixture tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS for `runVisualDebugFixturesTests()`.

- [ ] **Step 3: Commit the visual debug fixture module**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js
git commit -m "feat: extract gui visual debug fixtures"
```

## Task 5: Wire `App.jsx` To The Runtime Boundary

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add the runtime imports**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, add imports near the other webapp helper imports:

```js
import {
  LOADER_REQUESTS,
  deriveSocketMessageEffects,
} from "./app-runtime/socket-message-effects.js";
import { installVisualDebugFixtures } from "./app-runtime/visual-debug-fixtures.js";
```

- [ ] **Step 2: Replace inline visual fixture functions**

Remove the inline `loadTimelineFixture`, `loadInteractionFixture`, `loadThreadLifecycleFixture`, and the existing `useEffect` that assigns `window.__EMBEDAGENT_VISUAL_DEBUG__`.

Add this `useEffect` in the same location:

```js
  useEffect(() => {
    return installVisualDebugFixtures({
      windowObject: typeof window === "undefined" ? null : window,
      locationSearch: typeof window === "undefined" ? "" : window.location.search || "",
      dispatch,
      openDiffFixture: openDiffSurface,
      currentMode: state.requestedMode || DEFAULT_MODE,
    });
  }, [runtimeState.timelineItems, state.requestedMode]);
```

- [ ] **Step 3: Add loader request execution**

Add this function before `handleSocketMessage(...)`:

```js
  function executeLoaderRequest(request = {}) {
    if (request.name === LOADER_REQUESTS.LOAD_APP_BOOTSTRAP) {
      return loadAppBootstrap();
    }
    if (request.name === LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA) {
      return loadActiveWorkspaceData(request.sessionId || "", Boolean(request.assumeWorkspace));
    }
    if (request.name === LOADER_REQUESTS.LOAD_SESSIONS) {
      return loadSessions();
    }
    if (request.name === LOADER_REQUESTS.LOAD_SESSION && request.sessionId) {
      return loadSession(request.sessionId);
    }
    if (request.name === LOADER_REQUESTS.LOAD_TASKS && request.sessionId) {
      return loadTasks(request.sessionId);
    }
    if (request.name === LOADER_REQUESTS.LOAD_ARTIFACTS) {
      return loadArtifacts();
    }
    if (request.name === LOADER_REQUESTS.LOAD_PERMISSION_CONTEXT && request.sessionId) {
      return loadPermissionContext(request.sessionId);
    }
    if (request.name === LOADER_REQUESTS.LOAD_FILE_CHILDREN) {
      return loadFileChildren(request.path || ".");
    }
    return Promise.resolve();
  }
```

- [ ] **Step 4: Add socket descriptor execution**

Add this function after `executeLoaderRequest(...)`:

```js
  function executeSocketEffects(effects = {}) {
    const eventLogEntries = effects.eventLogEntries || [];
    if (eventLogEntries.length) {
      const nextLog = updateSessionEventLog((current) => {
        let next = current;
        for (const entry of eventLogEntries) {
          next = appendSessionEvent(next, entry || {});
        }
        return next;
      });
      if (
        (nextLog.replayState === "replay_needed" || nextLog.replayState === "degraded") &&
        currentSessionIdRef.current
      ) {
        void recoverSessionReplay(currentSessionIdRef.current, nextLog);
      }
    }

    for (const action of effects.actions || []) {
      if (action.type === "user_input_request" && action.resetUserAnswer) {
        setUserAnswer("");
      }
      if (action.type === "session_snapshot" && action.replayStatePatch) {
        updateSessionEventLog((current) => ({
          ...current,
          replayState: action.replayStatePatch,
        }));
      }
      dispatch(action);
    }

    for (const request of effects.loaderRequests || []) {
      void executeLoaderRequest(request);
    }
  }
```

- [ ] **Step 5: Replace `handleSocketMessage(...)`**

Replace the long branch-based body of `handleSocketMessage(type, data)` with:

```js
  function handleSocketMessage(type, data) {
    const effects = deriveSocketMessageEffects({
      type,
      data: data || {},
      currentSessionId: currentSessionIdRef.current,
      sessionEventLog: sessionEventLogRef.current,
      makeId: makeEventId,
      nowIso: () => new Date().toISOString(),
    });
    executeSocketEffects(effects);
  }
```

- [ ] **Step 6: Remove stale imports only if unused**

After the refactor, run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

If Vite reports unused imports, remove only imports made stale by this task. `makeEventId` remains needed by `respondToInteraction(...)`, so do not remove it unless the build proves it is unused.

- [ ] **Step 7: Update source-level assertions in `run-tests.mjs`**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, update the `appSource` assertions:

Keep these assertions:

```js
  assert.equal(appSource.includes("deriveSocketMessageEffects"), true);
  assert.equal(appSource.includes("executeSocketEffects"), true);
  assert.equal(appSource.includes("executeLoaderRequest"), true);
  assert.equal(appSource.includes("installVisualDebugFixtures"), true);
  assert.equal(appSource.includes("__EMBEDAGENT_VISUAL_DEBUG__"), false);
  assert.equal(appSource.includes("visual_timeline_fixture_loaded"), false);
  assert.equal(appSource.includes("visual_interaction_fixture_loaded"), false);
  assert.equal(appSource.includes("visual_thread_lifecycle_fixture_loaded"), false);
```

Remove old `appSource` assertions that require `loadTimelineFixture`, `loadInteractionFixture`, `loadThreadLifecycleFixture`, inline `visual_timeline_fixture_loaded`, inline `visual_interaction_fixture_loaded`, inline `visual_thread_lifecycle_fixture_loaded`, inline `kind: "reasoning"`, inline `kind: "compact"`, inline `commandName: "review"`, or inline `thinkingActive: true`.

Add new source checks for the runtime modules:

```js
  const socketMessageEffectsSource = fs.readFileSync(
    webappSourcePath("app-runtime", "socket-message-effects.js"),
    "utf8",
  );
  assert.equal(socketMessageEffectsSource.includes("deriveSocketMessageEffects"), true);
  assert.equal(socketMessageEffectsSource.includes("LOADER_REQUESTS"), true);
  assert.equal(socketMessageEffectsSource.includes("workspace_changed"), true);
  assert.equal(socketMessageEffectsSource.includes("session_event"), true);
  assert.equal(socketMessageEffectsSource.includes("permission_request"), true);
  assert.equal(socketMessageEffectsSource.includes("user_input_request"), true);
  assert.equal(socketMessageEffectsSource.includes("command_result"), true);
  assert.equal(socketMessageEffectsSource.includes("fetch("), false);
  assert.equal(socketMessageEffectsSource.includes("new WebSocket"), false);
  assert.equal(socketMessageEffectsSource.includes("useEffect"), false);

  const visualDebugFixturesSource = fs.readFileSync(
    webappSourcePath("app-runtime", "visual-debug-fixtures.js"),
    "utf8",
  );
  assert.equal(visualDebugFixturesSource.includes("__EMBEDAGENT_VISUAL_DEBUG__"), true);
  assert.equal(visualDebugFixturesSource.includes("visual_debug"), true);
  assert.equal(visualDebugFixturesSource.includes("loadTimelineFixture"), true);
  assert.equal(visualDebugFixturesSource.includes("loadInteractionFixture"), true);
  assert.equal(visualDebugFixturesSource.includes("loadThreadLifecycleFixture"), true);
  assert.equal(visualDebugFixturesSource.includes("visual_timeline_fixture_loaded"), true);
  assert.equal(visualDebugFixturesSource.includes('kind: "reasoning"'), true);
  assert.equal(visualDebugFixturesSource.includes('kind: "compact"'), true);
  assert.equal(visualDebugFixturesSource.includes('commandName: "review"'), true);
  assert.equal(visualDebugFixturesSource.includes("thinkingActive: true"), true);
```

- [ ] **Step 8: Run webapp tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands pass.

- [ ] **Step 9: Commit the `App.jsx` wiring**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "refactor: route gui app runtime effects through boundary"
```

## Task 6: Update Documentation And Run Full Verification

**Files:**
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Potentially modify generated GUI static assets if `npm run build` updates tracked files.

- [ ] **Step 1: Update `docs/modules/frontend-gui.md`**

In `docs/modules/frontend-gui.md`, update the frontend responsibility bullets near the top to mention:

```markdown
- GUI app-runtime boundary for frontend-only socket effect derivation and dev-only visual fixtures (`webapp/src/app-runtime/`)
```

Add a short section after the T3 timeline section:

```markdown
### GUI App Runtime Boundary

`webapp/src/app-runtime/` owns frontend-only runtime interpretation helpers.
`socket-message-effects.js` maps existing WebSocket messages into private
webapp descriptors: reducer actions, session event-log entries, and loader
requests. `App.jsx` remains the executor of those descriptors and continues to
own HTTP loader calls in this slice. `visual-debug-fixtures.js` owns the
development-only `?visual_debug=1` fixtures used by the visual harness. This
boundary is not a backend protocol, not session-history truth, and does not
change Agent Core, workflow packages, permission policy, or runtime reducers.
```

- [ ] **Step 2: Update `docs/development-tracker.md`**

At the top of the dated progress section, add:

```markdown
### 2026-06-18 - GUI App Runtime Controller Boundary

- React webapp now has a GUI-only `webapp/src/app-runtime/` boundary: socket messages are interpreted by pure descriptor derivation before `App.jsx` executes reducer actions, session event-log entries, and existing loader requests.
- Dev-only visual timeline/interaction/thread fixtures moved out of `App.jsx` into `visual-debug-fixtures.js`, while remaining gated by `?visual_debug=1`.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, workflow package, permission policy, transcript, runtime reducer, operation reducer, compaction reducer, recovery reducer, terminal execution, or source-control execution semantics changed.
```

Update the "updated date" line to:

```markdown
> 更新日期：2026-06-18（GUI app runtime controller boundary）
```

- [ ] **Step 3: Update `docs/design-change-log.md`**

Add a new top entry:

```markdown
## 2026-06-18 - GUI app runtime controller boundary

- 变更主题：GUI app-runtime 边界抽出 socket effect derivation 与 dev-only visual fixtures
- 变更内容：
  - React webapp 新增 `webapp/src/app-runtime/socket-message-effects.js`，把现有 WebSocket message 转换成私有 GUI descriptors：reducer actions、session event-log entries 和 loader requests。
  - `App.jsx` 继续执行现有 HTTP loader、session event-log append 和 reducer dispatch，但不再承载完整 socket message 分支解释。
  - React webapp 新增 `webapp/src/app-runtime/visual-debug-fixtures.js`，集中管理 `?visual_debug=1` 下的 timeline、interaction 和 thread lifecycle fixtures。
- 架构影响：
  - 该边界是 GUI app-shell implementation detail，不是 backend protocol、session-history truth 或 Agent Core extension API。
  - 未改变 transcript、timeline transport、permission policy、workflow packages、runtime reducers、operation reducers、compaction reducers、recovery reducers、terminal execution 或 source-control execution。
- 后续：
  - 可在后续切片继续把 app/session/bootstrap loaders 和 command routing 从 `App.jsx` 抽到更小 controller/hook 中。
```

- [ ] **Step 4: Run webapp verification**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands pass.

- [ ] **Step 5: Run focused GUI backend tests**

Run from repository root:

```bash
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run visual harness smoke**

Run from repository root:

```bash
node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-app-runtime-controller"
```

Expected: the command exits successfully, produces screenshots under the output directory, and reports no relevant browser console errors. If Playwright or the local GUI runtime is unavailable, record the exact blocker in the final implementation report and keep the passing unit/build/backend proof explicit.

- [ ] **Step 7: Check repository status**

Run:

```bash
git status --short
```

Expected: only intentional source, test, docs, and generated GUI static asset changes are present.

- [ ] **Step 8: Commit docs and any generated static assets**

```bash
git add docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md
git status --short
git commit -m "docs: record gui app runtime boundary"
```

If `npm run build` updates tracked static GUI assets, include those exact tracked asset paths in the same commit or in a separate commit with:

```bash
git add <tracked-gui-static-asset-paths>
git commit -m "build: refresh gui webapp assets"
```

## Final Verification Checklist

- [ ] `cd src/embedagent/frontend/gui/webapp && npm test`
- [ ] `cd src/embedagent/frontend/gui/webapp && npm run build`
- [ ] `uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q`
- [ ] `node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-app-runtime-controller"`
- [ ] Confirm `socket-message-effects.js` imports no React, DOM, backend, or Agent Core modules.
- [ ] Confirm visual debug fixtures remain gated by `visual_debug=1`.
- [ ] Confirm `App.jsx` still owns actual loader execution and no backend protocol changed.
- [ ] Confirm docs explicitly say this is GUI app-shell work only.
