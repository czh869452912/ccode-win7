# T3 Current GUI Parity And Agent Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Continue the existing GUI parity work until the current T3 Code UX and client-runtime boundaries are the reference, while one generic Agent App Protocol adapter supports both base and specialized Agents.

**Architecture:** Keep React 18, Vite 5, pywebview, WebView2 109, and the offline bundle. Normalize backend traffic in one adapter, feed T3-shaped client reducers, and keep presentation components independent of Agent Core, Host, workflows, and tool policy.

**Tech Stack:** React 18, JavaScript ES modules, Vite 5, Node test harness, Python 3.8, FastAPI/WebSocket, JSON-safe Agent App Protocol, existing visual debug runner.

---

## Delivery Order

Execute these as independently testable packages: P4.0 ledger, P4.3 protocol
adapter, P4.2 client runtime, P4.1/P4.4 T3 surfaces, P4.5 dynamic Agents, and
P4.6 release gates. Each package must pass focused tests and keep the GUI
buildable before the next package starts.

## Task 1: Pin The T3 Difference Ledger

**Files:**
- Create: docs/guides/t3-gui-parity-ledger.md
- Reference: docs/superpowers/specs/2026-07-18-t3-current-gui-parity-and-agent-adapter-design.md
- Reference: reference/t3code/apps/web/src/
- Reference: reference/t3code/packages/client-runtime/src/
- Reference: reference/t3code/packages/contracts/src/

- [ ] **Step 1: Capture the reference and write the table**

Run:

~~~powershell
git -C reference/t3code log -1 --date=iso --format="%H%n%ad%n%s"
~~~

Record commit 2318e00270203780b72efbbcffce92e907312027, date, subject, and rows
for Sidebar, ChatView/timeline, Composer, right panel, terminal/source
control, thread state, shell state, and app/session contract. Mark cloud,
Relay, mobile, Electron, remote environment, and provider-marketplace features
as excluded infrastructure.

- [ ] **Step 2: Document re-baselining and verify**

Document:

~~~powershell
git -C reference/t3code log -1 --date=iso --format="%H%n%ad%n%s"
rg --files reference/t3code/apps/web/src reference/t3code/packages/client-runtime/src reference/t3code/packages/contracts/src
~~~

Then run:

~~~powershell
git diff --check
rg -n "2318e002|excluded infrastructure" docs/guides/t3-gui-parity-ledger.md
~~~

- [ ] **Step 3: Commit**

~~~powershell
git add docs/guides/t3-gui-parity-ledger.md
git commit -m "docs: add T3 GUI parity ledger"
~~~

## Task 2: Isolate The Agent App Protocol Adapter

**Files:**
- Create: src/embedagent/frontend/gui/webapp/src/client-runtime/protocol-adapter.js
- Create: src/embedagent/frontend/gui/webapp/test/protocol-adapter.test.mjs
- Modify: src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js
- Modify: src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js
- Modify: src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js
- Modify: src/embedagent/frontend/gui/webapp/src/App.jsx
- Test: src/embedagent/frontend/gui/webapp/test/run-tests.mjs

- [ ] **Step 1: Write and run the failing adapter test**

Export runProtocolAdapterTests; record URL, method, and JSON body:

~~~js
const requests = [];
const adapter = createAgentAppProtocolAdapter({
  fetchJson: async (url, options) => {
    requests.push({ url, options });
    return { session_id: "s-1" };
  },
});
const payload = await adapter.loadSessionBootstrap("s-1");
assert.equal(payload.session_id, "s-1");
assert.equal(requests[0].url, "/api/sessions/s-1/bootstrap");
await adapter.sendSessionMessage("s-1", "hello");
assert.equal(requests[1].options.body, JSON.stringify({ text: "hello" }));
~~~

Run before implementation:

~~~powershell
node --input-type=module -e "import('./test/protocol-adapter.test.mjs').then((m) => m.runProtocolAdapterTests())"
~~~

Expected result: FAIL because the module is absent.

- [ ] **Step 2: Implement and integrate the adapter**

Implement createAgentAppProtocolAdapter with loadAppBootstrap,
loadSessionBootstrap, listSessions, loadSessionCapabilities,
sendSessionMessage, and respondToInteraction. Keep URL encoding and JSON
request construction here. Do not add Agent, workflow, tool-name, or
slash-command branches. Construct the adapter once in App.jsx and pass its
methods to existing loaders, session controllers, and interaction response
controllers. Remove duplicate URL construction from those controllers.

- [ ] **Step 3: Register, test, and commit**

Register runProtocolAdapterTests in test/run-tests.mjs. Run:

~~~powershell
node --input-type=module -e "import('./test/protocol-adapter.test.mjs').then((m) => m.runProtocolAdapterTests())"
npm test
~~~

Commit:

~~~powershell
git add src/embedagent/frontend/gui/webapp/src/client-runtime src/embedagent/frontend/gui/webapp/src/app-runtime src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: isolate GUI Agent App Protocol adapter"
~~~

## Task 3: Compose The T3-Shaped Client Runtime Reducer

**Files:**
- Create: src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js
- Create: src/embedagent/frontend/gui/webapp/test/runtime-reducer.test.mjs
- Modify: src/embedagent/frontend/gui/webapp/src/store.js
- Modify: src/embedagent/frontend/gui/webapp/src/App.jsx
- Reuse: src/embedagent/frontend/gui/webapp/src/app-shell/reducer.js
- Reuse: src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js
- Reuse: src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js
- Reuse: src/embedagent/frontend/gui/webapp/src/session-runtime/thread-state.js

- [ ] **Step 1: Lock delegation behavior**

Export runRuntimeReducerTests and assert that an approval.requested event
updates activity and thread state. Also assert that App.jsx imports
runtimeReducer and has no case session_event branch. Run the direct module test
before adding the module and expect FAIL.

- [ ] **Step 2: Implement reducer composition**

Use existing reducer return shapes:

~~~js
import { reduceAppShellState } from "../app-shell/reducer.js";
import { reduceActivityState } from "../session-runtime/activity-reducer.js";
import { reduceWorkbenchState } from "../workbench/surfaces.js";

export function runtimeReducer(state, action) {
  let next = { ...state, ...reduceActivityState(state, action) };
  next = { ...next, app: reduceAppShellState(next.app, action) };
  next = { ...next, workbench: reduceWorkbenchState(next.workbench, action) };
  return next;
}
~~~

Add existing thread, composer, terminal, source-control, and run-output
delegates from store.js without creating a second session-history source.
Preserve empty mode and workflow values.

- [ ] **Step 3: Switch App, test, and commit**

Import runtimeReducer in App.jsx. Keep initialState in store.js until all
imports migrate. Remove the old reducer export only after this command shows no
runtime import of reducer:

~~~powershell
rg -n 'from "./store.js"' src/embedagent/frontend/gui/webapp/src
node --input-type=module -e "import('./test/runtime-reducer.test.mjs').then((m) => m.runRuntimeReducerTests())"
npm test
~~~

Commit:

~~~powershell
git add src/embedagent/frontend/gui/webapp/src/client-runtime src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: compose GUI state through client runtime"
~~~

## Task 4: Advance Current T3 UX Parity

**Files:**
- Modify: src/embedagent/frontend/gui/webapp/src/components/workbench/AppSidebarLayout.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/Composer.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js
- Modify: src/embedagent/frontend/gui/webapp/src/styles.css
- Test: existing source/model tests under src/embedagent/frontend/gui/webapp/test/

- [ ] **Step 1: Record upstream behavior**

For every changed surface, add the current T3 source path to the ledger.
Primary references are Sidebar.tsx, ChatView.tsx, chat/ChatComposer.tsx,
chat/MessagesTimeline.tsx, RightPanelTabs.tsx, ThreadTerminalDrawer.tsx, and
GitActionsControl.tsx.

- [ ] **Step 2: Port three coherent slices**

Update shell/navigation files together; then timeline/composer files; then
right-panel, terminal, and source-control files. Copy T3 hierarchy, spacing,
focus behavior, and responsive layout. Keep labels from app-shell descriptors,
activity panels from activity records, and surface callbacks from existing
controllers. Components must not call backend routes.

- [ ] **Step 3: Test, inspect, and commit**

From src/embedagent/frontend/gui/webapp:

~~~powershell
npm test
npm run visual:gui -- --scenario responsive,timeline,file,diff,terminal,source-control
~~~

Inspect shell hierarchy, timeline density, composer placement, right-panel
behavior, terminal drawer behavior, and narrow viewport overlap. Commit each
coherent slice:

~~~powershell
git add src/embedagent/frontend/gui/webapp/src/components src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test
git commit -m "feat: advance T3 workbench parity"
~~~

## Task 5: Verify Dynamic Agents And Remove Renderer Hardcoding

**Files:**
- Create: src/embedagent/frontend/gui/webapp/test/dynamic-agent-capabilities.test.mjs
- Create: tests/test_gui_dynamic_agent_capabilities.py
- Modify: src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx
- Modify: src/embedagent/frontend/gui/webapp/src/workbench/commands.js
- Modify: src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js
- Modify: src/embedagent/frontend/gui/webapp/src/app-shell/model.js
- Modify: src/embedagent/frontend/gui/webapp/src/app-runtime/app-capability-model.js
- Modify: src/embedagent/frontend/gui/webapp/src/session-runtime/session-capability-model.js
- Modify: src/embedagent/frontend/gui/webapp/src/styles.css
- Test: src/embedagent/frontend/gui/webapp/test/run-tests.mjs

- [ ] **Step 1: Add generic fixtures and projection tests**

Use a base fixture with no modes/tools and a specialized fixture with generic
mode, command, tool, and surface descriptors. Assert product name, empty-state
copy, modes, commands, tools, and surfaces come from payloads; a missing
product name remains empty.

- [ ] **Step 2: Remove Agent-specific renderer branches**

Use app-shell metadata, empty-state descriptors, command descriptors, and tool
catalog presentation metadata. Remove branches keyed by run_recipe,
report_quality_v2, task_status, record_failing_evidence, bash, read_file,
write_file, and C/C++ mode names. Keep fixture literals only in
app-runtime/visual-debug-fixtures.js.

- [ ] **Step 3: Add backend and forbidden-literal tests**

In tests/test_gui_dynamic_agent_capabilities.py, pass both fixtures through
existing serializers and assert generic fields survive without importing a
workflow package. Scan production renderer files, excluding tests and visual
fixtures, for:

~~~text
run_recipe|report_quality_v2|record_failing_evidence|task_status
C/C++|Clang|embedded C
~~~

Report file and line for every match.

- [ ] **Step 4: Run and commit**

From the repository root:

~~~powershell
node --input-type=module -e "import('./src/embedagent/frontend/gui/webapp/test/dynamic-agent-capabilities.test.mjs').then((m) => m.runDynamicAgentCapabilityTests())"
uv run pytest tests/test_gui_dynamic_agent_capabilities.py -v
~~~

Run npm test from src/embedagent/frontend/gui/webapp, then commit:

~~~powershell
git add src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test tests/test_gui_dynamic_agent_capabilities.py
git commit -m "test: verify GUI adapts to generic Agent capabilities"
~~~

## Task 6: Run The Phase 4 GUI Gate

**Files:**
- Modify: generated assets under src/embedagent/frontend/gui/static/ when the
  build changes them.
- Reference: all files changed by Tasks 1-5.

- [ ] **Step 1: Build and test**

From src/embedagent/frontend/gui/webapp:

~~~powershell
npm test
npm run build
~~~

Expected result: PASS and generated assets change only under the known static
directory.

- [ ] **Step 2: Run Python and architecture gates**

From the repository root:

~~~powershell
uv run pytest tests/test_gui_app_shell.py tests/test_gui_protocol_projection.py tests/test_gui_session_events.py tests/test_gui_dynamic_agent_capabilities.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
~~~

- [ ] **Step 3: Run visual and compatibility checks**

~~~powershell
node scripts/gui-visual-debug.mjs --scenario responsive,timeline,file,diff,terminal,source-control --output "$env:TEMP\embedagent-t3-phase4"
git diff --check
uv run --locked python scripts/lint.py
git status --short
~~~

Confirm no new dependency requires Node 24, React 19, Electron, an online
service, or a non-bundled executable. Real Win7/WebView2 bundle smoke remains
release evidence and is not replaced by local tests.

- [ ] **Step 4: Commit the verified phase**

~~~powershell
git add src/embedagent/frontend/gui/static src/embedagent/frontend/gui/webapp docs/guides tests
git commit -m "feat: complete current T3 GUI parity phase"
~~~

## Self-Review

Task coverage is P4.0 ledger (Task 1), P4.3 adapter (Task 2), P4.2 runtime
(Task 3), P4.1/P4.4 UX (Task 4), P4.5 dynamic adaptation (Task 5), and P4.6
gates (Task 6). No task imports T3 cloud/Relay/mobile/Electron/React 19/Node 24
runtime dependencies or changes Agent Core, workflow execution, permissions,
or transcript truth.
