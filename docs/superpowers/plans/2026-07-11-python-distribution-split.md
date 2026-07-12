# Python Distribution Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and install Core, Protocol, Host, Composition, and product as separate Python distributions without breaking root development commands or the hosted application.

**Architecture:** Convert the repository into a uv workspace while keeping the root `embedagent` project as the product aggregator. Move package sources to distribution-owned `packages/*/src` trees and move concrete runtime modules from the product namespace into Host so no wheel depends back on the product.

**Tech Stack:** Python 3.8, uv workspace sources, setuptools PEP 621 metadata, wheel ZIP inspection, isolated venv smoke tests, existing offline packaging scripts.

**Status:** Complete. The five distributions build independently, pass archive
and inter-distribution dependency checks, pass Python 3.8 isolated import smoke
across all five distributions, and install those project distributions
wheel-only. Locked third-party dependencies remain a separate controlled
build-time step and may build sdists. The smoke is not a full GUI/provider
runtime test. Clean Win7/WebView2 target-bundle smoke remains a product release
gate, not a completion condition for this split.

---

## Target Workspace

```text
pyproject.toml                         product aggregator and GUI dependencies
src/embedagent/                       product CLI/TUI/GUI and product bootstrap
packages/embedagent-core/
  pyproject.toml
  src/embedagent_core/
packages/embedagent-protocol/
  pyproject.toml
  src/embedagent_protocol/
packages/embedagent-host/
  pyproject.toml
  src/embedagent_host/
packages/embedagent-composition/
  pyproject.toml
  src/embedagent_composition/
```

The C/C++ workflow distribution is created in Plan 3. During this plan its
source remains under the product package and the product registry remains the
default composition path.

### Task 1: Add Distribution Inspection And Isolated Import Tests

**Files:**
- Create: `scripts/check-python-distributions.py`
- Create: `tests/test_python_distribution_contract.py`
- Modify: `tests/test_core_package_imports.py`

- [x] **Step 1: Write the target metadata tests**

Create `tests/test_python_distribution_contract.py`:

```python
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _project(path):
    with path.open("rb") as handle:
        return tomllib.load(handle)["project"]


def test_workspace_distribution_names_are_unique():
    paths = (
        ROOT / "packages/embedagent-core/pyproject.toml",
        ROOT / "packages/embedagent-protocol/pyproject.toml",
        ROOT / "packages/embedagent-host/pyproject.toml",
        ROOT / "packages/embedagent-composition/pyproject.toml",
        ROOT / "pyproject.toml",
    )
    names = [_project(path)["name"] for path in paths]
    assert names == [
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-composition",
        "embedagent",
    ]
    assert len(set(names)) == len(names)


def test_core_distribution_has_no_runtime_dependencies():
    project = _project(ROOT / "packages/embedagent-core/pyproject.toml")
    assert project.get("dependencies", []) == []


def test_protocol_distribution_has_no_runtime_dependencies():
    project = _project(ROOT / "packages/embedagent-protocol/pyproject.toml")
    assert project.get("dependencies", []) == []


def test_composition_distribution_has_no_runtime_dependencies():
    project = _project(ROOT / "packages/embedagent-composition/pyproject.toml")
    assert project.get("dependencies", []) == []


def test_host_depends_only_on_core_and_protocol():
    project = _project(ROOT / "packages/embedagent-host/pyproject.toml")
    assert project.get("dependencies", []) == [
        "embedagent-core==0.1.0",
        "embedagent-protocol==0.1.0",
    ]
```

Python 3.8 does not provide `tomllib`; add `tomli` only to the development
dependency group if these tests run under 3.8, and import it as:

```python
try:
    import tomllib
except ImportError:
    import tomli as tomllib
```

Do not add `tomli` to any runtime distribution.

- [x] **Step 2: Add the wheel inspection script**

Create `scripts/check-python-distributions.py`. It must open wheel files with
`zipfile`, parse `*.dist-info/METADATA`, and enforce this table:

```python
EXPECTED = {
    "embedagent-core": {
        "required_prefixes": ("embedagent_core/",),
        "forbidden_prefixes": ("embedagent_host/", "embedagent_protocol/", "embedagent/"),
        "forbidden_requires": ("fastapi", "pywebview", "uvicorn", "websockets"),
    },
    "embedagent-protocol": {
        "required_prefixes": ("embedagent_protocol/",),
        "forbidden_prefixes": ("embedagent_core/", "embedagent_host/", "embedagent/"),
        "forbidden_requires": (),
    },
    "embedagent-host": {
        "required_prefixes": ("embedagent_host/",),
        "forbidden_prefixes": ("embedagent/frontend/", "embedagent/workflow_packages/"),
        "forbidden_requires": ("pywebview",),
    },
    "embedagent-composition": {
        "required_prefixes": ("embedagent_composition/",),
        "forbidden_prefixes": (
            "embedagent_core/",
            "embedagent_host/",
            "embedagent_protocol/",
            "embedagent/",
        ),
        "forbidden_requires": (),
    },
}
```

The script accepts `--dist-dir`, reports JSON to stdout, and exits non-zero for
missing wheels, missing prefixes, forbidden files, or forbidden dependencies.

- [x] **Step 3: Run the tests and verify the target is red**

```bash
uv run pytest tests/test_python_distribution_contract.py -v
```

Expected: FAIL because package pyprojects do not exist.

- [x] **Step 4: Commit the red packaging contracts**

```bash
git add scripts/check-python-distributions.py tests/test_python_distribution_contract.py tests/test_core_package_imports.py
git commit -m "test: define python distribution boundaries"
```

### Task 2: Create The uv Workspace And Empty Distribution Metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` through `uv lock` only
- Create: `packages/embedagent-core/pyproject.toml`
- Create: `packages/embedagent-protocol/pyproject.toml`
- Create: `packages/embedagent-host/pyproject.toml`
- Create: `packages/embedagent-composition/pyproject.toml`
- Create: `packages/embedagent-composition/src/embedagent_composition/__init__.py`

- [x] **Step 1: Add workspace members and local sources**

Keep the root project named `embedagent`. Add:

```toml
[tool.uv.workspace]
members = [
    "packages/embedagent-core",
    "packages/embedagent-protocol",
    "packages/embedagent-host",
    "packages/embedagent-composition",
]

[tool.uv.sources]
embedagent-core = { workspace = true }
embedagent-protocol = { workspace = true }
embedagent-host = { workspace = true }
embedagent-composition = { workspace = true }
```

Add exact local package dependencies to the root project. Keep GUI dependencies
only in the root product.

- [x] **Step 2: Create package pyprojects**

Each package uses `setuptools.build_meta`, Python `>=3.8,<3.9`, its local `src`
directory, and explicit include patterns. Example Core metadata:

```toml
[build-system]
requires = ["setuptools>=65"]
build-backend = "setuptools.build_meta"

[project]
name = "embedagent-core"
version = "0.1.0"
requires-python = ">=3.8,<3.9"
dependencies = []

[tool.setuptools.package-dir]
"" = "src"

[tool.setuptools.packages.find]
where = ["src"]
include = ["embedagent_core*"]
```

Protocol and Composition use no runtime dependencies. Host depends only on
exact matching `embedagent-core==0.1.0` and
`embedagent-protocol==0.1.0`. The root product imports Composition and registers
trusted Core/Host factories; the generic compiler never imports those packages.

- [x] **Step 3: Regenerate the lock through uv**

```bash
uv lock
uv sync
```

Expected: both commands exit zero. Do not edit `uv.lock` manually.

- [x] **Step 4: Run metadata tests**

```bash
uv run pytest tests/test_python_distribution_contract.py -v
```

Expected: metadata tests pass; wheel-content checks are deferred until sources
move.

- [x] **Step 5: Commit workspace metadata**

```bash
git add pyproject.toml uv.lock packages tests/test_python_distribution_contract.py
git commit -m "build: create agent package workspace"
```

### Task 3: Move Core And Protocol Sources

**Files:**
- Move: `src/embedagent_core/` to `packages/embedagent-core/src/embedagent_core/`
- Move: `src/embedagent/protocol/` to `packages/embedagent-protocol/src/embedagent_protocol/`
- Modify: protocol imports throughout `src/`, `packages/`, and `tests/`
- Modify: `pyproject.toml`
- Test: `tests/test_core_package_imports.py`
- Test: `tests/test_agent_app_protocol.py`

- [x] **Step 1: Move Core with history**

```bash
New-Item -ItemType Directory -Force packages/embedagent-core/src | Out-Null
git mv src/embedagent_core packages/embedagent-core/src/embedagent_core
```

Do not create a compatibility package at `src/embedagent_core`.

- [x] **Step 2: Move and rename Protocol**

```bash
New-Item -ItemType Directory -Force packages/embedagent-protocol/src | Out-Null
git mv src/embedagent/protocol packages/embedagent-protocol/src/embedagent_protocol
```

Replace imports of `embedagent.protocol` with `embedagent_protocol`. Remove the
Protocol dependency on `embedagent_core.permissions.PermissionContextView` by
defining a JSON-safe `PermissionContext` DTO in `embedagent_protocol` and
mapping the runtime view in Host.

- [x] **Step 3: Update tests and architecture scanners to workspace roots**

Change hard-coded roots from `src/embedagent_core` to
`packages/embedagent-core/src/embedagent_core`, and from
`src/embedagent/protocol` to
`packages/embedagent-protocol/src/embedagent_protocol`.

Add this import poison check to `tests/test_core_package_imports.py`:

```python
def test_importing_public_core_does_not_load_other_distributions(self):
    script = (
        "import sys\n"
        "from embedagent_core import Agent\n"
        "blocked = ('embedagent_host', 'embedagent_protocol', 'embedagent')\n"
        "raise SystemExit(1 if any(name == item or name.startswith(item + '.') "
        "for name in sys.modules for item in blocked) else 0)\n"
    )
    result = subprocess.run([sys.executable, "-c", script])
    assert result.returncode == 0
```

- [x] **Step 4: Remove Core and Host from the root package finder**

Root package discovery must include only `embedagent*`; the workspace package
pyprojects own `embedagent_core*`, `embedagent_protocol*`, and later
`embedagent_host*`.

- [x] **Step 5: Run Core and Protocol tests**

```bash
uv sync
uv run pytest tests/test_core_package_imports.py tests/test_agent_core_public_api.py tests/test_agent_app_protocol.py tests/test_gui_protocol_projection.py -v
```

Expected: PASS.

- [x] **Step 6: Commit Core and Protocol moves**

```bash
git add packages/embedagent-core packages/embedagent-protocol src tests pyproject.toml uv.lock
git commit -m "refactor: move core and protocol into workspace packages"
```

### Task 4: Move Host-Owned Runtime Modules

**Files:**
- Move: `src/embedagent_host/` to `packages/embedagent-host/src/embedagent_host/`
- Move into `packages/embedagent-host/src/embedagent_host/runtime/`:
  - `src/embedagent/agent_applications.py`
  - `src/embedagent/agent_profile_runtime.py`
  - `src/embedagent/context.py`
  - `src/embedagent/local_resources.py`
  - `src/embedagent/memory_maintenance.py`
  - `src/embedagent/plan_store.py`
  - `src/embedagent/project_extensions.py`
  - `src/embedagent/project_memory.py`
  - `src/embedagent/prompts.py`
  - `src/embedagent/review_command.py`
  - `src/embedagent/self_extension_authoring.py`
  - `src/embedagent/session_bootstrap_service.py`
  - `src/embedagent/session_history.py`
  - `src/embedagent/session_projector.py`
  - `src/embedagent/session_runtime.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/skill_index.py`
  - `src/embedagent/skills.py`
  - `src/embedagent/slash_command_service.py`
  - `src/embedagent/slash_commands.py`
  - `src/embedagent/tool_commit.py`
  - `src/embedagent/tool_evidence.py`
  - `src/embedagent/tool_result_store.py`
  - `src/embedagent/transcript_store.py`
  - `src/embedagent/workspace_intelligence.py`
  - `src/embedagent/workspace_profile.py`
  - `src/embedagent/workspace_recipes.py`
- Move directories:
  - `src/embedagent/services/`
  - `src/embedagent/tools/`
- Modify all imports and tests that reference moved modules.

- [x] **Step 1: Move the existing Host package**

```bash
New-Item -ItemType Directory -Force packages/embedagent-host/src | Out-Null
git mv src/embedagent_host packages/embedagent-host/src/embedagent_host
New-Item -ItemType Directory -Force packages/embedagent-host/src/embedagent_host/runtime | Out-Null
```

- [x] **Step 2: Move the listed concrete runtime modules**

Use `git mv` for every file and directory listed above. Preserve file history.
Rename imports to `embedagent_host.runtime.<module>` and
`embedagent_host.runtime.tools` / `embedagent_host.runtime.services`.

Do not move these product-owned areas:

```text
src/embedagent/cli.py
src/embedagent/frontend/
src/embedagent/frontends/
src/embedagent/core/
src/embedagent/workflow_packages/
src/embedagent/config.py
src/embedagent/runtime_discovery.py
src/embedagent/command_sanitizer.py
```

Product composition may inject config and runtime-discovery adapters into Host;
Host must not import the product package to obtain them.

- [x] **Step 3: Add a Host import-boundary test**

Create `tests/test_host_distribution_imports.py`:

```python
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_host_does_not_import_product_or_workflow_packages():
    offenders = []
    root = ROOT / "packages/embedagent-host/src/embedagent_host"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            if module == "embedagent" or module.startswith("embedagent."):
                offenders.append((str(path.relative_to(ROOT)), module))
            if "workflow" in module and "c_cpp" in module:
                offenders.append((str(path.relative_to(ROOT)), module))
    assert offenders == []
```

- [x] **Step 4: Run Host and product integration tests**

```bash
uv sync
uv run pytest tests/test_host_distribution_imports.py tests/test_host_package_composition.py tests/test_inprocess_adapter_frontend_api.py tests/test_hosted_interaction_service.py -v
```

Expected: PASS.

- [x] **Step 5: Commit Host ownership moves**

```bash
git add packages/embedagent-host src tests pyproject.toml uv.lock
git commit -m "refactor: move hosted runtime into host distribution"
```

### Task 5: Build Wheels And Run Isolated Installation Smoke

**Files:**
- Modify: `scripts/check-python-distributions.py`
- Create: `scripts/smoke-python-distributions.py`
- Modify: `Makefile`
- Modify: packaging scripts that copy project Python sources
- Test: `tests/test_python_distribution_contract.py`

- [x] **Step 1: Build all workspace wheels**

```bash
uv build --all-packages
```

Expected: creates wheels for Core, Protocol, Host, Composition, and product.

- [x] **Step 2: Run wheel content inspection**

```bash
uv run python scripts/check-python-distributions.py --dist-dir dist
```

Expected: JSON reports `ok: true` for every expected wheel.

- [x] **Step 3: Add isolated import smoke**

Create `scripts/smoke-python-distributions.py` to:

1. create temporary Python 3.8 virtual environments;
2. install wheels with `pip --no-index --find-links dist`;
3. run `from embedagent_core import Agent` in the Core-only environment;
4. run `import embedagent_protocol` in the Protocol-only environment;
5. install Core + Protocol + Host and run `import embedagent_host`;
6. install all five exact checked wheels, import the product and split packages,
   and prove the product module resolves from the temporary venv;
7. print one stable JSON report and return non-zero on any failure.

The script must accept `--python` so CI and Win7 preflight can pass the exact
Python 3.8 executable.

- [x] **Step 4: Run isolated smoke**

```bash
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: report contains `core_only: ok`, `protocol_only: ok`, and
`host_stack: ok`.

- [x] **Step 5: Update bundle source staging**

Update `scripts/prepare-offline.ps1`, `scripts/build-offline-bundle.ps1`, and
shared package helpers to copy installed workspace wheels/site-packages rather
than assuming all Python packages live below root `src/`. Keep GUI static asset
paths unchanged in this plan.

- [x] **Step 6: Add the distribution gate to local CI**

Add wheel build, inspection, and isolated import smoke to `make ci` after unit
tests and before offline bundle validation.

- [x] **Step 7: Commit packaging verification**

```bash
git add scripts Makefile tests/test_python_distribution_contract.py
git commit -m "build: verify isolated agent distributions"
```

### Task 6: Close Plan 2 Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/modules/packaging-and-deployment.md`
- Modify: `docs/adrs/0001-offline-portable-bundle-baseline.md`

- [x] **Step 1: Update package ownership documentation**

Record the new workspace paths, distribution dependencies, exact build
commands, and the rule that product code must not be imported by Core or Host.
Update AGENTS quick commands only if the commands actually changed; preserve
`uv sync`, pytest, lint, and GUI gates.

- [x] **Step 2: Run complete Plan 2 verification**

```bash
uv sync
uv run pytest tests/test_python_distribution_contract.py tests/test_core_package_imports.py tests/test_host_distribution_imports.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
uv build --all-packages
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: all commands exit zero.

- [x] **Step 3: Run GUI regression gate**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
```

Expected: PASS and generated static assets are committed if changed.

- [x] **Step 4: Commit Plan 2 closeout**

```bash
git add README.md AGENTS.md docs src/embedagent/frontend/gui/static
git commit -m "docs: document independent python distributions"
```
