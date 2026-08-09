# Architecture Decisions

## 2026-07-27: Minimal Agent Core Convergence Shape

**Status:** Implemented

Adopt a deep public `AgentSession` facade over a deliberately limited internal
effect/reducer kernel.

The public standalone flow remains `Agent.create -> Agent.open ->
AgentSession.submit`. Internally, `AgentKernel` plans and accepts three closed
effect families for context assembly, provider requests, and tool batches.
`AgentLoop` is a small commit-execute-resume driver. `SessionJournal`
appends events through `SessionLogPort` before `SessionReducer` applies them to
live state. The same reducer handlers restore persisted sessions.

Effects remain private and are not extension points. Extensions continue
through the existing capability, `AgentExtensionHost`, tool runtime, permission,
and workflow-patch contracts. Host continues through the non-root
`HostedSessionController` boundary and consumes frozen projections without
owning or passing mutable Core `Session` objects.

`AgentPorts.extension_manager` is the hosted shared-manager path and
`RuntimeDefinition.extensions` is the standalone declarative path. Supplying
both is invalid and must fail fast.

This shape was chosen because a single generic runtime command entry would hide
rather than remove orchestration complexity, while a fully general effect
framework would add more surface than the runtime needs. The selected hybrid
keeps the common SDK path deep and small, makes durable state single-writer, and
preserves explicit permission, interaction, compaction, and crash-recovery
semantics required by the offline hosted product.

The detailed design is recorded in
`docs/superpowers/specs/2026-07-27-minimal-agent-core-convergence-design.md`.

Implemented on 2026-07-30. `QueryEngine`, `SessionRestorer`,
`ExecutionTracer`, and `CircuitBreaker` were deleted without compatibility
aliases; Host mutable Core `Session` ownership was removed; and architecture,
full Python, six-distribution isolation, lint, and GUI gates passed. Clean
Windows 7/WebView2 bundle acceptance and real C/C++ project validation remain
separate external gates.

## 2026-08-09: Official Bundle Recipes Compile To One Immutable Plan

**Status:** Accepted; implementation pending

Adopt a small official bundle recipe registry with `minimal-cli` and
`cpp-desktop` as the first flavors. Keep flavor (product contents) orthogonal to
profile (build and validation assurance). Each flavor compiles through the
trusted Agent component catalog and the single offline runtime contract into
one immutable, hash-bound bundle plan consumed by dependency export, staging,
validation, release identity, and evidence selection.

Portable offline flavors continue to build, check, and wheel-only install the
exact six project distributions. Flavor configuration cannot enumerate wheels,
runtime assets, binary paths, or release gates. `minimal-cli` reduces shells,
third-party features, external assets, launchers, and applicable evidence while
keeping the six-distribution invariant; `cpp-desktop` preserves the current
full C/C++ desktop contract. Arbitrary product-definition packaging remains
private until the production catalog and fail-closed plan validation are proven.

The detailed design is recorded in
`docs/superpowers/specs/2026-08-09-configurable-agent-bundle-flavors-design.md`.
