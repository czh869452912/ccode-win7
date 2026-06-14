# Phase I Workflow Package Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only workflow package manifest control plane for the bundled C/C++ workflow package.

**Architecture:** Introduce a generic manifest model that validates and serializes package identity, tools, packs, modes, workflow states, and resource scopes. The bundled C/C++ workflow package exposes a manifest derived from existing harness-owned constants, and `CapabilityRegistry` projects that manifest as a non-executing `workflow_package` descriptor.

**Tech Stack:** Python 3.8 dataclasses, existing pytest suite, existing harness extension and capability registry modules.

---

## File Structure

- Create `src/embedagent/workflow_package_manifest.py`
  Owns generic dataclasses, validation, diagnostics, and JSON-serializable dictionaries for workflow package manifests.
- Create `src/embedagent/harness/package_manifest.py`
  Builds the bundled C/C++ workflow package manifest from `C_WORKFLOW_PACKS` and `C_WORKFLOW_TOOL_METADATA`.
- Modify `src/embedagent/capabilities.py`
  Adds `workflow_package` as a capability kind and adds `workflow_package_capability_descriptors(...)`.
- Modify `src/embedagent/harness/extension.py`
  Adds `package_manifest()` returning the bundled manifest dictionary.
- Modify `src/embedagent/inprocess_adapter.py`
  Includes bundled workflow package descriptors in `capability_snapshot()`.
- Add `tests/test_workflow_package_manifest.py`
  Tests the generic manifest model and bundled C/C++ manifest builder.
- Modify `tests/test_capability_registry.py`
  Tests workflow package capability projection and snapshot counts.
- Modify `tests/test_local_resources.py`
  Tests adapter capability snapshot includes the bundled workflow package descriptor.
- Modify `tests/test_workflow_extensions.py`
  Tests the harness extension exposes package manifest without changing activation.
- Update source-of-truth docs listed in `AGENTS.md`.

## Task 1: Generic Workflow Package Manifest Model

**Files:**
- Create: `src/embedagent/workflow_package_manifest.py`
- Test: `tests/test_workflow_package_manifest.py`

- [ ] **Step 1: Write failing generic manifest tests**

Add these tests to `tests/test_workflow_package_manifest.py`:

```python
import json

import pytest

from embedagent.workflow_package_manifest import (
    WorkflowPackageManifest,
    WorkflowPackageManifestError,
    WorkflowPackDeclaration,
    WorkflowToolDeclaration,
)


def test_workflow_package_manifest_serializes_stable_safe_payload():
    manifest = WorkflowPackageManifest(
        package_id=" embedagent.c_workflow ",
        label="C/C++ Workflow",
        version="1",
        source_type="builtin",
        source_id="embedagent.harness",
        supported_modes=["debug", "build", "build"],
        supported_workflow_states=["chat", "plan"],
        tools=[
            WorkflowToolDeclaration(
                name="run_recipe",
                permission_category="toolchain_exec",
                source_type="harness",
                source_id="embedagent.harness",
                metadata={"activity_kind": "diagnostic"},
            )
        ],
        packs=[
            WorkflowPackDeclaration(
                name="build_lite",
                tool_names=["read_file", "run_recipe", "read_file"],
            )
        ],
        resource_scopes=[".embedagent/recipes", ".embedagent/recipes"],
    )

    payload = manifest.to_dict()

    assert payload["package_id"] == "embedagent.c_workflow"
    assert payload["label"] == "C/C++ Workflow"
    assert payload["supported_modes"] == ["build", "debug"]
    assert payload["supported_workflow_states"] == ["chat", "plan"]
    assert payload["tools"][0]["name"] == "run_recipe"
    assert payload["tools"][0]["metadata"]["activity_kind"] == "diagnostic"
    assert payload["packs"][0]["tool_names"] == ["read_file", "run_recipe"]
    assert payload["resource_scopes"] == [".embedagent/recipes"]
    assert payload["diagnostics"] == []
    json.dumps(payload, sort_keys=True)


def test_workflow_package_manifest_rejects_missing_identity():
    with pytest.raises(WorkflowPackageManifestError):
        WorkflowPackageManifest(package_id="", label="Missing")
```

- [ ] **Step 2: Run generic manifest tests and confirm they fail**

Run:

```bash
uv run pytest tests/test_workflow_package_manifest.py -v
```

Expected: fails because `embedagent.workflow_package_manifest` does not exist.

- [ ] **Step 3: Implement generic manifest model**

Create `src/embedagent/workflow_package_manifest.py` with:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class WorkflowPackageManifestError(ValueError):
    pass


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _stable_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        text = _clean_text(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return sorted(result)


def _stable_ordered_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        text = _clean_text(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _copy_dict(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


@dataclass
class WorkflowToolDeclaration(object):
    name: str
    permission_category: str = "other"
    source_type: str = "workflow_package"
    source_id: str = "workflow_package"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name)
        self.permission_category = _clean_text(self.permission_category) or "other"
        self.source_type = _clean_text(self.source_type) or "workflow_package"
        self.source_id = _clean_text(self.source_id) or self.source_type
        self.metadata = _copy_dict(self.metadata)
        if not self.name:
            raise WorkflowPackageManifestError("workflow tool declaration requires name")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "permission_category": self.permission_category,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "metadata": _copy_dict(self.metadata),
        }


@dataclass
class WorkflowPackDeclaration(object):
    name: str
    tool_names: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name)
        self.tool_names = _stable_ordered_list(self.tool_names)
        if not self.name:
            raise WorkflowPackageManifestError("workflow pack declaration requires name")

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "tool_names": list(self.tool_names)}


@dataclass
class WorkflowPackageManifest(object):
    package_id: str
    label: str
    version: str = "1"
    source_type: str = "builtin"
    source_id: str = "workflow_package"
    supported_modes: List[str] = field(default_factory=list)
    supported_workflow_states: List[str] = field(default_factory=list)
    tools: List[WorkflowToolDeclaration] = field(default_factory=list)
    packs: List[WorkflowPackDeclaration] = field(default_factory=list)
    resource_scopes: List[str] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.package_id = _clean_text(self.package_id)
        self.label = _clean_text(self.label)
        self.version = _clean_text(self.version) or "1"
        self.source_type = _clean_text(self.source_type) or "builtin"
        self.source_id = _clean_text(self.source_id) or self.package_id
        self.supported_modes = _stable_list(self.supported_modes)
        self.supported_workflow_states = _stable_list(self.supported_workflow_states)
        self.tools = list(self.tools or [])
        self.packs = list(self.packs or [])
        self.resource_scopes = _stable_list(self.resource_scopes)
        self.diagnostics = [
            dict(item) for item in list(self.diagnostics or []) if isinstance(item, dict)
        ]
        if not self.package_id:
            raise WorkflowPackageManifestError("workflow package manifest requires package_id")
        if not self.label:
            raise WorkflowPackageManifestError("workflow package manifest requires label")

    def to_dict(self) -> Dict[str, Any]:
        tools = sorted([item.to_dict() for item in self.tools], key=lambda item: item["name"])
        packs = sorted([item.to_dict() for item in self.packs], key=lambda item: item["name"])
        return {
            "package_id": self.package_id,
            "label": self.label,
            "version": self.version,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "supported_modes": list(self.supported_modes),
            "supported_workflow_states": list(self.supported_workflow_states),
            "tools": tools,
            "packs": packs,
            "resource_scopes": list(self.resource_scopes),
            "diagnostics": [dict(item) for item in self.diagnostics],
        }
```

- [ ] **Step 4: Run generic manifest tests and confirm they pass**

Run:

```bash
uv run pytest tests/test_workflow_package_manifest.py -v
```

Expected: pass.

## Task 2: Bundled C/C++ Workflow Manifest

**Files:**
- Create: `src/embedagent/harness/package_manifest.py`
- Modify: `tests/test_workflow_package_manifest.py`
- Modify: `src/embedagent/harness/extension.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write failing bundled manifest tests**

Append to `tests/test_workflow_package_manifest.py`:

```python
def test_c_workflow_manifest_projects_package_packs_tools_and_resources():
    from embedagent.harness.package_manifest import build_c_workflow_package_manifest

    manifest = build_c_workflow_package_manifest()
    payload = manifest.to_dict()

    assert payload["package_id"] == "embedagent.c_workflow"
    assert payload["source_type"] == "builtin"
    assert payload["source_id"] == "embedagent.harness"
    assert payload["supported_modes"] == ["build", "debug", "verify"]
    assert "chat" in payload["supported_workflow_states"]
    assert ".embedagent/recipes" in payload["resource_scopes"]

    pack_names = [item["name"] for item in payload["packs"]]
    assert "build_lite" in pack_names
    assert "debug_lite" in pack_names
    assert "verify" in pack_names

    tools = dict((item["name"], item) for item in payload["tools"])
    assert tools["run_recipe"]["permission_category"] == "toolchain_exec"
    assert tools["task_status"]["permission_category"] == "read"
    assert tools["report_quality_v2"]["metadata"]["mode_visibility"] == ["verify"]


def test_c_harness_extension_exposes_read_only_package_manifest():
    from embedagent.harness.extension import CHarnessWorkflowExtension

    manifest = CHarnessWorkflowExtension().package_manifest()

    assert manifest["package_id"] == "embedagent.c_workflow"
    assert any(item["name"] == "verify" for item in manifest["packs"])
    assert any(item["name"] == "run_recipe" for item in manifest["tools"])
```

- [ ] **Step 2: Run bundled manifest tests and confirm they fail**

Run:

```bash
uv run pytest tests/test_workflow_package_manifest.py -v
```

Expected: first new test fails because `embedagent.harness.package_manifest` does not exist.

- [ ] **Step 3: Implement bundled C/C++ manifest builder**

Create `src/embedagent/harness/package_manifest.py` with:

```python
from __future__ import annotations

from typing import Any, Dict, List

from embedagent.harness.packs import C_WORKFLOW_PACKS
from embedagent.harness.tool_metadata import C_WORKFLOW_TOOL_METADATA
from embedagent.workflow_package_manifest import (
    WorkflowPackageManifest,
    WorkflowPackDeclaration,
    WorkflowToolDeclaration,
)

C_WORKFLOW_PACKAGE_ID = "embedagent.c_workflow"
C_WORKFLOW_PACKAGE_LABEL = "C/C++ Workflow"
C_WORKFLOW_PACKAGE_SOURCE_ID = "embedagent.harness"
C_WORKFLOW_SUPPORTED_MODES = ["build", "debug", "verify"]
C_WORKFLOW_SUPPORTED_STATES = ["chat", "plan", "review", "command"]
C_WORKFLOW_RESOURCE_SCOPES = [".embedagent/recipes"]


def _tool_declarations() -> List[WorkflowToolDeclaration]:
    declarations = []
    for name, metadata in sorted(C_WORKFLOW_TOOL_METADATA.items()):
        safe_metadata = dict(metadata or {})
        declarations.append(
            WorkflowToolDeclaration(
                name=name,
                permission_category=str(safe_metadata.get("permission_category") or "other"),
                source_type="harness",
                source_id=C_WORKFLOW_PACKAGE_SOURCE_ID,
                metadata=safe_metadata,
            )
        )
    return declarations


def _pack_declarations() -> List[WorkflowPackDeclaration]:
    return [
        WorkflowPackDeclaration(name=name, tool_names=list(tool_names or []))
        for name, tool_names in sorted(C_WORKFLOW_PACKS.items())
    ]


def build_c_workflow_package_manifest() -> WorkflowPackageManifest:
    return WorkflowPackageManifest(
        package_id=C_WORKFLOW_PACKAGE_ID,
        label=C_WORKFLOW_PACKAGE_LABEL,
        version="1",
        source_type="builtin",
        source_id=C_WORKFLOW_PACKAGE_SOURCE_ID,
        supported_modes=list(C_WORKFLOW_SUPPORTED_MODES),
        supported_workflow_states=list(C_WORKFLOW_SUPPORTED_STATES),
        tools=_tool_declarations(),
        packs=_pack_declarations(),
        resource_scopes=list(C_WORKFLOW_RESOURCE_SCOPES),
    )


def c_workflow_package_manifest_dict() -> Dict[str, Any]:
    return build_c_workflow_package_manifest().to_dict()
```

- [ ] **Step 4: Add harness extension manifest method**

Modify `src/embedagent/harness/extension.py` imports:

```python
from embedagent.harness.package_manifest import c_workflow_package_manifest_dict
```

Add this method to `CHarnessWorkflowExtension`:

```python
    def package_manifest(self) -> dict:
        return c_workflow_package_manifest_dict()
```

- [ ] **Step 5: Run bundled manifest tests and confirm they pass**

Run:

```bash
uv run pytest tests/test_workflow_package_manifest.py -v
```

Expected: pass.

## Task 3: Capability Registry Projection

**Files:**
- Modify: `src/embedagent/capabilities.py`
- Modify: `tests/test_capability_registry.py`

- [ ] **Step 1: Write failing capability registry tests**

Modify `tests/test_capability_registry.py` imports to include:

```python
    workflow_package_capability_descriptors,
```

Update `test_registry_registers_descriptors_and_serializes_snapshot()` expected counts:

```python
    assert payload["counts"] == {
        "command": 1,
        "model_profile": 0,
        "resource": 0,
        "tool": 1,
        "workflow_package": 0,
    }
```

Append:

```python
def test_workflow_package_capability_descriptors_project_manifest():
    from embedagent.harness.package_manifest import build_c_workflow_package_manifest

    descriptors = workflow_package_capability_descriptors(
        [build_c_workflow_package_manifest()]
    )
    registry = CapabilityRegistry(descriptors)
    payload = registry.snapshot().to_dict()

    assert payload["counts"]["workflow_package"] == 1
    item = payload["descriptors"][0]
    assert item["kind"] == "workflow_package"
    assert item["name"] == "embedagent.c_workflow"
    assert item["source_type"] == "builtin"
    assert item["source_id"] == "embedagent.harness"
    assert item["active"] is True
    assert item["metadata"]["label"] == "C/C++ Workflow"
    assert "packs" in item["metadata"]
    assert "tools" in item["metadata"]
    json.dumps(payload, sort_keys=True)
```

- [ ] **Step 2: Run capability registry tests and confirm they fail**

Run:

```bash
uv run pytest tests/test_capability_registry.py -v
```

Expected: fails because `workflow_package_capability_descriptors` does not exist and counts lack `workflow_package`.

- [ ] **Step 3: Implement workflow package capability projection**

Modify `src/embedagent/capabilities.py`:

```python
CAPABILITY_KINDS = ("command", "model_profile", "resource", "tool", "workflow_package")
```

Add:

```python
def workflow_package_capability_descriptors(manifests: Any) -> List[CapabilityDescriptor]:
    descriptors = []
    for manifest in list(manifests or []):
        if hasattr(manifest, "to_dict"):
            payload = manifest.to_dict()
        elif isinstance(manifest, dict):
            payload = dict(manifest)
        else:
            continue
        name = _clean_text(payload.get("package_id"))
        if not name:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=name,
                kind="workflow_package",
                source_type=_clean_text(payload.get("source_type"), "workflow_package"),
                source_id=_clean_text(payload.get("source_id"), name),
                metadata=payload,
                active=True,
            )
        )
    return sorted(descriptors, key=lambda item: item.key())
```

- [ ] **Step 4: Run capability registry tests and confirm they pass**

Run:

```bash
uv run pytest tests/test_capability_registry.py -v
```

Expected: pass.

## Task 4: Adapter Capability Snapshot Includes Package Manifest

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_local_resources.py`

- [ ] **Step 1: Write failing adapter capability test**

In `tests/test_local_resources.py`, extend `test_adapter_capability_snapshot_combines_tools_resources_commands_and_model()` with:

```python
        package_items = [
            item
            for item in snapshot["descriptors"]
            if item["kind"] == "workflow_package"
        ]

        self.assertEqual(len(package_items), 1)
        self.assertEqual(package_items[0]["name"], "embedagent.c_workflow")
        self.assertEqual(package_items[0]["metadata"]["label"], "C/C++ Workflow")
        self.assertIn("build_lite", [item["name"] for item in package_items[0]["metadata"]["packs"]])
```

Also update any expected count assertions in this test to include `workflow_package`.

- [ ] **Step 2: Run local resource capability test and confirm it fails**

Run:

```bash
uv run pytest tests/test_local_resources.py::TestLocalResources::test_adapter_capability_snapshot_combines_tools_resources_commands_and_model -v
```

Expected: fails because adapter does not include workflow package descriptors.

- [ ] **Step 3: Project bundled package manifest in adapter capability snapshot**

Modify `src/embedagent/inprocess_adapter.py` imports:

```python
    workflow_package_capability_descriptors,
```

Add:

```python
from embedagent.harness.package_manifest import build_c_workflow_package_manifest
```

Then in `capability_snapshot()` before model profile registration:

```python
        registry.extend(
            workflow_package_capability_descriptors([build_c_workflow_package_manifest()])
        )
```

- [ ] **Step 4: Run local resource capability test and confirm it passes**

Run:

```bash
uv run pytest tests/test_local_resources.py::TestLocalResources::test_adapter_capability_snapshot_combines_tools_resources_commands_and_model -v
```

Expected: pass.

## Task 5: Verify Activation Semantics Did Not Change

**Files:**
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Add no-behavior-change assertions**

Append to `tests/test_workflow_extensions.py`:

```python
def test_c_harness_package_manifest_does_not_drive_active_tools():
    from embedagent.harness.extension import CHarnessWorkflowExtension

    extension = CHarnessWorkflowExtension()
    manifest = extension.package_manifest()

    assert manifest["package_id"] == "embedagent.c_workflow"
    assert "read_file" in [
        name
        for pack in manifest["packs"]
        if pack["name"] == "core"
        for name in pack["tool_names"]
    ]
    assert extension.allowed_tool_names("explore") == set()
    assert "run_recipe" in extension.allowed_tool_names("build")
```

- [ ] **Step 2: Run workflow extension focused tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_c_harness_package_manifest_does_not_drive_active_tools tests/test_workflow_extensions.py::test_c_harness_extension_active_tools_are_pack_only_for_verify tests/test_workflow_extensions.py::test_c_harness_extension_is_inactive_for_non_harness_modes -v
```

Expected: pass.

## Task 6: Source-Of-Truth Docs And Archive

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/mode-schema.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Move: `docs/superpowers/specs/2026-06-14-phase-i-workflow-package-manifest-design.md` to `docs/archive/phase-i-workflow-package-manifest/`
- Move: `docs/superpowers/plans/2026-06-14-phase-i-workflow-package-manifest.md` to `docs/archive/phase-i-workflow-package-manifest/`

- [ ] **Step 1: Update active docs**

Document:

- Phase I workflow package manifest/read-model is complete.
- `WorkflowPackageManifest` is an internal read model, not a public extension API.
- The bundled C/C++ package manifest is derived from existing package-owned constants.
- `CapabilityRegistry` now includes `workflow_package` descriptors.
- Manifest projection is diagnostic/read-model state and does not activate tools or grant permissions.
- Next candidate remains structured compaction state or a future manifest-driven activation slice.

- [ ] **Step 2: Add design change log entry**

Add a new `DC-143` entry in `docs/design-change-log.md` with:

- subject: `Pi-inspired minimal Core Phase I workflow package manifest 收口`
- summary of new manifest model, bundled C/C++ manifest builder, capability projection, and unchanged activation semantics
- affected source files and tests
- no ADR required
- next actions: structured compaction state, possible manifest-driven activation after more validation

- [ ] **Step 3: Archive slice materials**

Run:

```powershell
$root = (Resolve-Path .).Path
$archive = Join-Path $root 'docs\archive\phase-i-workflow-package-manifest'
New-Item -ItemType Directory -Force -Path $archive | Out-Null
Move-Item -LiteralPath (Join-Path $root 'docs\superpowers\specs\2026-06-14-phase-i-workflow-package-manifest-design.md') -Destination $archive
Move-Item -LiteralPath (Join-Path $root 'docs\superpowers\plans\2026-06-14-phase-i-workflow-package-manifest.md') -Destination $archive
```

- [ ] **Step 4: Check docs for stale status**

Run:

```bash
rg -n "Phase I|workflow package manifest|control-plane manifests|next candidate" README.md AGENTS.md docs
```

Expected: active docs say Phase I is complete after implementation, and no active doc says workflow package manifest is still the next candidate.

## Task 7: Verification And Commit

**Files:**
- All Phase I files

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_workflow_package_manifest.py tests/test_capability_registry.py tests/test_local_resources.py::TestLocalResources::test_adapter_capability_snapshot_combines_tools_resources_commands_and_model tests/test_workflow_extensions.py::test_c_harness_package_manifest_does_not_drive_active_tools -v
```

Expected: pass.

- [ ] **Step 2: Run harness tests**

Run:

```bash
uv run pytest tests/ -m harness -v
```

Expected: pass.

- [ ] **Step 3: Run fast suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: pass.

- [ ] **Step 4: Run lint and format checks**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
git diff --check
```

Expected: all pass.

- [ ] **Step 5: Inspect git status**

Run:

```bash
git status --short --branch
git diff --stat
```

Expected: only Phase I files changed.

- [ ] **Step 6: Commit**

Run:

```bash
git add README.md AGENTS.md docs src tests
git commit -m "feat: add workflow package manifest"
```

Expected: commit succeeds on `codex/phase-i-workflow-manifest`.

## Self-Review

- Spec coverage: the plan covers generic manifest model, bundled C/C++ manifest, capability projection, adapter exposure, unchanged activation semantics, docs, archive, and verification.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: `WorkflowPackageManifest`, `WorkflowToolDeclaration`, `WorkflowPackDeclaration`, `WorkflowPackageManifestError`, and `workflow_package_capability_descriptors` names are consistent across tasks.
