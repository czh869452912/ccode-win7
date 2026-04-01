# Packaging Control Plane Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current public multi-script offline packaging workflow with a single `scripts/package.ps1` control plane that supports `doctor/deps/assemble/verify/release`, profile-driven behavior, and a single authoritative packaging verdict/report.

**Architecture:** Add a new PowerShell control plane (`package.ps1` + `package-lib.ps1` + `package.config.json`) and keep the existing `export/prepare/build/validate/check` scripts as internal stages. Instrument the current validators/checkers to emit machine-readable JSON summaries, orchestrate them from the new control plane, and rewrite operator-facing docs so they only teach the new command surface.

**Tech Stack:** PowerShell 5.1/7 compatible scripts, Python 3.8 standard library, existing offline asset manifest, `unittest` + `subprocess` smoke tests, JSON reports under `build/offline-reports/`

---

## File Map

| File | Operation | Responsibility |
|------|-----------|----------------|
| `scripts/package.ps1` | **Create** | Public packaging entry point and subcommand dispatch |
| `scripts/package-lib.ps1` | **Create** | Shared config loading, stage execution, report building, status mapping |
| `scripts/package.config.json` | **Create** | Declarative packaging defaults, profiles, script paths, asset policy |
| `scripts/export-dependencies.py` | **Modify** | Add machine-readable dependency export report |
| `scripts/check-bundle-dependencies.py` | **Modify** | Add machine-readable dependency-check report |
| `scripts/validate-offline-bundle.ps1` | **Modify** | Add machine-readable validation summary output |
| `scripts/bootstrap-dev-env.ps1` | **Modify** | Point humans to `package.ps1` instead of old stage scripts |
| `tests/test_packaging_control_plane.py` | **Create** | Regression tests for config parsing, report status mapping, command dispatch, mock orchestration |
| `tests/fixtures/package/mock-export.py` | **Create** | Mock dependency-export stage for orchestration tests |
| `tests/fixtures/package/mock-prepare.ps1` | **Create** | Mock staging stage for orchestration tests |
| `tests/fixtures/package/mock-build.ps1` | **Create** | Mock dist/zip stage for orchestration tests |
| `tests/fixtures/package/mock-check.py` | **Create** | Mock dependency-check stage for orchestration tests |
| `tests/fixtures/package/mock-validate.ps1` | **Create** | Mock bundle-validate stage for orchestration tests |
| `tests/fixtures/package/mock-config.json` | **Create** | Test-only control-plane config wired to mock stage scripts |
| `docs/offline-packaging-guide.md` | **Modify** | Public operator guide; should teach only `package.ps1` |
| `docs/offline-packaging.md` | **Modify** | Packaging architecture/reference doc; should explain profiles and report model |
| `docs/intranet-deployment.md` | **Modify** | Deployment doc updated to use `package.ps1` |
| `docs/development-tracker.md` | **Modify** | Update current Phase 7 focus and task table |
| `docs/design-change-log.md` | **Modify** | Record packaging control-plane redesign decision |
| `docs/implementation-roadmap.md` | **Modify** | Update Phase 7 execution path and recommended commands |
| `docs/adrs/0004-packaging-control-plane-redesign.md` | **Create** | Record the long-lived packaging interface decision |

---

### Task 1: Create the Shared Packaging Foundation

**Files:**
- Create: `scripts/package.config.json`
- Create: `scripts/package-lib.ps1`
- Create: `tests/test_packaging_control_plane.py`

- [ ] **Step 1: Write the initial failing tests for config parsing and final-status mapping**

Create `tests/test_packaging_control_plane.py` with this initial content:

```python
import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "scripts" / "package-lib.ps1"
CONFIG = ROOT / "scripts" / "package.config.json"


def _powershell_exe():
    candidates = [
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("No PowerShell executable found for packaging tests.")


def run_pwsh(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_powershell_exe(), "-NoProfile", "-Command", command],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class TestPackageFoundation(unittest.TestCase):
    def test_config_exposes_dev_and_release_profiles(self):
        result = run_pwsh(
            ". '{lib}'; "
            "$cfg = Read-PackageConfig -Path '{config}'; "
            "[ordered]@{{default_profile=$cfg.default_profile; profiles=@($cfg.profiles.PSObject.Properties.Name)}} "
            "| ConvertTo-Json -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
                config=str(CONFIG).replace("\\", "\\\\"),
            )
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["default_profile"], "dev")
        self.assertEqual(sorted(payload["profiles"]), ["dev", "release"])

    def test_release_report_maps_success_to_ready(self):
        result = run_pwsh(
            ". '{lib}'; "
            "$report = New-PackageReport -Command 'release' -Profile 'release'; "
            "Add-StageResult -Report ([ref]$report) -Name 'verify' -Status 'pass' -ExitCode 0 -Summary @{{validator='ok'}}; "
            "Complete-PackageReport -Report ([ref]$report); "
            "$report | ConvertTo-Json -Depth 8 -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
            )
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["final_status"], "READY")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the initial tests and confirm they fail because the config/library do not exist yet**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- `test_config_exposes_dev_and_release_profiles` fails because `Read-PackageConfig` or `package.config.json` does not exist.
- `test_release_report_maps_success_to_ready` fails because `New-PackageReport` / `Add-StageResult` / `Complete-PackageReport` do not exist.

- [ ] **Step 3: Create the initial declarative config file**

Create `scripts/package.config.json` with this full content:

```json
{
  "schema_version": 1,
  "default_profile": "dev",
  "paths": {
    "project_root": ".",
    "build_root": "build",
    "reports_root": "build/offline-reports",
    "asset_manifest": "scripts/offline-assets.json",
    "site_packages_export_root": "build/offline-cache/site-packages-export",
    "site_packages_root": "build/offline-cache/site-packages-export/site-packages",
    "llvm_root": "toolchains/llvm/current",
    "dist_bundle_root": "build/offline-dist/embedagent-win7-x64"
  },
  "tooling": {
    "export_dependencies": "scripts/export-dependencies.py",
    "prepare_bundle": "scripts/prepare-offline.ps1",
    "build_bundle": "scripts/build-offline-bundle.ps1",
    "validate_bundle": "scripts/validate-offline-bundle.ps1",
    "check_dependencies": "scripts/check-bundle-dependencies.py"
  },
  "profiles": {
    "dev": {
      "artifact_name": "embedagent-win7-x64-dev",
      "allow_download": false,
      "require_complete": false,
      "create_zip": false,
      "run_dynamic_checks": false,
      "run_dependency_checker": true,
      "required_assets": [
        "python_embedded_x64",
        "mingit_x64",
        "ripgrep_x64",
        "universal_ctags_x64",
        "webview2_fixed_runtime_x64"
      ]
    },
    "release": {
      "artifact_name": "embedagent-win7-x64",
      "allow_download": false,
      "require_complete": true,
      "create_zip": true,
      "run_dynamic_checks": true,
      "run_dependency_checker": true,
      "required_assets": [
        "python_embedded_x64",
        "mingit_x64",
        "ripgrep_x64",
        "universal_ctags_x64",
        "webview2_fixed_runtime_x64"
      ]
    }
  }
}
```

- [ ] **Step 4: Create the initial shared PowerShell library**

Create `scripts/package-lib.ps1` with this initial content:

```powershell
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-ConfigPath {
    param(
        [string]$ProjectRoot,
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $ProjectRoot $Path
}

function Read-PackageConfig {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Package config not found: $Path"
    }
    $raw = Get-Content -LiteralPath $Path -Raw
    $config = $raw | ConvertFrom-Json
    if (-not $config.profiles.dev -or -not $config.profiles.release) {
        throw "Package config must define both dev and release profiles."
    }
    return $config
}

function New-PackageReport {
    param(
        [string]$Command,
        [string]$Profile
    )

    return [ordered]@{
        command = $Command
        profile = $Profile
        started_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        command_status = 'running'
        final_status = $null
        stages = @()
        blocking_issues = @()
        warnings = @()
    }
}

function Add-StageResult {
    param(
        [ref]$Report,
        [string]$Name,
        [string]$Status,
        [int]$ExitCode,
        [hashtable]$Summary
    )

    $stage = [ordered]@{
        name = $Name
        status = $Status
        exit_code = $ExitCode
        summary = $Summary
    }
    $Report.Value.stages += $stage
    if ($Status -eq 'fail') {
        $Report.Value.blocking_issues += ('Stage failed: ' + $Name)
    }
    elseif ($Status -eq 'warn') {
        $Report.Value.warnings += ('Stage warned: ' + $Name)
    }
}

function Complete-PackageReport {
    param(
        [ref]$Report
    )

    $report = $Report.Value
    $hasFailures = @($report.blocking_issues).Count -gt 0
    if ($report.command -eq 'doctor') {
        $report.command_status = if ($hasFailures) { 'NOT_READY' } else { 'READY' }
        $report.final_status = $null
        return
    }

    if ($hasFailures) {
        $report.final_status = 'NOT_READY'
    }
    elseif ($report.command -eq 'release' -or $report.profile -eq 'release') {
        $report.final_status = 'READY'
    }
    else {
        $report.final_status = 'DEV_ONLY'
    }
    $report.command_status = 'completed'
}

function Get-PackageExitCode {
    param(
        [hashtable]$Report
    )

    if ($Report.command -eq 'doctor') {
        return $(if ($Report.command_status -eq 'READY') { 0 } else { 1 })
    }

    switch ($Report.final_status) {
        'READY' { return 0 }
        'DEV_ONLY' { return 0 }
        'NOT_READY' { return 1 }
        default { return 2 }
    }
}
```

- [ ] **Step 5: Re-run the focused tests and confirm they now pass**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- `2 tests` run
- both tests pass

- [ ] **Step 6: Commit the foundation**

```bash
git add scripts/package.config.json scripts/package-lib.ps1 tests/test_packaging_control_plane.py
git commit -m "feat: add packaging control-plane foundation"
```

---

### Task 2: Add Machine-Readable Output to Existing Stage Scripts

**Files:**
- Modify: `scripts/export-dependencies.py`
- Modify: `scripts/check-bundle-dependencies.py`
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `tests/test_packaging_control_plane.py`

- [ ] **Step 1: Extend the test file with failing JSON-report tests**

Append these tests to `tests/test_packaging_control_plane.py`:

```python
import sys
import tempfile


EXPORT_SCRIPT = ROOT / "scripts" / "export-dependencies.py"
CHECK_SCRIPT = ROOT / "scripts" / "check-bundle-dependencies.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-offline-bundle.ps1"


class TestStageJsonReports(unittest.TestCase):
    def test_dependency_checker_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            report_path = bundle_root / "dependency-report.json"
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(bundle_root), "--json-report", str(report_path)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("ok", payload)
            self.assertIn("checks", payload)

    def test_export_verify_only_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_root = Path(tmp)
            site_packages = export_root / "site-packages"
            site_packages.mkdir()
            for name in [
                "prompt_toolkit",
                "rich",
                "webview",
                "fastapi",
                "uvicorn",
                "websockets",
                "starlette",
                "pydantic",
                "anyio",
                "click",
                "h11",
                "idna",
                "sniffio",
                "typing_extensions",
            ]:
                (site_packages / name).mkdir()
            report_path = export_root / "export-report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT_SCRIPT),
                    "--output-dir",
                    str(export_root),
                    "--verify-only",
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertIn("missing_packages", payload)

    def test_validate_offline_bundle_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            sources_root = Path(tmp) / "sources"
            bundle_root.mkdir()
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
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(json_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("results", payload)
            self.assertIn("fail_count", payload)
```

- [ ] **Step 2: Run the tests and confirm the new JSON-report tests fail**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- the three new tests fail because the scripts do not yet accept JSON report arguments

- [ ] **Step 3: Modify `export-dependencies.py` to emit a JSON report**

Apply these changes to `scripts/export-dependencies.py`:

```python
def write_json_report(path: str, payload: dict) -> None:
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def verify_site_packages(site_packages_dir: str):
    sp = Path(site_packages_dir)
    critical_packages = [
        "prompt_toolkit",
        "rich",
        "webview",
        "fastapi",
        "uvicorn",
        "websockets",
        "starlette",
        "pydantic",
        "anyio",
        "click",
        "h11",
        "idna",
        "sniffio",
        "typing_extensions",
    ]
    missing = []
    for pkg in critical_packages:
        found = False
        for variant in [pkg, pkg.replace("-", "_"), pkg.replace("_", "-")]:
            if (sp / variant).exists() or (sp / f"{variant}.py").exists():
                found = True
                break
            if list(sp.glob(f"{variant}-*.dist-info")):
                found = True
                break
        if not found:
            missing.append(pkg)
    return len(missing) == 0, missing
```

And add these CLI arguments and output logic:

```python
parser.add_argument(
    "--json-report",
    default="",
    help="Optional path for a machine-readable JSON report",
)
```

```python
if args.verify_only:
    site_packages = Path(args.output_dir) / "site-packages"
    if not site_packages.exists():
        payload = {"ok": False, "missing_packages": ["site-packages"], "mode": "verify-only"}
        write_json_report(args.json_report, payload)
        print(f"Site-packages not found: {site_packages}")
        sys.exit(1)
    success, missing = verify_site_packages(str(site_packages))
    write_json_report(
        args.json_report,
        {
            "ok": success,
            "mode": "verify-only",
            "site_packages_root": str(site_packages),
            "missing_packages": missing,
        },
    )
    sys.exit(0 if success else 1)
```

At the end of the export flow, add:

```python
success, missing = verify_site_packages(str(site_packages))
write_json_report(
    args.json_report,
    {
        "ok": success,
        "mode": "export",
        "output_dir": args.output_dir,
        "site_packages_root": str(site_packages),
        "requirements_file": str(Path(args.output_dir) / "requirements-pinned.txt"),
        "missing_packages": missing,
    },
)
```

- [ ] **Step 4: Modify `check-bundle-dependencies.py` to emit a JSON report**

Add this CLI argument:

```python
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Offline Bundle Dependency Checker")
    parser.add_argument("bundle_root", nargs="?", default="", help="Bundle root to inspect")
    parser.add_argument("--json-report", default="", help="Optional machine-readable JSON report path")
    return parser.parse_args()
```

Add this helper:

```python
def write_json_report(path: str, payload: dict) -> None:
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
```

Replace `main()` with:

```python
def main():
    args = parse_args()
    bundle_root = Path(args.bundle_root) if args.bundle_root else get_bundle_root()
    checks = [
        ("Python Runtime", check_python_runtime),
        ("Site Packages", check_site_packages),
        ("External Tools", check_external_tools),
        ("Launchers", check_launchers),
        ("Config Files", check_config_files),
        ("Documentation", check_documentation),
        ("Static Files", check_static_files),
        ("Manifest", check_manifest),
    ]

    all_passed = True
    check_payloads = []
    for name, check_func in checks:
        passed, errors = check_func(bundle_root)
        check_payloads.append({"name": name, "ok": passed, "errors": errors})
        if not passed:
            all_passed = False

    write_json_report(
        args.json_report,
        {
            "ok": all_passed,
            "bundle_root": str(bundle_root),
            "checks": check_payloads,
        },
    )

    for item in check_payloads:
        status = "✓" if item["ok"] else "✗"
        print(f"{status} {item['name']}")
        for error in item["errors"]:
            print(f"   - {error}")

    return 0 if all_passed else 1
```

- [ ] **Step 5: Modify `validate-offline-bundle.ps1` to emit a JSON summary**

Add this parameter near the top:

```powershell
[string]$JsonOutputPath = ""
```

Add this helper near `Add-Result`:

```powershell
function Write-JsonReport {
    param(
        [string]$Path,
        [hashtable]$Payload
    )

    if (-not $Path) {
        return
    }
    $parent = Split-Path -Parent $Path
    if ($parent -and (-not (Test-Path -LiteralPath $parent))) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding ASCII
}
```

Before the final `exit`, add:

```powershell
$summaryPayload = [ordered]@{
    ok = ($failCount -eq 0)
    artifact_name = $ArtifactName
    bundle_root = $BundleRoot
    zip_path = $ZipPath
    sources_root = $SourcesRoot
    require_complete = [bool]$RequireComplete
    skip_dynamic_checks = [bool]$SkipDynamicChecks
    pass_count = $passCount
    warn_count = $warnCount
    fail_count = $failCount
    results = $results
}
Write-JsonReport -Path $JsonOutputPath -Payload $summaryPayload
```

- [ ] **Step 6: Re-run the focused test file and confirm all JSON-report tests pass**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- `5 tests` run
- all tests pass

- [ ] **Step 7: Commit the machine-readable stage output changes**

```bash
git add scripts/export-dependencies.py scripts/check-bundle-dependencies.py scripts/validate-offline-bundle.ps1 tests/test_packaging_control_plane.py
git commit -m "feat: add machine-readable packaging stage reports"
```

---

### Task 3: Implement the Public Entry Point and `doctor`

**Files:**
- Create: `scripts/package.ps1`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/test_packaging_control_plane.py`

- [ ] **Step 1: Add failing tests for `package.ps1 doctor`**

Append these tests to `tests/test_packaging_control_plane.py`:

```python
PACKAGE_SCRIPT = ROOT / "scripts" / "package.ps1"


class TestPackageDoctor(unittest.TestCase):
    def test_package_doctor_emits_json_summary(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "doctor",
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "doctor")
        self.assertIn("doctor_checks", payload)

    def test_package_doctor_fails_for_missing_config(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "doctor",
                "-Config",
                "scripts/does-not-exist.json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
```

- [ ] **Step 2: Run the tests and confirm the new `doctor` tests fail**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- `package.ps1` does not exist yet, so the new tests fail

- [ ] **Step 3: Create the initial public control-plane entry point**

Create `scripts/package.ps1` with this initial content:

```powershell
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('doctor', 'deps', 'assemble', 'verify', 'release')]
    [string]$Command = 'release',

    [ValidateSet('dev', 'release')]
    [string]$Profile = '',

    [string]$Config = 'scripts/package.config.json',
    [string]$BundleRoot = '',
    [string]$OutputRoot = '',
    [string]$ArtifactName = '',
    [switch]$AllowDownload,
    [switch]$NoZip,
    [switch]$Strict,
    [switch]$Json
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'package-lib.ps1')

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$configPath = Resolve-ConfigPath -ProjectRoot $projectRoot -Path $Config
$configObject = Read-PackageConfig -Path $configPath
$context = New-PackageContext `
    -ProjectRoot $projectRoot `
    -Config $configObject `
    -ConfigPath $configPath `
    -Command $Command `
    -RequestedProfile $Profile `
    -BundleRoot $BundleRoot `
    -OutputRoot $OutputRoot `
    -ArtifactName $ArtifactName `
    -AllowDownload ([bool]$AllowDownload) `
    -NoZip ([bool]$NoZip) `
    -Strict ([bool]$Strict)

switch ($Command) {
    'doctor' { $report = Invoke-PackageDoctor -Context $context }
    default { throw "Not implemented yet: $Command" }
}

if ($Json) {
    $report | ConvertTo-Json -Depth 8
}

exit (Get-PackageExitCode -Report $report)
```

- [ ] **Step 4: Extend `package-lib.ps1` with context resolution and `doctor`**

Append these functions to `scripts/package-lib.ps1`:

```powershell
function New-PackageContext {
    param(
        [string]$ProjectRoot,
        [object]$Config,
        [string]$ConfigPath,
        [string]$Command,
        [string]$RequestedProfile,
        [string]$BundleRoot,
        [string]$OutputRoot,
        [string]$ArtifactName,
        [bool]$AllowDownload,
        [bool]$NoZip,
        [bool]$Strict
    )

    $effectiveProfile = if ($RequestedProfile) {
        $RequestedProfile
    }
    elseif ($Command -eq 'release') {
        'release'
    }
    else {
        [string]$Config.default_profile
    }

    $profileConfig = $Config.profiles.$effectiveProfile
    if (-not $profileConfig) {
        throw "Unknown packaging profile: $effectiveProfile"
    }

    return [ordered]@{
        project_root = $ProjectRoot
        config_path = $ConfigPath
        config = $Config
        command = $Command
        profile = $effectiveProfile
        profile_config = $profileConfig
        bundle_root = $BundleRoot
        output_root = $OutputRoot
        artifact_name = $(if ($ArtifactName) { $ArtifactName } else { [string]$profileConfig.artifact_name })
        allow_download = $AllowDownload -or [bool]$profileConfig.allow_download
        no_zip = $NoZip
        strict = $Strict
    }
}

function Invoke-PackageDoctor {
    param(
        [hashtable]$Context
    )

    $report = New-PackageReport -Command 'doctor' -Profile $Context.profile
    $doctorChecks = @()

    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.asset_manifest)
    $toolingRootChecks = @(
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.export_dependencies),
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.prepare_bundle),
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.build_bundle),
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.validate_bundle),
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.check_dependencies)
    )

    $doctorChecks += [ordered]@{ name = 'config'; ok = (Test-Path -LiteralPath $Context.config_path); path = $Context.config_path }
    $doctorChecks += [ordered]@{ name = 'asset_manifest'; ok = (Test-Path -LiteralPath $assetManifestPath); path = $assetManifestPath }
    foreach ($toolPath in $toolingRootChecks) {
        $doctorChecks += [ordered]@{ name = ('tool:' + [System.IO.Path]::GetFileName($toolPath)); ok = (Test-Path -LiteralPath $toolPath); path = $toolPath }
    }

    foreach ($check in $doctorChecks) {
        if (-not $check.ok) {
            $report.blocking_issues += ('Missing required path: ' + $check.path)
        }
    }

    $report.doctor_checks = $doctorChecks
    Complete-PackageReport -Report ([ref]$report)
    return $report
}
```

- [ ] **Step 5: Re-run the focused tests and confirm `doctor` now works**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- all current tests pass

- [ ] **Step 6: Commit the public entry point and `doctor`**

```bash
git add scripts/package.ps1 scripts/package-lib.ps1 tests/test_packaging_control_plane.py
git commit -m "feat: add package doctor entrypoint"
```

---

### Task 4: Implement `deps`, `assemble`, `verify`, and `release` with Mocked Orchestration Tests

**Files:**
- Modify: `scripts/package.ps1`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/test_packaging_control_plane.py`
- Create: `tests/fixtures/package/mock-export.py`
- Create: `tests/fixtures/package/mock-prepare.ps1`
- Create: `tests/fixtures/package/mock-build.ps1`
- Create: `tests/fixtures/package/mock-check.py`
- Create: `tests/fixtures/package/mock-validate.ps1`
- Create: `tests/fixtures/package/mock-config.json`

- [ ] **Step 1: Add failing orchestration tests wired to mock stage scripts**

Append these tests to `tests/test_packaging_control_plane.py`:

```python
MOCK_CONFIG = ROOT / "tests" / "fixtures" / "package" / "mock-config.json"


class TestPackageOrchestration(unittest.TestCase):
    def test_package_verify_returns_not_ready_for_missing_bundle(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "verify",
                "-BundleRoot",
                "build/does-not-exist",
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["final_status"], "NOT_READY")

    def test_package_release_with_mock_stages_returns_ready(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "release",
                "-Config",
                str(MOCK_CONFIG),
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "release")
        self.assertEqual(payload["final_status"], "READY")
        self.assertTrue(payload["report_path"])
```

- [ ] **Step 2: Run the tests and confirm the new orchestration tests fail**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- the new tests fail because `verify` / `release` are not implemented yet

- [ ] **Step 3: Add the mock stage fixtures**

Create `tests/fixtures/package/mock-export.py`:

```python
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--json-report", required=True)
parser.add_argument("--output-dir", required=False, default="")
args = parser.parse_args()

Path(args.json_report).write_text(
    json.dumps(
        {
            "ok": True,
            "mode": "export",
            "output_dir": args.output_dir,
            "missing_packages": [],
        },
        indent=2,
    ),
    encoding="utf-8",
)
```

Create `tests/fixtures/package/mock-check.py`:

```python
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("bundle_root")
parser.add_argument("--json-report", required=True)
args = parser.parse_args()

Path(args.json_report).write_text(
    json.dumps(
        {
            "ok": True,
            "bundle_root": args.bundle_root,
            "checks": [{"name": "mock-check", "ok": True, "errors": []}],
        },
        indent=2,
    ),
    encoding="utf-8",
)
```

Create `tests/fixtures/package/mock-prepare.ps1`:

```powershell
[CmdletBinding()]
param()

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$bundleRoot = Join-Path $projectRoot 'build\offline-staging\EmbedAgent'
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'manifests') -Force | Out-Null
@{
    schema_version = 2
    components = @()
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\bundle-manifest.json') -Encoding ASCII
Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\checksums.txt') -Value @() -Encoding ASCII
Write-Host "mock prepare complete"
```

Create `tests/fixtures/package/mock-build.ps1`:

```powershell
[CmdletBinding()]
param(
    [string]$ArtifactName = 'mock-artifact'
)

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$distRoot = Join-Path $projectRoot 'build\offline-dist'
$bundleRoot = Join-Path $distRoot $ArtifactName
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'manifests') -Force | Out-Null
@{
    schema_version = 2
    components = @()
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\bundle-manifest.json') -Encoding ASCII
Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\checksums.txt') -Value @() -Encoding ASCII
Set-Content -LiteralPath (Join-Path $distRoot ($ArtifactName + '.zip')) -Value 'zip-sentinel' -Encoding ASCII
Write-Host "mock build complete"
```

Create `tests/fixtures/package/mock-validate.ps1`:

```powershell
[CmdletBinding()]
param(
    [string]$BundleRoot = '',
    [string]$JsonOutputPath = ''
)

$payload = [ordered]@{
    ok = $true
    bundle_root = $BundleRoot
    fail_count = 0
    warn_count = 0
    pass_count = 1
    results = @(
        [ordered]@{
            level = 'pass'
            code = 'mock.validate'
            message = 'mock validate succeeded'
        }
    )
}

if ($JsonOutputPath) {
    $parent = Split-Path -Parent $JsonOutputPath
    if ($parent -and (-not (Test-Path -LiteralPath $parent))) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $JsonOutputPath -Encoding ASCII
}

Write-Host "mock validate complete"
```

Create `tests/fixtures/package/mock-config.json`:

```json
{
  "schema_version": 1,
  "default_profile": "dev",
  "paths": {
    "project_root": ".",
    "build_root": "build",
    "reports_root": "build/offline-reports",
    "asset_manifest": "scripts/offline-assets.json",
    "site_packages_export_root": "build/offline-cache/site-packages-export",
    "site_packages_root": "build/offline-cache/site-packages-export/site-packages",
    "llvm_root": "toolchains/llvm/current",
    "dist_bundle_root": "build/offline-dist/mock-artifact"
  },
  "tooling": {
    "export_dependencies": "tests/fixtures/package/mock-export.py",
    "prepare_bundle": "tests/fixtures/package/mock-prepare.ps1",
    "build_bundle": "tests/fixtures/package/mock-build.ps1",
    "validate_bundle": "tests/fixtures/package/mock-validate.ps1",
    "check_dependencies": "tests/fixtures/package/mock-check.py"
  },
  "profiles": {
    "dev": {
      "artifact_name": "mock-artifact",
      "allow_download": false,
      "require_complete": false,
      "create_zip": false,
      "run_dynamic_checks": false,
      "run_dependency_checker": true,
      "required_assets": []
    },
    "release": {
      "artifact_name": "mock-artifact",
      "allow_download": false,
      "require_complete": true,
      "create_zip": true,
      "run_dynamic_checks": false,
      "run_dependency_checker": true,
      "required_assets": []
    }
  }
}
```

- [ ] **Step 4: Extend `package-lib.ps1` with full orchestration**

Append these functions to `scripts/package-lib.ps1`:

```powershell
function Resolve-ToolPath {
    param(
        [hashtable]$Context,
        [string]$RelativePath
    )

    return Resolve-ConfigPath -ProjectRoot $Context.project_root -Path $RelativePath
}

function Invoke-StageScript {
    param(
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    $extension = [System.IO.Path]::GetExtension($ScriptPath).ToLowerInvariant()
    if ($extension -eq '.py') {
        return & .venv\Scripts\python.exe $ScriptPath @Arguments 2>&1
    }
    if ($extension -eq '.ps1') {
        return & powershell -NoProfile -File $ScriptPath @Arguments 2>&1
    }
    throw "Unsupported stage script extension: $ScriptPath"
}

function New-ReportPath {
    param(
        [hashtable]$Context,
        [string]$StageName
    )

    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    if (-not (Test-Path -LiteralPath $reportsRoot)) {
        New-Item -ItemType Directory -Path $reportsRoot -Force | Out-Null
    }
    return Join-Path $reportsRoot ($StageName + '.json')
}

function Invoke-PackageDeps {
    param(
        [hashtable]$Context,
        [ref]$Report
    )

    $scriptPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.export_dependencies)
    $jsonPath = New-ReportPath -Context $Context -StageName 'deps'
    $outputRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.site_packages_export_root)
    $null = Invoke-StageScript -ScriptPath $scriptPath -Arguments @('--output-dir', $outputRoot, '--json-report', $jsonPath)
    $payload = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    Add-StageResult -Report $Report -Name 'deps' -Status $(if ($payload.ok) { 'pass' } else { 'fail' }) -ExitCode $(if ($payload.ok) { 0 } else { 1 }) -Summary @{ report = $jsonPath }
}

function Invoke-PackageAssemble {
    param(
        [hashtable]$Context,
        [ref]$Report
    )

    $preparePath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.prepare_bundle)
    $buildPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.build_bundle)
    $null = Invoke-StageScript -ScriptPath $preparePath -Arguments @()
    Add-StageResult -Report $Report -Name 'prepare' -Status 'pass' -ExitCode 0 -Summary @{ script = $preparePath }
    $null = Invoke-StageScript -ScriptPath $buildPath -Arguments @('-ArtifactName', [string]$Context.artifact_name)
    Add-StageResult -Report $Report -Name 'build' -Status 'pass' -ExitCode 0 -Summary @{ script = $buildPath; artifact_name = $Context.artifact_name }
}

function Invoke-PackageVerify {
    param(
        [hashtable]$Context,
        [ref]$Report
    )

    $bundleRoot = if ($Context.bundle_root) {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path $Context.bundle_root
    }
    else {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.dist_bundle_root)
    }
    if (-not (Test-Path -LiteralPath $bundleRoot)) {
        Add-StageResult -Report $Report -Name 'verify' -Status 'fail' -ExitCode 1 -Summary @{ reason = 'bundle_root_missing'; bundle_root = $bundleRoot }
        return
    }

    $validateScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.validate_bundle)
    $checkScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.check_dependencies)
    $validateJson = New-ReportPath -Context $Context -StageName 'validate'
    $checkJson = New-ReportPath -Context $Context -StageName 'check'

    $validateArgs = @('-BundleRoot', $bundleRoot, '-JsonOutputPath', $validateJson, '-SkipDynamicChecks')
    if ([bool]$Context.profile_config.require_complete -or [bool]$Context.strict) {
        $validateArgs += '-RequireComplete'
    }
    $null = Invoke-StageScript -ScriptPath $validateScript -Arguments $validateArgs
    $validatePayload = Get-Content -LiteralPath $validateJson -Raw | ConvertFrom-Json

    $null = Invoke-StageScript -ScriptPath $checkScript -Arguments @($bundleRoot, '--json-report', $checkJson)
    $checkPayload = Get-Content -LiteralPath $checkJson -Raw | ConvertFrom-Json

    $verifyOk = ([bool]$validatePayload.ok) -and ([bool]$checkPayload.ok)
    Add-StageResult -Report $Report -Name 'verify' -Status $(if ($verifyOk) { 'pass' } else { 'fail' }) -ExitCode $(if ($verifyOk) { 0 } else { 1 }) -Summary @{
        bundle_root = $bundleRoot
        validate_report = $validateJson
        dependency_report = $checkJson
    }
}

function Write-PackageReport {
    param(
        [hashtable]$Context,
        [hashtable]$Report
    )

    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    if (-not (Test-Path -LiteralPath $reportsRoot)) {
        New-Item -ItemType Directory -Path $reportsRoot -Force | Out-Null
    }
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
    $reportPath = Join-Path $reportsRoot ($timestamp + '-' + $Context.command + '.json')
    $latestPath = Join-Path $reportsRoot 'latest.json'
    $Report.report_path = $reportPath
    $Report.generated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $Report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding ASCII
    $Report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $latestPath -Encoding ASCII
    return $reportPath
}

function Invoke-PackageCommand {
    param(
        [hashtable]$Context
    )

    $report = New-PackageReport -Command $Context.command -Profile $Context.profile
    switch ($Context.command) {
        'deps' {
            Invoke-PackageDeps -Context $Context -Report ([ref]$report)
        }
        'assemble' {
            Invoke-PackageAssemble -Context $Context -Report ([ref]$report)
        }
        'verify' {
            Invoke-PackageVerify -Context $Context -Report ([ref]$report)
        }
        'release' {
            Invoke-PackageDeps -Context $Context -Report ([ref]$report)
            if (@($report.blocking_issues).Count -eq 0) {
                Invoke-PackageAssemble -Context $Context -Report ([ref]$report)
            }
            if (@($report.blocking_issues).Count -eq 0) {
                Invoke-PackageVerify -Context $Context -Report ([ref]$report)
            }
        }
        default {
            throw "Unsupported packaging command: $($Context.command)"
        }
    }
    Complete-PackageReport -Report ([ref]$report)
    $null = Write-PackageReport -Context $Context -Report $report
    return $report
}
```

- [ ] **Step 5: Update `scripts/package.ps1` to use the full command dispatcher**

Replace the switch block in `scripts/package.ps1` with:

```powershell
switch ($Command) {
    'doctor' { $report = Invoke-PackageDoctor -Context $context }
    'deps' { $report = Invoke-PackageCommand -Context $context }
    'assemble' { $report = Invoke-PackageCommand -Context $context }
    'verify' { $report = Invoke-PackageCommand -Context $context }
    'release' { $report = Invoke-PackageCommand -Context $context }
    default { throw "Unsupported command: $Command" }
}
```

Keep this JSON/stdout behavior:

```powershell
if ($Json) {
    $report | ConvertTo-Json -Depth 10
}
```

- [ ] **Step 6: Run the orchestration tests and the two direct smoke commands**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
```

Expected:

- all tests pass, including the mock `release` orchestration test

Then run:

```powershell
powershell -NoProfile -File scripts\package.ps1 doctor -Json
powershell -NoProfile -File scripts\package.ps1 release -Config tests\fixtures\package\mock-config.json -Json
```

Expected:

- the first command prints a JSON report whose `"command"` is `"doctor"`
- the second command prints a JSON report whose `"final_status"` is `"READY"`

- [ ] **Step 7: Commit the orchestration layer**

```bash
git add scripts/package.ps1 scripts/package-lib.ps1 tests/test_packaging_control_plane.py tests/fixtures/package
git commit -m "feat: add packaging control-plane orchestration"
```

---

### Task 5: Reclassify the Legacy Stages and Rewrite the Operator Docs

**Files:**
- Modify: `scripts/bootstrap-dev-env.ps1`
- Modify: `docs/offline-packaging-guide.md`
- Modify: `docs/offline-packaging.md`
- Modify: `docs/intranet-deployment.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/implementation-roadmap.md`
- Create: `docs/adrs/0004-packaging-control-plane-redesign.md`

- [ ] **Step 1: Update the bootstrap script so it points operators to the new entry point**

In `scripts/bootstrap-dev-env.ps1`, replace the current “next step” packaging hint with:

```powershell
Write-Host '[bootstrap] Next step — package the offline bundle via the control plane:'
Write-Host '[bootstrap]   .\scripts\package.ps1 doctor'
Write-Host '[bootstrap]   .\scripts\package.ps1 release'
Write-Host '[bootstrap] For fast local iteration use:'
Write-Host '[bootstrap]   .\scripts\package.ps1 assemble -Profile dev'
```

- [ ] **Step 2: Rewrite the public packaging guide so it only teaches `package.ps1`**

Replace the operator command sections in `docs/offline-packaging-guide.md` with this structure:

````markdown
## 1. Public Commands

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 deps
pwsh -File scripts/package.ps1 assemble -Profile dev
pwsh -File scripts/package.ps1 verify -BundleRoot build/offline-dist/embedagent-win7-x64
pwsh -File scripts/package.ps1 release
```

## 2. Recommended Workflows

### 2.1 Daily developer workflow

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 assemble -Profile dev
pwsh -File scripts/package.ps1 verify -Profile dev -BundleRoot build/offline-dist/embedagent-win7-x64-dev
```

### 2.2 Release workflow

```powershell
pwsh -File scripts/package.ps1 release
```

`release` will:

1. export dependencies
2. assemble the bundle
3. verify the bundle
4. emit the authoritative JSON report
5. return `READY` or `NOT_READY`
````

Keep the old script names only in a short “legacy internal stages” appendix.

- [ ] **Step 3: Update the packaging/reference docs and add the ADR**

Add `docs/adrs/0004-packaging-control-plane-redesign.md` with this content:

```markdown
# ADR 0004: Packaging Control Plane Redesign

## Status

Accepted

## Context

The project currently exposes multiple packaging scripts directly to operators:

- `export-dependencies.py`
- `prepare-offline.ps1`
- `build-offline-bundle.ps1`
- `validate-offline-bundle.ps1`
- `check-bundle-dependencies.py`

This creates unnecessary operator complexity and an ambiguous release-readiness story.

## Decision

Adopt `scripts/package.ps1` as the single public packaging control plane.

Use:

- declarative config (`scripts/package.config.json`)
- explicit profiles (`dev`, `release`)
- one authoritative final packaging verdict
- one authoritative JSON packaging report

Keep the existing scripts as internal stages or compatibility shims during migration.

## Consequences

- public docs will teach only `package.ps1`
- old scripts remain available but are no longer first-class operator commands
- Phase 7 validation and release language become simpler and more auditable
```

Update `docs/offline-packaging.md`, `docs/intranet-deployment.md`, `docs/development-tracker.md`, `docs/design-change-log.md`, and `docs/implementation-roadmap.md` so they consistently say:

- `scripts/package.ps1` is the public entry point
- `prepare/build/validate/export/check` are internal stages
- release readiness is determined by the new report/final status model

- [ ] **Step 4: Verify the docs no longer teach the old scripts as the primary workflow**

Run:

```powershell
rg -n "prepare-offline\.ps1|build-offline-bundle\.ps1|validate-offline-bundle\.ps1|check-bundle-dependencies\.py|export-dependencies\.py" docs\offline-packaging-guide.md docs\intranet-deployment.md scripts\bootstrap-dev-env.ps1
```

Expected:

- matches, if any, should only be in legacy/internal-stage explanations
- there should be no primary “follow these four old commands” sections left

- [ ] **Step 5: Run the final focused verification commands**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_packaging_control_plane -v
powershell -NoProfile -File scripts\package.ps1 doctor -Json
powershell -NoProfile -File scripts\package.ps1 release -Config tests\fixtures\package\mock-config.json -Json
```

Expected:

- the unittest suite passes
- `doctor` exits `0`
- the mock `release` exits `0` and reports `"final_status": "READY"`

- [ ] **Step 6: Commit the doc and migration surface updates**

```bash
git add scripts/bootstrap-dev-env.ps1 docs/offline-packaging-guide.md docs/offline-packaging.md docs/intranet-deployment.md docs/development-tracker.md docs/design-change-log.md docs/implementation-roadmap.md docs/adrs/0004-packaging-control-plane-redesign.md
git commit -m "docs: adopt package control plane as public packaging interface"
```

---

## Self-Review Checklist

- Spec coverage:
  - `scripts/package.ps1` public control plane: covered in Task 3 and Task 4
  - declarative config: covered in Task 1
  - profiles and final-status model: covered in Task 1 and Task 4
  - internal stage reuse: covered in Task 2 and Task 4
  - single authoritative report: covered in Task 4
  - doc migration: covered in Task 5
- Placeholder scan:
  - no unfinished-marker text remains anywhere in the plan
- Type consistency:
  - commands: `doctor`, `deps`, `assemble`, `verify`, `release`
  - statuses: `READY`, `DEV_ONLY`, `NOT_READY`
  - config path file: `scripts/package.config.json`
  - library file: `scripts/package-lib.ps1`
