# Architecture Decisions

## 2026-07-27: Minimal Agent Core Convergence Shape

**Status:** Approved

Adopt a deep public `AgentSession` facade over a deliberately limited internal
effect/reducer kernel.

The public standalone flow remains `Agent.create -> Agent.open ->
AgentSession.submit`. Internally, `AgentKernel` plans and accepts three closed
effect families for context assembly, provider requests, and tool batches.
`AgentLoop` becomes a small commit-execute-resume driver. `SessionJournal`
appends events through `SessionLogPort` before `SessionReducer` applies them to
live state. The same reducer handlers restore persisted sessions.

Effects remain private and are not extension points. Extensions continue
through the existing capability, `AgentExtensionHost`, tool runtime, permission,
and workflow-patch contracts. Host continues through the non-root
`HostedSessionController` boundary but must stop owning or passing mutable Core
`Session` objects.

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
