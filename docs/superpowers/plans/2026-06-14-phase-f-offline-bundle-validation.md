# Phase F Offline Bundle Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make offline bundle validation prove the runtime-invoked tool boundary introduced by the Pi-inspired minimal Core work.

**Architecture:** Add a small packaging-owned runtime contract JSON and make both bundle validators consume it. Keep `ToolContext` as runtime execution truth, and add guard tests that detect drift between the JSON contract and managed-tool classification.

**Tech Stack:** Python 3.8, PowerShell 5-compatible scripts, pytest/unittest, JSON contracts, existing packaging control plane.

---

## File Structure

- Create: `scripts/offline-runtime-contract.json`
  - Machine-readable bundle contract for runtime-invoked tools. It is not an asset download manifest.
- Modify: `scripts/validate-offline-bundle.ps1`
  - Load the runtime contract, validate static paths/alternatives/children, and run contract dynamic checks.
- Modify: `scripts/check-bundle-dependencies.py`
  - Load the same contract and use it for external runtime tool checks.
- Modify: `tests/test_packaging_control_plane.py`
  - Add contract schema tests and validator behavior tests.
- Modify: `tests/test_tools_package.py`
  - Add drift tests between `ToolContext` managed-tool classification and the contract.
- Modify: `tests/test_project_extensions.py`
  - Add dependency-install guard for project-local extension loading.
- Modify: `tests/test_self_extension_authoring.py`
  - Add generated extension validation recipe assertions.
- Modify docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/agent-harness-v2.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/guides/win7-preflight-checklist.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- Move after closure:
  - `docs/superpowers/specs/2026-06-14-phase-f-offline-bundle-validation-design.md`
  - `docs/superpowers/plans/2026-06-14-phase-f-offline-bundle-validation.md`

---

### Task 1: Runtime Contract

**Files:**
- Create: `scripts/offline-runtime-contract.json`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_tools_package.py`

- [ ] **Step 1: Write failing contract schema tests**

Add tests to `tests/test_packaging_control_plane.py`:

```python
RUNTIME_CONTRACT = ROOT / "scripts" / "offline-runtime-contract.json"


class TestRuntimeBundleContract(unittest.TestCase):
    def test_runtime_contract_lists_managed_tools(self):
        payload = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        tool_ids = [item["id"] for item in payload["required_tools"]]
        self.assertEqual(tool_ids, ["python", "git", "rg", "ctags", "llvm"])
        for item in payload["required_tools"]:
            self.assertTrue(item["component"])
            self.assertTrue(item["category"])
            self.assertTrue(item.get("paths") or item.get("alternatives"))

    def test_runtime_contract_lists_current_llvm_children(self):
        payload = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
        llvm = [item for item in payload["required_tools"] if item["id"] == "llvm"][0]
        child_paths = [child["path"] for child in llvm["children"]]
        self.assertEqual(
            child_paths,
            [
                "bin/llvm/bin/clang.exe",
                "bin/llvm/bin/clang++.exe",
                "bin/llvm/bin/clang-cl.exe",
                "bin/llvm/bin/clang-tidy.exe",
                "bin/llvm/bin/clang-analyzer.bat",
                "bin/llvm/bin/llvm-profdata.exe",
                "bin/llvm/bin/llvm-cov.exe",
            ],
        )
```

Add tests to `tests/test_tools_package.py`:

```python
class TestRuntimeContractAlignment(unittest.TestCase):
    def test_runtime_contract_matches_managed_tool_keys(self):
        contract_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "scripts",
            "offline-runtime-contract.json",
        )
        with open(contract_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        from embedagent.tools._base import MANAGED_RUNTIME_TOOL_KEYS

        self.assertEqual(
            [item["id"] for item in payload["required_tools"]],
            list(MANAGED_RUNTIME_TOOL_KEYS),
        )

    def test_runtime_contract_commands_are_classified_as_managed(self):
        contract_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "scripts",
            "offline-runtime-contract.json",
        )
        with open(contract_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        ctx = ToolContext(self.workspace)

        names = []
        for item in payload["required_tools"]:
            names.extend(item.get("command_names") or [])
            for child in item.get("children") or []:
                names.extend(child.get("command_names") or [])

        classified = {name: ctx.classify_managed_command(name) for name in names}
        self.assertEqual(classified["python"], "python")
        self.assertEqual(classified["git"], "git")
        self.assertEqual(classified["rg"], "rg")
        self.assertEqual(classified["ctags"], "ctags")
        self.assertEqual(classified["clang"], "llvm")
        self.assertEqual(classified["clang++"], "llvm")
        self.assertEqual(classified["clang-cl"], "llvm")
        self.assertEqual(classified["clang-tidy"], "llvm")
        self.assertEqual(classified["clang-analyzer"], "llvm")
        self.assertEqual(classified["llvm-profdata"], "llvm")
        self.assertEqual(classified["llvm-cov"], "llvm")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestRuntimeBundleContract tests/test_tools_package.py::TestRuntimeContractAlignment -q
```

Expected: failure because `scripts/offline-runtime-contract.json` does not exist.

- [ ] **Step 3: Add the runtime contract JSON**

Create `scripts/offline-runtime-contract.json`:

```json
{
  "schema_version": 1,
  "description": "Runtime-invoked tools that must be present in the offline portable bundle.",
  "required_tools": [
    {
      "id": "python",
      "component": "python_runtime",
      "category": "runtime",
      "paths": [
        "runtime/python/python.exe"
      ],
      "command_names": [
        "python",
        "python.exe"
      ],
      "dynamic_check": [
        "--version"
      ],
      "notes": "Used by launchers and generated local validation recipes."
    },
    {
      "id": "git",
      "component": "mingit_portable",
      "category": "vcs",
      "alternatives": [
        {
          "paths": [
            "bin/git/cmd/git.exe"
          ]
        },
        {
          "paths": [
            "bin/git/bin/git.exe"
          ]
        },
        {
          "paths": [
            "bin/git/git.exe"
          ]
        }
      ],
      "command_names": [
        "git",
        "git.exe"
      ],
      "dynamic_check": [
        "--version"
      ],
      "notes": "Used by built-in git tools and workspace intelligence."
    },
    {
      "id": "rg",
      "component": "ripgrep",
      "category": "search",
      "paths": [
        "bin/rg/rg.exe"
      ],
      "command_names": [
        "rg",
        "rg.exe"
      ],
      "dynamic_check": [
        "--version"
      ],
      "notes": "Used by search and discovery workflows."
    },
    {
      "id": "ctags",
      "component": "universal_ctags",
      "category": "symbols",
      "paths": [
        "bin/ctags/ctags.exe"
      ],
      "command_names": [
        "ctags",
        "ctags.exe"
      ],
      "dynamic_check": [
        "--version"
      ],
      "notes": "Used by symbol intelligence."
    },
    {
      "id": "llvm",
      "component": "llvm_clang_bundle",
      "category": "toolchain",
      "paths": [
        "bin/llvm/bin"
      ],
      "command_names": [],
      "children": [
        {
          "id": "clang",
          "path": "bin/llvm/bin/clang.exe",
          "command_names": ["clang", "clang.exe"],
          "dynamic_check": ["--version"]
        },
        {
          "id": "clangxx",
          "path": "bin/llvm/bin/clang++.exe",
          "command_names": ["clang++", "clang++.exe"],
          "dynamic_check": ["--version"]
        },
        {
          "id": "clang_cl",
          "path": "bin/llvm/bin/clang-cl.exe",
          "command_names": ["clang-cl", "clang-cl.exe"],
          "dynamic_check": ["--version"]
        },
        {
          "id": "clang_tidy",
          "path": "bin/llvm/bin/clang-tidy.exe",
          "command_names": ["clang-tidy", "clang-tidy.exe"],
          "dynamic_check": ["--version"]
        },
        {
          "id": "clang_analyzer",
          "path": "bin/llvm/bin/clang-analyzer.bat",
          "command_names": ["clang-analyzer", "clang-analyzer.bat"]
        },
        {
          "id": "llvm_profdata",
          "path": "bin/llvm/bin/llvm-profdata.exe",
          "command_names": ["llvm-profdata", "llvm-profdata.exe"],
          "dynamic_check": ["--version"]
        },
        {
          "id": "llvm_cov",
          "path": "bin/llvm/bin/llvm-cov.exe",
          "command_names": ["llvm-cov", "llvm-cov.exe"],
          "dynamic_check": ["--version"]
        }
      ],
      "notes": "Used by C/C++ build, static analysis, and coverage workflows."
    }
  ]
}
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestRuntimeBundleContract tests/test_tools_package.py::TestRuntimeContractAlignment -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/offline-runtime-contract.json tests/test_packaging_control_plane.py tests/test_tools_package.py
git commit -m "test: define offline runtime tool contract"
```

---

### Task 2: PowerShell Bundle Validator Contract Checks

**Files:**
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `tests/test_packaging_control_plane.py`

- [ ] **Step 1: Write failing PowerShell validator tests**

Add tests to `TestStageJsonReports` in `tests/test_packaging_control_plane.py`:

```python
    def test_validate_offline_bundle_fails_strict_for_missing_runtime_contract_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            sources_root = Path(tmp) / "sources"
            (bundle_root / "app" / "embedagent").mkdir(parents=True)
            (bundle_root / "runtime" / "python").mkdir(parents=True)
            (bundle_root / "bin" / "llvm" / "bin").mkdir(parents=True)
            sources_root.mkdir()
            json_path = Path(tmp) / "validate-report.json"
            result = subprocess.run(
                [
                    _powershell_exe(),
                    "-NoProfile",
                    "-File",
                    str(VALIDATE_SCRIPT),
                    "-BundleRoot",
                    str(bundle_root),
                    "-SourcesRoot",
                    str(sources_root),
                    "-ZipPath",
                    str(Path(tmp) / "bundle.zip"),
                    "-SkipDynamicChecks",
                    "-RequireComplete",
                    "-JsonOutputPath",
                    str(json_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("runtime_tool.git", result_codes)
            self.assertIn("runtime_tool.llvm.clang", result_codes)

    def test_validate_offline_bundle_passes_static_runtime_contract_for_mock_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            sources_root = Path(tmp) / "sources"
            for path in [
                "app/embedagent/__init__.py",
                "runtime/python/python.exe",
                "bin/git/cmd/git.exe",
                "bin/rg/rg.exe",
                "bin/ctags/ctags.exe",
                "bin/llvm/bin/clang.exe",
                "bin/llvm/bin/clang++.exe",
                "bin/llvm/bin/clang-cl.exe",
                "bin/llvm/bin/clang-tidy.exe",
                "bin/llvm/bin/clang-analyzer.bat",
                "bin/llvm/bin/llvm-profdata.exe",
                "bin/llvm/bin/llvm-cov.exe",
            ]:
                target = bundle_root / Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("stub", encoding="ascii")
            sources_root.mkdir()
            json_path = Path(tmp) / "validate-report.json"
            result = subprocess.run(
                [
                    _powershell_exe(),
                    "-NoProfile",
                    "-File",
                    str(VALIDATE_SCRIPT),
                    "-BundleRoot",
                    str(bundle_root),
                    "-SourcesRoot",
                    str(sources_root),
                    "-ZipPath",
                    str(Path(tmp) / "bundle.zip"),
                    "-SkipDynamicChecks",
                    "-JsonOutputPath",
                    str(json_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("runtime_tool.python", result_codes)
            self.assertIn("runtime_tool.git", result_codes)
            self.assertIn("runtime_tool.llvm.clang_tidy", result_codes)
            self.assertEqual(payload["runtime_contract"]["schema_version"], 1)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestStageJsonReports::test_validate_offline_bundle_fails_strict_for_missing_runtime_contract_tool tests/test_packaging_control_plane.py::TestStageJsonReports::test_validate_offline_bundle_passes_static_runtime_contract_for_mock_bundle -q
```

Expected: failure because `validate-offline-bundle.ps1` does not emit the new contract result codes.

- [ ] **Step 3: Implement contract loading and static checks**

In `scripts/validate-offline-bundle.ps1`:

- add parameter:

```powershell
[string]$RuntimeContractPath = ""
```

- resolve default after `$projectRoot`:

```powershell
if (-not $RuntimeContractPath) {
    $RuntimeContractPath = Join-Path $projectRoot 'scripts\offline-runtime-contract.json'
}
```

- add helpers:

```powershell
function Read-RuntimeContract {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Runtime contract not found: $Path"
    }
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Test-ContractPathSet {
    param(
        [string]$BundleRoot,
        [object[]]$RelativePaths
    )
    foreach ($relative in @($RelativePaths)) {
        $candidate = Join-Path $BundleRoot ([string]$relative).Replace('/', '\')
        if (-not (Test-Path -LiteralPath $candidate)) {
            return $false
        }
    }
    return $true
}

function Test-ContractAlternatives {
    param(
        [string]$BundleRoot,
        [object[]]$Alternatives
    )
    foreach ($alternative in @($Alternatives)) {
        if (Test-ContractPathSet -BundleRoot $BundleRoot -RelativePaths @($alternative.paths)) {
            return $true
        }
    }
    return $false
}

function Test-RuntimeContract {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [object]$Contract
    )
    foreach ($tool in @($Contract.required_tools)) {
        $toolId = [string]$tool.id
        $present = $false
        if ($tool.PSObject.Properties.Name -contains 'alternatives') {
            $present = Test-ContractAlternatives -BundleRoot $BundleRoot -Alternatives @($tool.alternatives)
        }
        else {
            $present = Test-ContractPathSet -BundleRoot $BundleRoot -RelativePaths @($tool.paths)
        }
        $level = if ($present) { 'pass' } elseif ($RequireComplete) { 'fail' } else { 'warn' }
        $message = if ($present) { "Runtime tool present: $toolId" } else { "Runtime tool missing: $toolId" }
        Add-Result -Results $Results -Level $level -Code ('runtime_tool.' + $toolId) -Message $message

        foreach ($child in @($tool.children)) {
            $childPath = Join-Path $BundleRoot ([string]$child.path).Replace('/', '\')
            $childPresent = Test-Path -LiteralPath $childPath
            $childLevel = if ($childPresent) { 'pass' } elseif ($RequireComplete) { 'fail' } else { 'warn' }
            $childMessage = if ($childPresent) { "Runtime tool child present: $toolId/$($child.id)" } else { "Runtime tool child missing: $toolId/$($child.id) at $($child.path)" }
            Add-Result -Results $Results -Level $childLevel -Code ('runtime_tool.' + $toolId + '.' + [string]$child.id) -Message $childMessage
        }
    }
}
```

- call after static bundle path setup:

```powershell
$runtimeContract = Read-RuntimeContract -Path $RuntimeContractPath
Test-RuntimeContract -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract
```

- add to report payload:

```powershell
runtime_contract = [ordered]@{
    path = $RuntimeContractPath
    schema_version = $runtimeContract.schema_version
}
```

- include `llvm_clang_bundle` in `$completeGateComponents`.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestStageJsonReports::test_validate_offline_bundle_fails_strict_for_missing_runtime_contract_tool tests/test_packaging_control_plane.py::TestStageJsonReports::test_validate_offline_bundle_passes_static_runtime_contract_for_mock_bundle -q
```

Expected: selected tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/validate-offline-bundle.ps1 tests/test_packaging_control_plane.py
git commit -m "feat: validate offline runtime contract in bundle gate"
```

---

### Task 3: Python Dependency Checker Contract Checks

**Files:**
- Modify: `scripts/check-bundle-dependencies.py`
- Modify: `tests/test_packaging_control_plane.py`

- [ ] **Step 1: Write failing dependency checker tests**

Add to `TestStageJsonReports`:

```python
    def test_dependency_checker_reports_runtime_contract_missing_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            (bundle_root / "app" / "embedagent").mkdir(parents=True)
            (bundle_root / "runtime" / "python").mkdir(parents=True)
            (bundle_root / "bin").mkdir()
            report_path = bundle_root / "dependency-report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CHECK_SCRIPT),
                    str(bundle_root),
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            external = [item for item in payload["checks"] if item["name"] == "External Tools"][0]
            self.assertFalse(external["ok"])
            self.assertTrue(any("runtime_tool.git" in error for error in external["errors"]))
            self.assertTrue(any("runtime_tool.llvm.clang" in error for error in external["errors"]))
            self.assertEqual(payload["runtime_contract"]["schema_version"], 1)

    def test_dependency_checker_accepts_runtime_contract_complete_mock_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            for path in [
                "app/embedagent/__init__.py",
                "runtime/python/python.exe",
                "runtime/site-packages/embedagent/__init__.py",
                "runtime/site-packages/prompt_toolkit/__init__.py",
                "runtime/site-packages/rich/__init__.py",
                "runtime/site-packages/webview/__init__.py",
                "runtime/site-packages/fastapi/__init__.py",
                "runtime/site-packages/uvicorn/__init__.py",
                "runtime/site-packages/websockets/__init__.py",
                "runtime/site-packages/starlette/__init__.py",
                "runtime/site-packages/pydantic/__init__.py",
                "runtime/site-packages/anyio/__init__.py",
                "runtime/site-packages/sniffio/__init__.py",
                "runtime/site-packages/h11/__init__.py",
                "runtime/site-packages/idna/__init__.py",
                "runtime/site-packages/click/__init__.py",
                "runtime/site-packages/typing_extensions.py",
                "runtime/site-packages/colorama/__init__.py",
                "runtime/site-packages/pygments/__init__.py",
                "runtime/site-packages/wcwidth/__init__.py",
                "bin/git/cmd/git.exe",
                "bin/rg/rg.exe",
                "bin/ctags/ctags.exe",
                "bin/llvm/bin/clang.exe",
                "bin/llvm/bin/clang++.exe",
                "bin/llvm/bin/clang-cl.exe",
                "bin/llvm/bin/clang-tidy.exe",
                "bin/llvm/bin/clang-analyzer.bat",
                "bin/llvm/bin/llvm-profdata.exe",
                "bin/llvm/bin/llvm-cov.exe",
                "embedagent.cmd",
                "embedagent-tui.cmd",
                "embedagent-gui.cmd",
                "config/config.json",
                "config/config.json.template",
                "config/permission-rules.json",
                "docs/configuration-guide.md",
                "docs/win7-preflight-checklist.md",
                "docs/intranet-deployment.md",
                "app/embedagent/frontend/gui/static/index.html",
                "app/embedagent/frontend/gui/static/assets/app.js",
                "manifests/bundle-manifest.json",
            ]:
                target = bundle_root / Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("{}", encoding="ascii")
            report_path = bundle_root / "dependency-report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CHECK_SCRIPT),
                    str(bundle_root),
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestStageJsonReports::test_dependency_checker_reports_runtime_contract_missing_tools tests/test_packaging_control_plane.py::TestStageJsonReports::test_dependency_checker_accepts_runtime_contract_complete_mock_bundle -q
```

Expected: failure because the dependency checker does not load or report runtime contract details.

- [ ] **Step 3: Implement Python contract checks**

In `scripts/check-bundle-dependencies.py`:

- add `CONTRACT = ROOT / "scripts" / "offline-runtime-contract.json"`
- add `load_runtime_contract()`
- add helpers `_path_exists`, `_paths_exist`, `_alternative_exists`
- rewrite `check_external_tools(bundle_root)` to use the contract
- include error strings like:

```python
"runtime_tool.git missing: alternatives not found"
"runtime_tool.llvm.clang missing: bin/llvm/bin/clang.exe"
```

- include `runtime_contract` in JSON report:

```python
"runtime_contract": {
    "path": str(CONTRACT),
    "schema_version": contract.get("schema_version"),
}
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestStageJsonReports::test_dependency_checker_reports_runtime_contract_missing_tools tests/test_packaging_control_plane.py::TestStageJsonReports::test_dependency_checker_accepts_runtime_contract_complete_mock_bundle -q
```

Expected: selected tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/check-bundle-dependencies.py tests/test_packaging_control_plane.py
git commit -m "feat: check bundle dependencies from runtime contract"
```

---

### Task 4: Extension Dependency And Authoring Guardrails

**Files:**
- Modify: `tests/test_project_extensions.py`
- Modify: `tests/test_self_extension_authoring.py`

- [ ] **Step 1: Write failing or strengthening guard tests**

Add to `tests/test_project_extensions.py`:

```python
def test_project_extension_loading_does_not_invoke_dependency_installers(tmp_path, monkeypatch):
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
                "    return SampleExtension()",
            ]
        ),
        encoding="utf-8",
    )

    calls = []

    def blocked(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("extension loader must not invoke subprocess installers")

    import subprocess

    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["loaded"] == 1
    assert calls == []
```

Add to `tests/test_self_extension_authoring.py`:

```python
def test_generated_extension_validation_recipe_uses_managed_python_command(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )

    result = SelfExtensionAuthoringService(str(tmp_path)).author(
        AuthoringRequest(kind="extension", name="Compile Check", summary="Validate code.")
    )
    recipe_path = (
        tmp_path
        / ".embedagent"
        / "extensions"
        / "compile-check"
        / "recipes"
        / "validate.json"
    )
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))

    assert result.success is True
    assert recipe["tool_name"] == "run_recipe"
    assert recipe["recipe_action"] == "test"
    assert recipe["command"].startswith("python -m py_compile ")
```

- [ ] **Step 2: Run tests to verify behavior**

Run:

```bash
uv run pytest tests/test_project_extensions.py::test_project_extension_loading_does_not_invoke_dependency_installers tests/test_self_extension_authoring.py::test_generated_extension_validation_recipe_uses_managed_python_command -q
```

Expected: tests pass if existing behavior already satisfies the guard; if not, fix only the violating implementation.

- [ ] **Step 3: Commit Task 4**

```bash
git add tests/test_project_extensions.py tests/test_self_extension_authoring.py
git commit -m "test: guard offline extension loading boundaries"
```

---

### Task 5: Documentation And Closure

**Files:**
- Modify source-of-truth docs listed in File Structure
- Move:
  - `docs/superpowers/specs/2026-06-14-phase-f-offline-bundle-validation-design.md`
  - `docs/superpowers/plans/2026-06-14-phase-f-offline-bundle-validation.md`

- [ ] **Step 1: Update docs**

Update docs with these durable conclusions:

- Phase F introduces `scripts/offline-runtime-contract.json`.
- Runtime-invoked tools are validated by contract, not scattered per-script assumptions.
- LLVM/Clang required executables are release-gate checks.
- Project-local extension loading remains dependency-install-free.
- Generated local capabilities remain workspace-bound; generated extensions remain disabled by default.
- Real clean Windows 7 smoke remains the external release gate.

- [ ] **Step 2: Archive completed Phase F slice docs**

Create:

```text
docs/archive/phase-f-offline-bundle-validation/
```

Move:

```text
docs/superpowers/specs/2026-06-14-phase-f-offline-bundle-validation-design.md
docs/superpowers/plans/2026-06-14-phase-f-offline-bundle-validation.md
```

to:

```text
docs/archive/phase-f-offline-bundle-validation/2026-06-14-phase-f-offline-bundle-validation-design.md
docs/archive/phase-f-offline-bundle-validation/2026-06-14-phase-f-offline-bundle-validation.md
```

- [ ] **Step 3: Run doc/status checks**

Run:

```bash
rg -n "Phase F|offline-runtime-contract|runtime contract|llvm_clang_bundle|dependency-install" README.md AGENTS.md docs
```

Expected: active docs and archive docs mention the final contract clearly.

- [ ] **Step 4: Commit Task 5**

```bash
git add README.md AGENTS.md docs
git commit -m "docs: close phase f offline bundle validation"
```

---

### Task 6: Final Verification

**Files:**
- No planned edits.

- [ ] **Step 1: Run focused Phase F tests**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py tests/test_tools_package.py tests/test_project_extensions.py tests/test_self_extension_authoring.py tests/test_local_resources.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run lint and format checks**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
```

Expected: both pass.

- [ ] **Step 3: Run full fast non-GUI suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -q
```

Expected: full fast suite passes.

- [ ] **Step 4: Inspect git status and log**

Run:

```bash
git status --short --branch
git log --oneline --decorate -8
```

Expected: clean worktree on `codex/phase-f-offline-bundle-validation`, with Phase F commits visible.

## Plan Self-Review

- Spec coverage: all Phase F requirements map to Tasks 1 through 6.
- Placeholder scan: no TBD/TODO/fill-in placeholders remain.
- Type consistency: contract field names are consistent across tests and implementation notes.
- Risk note: real clean Windows 7 smoke remains external to this workspace and must be reported as a release gate, not claimed complete from repo-side tests.
