# Strict Frontend Protocol Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one strict workflow-neutral wire schema and make GUI `ClientRuntime` plus TUI `TerminalRuntime` the only shell effect owners.

**Architecture:** `embedagent-protocol` defines current `snake_case`, versioned DTOs. The GUI protocol adapter validates wire data and maps it once into JavaScript view models; controllers call named protocol methods and never know endpoint paths. The TUI runtime exposes the same operation and envelope semantics over the in-process Host boundary, with renderers receiving only state projections and actions.

**Tech Stack:** Python 3.8 dataclasses and stdlib JSON, `embedagent-protocol`, `embedagent-host`, FastAPI, React 18 JavaScript, WebSocket, prompt_toolkit, pytest, Node test runner.

---

## Preconditions And File Responsibilities

This is Stage 2 of the frontend convergence design. Start only after `2026-08-03-frontend-transport-correctness.md` is merged and its `event_cursor` tests are green.

- `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`: strict app, capability, thread, session bootstrap, and shell DTOs.
- `src/embedagent/frontend/gui/backend/protocol_payloads.py`: constructs protocol DTOs; no casing aliases or frontend defaults.
- `src/embedagent/frontend/gui/webapp/src/client-runtime/http-transport.js`: sole JavaScript `fetch` owner.
- `src/embedagent/frontend/gui/webapp/src/client-runtime/socket-transport.js`: sole JavaScript `WebSocket` owner.
- `src/embedagent/frontend/gui/webapp/src/client-runtime/protocol-adapter.js`: sole JavaScript endpoint catalog and wire validation boundary.
- `src/embedagent/frontend/gui/webapp/src/client-runtime/client-runtime.js`: GUI operation lifecycle, controller composition, state/effect dispatch, and close.
- `src/embedagent/frontend/tui/runtime.py`: TUI operation lifecycle, bootstrap/event cursor state, and Host calls.
- React and prompt_toolkit files are renderer consumers. They must not import Host packages, call endpoints, or invoke adapter methods directly.

Current wire keys are `snake_case`. Internal JavaScript view-model keys may be camelCase only after successful validation in the protocol adapter. This plan deletes alternate readers in the same commit that changes producers.

### Task 1: Replace Mixed DTOs With A Strict Current Schema

**Files:**
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_protocol_versions.py`
- Modify: `tests/test_protocol_package_imports.py`

- [ ] **Step 1: Write failing strict DTO tests**

Define current DTO expectations in `tests/test_agent_app_protocol.py`:

```python
def test_session_bootstrap_uses_one_versioned_snake_case_shape():
    payload = SessionBootstrap(
        schema_version=1,
        event_cursor=4,
        thread=ThreadShell(
            id="s-1",
            title="Session",
            archived=False,
            current_mode="build",
            status="idle",
            updated_at="2026-08-03T00:00:00Z",
        ),
        snapshot={"session_id": "s-1", "workflow_state": {}},
        activities=[],
        capabilities=CapabilitySnapshot(schema_version=1),
    ).to_dict()

    assert payload["schema_version"] == 1
    assert payload["event_cursor"] == 4
    assert payload["thread"]["current_mode"] == "build"
    assert "currentMode" not in json.dumps(payload)
```

Add rejection tests for `schema_version=0`, `event_cursor=-1`, blank descriptor ids, unknown surface placements, blank renderer keys, and non-mapping `dispatch` values. Cross-record duplicate and reference checks belong to the Stage 3 compiler contract.

- [ ] **Step 2: Run the protocol tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_agent_app_protocol.py tests/test_protocol_versions.py tests/test_protocol_package_imports.py`

Expected: FAIL because current DTO output uses camelCase and has no strict `SessionBootstrap`.

- [ ] **Step 3: Define the current DTO set**

Keep these public dataclasses in `app_protocol.py` and export them from `embedagent_protocol.__init__`:

```python
@dataclass
class SurfaceDescriptor:
    id: str
    label: str
    placement: str
    renderer_key: str
    availability: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KeybindingDescriptor:
    command_id: str
    keys: str
    when: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineItemDescriptor:
    event_kind: str
    renderer_key: str
    priority: int = 0


@dataclass
class InteractionDescriptor:
    kind: str
    renderer_key: str


@dataclass
class ShellDescriptor:
    schema_version: int
    commands: List[CommandDescriptor] = field(default_factory=list)
    surfaces: List[SurfaceDescriptor] = field(default_factory=list)
    keybindings: List[KeybindingDescriptor] = field(default_factory=list)
    tool_presentations: List[ToolPresentation] = field(default_factory=list)
    timeline_items: List[TimelineItemDescriptor] = field(default_factory=list)
    interactions: List[InteractionDescriptor] = field(default_factory=list)


@dataclass
class SessionBootstrap:
    schema_version: int
    event_cursor: int
    thread: ThreadShell
    snapshot: Dict[str, Any]
    activities: List[Any]
    capabilities: CapabilitySnapshot
    workflow: Dict[str, Any] = field(default_factory=dict)
    integrity: Dict[str, Any] = field(default_factory=dict)
    plan: Optional[Dict[str, Any]] = None
    permission_context: Dict[str, Any] = field(default_factory=dict)
```

`AppBootstrap` contains `shell: ShellDescriptor` instead of parallel command/surface lists. `AppBootstrap`, `ShellDescriptor`, `CapabilitySnapshot`, and `SessionBootstrap` each carry `schema_version=1`. Every `to_dict()` emits field names exactly as declared: `icon_key`, `color_token`, `command_id`, `renderer_key`, `permission_category`, `workflow_packages`, `agent_application`, `agent_applications`, `current_mode`, `updated_at`, `pending_interaction`, `request_id`, `turn_id`, and `created_at`.

Use `__post_init__` to reject invalid schema versions, blank ids, placements outside `overlay|secondary`, blank renderer keys, malformed dispatch records, and negative cursors. Protocol validates structure only; the product compiler introduced in Stage 3 owns the supported renderer and dispatch-kind sets. Delete `ThreadDetailSnapshot`; `SessionBootstrap` is the only detailed bootstrap DTO.

- [ ] **Step 4: Run protocol tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_agent_app_protocol.py tests/test_protocol_versions.py tests/test_protocol_package_imports.py`

Expected: PASS and `embedagent-protocol` remains stdlib-only with no project dependencies.

- [ ] **Step 5: Commit strict DTO definitions**

```bash
git add packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py packages/embedagent-protocol/src/embedagent_protocol/__init__.py tests/test_agent_app_protocol.py tests/test_protocol_versions.py tests/test_protocol_package_imports.py
git commit -m "refactor: define strict frontend protocol dto"
```

### Task 2: Cut Producers And Consumers To The Same Wire Shape

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `tests/test_gui_protocol_projection.py`
- Modify: `tests/test_gui_backend_api.py`
- Create: `scripts/export-frontend-protocol-fixtures.py`
- Create: `tests/fixtures/frontend_protocol/app_bootstrap.json`
- Create: `tests/fixtures/frontend_protocol/session_bootstrap.json`
- Create: `tests/fixtures/frontend_protocol/session_event.json`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-envelope.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing producer tests for exact key sets**

Assert exact top-level contracts rather than key presence:

```python
self.assertEqual(
    set(payload),
    {
        "schema_version",
        "event_cursor",
        "thread",
        "snapshot",
        "history",
        "capabilities",
        "workflow",
        "plan",
        "permission_context",
    },
)
self.assertNotIn("agentApplication", json.dumps(payload))
self.assertNotIn("currentMode", json.dumps(payload))
```

Add endpoint assertions that app, capability, and session bootstrap responses all carry `schema_version == 1` and no legacy protocol wrapper.

- [ ] **Step 2: Run Python producer tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_gui_protocol_projection.py tests/test_gui_backend_api.py`

Expected: FAIL because serializers currently emit mixed casing and ad hoc extra fields.

- [ ] **Step 3: Construct DTOs directly in protocol serializers**

`serialize_app_bootstrap()` returns `AppBootstrap(...).to_dict()`. `serialize_session_bootstrap()` returns `SessionBootstrap(...).to_dict()`. Move all field selection into constructor arguments and delete `_camel_or_snake`, camelCase fallback reads, and post-serialization additions.

The serializer must fail on malformed protocol state instead of supplying UI labels or unknown defaults. Sanitization remains responsible only for excluding secrets and non-JSON values.

- [ ] **Step 4: Generate canonical cross-language fixtures**

The export script imports protocol DTOs, writes sorted UTF-8 JSON with a trailing newline, and accepts only `--output-dir`. Its entry point is:

```python
def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    write_fixture(args.output_dir, "app_bootstrap.json", build_app_bootstrap())
    write_fixture(args.output_dir, "session_bootstrap.json", build_session_bootstrap())
    write_fixture(args.output_dir, "session_event.json", build_session_event())
    return 0
```

Run: `uv run python scripts/export-frontend-protocol-fixtures.py --output-dir tests/fixtures/frontend_protocol`

Expected: three deterministic fixture files containing only `snake_case` keys.

- [ ] **Step 5: Write failing JavaScript strict-reader tests against the fixtures**

Read the committed fixtures and assert one conversion boundary:

```javascript
const session = normalizeSessionBootstrap(readFixture("session_bootstrap.json"));
assert.equal(session.schemaVersion, 1);
assert.equal(session.eventCursor, 4);
assert.equal(session.thread.currentMode, "build");
assert.throws(
  () => normalizeSessionBootstrap({ ...wireSession, eventCursor: 4 }),
  /invalid_session_bootstrap/,
);
```

Also reject unknown `schema_version`, a missing `event_cursor`, camelCase nested descriptor keys, and unknown enum values.

- [ ] **Step 6: Implement strict normalization and delete dual readers**

Replace `camelOrSnake` with required-field validators. A representative mapper is:

```javascript
function normalizeModeDescriptor(value) {
  const data = requiredRecord(value, "mode");
  return Object.freeze({
    id: requiredText(data.id, "mode.id"),
    label: requiredText(data.label, "mode.label"),
    description: optionalText(data.description),
    iconKey: optionalText(data.icon_key),
    colorToken: optionalText(data.color_token),
    commandId: requiredText(data.command_id, "mode.command_id"),
  });
}
```

Validate the full DTO before returning any view model. Delete support for `iconKey`, `commandId`, `agentApplication`, `workflowPackages`, `currentMode`, and every other alternate wire key.

- [ ] **Step 7: Run producer and consumer tests**

Run: `uv run python scripts/test-suite.py tdd tests/test_gui_protocol_projection.py tests/test_gui_backend_api.py`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with the Python-generated fixtures accepted and alternate casing rejected.

- [ ] **Step 8: Commit the synchronized cutover**

```bash
git add packages/embedagent-protocol/src/embedagent_protocol src/embedagent/frontend/gui/backend/protocol_payloads.py tests/test_gui_protocol_projection.py tests/test_gui_backend_api.py scripts/export-frontend-protocol-fixtures.py tests/fixtures/frontend_protocol src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-envelope.js src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: cut frontend wire protocol to snake case"
```

### Task 3: Establish Declared GUI Transport Owners

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/http-transport.js`
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/socket-transport.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/protocol-adapter.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/app-runtime/http-client.js`
- Test: `src/embedagent/frontend/gui/webapp/test/http-client.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/protocol-adapter.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/websocket-lifecycle.test.mjs`

- [ ] **Step 1: Write failing transport ownership tests**

Test JSON error normalization and abort propagation through `createHttpTransport({ fetchImpl })`. Test socket creation through `createSocketTransport({ WebSocketImpl, locationObject, timer })`. Assert `createAgentAppProtocolAdapter()` receives these two ports rather than raw globals.

```javascript
const protocol = createAgentAppProtocolAdapter({ http, socket });
await protocol.setSessionMode("s/1", "debug");
assert.deepEqual(http.calls[0], {
  path: "/api/sessions/s%2F1/mode",
  method: "POST",
  body: { mode: "debug" },
  signal: undefined,
});
```

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because the transport modules do not exist.

- [ ] **Step 3: Implement narrow HTTP and WebSocket ports**

`http-transport.js` exports only `createHttpTransport()` and contains the sole `fetch(` call. Its public method is:

```javascript
request({ path, method = "GET", body, signal } = {})
```

It owns JSON headers, response parsing, and normalized errors. `socket-transport.js` contains the sole `new WebSocket` expression and returns a closeable channel with `send`, `onMessage`, `onStateChange`, and `close`.

`protocol-adapter.js` owns every `/api/` and `/ws` path. Remove its public `request` and `fetchJson` escape hatches. Every endpoint method accepts domain arguments plus an optional final `{ signal }` object.

- [ ] **Step 4: Run transport tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS; no production test needs a browser global to instantiate either transport.

- [ ] **Step 5: Commit declared transport owners**

```bash
git add src/embedagent/frontend/gui/webapp/src/client-runtime/http-transport.js src/embedagent/frontend/gui/webapp/src/client-runtime/socket-transport.js src/embedagent/frontend/gui/webapp/src/client-runtime/protocol-adapter.js src/embedagent/frontend/gui/webapp/src/app-runtime/http-client.js src/embedagent/frontend/gui/webapp/test/http-client.test.mjs src/embedagent/frontend/gui/webapp/test/protocol-adapter.test.mjs src/embedagent/frontend/gui/webapp/test/websocket-lifecycle.test.mjs
git commit -m "refactor: centralize gui transport ownership"
```

### Task 4: Move Every GUI Operation Behind Named Protocol Methods

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/file-preview-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-list-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/thread-lifecycle-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/workspace-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/workspace-files-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/preview-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/source-control-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/preview/preview-api.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/source-control/source-control-api.js`
- Delete: `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/file-preview-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-activation-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-list-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/thread-lifecycle-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/workspace-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/workspace-files-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/preview-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/source-control-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs`
- Delete: `src/embedagent/frontend/gui/webapp/test/preview-api.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Change controller tests to inject a protocol object**

Use named spies, never URL assertions. The required mapping is:

| Controller | Protocol methods |
|---|---|
| file preview | `readFile` |
| interaction response | `respondToInteraction` |
| session activation | `loadSessionBootstrap`, `listTerminals` |
| session | `createSession`, `setSessionMode`, `cancelSession`, `sendSessionMessage`, `reloadSessionResources` |
| session list | `listSessions` |
| session capabilities | `loadSessionCapabilities` |
| thread lifecycle | `renameSession`, `archiveSession`, `forkSession` |
| workspace | `loadAppBootstrap`, `openWorkspacePath`, `activateWorkspace`, `removeWorkspace` |
| workspace files | `loadWorkspaceTree` |
| preview | `listPreviewSessions`, `openPreviewSession`, `refreshPreviewSession`, `closePreviewSession`, `openPreviewExternal` |
| source control | `getSourceControlStatus`, `refreshSourceControlStatus`, `getSourceControlDiff` |
| terminal | `listTerminals`, `openTerminal`, `getTerminalSnapshot`, `writeTerminal`, `clearTerminal`, `restartTerminal`, `resizeTerminal`, `closeTerminal` |

Representative test:

```javascript
const protocol = { loadSessionBootstrap: async (id) => bootstrap(id, 3) };
const load = createSessionActivationController({ protocol, dispatch });
await load("s-1");
assert.equal(actions[0].type, "session_activated");
```

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL while controllers still require `fetchJson` or standalone API functions.

- [ ] **Step 3: Replace controller transport parameters**

Every controller accepts `protocol` and calls only methods from the mapping table. Delete URL construction, `Content-Type` headers, JSON serialization, and `fetchJson` defaults from controllers. Optional contributions fail closed when their protocol method is absent; core session methods throw `protocol_method_missing:<name>` during runtime construction.

Delete the three standalone API modules and their direct-fetch tests after their behavior is covered by `protocol-adapter.test.mjs` and controller tests.

- [ ] **Step 4: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with controller assertions expressed in domain operations rather than paths.

- [ ] **Step 5: Commit controller migration and API deletion**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime src/embedagent/frontend/gui/webapp/src/preview/preview-api.js src/embedagent/frontend/gui/webapp/src/source-control/source-control-api.js src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: route gui operations through protocol adapter"
```

### Task 5: Compose And Close One GUI Client Runtime

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/client-runtime/client-runtime.js`
- Create: `src/embedagent/frontend/gui/webapp/test/client-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/main.jsx`

- [ ] **Step 1: Write a failing lifecycle test**

Test one construction and one close boundary:

```javascript
const runtime = createClientRuntime({
  protocol,
  dispatch: actions.push.bind(actions),
  getState: () => state,
  browser: browserHarness,
});
await runtime.start();
runtime.actions.selectSession("s-1");
runtime.close();

assert.equal(protocol.loadAppBootstrap.calls.length, 1);
assert.equal(browserHarness.socketCloseCalls, 1);
assert.equal(browserHarness.pendingTimerCount(), 0);
```

Assert `close()` is idempotent and every action called after close rejects with `client_runtime_closed`.

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because `client-runtime.js` does not exist.

- [ ] **Step 3: Compose controllers inside `createClientRuntime`**

The runtime owns protocol, transport controller, loader executor, socket effects, and all domain controllers. Its public API is frozen:

```javascript
return Object.freeze({
  start,
  close,
  actions: Object.freeze({
    activateWorkspace,
    selectSession,
    createSession,
    renameSession,
    archiveSession,
    forkSession,
    setMode,
    cancelSession,
    submitText,
    respondToInteraction,
    executeCommand,
    openContribution,
  }),
});
```

Feature-specific actions are reached through `openContribution` or descriptor command dispatch, not exposed as more top-level shell APIs.

- [ ] **Step 4: Reduce React construction to one runtime**

`main.jsx` creates the HTTP transport, socket transport, and protocol adapter. `App.jsx` receives `protocol` as a prop, creates one `ClientRuntime` bound to reducer dispatch/state refs, and starts/closes it in one effect. Delete all direct controller and transport imports from `App.jsx`.

- [ ] **Step 5: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS; source tests show `App.jsx` imports `createClientRuntime` and no individual controller factory.

- [ ] **Step 6: Commit GUI runtime ownership**

```bash
git add src/embedagent/frontend/gui/webapp/src/client-runtime/client-runtime.js src/embedagent/frontend/gui/webapp/test/client-runtime.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/main.jsx
git commit -m "refactor: compose gui effects in client runtime"
```

### Task 6: Introduce The TUI Terminal Runtime

**Files:**
- Create: `src/embedagent/frontend/tui/runtime.py`
- Create: `tests/test_tui_runtime.py`
- Modify: `src/embedagent/frontend/tui/bootstrap.py`
- Modify: `src/embedagent/frontend/tui/app.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/tui/services/sessions.py`
- Modify: `tests/test_terminal_frontend.py`
- Modify: `tests/test_tui_launcher.py`

- [ ] **Step 1: Write failing runtime contract tests**

Use a fake Hosted controller and real protocol envelopes:

```python
def test_terminal_runtime_installs_bootstrap_cursor_and_applies_contiguous_event():
    host = FakeHostedController(bootstrap=bootstrap_payload(event_cursor=2))
    actions = []
    runtime = TerminalRuntime(host, dispatch=actions.append)

    runtime.activate_session("s-1")
    runtime.on_session_event(session_event("s-1", 3, "evt-3"))

    assert runtime.event_cursor == 3
    assert [item["type"] for item in actions] == ["session_activated", "session_event"]
```

Add tests that reject a legacy `(event_name, session_id, payload)` callback, ignore another session, recover a gap through `get_session_bootstrap`, and reject operations after `close()`.

- [ ] **Step 2: Run TUI runtime tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_tui_runtime.py tests/test_terminal_frontend.py tests/test_tui_launcher.py`

Expected: FAIL because `TerminalRuntime` is undefined.

- [ ] **Step 3: Implement the in-process protocol port**

`TerminalRuntime` accepts only `HostedSessionController`-style public methods, owns `selected_session_id`, `event_cursor`, generation, close state, and dispatch. Its `on_session_event()` signature is:

```python
def on_session_event(self, envelope: SessionEventEnvelope) -> None:
    if self._closed or envelope.session_id != self._selected_session_id:
        return
    if envelope.sequence <= self._event_cursor:
        return
    if envelope.sequence != self._event_cursor + 1:
        self._recover_selected_session()
        return
    self._event_cursor = envelope.sequence
    self._dispatch({"type": "session_event", "event": envelope.to_dict()})
```

Expose named session/workspace/interaction methods matching GUI protocol semantics. Delete `SessionService.submit()`'s `TypeError` fallback and any `getattr(adapter, ...)` optional method probing. Missing required Host methods fail at runtime construction.

- [ ] **Step 4: Inject the runtime into the TUI shell**

`run_tui()` constructs `TerminalRuntime(session_host, dispatch=...)`; `TerminalApp` accepts `runtime`, not `adapter`. `TerminalController` invokes runtime methods and reduces returned actions. Services may remain for pure file/editor presentation, but no service calls Host directly.

- [ ] **Step 5: Run focused TUI tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_tui_runtime.py tests/test_terminal_frontend.py tests/test_tui_launcher.py`

Expected: PASS with envelope-only event handling and no compatibility fallback.

- [ ] **Step 6: Commit TUI runtime ownership**

```bash
git add src/embedagent/frontend/tui/runtime.py tests/test_tui_runtime.py src/embedagent/frontend/tui/bootstrap.py src/embedagent/frontend/tui/app.py src/embedagent/frontend/tui/controller.py src/embedagent/frontend/tui/services/sessions.py tests/test_terminal_frontend.py tests/test_tui_launcher.py
git commit -m "refactor: centralize tui effects in terminal runtime"
```

### Task 7: Add Mechanical Ownership Gates And Close Stage 2

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `docs/platform/protocol.md`
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/platform/frontend-gui.md`
- Modify: `docs/platform/frontend-tui.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Generated: `src/embedagent/frontend/gui/static/*`

- [ ] **Step 1: Add ownership and schema source scans**

Make the guard walk production JavaScript and enforce:

```python
assert api_path_files == {"client-runtime/protocol-adapter.js"}
assert fetch_owner_files == {"client-runtime/http-transport.js"}
assert websocket_owner_files == {"client-runtime/socket-transport.js"}
assert "camelOrSnake" not in all_frontend_source
assert "fetchJson" not in all_frontend_source
assert "ThreadDetailSnapshot" not in all_python_source
```

Exclude tests and generated static assets from source-owner scans. Add Python import guards proving TUI renderer/controller modules do not import `embedagent_host`.

- [ ] **Step 2: Run architecture guards**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`

Expected: PASS.

- [ ] **Step 3: Update active authority documents**

Record strict DTO keys and versions in `protocol.md`, effect ownership in frontend protocol/GUI/TUI documents, and replace the Stage 2 status with the Stage 3 shared-registration blocker. Do not retain old schema examples.

- [ ] **Step 4: Run all webapp checks and build static assets**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm run build`

Expected: exit code 0 with refreshed committed static assets.

- [ ] **Step 5: Run required Python and lint gates**

Run: `uv run python scripts/test-suite.py full`

Expected: PASS.

Run: `uv run --locked python scripts/lint.py`

Expected: PASS.

- [ ] **Step 6: Verify deletion and strict-cutover scans**

Run: `rg -n "camelOrSnake|agentApplication|workflowPackages|currentMode|fetchJson|ThreadDetailSnapshot" packages/embedagent-protocol/src src/embedagent/frontend/gui/backend src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/tui`

Expected: no wire aliases, compatibility readers, or retired DTO names. Internal JavaScript `currentMode` is permitted only after mapping and must be excluded from wire fixture assertions; any source match must be reviewed as an internal view-model property.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 7: Commit Stage 2 gates, docs, and generated assets**

```bash
git add tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py docs/platform/protocol.md docs/platform/frontend-protocol.md docs/platform/frontend-gui.md docs/platform/frontend-tui.md docs/current-status.md docs/implementation-roadmap.md src/embedagent/frontend/gui/static
git commit -m "docs: establish strict frontend protocol authority"
```

## Stage Exit Criteria

- Protocol DTOs emit one versioned `snake_case` wire shape and reject retired casing.
- GUI endpoint paths occur only in `protocol-adapter.js`; `fetch` and `WebSocket` each occur in one declared transport owner.
- GUI controllers consume named protocol methods and one `ClientRuntime` owns their lifecycle.
- TUI controllers and views consume one `TerminalRuntime`; only it talks to the hosted session boundary.
- Both shells accept the same Python-generated bootstrap and event fixtures.
- Alternate serializers, fallback readers, direct API modules, and callback-shape compatibility are deleted.
- Architecture guards, full Python tests, lint, webapp tests, and webapp build pass.
