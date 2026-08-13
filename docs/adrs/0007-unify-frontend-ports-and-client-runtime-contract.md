# ADR-0007: Unify Frontend Ports And Client Runtime Contract

- Status: accepted
- Date: 2026-08-13
- Owners: Agent platform maintainers

## Context

GUI currently reaches the hosted Agent through product `AgentCoreAdapter` and protocol
`CoreInterface`, while CLI and TUI use Host `HostedSessionHost`. These facades wrap the same
hosted adapter but expose different methods, event binding, and execution behavior. The CLI
remained on a retired three-argument event callback after Host adopted canonical
`SessionEventEnvelope`, and existing tests did not detect the mismatch.

The browser `ClientRuntime` and Python `TerminalRuntime` already implement similar activation,
bootstrap, cursor, recovery, interaction, and command-dispatch responsibilities. Directly
sharing the browser implementation is impossible without making CLI/TUI depend on DOM,
HTTP/WebSocket, or runtime Node.js, which conflicts with the offline product boundary.

## Decision

1. Protocol owns focused `FrontendSessionPort`, `FrontendWorkspacePort`, and
   `SessionEventSink` boundaries plus strict frontend DTOs.
2. Host supplies the only in-process implementation. Product composition resolves config,
   selects the application, constructs ports, and compiles the shell descriptor.
3. CLI and TUI share a Python session client runtime. GUI uses a JavaScript session client
   runtime over HTTP/WebSocket. Both implement the same observable state-machine contract and
   consume unchanged bootstrap/envelope DTOs.
4. Browser-only workbench behavior is composed by a separate browser app runtime and is not
   part of the common session runtime contract.
5. Cross-language consistency is verified with shared JSON protocol fixtures, not shared
   executable code, code generation, or a client DSL.
6. Frontend runtimes own only transient synchronization state. Agent/Core and Host remain the
   only owners of live and durable session truth.
7. `CoreInterface`, `FrontendCallbacks`, `AgentCoreAdapter`, `HostedSessionHost`, per-call event
   handlers, and resolver callbacks are removed without compatibility aliases.

## Consequences

- Agent and Host remain independent of shell, renderer, transport, and application behavior.
- New clients implement a transport and projection over one protocol instead of adding a Host
  facade or event shape.
- CLI and TUI cannot drift in activation, cursor, recovery, interaction, or descriptor dispatch.
- GUI keeps browser-native transport and controllers without making them platform requirements.
- Protocol changes require Python and JavaScript contract tests, but do not require cross-language
  runtime dependencies.
- The migration is intentionally breaking and must update all shells and release gates in one
  convergent program.

## Alternatives Considered

### Reuse The Existing Browser ClientRuntime Everywhere

Rejected. It would force CLI/TUI to depend on browser APIs, HTTP/WebSocket, or Node.js and would
promote GUI workbench concerns into the platform frontend boundary.

### Keep Independent CLI, TUI, And GUI Runtimes

Rejected. It preserves three implementations of session activation, event ordering,
interactions, and command dispatch. The current CLI regression demonstrates the maintenance
cost of that drift.

### Add A HostedShellRuntime Beside Existing Runtimes

Rejected. A third near-synonymous facade would hide the duplicated frontend boundary rather
than remove it.

### Generate Both Clients From A Shared State-Machine DSL

Rejected. The current protocol is small enough for fixture-based conformance. A generator or
DSL would add a new toolchain and debugging boundary without removing transport-specific code.

## Enforcement

- Architecture guards reject retired facades, three-argument callbacks, per-call handlers, and
  application/tool-specific frontend branching.
- Shared fixtures exercise activation, buffering, sequence, recovery, interaction, generation,
  and close behavior in Python and JavaScript.
- Bundle release smoke invokes the real CLI launcher rather than calling Host directly.
- Current behavior remains documented by platform protocol/frontend authorities after the
  implementation lands; the active design spec owns temporary migration detail.
