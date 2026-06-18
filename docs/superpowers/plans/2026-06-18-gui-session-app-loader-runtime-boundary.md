# GUI Session/App Loader Runtime Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract GUI app/session loader request orchestration and session bootstrap projection from `App.jsx` into a GUI-only `app-runtime` boundary.

**Architecture:** Add `webapp/src/app-runtime/session-loaders.js` as the single private loader request vocabulary and loader request executor. Keep concrete HTTP route calls, reducer dispatches, event-log resets, terminal summary loading, and task/artifact refreshes in `App.jsx`, but move branching and pure session bootstrap projection into testable frontend runtime helpers. `socket-message-effects.js` imports the shared loader vocabulary so socket effects and loader execution cannot drift.

**Tech Stack:** React 18, plain JavaScript ES modules, existing Node webapp tests, existing Vite build, existing Python GUI backend tests, existing Playwright visual debug harness.

---

## File Structure

- Create `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
  - Owns `LOADER_REQUESTS`.
  - Owns `createLoaderRequestExecutor(loaders)`.
  - Owns `deriveSessionActivation(payload, sessionId, options)`.
  - Imports only pure frontend helpers from `state-helpers.js`.
  - Does not import React, call `fetch`, open WebSockets, touch DOM globals, or import backend/Core code.
- Create `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs`
  - Tests loader request dispatch, defensive no-op behavior, file-tree default path, and session activation projection.
- Modify `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - Remove its local `LOADER_REQUESTS`.
  - Import `LOADER_REQUESTS` from `./session-loaders.js`.
  - Keep the module pure.
- Modify `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
  - Import `LOADER_REQUESTS` from `session-loaders.js`.
  - Keep existing socket effect behavior tests.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Import `createLoaderRequestExecutor` and `deriveSessionActivation`.
  - Use `deriveSessionActivation(...)` inside `loadSession(...)`.
  - Replace the inline `executeLoaderRequest(request)` switch with an executor created by `createLoaderRequestExecutor(...)`.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Run `session-loaders.test.mjs`.
  - Add source-level boundary assertions for `session-loaders.js`.
  - Assert `App.jsx` no longer contains the old inline loader request switch.
- Modify docs after implementation:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- Modify generated GUI static asset if `npm run build` refreshes it:
  - `src/embedagent/frontend/gui/static/assets/app.js`

## Constraints For Every Task

- Do not modify Agent Core, providers, tool execution, permission policy, workflow packages, transcript reducers, operation reducers, runtime reducers, compaction reducers, or recovery reducers.
- Do not change backend HTTP or WebSocket contracts.
- Do not add npm or Python dependencies.
- Do not move terminal execution, source-control execution, file preview, or right-panel rendering into Agent Core.
- Keep loader request descriptors private to `webapp/src/app-runtime/`.
- Keep concrete HTTP loaders in `App.jsx` for this slice.
- Keep terminal summary loading GUI-local and session-activation side-effect-only.
- Keep JavaScript syntax compatible with the existing webapp build.

## Task 1: Add Failing Loader Boundary Tests

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Create the failing loader test file**

Create `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs` with this content:

```js
import assert from "node:assert/strict";

import {
  LOADER_REQUESTS,
  createLoaderRequestExecutor,
  deriveSessionActivation,
} from "../src/app-runtime/session-loaders.js";

function createRecordedLoaders() {
  const calls = [];
  const record = (name) => (...args) => {
    calls.push({ name, args });
    return `${name}:done`;
  };
  return {
    calls,
    loaders: {
      loadAppBootstrap: record("loadAppBootstrap"),
      loadActiveWorkspaceData: record("loadActiveWorkspaceData"),
      loadSessions: record("loadSessions"),
      loadSession: record("loadSession"),
      loadTasks: record("loadTasks"),
      loadArtifacts: record("loadArtifacts"),
      loadPermissionContext: record("loadPermissionContext"),
      loadFileChildren: record("loadFileChildren"),
    },
  };
}

async function flush(result) {
  return await result;
}

export async function runSessionLoadersTests() {
  const { calls, loaders } = createRecordedLoaders();
  const execute = createLoaderRequestExecutor(loaders);

  assert.equal(await flush(execute({ name: LOADER_REQUESTS.LOAD_APP_BOOTSTRAP })), "loadAppBootstrap:done");
  assert.equal(calls.at(-1).name, "loadAppBootstrap");

  await execute({
    name: LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA,
    sessionId: "sess-1",
    assumeWorkspace: true,
  });
  assert.deepEqual(calls.at(-1), {
    name: "loadActiveWorkspaceData",
    args: ["sess-1", true],
  });

  await execute({ name: LOADER_REQUESTS.LOAD_SESSIONS });
  assert.deepEqual(calls.at(-1), { name: "loadSessions", args: [] });

  await execute({ name: LOADER_REQUESTS.LOAD_SESSION, sessionId: "sess-2" });
  assert.deepEqual(calls.at(-1), { name: "loadSession", args: ["sess-2"] });

  await execute({ name: LOADER_REQUESTS.LOAD_TASKS, sessionId: "sess-3" });
  assert.deepEqual(calls.at(-1), { name: "loadTasks", args: ["sess-3"] });

  await execute({ name: LOADER_REQUESTS.LOAD_ARTIFACTS });
  assert.deepEqual(calls.at(-1), { name: "loadArtifacts", args: [] });

  await execute({ name: LOADER_REQUESTS.LOAD_PERMISSION_CONTEXT, sessionId: "sess-4" });
  assert.deepEqual(calls.at(-1), { name: "loadPermissionContext", args: ["sess-4"] });

  await execute({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN });
  assert.deepEqual(calls.at(-1), { name: "loadFileChildren", args: ["."] });

  await execute({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "src" });
  assert.deepEqual(calls.at(-1), { name: "loadFileChildren", args: ["src"] });

  const beforeNoOps = calls.length;
  await execute({ name: "unknown_loader" });
  await execute({});
  await execute(null);
  await execute({ name: LOADER_REQUESTS.LOAD_SESSION });
  await execute({ name: LOADER_REQUESTS.LOAD_TASKS });
  await execute({ name: LOADER_REQUESTS.LOAD_PERMISSION_CONTEXT });
  assert.equal(calls.length, beforeNoOps);

  const missingOptionalExecutor = createLoaderRequestExecutor({});
  assert.equal(await missingOptionalExecutor({ name: LOADER_REQUESTS.LOAD_APP_BOOTSTRAP }), undefined);
  assert.equal(await missingOptionalExecutor({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN }), undefined);

  const activation = deriveSessionActivation(
    {
      snapshot: {
        session_id: "sess-bootstrap",
        status: "waiting_permission",
        current_mode: "debug",
        has_pending_permission: true,
      },
      history: {
        history_source: "step_events",
        integrity: { status: "healthy", event_count: 12 },
        turns: [
          {
            turn_id: "turn-1",
            user_text: "Inspect parser",
            steps: [
              {
                step_id: "step-1",
                step_index: 1,
                reasoning: "Read parser entry point",
                assistant_text: "Parser inspected.",
                tool_calls: [
                  {
                    call_id: "call-1",
                    tool_name: "read_file",
                    tool_label: "Read File",
                    status: "success",
                    arguments: { path: "src/parser.c" },
                  },
                ],
              },
            ],
          },
        ],
      },
      plan: { title: "Parser plan", steps: [] },
      permission_context: { session_id: "sess-bootstrap", rules: [{ category: "workspace_write" }] },
    },
    "sess-bootstrap",
  );

  assert.equal(activation.sessionId, "sess-bootstrap");
  assert.equal(activation.snapshot.session_id, "sess-bootstrap");
  assert.equal(activation.snapshot.current_mode, "debug");
  assert.equal(activation.snapshot.status, "waiting_permission");
  assert.equal(activation.timeline.length, 4);
  assert.equal(activation.timeline[0].kind, "user");
  assert.equal(activation.timeline[0].projectionSource, "step_events");
  assert.equal(activation.timeline[1].kind, "reasoning");
  assert.equal(activation.timeline[2].toolName, "read_file");
  assert.equal(activation.timeline[3].kind, "assistant");
  assert.deepEqual(activation.historyIntegrity, { status: "healthy", event_count: 12 });
  assert.equal(activation.plan.title, "Parser plan");
  assert.equal(activation.permissionContext.rules[0].category, "workspace_write");

  const sparseActivation = deriveSessionActivation(null, "sess-empty");
  assert.equal(sparseActivation.sessionId, "sess-empty");
  assert.equal(sparseActivation.snapshot.session_id, "");
  assert.deepEqual(sparseActivation.timeline, []);
  assert.equal(sparseActivation.historyIntegrity, null);
  assert.equal(sparseActivation.plan, null);
  assert.equal(sparseActivation.permissionContext, null);
}
```

- [ ] **Step 2: Update the socket effect test import to the future shared vocabulary**

In `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`, replace the current combined import:

```js
import {
  LOADER_REQUESTS,
  deriveSocketMessageEffects,
} from "../src/app-runtime/socket-message-effects.js";
```

with:

```js
import { LOADER_REQUESTS } from "../src/app-runtime/session-loaders.js";
import { deriveSocketMessageEffects } from "../src/app-runtime/socket-message-effects.js";
```

- [ ] **Step 3: Register the new test in the runner**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, add this import near the other runtime test imports:

```js
import { runSessionLoadersTests } from "./session-loaders.test.mjs";
```

Then call it immediately before `runSocketMessageEffectsTests()`:

```js
  runWebSocketLifecycleTests();
  await runSessionLoadersTests();
  runSocketMessageEffectsTests();
  runVisualDebugFixturesTests();
```

- [ ] **Step 4: Run the test and verify it fails for the right reason**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with a module-not-found error for `../src/app-runtime/session-loaders.js`.

- [ ] **Step 5: Commit the failing test**

```bash
git add src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: cover gui session loader boundary"
```

## Task 2: Implement `session-loaders.js`

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`

- [ ] **Step 1: Add the loader runtime module**

Create `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js` with this content:

```js
import { normalizeSessionPayload, timelineFromTurns } from "../state-helpers.js";

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

function invoke(callback, ...args) {
  if (typeof callback !== "function") {
    return Promise.resolve();
  }
  return Promise.resolve().then(() => callback(...args));
}

export function createLoaderRequestExecutor(loaders = {}) {
  return function executeLoaderRequest(request = {}) {
    const name = request?.name || "";
    if (name === LOADER_REQUESTS.LOAD_APP_BOOTSTRAP) {
      return invoke(loaders.loadAppBootstrap);
    }
    if (name === LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA) {
      return invoke(
        loaders.loadActiveWorkspaceData,
        request.sessionId || "",
        Boolean(request.assumeWorkspace),
      );
    }
    if (name === LOADER_REQUESTS.LOAD_SESSIONS) {
      return invoke(loaders.loadSessions);
    }
    if (name === LOADER_REQUESTS.LOAD_SESSION) {
      if (!request.sessionId) return Promise.resolve();
      return invoke(loaders.loadSession, request.sessionId);
    }
    if (name === LOADER_REQUESTS.LOAD_TASKS) {
      if (!request.sessionId) return Promise.resolve();
      return invoke(loaders.loadTasks, request.sessionId);
    }
    if (name === LOADER_REQUESTS.LOAD_ARTIFACTS) {
      return invoke(loaders.loadArtifacts);
    }
    if (name === LOADER_REQUESTS.LOAD_PERMISSION_CONTEXT) {
      if (!request.sessionId) return Promise.resolve();
      return invoke(loaders.loadPermissionContext, request.sessionId);
    }
    if (name === LOADER_REQUESTS.LOAD_FILE_CHILDREN) {
      return invoke(loaders.loadFileChildren, request.path || ".");
    }
    return Promise.resolve();
  };
}

export function deriveSessionActivation(payload = {}, sessionId = "", options = {}) {
  const safePayload = payload || {};
  const history = safePayload.history || {};
  const snapshot = normalizeSessionPayload(
    safePayload.snapshot || {},
    options.defaultMode || "explore",
  );
  return {
    sessionId,
    snapshot,
    timeline: timelineFromTurns(history.turns || [], [], {
      projectionSource: history.history_source || "",
    }),
    historyIntegrity: history.integrity || null,
    plan: safePayload.plan || null,
    permissionContext: safePayload.permission_context || null,
  };
}
```

- [ ] **Step 2: Run the new focused test through the runner**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS. At this point `socket-message-effects.js` may still keep its old local `LOADER_REQUESTS` copy, but the shared constants exist and have the same private request values.

- [ ] **Step 3: Commit the new module**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js
git commit -m "feat: add gui session loader runtime boundary"
```

## Task 3: Share Loader Vocabulary With Socket Effects

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Update the socket effects import**

In `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`, add this import after the existing pure helper imports:

```js
import { LOADER_REQUESTS } from "./session-loaders.js";
```

Then delete the local `export const LOADER_REQUESTS = Object.freeze({ ... });` block from `socket-message-effects.js`.

The top of the file should look like this:

```js
import { normalizeAppBootstrap } from "../app-workspaces.js";
import { createDiffSurfaceState } from "../session-runtime/diff-model.js";
import { makeEventId, normalizeSessionPayload } from "../state-helpers.js";
import { LOADER_REQUESTS } from "./session-loaders.js";
```

- [ ] **Step 2: Add source-level assertions for the shared boundary**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, update the source-level checks around `socketMessageEffectsSource`.

Keep existing checks for socket message handling, then add:

```js
  assert.equal(socketMessageEffectsSource.includes('from "./session-loaders.js"'), true);
  assert.equal(socketMessageEffectsSource.includes("export const LOADER_REQUESTS"), false);
```

Add this new source block after `socketMessageEffectsSource` checks:

```js
  const sessionLoadersSource = fs.readFileSync(
    webappSourcePath("app-runtime", "session-loaders.js"),
    "utf8",
  );
  assert.equal(sessionLoadersSource.includes("createLoaderRequestExecutor"), true);
  assert.equal(sessionLoadersSource.includes("deriveSessionActivation"), true);
  assert.equal(sessionLoadersSource.includes("LOADER_REQUESTS"), true);
  assert.equal(sessionLoadersSource.includes("timelineFromTurns"), true);
  assert.equal(sessionLoadersSource.includes("normalizeSessionPayload"), true);
  assert.equal(sessionLoadersSource.includes("fetch("), false);
  assert.equal(sessionLoadersSource.includes("new WebSocket"), false);
  assert.equal(sessionLoadersSource.includes("useEffect"), false);
  assert.equal(sessionLoadersSource.includes("import React"), false);
```

- [ ] **Step 3: Run webapp tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 4: Commit the shared loader vocabulary**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "refactor: share gui loader request vocabulary"
```

## Task 4: Wire `App.jsx` To The Loader Boundary

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Update `App.jsx` imports**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, remove only `timelineFromTurns` from the `./state-helpers.js` import. Keep `normalizeSessionPayload`; it is still used by other App-level flows such as new-session creation and interaction responses.

The `state-helpers.js` import should become:

```js
import {
  createTreeNode,
  makeEventId,
  normalizeSessionPayload,
} from "./state-helpers.js";
```

Replace the socket effects import:

```js
import {
  LOADER_REQUESTS,
  deriveSocketMessageEffects,
} from "./app-runtime/socket-message-effects.js";
```

with:

```js
import { deriveSocketMessageEffects } from "./app-runtime/socket-message-effects.js";
import {
  createLoaderRequestExecutor,
  deriveSessionActivation,
} from "./app-runtime/session-loaders.js";
```

- [ ] **Step 2: Use `deriveSessionActivation(...)` in `loadSession(...)`**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, replace the first part of `loadSession(sessionId)`:

```js
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/bootstrap`);
    const snapshot = normalizeSessionPayload(payload.snapshot || {});
    const history = payload.history || {};
    dispatch({
      type: "session_activated",
      sessionId,
      snapshot,
      timeline: timelineFromTurns(history.turns || [], [], {
        projectionSource: history.history_source || "",
      }),
      historyIntegrity: history.integrity || null,
    });
    replaceSessionEventLog(createRuntimeEventLog(snapshot));
    dispatch({ type: "plan_loaded", plan: payload.plan || null });
    dispatch({ type: "permission_context_loaded", context: payload.permission_context || null });
```

with:

```js
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/bootstrap`);
    const activation = deriveSessionActivation(payload, sessionId, { defaultMode: DEFAULT_MODE });
    dispatch({
      type: "session_activated",
      sessionId: activation.sessionId,
      snapshot: activation.snapshot,
      timeline: activation.timeline,
      historyIntegrity: activation.historyIntegrity,
    });
    replaceSessionEventLog(createRuntimeEventLog(activation.snapshot));
    dispatch({ type: "plan_loaded", plan: activation.plan });
    dispatch({ type: "permission_context_loaded", context: activation.permissionContext });
```

Leave terminal summary loading and the final `await Promise.all([loadTasks(sessionId), loadArtifacts()]);` unchanged.

- [ ] **Step 3: Replace the inline loader request switch**

Delete the current inline function:

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

Add this constant in the same location before `executeSocketEffects(...)`:

```js
  const executeLoaderRequest = createLoaderRequestExecutor({
    loadAppBootstrap,
    loadActiveWorkspaceData,
    loadSessions,
    loadSession,
    loadTasks,
    loadArtifacts,
    loadPermissionContext,
    loadFileChildren,
  });
```

Do not change `executeSocketEffects(...)` except that it now calls the injected executor constant.

- [ ] **Step 4: Update source-level assertions for `App.jsx`**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, keep these existing `appSource` assertions:

```js
  assert.equal(appSource.includes("deriveSocketMessageEffects"), true);
  assert.equal(appSource.includes("executeSocketEffects"), true);
  assert.equal(appSource.includes("executeLoaderRequest"), true);
  assert.equal(appSource.includes("installVisualDebugFixtures"), true);
```

Add these assertions immediately after them:

```js
  assert.equal(appSource.includes("createLoaderRequestExecutor"), true);
  assert.equal(appSource.includes("deriveSessionActivation"), true);
  assert.equal(appSource.includes("function executeLoaderRequest(request = {})"), false);
  assert.equal(appSource.includes("request.name === LOADER_REQUESTS"), false);
```

- [ ] **Step 5: Run webapp tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands pass.

- [ ] **Step 6: Commit the `App.jsx` wiring**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "refactor: route gui loaders through runtime boundary"
```

## Task 5: Update Documentation And Run Full Verification

**Files:**
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Potentially modify: `src/embedagent/frontend/gui/static/assets/app.js`

- [ ] **Step 1: Update `docs/modules/frontend-gui.md`**

In `docs/modules/frontend-gui.md`, update the responsibilities list item for app runtime to include session loaders:

```markdown
- GUI app-runtime boundary for frontend-only socket effect derivation, session/app loader request orchestration, session bootstrap projection, and dev-only visual fixtures（`webapp/src/app-runtime/`）
```

In the existing `### GUI App Runtime Boundary` section, replace the paragraph with:

```markdown
`webapp/src/app-runtime/` owns frontend-only runtime interpretation helpers.
`session-loaders.js` owns private loader request vocabulary, loader request
execution against injected GUI callbacks, and session bootstrap projection from
the official `/api/sessions/{id}/bootstrap` payload. `socket-message-effects.js`
maps existing WebSocket messages into private webapp descriptors: reducer
actions, session event-log entries, and loader requests. `App.jsx` remains the
executor of HTTP route calls, reducer dispatch, event-log reset, terminal
summary loading, task/artifact refreshes, and render composition in this slice.
`visual-debug-fixtures.js` owns the development-only `?visual_debug=1` fixtures
used by the visual harness. This boundary is not a backend protocol, not
session-history truth, and does not change Agent Core, workflow packages,
permission policy, terminal execution, source-control execution, provider
configuration, extension loading, or runtime reducers.
```

- [ ] **Step 2: Update `docs/development-tracker.md`**

At the top of the dated progress section, add:

```markdown
### 2026-06-18 - GUI Session/App Loader Runtime Boundary

- React webapp `webapp/src/app-runtime/session-loaders.js` now owns the GUI-private loader request vocabulary, defensive loader request executor, and session bootstrap projection helper.
- `socket-message-effects.js` shares that loader vocabulary instead of defining a second copy, while remaining a pure frontend effect derivation module.
- `App.jsx` now delegates session bootstrap projection and loader request execution branching to the app-runtime boundary, but still owns concrete HTTP route calls, reducer dispatch, event-log reset, terminal summary loading, task/artifact refreshes, and render composition.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, workflow package, permission policy, transcript, runtime reducer, operation reducer, compaction reducer, recovery reducer, terminal execution, or source-control execution semantics changed.
```

Update the top metadata line to:

```markdown
> 更新日期：2026-06-18（GUI session/app loader runtime boundary）
```

- [ ] **Step 3: Update `docs/design-change-log.md`**

Add a new top entry before the current DC-172 entry:

```markdown
### DC-173

- 日期：2026-06-18
- 变更主题：GUI session/app loader runtime boundary
- 变更摘要：
  - React webapp 新增 `webapp/src/app-runtime/session-loaders.js`，集中管理 GUI-private loader request vocabulary、防御性 loader request executor 与 session bootstrap projection helper。
  - `socket-message-effects.js` 改为共享 `session-loaders.js` 的 loader vocabulary，避免 socket effect derivation 和 loader execution 维护两份私有请求名。
  - `App.jsx` 继续拥有实际 HTTP route calls、reducer dispatch、event-log reset、terminal summary loading、task/artifact refreshes 和 render composition，但不再承载 loader request switch 或 session bootstrap projection 细节。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/superpowers/specs/2026-06-18-gui-session-app-loader-runtime-boundary-design.md`
  - `docs/superpowers/plans/2026-06-18-gui-session-app-loader-runtime-boundary.md`
- 是否需要 ADR：否；该边界是 GUI app-shell implementation detail，不是 backend protocol、session-history truth 或 Agent Core extension API。
- 后续动作：
  - 可在后续切片继续把 command routing、terminal action helpers、source-control action helpers 或 file preview loading 从 `App.jsx` 抽到更小 controller/hook 中。
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
node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-session-app-loader-runtime"
```

Expected: the command exits successfully, produces screenshots under the output directory, and reports no relevant browser console errors. If Playwright or the local GUI runtime is unavailable, record the exact blocker in the final implementation report and keep the passing unit/build/backend proof explicit.

- [ ] **Step 7: Check repository status**

Run:

```bash
git status --short
```

Expected: only intentional source, test, docs, and generated GUI static asset changes are present.

- [ ] **Step 8: Commit docs and generated static assets**

If `npm run build` updates `src/embedagent/frontend/gui/static/assets/app.js`, commit it separately:

```bash
git add src/embedagent/frontend/gui/static/assets/app.js
git commit -m "build: refresh gui webapp assets"
```

Then commit docs:

```bash
git add docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record gui session loader boundary"
```

If `npm run build` does not update tracked static assets, skip the build commit and only make the docs commit.

## Final Verification Checklist

- [ ] `cd src/embedagent/frontend/gui/webapp && npm test`
- [ ] `cd src/embedagent/frontend/gui/webapp && npm run build`
- [ ] `uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q`
- [ ] `node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-session-app-loader-runtime"`
- [ ] Confirm `session-loaders.js` imports no React, DOM, WebSocket, backend, or Agent Core modules.
- [ ] Confirm `socket-message-effects.js` imports `LOADER_REQUESTS` from `session-loaders.js` and does not define its own loader vocabulary.
- [ ] Confirm `App.jsx` still owns concrete HTTP route calls, reducer dispatches, terminal summary loading, task/artifact refreshes, and render composition.
- [ ] Confirm docs explicitly say this is GUI app-shell work only.
