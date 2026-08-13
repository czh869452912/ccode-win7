# CLI And Client Runtime Convergence Design

> Status: `active`
> Date: 2026-08-13
> Owners: Agent platform and EmbedAgent product maintainers

## 1. Purpose

This design replaces the obsolete CLI entry point and converges all frontend access to
the hosted Agent through one protocol-owned frontend boundary. The change is deliberately
breaking: the product is pre-release, so retired commands, callbacks, facades, aliases, and
tests are deleted instead of preserved behind compatibility layers.

The result must make the Agent independent of CLI, TUI, GUI, transport, and renderer
implementation details. CLI and TUI share a Python client runtime; GUI uses a JavaScript
client runtime over HTTP/WebSocket. Both runtimes implement the same session state-machine
contract and consume the same strict DTOs, but they do not share runtime code across
languages.

## 2. Problems To Remove

The current CLI combines argument parsing, TUI/GUI routing, configuration overrides,
session creation and restoration, legacy event handling, interaction callbacks, rendering,
and process exit policy in one file. Its three-argument event callback no longer matches the
canonical `SessionEventEnvelope` contract. Existing tests hide the regression by simulating
the retired callback, while the packaged CLI smoke bypasses `cli.main()` and calls Host
directly.

The frontend boundary is also duplicated:

- GUI uses product-owned `AgentCoreAdapter` through protocol `CoreInterface`;
- CLI and TUI use Host-owned `HostedSessionHost`;
- both facades wrap the same `InProcessAdapter`, but expose different method names,
  event-binding models, and synchronization behavior;
- GUI `ClientRuntime` includes both the reusable session state machine and browser workbench
  concerns such as DOM integration, keyboard handling, terminals, preview, and source control;
- configuration documentation says environment variables override files, while the current
  shared resolver lets file values override environment variables.

Keeping these paths would allow session activation, event ordering, interactions, and error
handling to drift again.

## 3. Goals

- Make one focused frontend protocol the only supported Host boundary for CLI, TUI, and GUI.
- Keep Agent Core and Host independent of shell, renderer, application, and transport details.
- Implement one client-runtime architecture with Python and JavaScript transport-specific
  implementations.
- Make CLI a dynamic renderer over descriptors, bootstrap DTOs, capabilities, and canonical
  events rather than a fixed catalog or state owner.
- Replace the mixed CLI with explicit `chat`, `run`, and `sessions` commands.
- Give automation stable stdout, JSON, failure-category, and exit-code contracts.
- Use the same configuration loader, precedence, validation, and bundle policy for every shell.
- Make real packaged CLI execution a release gate.
- Delete obsolete pre-release shapes instead of forwarding or aliasing them.

## 4. Non-Goals

- No compatibility for existing CLI arguments, naked-message invocation, `--tui`, or `--gui`.
- No shared Python/JavaScript runtime, schema generator, client DSL, or Node.js runtime dependency.
- No CLI JSONL event-stream protocol.
- No frontend ownership of session history, workflow, tasks, permissions, tool activation, or
  restore policy.
- No application-specific, workflow-specific, or tool-name-specific branches in generic
  frontend code.
- No change to the public standalone `Agent` / `AgentSession` Core SDK.
- No weakening of Windows 7, Python 3.8, offline, six-wheel, or flavor restrictions.

## 5. Architecture Decision

The architecture unifies the frontend protocol and client-runtime semantics, not the concrete
runtime implementation.

```text
CLI renderer ---\
                 +-- Python SessionClientRuntime -- InProcess transport --\
TUI renderer ---/                                                       \
                                                                          +-- frontend ports -- Host -- AgentSession
GUI renderer ------ BrowserAppRuntime -- JS SessionClientRuntime --------/
                                      -- HTTP/WebSocket transport
```

The protocol package owns JSON-safe DTOs and focused frontend ports. Host implements the
in-process ports. The GUI backend exposes the same operations over HTTP/WebSocket without
renaming or reshaping session DTOs. Product composition selects the application, resolves
configuration, constructs the ports, and compiles `ShellDescriptor`.

The frontend depends inward on Protocol and Host ports. Agent Core does not import Protocol,
Host, product, or frontend packages. Host does not import product or a shell.

## 6. Focused Frontend Ports

`embedagent_protocol` defines three workflow-neutral boundaries.

### 6.1 `FrontendSessionPort`

The session port owns frontend-facing session operations only:

- list, create, resume, and bootstrap a session;
- submit a user message;
- cancel a running session and set its mode;
- respond to a pending interaction;
- rename, archive, and fork a session;
- close the bound hosted runtime.

Methods return strict protocol DTOs or JSON-safe projections. Submission does not accept
permission resolvers, user-input resolvers, per-call event handlers, or mutable Host objects.

### 6.2 `FrontendWorkspacePort`

The workspace port owns workspace-facing read and command operations:

- workspace snapshot and tree;
- file children, read, write, and diff preview;
- resource reload;
- other registered workspace operations already exposed by the generic protocol.

It does not own session activation or application policy. GUI workspace registry and workspace
switching remain product-shell composition concerns and create or close a port set for the
selected workspace.

### 6.3 `SessionEventSink`

The event sink has one operation:

```python
def on_session_event(self, envelope: SessionEventEnvelope) -> None:
    ...
```

The sink is bound once when a frontend port set is created. Host creates each envelope once;
in-process clients and the WebSocket bridge forward it unchanged. Per-event callbacks and the
retired `(event_name, session_id, payload)` shape are forbidden.

### 6.4 Removed Facades

The following overlapping boundaries are deleted in the same migration:

- `CoreInterface`;
- `FrontendCallbacks`;
- product `AgentCoreAdapter`;
- Host `HostedSessionHost`;
- frontend access to `InProcessAdapter` or `session_host.adapter`;
- resolver callbacks passed into message submission.

No deprecated aliases, forwarding facades, or dual method names remain.

## 7. State Ownership

| Layer | Owned state | Explicitly not owned |
|---|---|---|
| Agent Core | live `Session`, turns, workflow carrier, execution state | frontend projection and transport |
| Host | transcript, restore, managed execution, frozen bootstrap/history/capabilities | renderer state and product shell policy |
| Client runtime | active session reference, cursor, generation, activation buffer, connection/request lifecycle | history, workflow, tasks, permissions, tools, restore |
| Renderer | draft input, scroll, selection, terminal presentation | session or workflow truth |

`transcript.jsonl` remains the only durable hosted history ledger. `SessionBootstrap` is the
only activation projection, and `SessionEventEnvelope` is the only live-event shape. A client
runtime can discard and reconstruct all of its state from Host.

## 8. Session Client Runtime Contract

Python and JavaScript implement the same observable state machine:

```text
idle -> activating -> ready -> submitting -> waiting_interaction -> ready -> closed
                              \-> ready

activating/submitting/waiting_interaction -> failed
```

Sequence gaps initiate one bootstrap recovery for the current generation. Recovery is an
operation, not a second source of session truth. A failed recovery reaches terminal `failed`.

Both implementations must:

- install one strict `SessionBootstrap` after create, resume, or selection;
- verify schema version and session identity;
- establish a new generation before activation begins;
- buffer live envelopes during activation;
- discard envelopes from another session, an old generation, or an applied sequence;
- apply only the next contiguous sequence;
- recover one time from the current bootstrap path when a sequence gap appears;
- resolve commands from `ShellDescriptor` and current capabilities;
- submit interaction responses through the session port;
- reject operations after close and ignore late events;
- dispatch frozen runtime actions to a renderer-owned reducer or presenter.

The shared contract does not include GUI workspace controllers, DOM or keyboard access,
browser dialogs, terminal/preview/source-control operations, TUI layout, CLI input, CLI output,
or application-specific behavior.

### 8.1 Python Runtime

The Python `SessionClientRuntime` uses an in-process transport backed by the focused frontend
ports. CLI and TUI use the same runtime instance shape and command dispatcher. The current TUI
`TerminalRuntime` is removed after its session activation, cursor, recovery, interaction, and
descriptor dispatch behavior moves to this runtime.

### 8.2 Browser Runtime

The JavaScript `SessionClientRuntime` uses protocol methods plus WebSocket events. The current
large GUI `ClientRuntime` is split:

- `SessionClientRuntime` owns only the common session state machine;
- `BrowserAppRuntime` composes GUI-only workspace, keyboard, dialog, contribution, terminal,
  preview, file, source-control, and workbench controllers;
- HTTP and WebSocket transports remain the only endpoint and socket owners.

The browser runtime does not become a base class for Python clients, and Python clients do not
start the GUI backend.

## 9. Dynamic Shell Behavior

CLI, TUI, and GUI derive behavior from product-compiled `ShellDescriptor`, session bootstrap,
and capability projections.

- Generic frontend code does not branch on application id, workflow type, C/C++ phase, task
  type, or tool name.
- Commands are resolved by descriptor identity, availability, arguments, and dispatch kind.
- Modes and tool presentation come from capabilities.
- Workflow rendering consumes only the registered generic projection.
- A missing declaration remains unavailable; the client does not synthesize a fallback.

Only renderer lifecycle commands can be local. CLI owns `/help` and `/exit`; all other slash
commands must be descriptor-backed. TUI and GUI keep only equivalent renderer-local lifecycle
actions where unavoidable.

## 10. CLI Product Contract

The top-level CLI accepts subcommands only:

```text
embedagent chat [options]
embedagent run [options] <task>
embedagent sessions list [options]
embedagent sessions show <reference> [options]
embedagent sessions rename <reference> <title> [options]
embedagent sessions archive <reference> [options]
embedagent sessions fork <reference> [--title <title>] [options]
```

`embedagent.cmd` launches only this CLI. TUI and GUI use their dedicated launchers. Bundle
policy continues to decide which launchers exist: `minimal-cli` contains CLI only, while
`cpp-desktop` contains CLI, TUI, and GUI.

### 10.1 `chat`

`chat` creates or resumes a session and runs a persistent input loop.

- Ordinary input is submitted to the active session.
- `/help` and `/exit` are local.
- Other slash commands must resolve through `ShellDescriptor`.
- Permission and user-input descriptors are rendered generically and answered through the
  runtime interaction operation.
- Bootstrap history can be rendered on activation, but CLI does not retain an independent
  history ledger.
- Live output is projected from canonical envelopes.
- `Ctrl+C` cancels a running turn; while idle it clears current input. A repeated interrupt or
  EOF exits.

### 10.2 `run`

`run` creates or resumes a session, submits one task, and waits for a terminal outcome.

- It never prompts for an interaction.
- Permission or user input leaves the Host interaction pending and returns `blocked`.
- Text mode writes only the final answer to stdout and diagnostics to stderr.
- `--output json` writes one final result object to stdout.
- It does not expose a JSONL event stream, interpret interactive slash commands, or prompt for
  terminal input. Agent tool execution continues through normal Host permission policy.

The JSON result shape is:

```json
{
  "schema_version": 1,
  "session_id": "session-id",
  "status": "completed",
  "exit_code": 0,
  "final_text": "result",
  "outcome": {},
  "failure": null
}
```

### 10.3 `sessions`

`sessions` only manages durable sessions. `list`, `show`, `rename`, `archive`, and `fork` call
the session port and do not activate or execute a turn. Continuing work is expressed through
`chat --resume` or `run --resume`.

Text output is concise and human-readable. `--output json` emits the corresponding strict
projection.

### 10.4 CLI Module Boundaries

The CLI implementation is split by responsibility:

- `parser.py`: subcommand syntax to immutable options;
- `app.py`: product composition of config, ports, descriptor, runtime, and command handler;
- `chat.py`: interactive policy and input loop;
- `run.py`: one-shot execution policy;
- `sessions.py`: durable session management commands;
- `renderer.py`: canonical runtime actions to human-readable output;
- `interaction.py`: generic descriptor-driven input;
- `result.py`: final JSON projection, failure category, and exit code.

No module imports TUI or GUI launchers.

## 11. Shared Configuration

All shells call one product launch-config composition entry. Launchers only construct
`LaunchOverrides`; they do not call `load_config()` or implement precedence.

The required precedence from lowest to highest is:

```text
built-in defaults
< ~/.embedagent/config.json
< <workspace>/.embedagent/config.json
< EMBEDAGENT_* environment variables
< explicit shell arguments
```

User configuration remains supported. Bundle flavor templates remain credential-free product
defaults. Model, URL, timeout, selected application, and bundle policy are validated before a
frontend port or provider is created. Diagnostics must not print API keys, raw configuration,
prompts, source, tool output, or permission payloads.

## 12. Failure And Exit Contract

Frontend failures use structure rather than localized message matching:

- `usage_error`;
- `configuration_error`;
- `session_not_found`;
- `interaction_required`;
- `permission_denied`;
- `provider_error`;
- `runtime_error`;
- `cancelled`;
- `protocol_error`.

CLI exit codes are stable:

| Code | Meaning |
|---:|---|
| `0` | completed |
| `2` | blocked, interaction required, or permission denied |
| `3` | usage or configuration error |
| `4` | provider, runtime, or protocol failure |
| `130` | cancelled |

Host failure records and session outcomes determine categories. CLI does not infer a category
from English or Chinese exception text.

## 13. Verification Strategy

### 13.1 Protocol Tests

Tests enforce focused port signatures, strict DTOs, structured failures, and the single
envelope sink. Architecture guards reject the retired facades and callback signatures.

### 13.2 Cross-Language Runtime Contract

One set of credential-free JSON fixtures describes observable inputs and expected runtime
actions for:

- normal activation;
- events received while bootstrap is loading;
- duplicate events;
- sequence gaps and recovery;
- stale generations and other-session events;
- pending and resolved interactions;
- close and late events;
- protocol validation failure.

Python pytest and JavaScript Node tests execute the same fixtures. Fixtures contain protocol
data and expected actions, not executable rules or generated implementation code.

### 13.3 CLI Tests

CLI tests use fake focused ports and real `SessionEventEnvelope` DTOs. They cover chat input,
descriptor commands, interactions, run completion/blocking/failure, session management,
stdout/stderr separation, JSON results, and every exit code. Tests must not invoke a handler
with three arguments.

### 13.4 Bundle Release Tests

The common CLI release gate must execute the bundle-local launcher and parser against a local
fake OpenAI-compatible provider. It covers:

- `embedagent.cmd run --output json "smoke"`;
- scripted `chat` completion and interaction;
- `sessions list` and `sessions show`;
- session restore;
- permission and user-input blocked outcomes;
- bundle-local Python and plan-selected application identity.

Calling Host APIs directly is useful as a lower-level test but does not satisfy the packaged
CLI gate. Both `minimal-cli` and `cpp-desktop` run the same CLI contract.

## 14. Migration Slices

Implementation proceeds as four independently verifiable slices:

1. Introduce focused frontend ports, one event sink, structured failures, and corrected shared
   configuration; migrate Host composition without adding compatibility facades.
2. Establish the Python and JavaScript session-client contract, extract GUI-only app runtime,
   and migrate TUI and GUI.
3. Replace the CLI with `chat`, `run`, and `sessions` over the Python client runtime.
4. Upgrade bundle smoke to execute real launchers, delete every retired boundary, update
   architecture authorities and delivery documentation, and run all required gates.

A slice may use a short-lived branch transition internally, but the merged result cannot expose
old and new public frontend boundaries simultaneously.

## 15. Acceptance Conditions

- CLI, TUI, and GUI use the focused frontend ports and canonical DTOs.
- Python CLI/TUI share one `SessionClientRuntime`; GUI separates common session runtime from
  `BrowserAppRuntime`.
- No three-argument event callback remains.
- `CoreInterface`, `FrontendCallbacks`, `AgentCoreAdapter`, and `HostedSessionHost` are absent.
- No per-submission event, permission, or user-input callback remains.
- CLI has no TUI/GUI import, launcher route, naked-message mode, or retired alias.
- CLI/TUI/GUI launchers do not call `load_config()` and observe the documented precedence.
- Generic frontend code does not branch on application id, workflow type, or tool name.
- `run` produces stable text/JSON output and exit codes.
- Bundle CLI smoke crosses the real launcher for both flavors.
- Protocol, runtime, CLI, architecture, full Python, lint, GUI test/build, six-wheel, and package
  release gates pass as required by `AGENTS.md`.
- Current architecture, protocol, CLI/TUI/GUI, composition, configuration, packaging, runtime
  contract, status/roadmap, and code-doc ownership documents describe only the landed shape.

## 16. Risks And Controls

- **Cross-language drift:** controlled by shared protocol fixtures and strict DTO validation.
- **Oversized common runtime:** controlled by limiting it to session synchronization and generic
  descriptor dispatch; workspace and renderer controllers remain outside.
- **Temporary frontend breakage:** controlled by migration slices and deletion in the same
  merge; compatibility layers are not an accepted mitigation.
- **Release smoke false confidence:** controlled by invoking the packaged command and checking
  stdout, JSON, exit code, runtime source, application, interactions, and restore.
- **Credential exposure:** controlled by credential-free fixtures and redacted diagnostics.
