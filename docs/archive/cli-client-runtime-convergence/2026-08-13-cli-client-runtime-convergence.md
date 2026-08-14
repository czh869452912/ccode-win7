# CLI And Client Runtime Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

> Status: `active`
> Design authority:
> `docs/superpowers/specs/2026-08-13-cli-client-runtime-convergence-design.md`
> Architecture decision:
> `docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md`

**Goal:** Replace the obsolete CLI and duplicate frontend facades with focused protocol
ports, transport-specific session client runtimes, explicit `chat`/`run`/`sessions`
commands, and real bundle-level CLI verification.

**Architecture:** Protocol owns strict DTOs, failure categories, and focused frontend port
interfaces. Host owns the in-process implementations and emits one canonical
`SessionEventEnvelope` to one bound sink. CLI and TUI share a Python
`SessionClientRuntime`; GUI composes an equivalent JavaScript `SessionClientRuntime`
inside a browser-only `BrowserAppRuntime`. Product composition is the only owner of
configuration precedence, application selection, and port-set construction.

**Tech Stack:** Python 3.8, stdlib ABC/dataclasses/threading/argparse, pytest through the
repository test harness, JavaScript ES modules and the existing Node test runner, PowerShell
offline packaging, six-wheel distribution checks.

---

## Execution Rules

- Work from the repository root and preserve Python `>=3.8,<3.9` syntax.
- Use the red/green loop for every task. Do not weaken a failing assertion to make old
  behavior pass.
- Temporary coexistence of old and new facades is allowed only inside this implementation
  branch. Task 15 removes all retired shapes before full verification.
- Keep fixtures credential-free. Never put API keys, prompts, source, raw tool output, or
  permission payloads into diagnostics.
- Do not edit `uv.lock` manually and do not add a runtime dependency.
- Run the focused command shown in each task before committing that task.
- Check off each item in this plan as it completes. Do not append progress narratives to
  architecture documents.

## Task 1: Define Strict Frontend DTO And Port Contracts

**Files:**

- Create: `packages/embedagent-protocol/src/embedagent_protocol/frontend_ports.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/session_events.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_session_event_protocol.py`
- Modify: `tests/test_protocol_package_imports.py`

- [x] **Step 1: Write failing DTO and port-contract tests.**

  Add tests that deserialize `ThreadShell`, `CapabilitySnapshot`, and
  `SessionBootstrap`; reject the wrong schema version, negative cursor, or malformed nested
  DTO; enumerate exactly the approved failure codes; and inspect port signatures to prove
  that submission accepts only `session_id`, `text`, and `stream`.

  ```python
  def test_frontend_session_port_has_no_callback_parameters():
      signature = inspect.signature(FrontendSessionPort.submit_user_message)
      assert list(signature.parameters) == ["self", "session_id", "text", "stream"]


  def test_frontend_failure_codes_are_closed():
      assert set(FRONTEND_FAILURE_CODES) == {
          "usage_error",
          "configuration_error",
          "session_not_found",
          "interaction_required",
          "permission_denied",
          "provider_error",
          "runtime_error",
          "cancelled",
          "protocol_error",
      }
  ```

- [x] **Step 2: Run the protocol tests and confirm the imports or factories fail.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_protocol_package_imports.py
  uv run python scripts/test-suite.py tdd tests/test_agent_app_protocol.py
  uv run python scripts/test-suite.py tdd tests/test_session_event_protocol.py
  ```

  Expected: failure because focused ports, closed failure categories, and nested
  `from_dict()` factories do not exist.

- [x] **Step 3: Implement factories, failure categories, and focused ABCs.**

  The new module must expose only workflow-neutral operations. Use existing DTOs wherever
  they already express the result; use JSON-safe mappings only for workspace projections
  that have no strict DTO.

  ```python
  class SessionEventSink(ABC):
      @abstractmethod
      def on_session_event(self, envelope: SessionEventEnvelope) -> None:
          raise NotImplementedError


  class FrontendSessionPort(ABC):
      @abstractmethod
      def list_sessions(self, limit: int = 10) -> List[ThreadShell]:
          raise NotImplementedError

      @abstractmethod
      def activate_session(self, reference: str, mode: str = "") -> SessionBootstrap:
          raise NotImplementedError

      @abstractmethod
      def create_session(self, mode: str) -> SessionBootstrap:
          raise NotImplementedError

      @abstractmethod
      def submit_user_message(
          self, session_id: str, text: str, stream: bool
      ) -> None:
          raise NotImplementedError

      @abstractmethod
      def respond_to_interaction(
          self, session_id: str, interaction_id: str, payload: Dict[str, Any]
      ) -> SessionBootstrap:
          raise NotImplementedError

      @abstractmethod
      def close(self) -> None:
          raise NotImplementedError
  ```

  Include the approved cancel, mode, show, rename, archive, and fork operations on
  `FrontendSessionPort`, and the current snapshot/tree/file/diff/reload operations on
  `FrontendWorkspacePort`. Do not place application selection or workspace registry policy
  on either port.

- [x] **Step 4: Run the focused tests to green.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_protocol_package_imports.py
  uv run python scripts/test-suite.py tdd tests/test_agent_app_protocol.py
  uv run python scripts/test-suite.py tdd tests/test_session_event_protocol.py
  ```

- [x] **Step 5: Commit the protocol contract.**

  ```powershell
  git add packages/embedagent-protocol/src/embedagent_protocol/frontend_ports.py packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py packages/embedagent-protocol/src/embedagent_protocol/session_events.py packages/embedagent-protocol/src/embedagent_protocol/__init__.py tests/test_protocol_package_imports.py tests/test_agent_app_protocol.py tests/test_session_event_protocol.py
  git commit -m "feat(protocol): define focused frontend ports"
  ```

## Task 2: Correct Shared Configuration Precedence

**Files:**

- Modify: `packages/embedagent-host/src/embedagent_host/hosted/launch_config.py`
- Modify: `src/embedagent/config.py`
- Modify: `src/embedagent/hosted.py`
- Modify: `tests/test_hosted_launch_config.py`
- Modify: `tests/test_product_host_composition.py`
- Modify: `tests/test_tui_launcher.py`
- Modify: `tests/test_gui_launcher_app_mode.py`

- [x] **Step 1: Add a full precedence matrix and launcher ownership tests.**

  Cover absent values and each collision in this exact low-to-high order:

  ```text
  built-in < user config < workspace config < environment < explicit override
  ```

  Patch `HOME`/`USERPROFILE` to a temporary directory, create both JSON files, set
  `EMBEDAGENT_MODEL`, and assert that an explicit `LaunchOverrides(model=...)` wins. Add
  source scans proving CLI, TUI, and GUI launchers do not import or call `load_config()`.

- [x] **Step 2: Run the launch-config tests and observe the environment collision fail.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_hosted_launch_config.py
  uv run python scripts/test-suite.py tdd tests/test_product_host_composition.py
  ```

  Expected: file configuration currently wins over `EMBEDAGENT_*`.

- [x] **Step 3: Make product configuration composition explicit.**

  Keep JSON file merging in `embedagent.config`, with user loaded before workspace. Resolve
  scalar launch values in Host as:

  ```python
  model = str(
      _first_non_empty(
          overrides.model,
          os.environ.get("EMBEDAGENT_MODEL"),
          getattr(app_config, "model", ""),
          "",
      )
      or ""
  )
  ```

  Apply the same ordering to URL, key, timeout, application, permission flags, and context
  limits. Represent boolean overrides as `Optional[bool]`; `False` must be an explicit value,
  not confused with “unspecified”. Keep model validation before provider or port creation.

- [x] **Step 4: Run all config and launcher ownership tests.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_hosted_launch_config.py
  uv run python scripts/test-suite.py tdd tests/test_product_host_composition.py
  uv run python scripts/test-suite.py tdd tests/test_tui_launcher.py
  uv run python scripts/test-suite.py tdd tests/test_gui_launcher_app_mode.py
  ```

- [x] **Step 5: Commit the precedence fix.**

  ```powershell
  git add packages/embedagent-host/src/embedagent_host/hosted/launch_config.py src/embedagent/config.py src/embedagent/hosted.py tests/test_hosted_launch_config.py tests/test_product_host_composition.py tests/test_tui_launcher.py tests/test_gui_launcher_app_mode.py
  git commit -m "fix(config): unify shell launch precedence"
  ```

## Task 3: Implement Host Frontend Port Set

**Files:**

- Create: `packages/embedagent-host/src/embedagent_host/frontend_ports.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/__init__.py`
- Modify: `packages/embedagent-host/src/embedagent_host/__init__.py`
- Modify: `src/embedagent/hosted.py`
- Create: `tests/test_host_frontend_ports.py`
- Modify: `tests/test_hosted_runtime.py`
- Modify: `tests/test_host_package_composition.py`

- [x] **Step 1: Write failing tests for one bound sink and private adapter ownership.**

  Use a recording `SessionEventSink`, construct a port set once, create and activate a
  session, and assert every event arrives as a `SessionEventEnvelope`. Assert neither the
  runtime nor either port exposes `.adapter` or `.session_host`.

  ```python
  runtime = create_hosted_runtime(config, event_sink=sink)
  bootstrap = runtime.session.create_session("build")
  runtime.session.submit_user_message(bootstrap.thread.id, "hi", stream=False)
  assert all(isinstance(item, SessionEventEnvelope) for item in sink.events)
  assert not hasattr(runtime, "session_host")
  assert not hasattr(runtime.session, "adapter")
  ```

- [x] **Step 2: Run the new Host tests and confirm the port set is absent.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_host_frontend_ports.py
  uv run python scripts/test-suite.py tdd tests/test_hosted_runtime.py
  ```

- [x] **Step 3: Add private in-process implementations and change runtime composition.**

  `HostedRuntime` must expose `launch_config`, `session`, and `workspace`. Store the adapter
  only as a private implementation detail in the port objects. Convert adapter dictionaries
  into strict protocol DTOs at the port boundary.

  ```python
  @dataclass
  class HostedRuntime(object):
      launch_config: LaunchConfig
      session: FrontendSessionPort
      workspace: FrontendWorkspacePort


  def create_hosted_runtime(..., event_sink=None) -> HostedRuntime:
      adapter = InProcessAdapter(..., event_handler=_sink_handler(event_sink))
      return HostedRuntime(
          launch_config=launch_config,
          session=InProcessFrontendSessionPort(adapter),
          workspace=InProcessFrontendWorkspacePort(adapter),
      )
  ```

  `_sink_handler` may adapt the Host internal call once during this task; it must accept one
  envelope and never reconstruct it. Task 4 removes the internal legacy signature.

- [x] **Step 4: Run Host and distribution tests.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_host_frontend_ports.py
  uv run python scripts/test-suite.py tdd tests/test_hosted_runtime.py
  uv run python scripts/test-suite.py tdd tests/test_host_package_composition.py
  ```

- [x] **Step 5: Commit the Host port set.**

  ```powershell
  git add packages/embedagent-host/src/embedagent_host/frontend_ports.py packages/embedagent-host/src/embedagent_host/hosted/runtime.py packages/embedagent-host/src/embedagent_host/hosted/__init__.py packages/embedagent-host/src/embedagent_host/__init__.py src/embedagent/hosted.py tests/test_host_frontend_ports.py tests/test_hosted_runtime.py tests/test_host_package_composition.py
  git commit -m "feat(host): expose focused frontend port set"
  ```

## Task 4: Converge Host Events, Interactions, And Failures

**Files:**

- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_command_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/frontend_ports.py`
- Create: `packages/embedagent-host/src/embedagent_host/frontend_errors.py`
- Modify: `tests/test_session_event_protocol.py`
- Modify: `tests/test_hosted_interaction_service.py`
- Modify: `tests/test_host_frontend_ports.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_c_cpp_workflow_task_projection.py`
- Modify: `tests/test_agent_runtime_integration.py`
- Modify: `tests/test_host_agent_facade.py`
- Modify: `tests/test_local_resources.py`
- Modify: `tests/test_gui_streaming.py`

- [x] **Step 1: Add failing tests for canonical sink calls and typed failures.**

  Assert that `InProcessAdapter.create_session`, `resume_session`, and
  `submit_user_message` do not contain `event_handler`, `permission_resolver`, or
  `user_input_resolver`. Exercise pending permission and user-input requests without a
  resolver and prove the session remains resumable. Raise representative provider, missing
  session, cancellation, and protocol errors and assert the returned `FailureRecord.code`
  without checking localized message text.

- [x] **Step 2: Run the focused tests and confirm legacy parameters remain.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_host_frontend_ports.py
  uv run python scripts/test-suite.py tdd tests/test_hosted_interaction_service.py
  uv run python scripts/test-suite.py tdd tests/test_session_event_protocol.py
  ```

- [x] **Step 3: Make the event emitter envelope-only.**

  Bind the sink at adapter construction and change the emitter core to:

  ```python
  class EventEmitter(object):
      def __init__(self, sink: Optional[SessionEventSink] = None) -> None:
          self._sink = sink
          self._encoder = SessionEventEncoder()

      def emit(
          self, event_name: str, session_id: str, payload: Dict[str, Any]
      ) -> None:
          with self._encoder.session_scope(session_id):
              envelope = self._encoder.encode(session_id, event_name, payload)
              if self._sink is not None:
                  self._sink.on_session_event(envelope)
  ```

  Create the envelope once before dispatch. Remove per-call handlers and resolver callbacks.
  Remove their parameters from `HostedCommandService` and `HostedInteractionService` as well
  as `InProcessAdapter`; do not merely hide them at the frontend port. A pending interaction
  is represented by Host state and canonical events; only `respond_to_interaction()` resolves
  it.

- [x] **Step 4: Add structured Host exception translation.**

  Implement a Host-owned `FrontendPortError` carrying a protocol `FailureRecord`. Map known
  exception types or explicit outcome states to the closed categories. Do not inspect
  exception message strings.

  ```python
  class FrontendPortError(RuntimeError):
      def __init__(self, failure: FailureRecord) -> None:
          super().__init__(failure.message)
          self.failure = failure
  ```

  Session error envelopes must carry `failure.to_dict()` and a stable outcome status.

- [x] **Step 5: Run event, interaction, and stream tests.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_session_event_protocol.py
  uv run python scripts/test-suite.py tdd tests/test_hosted_interaction_service.py
  uv run python scripts/test-suite.py tdd tests/test_host_frontend_ports.py
  uv run python scripts/test-suite.py tdd tests/test_inprocess_adapter_frontend_api.py
  uv run python scripts/test-suite.py tdd tests/test_c_cpp_workflow_task_projection.py
  uv run python scripts/test-suite.py tdd tests/test_agent_runtime_integration.py
  uv run python scripts/test-suite.py tdd tests/test_host_agent_facade.py
  uv run python scripts/test-suite.py tdd tests/test_local_resources.py
  uv run python scripts/test-suite.py tdd tests/test_gui_streaming.py
  ```

- [x] **Step 6: Commit the Host convergence.**

  ```powershell
  git add packages/embedagent-host/src/embedagent_host/inprocess_adapter.py packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py packages/embedagent-host/src/embedagent_host/hosted_command_service.py packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py packages/embedagent-host/src/embedagent_host/frontend_ports.py packages/embedagent-host/src/embedagent_host/frontend_errors.py tests/test_session_event_protocol.py tests/test_hosted_interaction_service.py tests/test_host_frontend_ports.py tests/test_inprocess_adapter_frontend_api.py tests/test_c_cpp_workflow_task_projection.py tests/test_agent_runtime_integration.py tests/test_host_agent_facade.py tests/test_local_resources.py tests/test_gui_streaming.py
  git commit -m "refactor(host): converge events and interactions"
  ```

## Task 5: Establish Cross-Language Runtime Fixtures

**Files:**

- Create: `tests/fixtures/session_client_runtime/contract.json`
- Create: `tests/test_session_client_runtime_contract.py`
- Create: `src/embedagent/frontend/runtime/__init__.py`
- Create: `src/embedagent/frontend/runtime/session_client_runtime.py`
- Create: `src/embedagent/frontend/runtime/runtime_actions.py`

- [x] **Step 1: Add one credential-free observable contract fixture.**

  Each case contains `initial`, ordered `operations`, and expected frozen `actions`. Include
  normal activation, activation buffering, duplicate event, one sequence gap recovery,
  recovery failure, stale generation, another session, pending/resolved interaction, close,
  late event, schema mismatch, and session-id mismatch.

  ```json
  {
    "schema_version": 1,
    "cases": [
      {
        "name": "duplicate_event_is_ignored",
        "operations": [
          {"kind": "activate", "bootstrap": "session_bootstrap"},
          {"kind": "event", "event": "sequence_2"},
          {"kind": "event", "event": "sequence_2"}
        ],
        "actions": [
          {"kind": "session_activated", "session_id": "session-1", "cursor": 1},
          {"kind": "session_event", "session_id": "session-1", "sequence": 2}
        ]
      }
    ]
  }
  ```

- [x] **Step 2: Write the Python fixture runner and see it fail on missing runtime.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
  ```

- [x] **Step 3: Implement the minimal Python state machine.**

  Keep only active session id, cursor, generation, activation buffer, request state, and
  closed/failed lifecycle. Use an `RLock` plus `Condition` for event delivery; do not copy
  session history, workflow, tasks, permissions, or tool state into the runtime.

  ```python
  @dataclass(frozen=True)
  class RuntimeAction(object):
      kind: str
      payload: Dict[str, Any]


  class SessionClientRuntime(SessionEventSink):
      def bind_session_port(self, session_port: FrontendSessionPort) -> None:
          if self._session_port is not None:
              raise RuntimeError("session port is already bound")
          self._session_port = session_port

      def on_session_event(self, envelope: SessionEventEnvelope) -> None:
          with self._condition:
              self._apply_or_buffer(envelope)
              self._condition.notify_all()
  ```

  A gap calls the current generation's bootstrap transport once. A second gap or failed
  recovery emits `protocol_failed` and enters terminal `failed`.

- [x] **Step 4: Run the Python contract tests to green.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
  ```

- [x] **Step 5: Commit the fixture and Python runtime kernel.**

  ```powershell
  git add tests/fixtures/session_client_runtime tests/test_session_client_runtime_contract.py src/embedagent/frontend/runtime
  git commit -m "feat(frontend): add python session client runtime"
  ```

## Task 6: Add Descriptor-Driven Python Commands And Waiting

**Files:**

- Create: `src/embedagent/frontend/runtime/commands.py`
- Modify: `src/embedagent/frontend/runtime/session_client_runtime.py`
- Modify: `tests/test_session_client_runtime_contract.py`
- Create: `tests/test_session_client_commands.py`

- [x] **Step 1: Add failing tests for command resolution and terminal outcomes.**

  Test that commands are discovered from `ShellDescriptor`, unavailable commands remain
  unavailable, dispatch uses the descriptor's declared kind and arguments, and no application
  id, workflow type, or tool name is recognized by hard-coded branches. Test runtime waiting
  for completed, blocked, failed, cancelled, and timeout outcomes.

- [x] **Step 2: Run the tests and confirm dispatcher/wait APIs are missing.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py
  uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
  ```

- [x] **Step 3: Implement generic dispatch and condition-based waiting.**

  ```python
  def resolve_command(shell: ShellDescriptor, name: str) -> CommandDescriptor:
      normalized = name.strip().lstrip("/")
      matches = [item for item in shell.commands if item.id == normalized]
      if not matches:
          raise UnknownShellCommand(normalized)
      return matches[0]
  ```

  The runtime emits immutable actions for renderer consumption and derives terminal outcomes
  only from bootstrap/event structure. It must never match English or Chinese text.

- [x] **Step 4: Run both runtime test files to green.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py
  uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
  ```

- [x] **Step 5: Commit the shared Python runtime surface.**

  ```powershell
  git add src/embedagent/frontend/runtime tests/test_session_client_commands.py tests/test_session_client_runtime_contract.py
  git commit -m "feat(frontend): dispatch descriptor commands in python runtime"
  ```

## Task 7: Migrate TUI To SessionClientRuntime

**Files:**

- Modify: `src/embedagent/frontend/tui/bootstrap.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/tui/frontend_adapter.py`
- Modify: `src/embedagent/frontend/tui/host.py`
- Delete: `src/embedagent/frontend/tui/runtime.py`
- Modify: `tests/test_tui_runtime.py`
- Modify: `tests/test_tui_launcher.py`
- Modify: `tests/test_tui_activity_timeline.py`
- Modify: `tests/test_tui_timeline_activities.py`

- [x] **Step 1: Rewrite TUI tests against the common runtime.**

  Keep renderer/reducer assertions, but instantiate `SessionClientRuntime` with fake focused
  ports and canonical envelopes. Add a source assertion that TUI files do not import
  `HostedSessionHost`, access `.adapter`, or define another cursor/generation recovery loop.

- [x] **Step 2: Run the TUI tests and confirm old runtime coupling fails.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_tui_runtime.py
  uv run python scripts/test-suite.py tdd tests/test_tui_launcher.py
  ```

- [x] **Step 3: Rewire TUI bootstrap and controller.**

  Product composition constructs the client runtime first, creates the Host port set with
  that runtime as the event sink, then calls `bind_session_port()` exactly once with the
  created session port. It separately supplies the workspace port and compiled
  `ShellDescriptor` to TUI composition. TUI controllers consume `RuntimeAction`; only
  layout, draft input, selection, and presentation remain TUI-owned.

- [x] **Step 4: Delete `TerminalRuntime` and its duplicated synchronization code.**

  Move no forwarding alias into `tui.__init__`. Update imports directly.

- [x] **Step 5: Run all focused TUI tests.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_tui_runtime.py
  uv run python scripts/test-suite.py tdd tests/test_tui_launcher.py
  uv run python scripts/test-suite.py tdd tests/test_tui_activity_timeline.py
  uv run python scripts/test-suite.py tdd tests/test_tui_timeline_activities.py
  ```

- [x] **Step 6: Commit the TUI migration.**

  ```powershell
  git add src/embedagent/frontend/tui/bootstrap.py src/embedagent/frontend/tui/controller.py src/embedagent/frontend/tui/frontend_adapter.py src/embedagent/frontend/tui/host.py src/embedagent/frontend/tui/runtime.py tests/test_tui_runtime.py tests/test_tui_launcher.py tests/test_tui_activity_timeline.py tests/test_tui_timeline_activities.py
  git commit -m "refactor(tui): use shared session client runtime"
  ```

## Task 8: Migrate GUI Backend To Focused Ports

**Files:**

- Modify: `src/embedagent/frontend/gui/backend/app_host.py`
- Modify: `src/embedagent/frontend/gui/backend/bridge.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_app.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/backend/workspace_registry.py`
- Modify: `src/embedagent/frontend/gui/launcher.py`
- Modify: `tests/test_gui_app_host.py`
- Modify: `tests/test_gui_backend_api.py`
- Modify: `tests/test_gui_session_events.py`
- Modify: `tests/test_gui_workspace_registry.py`

- [x] **Step 1: Add failing backend tests for protocol identity.**

  Assert HTTP routes call `FrontendSessionPort`/`FrontendWorkspacePort`, bootstrap payloads
  equal the strict DTO output, and WebSocket forwarding is exactly:

  ```python
  {"type": "session_event", "data": envelope.to_dict()}
  ```

  Add a source assertion that backend code does not import `CoreInterface` or
  `AgentCoreAdapter`.

- [x] **Step 2: Run backend tests and observe facade imports fail the new contract.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_gui_app_host.py
  uv run python scripts/test-suite.py tdd tests/test_gui_backend_api.py
  uv run python scripts/test-suite.py tdd tests/test_gui_session_events.py
  ```

- [x] **Step 3: Inject the focused port set into GUI app host and routes.**

  Bind the WebSocket bridge as the Host event sink at workspace port-set construction.
  Workspace switching closes the previous port set, then creates one for the selected
  workspace. Routes must preserve protocol names and payloads instead of adding GUI-specific
  session translations.

- [x] **Step 4: Run all backend and workspace tests.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_gui_app_host.py
  uv run python scripts/test-suite.py tdd tests/test_gui_backend_api.py
  uv run python scripts/test-suite.py tdd tests/test_gui_session_events.py
  uv run python scripts/test-suite.py tdd tests/test_gui_workspace_registry.py
  ```

- [x] **Step 5: Commit the GUI backend migration.**

  ```powershell
  git add src/embedagent/frontend/gui/backend/app_host.py src/embedagent/frontend/gui/backend/bridge.py src/embedagent/frontend/gui/backend/routes_sessions.py src/embedagent/frontend/gui/backend/routes_app.py src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/backend/workspace_registry.py src/embedagent/frontend/gui/launcher.py tests/test_gui_app_host.py tests/test_gui_backend_api.py tests/test_gui_session_events.py tests/test_gui_workspace_registry.py
  git commit -m "refactor(gui): use focused frontend ports"
  ```

## Task 9: Implement The JavaScript Session Runtime Contract

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js`
- Create: `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Reuse: `tests/fixtures/session_client_runtime/contract.json`

- [x] **Step 1: Register a JavaScript runner for the shared fixture.**

  Resolve the fixture from repository root without copying it into the webapp. Assert the
  exact expected action sequence for every case and deep-freeze dispatched actions in tests.

- [x] **Step 2: Run the Node suite and confirm the module is missing.**

  ```powershell
  Push-Location src/embedagent/frontend/gui/webapp
  npm test
  Pop-Location
  ```

- [x] **Step 3: Implement the same observable state machine in JavaScript.**

  ```javascript
  export class SessionClientRuntime {
    constructor({ transport, dispatch }) {
      this.transport = transport;
      this.dispatch = dispatch;
      this.sessionId = "";
      this.cursor = 0;
      this.generation = 0;
      this.activationBuffer = [];
      this.lifecycle = "idle";
    }

    acceptSessionEvent(envelope) {
      // Validate, buffer or apply, then dispatch one frozen observable action.
    }
  }
  ```

  Keep browser APIs, workspace controllers, dialogs, keyboard behavior, terminals, preview,
  and source control out of this class.

- [x] **Step 4: Run Node tests to green.**

  ```powershell
  Push-Location src/embedagent/frontend/gui/webapp
  npm test
  Pop-Location
  ```

- [x] **Step 5: Commit the browser session runtime.**

  ```powershell
  git add src/embedagent/frontend/gui/webapp tests/fixtures/session_client_runtime/contract.json
  git commit -m "feat(gui): implement session runtime contract"
  ```

## Task 10: Extract BrowserAppRuntime

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/browser-app-runtime.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/client-runtime.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/use-agent-shell-runtime.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/client-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/client-runtime-reducers.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`

- [x] **Step 1: Add responsibility-boundary tests.**

  Assert `SessionClientRuntime` has no DOM/window/workspace/terminal/preview/source-control
  references. Assert `BrowserAppRuntime` composes it and owns the existing browser-only
  controllers. Update integration tests to instantiate `BrowserAppRuntime`.

- [x] **Step 2: Run `npm test` and confirm the old monolith violates the boundary.**

  ```powershell
  Push-Location src/embedagent/frontend/gui/webapp
  npm test
  Pop-Location
  ```

- [x] **Step 3: Move browser orchestration and narrow the old module.**

  `browser-app-runtime.js` owns controller construction and lifecycle. Delete the old
  `ClientRuntime` export after all imports move; do not retain it as an alias. The React hook
  creates `BrowserAppRuntime`, while session activation/events flow through the common
  runtime.

- [x] **Step 4: Run tests and build generated static assets.**

  ```powershell
  Push-Location src/embedagent/frontend/gui/webapp
  npm test
  npm run build
  Pop-Location
  ```

- [x] **Step 5: Commit source and generated static assets.**

  ```powershell
  git add src/embedagent/frontend/gui/webapp src/embedagent/frontend/gui/static
  git commit -m "refactor(gui): separate browser and session runtimes"
  ```

## Task 11: Replace CLI Parsing And Result Contracts

**Files:**

- Delete: `src/embedagent/cli.py`
- Create: `src/embedagent/cli/__init__.py`
- Create: `src/embedagent/cli/parser.py`
- Create: `src/embedagent/cli/options.py`
- Create: `src/embedagent/cli/result.py`
- Create: `src/embedagent/cli/app.py`
- Modify: `tests/test_cli_hosted_entrypoint.py`
- Create: `tests/test_cli_parser.py`
- Create: `tests/test_cli_result.py`

- [x] **Step 1: Replace old CLI tests with the approved grammar.**

  Cover only:

  ```text
  embedagent chat [options]
  embedagent run [options] <task>
  embedagent sessions list|show|rename|archive|fork
  ```

  Assert naked messages, `--tui`, `--gui`, and `--list-sessions` are usage errors. Verify
  parser output is immutable and `main(argv)` returns an integer without calling
  `sys.exit()` internally.

- [x] **Step 2: Add the exact final-result and exit-code tests.**

  ```python
  assert CliResult.completed("s1", "ok").to_dict() == {
      "schema_version": 1,
      "session_id": "s1",
      "status": "completed",
      "exit_code": 0,
      "final_text": "ok",
      "outcome": {},
      "failure": None,
  }
  ```

  Assert completed `0`, blocked/interaction/permission `2`, usage/config `3`,
  provider/runtime/protocol `4`, and cancelled `130`.

- [x] **Step 3: Run parser/result tests and confirm old CLI fails.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_parser.py
  uv run python scripts/test-suite.py tdd tests/test_cli_result.py
  uv run python scripts/test-suite.py tdd tests/test_cli_hosted_entrypoint.py
  ```

- [x] **Step 4: Create the CLI package and composition shell.**

  Use subparsers with `required=True`. Common launch flags construct only
  `LaunchOverrides`. `app.main()` resolves bundle policy, launch config, application,
  descriptor, focused ports, and common runtime, then dispatches to command modules added in
  Tasks 12-14.

  ```python
  def main(argv: Optional[List[str]] = None) -> int:
      parsed = build_parser().parse_args(argv)
      try:
          return CliApplication.from_options(parsed).run()
      except FrontendPortError as exc:
          return write_failure(exc.failure)
  ```

  Keep the existing entry point `embedagent.cli:main` valid through package export. Do not
  import TUI or GUI.

- [x] **Step 5: Run parser/result tests to green.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_parser.py
  uv run python scripts/test-suite.py tdd tests/test_cli_result.py
  ```

- [x] **Step 6: Commit the CLI contract.**

  ```powershell
  git add src/embedagent/cli tests/test_cli_parser.py tests/test_cli_result.py tests/test_cli_hosted_entrypoint.py
  git commit -m "refactor(cli): define explicit command contract"
  ```

## Task 12: Implement One-Shot `run`

**Files:**

- Create: `src/embedagent/cli/run.py`
- Create: `src/embedagent/cli/renderer.py`
- Modify: `src/embedagent/cli/app.py`
- Create: `tests/test_cli_run.py`
- Modify: `tests/test_cli_hosted_entrypoint.py`

- [x] **Step 1: Add fake-port tests for every terminal state.**

  Drive the real Python client runtime with canonical envelopes. Cover create and resume,
  completed final text, pending permission, pending user input, provider failure, runtime
  failure, protocol failure, cancellation, JSON output, and stdout/stderr separation. Assert
  run never calls `input()` or `respond_to_interaction()`.

- [x] **Step 2: Run the tests and confirm `run` is not implemented.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_run.py
  uv run python scripts/test-suite.py tdd tests/test_cli_hosted_entrypoint.py
  ```

- [x] **Step 3: Implement one-shot policy over the common runtime.**

  ```python
  def execute_run(context: CliContext, options: RunOptions) -> CliResult:
      bootstrap = context.runtime.activate(options.resume, options.mode)
      context.runtime.submit(options.task, stream=not options.no_stream)
      outcome = context.runtime.wait_for_terminal(options.timeout)
      return CliResult.from_runtime_outcome(bootstrap.thread.id, outcome)
  ```

  In text mode write only `final_text` to stdout. Send structured, redacted diagnostics to
  stderr. In JSON mode serialize one `CliResult` with stable key order and a trailing newline.
  Leave pending Host interactions untouched and return blocked.

- [x] **Step 4: Run the `run` tests to green.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_run.py
  uv run python scripts/test-suite.py tdd tests/test_cli_hosted_entrypoint.py
  ```

- [x] **Step 5: Commit one-shot execution.**

  ```powershell
  git add src/embedagent/cli tests/test_cli_run.py tests/test_cli_hosted_entrypoint.py
  git commit -m "feat(cli): add one-shot run command"
  ```

## Task 13: Implement Durable `sessions` Management

**Files:**

- Create: `src/embedagent/cli/sessions.py`
- Modify: `src/embedagent/cli/app.py`
- Create: `tests/test_cli_sessions.py`

- [x] **Step 1: Add tests for list/show/rename/archive/fork.**

  Test text and JSON projections, limit handling, missing references, title validation, and
  fork's optional title. Assert these commands never submit a turn, respond to an
  interaction, or activate the common session runtime.

- [x] **Step 2: Run the tests and confirm the command handler is missing.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_sessions.py
  ```

- [x] **Step 3: Implement thin management handlers over `FrontendSessionPort`.**

  Human output must use stable columns/labels and no localized string parsing. JSON output
  serializes strict DTO/projection data directly. `show` uses the non-activating summary
  operation, not session bootstrap.

- [x] **Step 4: Run the sessions tests to green.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_sessions.py
  ```

- [x] **Step 5: Commit session management.**

  ```powershell
  git add src/embedagent/cli tests/test_cli_sessions.py
  git commit -m "feat(cli): add durable session commands"
  ```

## Task 14: Implement Interactive `chat`

**Files:**

- Create: `src/embedagent/cli/chat.py`
- Create: `src/embedagent/cli/interaction.py`
- Modify: `src/embedagent/cli/renderer.py`
- Modify: `src/embedagent/cli/app.py`
- Create: `tests/test_cli_chat.py`
- Create: `tests/test_cli_interaction.py`

- [x] **Step 1: Add scripted chat tests.**

  Use injected input/output streams. Cover ordinary turns, create/resume, activation history
  rendering, `/help`, `/exit`, descriptor-backed slash commands, unknown command, permission
  choice, user input, EOF, running-turn `Ctrl+C`, idle interrupt, and repeated interrupt.
  Assert the chat object owns no history/session/workflow/task truth.

- [x] **Step 2: Add generic interaction descriptor tests.**

  Resolve prompt, choices, default, validation, and payload construction from
  `InteractionDescriptor`. Do not branch on C/C++ types, tool names, or application id.

- [x] **Step 3: Run the tests and confirm chat modules are missing.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_chat.py
  uv run python scripts/test-suite.py tdd tests/test_cli_interaction.py
  ```

- [x] **Step 4: Implement the persistent loop and generic renderer.**

  `/help` and `/exit` are the only local slash commands. Every other slash command resolves
  through the current `ShellDescriptor`. Runtime actions drive output; interaction answers
  call only `respond_to_interaction()`.

  ```python
  while not runtime.closed:
      line = input_stream.readline()
      if line == "":
          return 0
      command = line.strip()
      if command == "/exit":
          return 0
      if command == "/help":
          renderer.write_help(shell)
          continue
      dispatch_chat_input(runtime, shell, command)
  ```

- [x] **Step 5: Run all CLI tests to green.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_cli_chat.py
  uv run python scripts/test-suite.py tdd tests/test_cli_interaction.py
  uv run python scripts/test-suite.py tdd tests/test_cli_run.py
  uv run python scripts/test-suite.py tdd tests/test_cli_sessions.py
  uv run python scripts/test-suite.py tdd tests/test_cli_hosted_entrypoint.py
  ```

- [x] **Step 6: Commit interactive chat.**

  ```powershell
  git add src/embedagent/cli tests/test_cli_chat.py tests/test_cli_interaction.py tests/test_cli_run.py tests/test_cli_sessions.py tests/test_cli_hosted_entrypoint.py
  git commit -m "feat(cli): add descriptor-driven chat command"
  ```

## Task 15: Delete Retired Frontend Boundaries

**Files:**

- Delete: `packages/embedagent-host/src/embedagent_host/hosted/session_host.py`
- Delete: `src/embedagent/core/adapter.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/__init__.py`
- Modify: `src/embedagent/core/__init__.py`
- Modify: `src/embedagent/frontend/__init__.py`
- Modify: `src/embedagent/frontend/tui/frontend_adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/app_host.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/launcher.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `tests/test_architecture.py`
- Modify: `tests/test_protocol_package_imports.py`
- Modify: `tests/test_host_distribution_imports.py`
- Delete: `tests/test_core_adapter_shutdown.py`
- Modify: `tests/test_exception_characterization.py`
- Modify: `tests/test_gui_runtime.py`
- Modify: `tests/test_gui_session_events.py`
- Modify: `tests/test_gui_sync.py`
- Modify: `tests/test_hosted_runtime.py`
- Modify: `tests/test_tui_runtime.py`

- [x] **Step 1: Add source guards before deleting code.**

  Search the owning source trees and fail if any of these remain:

  ```text
  CoreInterface
  FrontendCallbacks
  AgentCoreAdapter
  HostedSessionHost
  session_host.adapter
  event_handler= on create/resume/submit
  permission_resolver
  user_input_resolver
  def on_event(event_name, session_id, payload)
  ```

  Also fail if generic frontend runtime code branches on application id, workflow type, or
  known tool names.

- [x] **Step 2: Run architecture guards and confirm they identify every remaining site.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_pre_release_architecture_guards.py
  uv run python scripts/test-suite.py tdd tests/test_current_architecture_boundaries.py
  ```

- [x] **Step 3: Delete facades, exports, obsolete tests, and forwarding methods.**

  Update every live caller directly to focused ports. Do not leave deprecation warnings,
  aliases, proxy classes, or a compatibility module at the deleted paths.

- [x] **Step 4: Run architecture and distribution boundaries.**

  ```powershell
  uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
  uv run python scripts/test-suite.py tdd tests/test_protocol_package_imports.py
  uv run python scripts/test-suite.py tdd tests/test_host_distribution_imports.py
  uv run python scripts/test-suite.py tdd tests/test_python_distribution_contract.py
  ```

- [x] **Step 5: Verify the retired names are absent.**

  ```powershell
  rg -n "CoreInterface|FrontendCallbacks|AgentCoreAdapter|HostedSessionHost|permission_resolver|user_input_resolver" packages src tests
  rg -n "def on_event\(event_name, session_id, payload\)|event_handler=" packages src tests
  ```

  Expected: no production matches; test matches are limited to explicit forbidden-name
  literals inside architecture guards.

- [x] **Step 6: Commit the deletion.**

  ```powershell
  git add packages/embedagent-host/src/embedagent_host/hosted/session_host.py packages/embedagent-protocol/src/embedagent_protocol/__init__.py packages/embedagent-host/src/embedagent_host/hosted/__init__.py src/embedagent/core/adapter.py src/embedagent/core/__init__.py src/embedagent/frontend/__init__.py src/embedagent/frontend/tui/frontend_adapter.py src/embedagent/frontend/gui/backend/app_host.py src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/launcher.py tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_architecture.py tests/test_protocol_package_imports.py tests/test_host_distribution_imports.py tests/test_core_adapter_shutdown.py tests/test_exception_characterization.py tests/test_gui_runtime.py tests/test_gui_session_events.py tests/test_gui_sync.py tests/test_hosted_runtime.py tests/test_tui_runtime.py
  git commit -m "refactor(frontend): remove retired host facades"
  ```

## Task 16: Make Real CLI Launchers A Release Gate

**Files:**

- Modify: `scripts/validate-cli-smoke.py`
- Modify: `scripts/prepare-offline.ps1`
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `scripts/offline-runtime-contract.json`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_python_distribution_smoke.py`
- Modify: `tests/test_python_distribution_contract.py`

- [x] **Step 1: Add failing packaging contract tests.**

  Inspect the smoke runner and require it to cross the staged `embedagent.cmd` launcher, not
  import product Host APIs. Require both `minimal-cli` and `cpp-desktop` plans to run:

  ```text
  embedagent.cmd run --output json "smoke"
  scripted chat completion
  scripted permission and user-input interaction
  sessions list
  sessions show
  run --resume
  blocked permission
  blocked user input
  ```

- [x] **Step 2: Run packaging tests and confirm direct Host smoke is rejected.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py
  uv run python scripts/test-suite.py tdd tests/test_python_distribution_smoke.py
  ```

- [x] **Step 3: Rewrite smoke orchestration around the staged command.**

  Start the existing local fake OpenAI-compatible provider, create a credential-free
  temporary user/workspace config, invoke the bundle-local command with captured
  stdout/stderr/exit code, and validate the JSON contract. Confirm runtime source is bundle,
  the plan-selected application is active, and no system tool fallback occurs.

- [x] **Step 4: Align the single offline runtime contract.**

  Add or update only `scripts/offline-runtime-contract.json`; do not create another
  hard-coded launcher or required-binary list. Ensure flavor policy still exposes CLI only
  for `minimal-cli` and CLI/TUI/GUI for `cpp-desktop`.

- [x] **Step 5: Run packaging control and six-wheel smoke tests.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py
  uv run python scripts/test-suite.py tdd tests/test_python_distribution_contract.py
  uv run python scripts/test-suite.py tdd tests/test_python_distribution_smoke.py
  uv run python scripts/build-python-distributions.py --dist-dir dist
  uv run python scripts/check-python-distributions.py --dist-dir dist
  uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
  ```

- [x] **Step 6: Commit the real CLI release gate.**

  ```powershell
  git add scripts/validate-cli-smoke.py scripts/prepare-offline.ps1 scripts/validate-offline-bundle.ps1 scripts/offline-runtime-contract.json tests/test_packaging_control_plane.py tests/test_python_distribution_contract.py tests/test_python_distribution_smoke.py
  git commit -m "test(release): execute packaged cli contract"
  ```

## Task 17: Synchronize Authorities And Close The Slice

**Files:**

- Modify: `docs/platform/protocol.md`
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/platform/frontend-tui.md`
- Modify: `docs/platform/frontend-gui.md`
- Modify: `docs/product/composition.md`
- Modify: `docs/guides/configuration-guide.md`
- Modify: `docs/product/packaging-and-deployment.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/superpowers/README.md`
- Move after all acceptance gates pass:
  `docs/superpowers/specs/2026-08-13-cli-client-runtime-convergence-design.md`
- Move after all acceptance gates pass:
  `docs/superpowers/plans/2026-08-13-cli-client-runtime-convergence.md`
- Create: `docs/archive/cli-client-runtime-convergence/README.md`

- [x] **Step 1: Update each owning authority in place.**

  Document only the landed names and behavior: focused ports, state ownership, Python/JS
  runtime equivalence, CLI grammar/output/exit codes, shared configuration order, flavor
  launchers, and real launcher smoke. Remove current references to retired facades and
  callbacks. Keep status and roadmap as current state, not a completion diary.

- [x] **Step 2: Run documentation and architecture checks.**

  ```powershell
  uv run python scripts/test-suite.py tdd tests/test_documentation_navigation.py
  uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
  uv run python scripts/test-suite.py audit
  ```

- [x] **Step 3: Run the complete required verification set.**

  ```powershell
  uv run python scripts/test-suite.py full
  uv run --locked python scripts/lint.py
  Push-Location src/embedagent/frontend/gui/webapp
  npm test
  npm run build
  Pop-Location
  uv run python scripts/build-python-distributions.py --dist-dir dist
  uv run python scripts/check-python-distributions.py --dist-dir dist
  uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
  powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor
  powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release
  ```

  A local release may report `TARGET_READY`/`PENDING_WIN7`; do not claim clean-machine Win7
  acceptance without the separate hash-bound evidence required by the runbook.

- [x] **Step 4: Perform final static acceptance searches.**

  ```powershell
  rg -n "CoreInterface|FrontendCallbacks|AgentCoreAdapter|HostedSessionHost|permission_resolver|user_input_resolver" packages src docs
  rg -n -- "--tui|--gui|--list-sessions|def on_event\(event_name, session_id, payload\)" packages src docs
  git diff --check
  git status --short
  ```

  Review every match. The first search should have no active production or authority matches;
  the second may mention retired forms only in archive history or explicit architecture
  guards.

- [x] **Step 5: Archive the completed slice.**

  Move the design and this plan to `docs/archive/cli-client-runtime-convergence/`, add an
  archive index pointing to the durable ADR and authorities, and remove the active slice from
  `docs/superpowers/README.md`. Do this only after every repository-side acceptance condition
  above is green.

- [x] **Step 6: Commit documentation and closure.**

  ```powershell
  git add docs src/embedagent/frontend/gui/static
  git commit -m "docs: close cli client runtime convergence"
  ```

## Completion Evidence

Before declaring the implementation complete, record the exact results for:

- focused protocol, Host, runtime, CLI, TUI, GUI, architecture, and packaging tests;
- full Python partition and locked lint;
- webapp test and production build;
- six-wheel build/check/isolated smoke;
- package doctor and release;
- final forbidden-name searches and `git diff --check`;
- release status distinction between repository target readiness and real Win7 acceptance.

The implementation is incomplete if any retired facade, callback signature, alternate state
owner, shell-specific config loader, hard-coded workflow branch, or direct-Host packaged CLI
smoke remains.
