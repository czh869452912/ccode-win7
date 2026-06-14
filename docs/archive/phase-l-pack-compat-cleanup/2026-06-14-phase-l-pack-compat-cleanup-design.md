# Phase L Pack Compatibility Cleanup Design

## Context

Phase A through Phase K moved Agent Core toward the Pi-inspired target through durable reducers, source-aware extension dispatch, lifecycle boundaries, workflow package ownership, self-extension authoring, offline bundle contracts, turn snapshots, capability/runtime read models, compaction state, and recovery state.

The current roadmap now names stale compatibility cleanup as one of the remaining in-repo priorities. A concrete leftover is `src/embedagent/tooling/packs.py`: it re-exports C/C++ workflow pack constants from `embedagent.harness.packs`. Product code already imports pack truth from the harness package. The remaining re-export exists only as a historical compatibility path.

## Goal

Remove the obsolete `embedagent.tooling.packs` compatibility module and make `embedagent.harness.packs` the only current source for bundled C/C++ workflow pack definitions.

## Non-Goals

- Do not change pack contents.
- Do not change active tool selection.
- Do not change `ExtensionManager.allowed_tool_names(...)`, `CHarnessWorkflowExtension.allowed_tool_names(...)`, or runtime schema projection.
- Do not remove `embedagent.tooling.contracts` or `embedagent.tooling.result_budget`; those remain live support modules.
- Do not attempt real Win7 bundle smoke in this slice.
- Do not delete unrelated compatibility tests or public imports.

## Options Considered

### Option A: Delete Only `embedagent.tooling.packs`

Delete the historical re-export module, remove pack aliases from `embedagent.tooling.__init__`, and update tests/docs to import pack definitions from `embedagent.harness.packs`.

This is the recommended option. It removes a stale path while preserving behavior and keeping the slice small enough to verify thoroughly.

### Option B: Delete The Entire `embedagent.tooling` Package

Remove `tooling/` completely and migrate `contracts.py` and `result_budget.py`.

This is too broad for Phase L. `result_budget.py` is still covered by tests and can remain a focused utility until a later cleanup proves it is dead or has a better home.

### Option C: Keep The Re-Export But Mark It Deprecated

Add warnings or comments to `tooling.packs`.

This conflicts with the current product stage. The project is not online yet and has explicitly chosen to avoid compatibility baggage when an old path is no longer official.

## Chosen Design

Use Option A.

`src/embedagent/tooling/packs.py` will be removed. The package root `src/embedagent/tooling/__init__.py` will no longer import or export `BUILD_LITE_PACK`, `CORE_PACK`, or `pack_tool_names`. Any remaining pack tests will import from `embedagent.harness.packs`.

The architecture test suite will gain an explicit guard:

- `importlib.util.find_spec("embedagent.tooling.packs") is None`
- `embedagent.tooling` does not expose pack aliases

This keeps the deletion durable and prevents a future reintroduction of the old global pack registry.

## Data Flow

Before:

`embedagent.tooling.packs -> embedagent.harness.packs -> CHarnessWorkflowExtension`

After:

`embedagent.harness.packs -> CHarnessWorkflowExtension`

No runtime data flow changes. Tool activation still flows through `CHarnessWorkflowExtension`, `ExtensionManager`, `AgentExtensionHost`, and `ToolRuntime.schemas_for(..., tool_names=...)`.

## Error Handling

Importing `embedagent.tooling.packs` should now fail through normal Python import semantics. Current product code must not rely on that import path.

## Testing

- Add a failing architecture test proving the compatibility module and package-root aliases still exist.
- Update pack ownership tests to use `embedagent.harness.packs`.
- Run focused workflow/tooling tests.
- Run harness tests.
- Run fast non-slow/non-GUI tests.
- Run ruff, black check, and git diff check.

## Documentation

Update source-of-truth docs to record Phase L as completed:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/agent-harness-v2.md`
- `docs/tool-contracts.md`
- `docs/pi-inspired-agent-core-blueprint.md`

Archive this design and the implementation plan after the implementation lands.

## Acceptance Criteria

- `src/embedagent/tooling/packs.py` is gone.
- `embedagent.tooling` no longer re-exports workflow pack names.
- C/C++ workflow pack truth remains available from `embedagent.harness.packs`.
- Active tool selection and schema projection behavior remain unchanged.
- Focused, harness, and fast test suites pass.
- Docs describe Phase L and no longer call `tooling.packs` a live compatibility export.
