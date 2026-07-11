# Deterministic Agent Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile trusted component registrations and product definitions into reproducible base-Agent and C/C++-Agent exports with auditable lock records and complete offline asset closure.

**Architecture:** Keep manifests non-executing, register factories explicitly in the product composition root, freeze the catalog before compilation, and emit canonical JSON. Support only two fixed exporters in this milestone: a base wheel set and the existing Win7 portable bundle specialized by a compiled C/C++ definition.

**Tech Stack:** Python 3.8 dataclasses, JSON canonical serialization, hashlib, pathlib/shutil/zipfile, existing uv-built wheels and offline runtime contract, pytest.

---

## File Structure

```text
packages/embedagent-composition/src/embedagent_composition/
  models.py              immutable manifests, refs, definitions, diagnostics
  catalog.py             explicit registration and one-way freeze
  compiler.py            dependency/conflict/order/capability validation
  lockfile.py             canonical safe lock and hashes
  exporters.py            wheel-set and portable-bundle export coordination
  cli.py                  validate, compile, and export commands
  __main__.py
src/embedagent/product_catalog.py
                         trusted built-in component factory registration
products/base-agent.json
products/cpp-agent.json
scripts/smoke-exported-agent.py
tests/test_component_catalog.py
tests/test_agent_compiler.py
tests/test_agent_lockfile.py
tests/test_agent_exporters.py
```

### Task 1: Define Non-Executing Composition Models

**Files:**
- Create: `packages/embedagent-composition/src/embedagent_composition/models.py`
- Create: `tests/test_component_catalog.py`

- [ ] **Step 1: Write manifest and definition validation tests**

Create `tests/test_component_catalog.py`:

```python
import pytest

from embedagent_composition.models import (
    AgentProductDefinition,
    ComponentManifest,
    ComponentRef,
    CompositionError,
)


def test_manifest_requires_stable_component_id():
    with pytest.raises(CompositionError, match="invalid component id"):
        ComponentManifest(component_id="Bad Id", kind="workflow", version="1.0.0", api_version="1")


def test_manifest_rejects_executable_builder_metadata():
    with pytest.raises(CompositionError, match="executable metadata is forbidden"):
        ComponentManifest(
            component_id="tests.workflow",
            kind="workflow",
            version="1.0.0",
            api_version="1",
            metadata={"builder_path": "some.module:build"},
        )


def test_definition_keeps_component_ids_only():
    definition = AgentProductDefinition(
        agent_id="tests.agent",
        version="1.0.0",
        profile=ComponentRef("tests.profile"),
        providers=(ComponentRef("tests.provider"),),
    )
    assert definition.profile.component_id == "tests.profile"
    assert definition.providers[0].component_id == "tests.provider"
```

- [ ] **Step 2: Run the tests and verify they fail**

```bash
uv run pytest tests/test_component_catalog.py -v
```

Expected: FAIL because composition models do not exist.

- [ ] **Step 3: Implement immutable models**

Create `models.py` with:

```python
COMPONENT_KINDS = frozenset(("profile", "provider", "workflow", "tool", "resource", "host", "gui"))
FORBIDDEN_METADATA_KEYS = frozenset(("builder_path", "factory", "import_path", "api_key", "token", "secret"))


class CompositionError(ValueError):
    pass


@dataclass(frozen=True)
class ComponentManifest:
    component_id: str
    kind: str
    version: str
    api_version: str
    requires: Tuple[str, ...] = field(default_factory=tuple)
    conflicts: Tuple[str, ...] = field(default_factory=tuple)
    permission_categories: Tuple[str, ...] = field(default_factory=tuple)
    runtime_assets: Tuple[str, ...] = field(default_factory=tuple)
    resource_scopes: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentRef:
    component_id: str
    config: Mapping[str, Any] = field(default_factory=dict)
    order: int = 0


@dataclass(frozen=True)
class AgentProductDefinition:
    agent_id: str
    version: str
    profile: ComponentRef
    providers: Tuple[ComponentRef, ...]
    workflows: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    tools: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    resources: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    host: Optional[ComponentRef] = None
    gui: Optional[ComponentRef] = None
```

In `__post_init__`, normalize only immutable copies and validate IDs against
`^[a-z0-9][a-z0-9._-]*$`. Reject forbidden metadata/config keys recursively.

- [ ] **Step 4: Add JSON parsing helpers**

Implement `AgentProductDefinition.from_dict()` and `to_dict()` with explicit
known fields. Reject unknown top-level fields instead of silently retaining
them.

- [ ] **Step 5: Run model tests**

```bash
uv run pytest tests/test_component_catalog.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit composition models**

```bash
git add packages/embedagent-composition/src/embedagent_composition/models.py tests/test_component_catalog.py
git commit -m "feat: define agent composition models"
```

### Task 2: Implement Explicit Registration And Catalog Freeze

**Files:**
- Create: `packages/embedagent-composition/src/embedagent_composition/catalog.py`
- Modify: `tests/test_component_catalog.py`

- [ ] **Step 1: Add duplicate, mutation, and trust tests**

Append:

```python
def test_catalog_rejects_duplicate_component_id(component):
    catalog = ComponentCatalog()
    catalog.register(component)
    with pytest.raises(CompositionError, match="duplicate component"):
        catalog.register(component)


def test_frozen_catalog_rejects_registration(component):
    catalog = ComponentCatalog()
    catalog.register(component)
    frozen = catalog.freeze()
    with pytest.raises(CompositionError, match="catalog is frozen"):
        catalog.register(component)
    assert frozen.require(component.manifest.component_id) is component


def test_catalog_does_not_discover_entry_points():
    assert not hasattr(ComponentCatalog, "discover")
    assert not hasattr(ComponentCatalog, "install")
```

- [ ] **Step 2: Implement the catalog**

Define `ComponentFactory` as a protocol with a manifest property and
`contribute(context, config)` method. `ComponentCatalog.register()` accepts a
factory object directly, validates the manifest, and stores it by component id.

`freeze()` returns `FrozenComponentCatalog` containing an immutable, sorted
mapping. The frozen catalog exposes only `require()`, `manifests()`, and
`component_ids()`.

- [ ] **Step 3: Run catalog tests**

```bash
uv run pytest tests/test_component_catalog.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit catalog freeze**

```bash
git add packages/embedagent-composition/src/embedagent_composition/catalog.py tests/test_component_catalog.py
git commit -m "feat: add frozen component catalog"
```

### Task 3: Compile And Validate The Component Graph

**Files:**
- Create: `packages/embedagent-composition/src/embedagent_composition/compiler.py`
- Create: `tests/test_agent_compiler.py`

- [ ] **Step 1: Write dependency, conflict, and ordering tests**

Create `tests/test_agent_compiler.py` with small in-memory factories and these
complete cases:

```python
import pytest

from embedagent_composition.catalog import ComponentCatalog
from embedagent_composition.compiler import compile_agent
from embedagent_composition.models import (
    AgentProductDefinition,
    ComponentManifest,
    ComponentRef,
    CompositionError,
)


class Factory:
    def __init__(self, component_id, kind, **values):
        self.manifest = ComponentManifest(
            component_id=component_id,
            kind=kind,
            version="1.0.0",
            api_version="1",
            **values
        )

    def contribute(self, context, config):
        return {"component_id": self.manifest.component_id, "config": dict(config)}


def compile_with(selected, available):
    profile = Factory("tests.profile", "profile")
    provider = Factory("tests.provider", "provider")
    catalog = ComponentCatalog()
    for factory in (profile, provider) + tuple(available):
        catalog.register(factory)
    workflows = tuple(
        ComponentRef(factory.manifest.component_id)
        for factory in selected
        if factory.manifest.kind == "workflow"
    )
    tools = tuple(
        ComponentRef(factory.manifest.component_id)
        for factory in selected
        if factory.manifest.kind == "tool"
    )
    definition = AgentProductDefinition(
        agent_id="tests.agent",
        version="1.0.0",
        profile=ComponentRef(profile.manifest.component_id),
        providers=(ComponentRef(provider.manifest.component_id),),
        workflows=workflows,
        tools=tools,
    )
    return compile_agent(definition, catalog.freeze())


def test_compile_rejects_missing_required_component():
    workflow = Factory("tests.workflow", "workflow", requires=("tests.missing",))
    with pytest.raises(CompositionError, match="missing required component tests.missing"):
        compile_with((workflow,), (workflow,))


def test_compile_rejects_dependency_cycle():
    first = Factory("tests.first", "workflow", requires=("tests.second",))
    second = Factory("tests.second", "workflow", requires=("tests.first",))
    with pytest.raises(CompositionError, match="dependency cycle"):
        compile_with((first,), (first, second))


def test_compile_rejects_declared_conflict():
    first = Factory("tests.first", "workflow", conflicts=("tests.second",))
    second = Factory("tests.second", "workflow")
    with pytest.raises(CompositionError, match="conflict"):
        compile_with((first, second), (first, second))


def test_compile_rejects_duplicate_tool_name():
    first = Factory("tests.first", "tool", metadata={"tool_name": "same"})
    second = Factory("tests.second", "tool", metadata={"tool_name": "same"})
    with pytest.raises(CompositionError, match="duplicate tool name same"):
        compile_with((first, second), (first, second))


def test_compile_rejects_workflow_namespace_collision():
    first = Factory("tests.first", "workflow", metadata={"workflow_namespace": "same"})
    second = Factory("tests.second", "workflow", metadata={"workflow_namespace": "same"})
    with pytest.raises(CompositionError, match="workflow namespace same"):
        compile_with((first, second), (first, second))


def test_compile_orders_dependencies_before_dependents():
    dependent = Factory("tests.dependent", "workflow", requires=("tests.required",))
    required = Factory("tests.required", "resource")
    result = compile_with((dependent,), (dependent, required))
    assert result.spec.component_ids.index("tests.required") < result.spec.component_ids.index("tests.dependent")


def test_compile_does_not_treat_permissions_as_grants():
    tool = Factory("tests.network", "tool", permission_categories=("network",))
    result = compile_with((tool,), (tool,))
    assert result.spec.permission_requirements == ("network",)
    assert not hasattr(result.spec, "granted_permissions")
```

- [ ] **Step 2: Run compiler tests and verify they fail**

```bash
uv run pytest tests/test_agent_compiler.py -v
```

Expected: FAIL because compiler types do not exist.

- [ ] **Step 3: Implement CompiledAgentSpec**

Define a frozen result containing:

```python
@dataclass(frozen=True)
class CompiledAgentSpec:
    definition: AgentProductDefinition
    component_ids: Tuple[str, ...]
    manifests: Tuple[ComponentManifest, ...]
    permission_requirements: Tuple[str, ...]
    runtime_assets: Tuple[str, ...]
    diagnostics: Tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class CompiledContributions:
    values: Tuple[Tuple[str, Any], ...]


@dataclass(frozen=True)
class CompilationResult:
    spec: CompiledAgentSpec
    contributions: CompiledContributions
```

`CompiledAgentSpec` contains no secrets and no live factory objects.
`CompiledContributions` is build-process-only and is never serialized into the
lock or export. `compile_agent()` always returns `CompilationResult`, so lock
and export callers consume `result.spec` explicitly.

- [ ] **Step 4: Implement deterministic graph compilation**

`compile_agent()` must:

1. collect all direct refs;
2. close `requires` transitively;
3. detect missing ids and cycles;
4. reject conflicts;
5. validate one profile and at least one provider;
6. reject duplicate tool names and primary workflow namespaces using manifest
   metadata;
7. topologically sort with component id as the tie breaker;
8. union permissions and assets without granting or activating them;
9. invoke the selected trusted factories only after graph validation;
10. return `CompilationResult(spec, contributions)`.

- [ ] **Step 5: Run compiler tests**

```bash
uv run pytest tests/test_agent_compiler.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit compiler**

```bash
git add packages/embedagent-composition/src/embedagent_composition/compiler.py tests/test_agent_compiler.py
git commit -m "feat: compile deterministic agent components"
```

### Task 4: Generate A Canonical Safe Lock Record

**Files:**
- Create: `packages/embedagent-composition/src/embedagent_composition/lockfile.py`
- Create: `tests/test_agent_lockfile.py`

- [ ] **Step 1: Write determinism and secret-exclusion tests**

Create `tests/test_agent_lockfile.py`:

```python
import hashlib

import pytest

from embedagent_composition.compiler import CompiledAgentSpec
from embedagent_composition.lockfile import (
    build_lock_payload,
    canonical_json_bytes,
    reject_secret_fields,
)
from embedagent_composition.models import (
    AgentProductDefinition,
    ComponentManifest,
    ComponentRef,
    CompositionError,
)


def sample_spec():
    manifests = (
        ComponentManifest("tests.profile", "profile", "1.0.0", "1"),
        ComponentManifest("tests.provider", "provider", "1.0.0", "1"),
    )
    definition = AgentProductDefinition(
        agent_id="tests.agent",
        version="1.0.0",
        profile=ComponentRef("tests.profile"),
        providers=(ComponentRef("tests.provider"),),
    )
    return CompiledAgentSpec(
        definition=definition,
        component_ids=("tests.profile", "tests.provider"),
        manifests=manifests,
        permission_requirements=(),
        runtime_assets=(),
        diagnostics=(),
    )


def lock_bytes(spec, root, component_files):
    payload = build_lock_payload(spec, source_root=root, component_files=component_files)
    return canonical_json_bytes(payload)


def test_identical_specs_produce_identical_lock_bytes(tmp_path):
    source = tmp_path / "component.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    files = {"tests.profile": (source,), "tests.provider": ()}
    assert lock_bytes(sample_spec(), tmp_path, files) == lock_bytes(sample_spec(), tmp_path, files)


def test_component_file_mapping_order_does_not_change_lock_bytes(tmp_path):
    spec = sample_spec()
    first = {"tests.profile": (), "tests.provider": ()}
    second = {"tests.provider": (), "tests.profile": ()}
    assert lock_bytes(spec, tmp_path, first) == lock_bytes(spec, tmp_path, second)


def test_lock_contains_sha256_for_every_component_file(tmp_path):
    source = tmp_path / "component.py"
    source.write_bytes(b"VALUE = 1\n")
    payload = build_lock_payload(
        sample_spec(),
        source_root=tmp_path,
        component_files={"tests.profile": (source,), "tests.provider": ()},
    )
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert payload["components"][0]["files"] == [
        {"path": "component.py", "sha256": expected}
    ]


def test_lock_rejects_secret_shaped_fields():
    with pytest.raises(CompositionError, match="secret-shaped field"):
        reject_secret_fields({"nested": {"api_key": "not-allowed"}})


def test_lock_uses_lf_and_trailing_newline(tmp_path):
    value = lock_bytes(
        sample_spec(),
        tmp_path,
        {"tests.profile": (), "tests.provider": ()},
    )
    assert value.endswith(b"\n")
    assert b"\r\n" not in value
```

- [ ] **Step 2: Implement canonical JSON serialization**

Use:

```python
def canonical_json_bytes(payload):
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return (text + "\n").encode("ascii")
```

The lock schema contains `schemaVersion`, agent id/version, ordered component
records, relative file paths with SHA-256 hashes, permission requirements,
runtime asset ids, and compiler version. Reject keys matching
`api_key|token|secret|password|credential` case-insensitively.

- [ ] **Step 3: Implement atomic lock writing**

Write to a sibling temporary file, `flush()`, `os.fsync()`, then `os.replace()`.
Never leave a partially written lock at the destination.

- [ ] **Step 4: Run lock tests**

```bash
uv run pytest tests/test_agent_lockfile.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit lock generation**

```bash
git add packages/embedagent-composition/src/embedagent_composition/lockfile.py tests/test_agent_lockfile.py
git commit -m "feat: generate deterministic agent lock"
```

### Task 5: Register Built-In Product Components

**Files:**
- Modify: `src/embedagent/product_catalog.py`
- Create: `products/base-agent.json`
- Create: `products/cpp-agent.json`
- Create: `tests/test_product_catalog.py`

- [ ] **Step 1: Write product catalog tests**

Create `tests/test_product_catalog.py`:

```python
import json
from pathlib import Path

from embedagent.product_catalog import build_product_catalog
from embedagent_composition.compiler import compile_agent
from embedagent_composition.models import AgentProductDefinition


ROOT = Path(__file__).resolve().parents[1]


def compile_product(filename):
    payload = json.loads((ROOT / "products" / filename).read_text(encoding="utf-8"))
    definition = AgentProductDefinition.from_dict(payload)
    return payload, compile_agent(definition, build_product_catalog()).spec


def test_base_product_has_no_cpp_component_or_assets():
    payload, spec = compile_product("base-agent.json")
    assert all("cpp" not in component_id for component_id in spec.component_ids)
    assert all("clang" not in asset.lower() and "llvm" not in asset.lower() for asset in spec.runtime_assets)
    assert payload["workflows"] == []


def test_cpp_product_selects_cpp_workflow():
    payload, spec = compile_product("cpp-agent.json")
    assert payload["workflows"] == [{"component_id": "embedagent.workflow.cpp"}]
    assert "embedagent.workflow.cpp" in spec.component_ids


def test_product_catalog_is_explicit_not_discovered():
    source = (ROOT / "src/embedagent/product_catalog.py").read_text(encoding="utf-8")
    assert "importlib" not in source
    assert "entry_points" not in source
    assert ".discover(" not in source


def test_product_definitions_compile_without_credentials():
    for filename in ("base-agent.json", "cpp-agent.json"):
        payload, spec = compile_product(filename)
        serialized = json.dumps(payload, sort_keys=True).lower()
        assert "api_key" not in serialized
        assert "token" not in serialized
        assert spec.definition.agent_id
```

- [ ] **Step 2: Create explicit factory registration**

`build_product_catalog()` imports trusted factories from Host, Core, Protocol,
GUI descriptors, and `embedagent_workflow_cpp`, registers them explicitly, and
returns `catalog.freeze()`. This file is the only product composition root that
imports the C/C++ workflow package.

Do not use `importlib`, entry points, directory scanning, or manifest-provided
module paths.

- [ ] **Step 3: Add the base product definition**

`products/base-agent.json` references the generic profile, local
OpenAI-compatible provider, workspace tools, local resources, offline Host, and
no workflow or GUI component. It must compile without LLVM/Clang asset ids.

- [ ] **Step 4: Add the C/C++ product definition**

`products/cpp-agent.json` references the C/C++ profile/workflow contribution,
workspace and C/C++ tools, local/C++ resources, offline Host, and the existing
GUI shell descriptor. Its runtime assets come from the workflow and Host
manifests, not a product-side duplicated list.

- [ ] **Step 5: Run product catalog tests**

```bash
uv run pytest tests/test_product_catalog.py tests/test_agent_compiler.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit product definitions**

```bash
git add src/embedagent/product_catalog.py products tests/test_product_catalog.py
git commit -m "feat: declare base and cpp agent products"
```

### Task 6: Implement Fixed Exporters And CLI

**Files:**
- Create: `packages/embedagent-composition/src/embedagent_composition/exporters.py`
- Create: `packages/embedagent-composition/src/embedagent_composition/cli.py`
- Create: `packages/embedagent-composition/src/embedagent_composition/__main__.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/__init__.py`
- Modify: `packages/embedagent-composition/pyproject.toml`
- Modify: `scripts/prepare-offline.ps1`
- Modify: `scripts/build-offline-bundle.ps1`
- Create: `tests/test_agent_exporters.py`

- [ ] **Step 1: Write exporter failure and cleanup tests**

Create `tests/test_agent_exporters.py`. Keep the process boundary injectable so
unit tests do not invoke PowerShell:

```python
import hashlib
import json

import pytest

from embedagent_composition.exporters import (
    ExportError,
    export_portable_bundle,
    export_wheel_set,
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_export_inputs(tmp_path, wheel_names=("embedagent_core-0.1.0-py3-none-any.whl",), assets=()):
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    wheel_records = []
    for name in wheel_names:
        path = wheel_dir / name
        path.write_bytes(name.encode("ascii"))
        wheel_records.append({"filename": name, "sha256": sha256(path)})
    definition = tmp_path / "agent.json"
    definition.write_text('{"agent_id":"tests.agent"}\n', encoding="ascii")
    lock = tmp_path / "agent.lock.json"
    lock.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "agent": {"id": "tests.agent", "version": "1.0.0"},
                "wheels": wheel_records,
                "runtimeAssets": list(assets),
            },
            sort_keys=True,
        ) + "\n",
        encoding="ascii",
    )
    return definition, lock, wheel_dir


def test_wheel_set_export_copies_only_locked_wheels(tmp_path):
    definition, lock, wheel_dir = write_export_inputs(tmp_path)
    (wheel_dir / "unlocked.whl").write_bytes(b"not selected")
    destination = tmp_path / "export"
    report = export_wheel_set(definition, lock, wheel_dir, destination)
    assert sorted(path.name for path in (destination / "wheels").iterdir()) == [
        "embedagent_core-0.1.0-py3-none-any.whl"
    ]
    assert report.agent_id == "tests.agent"


def test_portable_export_passes_locked_assets_to_bundle_builder(tmp_path):
    definition, lock, wheel_dir = write_export_inputs(tmp_path, assets=("llvm.clang",))
    llvm = tmp_path / "llvm"
    llvm.mkdir()
    observed = {}

    def bundle_runner(request):
        observed.update(request)
        return 0

    export_portable_bundle(
        definition,
        lock,
        wheel_dir,
        {"llvm.clang": llvm},
        tmp_path / "portable",
        bundle_runner=bundle_runner,
    )
    assert observed["asset_ids"] == ("llvm.clang",)
    assert observed["definition_path"] == definition.resolve()


def test_missing_wheel_fails_before_destination_promotion(tmp_path):
    definition, lock, wheel_dir = write_export_inputs(tmp_path)
    next(wheel_dir.iterdir()).unlink()
    destination = tmp_path / "export"
    with pytest.raises(ExportError, match="missing locked wheel"):
        export_wheel_set(definition, lock, wheel_dir, destination)
    assert not destination.exists()


def test_missing_runtime_asset_fails_before_destination_promotion(tmp_path):
    definition, lock, wheel_dir = write_export_inputs(tmp_path, assets=("llvm.clang",))
    destination = tmp_path / "portable"
    with pytest.raises(ExportError, match="missing runtime asset llvm.clang"):
        export_portable_bundle(
            definition,
            lock,
            wheel_dir,
            {},
            destination,
            bundle_runner=lambda request: 0,
        )
    assert not destination.exists()


def test_failed_export_removes_temporary_directory(tmp_path):
    definition, lock, wheel_dir = write_export_inputs(tmp_path)
    destination = tmp_path / "portable"

    def failing_runner(request):
        raise RuntimeError("bundle failed")

    with pytest.raises(ExportError, match="bundle failed"):
        export_portable_bundle(
            definition,
            lock,
            wheel_dir,
            {},
            destination,
            bundle_runner=failing_runner,
        )
    assert not destination.exists()
    assert list(tmp_path.glob("portable.tmp-*")) == []
```

- [ ] **Step 2: Implement wheel-set export**

Create a temporary sibling directory, copy `agent.json`, `agent.lock.json`, and
exact locked wheels from `dist`, verify hashes after copying, write an export
report, then atomically rename the directory to the destination. Implement the
exact public function used above:

```python
def export_wheel_set(definition_path, lock_path, wheel_dir, destination):
    """Return ExportReport after atomically promoting a verified wheel set."""
```

- [ ] **Step 3: Implement portable-bundle coordination**

Invoke the existing PowerShell packaging control plane with explicit paths for
the compiled definition, lock, wheel directory, and locked asset id file. The
PowerShell scripts must consume those records and the existing
`offline-runtime-contract.json`; they must not rediscover a separate C/C++
tool list. `export_portable_bundle()` accepts
`bundle_runner: Callable[[Mapping[str, Any]], int]`; production passes the
PowerShell runner and tests pass an in-process recorder. A non-zero return or
exception becomes `ExportError` and removes the sibling staging directory.

- [ ] **Step 4: Implement CLI commands**

Provide:

```text
python -m embedagent_composition validate <definition>
python -m embedagent_composition compile <definition> --output <dir>
python -m embedagent_composition export <definition> --output <dir>
```

Exit 0 on success, 2 for definition/catalog errors, 3 for missing wheel/assets,
and 4 for exporter process failure. Print safe JSON diagnostics to stdout.

- [ ] **Step 5: Add the console script**

In the composition pyproject:

```toml
[project.scripts]
embedagent-compose = "embedagent_composition.cli:main"
```

- [ ] **Step 6: Run exporter tests**

```bash
uv run pytest tests/test_agent_exporters.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit exporters**

```bash
git add packages/embedagent-composition scripts tests/test_agent_exporters.py
git commit -m "feat: export deterministic agent products"
```

### Task 7: Add Exported Product Smoke And Milestone Gates

**Files:**
- Create: `scripts/smoke-exported-agent.py`
- Modify: `scripts/check-python-distributions.py`
- Modify: `Makefile`
- Test: `tests/test_agent_exporters.py`

- [ ] **Step 1: Implement exported-agent smoke**

The script accepts an export directory and `--expect-agent`. It verifies lock
hashes, creates a temporary Python 3.8 environment, installs only exported
wheels with `--no-index`, imports the declared bootstrap, uses a fake model to
open one session, and asserts the runtime capability manifest agent id.

For C/C++ export, also invoke the existing bundle-local C smoke validator. For
base export, assert no workflow C++ wheel and no LLVM asset path exists.

- [ ] **Step 2: Build and export both products twice**

```bash
uv build --all-packages
uv run python -m embedagent_composition export products/base-agent.json --output build/exports/base-a
uv run python -m embedagent_composition export products/base-agent.json --output build/exports/base-b
uv run python -m embedagent_composition export products/cpp-agent.json --output build/exports/cpp-a
uv run python -m embedagent_composition export products/cpp-agent.json --output build/exports/cpp-b
```

Expected: all commands exit zero.

- [ ] **Step 3: Compare deterministic records**

```bash
git diff --no-index -- build/exports/base-a/agent.lock.json build/exports/base-b/agent.lock.json
git diff --no-index -- build/exports/cpp-a/agent.lock.json build/exports/cpp-b/agent.lock.json
```

Expected: both commands exit zero with no diff.

- [ ] **Step 4: Run exported smokes**

```bash
uv run python scripts/smoke-exported-agent.py build/exports/base-a --expect-agent embedagent.base
uv run python scripts/smoke-exported-agent.py build/exports/cpp-a --expect-agent embedagent.default_c_cpp
```

Expected: PASS.

- [ ] **Step 5: Add composition gates to local CI**

Add compiler, lock, exporter, distribution inspection, and both product smokes
after wheel build. Do not add Win7 target-machine smoke to ordinary local CI;
keep it as an explicit release gate.

- [ ] **Step 6: Commit milestone gates**

```bash
git add scripts Makefile tests
git commit -m "test: gate deterministic agent exports"
```

### Task 8: Close Milestone Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: packaging/offline deployment documentation

- [ ] **Step 1: Document product composition commands**

Add the two source product definitions, catalog trust rule, lock format,
supported fixed exporters, and exact offline verification commands. State that
runtime discovery/installation and arbitrary entry points are unsupported.

- [ ] **Step 2: Run composition and package tests**

```bash
uv run pytest tests/test_component_catalog.py tests/test_agent_compiler.py tests/test_agent_lockfile.py tests/test_product_catalog.py tests/test_agent_exporters.py -v
uv run pytest tests/test_python_distribution_contract.py tests/test_cpp_workflow_distribution.py -v
```

Expected: PASS.

- [ ] **Step 3: Run architecture and fast regression gates**

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Expected: PASS.

- [ ] **Step 4: Run GUI gate**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
```

Expected: PASS and generated assets are committed if changed.

- [ ] **Step 5: Run complete first-milestone export gate**

Run every command under `Milestone Verification` in
`2026-07-11-agent-core-first-milestone-roadmap.md`.

Expected: all commands exit zero and both exported-agent smokes pass.

- [ ] **Step 6: Commit milestone closeout**

```bash
git add README.md AGENTS.md docs src/embedagent/frontend/gui/static
git commit -m "docs: complete independent agent core milestone"
```
