# Pi-Style Minimal Core And Compaction Design

## Reader And Outcome

This design is for internal engineers planning the next Agent Core architecture
slices.

After reading it, an engineer should be able to split implementation work that
keeps EmbedAgent offline-first and Windows 7 compatible while moving the runtime
toward a smaller Pi-style core and a Codex/Pi-style durable compaction model.

## Context

EmbedAgent already moved much of the C/C++ workflow behind the bundled workflow
extension. The remaining risk is not architectural direction. The risk is that
the generic core still understands too many rich product concepts directly:
tool presentation metadata, workflow prompt shape, compact summary generation,
context replacement diagnostics, and replay read models.

Pi shows a useful small-core shape:

- agent state is small and explicit
- context transformation happens at one boundary before provider calls
- tool hooks are narrow pre/post execution hooks
- workflow, session tree, compaction, resources, and extension behavior live in
  harness or package layers

Codex shows a useful compaction shape:

- compaction installs a replacement history
- the original append-only history remains auditable
- resume reconstructs from the newest surviving replacement-history checkpoint
  plus the newer suffix
- pre-turn and mid-turn compaction differ only in where canonical initial
  context is reinjected

EmbedAgent should adopt these ideas without copying online dependencies,
remote compaction endpoints, cloud services, marketplaces, Docker, WSL, VS Code,
or Python versions newer than 3.8.

## Design Thesis

Agent Core should schedule and enforce. It should not explain every workflow.

The target core concepts are:

- session log append
- turn lifecycle
- context snapshot
- provider call
- tool execution gate
- permission policy
- extension event dispatch
- compacted-history installation

The default C/C++ workflow package should own C/C++ task language, phase
language, recipe guidance, quality-gate guidance, and workflow-specific tool
activation.

Diagnostic read models should explain what happened after the fact. They should
not become active policy surfaces.

## Target Runtime Boundary

The target boundary is:

```text
Frontend shell
  -> Hosted adapter
  -> Agent session facade
  -> Minimal turn loop
  -> Context assembler / compactor
  -> Provider adapter
  -> Tool action service
  -> Permission policy
  -> Extension event bus
  -> Workflow packages and project extensions
```

The minimal turn loop needs only a few injected operations:

- append user or command input
- build provider context
- project active tool schemas
- call provider
- execute requested tools
- decide whether to continue, stop, suspend, or compact
- append durable events

It should not know about C/C++ phases, task graph internals, recipe semantics,
GUI renderer keys, or frontend presentation metadata.

## Tool Surface Simplification

The model-visible tool contract should remain small:

- `name`
- `description`
- JSON parameter schema
- permission category
- source identity
- handler

Execution metadata that affects safety can remain close to execution:

- read-only flag
- concurrency safety
- interrupt behavior

Presentation and context-policy metadata should move out of the hot path:

- labels
- renderer keys
- diff preview hints
- activity kind
- context priority
- reducer key

Those fields can still exist, but as catalog or capability projections consumed
by frontends, diagnostics, or workflow packages. Tool execution should not need
to understand display vocabulary.

Dynamic extension tools should continue to require explicit permission
metadata, source metadata, no built-in replacement, and normal permission
checks.

## Extension Event Shape

The extension host should converge on a small event vocabulary:

- `resources_discover`
- `before_agent_start`
- `context`
- `tool_call`
- `tool_result`
- `compact_prepare`
- `compact_result`
- `workflow_state`
- `session_lifecycle`

Each event must define reducer semantics once:

- merge lists
- last patch wins
- first block wins
- first non-null result wins
- observer only

New extension behavior should attach to this bus instead of adding facade
methods for each new product concept.

Project extensions remain manifest-gated, workspace-bound, dependency-free at
runtime, and disabled by default.

## Prompt Surface Simplification

System prompts should describe constraints, not choreograph implementation.

The generic mode prompt should carry:

- current mode
- mode responsibility
- write boundary
- user-confirmation rule
- reminder that permission policy is runtime-owned

Workflow packages may add compact workflow prompt units:

- active workflow state
- active pack name
- task summary
- current quality or debug phase
- workflow-specific tool hints

Workflow prompt units should avoid long checklists unless the user explicitly
entered a planning workflow. The default model guidance should be light enough
that the agent can adapt to the current codebase instead of forcing a fixed
process template.

Local skills and prompts should remain explicit resource expansions. Discovery
may list them, but bodies should enter context only through explicit invocation
or a package-owned prompt unit.

## Compaction Model

Compaction should become a durable context rewrite point, not only diagnostic
metadata.

Introduce a compacted-history event that records:

- compaction id
- trigger: manual, auto threshold, provider context error, resume repair
- phase: pre-turn, mid-turn, standalone
- summary text
- first kept message or turn anchor
- replacement messages
- token counts before and after
- message counts before and after
- safe file activity
- evidence references
- whether an extension supplied or modified the summary

The append-only transcript remains the durable audit log. The compacted-history
event is the durable instruction for how future provider history is rebuilt.

### Context Assembly After Compaction

Context assembly should use:

1. the latest valid compacted replacement history
2. all transcript messages after that compaction point
3. current system, mode, workflow, resource, and project-memory prompt units

It should not repeatedly infer old windows from raw turns when a replacement
history is already installed.

The existing compact boundary read model can remain as diagnostics, but it
should project from the same compacted-history event once the new event exists.

### Summary Generation

Summary generation should be a replaceable strategy behind a compactor
interface.

Initial strategies:

- deterministic local summary using current reducers
- provider-generated summary using the configured offline-compatible provider
- extension-supplied summary through `compact_prepare`

The deterministic strategy is required as a fallback. Provider-generated
summary is optional and must fail closed to deterministic compaction.

The summary format should preserve:

- goal
- constraints and preferences
- completed work
- current in-progress work
- blockers
- key decisions
- next steps
- critical file paths, symbol names, commands, errors, and evidence refs

### Split-Turn Handling

If compaction would cut through a turn, the compactor should create a short
turn-prefix summary and keep the recent suffix intact. This preserves the
meaning of large tool-heavy turns without carrying every old tool result.

### Initial Context Reinjection

Pre-turn and manual compaction should avoid embedding current initial context
inside replacement history. The next normal provider request can inject current
system and workflow context.

Mid-turn compaction should insert current canonical context before the last
real user message or summary item so the next provider call sees a coherent
history shape without duplicating stale instructions.

## Recovery And Replay

Restore should eventually reconstruct active provider history by scanning for
the newest valid compacted-history checkpoint, installing its replacement
messages, then replaying only the newer suffix.

This keeps resume deterministic and avoids making context selection depend on
frontend history, timeline transport, or diagnostic reducer state.

Legacy compact boundaries remain readable. If a legacy boundary has no
replacement history, restore may use the current summary-plus-anchor behavior
until the compatibility window closes.

## Migration Slices

### Slice 1: Compaction Event Contract

Add the compacted-history event schema and reducer projection. Do not change
active context selection yet.

Acceptance:

- event validation rejects malformed anchors and duplicate ids
- reducer exposes latest compacted-history metadata
- existing compact boundary projection remains compatible

### Slice 2: Compactor Interface

Extract compact preparation, summary generation, and replacement-history
construction behind a small interface.

Acceptance:

- deterministic compactor reproduces current offline behavior
- provider-generated summary can be plugged in without changing the turn loop
- extension hooks can cancel or provide a summary without bypassing policy

### Slice 3: Context Assembly From Replacement History

Teach context assembly to use the latest compacted replacement history as the
base input.

Acceptance:

- provider request history after compaction is stable across repeated builds
- resume rebuilds the same context shape as live execution
- legacy compact boundaries continue to work

### Slice 4: Prompt And Tool Surface Slimming

Move presentation-only tool metadata and workflow-heavy prompt text out of
generic Core surfaces.

Acceptance:

- model-visible tool schemas are unchanged
- GUI catalog data remains available through projections
- generic mode prompt is shorter and workflow-neutral
- C/C++ package prompt units still provide C workflow guidance

### Slice 5: QueryEngine Facade Slimming

Move compact-boundary construction, workflow prompt append logic, and tool
hook routing out of the session facade where practical.

Acceptance:

- QueryEngine remains the compatibility facade
- new behavior is owned by compactor, extension host, tool action service, or
  lifecycle journal
- tests cover the same hosted C/C++ behavior

## Non-Goals

This design does not add:

- online extension registries
- runtime dependency installation
- public marketplaces
- Docker, WSL, VS Code, or Node runtime requirements
- mandatory network services
- replacement of built-in tools by project extensions
- general multi-agent orchestration in Agent Core
- remote-only compaction

## Documentation Updates When Implemented

Implementation slices should update the active source-of-truth documents when
they change behavior:

- architecture overview
- implementation roadmap
- tool contracts
- mode schema
- frontend protocol
- permission model, if new permission behavior is introduced
- design change log and development tracker

Completed slice-local design docs should be archived after durable conclusions
are synchronized into active docs.

## Reader-Test Checklist

A future implementer should be able to answer:

- Does this capability belong in Core, a workflow package, a project extension,
  or a frontend shell?
- Does this data affect active execution, or is it a read-only projection?
- Is compaction installing replacement history, or only writing diagnostics?
- Can the default C/C++ workflow still run offline on Windows 7?
- Can a bare Agent Core still run without C/C++ workflow vocabulary?

If a proposed change makes any answer unclear, it needs a smaller boundary
before implementation.
