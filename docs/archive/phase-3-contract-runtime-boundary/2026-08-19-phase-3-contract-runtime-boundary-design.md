# Phase 3 Contract And Runtime Boundary Design

> Status: approved for implementation on 2026-08-19.

## Goal

Close the remaining contract and runtime-boundary debt without introducing a generic service bag or a
second lifecycle runtime. The phase makes selected runtime closure, public failure diagnostics, and
Host/extension teardown mechanically verifiable while preserving a small evolution path toward a
Cordis-like Fiber model.

## Scope

This phase contains three independently testable boundaries:

1. Application-selected runtime closure validation.
2. Safe diagnostics at the Protocol/Host/frontend boundary.
3. Owner-scoped shutdown, quiescence, and disposer cleanup.

Windows 7 clean-machine evidence, real C/C++ project validation, and the isolated C++ wheel proof remain
release gates. This phase does not perform a physical repository split, remove all platform mode/profile
contracts, add remote extension loading, or introduce dynamic dependency injection.

## Invariants

- `bundle-plan.json` is the only selected runtime closure input. Runtime code does not import
  `embedagent_composition` and no validator maintains a duplicate global tool list.
- `SessionEventEnvelope`, snapshots, frontend DTOs, extension diagnostics, and telemetry contain only
  safe data. Raw exception text, exception arguments, prompts, source, credentials, and raw tool output
  never cross these boundaries.
- Every runtime-owned registration or resource has one owner scope and one idempotent disposer.
- Shutdown closes admission before waiting for in-flight work, then disposes children before parents in
  reverse registration order. Repeated shutdown has the same result as the first call.
- Core remains dependency-free from Protocol/Host/Product. The lifecycle primitive is the existing
  `RegistrationScope`; this phase does not create a generic Context/service repository.

## Boundary A: Selected Runtime Closure

### Ownership

Build-time composition continues to emit `CompiledBundlePlan` with the selected
`runtime_capability_ids`, `runtime_component_ids`, `asset_ids`, `project_distribution_ids`,
`registration_entries`, and `gate_ids`. Product runtime code consumes those fields through the immutable
`BundleRuntimePolicy` projection in `src/embedagent/bundle_policy.py`.

The policy loader validates the plan/manifest hash and identity, then validates all selected lists as
unique, non-empty, schema-compatible data. The distribution checker remains responsible for checking
physical wheel and asset contents; the runtime loader never reconstructs that inventory from imports or
environment probing.

### Required checks

- application id, shell id, registration entry, distribution id, capability id, component id, asset id,
  and gate id are present in the selected plan and have the expected syntax;
- selected application registration entries are a subset of the compiled plan and have no duplicates;
- selected runtime components and capabilities are present and internally consistent;
- plan hash, flavor, schema version, and bundle manifest identity agree;
- missing, duplicated, unknown, or mismatched closure data fails closed before Host startup.

The returned policy exposes frozen tuples only. It does not expose factories, live registries, mutable
session objects, or composition compiler objects.

## Boundary B: Safe Diagnostics

### Public failure DTO

`embedagent_protocol.FailureRecord` is the only public failure structure. Its allowed fields are
`code`, `retryable`, `source`, `phase`, `kind`, `correlation_id`, `safe_message`, and `exception_type`.
The existing `message` field, where retained by the wire contract, is always the same safe message and
never accepts exception text.

`failure_for_exception()` classifies exceptions without serializing their text. The original exception
may remain available to the current synchronous caller through normal exception chaining, but is never
stored in a session projection or emitted in a public event.

### Propagation rules

- `session_error` contains `failure` and stable lifecycle fields only; raw `error` fields are removed.
- `ManagedSession` stores a safe `last_failure` projection; snapshots and frontend fixtures use
  `last_failure`, not a raw `last_error` compatibility field.
- Core `ExtensionDiagnostic` remains Protocol-independent and stores only safe code/kind/type/message
  fields. Host converts it into the public failure projection.
- failed frontend tool events retain structured failure and remove the raw error string at the
  `SessionEventEncoder` boundary. Durable model-visible observations remain owned by the Core session
  ledger and are not conflated with frontend diagnostics.
- project extension load failures and interaction resume failures use the same safe classification path.

Static architecture guards prohibit `str(exc)`, `repr(exc)`, and `exception.args` in public payload
construction. Tests inspect serialized payloads and nested metadata, not only top-level fields.

## Boundary C: Lifecycle And Future Fiber Evolution

### Scope tree

The Host runtime owns a `hosted-runtime` root `RegistrationScope`. Application extension registrations,
project extension registrations, context reducers, workflow caches, and session-owned handles are
registered under child scopes. The scope owns reversible effects only; it does not resolve dependencies
or retain arbitrary services.

### Shutdown protocol

1. Mark the root scope quiescing so new sessions, turns, registrations, and operations are rejected.
2. Signal active sessions and resolve pending interaction waits with a typed cancellation outcome.
3. Join active and resume workers until the configured deadline; report non-quiescence without silently
   clearing live resources.
4. Dispose extension/project/session children in reverse ownership order, continuing after individual
   disposer failures and aggregating failures.
5. Clear only in-memory runtime projections and mark the adapter closed. Durable transcript/session data
   remains owned by the stores.

`close()` and `shutdown()` are idempotent and concurrent callers share the same completion barrier. A
failed disposer cannot prevent later disposers from running.

### Cordis/Fiber preparation

The phase strengthens the existing `RegistrationScope` with explicit owner identity, admission and
leakage observations, while preserving its synchronous Python 3.8 API. Its parent/child ancestry,
operation admission, quiescence barrier, reverse effects, and idempotence are the only concepts reserved
for a future Fiber implementation. No generic `inject`, event repository, or runtime service lookup is
added in this phase.

## Testing Strategy

### Contract tests

- valid selected plans expose all closure tuples through `BundleRuntimePolicy`;
- malformed, duplicated, unknown, stale, or cross-flavor closure data fails closed;
- runtime policy imports remain product-local and composition remains build-time only.

### Diagnostics tests

- exception text and nested secrets are absent from `FailureRecord`, session error events, snapshots,
  extension diagnostics, and failed-tool frontend events;
- sync and worker failures, interaction resume failures, and project extension load failures all use the
  same safe fields;
- static source guards reject new raw exception serialization paths.

### Lifecycle tests

- scope ownership, idempotent disposer, reverse order, quiescence, concurrent close, and disposer
  aggregation;
- adapter shutdown rejects new admission, joins workers, clears extension/reducer/cache state, and is
  safe to call repeatedly;
- sequential adapter/application/project-extension reload does not accumulate handlers or registrations.

### Full gates

Run the focused tests, pre-release architecture guards, full regular partition, locked lint, and
`git diff --check`. The selected C++ distribution/isolation smoke and Win7 evidence remain explicitly
unchecked release gates until their external prerequisites are available.

## Exit Criteria

The phase is complete only when:

- each selected closure field has one producer, one runtime projection, and one validator;
- no public diagnostic path can expose raw exception text or retired `last_error` state;
- every runtime-owned effect is scope-owned and teardown is quiescent, idempotent, and observable;
- active platform/application authorities describe the new ownership model without completion diaries;
- all implementation-plan checkboxes map to passing tests and the full regular partition is green.
