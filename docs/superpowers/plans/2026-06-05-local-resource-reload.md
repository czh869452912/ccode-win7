# Local Resource Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Slice 3 of the self-extensible Agent Core by discovering local `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` resources, adding an explicit reload command/API, and recording resource reload diagnostics in transcript-backed session truth.

**Architecture:** Add a small file-only local resource scanner and wire it through `ToolRuntime`, `InProcessAdapter`, and the existing `ExtensionManager.discover_resources(...)` hook. Recipe resources feed the existing `list_recipes` / `run_recipe` path; skills and prompts are discovered and surfaced but not executed as Python code.

**Tech Stack:** Python 3.8, standard library JSON/OS APIs, existing `ExtensionManager`, `ToolRuntime`, `InProcessAdapter`, `TranscriptStore`, pytest.

---

## Scope

Included:

- Discover `.embedagent/skills/`, `.embedagent/prompts/`, and `.embedagent/recipes/`.
- Parse `.embedagent/recipes/*.json` recipe files into the existing workspace recipe contract.
- Merge extension-contributed resource paths through `ExtensionManager.discover_resources(...)`.
- Add `ToolRuntime.reload_resources()` / `local_resources()` as the runtime API.
- Add `InProcessAdapter.reload_resources(...)` and `/resources reload` as the hosted API/command.
- Append `resource_discovered` / `resource_reloaded` transcript events with counts and diagnostics.
- Update durable architecture docs and mark Slice 1/2 governance tail items.

Excluded:

- Loading `.embedagent/extensions/<name>/extension.py`.
- Executing skill or prompt files.
- Installing dependencies.
- Frontend custom rendering for resources.
- Remote registries, marketplace behavior, or online downloads.

## File Structure

- Create `src/embedagent/local_resources.py`
  - File-only scanner for local skills, prompts, and recipes.
  - Safe workspace-bound path resolution and concise diagnostics.

- Modify `src/embedagent/workspace_recipes.py`
  - Load recipe JSON files from `.embedagent/recipes` and extension-contributed recipe paths.

- Modify `src/embedagent/tools/_base.py`
  - Store resource paths and cached resource snapshot on `ToolContext`.

- Modify `src/embedagent/tools/runtime.py`
  - Expose `reload_resources()` and `local_resources()` APIs.

- Modify `src/embedagent/inprocess_adapter.py`
  - Merge extension resource paths, update tool runtime, write transcript events, project resource state, and implement `/resources`.

- Modify `src/embedagent/slash_commands.py`
  - Register `/resources [reload]`.

- Add `tests/test_local_resources.py`
  - Focused scanner/runtime/adapter tests.

- Update docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - Slice plan checkboxes / archive-ready notes.

---

## Tasks

### Task 1: Local Resource Scanner

- [ ] Write failing tests for skill/prompt discovery and recipe JSON parsing.
- [ ] Implement `local_resources.discover_local_resources(...)`.
- [ ] Run scanner tests.
- [ ] Commit scanner.

### Task 2: Runtime Recipe Integration

- [ ] Write failing tests proving `.embedagent/recipes/*.json` appears in `list_workspace_recipes()` and `run_recipe`.
- [ ] Wire resource recipe paths through `workspace_recipes.py`, `ToolContext`, and `ToolRuntime`.
- [ ] Run recipe/runtime focused tests.
- [ ] Commit runtime integration.

### Task 3: Adapter Reload Command/API

- [ ] Write failing tests for `InProcessAdapter.reload_resources(...)`, `/resources reload`, transcript events, and extension-contributed resource paths.
- [ ] Implement adapter reload plumbing and slash command.
- [ ] Run adapter/resource tests.
- [ ] Commit reload command/API.

### Task 4: Documentation And Slice Governance

- [ ] Update source-of-truth docs to state local resource discovery/reload is official while Python extension loading remains deferred.
- [ ] Mark Slice 2 plan checkboxes complete and add archive-ready notes for completed Slice 1/2 materials.
- [ ] Add Slice 3 tracker and design-change entries.
- [ ] Commit docs.

### Task 5: Final Verification

- [ ] Run `uv run pytest tests/test_local_resources.py tests/test_tools_package.py tests/test_inprocess_adapter_frontend_api.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py tests/test_workflow_extensions.py -v`.
- [ ] Run fast suite with workspace temp directory.
- [ ] Run focused `ruff check`.
- [ ] Inspect final git state.
