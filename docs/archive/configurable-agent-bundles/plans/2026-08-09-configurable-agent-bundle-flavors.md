# Configurable Agent Bundle Flavors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic `minimal-cli` and `cpp-desktop` offline bundle flavors from one hash-bound plan while preserving the exact six-wheel distribution contract.

**Architecture:** `embedagent-composition` owns dependency-free recipe and immutable plan contracts. Product code owns the audited component catalog and official recipes; a Python CLI compiles those inputs with the schema-versioned runtime contract before any package stage mutates output. Dependency export, staging, validation, release identity, target evidence, and runtime bootstrap consume the same plan and fail closed on a hash or capability mismatch.

**Tech Stack:** Python 3.8, dataclasses, stdlib JSON/hash/path APIs, pytest, PowerShell 5.1-compatible scripts, uv locked dependency export, Windows 7 portable bundle tooling.

---

## Scope And File Map

This is one sequential product-delivery change rather than independent sub-projects: later stages cannot be made plan-driven until the immutable plan and official recipes exist, and runtime/evidence enforcement is not useful until the plan is embedded in the artifact. Implement the tasks in order.

New files:

- `packages/embedagent-composition/src/embedagent_composition/recipes.py`: immutable recipe and frozen registry contracts.
- `packages/embedagent-composition/src/embedagent_composition/bundle.py`: canonical hashing, runtime-capability closure, condition evaluation, and `CompiledBundlePlan`.
- `src/embedagent/bundle_catalog.py`: trusted product component catalog and the two official recipes.
- `src/embedagent/bundle_policy.py`: read-only runtime enforcement of bundle application and shell restrictions.
- `scripts/compile-bundle-plan.py`: build-time CLI that writes `agent.json`, `agent.lock.json`, and `bundle-plan.json` atomically.
- `config/bundle-flavors/minimal-cli.json`: credential-free generic Agent configuration template.
- `config/bundle-flavors/cpp-desktop.json`: credential-free default C/C++ configuration template.
- `tests/test_bundle_plan.py`: dependency-free recipe/plan compiler contract tests.
- `tests/test_product_bundle_recipes.py`: production catalog and official flavor tests.
- `tests/test_bundle_runtime_policy.py`: packaged runtime restriction tests.

Primary modified files:

- `packages/embedagent-composition/src/embedagent_composition/model.py`, `catalog.py`, `definitions.py`, `__init__.py`
- `tests/test_agent_composition.py`
- `scripts/offline-runtime-contract.json`, `package.config.json`, `package.ps1`, `package-lib.ps1`
- `scripts/export-dependencies.py`, `prepare-offline.ps1`, `build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`, `check-bundle-dependencies.py`
- `scripts/release_identity.py`, `create-release-identity.py`, `validate-release-evidence.py`
- `src/embedagent/product_catalog.py`, `hosted.py`, `cli.py`
- `src/embedagent/frontend/tui/launcher.py`, `src/embedagent/frontend/gui/launcher.py`
- packaging fixtures and release tests under `tests/fixtures/package/` and `tests/`
- `pyproject.toml` and generated `uv.lock` through `uv lock`, never by hand
- product composition, packaging, configuration, release, status, roadmap, and code/doc ownership documents

## Shared Constants

Use these exact identifiers throughout all tasks:

```python
PORTABLE_PROJECT_DISTRIBUTIONS = (
    "embedagent-core",
    "embedagent-protocol",
    "embedagent-host",
    "embedagent-composition",
    "embedagent-workflow-cpp",
    "embedagent",
)

MINIMAL_CLI_FLAVOR = "minimal-cli"
CPP_DESKTOP_FLAVOR = "cpp-desktop"
PORTABLE_TARGET = "win7-x64-portable"

CLI_SHELL_ID = "cli"
TUI_SHELL_ID = "tui"
GUI_SHELL_ID = "gui"
```

The canonical plan filename is `bundle-plan.json`; the canonical in-bundle path is `manifests/bundle-plan.json`. Plan schema version starts at `1`; runtime contract schema version becomes `2`; release identity schema version becomes `2`.

### Task 1: Generalize Agent Composition For Shells And Runtime Requirements

**Files:**

- Modify: `packages/embedagent-composition/src/embedagent_composition/model.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/catalog.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/definitions.py`
- Modify: `tests/test_agent_composition.py`

- [ ] **Step 1: Write failing composition tests**

Add tests that prove shell references participate in component closure and runtime requirements are deterministic and validated:

```python
def test_shells_and_runtime_requirements_are_compiled_deterministically():
    catalog = ComponentCatalog()
    catalog.register(manifest("profile", "profile"))
    catalog.register(
        ComponentManifest(
            component_id="shell.cli",
            kind="shell",
            version="0.1.0",
            api_version="agent_component_v1",
            runtime_requirements=("runtime.python", "search.rg"),
        )
    )
    definition = AgentProductDefinition(
        agent_id="tests.agent",
        profile=ComponentRef("profile"),
        shells=(ComponentRef("shell.cli"),),
    )

    compiled = compile_agent(definition, catalog.freeze())

    components = dict(
        (item["component_id"], item) for item in compiled.manifest["components"]
    )
    assert components["shell.cli"]["runtime_requirements"] == [
        "runtime.python",
        "search.rg",
    ]


@pytest.mark.parametrize(
    "requirement",
    ("", "Runtime.Python", "runtime python", "runtime/python", "runtime..python"),
)
def test_catalog_rejects_invalid_runtime_requirement(requirement):
    catalog = ComponentCatalog()
    with pytest.raises(CompositionError) as error:
        catalog.register(
            ComponentManifest(
                component_id="invalid",
                kind="profile",
                version="0.1.0",
                api_version="agent_component_v1",
                runtime_requirements=(requirement,),
            )
        )
    assert error.value.code == "invalid_runtime_requirement"
```

Replace every `gui=ComponentRef("shell.gui")` test construction with
`shells=(ComponentRef("shell.gui"),)` and assert `component_refs()` contains each shell once.

- [ ] **Step 2: Run the focused test and verify red**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_agent_composition.py
```

Expected: failure because `runtime_requirements` and `shells` do not exist.

- [ ] **Step 3: Implement the composition model change**

In `ComponentManifest`, add the field and serialize it:

```python
runtime_requirements: Tuple[str, ...] = field(default_factory=tuple)
```

```python
"runtime_requirements": list(self.runtime_requirements),
```

Replace the `gui` field in `AgentProductDefinition` with:

```python
shells: Tuple[ComponentRef, ...] = field(default_factory=tuple)
```

Replace the final GUI branch in `component_refs()` with:

```python
refs.extend(self.shells)
return tuple(refs)
```

This is a pre-release cutover: do not retain a `gui` alias or compatibility property.

- [ ] **Step 4: Validate requirement identifiers in the catalog**

Add at module scope in `catalog.py`:

```python
import re

_RUNTIME_REQUIREMENT_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_-]*)+$")
```

Add inside `ComponentCatalog.register()` before storing the manifest:

```python
for requirement in manifest.runtime_requirements:
    value = str(requirement or "").strip()
    if not _RUNTIME_REQUIREMENT_RE.match(value):
        raise CompositionError("invalid_runtime_requirement", value)
```

- [ ] **Step 5: Update built-in definitions and run green**

Keep the existing application definitions shell-neutral. Official recipes in Task 4 will add shell references, so `generic_agent_definition()` and `c_cpp_agent_definition()` continue to describe application behavior only.

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_agent_composition.py
```

Expected: all tests in `tests/test_agent_composition.py` pass.

- [ ] **Step 6: Commit**

```powershell
git add packages/embedagent-composition/src/embedagent_composition/model.py packages/embedagent-composition/src/embedagent_composition/catalog.py packages/embedagent-composition/src/embedagent_composition/definitions.py tests/test_agent_composition.py
git commit -m "refactor: generalize composition shell requirements"
```

### Task 2: Add Immutable Recipe And Registry Contracts

**Files:**

- Create: `packages/embedagent-composition/src/embedagent_composition/recipes.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/__init__.py`
- Test: `tests/test_bundle_plan.py`

- [ ] **Step 1: Write registry failure and determinism tests**

Create `tests/test_bundle_plan.py` with the initial registry tests:

```python
import pytest
from embedagent_composition import (
    AgentProductDefinition,
    ComponentRef,
    CompositionError,
    FrozenBundleRecipeRegistry,
    OfficialBundleRecipe,
)


def _definition():
    return AgentProductDefinition(
        agent_id="tests.generic",
        profile=ComponentRef("profile.generic"),
        shells=(ComponentRef("shell.cli"),),
    )


def _recipe(recipe_id="minimal-cli"):
    return OfficialBundleRecipe(
        recipe_id=recipe_id,
        definition_factory=_definition,
        shell_ids=("cli",),
        config_template_id="minimal-cli",
    )


def test_recipe_registry_is_sorted_and_frozen():
    registry = FrozenBundleRecipeRegistry((_recipe("z-last"), _recipe("a-first")))
    assert registry.names() == ("a-first", "z-last")
    assert registry.resolve("a-first").definition_factory().agent_id == "tests.generic"


def test_recipe_registry_rejects_duplicates_and_unknown_ids():
    with pytest.raises(CompositionError) as duplicate:
        FrozenBundleRecipeRegistry((_recipe(), _recipe()))
    assert duplicate.value.code == "duplicate_bundle_recipe"

    registry = FrozenBundleRecipeRegistry((_recipe(),))
    with pytest.raises(CompositionError) as unknown:
        registry.resolve("missing")
    assert unknown.value.code == "unknown_bundle_recipe"
```

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_bundle_plan.py
```

Expected: import failure for the recipe contracts.

- [ ] **Step 3: Implement `recipes.py`**

Create the complete contract module:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Tuple

from .errors import CompositionError
from .model import AgentProductDefinition


@dataclass(frozen=True)
class OfficialBundleRecipe:
    recipe_id: str
    definition_factory: Callable[[], AgentProductDefinition]
    shell_ids: Tuple[str, ...]
    config_template_id: str

    def __post_init__(self) -> None:
        recipe_id = str(self.recipe_id or "").strip()
        template_id = str(self.config_template_id or "").strip()
        shells = tuple(str(item or "").strip() for item in self.shell_ids)
        if not recipe_id or not template_id or not callable(self.definition_factory):
            raise CompositionError("invalid_bundle_recipe", recipe_id)
        if not shells or any(not item for item in shells) or len(set(shells)) != len(shells):
            raise CompositionError("invalid_bundle_recipe_shells", recipe_id)
        object.__setattr__(self, "recipe_id", recipe_id)
        object.__setattr__(self, "config_template_id", template_id)
        object.__setattr__(self, "shell_ids", shells)


class FrozenBundleRecipeRegistry(object):
    def __init__(self, recipes: Iterable[OfficialBundleRecipe]):
        records = {}  # type: Dict[str, OfficialBundleRecipe]
        for recipe in recipes:
            if recipe.recipe_id in records:
                raise CompositionError("duplicate_bundle_recipe", recipe.recipe_id)
            records[recipe.recipe_id] = recipe
        if not records:
            raise CompositionError("empty_bundle_recipe_registry", "no recipes registered")
        self._recipes = records

    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._recipes))

    def resolve(self, recipe_id: str) -> OfficialBundleRecipe:
        requested = str(recipe_id or "").strip()
        try:
            return self._recipes[requested]
        except KeyError:
            raise CompositionError("unknown_bundle_recipe", requested)
```

- [ ] **Step 4: Export the public contracts**

Import both classes in `embedagent_composition/__init__.py` and add them to `__all__`:

```python
from .recipes import FrozenBundleRecipeRegistry, OfficialBundleRecipe
```

```python
"FrozenBundleRecipeRegistry",
"OfficialBundleRecipe",
```

- [ ] **Step 5: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_bundle_plan.py
git add packages/embedagent-composition/src/embedagent_composition/recipes.py packages/embedagent-composition/src/embedagent_composition/__init__.py tests/test_bundle_plan.py
git commit -m "feat: add official bundle recipe registry"
```

Expected: registry tests pass and the commit succeeds.

### Task 3: Compile A Canonical Bundle Plan

**Files:**

- Create: `packages/embedagent-composition/src/embedagent_composition/bundle.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/__init__.py`
- Modify: `tests/test_bundle_plan.py`

- [ ] **Step 1: Add plan compiler tests**

Add fixtures with one CLI recipe, one GUI runtime provider, and conditional gates. Assert exact six distributions, sorted closure, deterministic hashes, and fail-closed ambiguity:

```python
import hashlib
import json

from embedagent_composition import ComponentCatalog, ComponentManifest, compile_bundle_plan


def _catalog():
    catalog = ComponentCatalog()
    catalog.register(
        ComponentManifest(
            component_id="profile.generic",
            kind="profile",
            version="0.1.0",
            api_version="agent_component_v1",
            runtime_requirements=("runtime.python",),
        )
    )
    catalog.register(
        ComponentManifest(
            component_id="shell.cli",
            kind="shell",
            version="0.1.0",
            api_version="agent_component_v1",
        )
    )
    return catalog.freeze()


def _runtime_contract():
    return {
        "schema_version": 2,
        "targets": {
            "win7-x64-portable": {
                "always_requires": ["runtime.python"],
                "always_gates": ["runtime_contract"],
            }
        },
        "runtime_components": [
            {
                "id": "python",
                "provides": ["runtime.python"],
                "asset_ids": ["python_embedded_x64"],
                "paths": ["runtime/python/python.exe"],
                "python_feature_ids": [],
                "launcher_ids": ["cli"],
            }
        ],
        "release_gates": [
            {"id": "runtime_contract", "applies_when": {"all_of": []}}
        ],
    }


def _asset_manifest():
    return {
        "schema_version": 1,
        "assets": [
            {
                "id": "python_embedded_x64",
                "version": "3.8.10",
                "sha256": "a" * 64,
            }
        ],
    }


def test_bundle_plan_is_deterministic_and_exactly_six_distributions():
    first = compile_bundle_plan(
        recipe=_recipe(),
        catalog=_catalog(),
        runtime_contract=_runtime_contract(),
        asset_manifest=_asset_manifest(),
        target_id="win7-x64-portable",
        assurance="release",
    )
    second = compile_bundle_plan(
        recipe=_recipe(),
        catalog=_catalog(),
        runtime_contract=_runtime_contract(),
        asset_manifest=_asset_manifest(),
        target_id="win7-x64-portable",
        assurance="release",
    )

    assert first.to_dict() == second.to_dict()
    assert first.project_distribution_ids == PORTABLE_PROJECT_DISTRIBUTIONS
    assert first.config_template_id == "minimal-cli"
    assert first.allowed_agent_application_ids == ("tests.generic",)
    assert first.runtime_capability_ids == ("runtime.python",)
    assert first.asset_ids == ("python_embedded_x64",)
    assert first.gate_ids == ("runtime_contract",)
    encoded = json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":"))
    assert first.sha256 == hashlib.sha256(encoded.encode("ascii")).hexdigest()


def test_bundle_plan_rejects_ambiguous_runtime_provider():
    contract = _runtime_contract()
    contract["runtime_components"].append(
        {
            "id": "second-python",
            "provides": ["runtime.python"],
            "asset_ids": [],
            "paths": ["runtime/python/other.exe"],
            "python_feature_ids": [],
            "launcher_ids": [],
        }
    )
    with pytest.raises(CompositionError) as error:
        compile_bundle_plan(
            recipe=_recipe(),
            catalog=_catalog(),
            runtime_contract=contract,
            asset_manifest=_asset_manifest(),
            target_id="win7-x64-portable",
            assurance="release",
        )
    assert error.value.code == "ambiguous_runtime_provider"
```

Define `PORTABLE_PROJECT_DISTRIBUTIONS` in the test module with the shared constant tuple from this plan.

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_bundle_plan.py
```

Expected: import failure for `compile_bundle_plan` and `CompiledBundlePlan`.

- [ ] **Step 3: Implement the immutable plan type and canonical hash**

Create `bundle.py` with a frozen `CompiledBundlePlan` containing these fields in this exact order:

```python
@dataclass(frozen=True)
class CompiledBundlePlan:
    schema_version: int
    flavor_id: str
    target_id: str
    assurance: str
    artifact_name: str
    agent_id: str
    config_template_id: str
    allowed_agent_application_ids: Tuple[str, ...]
    component_ids: Tuple[str, ...]
    shell_ids: Tuple[str, ...]
    plan_fact_ids: Tuple[str, ...]
    runtime_capability_ids: Tuple[str, ...]
    runtime_component_ids: Tuple[str, ...]
    asset_ids: Tuple[str, ...]
    python_feature_ids: Tuple[str, ...]
    launcher_ids: Tuple[str, ...]
    gate_ids: Tuple[str, ...]
    project_distribution_ids: Tuple[str, ...]
    agent_lock_sha256: str
    component_catalog_sha256: str
    runtime_contract_sha256: str
```

`to_dict()` must emit only those fields, converting tuples to lists:

```python
def to_dict(self) -> Dict[str, object]:
    return {
        "schema_version": self.schema_version,
        "flavor_id": self.flavor_id,
        "target_id": self.target_id,
        "assurance": self.assurance,
        "artifact_name": self.artifact_name,
        "agent_id": self.agent_id,
        "config_template_id": self.config_template_id,
        "allowed_agent_application_ids": list(self.allowed_agent_application_ids),
        "component_ids": list(self.component_ids),
        "shell_ids": list(self.shell_ids),
        "plan_fact_ids": list(self.plan_fact_ids),
        "runtime_capability_ids": list(self.runtime_capability_ids),
        "runtime_component_ids": list(self.runtime_component_ids),
        "asset_ids": list(self.asset_ids),
        "python_feature_ids": list(self.python_feature_ids),
        "launcher_ids": list(self.launcher_ids),
        "gate_ids": list(self.gate_ids),
        "project_distribution_ids": list(self.project_distribution_ids),
        "agent_lock_sha256": self.agent_lock_sha256,
        "component_catalog_sha256": self.component_catalog_sha256,
        "runtime_contract_sha256": self.runtime_contract_sha256,
    }
```

Implement `sha256` as a property over `to_dict()` so the hash never contains itself:

```python
def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _value_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


@property
def sha256(self) -> str:
    return _value_sha256(self.to_dict())
```

- [ ] **Step 4: Implement fail-closed capability closure**

Use these exact rules in `compile_bundle_plan()`:

```python
if runtime_contract.get("schema_version") != 2:
    raise CompositionError("unsupported_runtime_contract", str(runtime_contract.get("schema_version")))
target = (runtime_contract.get("targets") or {}).get(target_id)
if not isinstance(target, dict):
    raise CompositionError("unknown_bundle_target", target_id)

compiled_agent = compile_agent(recipe.definition_factory(), catalog)
components = compiled_agent.manifest["components"]
component_ids = tuple(item["component_id"] for item in components)
requirements = set(target.get("always_requires") or ())
for component in components:
    requirements.update(component.get("runtime_requirements") or ())
```

Index every `runtime_components` entry by `id` and every provided capability. Reject blank/duplicate component IDs, blank/duplicate capabilities, ambiguous providers, unknown requirements, and runtime-component dependency cycles with `CompositionError`. Resolve requirements and each selected component's optional `requires` list until stable.

Index the top-level runtime-contract `launchers` array by unique ID. After gate selection,
collect launcher IDs from selected runtime components and selected gates, reject unknown IDs,
and serialize the sorted unique IDs into the plan. Recipes and package configuration never
declare launcher IDs.

Derive facts without recipe-supplied strings:

```python
facts = set(
    "component.%s.%s" % (item["kind"], item["component_id"].replace("_", "-").replace(".", "-"))
    for item in components
)
facts.update("shell.%s" % item for item in recipe.shell_ids)
facts.update("runtime.%s" % item for item in requirements)
facts.add("assurance.%s" % assurance)
facts.add("target.%s" % target_id)
```

Validate conditions recursively. Only dictionaries containing exactly one of `all_of`, `any_of`, or `not` are accepted. `all_of` and `any_of` values are lists of known fact strings; `not` contains one known fact string. Unknown operators or facts raise `CompositionError` before a plan is returned.

Preserve existing desktop artifact paths: `cpp-desktop` compiles to `embedagent-win7-x64`
for release and `embedagent-win7-x64-dev` for dev. `minimal-cli` compiles to
`embedagent-minimal-cli-win7-x64` for release and appends `-dev` for dev. Set
`allowed_agent_application_ids` to the single compiled `agent_id`. Validate the selected shell
components by comparing `recipe.shell_ids` with component IDs `shell.<shell_id>` from the
compiled agent.

- [ ] **Step 5: Export, run green, and commit**

Export `CompiledBundlePlan` and `compile_bundle_plan` through `embedagent_composition.__init__`.

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_bundle_plan.py
git add packages/embedagent-composition/src/embedagent_composition/bundle.py packages/embedagent-composition/src/embedagent_composition/__init__.py tests/test_bundle_plan.py
git commit -m "feat: compile immutable bundle plans"
```

Expected: plan compiler tests pass.

### Task 4: Add The Production Catalog, Official Flavors, And Plan CLI

**Files:**

- Create: `src/embedagent/bundle_catalog.py`
- Create: `scripts/compile-bundle-plan.py`
- Create: `config/bundle-flavors/minimal-cli.json`
- Create: `config/bundle-flavors/cpp-desktop.json`
- Create: `tests/test_product_bundle_recipes.py`
- Modify: `scripts/offline-runtime-contract.json`
- Modify: `scripts/offline-assets.json` only if a selected runtime component adds an archive asset not already represented

- [ ] **Step 1: Write official flavor tests**

Create tests that compile both flavors using the production files:

```python
import json
from pathlib import Path

from embedagent_composition import compile_bundle_plan
from embedagent.bundle_catalog import official_bundle_recipe_registry, product_component_catalog

ROOT = Path(__file__).resolve().parents[1]


def _compile(flavor):
    contract = json.loads(
        (ROOT / "scripts" / "offline-runtime-contract.json").read_text(encoding="utf-8")
    )
    assets = json.loads(
        (ROOT / "scripts" / "offline-assets.json").read_text(encoding="utf-8")
    )
    return compile_bundle_plan(
        recipe=official_bundle_recipe_registry().resolve(flavor),
        catalog=product_component_catalog(),
        runtime_contract=contract,
        asset_manifest=assets,
        target_id="win7-x64-portable",
        assurance="release",
    )


def test_minimal_cli_excludes_cpp_gui_and_desktop_gates():
    plan = _compile("minimal-cli")
    assert plan.shell_ids == ("cli",)
    assert plan.allowed_agent_application_ids == ("embedagent.generic",)
    assert "renderer.webview2" not in plan.runtime_capability_ids
    assert "toolchain.clang" not in plan.runtime_capability_ids
    assert "gui" not in plan.python_feature_ids
    assert "tui" not in plan.python_feature_ids
    assert "gui_headless_smoke" not in plan.gate_ids
    assert "cpp_smoke_workspace" not in plan.gate_ids
    assert plan.gate_ids == ("runtime_contract", "win7_cli_smoke")


def test_cpp_desktop_preserves_full_runtime_and_gates():
    plan = _compile("cpp-desktop")
    assert plan.shell_ids == ("cli", "tui", "gui")
    assert plan.allowed_agent_application_ids == ("embedagent.default_c_cpp",)
    assert "renderer.webview2" in plan.runtime_capability_ids
    assert "toolchain.clang" in plan.runtime_capability_ids
    assert plan.python_feature_ids == ("gui", "tui")
    assert set(plan.gate_ids) == {
        "runtime_contract",
        "win7_cli_smoke",
        "cpp_smoke_workspace",
        "gui_headless_smoke",
        "win7_windowed_gui_smoke",
    }
```

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_product_bundle_recipes.py
```

Expected: `embedagent.bundle_catalog` is missing.

- [ ] **Step 3: Build the trusted production catalog**

In `bundle_catalog.py`, register these component IDs and exact runtime requirements:

| Component | Kind | Requires | Runtime requirements |
|---|---|---|---|
| `profile.generic` | `profile` | `embedagent-core` | `runtime.python` |
| `profile.cpp` | `profile` | `embedagent-core` | `runtime.python` |
| `provider.openai-compatible` | `provider` | `embedagent-host` | `runtime.python` |
| `toolset.workflow-neutral` | `toolset` | `embedagent-host` | `runtime.python`, `vcs.git`, `shell.bash`, `search.rg`, `symbols.ctags` |
| `workflow.cpp` | `workflow` | `embedagent-workflow-cpp` | `toolchain.clang` |
| `shell.cli` | `shell` | `embedagent` | none |
| `shell.tui` | `shell` | `embedagent` | `python-feature.tui` |
| `shell.gui` | `shell` | `embedagent` | `python-feature.gui`, `renderer.webview2` |

Also register the six distribution components using their exact dependency direction from `AGENTS.md`. Use version `0.1.0` and API version `agent_component_v1` for every record.

Create two definition factories. The minimal factory selects generic profile, provider, neutral toolset, Host, and CLI. The desktop factory selects C++ profile, provider, neutral toolset, C++ workflow, Host, and all three shells. Return a new frozen catalog and registry from each public factory so callers cannot mutate global state.

- [ ] **Step 4: Replace the runtime contract with schema version 2**

Use target `win7-x64-portable`, with `always_requires: ["runtime.python"]` and `always_gates: ["runtime_contract"]`. Convert each existing required tool into a runtime component while preserving its existing paths, alternatives, child commands, dynamic checks, notes, and no-system-fallback behavior.

Use this exact capability and contribution mapping:

| Runtime component | Provides | Asset IDs | Python features | Launchers |
|---|---|---|---|---|
| `python` | `runtime.python` | `python_embedded_x64` | none | `cli` |
| `mingit` | `vcs.git`, `shell.bash` | `mingit_x64` | none | none |
| `ripgrep` | `search.rg` | `ripgrep_x64` | none | none |
| `ctags` | `symbols.ctags` | `universal_ctags_x64` | none | none |
| `llvm` | `toolchain.clang` | none; staged from trusted `paths.llvm_root` | none | none |
| `tui-python` | `python-feature.tui` | none | `tui` | `tui` |
| `gui-python` | `python-feature.gui` | none | `gui` | `gui-command` |
| `webview2` | `renderer.webview2` | `webview2_fixed_runtime_x64` | none | `gui-native-user`, `gui-native-cli` |

Define these exact top-level launcher records; each record owns its staged relative path:

| Launcher ID | Staged path |
|---|---|
| `cli` | `embedagent.cmd` |
| `tui` | `embedagent-tui.cmd` |
| `gui-command` | `embedagent-gui.cmd` |
| `gui-native-user` | `EmbedAgent.exe` |
| `gui-native-cli` | `embedagent-gui.exe` |
| `cli-smoke` | `validate-cli-smoke.cmd` |
| `cpp-smoke` | `validate-cpp-smoke.cmd` |
| `gui-smoke` | `validate-gui-smoke.cmd` |

The three smoke gates contribute `cli-smoke`, `cpp-smoke`, and `gui-smoke` respectively.

Use these exact conditions:

```json
{"id":"runtime_contract","applies_when":{"all_of":[]}}
{"id":"win7_cli_smoke","applies_when":{"all_of":["shell.cli","assurance.release"]}}
{"id":"cpp_smoke_workspace","applies_when":{"all_of":["component.workflow.workflow-cpp","runtime.toolchain.clang"]}}
{"id":"gui_headless_smoke","applies_when":{"all_of":["shell.gui","runtime.renderer.webview2"]}}
{"id":"win7_windowed_gui_smoke","applies_when":{"all_of":["shell.gui","runtime.renderer.webview2","assurance.release"]}}
```

Keep the existing gate script, launcher, args, WebView2 version, renderer, and fallback fields on the matching records.

- [ ] **Step 5: Add credential-free templates**

`minimal-cli.json`:

```json
{
  "base_url": "http://127.0.0.1:8000/v1",
  "model": "",
  "timeout": 120,
  "default_mode": "explore",
  "agent_application_id": "embedagent.generic"
}
```

`cpp-desktop.json`:

```json
{
  "base_url": "http://127.0.0.1:8000/v1",
  "model": "",
  "timeout": 120,
  "default_mode": "explore",
  "agent_application_id": "embedagent.default_c_cpp"
}
```

Neither file may contain `api_key`.

- [ ] **Step 6: Implement the atomic plan compiler CLI**

`compile-bundle-plan.py` accepts exactly:

```text
--flavor
--target
--assurance
--runtime-contract
--asset-manifest
--output-dir
--json-report
```

Resolve the official recipe, compile the Agent and plan, and create a sibling output directory
whose name is the final directory plus `.tmp`. Write `agent.json`, `agent.lock.json`, and
`bundle-plan.json` as canonical sorted compact ASCII JSON with no trailing newline, then replace
the final directory. This makes the on-disk SHA-256 equal to the compiler's canonical SHA-256;
PowerShell never reimplements JSON canonicalization. The report contains `ok`, `flavor_id`,
`target_id`, `assurance`, `plan_path`, and `plan_sha256`; on failure it contains only `ok`,
`error_code`, and a credential-free error message. Reject an output path whose parent equals
itself.

- [ ] **Step 7: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_product_bundle_recipes.py tests/test_bundle_plan.py
uv run python scripts/compile-bundle-plan.py --flavor minimal-cli --target win7-x64-portable --assurance dev --runtime-contract scripts/offline-runtime-contract.json --asset-manifest scripts/offline-assets.json --output-dir build/test-bundle-plan --json-report build/test-bundle-plan-report.json
git add src/embedagent/bundle_catalog.py scripts/compile-bundle-plan.py scripts/offline-runtime-contract.json scripts/offline-assets.json config/bundle-flavors tests/test_product_bundle_recipes.py
git commit -m "feat: add official bundle flavor plans"
```

Expected: tests pass and the CLI report records the same hash as the emitted plan.

### Task 5: Resolve Flavor Before Any Packaging Mutation

**Files:**

- Modify: `scripts/package.config.json`
- Modify: `scripts/package.ps1`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/fixtures/package/mock-config.json`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_package_report_provenance.py`

- [ ] **Step 1: Write package context tests**

Update `TestPackageFoundation` to assert `default_flavor == "cpp-desktop"`, the public command accepts `-Flavor minimal-cli`, and unknown flavors fail before the configured build root exists. Add this PowerShell-level assertion:

```python
def test_profile_and_flavor_are_orthogonal(self):
    result = run_pwsh(
        ". '{lib}'; "
        "$cfg = Read-PackageConfig -Path '{config}'; "
        "$ctx = New-PackageContext -ProjectRoot '{root}' -Config $cfg "
        "-ConfigPath '{config}' -Command 'doctor' -RequestedProfile 'release' "
        "-RequestedFlavor 'minimal-cli' -BundleRoot '' -OutputRoot '' "
        "-ArtifactName '' -AllowDownload $false -NoZip $false -Strict $false; "
        "[ordered]@{{profile=$ctx.profile; flavor=$ctx.flavor; plan=$ctx.bundle_plan.flavor_id}} "
        "| ConvertTo-Json -Compress".format(
            lib=str(LIB).replace("\\", "\\\\"),
            config=str(CONFIG).replace("\\", "\\\\"),
            root=str(ROOT).replace("\\", "\\\\"),
        )
    )
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(json.loads(result.stdout), {
        "profile": "release",
        "flavor": "minimal-cli",
        "plan": "minimal-cli",
    })
```

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py tests/test_package_report_provenance.py
```

Expected: configuration and parameter assertions fail.

- [ ] **Step 3: Simplify package configuration**

Add at the root of both production and fixture config:

```json
"default_flavor": "cpp-desktop"
```

Add tooling path:

```json
"compile_bundle_plan": "scripts/compile-bundle-plan.py"
```

Remove `required_assets`, `required_project_distributions`, `run_frontend_build`, and `run_gui_launcher_build` from both profile records. Profiles retain assurance-only properties: artifact override, download/offline policy, completeness, zip, dynamic checks, dependency checker, and minimum disk space.

- [ ] **Step 4: Add public `-Flavor` and compile the plan in context creation**

Add to `package.ps1`:

```powershell
[ValidateSet('minimal-cli', 'cpp-desktop')]
[string]$Flavor = '',
```

Pass it as `-RequestedFlavor $Flavor`. Add that parameter to `New-PackageContext`. Resolve it from the explicit argument or `Config.default_flavor` and invoke `compile-bundle-plan.py` before resolving or creating build/output roots. Store:

```powershell
flavor = $effectiveFlavor
bundle_plan = $plan
bundle_plan_path = $planPath
bundle_plan_sha256 = $planReport.plan_sha256
```

The plan output root is `reports_root\plan-<flavor>-<profile>`. Delete only the known prior plan directory after the new temporary compile succeeds; the Python compiler owns atomic replacement.

- [ ] **Step 5: Put plan identity into every report**

Add `flavor`, `bundle_plan_path`, and `bundle_plan_sha256` to `New-PackageContextReport`, doctor output, errors emitted by `package.ps1`, and reproducibility child arguments. Log commands as:

```powershell
Write-PackageLog ("=== Package Command: {0} (profile: {1}, flavor: {2}) ===" -f $Context.command, $Context.profile, $Context.flavor)
```

When `ArtifactName` is omitted, use `bundle_plan.artifact_name`, not a profile field.

- [ ] **Step 6: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py tests/test_package_report_provenance.py tests/test_release_reproducibility.py
git add scripts/package.config.json scripts/package.ps1 scripts/package-lib.ps1 tests/fixtures/package/mock-config.json tests/test_packaging_control_plane.py tests/test_package_report_provenance.py tests/test_release_reproducibility.py
git commit -m "feat: resolve bundle flavor before packaging"
```

Expected: package control-plane tests pass and unknown flavor tests leave output roots absent.

### Task 6: Export Only Plan-Selected Locked Python Features

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock` through `uv lock`
- Modify: `scripts/export-dependencies.py`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/test_python_distribution_smoke.py`
- Modify: `tests/fixtures/package/mock-export.py`
- Modify: `tests/test_phase7_dependency_stage.py`

- [ ] **Step 1: Write feature-selection tests**

Add tests for exact uv arguments and manifest fields:

```python
def test_dependency_export_uses_only_plan_selected_features(tmp_path, monkeypatch):
    exporter = _load_script(EXPORT_SCRIPT, "feature_selected_export")
    calls = []
    monkeypatch.setattr(exporter, "find_uv", lambda: "uv")
    monkeypatch.setattr(
        exporter,
        "_run",
        lambda cmd, cwd=None, check=True: calls.append(cmd)
        or subprocess.CompletedProcess(cmd, 0, stdout="fastapi==0.116.1\n", stderr=""),
    )

    deps = exporter.get_all_dependencies(str(ROOT), ("gui", "tui"))

    assert deps == ["fastapi==0.116.1"]
    export_command = calls[0]
    assert export_command.count("--extra") == 2
    assert export_command[export_command.index("--extra") + 1] == "gui"
    assert export_command[export_command.index("--extra", export_command.index("--extra") + 1) + 1] == "tui"
    assert "--no-dev" in export_command
```

Add a negative test that a plan feature other than `gui` or `tui` raises `ValueError("unknown python feature")` before running uv.

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_python_distribution_smoke.py tests/test_phase7_dependency_stage.py
```

Expected: feature arguments and manifest fields are missing.

- [ ] **Step 3: Split product optional dependencies**

Keep all five exact project distributions in base dependencies. Move third-party packages into:

```toml
[project.optional-dependencies]
tui = [
    "prompt-toolkit==3.0.52",
    "rich==14.3.3",
]
gui = [
    "pywebview>=4.0",
    "fastapi>=0.100",
    "uvicorn[standard]>=0.23",
    "websockets>=11.0",
]
```

Keep source-tree GUI/TUI tests available under ordinary `uv sync` by also declaring those six
third-party requirements in the existing `dependency-groups.dev` array. Release export uses
`--no-dev`, so this development declaration cannot leak them into `minimal-cli`.

Run `uv lock`; do not edit `uv.lock` manually.

- [ ] **Step 4: Make export consume the bundle plan**

Add `--bundle-plan` to `export-dependencies.py`. Load it as JSON, require schema version `1`, require the exact `PORTABLE_PROJECT_DISTRIBUTIONS`, read `python_feature_ids`, and verify the supplied SHA-256 if `--bundle-plan-sha256` is present.

Change the uv export command to start with:

```python
command = [
    uv,
    "export",
    "--no-hashes",
    "--format",
    "requirements-txt",
    "--no-emit-workspace",
    "--no-dev",
]
for feature_id in sorted(feature_ids):
    command.extend(("--extra", feature_id))
```

`verify_site_packages()` receives feature IDs. Its critical set always includes the six project packages; it adds prompt-toolkit/rich for `tui` and GUI dependencies for `gui`. The export manifest and JSON report add `flavor_id`, `bundle_plan_sha256`, and `python_feature_ids`.

- [ ] **Step 5: Pass plan arguments from PowerShell and update fixture**

`Invoke-PackageDeps` adds:

```powershell
'--bundle-plan', $Context.bundle_plan_path,
'--bundle-plan-sha256', $Context.bundle_plan_sha256
```

The mock exporter accepts both arguments and echoes the plan's flavor, hash, selected feature IDs, exact six distributions, six wheel names, and six wheel hashes in its report.

- [ ] **Step 6: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_python_distribution_smoke.py tests/test_phase7_dependency_stage.py tests/test_packaging_control_plane.py
git add pyproject.toml uv.lock scripts/export-dependencies.py scripts/package-lib.ps1 tests/test_python_distribution_smoke.py tests/test_phase7_dependency_stage.py tests/fixtures/package/mock-export.py
git commit -m "feat: export plan-selected python features"
```

Expected: minimal export omits TUI/GUI packages; desktop export requires both feature sets; six wheels remain unchanged.

### Task 7: Make Staging And Artifact Assembly Consume Only The Plan

**Files:**

- Modify: `scripts/prepare-offline.ps1`
- Modify: `scripts/build-offline-bundle.ps1`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/fixtures/package/mock-prepare.ps1`
- Modify: `tests/fixtures/package/mock-build.ps1`
- Modify: `tests/test_phase7_bundle_assembly.py`
- Modify: `tests/test_packaging_control_plane.py`

- [ ] **Step 1: Write minimal and desktop staging contract tests**

Add tests that run fixture assembly for both flavors and inspect the emitted manifest. The minimal assertion is:

```python
assert manifest["flavor_id"] == "minimal-cli"
assert manifest["shell_ids"] == ["cli"]
assert manifest["allowed_agent_application_ids"] == ["embedagent.generic"]
assert "gui-command" not in manifest["staged_launcher_ids"]
assert "cpp-smoke" not in manifest["staged_launcher_ids"]
assert "webview2_fixed_runtime_x64" not in manifest["resolved_asset_ids"]
```

The desktop assertion requires CLI/TUI/GUI launchers, both native GUI executables, both smoke launchers, C workspace, WebView2, LLVM, and all current runtime tools.

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_phase7_bundle_assembly.py tests/test_packaging_control_plane.py
```

Expected: prepare/build scripts do not accept `BundlePlanPath` and stage GUI/C++ unconditionally.

- [ ] **Step 3: Add a shared fail-closed plan reader in both PowerShell scripts**

Add `-BundlePlanPath` and `-BundlePlanSha256` parameters. The reader must:

```powershell
if (-not (Test-Path -LiteralPath $BundlePlanPath -PathType Leaf)) {
    throw "Bundle plan not found: $BundlePlanPath"
}
$actualPlanSha256 = (Get-FileHash -LiteralPath $BundlePlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualPlanSha256 -ne $BundlePlanSha256.ToLowerInvariant()) {
    throw "Bundle plan hash mismatch."
}
$bundlePlan = Get-Content -LiteralPath $BundlePlanPath -Raw | ConvertFrom-Json
if ([int]$bundlePlan.schema_version -ne 1) {
    throw "Unsupported bundle plan schema version."
}
```

Require every plan array and exact six `project_distribution_ids`. Reject unrecognized shell, launcher, asset, feature, or gate IDs.

- [ ] **Step 4: Replace unconditional prepare blocks with plan conditions**

Create directories only for selected component paths. Always stage application code, six-wheel site-packages, CLI launcher, config, common documentation, checksums, and plan/Agent manifests.

Use exact conditions:

```powershell
$hasTui = @($bundlePlan.shell_ids) -contains 'tui'
$hasGui = @($bundlePlan.shell_ids) -contains 'gui'
$hasCppGate = @($bundlePlan.gate_ids) -contains 'cpp_smoke_workspace'
$hasGuiGate = @($bundlePlan.gate_ids) -contains 'gui_headless_smoke'
```

Only `$hasGui` ensures GUI frontend assets, checks installed static files, stages WebView2, writes `embedagent-gui.cmd`, and stages native GUI launchers. Only `$hasTui` writes `embedagent-tui.cmd`. Only `$hasCppGate` stages LLVM, `data/workspace-template`, `validate-cpp-smoke.py`, and its launcher. Only `$hasGuiGate` stages GUI smoke files. Generate the runtime `PATH` entries from selected runtime component IDs so minimal CLI never advertises absent LLVM/WebView paths.

Copy the selected `config/bundle-flavors/<config_template_id>.json` to both `config/config.json` and `config/config.json.template`; reject missing templates and reject JSON containing an `api_key` property.

- [ ] **Step 5: Bind plan and Agent manifests into the artifact**

Copy `bundle-plan.json`, `agent.json`, and `agent.lock.json` into `manifests/`. Add to `bundle-manifest.json`:

```powershell
flavor_id = [string]$bundlePlan.flavor_id
bundle_plan_sha256 = $actualPlanSha256
agent_lock_sha256 = [string]$bundlePlan.agent_lock_sha256
allowed_agent_application_ids = @($bundlePlan.allowed_agent_application_ids)
shell_ids = @($bundlePlan.shell_ids)
runtime_component_ids = @($bundlePlan.runtime_component_ids)
resolved_asset_ids = @($bundlePlan.asset_ids)
python_feature_ids = @($bundlePlan.python_feature_ids)
staged_launcher_ids = @($bundlePlan.launcher_ids)
gate_ids = @($bundlePlan.gate_ids)
```

`build-offline-bundle.ps1` verifies these fields against its input plan before copying staging to dist and carries the three plan/Agent files into the sources archive.

- [ ] **Step 6: Pass plan parameters through package orchestration and fixtures**

Add both arguments to prepare/build invocations. Fixture scripts must validate the hash and produce flavor-aware manifests without inventing asset or gate lists.

- [ ] **Step 7: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_phase7_bundle_assembly.py tests/test_packaging_control_plane.py tests/test_package_report_provenance.py
git add scripts/prepare-offline.ps1 scripts/build-offline-bundle.ps1 scripts/package-lib.ps1 tests/fixtures/package/mock-prepare.ps1 tests/fixtures/package/mock-build.ps1 tests/test_phase7_bundle_assembly.py tests/test_packaging_control_plane.py
git commit -m "feat: stage bundles from immutable plans"
```

Expected: fixture assemblies prove minimal exclusions and desktop completeness.

### Task 8: Validate Planned Files, Dependencies, Launchers, And Gates

**Files:**

- Modify: `scripts/check-bundle-dependencies.py`
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/fixtures/package/mock-validate.ps1`
- Modify: `tests/fixtures/package/mock-check.py`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_phase7_bundle_dependency_contract.py`

- [ ] **Step 1: Write negative validator tests**

Add parameterized tests that mutate one valid minimal fixture at a time:

```python
@pytest.mark.parametrize(
    "unexpected_path",
    (
        "embedagent-gui.cmd",
        "runtime/webview2-fixed-runtime/msedgewebview2.exe",
        "bin/llvm/bin/clang.exe",
        "data/workspace-template/main.c",
    ),
)
def test_minimal_bundle_rejects_unplanned_runtime_content(tmp_path, unexpected_path):
    bundle = write_valid_minimal_bundle(tmp_path)
    target = bundle / unexpected_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unexpected", encoding="ascii")

    ok, errors = checker.validate_against_plan(bundle)

    assert not ok
    assert any("unplanned" in item for item in errors)
```

Add plan hash mismatch, missing selected file, missing selected dependency feature, and extra gate tests.

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py tests/test_phase7_bundle_dependency_contract.py
```

Expected: validators still assume the full desktop bundle.

- [ ] **Step 3: Make the Python checker plan-aware**

Load `manifests/bundle-plan.json`, verify it against `bundle-manifest.bundle_plan_sha256`, and change every fixed list to a plan projection:

- critical third-party packages from `python_feature_ids`;
- external tool records from selected `runtime_component_ids` in runtime contract v2;
- launchers from `launcher_ids`;
- static GUI files only when `shell_ids` contains `gui`;
- release assets only from `gate_ids`;
- C workspace only for `cpp_smoke_workspace`.

Add `validate_against_plan(bundle_root)` that rejects known runtime-component stage paths and launcher paths when their IDs are not selected. Continue enforcing product-only `app/embedagent`, exact lower distributions, no editable links, and exact six archived wheels for every flavor.

- [ ] **Step 4: Make the PowerShell validator plan-aware**

Add `-BundlePlanPath` only for development override; by default read `manifests\bundle-plan.json`. Verify hash/schema, select runtime contract components and gates by plan IDs, and invoke dynamic checks only for selected records. Replace fixed GUI/C++ launcher checks and `Test-ReleaseGateAssets` branches with loops over selected launchers and gate records.

Reject an artifact that contains any known unselected runtime stage path. Missing or extra known paths are failures under `-RequireComplete`; they are warnings only for non-strict dev skeleton validation.

- [ ] **Step 5: Derive local gates from `gate_ids`**

In `Invoke-PackageVerify`, replace the fixed GUI and C++ calls with:

```powershell
if (@($Context.bundle_plan.gate_ids) -contains 'gui_headless_smoke') {
    $guiScript = Join-Path $bundleRoot 'tools\validation\validate-gui-smoke.py'
    $guiReport = Join-Path $reportsRoot 'gui-smoke.json'
    if (-not (Invoke-PackageLocalGate -Context $Context -Report $Report -Name 'gui_headless_smoke' -ScriptPath $guiScript -Arguments @('--bundle-root', $bundleRoot, '--require-fixed-webview2') -ReportPath $guiReport)) {
        $localGatesOk = $false
    }
}
if (@($Context.bundle_plan.gate_ids) -contains 'cpp_smoke_workspace') {
    $cppScript = Join-Path $bundleRoot 'tools\validation\validate-cpp-smoke.py'
    $cppReport = Join-Path $reportsRoot 'cpp-smoke.json'
    if (-not (Invoke-PackageLocalGate -Context $Context -Report $Report -Name 'cpp_smoke' -ScriptPath $cppScript -Arguments @('--bundle-root', $bundleRoot, '--json-report', $cppReport) -ReportPath $cppReport)) {
        $localGatesOk = $false
    }
}
```

The implementation body uses the existing `Invoke-PackageLocalGate` calls unchanged; only their selection becomes plan-driven. Pass plan path/hash to validator and checker reports and require each report to echo the same values.

- [ ] **Step 6: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py tests/test_phase7_bundle_dependency_contract.py tests/test_phase7_bundle_assembly.py
git add scripts/check-bundle-dependencies.py scripts/validate-offline-bundle.ps1 scripts/package-lib.ps1 tests/fixtures/package/mock-validate.ps1 tests/fixtures/package/mock-check.py tests/test_packaging_control_plane.py tests/test_phase7_bundle_dependency_contract.py tests/test_phase7_bundle_assembly.py
git commit -m "feat: validate bundles against compiled plans"
```

Expected: minimal accepts no GUI/C++ content and desktop retains all current validators.

### Task 9: Bind Release Identity And Target Evidence To The Plan

**Files:**

- Modify: `scripts/release_identity.py`
- Modify: `scripts/create-release-identity.py`
- Modify: `scripts/validate-release-evidence.py`
- Modify: `scripts/target-report.schema.json`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/test_release_identity.py`
- Modify: `tests/test_release_evidence.py`
- Modify: `tests/test_release_reproducibility.py`

- [ ] **Step 1: Write identity and exact-gate evidence tests**

Add to the identity fixture:

```python
"flavor_id": "minimal-cli",
"target_id": "win7-x64-portable",
"bundle_plan_sha256": "e" * 64,
"agent_lock_sha256": "f" * 64,
"gate_ids": ["runtime_contract", "win7_cli_smoke"],
```

Assert changing any one field produces a comparison mismatch. Add evidence tests proving minimal CLI accepts `runtime_contract` plus a CLI Win7 smoke record without GUI/CPP objects, while desktop rejects missing GUI or C++ gate evidence and both reject extra claimed gate IDs.

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_release_identity.py tests/test_release_evidence.py tests/test_release_reproducibility.py
```

Expected: identity schema and evidence validation do not know the plan.

- [ ] **Step 3: Upgrade release identity to schema version 2**

`build_release_identity()` receives `bundle_plan_path` and loads it. Add exact fields:

```python
"schema_version": 2,
"flavor_id": plan["flavor_id"],
"target_id": plan["target_id"],
"bundle_plan_sha256": sha256_file(bundle_plan_path),
"agent_lock_sha256": plan["agent_lock_sha256"],
"gate_ids": list(plan["gate_ids"]),
```

Make GUI static hash optional: it is `None` when `gui` is absent and required when present. Keep exact six wheel entries for all flavors. `create-release-identity.py` adds required `--bundle-plan` and no longer requires `--gui-static-root`; it accepts that path only when the plan selects GUI.

- [ ] **Step 4: Validate evidence against the exact gate set**

Target reports add:

```json
{
  "bundle_plan_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
  "gate_ids": ["runtime_contract", "win7_cli_smoke"],
  "gate_results": {
    "runtime_contract": {"ok": true},
    "win7_cli_smoke": {"ok": true, "runtime_source": "bundle"}
  }
}
```

The validator requires report plan hash equality and exact equality between identity gate IDs
and report gate IDs. Dispatch gate-specific validation: CLI checks for `win7_cli_smoke`, GUI
and WebView2 checks only for `win7_windowed_gui_smoke`, and C++ checks only for
`cpp_smoke_workspace`. Target acceptance remains disabled until Task 11 supplies and exercises
the bundle-local CLI smoke implementation referenced by the contract.

- [ ] **Step 5: Update orchestration and reproducibility comparison**

Pass the plan to identity creation, copy it beside identity/evidence, and include plan/Agent hashes in stable artifact comparison. A different flavor or plan must make two runs non-equivalent even when wheel hashes match.

- [ ] **Step 6: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_release_identity.py tests/test_release_evidence.py tests/test_release_reproducibility.py
git add scripts/release_identity.py scripts/create-release-identity.py scripts/validate-release-evidence.py scripts/target-report.schema.json scripts/offline-runtime-contract.json scripts/package-lib.ps1 tests/test_release_identity.py tests/test_release_evidence.py tests/test_release_reproducibility.py
git commit -m "feat: bind release evidence to bundle plans"
```

Expected: identity/evidence tests pass for both exact gate sets.

### Task 10: Enforce Application And Shell Restrictions At Runtime

**Files:**

- Create: `src/embedagent/bundle_policy.py`
- Create: `tests/test_bundle_runtime_policy.py`
- Modify: `src/embedagent/product_catalog.py`
- Modify: `src/embedagent/hosted.py`
- Modify: `src/embedagent/cli.py`
- Modify: `src/embedagent/frontend/tui/launcher.py`
- Modify: `src/embedagent/frontend/gui/launcher.py`
- Modify: `tests/test_product_host_composition.py`
- Modify: `tests/test_cli_hosted_entrypoint.py`
- Modify: `tests/test_tui_launcher.py`
- Modify: relevant GUI launcher tests under `tests/`

- [ ] **Step 1: Write runtime policy tests**

Create a temporary bundle marker and manifest, then assert fail-closed restrictions:

```python
def test_bundle_policy_rejects_unplanned_application_and_shell(tmp_path):
    bundle = write_bundle_policy(
        tmp_path,
        applications=("embedagent.generic",),
        shells=("cli",),
    )
    policy = load_bundle_policy(str(bundle))

    assert policy.require_application("embedagent.generic") == "embedagent.generic"
    assert policy.require_shell("cli") == "cli"
    with pytest.raises(ValueError, match="not included in bundle flavor"):
        policy.require_application("embedagent.default_c_cpp")
    with pytest.raises(ValueError, match="not included in bundle flavor"):
        policy.require_shell("gui")
```

Add tests that an absent bundle root returns unrestricted development policy, but a malformed in-bundle manifest raises before runtime/GUI/TUI construction.

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_bundle_runtime_policy.py tests/test_product_host_composition.py tests/test_cli_hosted_entrypoint.py tests/test_tui_launcher.py
```

Expected: runtime policy module is missing.

- [ ] **Step 3: Implement immutable runtime policy loading**

Create:

```python
@dataclass(frozen=True)
class BundleRuntimePolicy:
    bundled: bool
    flavor_id: str = ""
    bundle_plan_sha256: str = ""
    allowed_agent_application_ids: Tuple[str, ...] = field(default_factory=tuple)
    shell_ids: Tuple[str, ...] = field(default_factory=tuple)
```

`load_bundle_policy(bundle_root)` returns `bundled=False` only when no bundle root is discovered.
For an existing bundle it requires `manifests/bundle-plan.json`, recomputes its canonical file
hash, compares `bundle-manifest.bundle_plan_sha256`, requires schema version `1`, and loads
nonempty application/shell tuples. Both enforcement methods use the same exact denial body:

```python
raise ValueError(
    "%s is not included in bundle flavor %s" % (requested_id, self.flavor_id)
)
```

- [ ] **Step 4: Filter the product registry and guard every shell entry**

Change `product_agent_application_registry()` to accept `allowed_application_ids: Optional[Tuple[str, ...]]`. Filter records in the original stable order and set default to the selected plan application; reject an empty result or an unknown allowed ID.

`hosted.resolve_launch_config()` loads policy and validates the resolved application ID. `create_hosted_runtime()` injects the filtered registry. `cli.main()` requires shell `cli` before resolving launch config; the TUI and GUI launch functions require their shell IDs before dependency checks or runtime construction. Both launchers use the same filtered application registry rather than calling an unrestricted registry later.

- [ ] **Step 5: Run green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_bundle_runtime_policy.py tests/test_product_host_composition.py tests/test_cli_hosted_entrypoint.py tests/test_tui_launcher.py tests/test_gui_launcher_app_mode.py tests/test_gui_launcher_exe_contract.py
git add src/embedagent/bundle_policy.py src/embedagent/product_catalog.py src/embedagent/hosted.py src/embedagent/cli.py src/embedagent/frontend/tui/launcher.py src/embedagent/frontend/gui/launcher.py tests/test_bundle_runtime_policy.py tests/test_product_host_composition.py tests/test_cli_hosted_entrypoint.py tests/test_tui_launcher.py tests/test_gui_launcher_app_mode.py tests/test_gui_launcher_exe_contract.py
git commit -m "feat: enforce packaged runtime flavor policy"
```

Expected: source files or wheels being physically present cannot activate an unplanned application or shell.

### Task 11: Add End-To-End Flavor Release Smokes

**Files:**

- Create: `scripts/validate-cli-smoke.py`
- Modify: `scripts/prepare-offline.ps1`
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `scripts/offline-runtime-contract.json`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_release_reproducibility.py`
- Modify: `tests/test_package_report_provenance.py`
- Modify: `tests/fixtures/package/` scripts and config

- [ ] **Step 1: Write the CLI smoke contract test**

Add a release test that constructs a minimal bundle with the controlled provider used by existing hosted runtime tests, runs the bundled Python with `validate-cli-smoke.py`, and asserts the report records:

```python
assert report["ok"] is True
assert report["flavor_id"] == "minimal-cli"
assert report["agent_application_id"] == "embedagent.generic"
assert report["runtime_source"] == "bundle"
assert report["session_created"] is True
assert report["tool_completed"] is True
assert report["permission_interaction_completed"] is True
assert report["user_input_interaction_completed"] is True
assert report["session_restored"] is True
```

- [ ] **Step 2: Run red**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py
```

Expected: CLI smoke script and gate do not exist.

- [ ] **Step 3: Implement bundle-local CLI smoke**

Reuse public product APIs only: `resolve_launch_config`, `create_hosted_runtime`, and hosted session methods. Provide a deterministic fake OpenAI-compatible response fixture without network access. Create one session, execute one read-only tool, complete permission and user-input continuations, close, restore by session ID, and write sorted JSON. Do not import private Core session members or inspect prompt/source/tool payloads in the report.

Use the already registered `win7_cli_smoke` condition:

```json
{"all_of":["shell.cli","assurance.release"]}
```

Stage `validate-cli-smoke.py` and `validate-cli-smoke.cmd` for both release flavors and run it
during release verification. Desktop runs it in addition to existing GUI/C++ gates; target
evidence still contains exactly the plan-selected gate set. Dev plans do not select this
assurance-conditioned gate or its launcher.

- [ ] **Step 4: Add fixture end-to-end assertions**

Run package fixture release for these matrices:

| Profile | Flavor | Expected assurance behavior | Expected content |
|---|---|---|---|
| `dev` | `minimal-cli` | no zip, static checks | minimal |
| `release` | `minimal-cli` | zip, dynamic CLI gate | minimal |
| `dev` | `cpp-desktop` | no zip, static checks | desktop |
| `release` | `cpp-desktop` | zip, CLI/GUI/C++ gates | desktop |

Assert all four reports contain the expected flavor and plan hash and that reproducibility compares only runs with the same flavor.

- [ ] **Step 5: Run release-focused green and commit**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py tests/test_release_reproducibility.py tests/test_package_report_provenance.py
git add scripts/validate-cli-smoke.py scripts/prepare-offline.ps1 scripts/validate-offline-bundle.ps1 scripts/offline-runtime-contract.json tests/test_packaging_control_plane.py tests/test_release_reproducibility.py tests/test_package_report_provenance.py tests/fixtures/package
git commit -m "test: cover minimal and desktop bundle releases"
```

Expected: all four fixture combinations and reproducibility tests pass.

### Task 12: Synchronize Authorities And Run Full Delivery Gates

**Files:**

- Modify: `docs/product/composition.md`
- Modify: `docs/product/packaging-and-deployment.md`
- Modify: `docs/guides/configuration-guide.md`
- Modify: `docs/guides/win7-release-runbook.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/superpowers/README.md`
- Move on closure: design and this plan into an indexed `docs/archive/configurable-agent-bundles/` package

- [ ] **Step 1: Update durable product composition truth**

Document official recipe ownership, `minimal-cli` and `cpp-desktop`, shell/application runtime restrictions, production component catalog, and the fact that arbitrary product definitions remain private.

- [ ] **Step 2: Update packaging and release truth**

Replace fixed full-bundle language with flavor-aware rules while preserving the exact six-wheel invariant. Document:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor -Flavor minimal-cli
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Flavor minimal-cli
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Flavor cpp-desktop
```

State that omitted flavor remains `cpp-desktop`; Profile controls assurance only; plan-selected gates cannot be disabled.

- [ ] **Step 3: Update configuration and Win7 evidence guides**

List allowed runtime application IDs per flavor. Explain that minimal target acceptance requires CLI smoke and no GUI/C++ evidence, while desktop still requires WebView2 109 and bundle-local C smoke. Remove any statement that every bundle necessarily contains GUI, LLVM, or C workspace assets.

- [ ] **Step 4: Replace status and roadmap state**

Record implementation evidence in place. Keep clean-machine Windows 7 evidence pending separately for each official release flavor until the matching plan-bound target report is accepted. Add new code paths to the existing Product composition and Packaging/delivery rows in the code-doc matrix; do not create a second ownership row.

- [ ] **Step 5: Run architecture, full, release, lint, and six-wheel gates**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py release
uv run --locked python scripts/lint.py
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: every command exits `0`; the distribution checker and smoke report exactly six distributions.

- [ ] **Step 6: Run both packaging doctors and available release gates**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor -Profile release -Flavor minimal-cli -Json
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor -Profile release -Flavor cpp-desktop -Json
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Flavor minimal-cli -Json
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Flavor cpp-desktop -Json
```

Expected: both reports carry distinct plan hashes, exact six wheels, and only their applicable gates. Do not claim clean-machine Windows 7 acceptance from these local runs.

- [ ] **Step 7: Archive the closed slice and commit**

Create `docs/archive/configurable-agent-bundles/README.md` indexing the approved design and implementation plan, move both files from `docs/superpowers/`, and remove their active index entries only after every repository acceptance condition above passes.

```powershell
git add docs
git commit -m "docs: document configurable bundle flavors"
```

Do not stage `README.md` or `AGENTS.md` unless implementation changed their routed commands or
constitutional constraints. Inspect `git diff --cached --name-status`; if those two files were
staged without an intended documentation change, run
`git restore --staged README.md AGENTS.md` without modifying their working-tree content.

## Final Acceptance Checklist

- `-Profile` changes assurance only; `-Flavor` changes product contents only.
- Omitted flavor resolves to `cpp-desktop`.
- Unknown flavor, target, component, requirement, provider, asset, feature, launcher, gate, schema, or plan hash fails before output mutation.
- Both flavors build, check, wheel-only install, and archive exactly six project distributions.
- `minimal-cli` excludes GUI/TUI dependencies, GUI/WebView2, LLVM/C++ workspace, and corresponding launchers/gates.
- `cpp-desktop` retains the current full C/C++ desktop behavior.
- No package configuration or recipe enumerates asset paths, wheel names, or release gates.
- Dependency export, staging, validation, release identity, evidence, and runtime bootstrap agree on one plan hash.
- Runtime application and shell overrides outside the plan fail even though all six wheels are present.
- Configuration templates contain no API key or credential field.
- Local repository evidence does not claim Windows 7 target acceptance.
