# Project-Local Python Extensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add manifest-gated project-local Python extension loading for `.embedagent/extensions/<name>/extension.json` and `extension.py` while preserving offline safety, diagnostics, and existing permission gates.

**Architecture:** Create a small project extension loader that validates manifests, builds a narrow API object, imports enabled workspace-bound `extension.py` files, and returns loaded extension objects plus load diagnostics. `InProcessAdapter` will assemble these project extensions into its shared `ExtensionManager` after bundled default extensions are built and project their state into session snapshots. Direct `QueryEngine` construction remains unchanged.

**Tech Stack:** Python 3.8 standard library (`json`, `os`, `re`, `importlib.util`), existing `ExtensionManager`, `ToolRuntime`, `InProcessAdapter`, pytest.

---

## File Structure

- Create `src/embedagent/project_extensions.py`
  - Manifest validation.
  - Workspace-bound path resolution.
  - Narrow `ProjectExtensionApi`.
  - Enabled-extension import and factory handling.
  - Diagnostics payload generation.

- Modify `src/embedagent/extensions.py`
  - Add a public diagnostic recording helper for loader-origin diagnostics.
  - Keep project extension hook failures isolated through existing `builtin_extension = False` behavior.

- Modify `src/embedagent/inprocess_adapter.py`
  - Load project extensions during hosted adapter initialization.
  - Register loaded extensions into the shared `ExtensionManager`.
  - Store project extension load state.
  - Project load state into each session's `workflow_state["extensions"]["project_extensions"]`.

- Add `tests/test_project_extensions.py`
  - Focused loader tests.
  - Adapter integration tests.

- Update docs after implementation:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`

---

## Task 1: Loader Manifest Discovery And Validation

**Files:**
- Create: `src/embedagent/project_extensions.py`
- Test: `tests/test_project_extensions.py`

- [x] **Step 1: Write failing tests for disabled and invalid manifests**

Add tests:

```python
def test_disabled_manifest_is_discovered_but_not_imported(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": false, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text("raise RuntimeError('should not import')", encoding="utf-8")

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["discovered"] == 1
    assert payload["counts"]["disabled"] == 1
    assert payload["counts"]["loaded"] == 0
    assert payload["extensions"][0]["status"] == "disabled"
    assert payload["loaded_extensions"] == []
    assert payload["diagnostics"] == []


def test_enabled_manifest_requires_permissions(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true}',
        encoding="utf-8",
    )

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["failed"] == 1
    assert payload["extensions"][0]["status"] == "failed"
    assert "permissions" in payload["diagnostics"][0]["error"]
```

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_project_extensions.py::test_disabled_manifest_is_discovered_but_not_imported tests/test_project_extensions.py::test_enabled_manifest_requires_permissions -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'embedagent.project_extensions'`.

- [x] **Step 3: Implement manifest-only loader**

Create `src/embedagent/project_extensions.py` with:

```python
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

DEFAULT_EXTENSION_RELPATH = os.path.join(".embedagent", "extensions")
_VALID_EXTENSION_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_ALLOWED_PERMISSIONS = set(["read", "workspace_write", "shell_exec", "toolchain_exec", "git_write"])


def load_project_extensions(workspace: str, extensions_path: Optional[str] = None) -> Dict[str, Any]:
    workspace_root = os.path.realpath(workspace)
    root = _resolve_inside(workspace_root, extensions_path or DEFAULT_EXTENSION_RELPATH)
    diagnostics = []
    entries = []
    loaded_extensions = []
    if not os.path.isdir(root):
        return _payload(workspace_root, entries, diagnostics, loaded_extensions)
    for extension_dir in _iter_extension_dirs(root):
        entry = _load_manifest_entry(workspace_root, extension_dir, diagnostics)
        entries.append(entry)
    return _payload(workspace_root, entries, diagnostics, loaded_extensions)
```

Include helpers for `_iter_extension_dirs`, `_load_manifest_entry`, `_validate_manifest`, `_resolve_inside`, `_display_path`, and `_payload`. For Task 1, enabled valid manifests may return status `failed` with `extension loading not implemented` until Task 2.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_project_extensions.py::test_disabled_manifest_is_discovered_but_not_imported tests/test_project_extensions.py::test_enabled_manifest_requires_permissions -v
```

Expected: PASS.

- [x] **Step 5: Commit Task 1**

```bash
git add src/embedagent/project_extensions.py tests/test_project_extensions.py
git commit -m "feat: discover project extension manifests"
```

## Task 2: Enabled Extension Import And Narrow API

**Files:**
- Modify: `src/embedagent/project_extensions.py`
- Test: `tests/test_project_extensions.py`

- [x] **Step 1: Write failing tests for enabled extension loading and API path guards**

Add tests:

```python
def test_enabled_extension_create_extension_receives_narrow_api(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "data.txt").write_text("hello", encoding="utf-8")
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    class SampleExtension(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "        def resources_discover(self, event, context):",
                "            assert api.read_text('.embedagent/extensions/sample/data.txt') == 'hello'",
                "            return api.ResourcesDiscoverResult(skill_paths=['.embedagent/skills'])",
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent.extensions import ExtensionManager
    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))
    manager = ExtensionManager(payload["loaded_extensions"])
    result = manager.discover_resources(str(tmp_path), reason="test")

    assert payload["counts"]["loaded"] == 1
    assert payload["extensions"][0]["status"] == "loaded"
    assert result.skill_paths == [".embedagent/skills"]


def test_project_extension_api_blocks_path_escape(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    try:",
                "        api.safe_join('..', '..', 'outside.txt')",
                "    except ValueError:",
                "        class SampleExtension(object):",
                "            extension_id = api.extension_id",
                "            builtin_extension = False",
                "        return SampleExtension()",
                "    raise RuntimeError('path escape allowed')",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["loaded"] == 1
    assert payload["diagnostics"] == []
```

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_project_extensions.py::test_enabled_extension_create_extension_receives_narrow_api tests/test_project_extensions.py::test_project_extension_api_blocks_path_escape -v
```

Expected: FAIL because enabled import is not implemented.

- [x] **Step 3: Implement import and API**

Update `project_extensions.py`:

- Add `ProjectExtensionApi` class.
- Import enabled entrypoints with `importlib.util.spec_from_file_location`.
- Prefer `create_extension(api)`.
- Fall back to module-level `EXTENSION`.
- Reject missing extension object.
- Set `extension_id`, `builtin_extension = False`, and `project_extension = True` when missing.
- Add loaded objects to `payload["loaded_extensions"]`.

Catch `OSError`, `ValueError`, `RuntimeError`, `TypeError`, and `ImportError` as diagnostics with status `failed`.

- [x] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_project_extensions.py -v
```

Expected: PASS.

- [x] **Step 5: Commit Task 2**

```bash
git add src/embedagent/project_extensions.py tests/test_project_extensions.py
git commit -m "feat: load enabled project extensions"
```

## Task 3: Adapter Integration And Snapshot State

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_project_extensions.py`

- [x] **Step 1: Write failing adapter integration test**

Add test:

```python
def test_inprocess_adapter_loads_enabled_project_extension_into_shared_manager(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    class SampleExtension(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "        def allowed_tool_names(self, mode_name, workflow_state='chat'):",
                "            return {'project_echo'} if mode_name == 'build' else set()",
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    snapshot = adapter.create_session(mode="build")

    assert adapter.project_extension_state["counts"]["loaded"] == 1
    assert "project_extensions" in snapshot["extensions"]
    assert snapshot["extensions"]["project_extensions"]["state"]["counts"]["loaded"] == 1
    assert "project_echo" in adapter.extension_manager.allowed_tool_names("build")
```

- [x] **Step 2: Run test to verify RED**

Run:

```bash
uv run pytest tests/test_project_extensions.py::test_inprocess_adapter_loads_enabled_project_extension_into_shared_manager -v
```

Expected: FAIL because `InProcessAdapter` does not load project extensions.

- [x] **Step 3: Wire loader into adapter**

In `src/embedagent/inprocess_adapter.py`:

- Import `load_project_extensions`.
- After `default_extensions = build_default_extension_set(self.tools)`, call the loader with `self.tools.workspace`.
- Register each item from `payload["loaded_extensions"]` into `self.extension_manager`.
- Store a sanitized `self.project_extension_state` without `loaded_extensions`.
- Store loader diagnostics in `self.project_extension_state`; Task 4 will mirror them into `ExtensionManager` diagnostics.
- Add helper `_project_extension_snapshot_state()`.
- In `create_session()` and `resume_session()`, ensure `session.workflow_state["extensions"]["project_extensions"]` is set before snapshot projection.

- [x] **Step 4: Run adapter test to verify GREEN**

Run:

```bash
uv run pytest tests/test_project_extensions.py::test_inprocess_adapter_loads_enabled_project_extension_into_shared_manager -v
```

Expected: PASS.

- [x] **Step 5: Commit Task 3**

```bash
git add src/embedagent/inprocess_adapter.py tests/test_project_extensions.py
git commit -m "feat: load project extensions in hosted adapter"
```

## Task 4: Diagnostics Mirroring And Dynamic Tool Flow

**Files:**
- Modify: `src/embedagent/extensions.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_project_extensions.py`

- [ ] **Step 1: Write failing tests for import diagnostics and dynamic tool registration**

Add tests:

```python
def test_project_extension_import_failure_appears_in_adapter_diagnostics(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "broken"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "broken_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text("raise RuntimeError('boom')", encoding="utf-8")

    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    snapshot = adapter.create_session(mode="build")

    assert adapter.project_extension_state["counts"]["failed"] == 1
    assert snapshot["extension_diagnostics"]
    assert snapshot["extension_diagnostics"][0]["extension_id"] == "broken_extension"
    assert "boom" in snapshot["extension_diagnostics"][0]["error"]


def test_project_extension_dynamic_tool_uses_existing_catalog_and_permission_flow(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "tools"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "project_tools", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "\n".join(
            [
                "def create_extension(api):",
                "    def handler(arguments):",
                "        return api.Observation('project_echo', True, None, {'echo': arguments.get('message', '')})",
                "    class ProjectTools(object):",
                "        extension_id = api.extension_id",
                "        builtin_extension = False",
                "        def register_tools(self, event, context):",
                "            tool = api.ToolDefinition(",
                "                name='project_echo',",
                "                description='Echo from project extension.',",
                "                parameters={'type': 'object', 'properties': {'message': {'type': 'string'}}},",
                "                handler=handler,",
                "                metadata={",
                "                    'permission_category': 'read',",
                "                    'mode_visibility': ['build'],",
                "                    'workflow_visibility': ['chat'],",
                "                    'user_label': 'Project Echo',",
                "                    'progress_renderer_key': 'default',",
                "                    'result_renderer_key': 'default',",
                "                    'supports_diff_preview': False,",
                "                    'context_reducer_key': 'project_echo',",
                "                    'read_only': True,",
                "                    'concurrency_safe': True,",
                "                    'interrupt_behavior': 'block',",
                "                    'result_budget_policy': 'compact-preview',",
                "                    'activity_kind': 'tool',",
                "                    'context_priority': 50,",
                "                },",
                "            )",
                "            return api.ToolRegistrationResult(tools=[tool], source_id=api.extension_id)",
                "        def allowed_tool_names(self, mode_name, workflow_state='chat'):",
                "            return {'project_echo'} if mode_name == 'build' else set()",
                "    return ProjectTools()",
            ]
        ),
        encoding="utf-8",
    )

    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    catalog = adapter.get_tool_catalog()
    result = adapter.tools.execute("project_echo", {"message": "hi"})

    entry = adapter.tools.tool_catalog_entry("project_echo")
    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "project_tools"
    assert any(item["name"] == "project_echo" for item in catalog)
    assert result.data["echo"] == "hi"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_project_extensions.py::test_project_extension_import_failure_appears_in_adapter_diagnostics tests/test_project_extensions.py::test_project_extension_dynamic_tool_uses_existing_catalog_and_permission_flow -v
```

Expected: at least one FAIL because diagnostics are not mirrored or dynamic tool flow is not fully registered.

- [ ] **Step 3: Add diagnostic helper and finish adapter mirroring**

In `src/embedagent/extensions.py` add:

```python
def record_diagnostic(self, extension_id, event, error, severity="error", source="project", metadata=None):
    self._diagnostics.append(ExtensionDiagnostic(...))
```

Use it from adapter loader integration for loader diagnostics.

Ensure `get_tool_catalog()` already calls `_ensure_extension_tools_registered(reason="catalog")`, so loaded project extension tools flow through existing dynamic registration.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_project_extensions.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py -v --basetemp .pytest-tmp-project-extensions-focused
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/embedagent/extensions.py src/embedagent/inprocess_adapter.py tests/test_project_extensions.py
git commit -m "feat: surface project extension diagnostics"
```

## Task 5: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/superpowers/plans/2026-06-05-project-local-python-extensions.md`

- [ ] **Step 1: Update source-of-truth docs**

Document:

- project-local Python extensions are available only through `.embedagent/extensions/<name>/extension.json`;
- `enabled` defaults to false;
- no dependency install or remote registry;
- loaded project extensions use `ExtensionManager`;
- dynamic tools remain metadata-classified and permission-gated;
- built-in tool replacement remains disallowed.

- [ ] **Step 2: Add design-change and tracker entries**

Add `DC-126` for Slice 4 and update `docs/development-tracker.md` latest self-extensible Agent Core status.

- [ ] **Step 3: Run focused verification**

Run:

```bash
$tmp = Join-Path (Get-Location) '.pytest-envtmp'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null; $env:TMP=$tmp; $env:TEMP=$tmp; uv run pytest tests/test_project_extensions.py tests/test_local_resources.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py tests/test_workflow_extensions.py tests/test_inprocess_adapter_frontend_api.py -v --basetemp .pytest-tmp-project-extensions-regression
```

Expected: PASS.

- [ ] **Step 4: Run fast suite**

Run:

```bash
$tmp = Join-Path (Get-Location) '.pytest-envtmp'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null; $env:TMP=$tmp; $env:TEMP=$tmp; uv run pytest tests/ -m "not slow and not gui" -v --basetemp .pytest-tmp-project-extensions-fast
```

Expected: PASS.

- [ ] **Step 5: Run focused ruff**

Run:

```bash
uv run ruff check src/embedagent/project_extensions.py src/embedagent/extensions.py src/embedagent/inprocess_adapter.py tests/test_project_extensions.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Clean temp directories and inspect final state**

Remove only workspace-local verification dirs:

```powershell
$paths = @('.pytest-envtmp', '.pytest-tmp-project-extensions-focused', '.pytest-tmp-project-extensions-regression', '.pytest-tmp-project-extensions-fast')
foreach ($path in $paths) {
  $resolved = Resolve-Path -LiteralPath $path -ErrorAction SilentlyContinue
  if ($resolved) {
    $full = $resolved.Path
    $root = (Resolve-Path -LiteralPath (Get-Location)).Path
    if ($full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $full -Recurse -Force
    } else {
      throw "Refusing to delete outside workspace: $full"
    }
  }
}
git status --short
```

- [ ] **Step 7: Commit docs and final plan state**

```bash
git add README.md AGENTS.md docs
git commit -m "docs: document project local python extensions"
```

If code and docs are already in one final staged set after verification, use one combined final commit with a clear message.
