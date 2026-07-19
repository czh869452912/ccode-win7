# Adaptive GUI Protocol And Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one independently installable T3-style GUI shell that connects unchanged to base, C/C++, and non-C agents through versioned protocols and safe declarative capability projections.

**Architecture:** Replace the monolithic GUI protocol with four documents: app shell, IDE services, agent capabilities, and session state. Keep executable UI code in the GUI wheel; agents may declare data, labels, commands, and allowlisted read-only panels, but never JavaScript, Python, HTML, URLs, imports, or renderer code. Generate Python and JavaScript contract constants from one committed schema and validate every bootstrap before state mutation.

**Tech Stack:** Python 3.8 dataclasses and standard-library JSON, FastAPI Host routes, React 18, Node test runner, Vite, Playwright, uv workspace wheels.

---

## Target Boundaries

```text
packages/embedagent-protocol/src/embedagent_protocol/
  app_shell.py
  ide_services.py
  agent_capabilities.py
  session_protocol.py
  events.py
  validation.py
  schema/gui-protocol-v2.json

packages/embedagent-gui/
  pyproject.toml
  src/embedagent_gui/
    backend/
    launcher.py
    static/
    webapp/
      src/protocol/generated-contract.js
      src/protocol/validate-document.js
      src/session-runtime/protocol-normalizer.js
      src/session-runtime/declarative-surfaces.js
```

The four top-level protocol identifiers are:

- `gui_app_shell_v2`
- `gui_ide_services_v1`
- `agent_capabilities_v2`
- `agent_session_v2`

### Task 1: Add Failing Protocol Separation Contracts

**Files:**
- Delete after serializer migration: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`
- Create: `tests/test_gui_protocol_v2.py`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_gui_protocol_projection.py`

- [ ] **Step 1: Write document ownership tests**

Create `tests/test_gui_protocol_v2.py`:

```python
import json

from embedagent_protocol import (
    AgentCapabilityDocument,
    AppShellDocument,
    IdeCapabilityDocument,
    SessionBootstrapDocument,
)


def test_protocol_documents_have_disjoint_truth():
    app = AppShellDocument.empty(product_name="Tests")
    ide = IdeCapabilityDocument.empty()
    agent = AgentCapabilityDocument.empty(agent_id="tests.base")
    session = SessionBootstrapDocument.empty(
        session_id="session-1",
        capability_revision="cap-1",
    )

    app_payload = app.to_dict()
    ide_payload = ide.to_dict()
    agent_payload = agent.to_dict()
    session_payload = session.to_dict()

    assert app_payload["protocol"] == "gui_app_shell_v2"
    assert ide_payload["protocol"] == "gui_ide_services_v1"
    assert agent_payload["protocol"] == "agent_capabilities_v2"
    assert session_payload["protocol"] == "agent_session_v2"
    assert "history" not in app_payload
    assert "tools" not in app_payload
    assert "history" not in agent_payload
    assert "capabilities" not in session_payload
    assert session_payload["capabilityRevision"] == "cap-1"


def test_empty_agent_document_does_not_invent_mode_or_workflow():
    payload = AgentCapabilityDocument.empty(agent_id="tests.base").to_dict()
    assert payload["modes"] == []
    assert payload["commands"] == []
    assert payload["workflowPackages"] == []
    assert payload["surfaces"] == []
    assert "chat" not in json.dumps(payload).lower()
    assert "explore" not in json.dumps(payload).lower()
```

- [ ] **Step 2: Add old-contract deletion assertions**

Update the existing protocol tests to require that `app_protocol.py`,
`AgentApplicationDescriptor`, and the global `/api/sessions/capabilities`
route are absent after this plan. `CoreInterface` is deleted by Phase 6 after
all frontend callers use narrow Host ports. Do not preserve protocol import
aliases.

- [ ] **Step 3: Run the protocol tests and verify they fail**

```bash
uv run pytest tests/test_gui_protocol_v2.py tests/test_agent_app_protocol.py tests/test_gui_protocol_projection.py -v
```

Expected: FAIL because the separated documents do not exist.

- [ ] **Step 4: Commit red protocol contracts**

```bash
git add tests/test_gui_protocol_v2.py tests/test_agent_app_protocol.py tests/test_gui_protocol_projection.py
git commit -m "test: define adaptive gui protocol boundaries"
```

### Task 2: Split Protocol Models And Generate One Shared Contract

**Files:**
- Create: `packages/embedagent-protocol/src/embedagent_protocol/app_shell.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/ide_services.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/agent_capabilities.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/session_protocol.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/events.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/validation.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/schema/gui-protocol-v2.json`
- Create: `scripts/generate-gui-protocol.py`
- Create: `src/embedagent/frontend/gui/webapp/src/protocol/generated-contract.js`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `tests/test_gui_protocol_v2.py`

- [ ] **Step 1: Define strict outer envelopes**

Every document must carry `protocol`, integer `schemaVersion`, `revision`, and
its owned payload. Required identity and sequence fields are strict; unknown
presentation metadata is retained only inside explicit `metadata` mappings.
All dataclasses are frozen and copy incoming mappings/lists into immutable
tuples or fresh dictionaries.

Use these public constructors:

```python
AgentCapabilityDocument.empty(agent_id="tests.base")
AppShellDocument.empty(product_name="Tests")
IdeCapabilityDocument.empty()
SessionBootstrapDocument.empty(session_id="session-1", capability_revision="cap-1")
validate_protocol_document(payload, expected_protocol="agent_session_v2")
```

Agent capabilities own only:

- agent identity and presentation;
- declared modes and commands;
- tool presentation metadata;
- workflow package descriptors and generic workflow read-model schema ids;
- allowlisted read-only surface descriptors;
- empty-state copy.

They do not own permissions, active-tool decisions, session history, IDE
availability, app workspaces, or executable handlers.

Agent command dispatch is limited to `session.message` and `mode.set` records
validated by Host. It cannot call a tool directly, approve permission, answer
an interaction, invoke an app/IDE handler, open a URL, or name executable code.
App-shell and IDE command handler keys come only from their trusted Host
documents and still resolve through a fixed GUI handler registry.

Update the current GUI protocol serializer in the same step to consume the new
document models. Delete `app_protocol.py` and its old DTO exports now that all
in-repository serializers/tests use the split modules; do not keep re-exports.

- [ ] **Step 2: Commit the canonical schema**

`gui-protocol-v2.json` defines the four document envelopes, WebSocket event
envelope, mode, command, tool, activity, and read-only surface records. Reject
these keys recursively in agent-supplied capability metadata and surface
descriptors:

```text
script, javascript, python, html, import, module, entrypoint, factory,
builder_path, url, api_key, token, secret, password, credential
```

The schema permits only these agent surface renderer keys:

```text
summary, key_value, list, task_list, diagnostics, markdown
```

- [ ] **Step 3: Generate JavaScript constants deterministically**

`scripts/generate-gui-protocol.py` reads the schema with the standard library
and initially writes the current GUI path `generated-contract.js` with sorted
protocol names, required fields,
forbidden metadata keys, renderer keys, and the schema SHA-256. It accepts
`--check` and exits non-zero when the committed file differs. The generated
file has LF line endings and a trailing newline.

- [ ] **Step 4: Run generation and protocol tests**

```bash
uv run python scripts/generate-gui-protocol.py
uv run python scripts/generate-gui-protocol.py --check
uv run pytest tests/test_gui_protocol_v2.py tests/test_agent_app_protocol.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit split protocol ownership**

```bash
git add packages/embedagent-protocol src/embedagent/frontend/gui scripts/generate-gui-protocol.py tests
git commit -m "refactor: split gui protocol documents"
```

### Task 3: Move The GUI Into An Independent Distribution

**Files:**
- Create: `packages/embedagent-gui/pyproject.toml`
- Move: `src/embedagent/frontend/gui/` to `packages/embedagent-gui/src/embedagent_gui/`
- Delete: `src/embedagent/frontend/__init__.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock` through uv only
- Create: `tests/test_gui_distribution.py`
- Modify: GUI imports in `src/`, `packages/`, `tests/`, scripts, and active docs

- [ ] **Step 1: Add distribution and import guards**

Create `tests/test_gui_distribution.py` to assert:

- project name is `embedagent-gui`;
- Python requirement is `>=3.8,<3.9`;
- runtime dependencies are exactly `embedagent-protocol==0.1.0`,
  `pywebview>=4.0`, `fastapi>=0.100`,
  `uvicorn[standard]>=0.23`, and `websockets>=11.0`;
- GUI source never imports `embedagent_core`, `embedagent_host`, or
  `embedagent_workflow_cpp`;
- the old `src/embedagent/frontend` path is absent;
- wheel contents include backend Python, webapp source needed for development,
  and generated static assets.

- [ ] **Step 2: Move with history and update imports**

```bash
New-Item -ItemType Directory -Force packages/embedagent-gui/src | Out-Null
git mv src/embedagent/frontend/gui packages/embedagent-gui/src/embedagent_gui
```

Rename imports from `embedagent.frontend.gui` to `embedagent_gui`. The root
product launcher may import `embedagent_gui.launcher` and adapt Host to the GUI
port; Core, Host, Protocol, Composition, and workflow packages must not import
GUI.

Update `scripts/generate-gui-protocol.py` in the same move so its output target
is `packages/embedagent-gui/src/embedagent_gui/webapp/src/protocol/generated-contract.js`.

- [ ] **Step 3: Add GUI package metadata and regenerate the lock**

Include package data for `static/**`, the protocol schema hash artifact, and
the WebView2 loader assets already required by the product. Add the wheel to
the uv workspace and root product dependencies, then run:

```bash
uv lock
uv sync
```

Expected: both commands exit zero.

- [ ] **Step 4: Run GUI Python tests after the move**

```bash
uv run pytest tests/test_gui_distribution.py tests/test_gui_backend_api.py tests/test_gui_app_shell.py tests/test_gui_runtime.py -v
```

Expected: PASS after import rewrites.

- [ ] **Step 5: Commit GUI distribution extraction**

```bash
git add packages/embedagent-gui src tests scripts pyproject.toml uv.lock docs
git commit -m "refactor: extract independent gui distribution"
```

### Task 4: Expose Separate Backend Documents And Ordered Events

**Files:**
- Create: `packages/embedagent-gui/src/embedagent_gui/backend/gui_host_port.py`
- Modify: `packages/embedagent-gui/src/embedagent_gui/backend/routes_app.py`
- Modify: `packages/embedagent-gui/src/embedagent_gui/backend/routes_sessions.py`
- Create: `packages/embedagent-gui/src/embedagent_gui/backend/routes_ide.py`
- Modify: `packages/embedagent-gui/src/embedagent_gui/backend/protocol_payloads.py`
- Modify: `packages/embedagent-gui/src/embedagent_gui/backend/session_events.py`
- Modify: `tests/test_gui_backend_api.py`
- Modify: `tests/test_gui_session_events.py`

- [ ] **Step 1: Define the narrow GUI Host port**

`GuiHostPort` exposes only app-shell projection, IDE service projection,
session bootstrap, session capability projection, message submission,
interaction reply, cancellation, and lifecycle commands. It is GUI-owned and
implemented by a root-product adapter over Host; neither GUI nor Host imports
the other. It does not expose `QueryEngine`, `Agent`, extension managers,
permission policy, or transcript storage.

- [ ] **Step 2: Implement the four endpoint families**

Use these exact routes:

```text
GET /api/app/bootstrap
GET /api/ide/capabilities
GET /api/sessions/{session_id}/bootstrap
GET /api/sessions/{session_id}/capabilities
```

Session bootstrap returns `capabilityRevision` but not the capability body.
The capability route returns the matching revision. If capabilities change
between the two requests, return the newest document and let the renderer
atomically replace its session capability model.

Delete `/api/sessions/capabilities`. Do not add a compatibility redirect.

- [ ] **Step 3: Version and order WebSocket messages**

Every live message becomes:

```json
{
  "protocol": "agent_session_event_v2",
  "schemaVersion": 2,
  "sessionId": "session-1",
  "sequence": 12,
  "eventId": "event-12",
  "kind": "activity.appended",
  "payload": {}
}
```

Sequence is monotonic per session. Renderer gaps trigger one session bootstrap
reload; duplicate or older sequence values are ignored. Raw interaction
requests continue to drive blocking controls only and never become a second
history source.

- [ ] **Step 4: Run backend protocol tests**

```bash
uv run pytest tests/test_gui_backend_api.py tests/test_gui_protocol_projection.py tests/test_gui_session_events.py tests/test_session_history.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit backend separation**

```bash
git add packages/embedagent-gui packages/embedagent-host tests
git commit -m "refactor: separate gui backend protocols"
```

### Task 5: Validate Documents Before Renderer State Mutation

**Files:**
- Create: `packages/embedagent-gui/src/embedagent_gui/webapp/src/protocol/validate-document.js`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/session-runtime/protocol-normalizer.js`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/app-runtime/session-loaders.js`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/app-runtime/initial-app-load-controller.js`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/store.js`
- Create: `packages/embedagent-gui/src/embedagent_gui/webapp/test/protocol-v2.test.mjs`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add renderer validation tests**

Test all four valid empty documents, wrong protocol, missing required fields,
forbidden metadata, unknown surface renderer, stale session sequence, and a
capability revision change. Assert invalid documents produce structured
diagnostics and leave prior state unchanged.

- [ ] **Step 2: Remove renderer synthesis**

Delete `commandFromMode()`. Modes no longer synthesize `/mode` commands,
labels, command ids, or visibility. Only backend-declared commands appear in
the composer and command palette. Preserve an absent current mode as `""` and
an absent workflow as `{}`.

Generic fallbacks remain presentation-only:

- unknown tool: escaped tool name, generic wrench icon, generic detail body;
- unknown activity: system-neutral row with escaped kind and safe payload;
- unknown color token: neutral info token;
- unknown surface renderer: hidden plus diagnostic.

- [ ] **Step 3: Load session and capabilities atomically**

The activation controller requests session bootstrap and session capabilities,
validates both, checks `capabilityRevision`, then dispatches one
`session_activated` action. No intermediate state may render the new session
with the previous agent's modes, tools, commands, or surfaces.

- [ ] **Step 4: Run renderer tests**

```bash
cd packages/embedagent-gui/src/embedagent_gui/webapp
npm test
cd ../../../../..
```

Expected: PASS.

- [ ] **Step 5: Commit protocol validation**

```bash
git add packages/embedagent-gui
git commit -m "refactor: validate gui protocol before state updates"
```

### Task 6: Add Safe Declarative Agent Surfaces

**Files:**
- Create: `packages/embedagent-gui/src/embedagent_gui/webapp/src/session-runtime/declarative-surfaces.js`
- Create: `packages/embedagent-gui/src/embedagent_gui/webapp/src/components/workbench/DeclarativeAgentSurface.jsx`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/workbench/surfaces.js`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/components/SurfacePanel.jsx`
- Create: `packages/embedagent-gui/src/embedagent_gui/webapp/test/declarative-surfaces.test.mjs`
- Modify: `tests/test_gui_protocol_v2.py`

- [ ] **Step 1: Define surface descriptors as data selectors**

An agent surface descriptor contains only:

```json
{
  "id": "workflow.tasks",
  "placement": "right",
  "title": "Tasks",
  "rendererKey": "task_list",
  "dataPath": ["workflow", "items"],
  "order": 30,
  "emptyLabel": ""
}
```

`dataPath` may read only from the validated session snapshot/read models. It
cannot access global objects, call functions, traverse prototype keys, fetch a
URL, execute commands, or invoke tools.

- [ ] **Step 2: Implement the fixed renderer registry**

Implement six GUI-owned renderers: `summary`, `key_value`, `list`,
`task_list`, `diagnostics`, and safe Markdown. Markdown disables raw HTML,
external media, and clickable external URLs; workspace-local file references
use the existing safe file-link path. All values are bounded in size before rendering. IDE surfaces
such as terminal, preview, source control, files, and diff remain declared by
the IDE/app-shell documents and cannot be requested through agent capability
metadata.

- [ ] **Step 3: Add safety and degradation tests**

Test valid task and diagnostics surfaces, missing data, unknown renderer,
prototype-path segments, forbidden metadata, oversized records, and agent
attempts to declare terminal or preview. Unknown/unsafe surfaces stay hidden
and emit diagnostics; the rest of the session remains usable.

- [ ] **Step 4: Run surface tests and build**

```bash
cd packages/embedagent-gui/src/embedagent_gui/webapp
npm test
npm run build
cd ../../../../..
```

Expected: PASS and generated static assets are updated.

- [ ] **Step 5: Commit declarative surfaces**

```bash
git add packages/embedagent-gui tests/test_gui_protocol_v2.py
git commit -m "feat: render safe agent-declared surfaces"
```

### Task 7: Prove One GUI Against Base, C/C++, And Non-C Agents

**Files:**
- Create: `tests/fixtures/gui_agents/base.json`
- Create: `tests/fixtures/gui_agents/cpp.json`
- Create: `tests/fixtures/gui_agents/python.json`
- Create: `tests/test_gui_agent_matrix.py`
- Create: `docs/t3-gui-parity-matrix.md`
- Create: `packages/embedagent-gui/src/embedagent_gui/webapp/test/agent-adaptation.test.mjs`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/app-runtime/visual-debug-controller.js`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/app-runtime/visual-debug-fixtures.js`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/index.html`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/build.mjs`
- Modify: `packages/embedagent-gui/src/embedagent_gui/launcher.py`

- [ ] **Step 1: Lock the T3 parity matrix**

Read `reference/t3code` as the behavioral reference and record implemented,
missing, and intentionally excluded behavior for thread navigation, workbench
header, timeline rows/folds, changed-files and diff flows, composer and command
menu, permission/user-input controls, right-panel tabs, files/file preview,
source control, browser preview, terminal/bottom drawer, keyboard commands,
resize behavior, reconnect, and empty/loading/error states.

Every included row names the reference source, current GUI owner, protocol
input, automated test, and desktop/mobile screenshot state. Reference source is
never a runtime dependency and does not override Win7/WebView2 constraints.

- [ ] **Step 2: Add three complete fixture document sets**

Each fixture contains app, IDE, capabilities, session bootstrap, and ordered
events. The base fixture has no modes/workflow/surfaces; C/C++ declares the
current workflow and task surface; Python declares unrelated modes, a `pytest`
tool, and diagnostics surface. All three use the same GUI build hash.

- [ ] **Step 3: Add cross-agent assertions**

For each fixture assert:

- visible commands, modes, tools, and surfaces equal declarations;
- base contains no C/C++, Clang, recipe, task, or default mode copy;
- Python contains no C/C++ labels or tool names;
- unknown tool/activity/surface values degrade safely;
- switching agents atomically removes the previous catalog and panels;
- no renderer source change or product-specific import is required.

Also require existing `workbench-parity-model`, timeline, diff, composer,
right-panel, terminal, source-control, and visual-language suites to pass for
all shared T3 shell behavior in the parity matrix.

- [ ] **Step 4: Remove product-name and mode defaults**

Set `document.title` only from validated app-shell `productName`. Preserve a
missing name as empty. Remove `EmbedAgent` from runtime window-title fallbacks
and remove `explore` from visual-debug controller defaults. Product-specific
names and C/C++ tool values may remain only inside explicit product fixtures,
product definitions, and the C/C++ workflow package.

- [ ] **Step 5: Run Python and JavaScript matrix tests**

```bash
uv run pytest tests/test_gui_agent_matrix.py tests/test_non_c_workflow_capabilities.py tests/test_gui_protocol_projection.py -v
cd packages/embedagent-gui/src/embedagent_gui/webapp
npm test
npm run build
cd ../../../../..
```

Expected: PASS.

- [ ] **Step 6: Run T3 parity and responsive browser smoke**

Start the packaged GUI backend with the fixture Host port and use Playwright at
`1440x900`, `1024x768`, and `390x844`. Capture every required parity-matrix
state plus base, C/C++, Python, unknown-tool, and reconnect states. Assert the
T3 workbench structure and interactions remain present, and assert no overlap,
blank root, console error, or horizontal page overflow. Record intentional
visual differences required by WebView2 109 or the product's offline model.

- [ ] **Step 7: Commit the adaptation and T3 parity matrix**

```bash
git add packages/embedagent-gui tests scripts docs/t3-gui-parity-matrix.md
git commit -m "test: prove gui parity across agent products"
```

### Task 8: Close GUI Documentation And Gates

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `scripts/check-python-distributions.py`
- Modify: `Makefile`

- [ ] **Step 1: Replace active protocol documentation**

Document the four documents, endpoint ownership, revision/sequence behavior,
safe renderer allowlist, unknown-value degradation, and explicit prohibition
on agent-supplied UI code. Delete v1 examples instead of documenting both.

- [ ] **Step 2: Run the Phase 5 Python gate**

```bash
uv run python scripts/generate-gui-protocol.py --check
uv run pytest tests/test_gui_protocol_v2.py tests/test_gui_distribution.py tests/test_gui_backend_api.py tests/test_gui_protocol_projection.py tests/test_gui_session_events.py tests/test_gui_agent_matrix.py tests/test_non_c_workflow_capabilities.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
uv build --all-packages
uv run python scripts/check-python-distributions.py --dist-dir dist
```

Expected: all commands exit zero.

- [ ] **Step 3: Run the Phase 5 GUI gate**

```bash
cd packages/embedagent-gui/src/embedagent_gui/webapp
npm test
npm run build
cd ../../../../..
```

Expected: PASS and generated static assets are committed.

- [ ] **Step 4: Commit Phase 5 closeout**

```bash
git add README.md AGENTS.md docs scripts Makefile packages/embedagent-gui
git commit -m "docs: define adaptive gui architecture"
```

## Phase 5 Exit Criteria

- `embedagent-gui` installs independently from Core and workflow packages.
- The same committed GUI build connects to base, C/C++, and Python fixtures.
- Session activation never exposes stale capabilities from another agent.
- Missing mode/workflow/product copy stays empty throughout the renderer.
- Agent-provided data can use only the six safe read-only renderers.
- Unknown tools, activities, and surfaces do not crash or execute code.
- Python, JavaScript, build, and responsive browser gates pass.
