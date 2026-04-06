# Agent Harness V2 Official Cutover Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Agent Harness V2 the only official implementation, remove legacy mode/tool/runtime architecture from product paths, and converge the codebase onto one coherent `explore/spec/build/debug/verify` system.

**Architecture:** Promote the current Harness V2 slices from sidecar packages into the formal product core, then delete the old parallel runtime/mode/tool path instead of continuing to bridge between them. The cutover is complete only when entrypoints, context assembly, permissions, protocol/frontend defaults, tests, and docs all speak the same V2 vocabulary and no model-facing legacy toolset remains.

**Tech Stack:** Python 3.8, QueryEngine/InProcessAdapter, Prompt/Mode Harness, recipe-centered tool runtime, session snapshots, file-backed state, FastAPI/PyWebView frontend.

---

## 1. Target State

The repository should converge to the following single official architecture:

- Official user-visible modes: `explore`, `spec`, `build`, `debug`, `verify`
- Official execution model: `mode + discipline_profile + execution_phase`
- Official model-facing tool vocabulary:
  - `read_file`
  - `list_dir`
  - `glob_files`
  - `grep_text`
  - `edit_file`
  - `write_file`
  - `list_recipes`
  - `run_recipe`
  - `report_quality_v2`
  - `task_status`
  - `task_update` or a consciously deferred replacement
  - `ask_user`
  - `record_failing_evidence`
- Official permission system: V2 rule schema and explanation model
- Official task truth source: `TaskGraph`, not prompt-only `manage_todos`
- Official runtime entrypoint: one `ToolRuntime` implementation, not `ToolRuntime + ToolRuntimeV2 + bridge`

The following should no longer be part of the formal architecture after cutover:

- `code` as a first-class mode
- model-facing `list_files` / `search_text` / `compile_project` / `report_quality`
- the current dual-path `ToolRuntime` plus `ToolRuntimeV2` arrangement
- legacy `PermissionPolicy` as the main permission engine
- `manage_todos` as the primary model-facing task system
- `loop.py::_legacy_run` and any similar fallback execution path

---

## 2. Gap Matrix

### 2.1 Core Loop And Runtime

**Current state**

- `QueryEngine` already routes `build/debug/verify` through Harness V2 context and pack selection.
- Real execution still depends on `ToolRuntime` as the public runtime object.
- `ToolRuntimeV2` and `tooling/bridge.py` are still sidecar layers rather than the official runtime core.

**Gap**

- There is still a dual-runtime architecture:
  - old `embedagent.tools.ToolRuntime`
  - new `embedagent.tools_v2.ToolRuntimeV2`
  - `HarnessToolBridge` stitching both together
- This is the clearest remaining sign that V2 is not yet the only implementation.

**Required cutover outcome**

- `embedagent.tools.ToolRuntime` becomes the single official runtime facade.
- V2 behavior is promoted into the official runtime contract.
- `tools_v2/` and `bridge.py` are either removed or reduced to internal migration shims that no product path references.

### 2.2 Modes, Prompting, And Configuration

**Current state**

- Harness V2 uses `build/debug/verify`.
- Repository-wide defaults still assume `code`.
- `modes.py`, `interaction.py`, config defaults, CLI/TUI/GUI defaults, tests, and docs still treat `code` as first-class.

**Gap**

- The product still has two competing mode vocabularies:
  - old: `explore/spec/code/debug/verify`
  - intended: `explore/spec/build/debug/verify`

**Required cutover outcome**

- `code` is removed as a first-class mode from config, prompt enums, protocol defaults, frontend defaults, and docs.
- `build` becomes the only implementation-mode concept.
- `build_system_prompt()` and Harness prompt units stop feeling like two stacked systems and become one coherent prompt contract.

### 2.3 Context Assembly And Workspace Intelligence

**Current state**

- `ContextManager` and reducer registry still key heavily on old tool names and old mode names.
- Duplicate suppression, artifact replacement, diagnostics aggregation, and context policies still speak legacy vocabulary (`list_files`, `search_text`, `compile_project`, `report_quality`, `code`).

**Gap**

- Even if the model sees V2 packs, the context/compression/intelligence layer is still optimized for the old tool ontology.
- This will keep leaking legacy semantics into prompts, summaries, hot-file selection, and replacement text.

**Required cutover outcome**

- Context policies, reducers, hot-tool priorities, replacement logic, diagnostics aggregation, and workspace intelligence all operate on V2 names and V2 mode semantics.
- `build` replaces `code` as the primary implementation context mode.
- Recipe-centered verification becomes first-class in the context layer.

### 2.4 Permission System

**Current state**

- `permissions_v2/` exists, but `PermissionPolicy` in `permissions.py` remains the production engine.
- Frontends and protocol still expose the old category model.

**Gap**

- The repository still has a parallel permission architecture:
  - old category sets and rule matching
  - new rule schema and explainer package not yet promoted

**Required cutover outcome**

- One official permission engine only.
- One official category vocabulary only.
- One official frontend-visible explanation format only.
- The current `permissions_v2` logic is either promoted into `permissions.py` or the old file is replaced and imports are updated accordingly.

### 2.5 Task System

**Current state**

- `TaskGraph` exists but is only partially used.
- `manage_todos` remains universal, user-visible, test-visible, and mode-visible.

**Gap**

- The current task model still has two truths:
  - harness-side `TaskGraph`
  - old todo-store driven `manage_todos`

**Required cutover outcome**

- `TaskGraph` becomes the single truth for model-facing workflow state.
- If a user-facing todo list remains, it must be a projection of `TaskGraph`, not a separate model-facing control plane.
- `task_status` and the final mutation mechanism replace `manage_todos` in model tool packs.

### 2.6 Protocol, Core Adapter, And Frontends

**Current state**

- Core Adapter, GUI backend, CLI, TUI, config, and many tests default to `code`.
- Session snapshot payloads now include Harness V2 fields, but the surrounding protocol semantics are still partly legacy.

**Gap**

- The product shell still boots, resumes, and serializes sessions in old vocabulary.

**Required cutover outcome**

- All entrypoints default to the official V2 mode set.
- Snapshot defaults, GUI/TUI session creation, slash-command help, and workflow hints all align with `build`.
- Frontend documentation and payload examples stop referencing `code`.

### 2.7 Legacy Execution Surface

**Current state**

- `loop.py` still contains a large `_legacy_run`.
- Old tool modules remain fully implemented.
- Old tests still treat legacy tool/runtime behavior as first-class.

**Gap**

- The codebase still pays maintenance cost for a fallback architecture that is no longer the design target.

**Required cutover outcome**

- `AgentLoop` becomes a thin compatibility wrapper around the official QueryEngine or is reduced further.
- Dead legacy execution branches are removed.
- Tests are rewritten to assert the official V2 architecture, not preserve legacy structure.

### 2.8 Documentation

**Current state**

- README, architecture, roadmap, mode-schema, tool-contracts, permission-model, frontend protocol, and deployment docs still center old mode/tool vocabulary.
- `docs/agent-harness-v2.md` itself still says “confirmed design baseline, not yet implemented”.

**Gap**

- The repository’s source-of-truth documents still describe the old system as the official product.

**Required cutover outcome**

- The official architecture docs describe only the post-cutover system.
- Historical V1/V2 language moves into archive/change-log material.
- `docs/agent-harness-v2.md` is rewritten from “future design” to “official architecture baseline”.

---

## 3. Completion Criteria

V2 is not “complete enough” until all of the following are true:

- There is exactly one official runtime path for model tool schema generation and execution.
- There is exactly one official mode vocabulary in code, protocol, config, tests, and docs.
- The context/compression/intelligence layer no longer keys on legacy tool names as first-class concepts.
- The permission engine is singular and promoted.
- The task truth source is singular and promoted.
- Frontend/API defaults no longer create `code` sessions.
- Legacy execution code exists only as a minimal compatibility shell or is removed.
- The documentation set no longer describes the old architecture as the product.

---

## 4. Recommended Execution Order

### Program 1: Runtime Promotion

**Objective**

Make V2 runtime behavior the official `embedagent.tools.ToolRuntime` implementation.

**Files**

- Modify: `src/embedagent/tools/__init__.py`
- Modify: `src/embedagent/tools/runtime.py`
- Move or merge: `src/embedagent/tools_v2/*.py`
- Remove after cutover: `src/embedagent/tooling/bridge.py`
- Update callers: `src/embedagent/query_engine.py`, `src/embedagent/inprocess_adapter.py`, `src/embedagent/cli.py`, `src/embedagent/frontend/tui/bootstrap.py`, `src/embedagent/frontend/gui/launcher.py`

**Exit criteria**

- No product path instantiates `ToolRuntimeV2`.
- No product path depends on `HarnessToolBridge`.
- `embedagent.tools.ToolRuntime` exposes pack-aware schema/execution/capability APIs directly.

### Program 2: Mode Vocabulary Cutover

**Objective**

Make `explore/spec/build/debug/verify` the only first-class mode set.

**Files**

- Modify: `src/embedagent/modes.py`
- Modify: `src/embedagent/interaction.py`
- Modify: `src/embedagent/config.py`
- Modify: `src/embedagent/cli.py`
- Modify: `src/embedagent/frontend/tui/launcher.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/core/adapter.py`
- Update tests that assert `code`

**Exit criteria**

- `code` is gone as a first-class mode.
- All defaults, enums, and examples use `build`.
- Session snapshots and frontend boot flows create `build` or `explore`, never `code`.

### Program 3: Context And Intelligence Cutover

**Objective**

Make context assembly understand only the official V2 tool/mode ontology.

**Files**

- Modify: `src/embedagent/context.py`
- Modify: `src/embedagent/workspace_intelligence.py`
- Modify any recipe/diagnostics aggregation helpers touched by those modules

**Exit criteria**

- Reducers exist for `list_dir/glob_files/grep_text/run_recipe/report_quality_v2/task_status/record_failing_evidence`.
- Replacement text and duplicate suppression no longer mention `list_files/search_text` as first-class.
- Context policy defaults are defined for `explore/spec/build/debug/verify`.

### Program 4: Permission And Task Truth Cutover

**Objective**

Remove dual truth in permission and task systems.

**Files**

- Promote/replace: `src/embedagent/permissions.py` with V2 logic
- Merge from: `src/embedagent/permissions_v2/*.py`
- Modify: `src/embedagent/harness/task_graph.py`
- Modify: `src/embedagent/harness/runner.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Replace model-facing todo tools in official packs

**Exit criteria**

- One official permission engine only.
- One official task truth source only.
- `manage_todos` is not part of the official model tool packs.

### Program 5: Frontend And Protocol Officialization

**Objective**

Make API/frontend/state layers describe the official V2 product and nothing else.

**Files**

- Modify: `src/embedagent/protocol/__init__.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/webapp/*`
- Modify: `src/embedagent/frontend/tui/*`

**Exit criteria**

- Frontend payloads, UI labels, default modes, and inspector summaries use only official V2 vocabulary.
- Tool catalog and runtime panels show official V2 tool names.

### Program 6: Legacy Deletion And Documentation Rewrite

**Objective**

Delete the old architecture as architecture, not just stop using it.

**Files**

- Reduce or remove: `src/embedagent/loop.py`
- Delete or rewrite legacy-only tool modules once merged
- Rewrite:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`

**Exit criteria**

- Docs describe one architecture only.
- The remaining old terminology is limited to archive/changelog/history material.

---

## 5. Immediate Next Work

The most efficient next slice is:

1. **Promote runtime first**
   - Make the official `ToolRuntime` V2-native.
   - This removes the biggest architectural split.
2. **Then cut over mode vocabulary**
   - Replace `code` with `build` everywhere.
   - This removes the biggest conceptual split.
3. **Then rewire context**
   - Otherwise the system will keep emitting old tool/mode semantics after runtime cutover.
4. **Then promote permissions/task truth**
   - This eliminates the remaining dual-control planes.
5. **Then rewrite docs and delete legacy branches**
   - Documentation rewrite should happen after the runtime/mode truth is settled, not before.

---

## 6. Decision Summary

The repository is **not** at “final V2, safe to delete legacy now”.

It is at:

- **main loop cutover started**
- **product perimeter still legacy-labeled**
- **runtime, mode, context, permission, task, and docs not yet unified**

That means the right next step is **not** “remove a few old files”.

The right next step is **officialization by subsystem**, then deletion:

- first runtime
- then mode vocabulary
- then context/intelligence
- then permission/task truth
- then frontends/protocol
- then legacy deletion and doc rewrite

Only after those programs finish should the repository claim that Agent Harness V2 is the product, rather than an in-progress side architecture.
