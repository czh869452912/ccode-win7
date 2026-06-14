# Phase L Pack Compatibility Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the obsolete `embedagent.tooling.packs` compatibility re-export so bundled C/C++ workflow packs are owned only by `embedagent.harness.packs`.

**Architecture:** This is a stale-path deletion slice. Product behavior remains unchanged because runtime activation already flows through `CHarnessWorkflowExtension`, `ExtensionManager`, `AgentExtensionHost`, and explicit `ToolRuntime.schemas_for(..., tool_names=...)`; this plan only removes a historical import surface.

**Tech Stack:** Python 3.8, pytest, ruff, black, existing harness/workflow extension modules.

---

## File Structure

- Modify `tests/test_workflow_extensions.py`
  Add deletion guards and update the pack ownership test to import from `embedagent.harness.packs`.
- Modify `src/embedagent/tooling/__init__.py`
  Keep only live `ToolSpecV2` and `apply_aggregate_budget` exports.
- Delete `src/embedagent/tooling/packs.py`
  Remove the obsolete re-export module.
- Modify source-of-truth docs:
  `README.md`, `AGENTS.md`, `docs/overall-solution-architecture.md`, `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/design-change-log.md`, `docs/agent-harness-v2.md`, `docs/tool-contracts.md`, `docs/pi-inspired-agent-core-blueprint.md`.
- Move slice docs after implementation:
  `docs/superpowers/specs/2026-06-14-phase-l-pack-compat-cleanup-design.md`
  and this plan into `docs/archive/phase-l-pack-compat-cleanup/`.

---

### Task 1: Add Failing Architecture Guard

**Files:**
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write the failing test**

Add `import importlib.util` near the top of `tests/test_workflow_extensions.py`.

Add this test near the existing workflow pack tests:

```python
def test_tooling_package_no_longer_reexports_c_workflow_packs():
    import embedagent.tooling as tooling

    assert importlib.util.find_spec("embedagent.tooling.packs") is None
    for name in ("BUILD_LITE_PACK", "CORE_PACK", "DEBUG_LITE_PACK", "VERIFY_PACK", "PACKS", "pack_tool_names"):
        assert not hasattr(tooling, name)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_tooling_package_no_longer_reexports_c_workflow_packs -v
```

Expected: FAIL because `embedagent.tooling.packs` still exists and package-root aliases are still exported.

---

### Task 2: Remove The Compatibility Re-Export

**Files:**
- Modify: `tests/test_workflow_extensions.py`
- Modify: `src/embedagent/tooling/__init__.py`
- Delete: `src/embedagent/tooling/packs.py`

- [ ] **Step 1: Update pack ownership test imports**

Replace:

```python
from embedagent.tooling.packs import BUILD_LITE_PACK, CORE_PACK, DEBUG_LITE_PACK, VERIFY_PACK
```

with:

```python
from embedagent.harness.packs import (
    C_WORKFLOW_BUILD_LITE_PACK,
    C_WORKFLOW_CORE_PACK,
    C_WORKFLOW_DEBUG_LITE_PACK,
    C_WORKFLOW_VERIFY_PACK,
)
```

Update assertions to use the `C_WORKFLOW_*` names.

- [ ] **Step 2: Remove package-root aliases**

Change `src/embedagent/tooling/__init__.py` to:

```python
from embedagent.tooling.contracts import ToolSpecV2
from embedagent.tooling.result_budget import apply_aggregate_budget

__all__ = [
    "apply_aggregate_budget",
    "ToolSpecV2",
]
```

- [ ] **Step 3: Delete old module**

Delete:

```text
src/embedagent/tooling/packs.py
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_tooling_package_no_longer_reexports_c_workflow_packs tests/test_workflow_extensions.py::test_core_pack_no_longer_contains_harness_workflow_tools tests/test_workflow_extensions.py::test_harness_package_owns_c_workflow_packs tests/test_tooling_budget_v2.py -v
```

Expected: PASS.

---

### Task 3: Synchronize Docs

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`

- [ ] **Step 1: Update Phase status**

Update current architecture summaries from `Phase A-K` to `Phase A-L`, with Phase L described as pack compatibility cleanup.

- [ ] **Step 2: Remove live compatibility wording**

Replace live references that say `src/embedagent/tooling/packs.py` is a compatibility export with wording that says it has been removed and pack truth now lives only in `src/embedagent/harness/packs.py`.

- [ ] **Step 3: Add design change log entry**

Add a new top entry:

```markdown
## DC-146 - Phase L pack compatibility cleanup

- 日期：2026-06-14
- 状态：Accepted
- 变更类型：Architecture cleanup
- 背景：Phase D made `embedagent.harness.packs` the owner of default C/C++ workflow packs, but `embedagent.tooling.packs` remained as a compatibility re-export.
- 决策：删除 `src/embedagent/tooling/packs.py` and package-root pack aliases from `embedagent.tooling`.
- 影响：
  - bundled C/C++ workflow pack truth is only exposed through `embedagent.harness.packs`
  - active tool selection and runtime schema projection are unchanged
  - `embedagent.tooling.contracts` and `embedagent.tooling.result_budget` remain live
- 验证：
  - focused workflow/tooling tests
  - harness tests
  - fast non-slow/non-GUI tests
- 后续：
  - continue real Win7 smoke validation
  - continue real C/C++ project validation
  - continue deleting proven stale compatibility paths
```

- [ ] **Step 4: Search for stale live references**

Run:

```bash
rg -n "tooling\\.packs|Phase A-K|Phase K recovery state are complete|pack definitions now live under `src/embedagent/harness/packs.py`; `src/embedagent/tooling/packs.py`" README.md AGENTS.md docs
```

Expected: only archived historical docs may mention `tooling.packs`; live docs should describe Phase L as complete after implementation.

---

### Task 4: Archive Slice Docs

**Files:**
- Move: `docs/superpowers/specs/2026-06-14-phase-l-pack-compat-cleanup-design.md`
- Move: `docs/superpowers/plans/2026-06-14-phase-l-pack-compat-cleanup.md`
- Create directory: `docs/archive/phase-l-pack-compat-cleanup/`

- [ ] **Step 1: Move docs**

Move the design and plan into:

```text
docs/archive/phase-l-pack-compat-cleanup/
```

- [ ] **Step 2: Verify no active slice docs remain**

Run:

```bash
rg -n "phase-l-pack-compat-cleanup" docs/superpowers docs/archive/phase-l-pack-compat-cleanup
```

Expected: only archive paths should contain the Phase L design/plan after the move.

---

### Task 5: Final Verification And Commit

**Files:**
- All changed files

- [ ] **Step 1: Run focused tests**

```bash
uv run pytest tests/test_workflow_extensions.py::test_tooling_package_no_longer_reexports_c_workflow_packs tests/test_workflow_extensions.py::test_core_pack_no_longer_contains_harness_workflow_tools tests/test_workflow_extensions.py::test_harness_package_owns_c_workflow_packs tests/test_tooling_budget_v2.py -v
```

Expected: PASS.

- [ ] **Step 2: Run harness suite**

```bash
uv run pytest tests/ -m harness -v
```

Expected: PASS.

- [ ] **Step 3: Run fast suite**

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [ ] **Step 4: Run static checks**

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
git diff --check
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md docs src tests
git commit -m "refactor: remove tooling pack compatibility export"
```
