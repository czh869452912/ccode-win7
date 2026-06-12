# Self-Extensible Documentation Cutover Slice 6 Design

## 1. Background

Slice 6 closes the self-extensible Agent Core program described in
`docs/archive/self-extensible-agent-core/2026-06-04-self-extensible-agent-core-design.md`.

Slices 1-5 have already landed the runtime behavior:

- capability extension contract and diagnostics
- dynamic in-process tool registration
- file-only local resource reload for `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes`
- manifest-gated project-local Python extensions under `.embedagent/extensions/<name>/extension.json`
- `QueryEngine` slimming through `AgentExtensionHost`, `AgentToolActionService`, and `AgentLoop`

The active source-of-truth docs already mention most of this, but the documentation
cutover is not yet complete. Some module docs still describe the older pre-Slice-5
execution spine, the self-extensible archive index does not list the completed Slice 5
materials, and one completed Slice 3 plan is still in the active `docs/superpowers/plans`
directory.

Slice 6 is documentation-only by design. Its job is to make the current product
baseline easy for future agents and contributors to discover without reading the
whole historical archive.

## 2. Goals

Slice 6 must make the following statements true in active documentation:

1. Local offline self-extension is part of the official architecture.
2. Remote registries, plugin marketplaces, online installs, dependency installation,
   built-in tool replacement, and general multi-agent orchestration remain non-goals.
3. The default C/C++ harness is a bundled built-in extension installed by hosted
   product paths, not irreducible Agent Core.
4. `QueryEngine` is a session-scoped facade and transcript/session mutation owner.
5. `AgentExtensionHost`, `AgentToolActionService`, and `AgentLoop` are the official
   session-engine sub-boundaries for extension dispatch, non-LLM action execution,
   and turn-loop orchestration.
6. Workspace-local resources and project-local Python extensions are distinct:
   resource reload is file-only, while Python extension loading is an explicit
   hosted-adapter operation.
7. Module docs and archive indexes match the current code and active architecture docs.

## 3. Non-Goals

Slice 6 does not:

- change runtime code
- add new extension APIs
- add a user-facing extension authoring guide
- add examples under `.embedagent/`
- introduce documentation tests beyond lightweight textual audits if needed
- re-open the product scope for marketplaces, online installs, dependency managers,
  general plugin ecosystems, browser automation, or multi-agent orchestration

If a later slice wants an extension authoring guide or sample extension, it should be
planned separately after the official source-of-truth docs are aligned.

## 4. Current Findings

The active architecture docs are mostly correct after Slice 5, especially:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/tool-contracts.md`
- `docs/agent-harness-v2.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The remaining documentation drift is concentrated in these areas:

- `docs/modules/agent-core.md` still lists `QueryEngine`, `InProcessAdapter`, and
  `ManagedSession` as the whole core ownership model. It should include
  `AgentLoop`, `AgentToolActionService`, `AgentExtensionHost`, `ExtensionManager`,
  and project-local extension loading.
- `docs/modules/tools-and-tooling.md` still describes tool flow as
  `Harness -> ToolRuntime -> tool ops`. It should mention explicit active schema
  projection, source-aware dynamic tools, resource reload, and permission-gated
  extension tools.
- `docs/modules/harness.md` should state that the default C/C++ harness is bundled
  as the built-in workflow extension and externally projects generic workflow state.
- `docs/modules/session-runtime.md` should mention that session snapshots include
  extension diagnostics and project extension state.
- `docs/modules/permissions-and-context.md` should connect permission enforcement
  to extension-registered tools and extension pre/post hooks.
- `docs/modules/protocol-and-core.md` should describe resource reload and extension
  diagnostics as part of the stable frontend/core contract.
- `docs/archive/self-extensible-agent-core/README.md` does not list the Slice 5
  design and plan files.
- `docs/superpowers/plans/2026-06-05-local-resource-reload.md` is a completed
  Slice 3 plan that should move to `docs/archive/self-extensible-agent-core/`.

Historical documents may still contain old statements such as "project-local
extension discovery remains out of scope." That is acceptable inside dated archive
entries and older changelog records, but active docs must not present that as the
current product baseline.

## 5. Chosen Approach

Use a strict documentation cutover:

1. Update active source-of-truth docs only where they still need alignment.
2. Update module docs so code ownership and test guidance match the Slice 5 execution
   spine.
3. Move completed self-extensible slice materials out of active `docs/superpowers`
   when they are still present.
4. Update `docs/archive/self-extensible-agent-core/README.md` so the archive package
   accurately lists completed slices.
5. Add one `DC-128` design-change-log entry and one development tracker row for
   Slice 6.
6. Keep all changes documentation-only unless a textual audit uncovers an active-doc
   regression that is better captured by an existing test.

This keeps Slice 6 close to the original migration plan: "Update README, AGENTS, and
active docs; state local offline self-extension as architecture; keep marketplace,
online install, and general multi-agent orchestration as non-goals; archive
superseded slice-local docs."

## 6. Documentation Scope

### 6.1 Project Source-Of-Truth Docs

Review and update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`

Expected edits should be small in files that Slice 5 already updated. The goal is
consistency, not rewriting every document.

### 6.2 Module Docs

Update module docs that still describe pre-self-extensible ownership:

- `docs/modules/agent-core.md`
- `docs/modules/tools-and-tooling.md`
- `docs/modules/harness.md`
- `docs/modules/session-runtime.md`
- `docs/modules/permissions-and-context.md`
- `docs/modules/protocol-and-core.md`
- `docs/modules/README.md`

Each module doc should answer:

- which current files own the behavior
- which boundary owns extension-related responsibilities
- which tests are the right regression entry points
- which active source-of-truth docs must be updated when the module changes

### 6.3 Archive And Active Slice Cleanup

Update:

- `docs/archive/self-extensible-agent-core/README.md`
- `docs/README.md`

Move completed Slice 3 local-resource plan from:

- `docs/superpowers/plans/2026-06-05-local-resource-reload.md`

to:

- `docs/archive/self-extensible-agent-core/2026-06-05-local-resource-reload.md`

Do not move unrelated active superpowers materials:

- documentation governance baseline
- GUI IDE redesign
- workflow extension boundary design

Those are outside this slice unless the user separately asks to close them.

## 7. Verification Strategy

Because Slice 6 is documentation-only, verification should focus on textual
consistency and repository hygiene:

- `git diff --check`
- `rg` checks for current active docs that still present local extension loading as
  future-only or out-of-scope
- `rg` checks that `AgentExtensionHost`, `AgentToolActionService`, and `AgentLoop`
  are discoverable from active docs and module docs
- `rg` checks that Slice 3 local-resource plan no longer lives under active
  `docs/superpowers/plans`
- optional focused pytest only if documentation edits require touching tests or code

The fast Python suite is not required for a docs-only cutover unless implementation
scope changes.

## 8. Completion Criteria

Slice 6 is complete when:

- active source-of-truth docs state that local offline self-extension is official
  architecture
- module docs reflect the current execution spine and extension boundaries
- archive README lists Slice 1-5 materials and the Slice 3 local-resource plan
- no completed self-extensible slice plan remains in active `docs/superpowers/plans`
- `docs/design-change-log.md` and `docs/development-tracker.md` record Slice 6
- verification commands pass
- this Slice 6 design and its implementation plan are archived after global docs are
  synchronized
