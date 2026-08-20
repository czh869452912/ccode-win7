# Frontend Contract Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 CLI、TUI、GUI 迁移到同一套 v2 frontend contract，同时保持 runtime 只依赖 focused ports 和稳定 DTO，具体 shell、provider、renderer 与 workflow 可替换。

**Architecture:** Protocol 发行包拥有 schema v2、`FailureRecord`、canonical session event、最小化 `InteractionProjection` 和 app-level notification DTO。Python/JavaScript `SessionClientRuntime` 各自拥有 transport 下的 generation、cursor、interaction 和 close 状态机；shell 只做 descriptor projection，产品组合显式提供 focused collaborators，Host 不构造默认 provider。

**Tech Stack:** Python 3.8 stdlib/dataclasses/pytest，JavaScript ES modules/Node test runner，现有 `embedagent-protocol` DTO、`SessionClientRuntime`、GUI WebSocket/HTTP bridge、TUI prompt_toolkit/rich、architecture guards。

---

## 文件与职责映射

- Protocol DTO 与版本：
  `packages/embedagent-protocol/src/embedagent_protocol/versions.py`,
  `app_protocol.py`, `session_events.py`, `frontend_interactions.py`,
  `frontend_notifications.py`。
- Python runtime owner：`src/embedagent/frontend/runtime/session_client_runtime.py`,
  `src/embedagent/frontend/runtime/interaction_projection.py`,
  `src/embedagent/frontend/runtime/commands.py`。
- CLI：`src/embedagent/cli/app.py`, `chat.py`, `sessions.py`, `interaction.py`（迁移后删除）。
- TUI：`src/embedagent/frontend/tui/controller.py`, `frontend_adapter.py`, `state.py`,
  `shell_state.py`, `views/composer.py`, `bootstrap.py`, `launcher.py`。
- GUI Python bridge：`src/embedagent/frontend/gui/backend/app_host.py`, `app_shell.py`,
  `server.py`, `http_errors.py`, `protocol_payloads.py`。
- GUI browser runtime：`src/embedagent/frontend/gui/webapp/src/session-runtime/`,
  `client-runtime/`, `app-runtime/`, `app-shell/`。
- Product/Host composition：`packages/embedagent-host/src/embedagent_host/hosted/runtime.py`,
  `src/embedagent/hosted.py`。
- Shared contract tests：`tests/fixtures/session_client_runtime/contract.json`,
  `tests/fixtures/frontend_protocol/*.json`, `tests/test_session_client_runtime_contract.py`,
  `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`。

## 不可违反的耦合边界

- Protocol DTO、schema version、focused port、lifecycle state 和 capability key 是允许的公共耦合。
- runtime 不导入具体 Host adapter、provider SDK、prompt_toolkit、React、pywebview 或 workflow package。
- shell renderer 只通过 descriptor registry 选择；不得按 application id、workflow name 或 tool name 重建 policy。
- 不新增 aggregate service、callback bag、forwarding facade、`last_error` alias 或第三套 session runtime。
- 每个可插拔 collaborator 必须通过 focused interface/Protocol 注入，并能用 fake 实现通过 contract tests。

## Task 1: 建立 v2 Protocol DTO 与共享 fixture

**Files:**
- Create: `packages/embedagent-protocol/src/embedagent_protocol/versions.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/frontend_interactions.py`
- Create: `packages/embedagent-protocol/src/embedagent_protocol/frontend_notifications.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/session_events.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Test: `tests/test_frontend_contract_v2.py`, `tests/test_protocol_versions.py`,
  `tests/test_session_event_protocol.py`
- Fixtures: `tests/fixtures/frontend_protocol/app_bootstrap.json`,
  `session_bootstrap.json`, `session_event.json`, `tests/fixtures/session_client_runtime/contract.json`

- [ ] **Step 1: Write failing DTO tests.**

  Add tests asserting that `CURRENT_SCHEMA_VERSION == 2`, `AppBootstrap` accepts only
  `last_failure: FailureRecord | None` and rejects `last_error`, and the new DTOs reject
  unknown root fields. The interaction test must use this concrete shape:

  ```python
  projection = InteractionProjection(
      kind="permission",
      interaction_id="approval-1",
      turn_id="turn-1",
      renderer="interaction",
      descriptor_version=1,
      descriptor={"choices": ["accept", "decline"], "default": "decline"},
  )
  assert projection.to_dict()["descriptor"]["default"] == "decline"
  ```

  Add a `WorkspaceChangedNotification` round-trip test and assert it is not a
  `SessionEventEnvelope` and has no session sequence.

- [ ] **Step 2: Run the focused tests and verify the expected red state.**

  Run:

  ```text
  uv run pytest tests/test_frontend_contract_v2.py tests/test_protocol_versions.py tests/test_session_event_protocol.py -q
  ```

  Expected: FAIL because schema v2 and the new DTO modules do not exist and `AppBootstrap`
  still serializes `last_error`.

- [ ] **Step 3: Implement the minimal version and DTO contract.**

  Put `CURRENT_SCHEMA_VERSION = 2` in `versions.py`; import it from both
  `app_protocol.py` and `session_events.py` to avoid a circular dependency. Change
  `AppBootstrap` to hold `last_failure: Optional[FailureRecord]`, validate it with
  `FailureRecord.from_dict` on input, and serialize `last_failure` or `None`.
  `InteractionProjection` must freeze/copy JSON-safe descriptor data and expose only
  `kind`, `interaction_id`, `turn_id`, `renderer`, `descriptor_version`, and `descriptor`.
  `WorkspaceChangedNotification` must expose `schema_version`, `workspace_id`, `path`,
  and `reason`, with strict unknown-field rejection.

- [ ] **Step 4: Migrate protocol fixtures and JavaScript normalizer expectations.**

  Update every v1 fixture used by the frontend contract to schema version 2, replace
  `last_error` with a serialized `last_failure`, and update `tests/test_protocol_versions.py`
  expected values. Update `protocol-normalizer.test.mjs` and `protocol-envelope.test.mjs`
  so an extra `last_error` root field fails and `last_failure` is deeply frozen.

- [ ] **Step 5: Run the DTO and fixture gates.**

  ```text
  uv run pytest tests/test_frontend_contract_v2.py tests/test_protocol_versions.py tests/test_session_event_protocol.py -q
  node src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs
  node src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs
  ```

  Expected: all focused tests pass with no `last_error` in v2 DTO output.

- [ ] **Step 6: Commit the protocol boundary.**

  ```text
  git add packages/embedagent-protocol tests/test_frontend_contract_v2.py tests/test_protocol_versions.py tests/test_session_event_protocol.py tests/fixtures/frontend_protocol tests/fixtures/session_client_runtime src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs
  git commit -m "feat: define frontend protocol v2 DTOs"
  ```

## Task 2: 收敛 Python SessionClientRuntime ownership

**Files:**
- Modify: `src/embedagent/frontend/runtime/session_client_runtime.py`
- Modify: `src/embedagent/frontend/runtime/__init__.py`
- Modify: `tests/test_session_client_runtime_contract.py`
- Modify: `tests/fixtures/session_client_runtime/contract.json`

- [ ] **Step 1: Add failing ownership and reentrancy cases.**

  Extend the Python contract harness with cases asserting:

  - `runtime.active_session_id` is the only id used by `submit_user_message` and
    `respond_to_interaction(interaction_id, payload)`;
  - `activate_session` raises a typed `FrontendPortError` instead of returning `None`;
  - a dispatch callback that calls `activate_session` is deferred until the current
    publication commits its cursor and terminal outcome;
  - `fork_session` returns a `ThreadShell`, while `fork_and_activate_session` returns a
    `SessionBootstrap` for descriptor session commands;
  - `close()` makes later operations fail with the existing closed-runtime error.

  Add the same observable cases to the JSON fixture consumed by the JavaScript contract test.

- [ ] **Step 2: Run the runtime contract and confirm failure.**

  ```text
  uv run pytest tests/test_session_client_runtime_contract.py -q
  node src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs
  ```

  Expected: FAIL on the old `None` activation result, local-id method signatures and
  synchronous nested publication.

- [ ] **Step 3: Implement focused runtime APIs.**

  Add a read-only `active_session_id` property and active-session operations:

  ```python
  def submit_active_message(self, text: str, stream: bool = True) -> None: ...
  def respond_to_interaction(self, interaction_id: str, payload: Dict[str, Any]) -> SessionBootstrap: ...
  def fork_session(self, session_id: str, title: str = "") -> ThreadShell: ...
  def fork_and_activate_session(self, session_id: str, title: str = "") -> SessionBootstrap: ...
  ```

  Keep the session port id internal to the runtime and change `activate_session` to return a
  `SessionBootstrap` or raise a typed failure. Convert activation `FrontendPortError` into a
  `protocol_failed` action plus re-raise; do not use `None` as an error signal.
  Add a FIFO deferred operation queue guarded by the existing condition. A sink callback
  can enqueue an operation, but `_drain_event_queue` commits cursor/lifecycle/terminal outcome
  before draining deferred work. Do not import any shell class into this module.

- [ ] **Step 4: Make the Python and JavaScript contract observations identical.**

  Update `_observable` in `tests/test_session_client_runtime_contract.py` and the matching
  JavaScript helper so both compare the same action kind, generation, cursor and failure code.
  Add a property test that every accepted event sequence has strictly increasing committed
  cursor and at most one terminal outcome.

- [ ] **Step 5: Run the shared runtime gates.**

  ```text
  uv run pytest tests/test_session_client_runtime_contract.py tests/test_session_client_commands.py -q
  node src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs
  ```

  Expected: Python and JavaScript contract cases pass without a shell-specific branch.

- [ ] **Step 6: Commit runtime ownership.**

  ```text
  git add src/embedagent/frontend/runtime tests/test_session_client_runtime_contract.py tests/fixtures/session_client_runtime/contract.json src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs
  git commit -m "refactor: make frontend runtime the session owner"
  ```

## Task 3: 迁移 CLI 与 TUI 到 descriptor/runtime contract

**Files:**
- Create: `src/embedagent/frontend/runtime/interaction_projection.py`
- Modify: `src/embedagent/cli/app.py`, `src/embedagent/cli/chat.py`, `src/embedagent/cli/sessions.py`
- Delete: `src/embedagent/cli/interaction.py`
- Modify: `src/embedagent/frontend/tui/controller.py`, `frontend_adapter.py`, `state.py`,
  `shell_state.py`, `views/composer.py`, `bootstrap.py`, `launcher.py`
- Test: `tests/test_cli_chat.py`, `tests/test_cli_sessions.py`, `tests/test_terminal_frontend.py`,
  `tests/test_tui_activity_timeline.py`, `tests/test_tui_runtime.py`, `tests/test_tui_launcher.py`,
  `tests/test_frontend_python_shell_contract.py`

- [ ] **Step 1: Write failing shell contract tests.**

  Add tests that:

  - CLI preserves `ApplicationConfigurationError` metadata and maps each closed failure code
    through `exit_code_for_failure`;
  - CLI session management invokes runtime methods and never reads `context.session_port`;
  - TUI accepts a normalized nested interaction projection, resolves descriptor choices/defaults,
    and sends the descriptor answer key;
  - TUI uses `runtime.active_session_id`, clears pending state on both resolved and response-failed;
  - TUI filters unavailable command/keybinding projections;
  - direct `run_tui()` closes runtime and late actions are ignored;
  - interaction response failures render `FailureRecord.safe_message`, not `str(exc)`.

- [ ] **Step 2: Run the Python shell tests and verify failure.**

  ```text
  uv run pytest tests/test_cli_chat.py tests/test_cli_sessions.py tests/test_terminal_frontend.py tests/test_tui_activity_timeline.py tests/test_tui_runtime.py tests/test_tui_launcher.py tests/test_frontend_python_shell_contract.py -q
  ```

  Expected: FAIL on direct port access, hard-coded y/n/answer, local session ids, missing
  response-failed handling and raw exception rendering.

- [ ] **Step 3: Move interaction resolution to the transport-neutral runtime package.**

  Move `InteractionChoice`, `InteractionPrompt`, descriptor lookup and response construction
  from `src/embedagent/cli/interaction.py` to
  `src/embedagent/frontend/runtime/interaction_projection.py`. The module may import only
  Protocol DTOs and `typing`; CLI and TUI both call the same `resolve_interaction` and
  `build_interaction_response`. Delete the old CLI module after imports are migrated.

- [ ] **Step 4: Remove CLI port escapes and raw failure classification.**

  Route `src/embedagent/cli/sessions.py` list/summary/rename/archive/fork through runtime
  methods. At the shell boundary, reuse
  `packages/embedagent-host/src/embedagent_host/frontend_errors.py` `failure_for_exception`
  for typed mapping; the transport-neutral runtime itself continues to depend only on
  Protocol `FailureRecord` and an exception's optional `.failure` attribute. In
  `src/embedagent/cli/app.py` catch `FrontendPortError` first and use that mapper for unknown
  exceptions; do not create a bare `FailureRecord` for every `ValueError`. In
  `CliChat.on_runtime_action`, parse the action failure and return
  `exit_code_for_failure(failure.code)` rather than the literal `4`.

- [ ] **Step 5: Make TUI descriptor and runtime ownership explicit.**

  Store the frozen capability projection in `TerminalState`, normalize pending interaction
  to top-level `kind`, and use `interaction_projection.py` for prompt/response choices.
  Replace `state.session.current_session_id` arguments with `runtime.active_session_id` or
  active-session runtime methods. Catch `FrontendPortError` and render only its `FailureRecord`.
  Route `interaction.respond` through runtime dispatch, evaluate command availability before
  palette/keybinding projection, and close the runtime in every `run_tui`/launcher exit path.
  Defer post-finish refresh until runtime publication has committed; the controller must not
  synchronously call `activate_session` from inside the event sink.

- [ ] **Step 6: Run Python shell gates and static ownership checks.**

  ```text
  uv run pytest tests/test_cli_chat.py tests/test_cli_sessions.py tests/test_terminal_frontend.py tests/test_tui_activity_timeline.py tests/test_tui_runtime.py tests/test_tui_launcher.py tests/test_frontend_python_shell_contract.py -q
  uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q
  ```

  Expected: all focused tests pass and architecture guards report no CLI `session_port`
  access, no TUI raw exception presentation, and no second interaction resolver.

- [ ] **Step 7: Commit Python shell convergence.**

  ```text
  git add src/embedagent/frontend/runtime/interaction_projection.py src/embedagent/cli src/embedagent/frontend/tui tests/test_cli_chat.py tests/test_cli_sessions.py tests/test_terminal_frontend.py tests/test_tui_activity_timeline.py tests/test_tui_runtime.py tests/test_tui_launcher.py tests/test_frontend_python_shell_contract.py
  git commit -m "refactor: converge cli and tui on frontend runtime contract"
  ```

## Task 4: 迁移 GUI HTTP/WebSocket 与 browser runtime

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`, `app_host.py`, `app_shell.py`,
  `server.py`, `http_errors.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`,
  `session-client-runtime.js`, `protocol-envelope.js`, `interaction-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/protocol-adapter.js`,
  `socket-message-controller.js`, `app-runtime/browser-app-runtime.js`, `app-runtime/workspace-controller.js`
- Tests: `tests/test_gui_app_host.py`, `tests/test_gui_backend_api.py`, `tests/test_gui_session_events.py`,
  `tests/test_gui_sync.py`, `tests/test_gui_protocol_projection.py`,
  `src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs`,
  `protocol-envelope.test.mjs`, `session-runtime.test.mjs`, `client-runtime.test.mjs`,
  `workspace-controller.test.mjs`, `websocket-lifecycle.test.mjs`

- [ ] **Step 1: Write failing GUI contract tests.**

  Cover structured `FailureRecord` JSON for HTTP errors, strict rejection of an inbound
  WebSocket envelope with extra root/sensitive fields, propagation of dispatcher/broadcast
  failure, activation failure reaching BrowserAppRuntime, `last_failure` normalization, and
  a `workspace_changed` app notification that does not increment session cursor.

- [ ] **Step 2: Run the GUI focused tests and verify failure.**

  ```text
  uv run pytest tests/test_gui_app_host.py tests/test_gui_backend_api.py tests/test_gui_session_events.py tests/test_gui_sync.py tests/test_gui_protocol_projection.py -q
  node src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs
  node src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs
  node src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs
  node src/embedagent/frontend/gui/webapp/test/client-runtime.test.mjs
  ```

  Expected: FAIL because backend/JS still uses `last_error`, activation catches all errors,
  WebSocket bypasses strict normalizer, and workspace changes are HTTP-only.

- [ ] **Step 3: Migrate GUI payloads and structured HTTP failures.**

  Change `serialize_app_bootstrap` and `app_shell.py` to emit `last_failure` or `None`.
  Make `frontend_port_http_error` serialize the complete safe `FailureRecord` fields; map
  `ApplicationConfigurationError` to `configuration_error` without reading exception text.
  Store a `FailureRecord` in `GUIAppHost`, and make workspace activation clear/replace that
  record atomically.

- [ ] **Step 4: Make WebSocket publication strict.**

  Run every inbound session message through `normalizeSessionEventEnvelope` before
  `SessionClientRuntime.acceptSessionEvent`. Change dispatcher/broadcast to return a typed
  failure or raise `FrontendPortError`; a failed socket is removed but the publication caller
  receives a failure signal. Add the app-level `workspace_changed` notification path without
  entering the session event queue.

- [ ] **Step 5: Remove browser activation swallowing and normalize failures.**

  Delete the blanket `catch { return null; }` in `SessionClientRuntime.activateSession`.
  Let `BrowserAppRuntime` receive the typed failure and dispatch a structured notice/state
  action. Change the public JavaScript runtime methods to derive the selected session from
  `this.sessionId`, matching Python `respond_to_interaction(interaction_id, payload)` and
  `submit_active_message(text, stream)`, while the transport adapter remains the only layer
  that passes the internal session id over HTTP. Update reducers/selectors from `last_error`
  to `last_failure`; keep renderer-specific text as a local safe-message projection only.

- [ ] **Step 6: Run GUI tests and build.**

  ```text
  uv run pytest tests/test_gui_app_host.py tests/test_gui_backend_api.py tests/test_gui_session_events.py tests/test_gui_sync.py tests/test_gui_protocol_projection.py -q
  npm test
  npm run build
  ```

  Run the commands from `src/embedagent/frontend/gui/webapp`. Expected: focused Python tests,
  all browser contract tests executed by the test runner, and the production build pass.

- [ ] **Step 7: Commit GUI convergence.**

  ```text
  git add src/embedagent/frontend/gui/backend src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test tests/test_gui_app_host.py tests/test_gui_backend_api.py tests/test_gui_session_events.py tests/test_gui_sync.py tests/test_gui_protocol_projection.py
  git commit -m "refactor: enforce gui frontend contract v2"
  ```

## Task 5: Move provider construction to product composition

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/runtime.py`
- Modify: `src/embedagent/hosted.py`
- Modify: `tests/test_hosted_runtime.py`, `tests/test_cli_hosted_entrypoint.py`,
  `tests/test_current_architecture_boundaries.py`, `tests/test_frontend_composition_contract.py`

- [ ] **Step 1: Add a failing composition boundary test.**

  Assert that `create_generic_hosted_runtime` cannot construct a runtime without explicit
  focused `model_client`, `tool_runtime`, `context_manager`, and `permission_policy`, and
  that a fake implementation satisfying those interfaces can be injected without importing
  a provider SDK into the generic Host module.

- [ ] **Step 2: Run the composition tests and verify failure.**

  ```text
  uv run pytest tests/test_hosted_runtime.py tests/test_cli_hosted_entrypoint.py tests/test_current_architecture_boundaries.py tests/test_frontend_composition_contract.py -q
  ```

  Expected: FAIL because `packages/embedagent-host/.../hosted/runtime.py` still imports and
  constructs `OpenAICompatibleClient`, `ToolRuntime`, `ContextManager`, and `PermissionPolicy`.

- [ ] **Step 3: Change the generic Host factory to focused interfaces.**

  Remove concrete provider imports from `hosted/runtime.py`. Require explicit named
  collaborators in `create_hosted_runtime` and validate their focused methods at the
  composition boundary. Do not introduce an aggregate dependency bag. Keep `HostedRuntime`
  responsible only for port ownership and close.

- [ ] **Step 4: Construct concrete collaborators in product composition.**

  In `src/embedagent/hosted.py`, build the selected product's model client, tool runtime,
  context manager and permission policy, then pass them to the generic Host factory. The
  product may import Host implementations; the reverse dependency remains forbidden. Missing
  or malformed collaborators must raise `ApplicationConfigurationError` before session creation.

- [ ] **Step 5: Run composition and offline boundary gates.**

  ```text
  uv run pytest tests/test_hosted_runtime.py tests/test_cli_hosted_entrypoint.py tests/test_current_architecture_boundaries.py tests/test_frontend_composition_contract.py -q
  uv run pytest tests/test_pre_release_architecture_guards.py -q
  ```

  Expected: fake collaborator injection passes and static guards find no provider construction
  in the generic Host module.

- [ ] **Step 6: Commit provider inversion.**

  ```text
  git add packages/embedagent-host/src/embedagent_host/hosted/runtime.py src/embedagent/hosted.py tests/test_hosted_runtime.py tests/test_cli_hosted_entrypoint.py tests/test_current_architecture_boundaries.py tests/test_frontend_composition_contract.py
  git commit -m "refactor: inject hosted collaborators from product composition"
  ```

## Task 6: Add architecture guards and synchronize authorities

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`,
  `tests/test_current_architecture_boundaries.py`
- Modify: `docs/platform/protocol.md`, `docs/platform/frontend-protocol.md`,
  `docs/platform/frontend-gui.md`, `docs/platform/frontend-tui.md`,
  `docs/references/code-doc-matrix.md`, `docs/current-status.md`,
  `docs/implementation-roadmap.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: Add static guards before removing the design slice.**

  Add assertions that active source contains no wire `last_error`, no CLI direct
  `context.session_port`, no `str(exc)` in frontend diagnostics, no blanket activation
  catch returning `None`, and no concrete provider construction in generic Host runtime.
  Add a guard that every active shell imports the shared runtime interaction resolver rather
  than defining another permission/user-input response mapper.

- [ ] **Step 2: Update owning authority documents to landed v2 behavior.**

  Replace the current v1 field tables and lifecycle descriptions with the implemented DTO,
  runtime owner, app notification, descriptor and close behavior. Keep ADR-0010 as rationale;
  move implementation detail out of the temporary design slice into the four platform
  authorities. Update the code-doc matrix for new Protocol modules and runtime files.

- [ ] **Step 3: Replace current status and roadmap entries.**

  Record only the open release evidence after implementation (real Win7/WebView2 and selected
  bundle evidence). Remove the frontend convergence slice from `docs/superpowers/README.md`
  only after the focused/full gates pass, then move the design and implementation plan into an
  indexed `docs/archive/frontend-contract-convergence/` package.

- [ ] **Step 4: Run documentation and architecture gates.**

  ```text
  uv run pytest tests/test_documentation_navigation.py tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q
  uv run --locked python scripts/lint.py
  ```

  Expected: no active document routes to deleted fields or retired facades, and all guards pass.

- [ ] **Step 5: Commit the gates and authority sync.**

  ```text
  git add tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py docs/platform docs/references/code-doc-matrix.md docs/current-status.md docs/implementation-roadmap.md docs/superpowers/README.md
  git commit -m "test: enforce frontend contract convergence boundaries"
  ```

## Task 7: Full verification and delivery handoff

- [ ] **Step 1: Run all affected focused partitions.**

  ```text
  uv run pytest tests/test_frontend_contract_v2.py tests/test_session_client_runtime_contract.py tests/test_session_client_commands.py tests/test_cli_chat.py tests/test_cli_sessions.py tests/test_terminal_frontend.py tests/test_tui_activity_timeline.py tests/test_tui_runtime.py tests/test_tui_launcher.py tests/test_gui_app_host.py tests/test_gui_backend_api.py tests/test_gui_session_events.py tests/test_gui_sync.py tests/test_gui_protocol_projection.py tests/test_hosted_runtime.py tests/test_frontend_composition_contract.py -q
  ```

- [ ] **Step 2: Run the complete regular Python partition.**

  ```text
  uv run python scripts/test-suite.py full
  ```

  Expected: all selected tests pass; any skips must be existing documented environment skips.

- [ ] **Step 3: Run GUI test/build and lint gates.**

  ```text
  npm test
  npm run build
  uv run --locked python scripts/lint.py
  ```

  Run the npm commands from `src/embedagent/frontend/gui/webapp`.

- [ ] **Step 4: Run the selected distribution checks when the composition files are included.**

  ```text
  uv run python scripts/build-python-distributions.py --dist-dir dist --bundle-plan build/plans/minimal-cli/bundle-plan.json
  uv run python scripts/check-python-distributions.py --dist-dir dist --bundle-plan build/plans/minimal-cli/bundle-plan.json
  uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe --bundle-plan build/plans/minimal-cli/bundle-plan.json
  ```

- [ ] **Step 5: Review the final diff for coupling and deletion debt.**

  ```text
  rg -n "last_error|context\.session_port|str\(exc\)|return None|OpenAICompatibleClient\(|ToolRuntime\(|ContextManager\(|PermissionPolicy\(" src packages tests docs/platform
  git diff --check
  git status --short
  ```

  Expected: only intentional local presentation variables or historical archive references
  remain; no active protocol/runtime path matches the forbidden patterns. Preserve any user
  changes in GUI static assets and do not stage them unless explicitly requested.

- [ ] **Step 6: Record the implementation handoff.**

  The final response must name the implementation commits, focused/full/release evidence,
  remaining external Win7/WebView2 evidence, and any deliberate non-blocking follow-up. Do not
  claim Windows 7 delivery from local tests.
