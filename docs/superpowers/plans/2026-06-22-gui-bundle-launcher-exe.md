# GUI Bundle Launcher Exe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native Windows GUI launcher executable to the existing one-folder offline bundle so users can double-click `EmbedAgent.exe` while preserving the current Python/WebView2 bundle model.

**Architecture:** Build a tiny Win32 launcher that only resolves the bundle root, sets the same environment as `embedagent-gui.cmd`, checks bundled Python and WebView2, forwards arguments to `launcher.py`, and returns the Python process exit code. The packaging control plane builds and stages that launcher into the portable bundle; validators and smoke tools treat it as the preferred GUI entry point while keeping `.cmd` launchers as diagnostics.

**Tech Stack:** PowerShell packaging scripts, C++ Win32 APIs, Python unittest tests, existing offline bundle validators, Python 3.8-compatible project code.

---

## File Structure

- Create `scripts/launcher/embedagent_gui_launcher.cpp`
  - Single-purpose Win32 launcher source.
  - Uses `GetModuleFileNameW`, `SetEnvironmentVariableW`, `CommandLineToArgvW`, and `CreateProcessW`.
  - Does not import project Python modules or own GUI behavior.

- Create `scripts/build-gui-launcher.ps1`
  - Build-time helper for compiling the launcher executable.
  - Writes `build/offline-cache/gui-launcher/embedagent-gui.exe` by default.
  - Uses a configured compiler or discovers `cl.exe` / `clang-cl.exe`.

- Modify `scripts/package.config.json`
  - Add `paths.gui_launcher_build_root`.
  - Add `tooling.build_gui_launcher`.
  - Add profile flag `run_gui_launcher_build`.

- Modify `scripts/package-lib.ps1`
  - Add GUI launcher build orchestration in `Invoke-PackageAssemble`.
  - Pass `-GuiLauncherExePath` into `prepare-offline.ps1`.
  - Keep mock/test configs able to disable this build stage.

- Modify `scripts/prepare-offline.ps1`
  - Add `-GuiLauncherExePath`.
  - Stage the native launcher into `EmbedAgent.exe` and `embedagent-gui.exe`.
  - Add a `gui_launcher_exe` component to `bundle-manifest.json`.

- Modify `scripts/validate-offline-bundle.ps1`
  - Require both native GUI launcher names for complete bundles.
  - Run `EmbedAgent.exe --help` and `embedagent-gui.exe --help` in dynamic validation.
  - Keep `embedagent-gui.cmd --help`.

- Modify `scripts/check-bundle-dependencies.py`
  - Require `EmbedAgent.exe`, `embedagent-gui.exe`, and existing `.cmd` launchers.

- Modify `scripts/validate-gui-smoke.py`
  - Prefer `embedagent-gui.exe` when `--bundle-root` is provided.
  - Fall back to `embedagent-gui.cmd` only when the exe is absent, so support workflows still have diagnostics.

- Modify test files:
  - `tests/test_gui_launcher_exe_contract.py`
  - `tests/test_packaging_control_plane.py`
  - `tests/test_gui_smoke_contract.py`

- Modify docs:
  - `docs/adrs/0005-gui-native-launcher-in-portable-bundle.md`
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/guides/win7-gui-validation.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`

---

### Task 1: Add Native Launcher Contract Tests

**Files:**
- Create: `tests/test_gui_launcher_exe_contract.py`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_gui_smoke_contract.py`

- [ ] **Step 1: Write failing launcher contract tests**

Create `tests/test_gui_launcher_exe_contract.py`:

```python
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_SOURCE = ROOT / "scripts" / "launcher" / "embedagent_gui_launcher.cpp"
BUILD_SCRIPT = ROOT / "scripts" / "build-gui-launcher.ps1"
PREPARE_SCRIPT = ROOT / "scripts" / "prepare-offline.ps1"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-offline-bundle.ps1"
DEPENDENCY_CHECKER = ROOT / "scripts" / "check-bundle-dependencies.py"


def read(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class TestGuiLauncherExeContract(unittest.TestCase):
    def test_launcher_source_is_thin_win32_process_launcher(self):
        source = read(LAUNCHER_SOURCE)

        self.assertIn("CreateProcessW", source)
        self.assertIn("SetEnvironmentVariableW", source)
        self.assertIn("CommandLineToArgvW", source)
        self.assertIn("runtime\\\\python\\\\python.exe", source)
        self.assertIn("app\\\\embedagent\\\\frontend\\\\gui\\\\launcher.py", source)
        self.assertIn("runtime\\\\webview2-fixed-runtime\\\\msedgewebview2.exe", source)
        self.assertIn("EMBEDAGENT_BUNDLE_ROOT", source)
        self.assertIn("PYTHONNOUSERSITE", source)
        self.assertNotIn("ShellExecute", source)
        self.assertNotIn("PyInstaller", source)
        self.assertNotIn("Nuitka", source)

    def test_build_script_targets_gui_subsystem_launcher(self):
        script = read(BUILD_SCRIPT)

        self.assertIn("embedagent_gui_launcher.cpp", script)
        self.assertIn("embedagent-gui.exe", script)
        self.assertIn("/SUBSYSTEM:WINDOWS,6.01", script)
        self.assertIn("cl.exe", script)
        self.assertIn("clang-cl.exe", script)
        self.assertIn("EMBEDAGENT_LAUNCHER_CC", script)

    def test_prepare_offline_stages_native_gui_launchers(self):
        script = read(PREPARE_SCRIPT)

        self.assertIn("GuiLauncherExePath", script)
        self.assertIn("gui_launcher_exe", script)
        self.assertIn("EmbedAgent.exe", script)
        self.assertIn("embedagent-gui.exe", script)
        self.assertIn("Generated embedagent.cmd, embedagent-tui.cmd, embedagent-gui.cmd", script)

    def test_validate_offline_bundle_requires_native_gui_launchers(self):
        script = read(VALIDATE_SCRIPT)

        self.assertIn("bundle.launcher.gui_exe_user", script)
        self.assertIn("bundle.launcher.gui_exe_cli", script)
        self.assertIn("dynamic.gui_launcher_exe_user", script)
        self.assertIn("dynamic.gui_launcher_exe_cli", script)
        self.assertIn("EmbedAgent.exe --help", script)
        self.assertIn("embedagent-gui.exe --help", script)
        self.assertIn("embedagent-gui.cmd --help", script)

    def test_dependency_checker_requires_native_gui_launchers(self):
        script = read(DEPENDENCY_CHECKER)

        self.assertIn('"EmbedAgent.exe"', script)
        self.assertIn('"embedagent-gui.exe"', script)
        self.assertIn('"embedagent-gui.cmd"', script)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Extend existing packaging and smoke contract tests**

In `tests/test_packaging_control_plane.py`, add these tests near the existing packaging contract tests:

```python
    def test_package_config_exposes_gui_launcher_build_tool(self):
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))

        self.assertIn("gui_launcher_build_root", payload["paths"])
        self.assertEqual(payload["tooling"]["build_gui_launcher"], "scripts/build-gui-launcher.ps1")
        self.assertTrue(payload["profiles"]["dev"]["run_gui_launcher_build"])
        self.assertTrue(payload["profiles"]["release"]["run_gui_launcher_build"])

    def test_prepare_offline_contract_mentions_native_gui_launcher_component(self):
        script = (ROOT / "scripts" / "prepare-offline.ps1").read_text(encoding="utf-8")

        self.assertIn("GuiLauncherExePath", script)
        self.assertIn("gui_launcher_exe", script)
        self.assertIn("EmbedAgent.exe", script)
        self.assertIn("embedagent-gui.exe", script)

    def test_validate_offline_bundle_flags_missing_native_gui_launcher_in_strict_mode(self):
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
            self.assertIn("bundle.launcher.gui_exe_user", result_codes)
            self.assertIn("bundle.launcher.gui_exe_cli", result_codes)
```

In `tests/test_gui_smoke_contract.py`, add:

```python
    def test_smoke_script_prefers_native_bundle_gui_launcher(self):
        text = self._script_text()

        self.assertIn('"embedagent-gui.exe"', text)
        self.assertIn('"embedagent-gui.cmd"', text)
        self.assertLess(text.index('"embedagent-gui.exe"'), text.index('"embedagent-gui.cmd"'))
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/test_gui_launcher_exe_contract.py tests/test_gui_smoke_contract.py -q
```

Expected: FAIL because `scripts/launcher/embedagent_gui_launcher.cpp` and `scripts/build-gui-launcher.ps1` do not exist yet, and the smoke script still uses `embedagent-gui.cmd`.

Run on Windows:

```bash
uv run pytest tests/test_packaging_control_plane.py -q
```

Expected: FAIL on the new packaging config and native launcher validation assertions.

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/test_gui_launcher_exe_contract.py tests/test_packaging_control_plane.py tests/test_gui_smoke_contract.py
git commit -m "test: add GUI launcher exe contracts"
```

---

### Task 2: Add The Win32 Launcher Source And Build Script

**Files:**
- Create: `scripts/launcher/embedagent_gui_launcher.cpp`
- Create: `scripts/build-gui-launcher.ps1`

- [ ] **Step 1: Add the Win32 launcher source**

Create `scripts/launcher/embedagent_gui_launcher.cpp`:

```cpp
#define UNICODE
#define _UNICODE

#include <shellapi.h>
#include <windows.h>

#include <string>
#include <vector>

static const wchar_t *kPythonRelativePath = L"runtime\\python\\python.exe";
static const wchar_t *kGuiScriptRelativePath = L"app\\embedagent\\frontend\\gui\\launcher.py";
static const wchar_t *kWebView2RelativePath =
    L"runtime\\webview2-fixed-runtime\\msedgewebview2.exe";

static std::wstring JoinPath(const std::wstring &left, const std::wstring &right)
{
    if (left.empty()) {
        return right;
    }
    if (left[left.size() - 1] == L'\\' || left[left.size() - 1] == L'/') {
        return left + right;
    }
    return left + L"\\" + right;
}

static bool FileExists(const std::wstring &path)
{
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

static std::wstring LastErrorMessage(DWORD code)
{
    wchar_t *buffer = NULL;
    DWORD flags = FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
                  FORMAT_MESSAGE_IGNORE_INSERTS;
    DWORD length = FormatMessageW(
        flags,
        NULL,
        code,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<LPWSTR>(&buffer),
        0,
        NULL);
    if (length == 0 || buffer == NULL) {
        return L"Windows error " + std::to_wstring(code);
    }
    std::wstring message(buffer, length);
    LocalFree(buffer);
    while (!message.empty() && (message[message.size() - 1] == L'\r' ||
                                message[message.size() - 1] == L'\n' ||
                                message[message.size() - 1] == L' ')) {
        message.erase(message.size() - 1);
    }
    return message;
}

static int Fail(const std::wstring &message, int exitCode)
{
    MessageBoxW(NULL, message.c_str(), L"EmbedAgent startup error", MB_OK | MB_ICONERROR);
    return exitCode;
}

static std::wstring QuoteArgument(const std::wstring &argument)
{
    if (argument.empty()) {
        return L"\"\"";
    }

    bool needsQuotes = argument.find_first_of(L" \t\n\v\"") != std::wstring::npos;
    if (!needsQuotes) {
        return argument;
    }

    std::wstring result = L"\"";
    size_t backslashes = 0;
    for (size_t i = 0; i < argument.size(); ++i) {
        wchar_t ch = argument[i];
        if (ch == L'\\') {
            ++backslashes;
            continue;
        }
        if (ch == L'"') {
            result.append(backslashes * 2 + 1, L'\\');
            result.push_back(ch);
            backslashes = 0;
            continue;
        }
        result.append(backslashes, L'\\');
        backslashes = 0;
        result.push_back(ch);
    }
    result.append(backslashes * 2, L'\\');
    result.push_back(L'"');
    return result;
}

static std::wstring GetEnvironmentValue(const wchar_t *name)
{
    DWORD length = GetEnvironmentVariableW(name, NULL, 0);
    if (length == 0) {
        return L"";
    }
    std::vector<wchar_t> buffer(length);
    DWORD written = GetEnvironmentVariableW(name, &buffer[0], length);
    if (written == 0 || written >= length) {
        return L"";
    }
    return std::wstring(&buffer[0], written);
}

static bool SetEnvironmentValue(const wchar_t *name, const std::wstring &value)
{
    return SetEnvironmentVariableW(name, value.c_str()) != FALSE;
}

static bool PrependPath(const std::vector<std::wstring> &entries)
{
    std::wstring existing = GetEnvironmentValue(L"PATH");
    std::wstring combined;
    for (size_t i = 0; i < entries.size(); ++i) {
        if (entries[i].empty()) {
            continue;
        }
        if (!combined.empty()) {
            combined += L";";
        }
        combined += entries[i];
    }
    if (!existing.empty()) {
        if (!combined.empty()) {
            combined += L";";
        }
        combined += existing;
    }
    return SetEnvironmentValue(L"PATH", combined);
}

static std::wstring ExecutableDirectory()
{
    std::vector<wchar_t> buffer(MAX_PATH);
    DWORD length = GetModuleFileNameW(NULL, &buffer[0], static_cast<DWORD>(buffer.size()));
    while (length == buffer.size()) {
        buffer.resize(buffer.size() * 2);
        length = GetModuleFileNameW(NULL, &buffer[0], static_cast<DWORD>(buffer.size()));
    }
    if (length == 0) {
        return L"";
    }
    std::wstring path(&buffer[0], length);
    size_t slash = path.find_last_of(L"\\/");
    if (slash == std::wstring::npos) {
        return L"";
    }
    return path.substr(0, slash);
}

static bool ConfigureEnvironment(const std::wstring &bundleRoot)
{
    std::wstring pythonHome = JoinPath(bundleRoot, L"runtime\\python");
    std::wstring pythonPath =
        JoinPath(bundleRoot, L"app") + L";" + JoinPath(bundleRoot, L"runtime\\site-packages");

    if (!SetEnvironmentValue(L"EMBEDAGENT_BUNDLE_ROOT", bundleRoot)) {
        return false;
    }
    if (!SetEnvironmentValue(L"PYTHONHOME", pythonHome)) {
        return false;
    }
    if (!SetEnvironmentValue(L"PYTHONPATH", pythonPath)) {
        return false;
    }
    if (!SetEnvironmentValue(L"PYTHONNOUSERSITE", L"1")) {
        return false;
    }

    if (GetEnvironmentValue(L"EMBEDAGENT_HOME").empty()) {
        std::wstring userProfile = GetEnvironmentValue(L"USERPROFILE");
        if (!userProfile.empty()) {
            SetEnvironmentValue(L"EMBEDAGENT_HOME", JoinPath(userProfile, L".embedagent"));
        }
    }

    std::vector<std::wstring> pathEntries;
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\git\\cmd"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\git\\bin"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\rg"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\ctags"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\llvm\\bin"));
    pathEntries.push_back(JoinPath(bundleRoot, L"bin\\llvm\\libexec"));
    return PrependPath(pathEntries);
}

static std::wstring BuildCommandLine(
    const std::wstring &pythonExe,
    const std::wstring &guiScript,
    int argc,
    wchar_t **argv)
{
    std::wstring command = QuoteArgument(pythonExe) + L" " + QuoteArgument(guiScript);
    for (int i = 1; i < argc; ++i) {
        command += L" ";
        command += QuoteArgument(argv[i]);
    }
    return command;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int)
{
    std::wstring bundleRoot = ExecutableDirectory();
    if (bundleRoot.empty()) {
        return Fail(L"Unable to determine the EmbedAgent bundle root.", 1);
    }

    std::wstring pythonExe = JoinPath(bundleRoot, kPythonRelativePath);
    std::wstring guiScript = JoinPath(bundleRoot, kGuiScriptRelativePath);
    std::wstring webview2Exe = JoinPath(bundleRoot, kWebView2RelativePath);

    if (!FileExists(pythonExe)) {
        return Fail(
            L"Bundled Python runtime not found:\n" + pythonExe +
                L"\n\nRepair or rebuild the offline bundle.",
            1);
    }
    if (!FileExists(guiScript)) {
        return Fail(
            L"GUI launcher script not found:\n" + guiScript +
                L"\n\nRepair or rebuild the offline bundle.",
            1);
    }
    if (!FileExists(webview2Exe)) {
        return Fail(
            L"Bundled Fixed Version WebView2 runtime not found:\n" + webview2Exe +
                L"\n\nGUI does not fall back to IE11. Use TUI/CLI or repair the bundle.",
            1);
    }
    if (!ConfigureEnvironment(bundleRoot)) {
        return Fail(L"Failed to configure the EmbedAgent bundle environment.", 1);
    }

    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == NULL) {
        return Fail(L"Failed to parse command-line arguments.", 1);
    }

    std::wstring commandLine = BuildCommandLine(pythonExe, guiScript, argc, argv);
    LocalFree(argv);

    std::vector<wchar_t> mutableCommand(commandLine.begin(), commandLine.end());
    mutableCommand.push_back(L'\0');

    STARTUPINFOW startupInfo;
    ZeroMemory(&startupInfo, sizeof(startupInfo));
    startupInfo.cb = sizeof(startupInfo);

    PROCESS_INFORMATION processInfo;
    ZeroMemory(&processInfo, sizeof(processInfo));

    BOOL created = CreateProcessW(
        pythonExe.c_str(),
        &mutableCommand[0],
        NULL,
        NULL,
        TRUE,
        0,
        NULL,
        bundleRoot.c_str(),
        &startupInfo,
        &processInfo);

    if (!created) {
        DWORD error = GetLastError();
        return Fail(
            L"Failed to start the EmbedAgent GUI process:\n" + pythonExe +
                L"\n\n" + LastErrorMessage(error),
            1);
    }

    WaitForSingleObject(processInfo.hProcess, INFINITE);
    DWORD exitCode = 1;
    GetExitCodeProcess(processInfo.hProcess, &exitCode);
    CloseHandle(processInfo.hThread);
    CloseHandle(processInfo.hProcess);
    return static_cast<int>(exitCode);
}
```

- [ ] **Step 2: Add the launcher build script**

Create `scripts/build-gui-launcher.ps1`:

```powershell
[CmdletBinding()]
param(
    [string]$SourcePath = "",
    [string]$OutputPath = "",
    [string]$CompilerPath = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-ProjectPath {
    param(
        [string]$ProjectRoot,
        [string]$Value
    )

    if (-not $Value) {
        return ""
    }
    $candidate = $Value
    if (-not [System.IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path $ProjectRoot $candidate
    }
    return [System.IO.Path]::GetFullPath($candidate)
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-CommandPathOrEmpty {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command -and $command.Source) {
        return $command.Source
    }
    return ""
}

function Resolve-LauncherCompiler {
    param(
        [string]$ProjectRoot,
        [string]$CompilerPath
    )

    $candidates = @()
    if ($CompilerPath) {
        $candidates += $CompilerPath
    }
    if ($env:EMBEDAGENT_LAUNCHER_CC) {
        $candidates += $env:EMBEDAGENT_LAUNCHER_CC
    }
    $cl = Get-CommandPathOrEmpty -Name 'cl.exe'
    if ($cl) {
        $candidates += $cl
    }
    $clangCl = Get-CommandPathOrEmpty -Name 'clang-cl.exe'
    if ($clangCl) {
        $candidates += $clangCl
    }
    $projectClangCl = Join-Path $ProjectRoot 'toolchains\llvm\current\bin\clang-cl.exe'
    if (Test-Path -LiteralPath $projectClangCl) {
        $candidates += $projectClangCl
    }

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'No launcher compiler found. Install MSVC Build Tools, put cl.exe or clang-cl.exe on PATH, or set EMBEDAGENT_LAUNCHER_CC.'
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $SourcePath) {
    $SourcePath = Join-Path $projectRoot 'scripts\launcher\embedagent_gui_launcher.cpp'
}
else {
    $SourcePath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $SourcePath
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $projectRoot 'build\offline-cache\gui-launcher\embedagent-gui.exe'
}
else {
    $OutputPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $OutputPath
}

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Launcher source not found: $SourcePath"
}

$compiler = Resolve-LauncherCompiler -ProjectRoot $projectRoot -CompilerPath $CompilerPath
$outputParent = Split-Path -Parent $OutputPath
Ensure-Directory -Path $outputParent

$args = @(
    '/nologo',
    '/EHsc',
    '/W4',
    '/O2',
    '/MT',
    '/DUNICODE',
    '/D_UNICODE',
    ('/Fe:' + $OutputPath),
    $SourcePath,
    '/link',
    '/SUBSYSTEM:WINDOWS,6.01',
    'shell32.lib',
    'user32.lib'
)

Write-Host "[launcher] Compiler: $compiler"
Write-Host "[launcher] Source: $SourcePath"
Write-Host "[launcher] Output: $OutputPath"

$output = & $compiler @args 2>&1
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw ("GUI launcher build failed (exit {0}): {1}" -f $exitCode, ($output | Out-String).Trim())
}
if (-not (Test-Path -LiteralPath $OutputPath)) {
    throw "GUI launcher compiler succeeded but output was not created: $OutputPath"
}

Write-Host "[launcher] Build complete"
```

- [ ] **Step 3: Run contract tests and confirm source/build-script tests pass**

Run:

```bash
uv run pytest tests/test_gui_launcher_exe_contract.py::TestGuiLauncherExeContract::test_launcher_source_is_thin_win32_process_launcher tests/test_gui_launcher_exe_contract.py::TestGuiLauncherExeContract::test_build_script_targets_gui_subsystem_launcher -q
```

Expected: PASS for these two tests. Other tests still fail because packaging scripts are not integrated.

- [ ] **Step 4: Try a local launcher build when a compiler is available**

Run on Windows:

```powershell
pwsh -File scripts/build-gui-launcher.ps1
```

Expected if a compiler is configured: `build/offline-cache/gui-launcher/embedagent-gui.exe` exists.

Expected if no compiler is configured: the script fails with `No launcher compiler found...`. This is acceptable at this point, but must be recorded in verification notes.

- [ ] **Step 5: Commit launcher source and build script**

```bash
git add scripts/launcher/embedagent_gui_launcher.cpp scripts/build-gui-launcher.ps1
git commit -m "feat: add native GUI launcher source"
```

---

### Task 3: Wire Launcher Build Into The Packaging Control Plane

**Files:**
- Modify: `scripts/package.config.json`
- Modify: `scripts/package-lib.ps1`
- Modify: `tests/fixtures/package/mock-config.json`
- Create: `tests/fixtures/package/mock-build-gui-launcher.ps1`

- [ ] **Step 1: Update config tests if Task 1 did not already add them**

Ensure `tests/test_packaging_control_plane.py` includes:

```python
    def test_package_config_exposes_gui_launcher_build_tool(self):
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))

        self.assertIn("gui_launcher_build_root", payload["paths"])
        self.assertEqual(payload["tooling"]["build_gui_launcher"], "scripts/build-gui-launcher.ps1")
        self.assertTrue(payload["profiles"]["dev"]["run_gui_launcher_build"])
        self.assertTrue(payload["profiles"]["release"]["run_gui_launcher_build"])
```

- [ ] **Step 2: Update `scripts/package.config.json`**

Add `gui_launcher_build_root` under `paths`:

```json
"gui_launcher_build_root": "build/offline-cache/gui-launcher"
```

Add `build_gui_launcher` under `tooling`:

```json
"build_gui_launcher": "scripts/build-gui-launcher.ps1"
```

Add this field to both `dev` and `release` profiles:

```json
"run_gui_launcher_build": true
```

- [ ] **Step 3: Add a mock launcher build script**

Create `tests/fixtures/package/mock-build-gui-launcher.ps1`:

```powershell
[CmdletBinding()]
param(
    [string]$OutputPath = ''
)

if (-not $OutputPath) {
    throw 'mock GUI launcher build expected OutputPath'
}

$parent = Split-Path -Parent $OutputPath
if ($parent -and (-not (Test-Path -LiteralPath $parent))) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
Set-Content -LiteralPath $OutputPath -Value 'mock gui launcher exe' -Encoding ASCII
Write-Host "mock GUI launcher build complete"
```

- [ ] **Step 4: Update mock package config**

In `tests/fixtures/package/mock-config.json`, add:

```json
"gui_launcher_build_root": "build/offline-cache/gui-launcher"
```

under `paths`, add:

```json
"build_gui_launcher": "tests/fixtures/package/mock-build-gui-launcher.ps1"
```

under `tooling`, and set:

```json
"run_gui_launcher_build": false
```

in both mock profiles. Keeping the mock value false preserves the existing mock stage-name expectations.

- [ ] **Step 5: Add packaging orchestration helpers**

In `scripts/package-lib.ps1`, add this function after `Get-PackageRequiredAssetIds`:

```powershell
function Get-GuiLauncherOutputPath {
    param(
        [System.Collections.IDictionary]$Context
    )

    $root = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.gui_launcher_build_root)
    return Join-Path $root 'embedagent-gui.exe'
}
```

Add this function near `Invoke-FrontendBuild`:

```powershell
function Invoke-GuiLauncherBuild {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[assemble] Building native GUI launcher..."
    $scriptPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.build_gui_launcher)
    $outputPath = Get-GuiLauncherOutputPath -Context $Context
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $scriptPath -Arguments @('-OutputPath', $outputPath)
        Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'pass' -ExitCode 0 -Summary @{
            script = $scriptPath
            output = $outputPath
        }
        Write-PackageLog "[assemble]   gui_launcher_build OK"
    }
    catch {
        Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'fail' -ExitCode 1 -Summary @{
            script = $scriptPath
            output = $outputPath
            error = $_.Exception.Message
        }
        Write-PackageLog ("[assemble]   gui_launcher_build FAILED: {0}" -f $_.Exception.Message)
    }
}
```

In `Invoke-PackageAssemble`, after frontend build and before `prepare-offline.ps1`, add:

```powershell
    $guiLauncherExePath = ''
    if ([bool]$Context.profile_config.run_gui_launcher_build) {
        Invoke-GuiLauncherBuild -Context $Context -Report $Report
        if (@($Report.Value.blocking_issues).Count -gt 0) { return }
        $guiLauncherExePath = Get-GuiLauncherOutputPath -Context $Context
    }
```

Then before invoking prepare, add:

```powershell
    if ($guiLauncherExePath) {
        $prepareArgs += '-GuiLauncherExePath'
        $prepareArgs += $guiLauncherExePath
    }
```

- [ ] **Step 6: Run packaging control-plane tests**

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestPackageFoundation::test_config_exposes_dev_and_release_profiles tests/test_packaging_control_plane.py::TestPackageOrchestration::test_package_release_with_mock_stages_returns_ready tests/test_packaging_control_plane.py::TestPackageOrchestration::test_mock_release_does_not_inject_frontend_build_stage -q
```

Expected: PASS. The mock config has `run_gui_launcher_build=false`, so existing mock stage expectations remain unchanged.

Run:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestPackageFoundation::test_package_config_exposes_gui_launcher_build_tool -q
```

Expected: PASS.

- [ ] **Step 7: Commit packaging control-plane wiring**

```bash
git add scripts/package.config.json scripts/package-lib.ps1 tests/fixtures/package/mock-config.json tests/fixtures/package/mock-build-gui-launcher.ps1 tests/test_packaging_control_plane.py
git commit -m "feat: wire GUI launcher build into packaging"
```

---

### Task 4: Stage Native Launchers In The Offline Bundle

**Files:**
- Modify: `scripts/prepare-offline.ps1`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_gui_launcher_exe_contract.py`

- [ ] **Step 1: Add a failing prepare-offline contract test if missing**

Ensure `tests/test_packaging_control_plane.py` has:

```python
    def test_prepare_offline_contract_mentions_native_gui_launcher_component(self):
        script = (ROOT / "scripts" / "prepare-offline.ps1").read_text(encoding="utf-8")

        self.assertIn("GuiLauncherExePath", script)
        self.assertIn("gui_launcher_exe", script)
        self.assertIn("EmbedAgent.exe", script)
        self.assertIn("embedagent-gui.exe", script)
```

- [ ] **Step 2: Add the prepare parameter**

In `scripts/prepare-offline.ps1`, add this parameter after `$LlvmRoot`:

```powershell
[string]$GuiLauncherExePath = "",
```

If parameter ordering makes a trailing comma awkward, add it before `[switch]$SkipBuild`.

- [ ] **Step 3: Add staging helper**

Add this function near `Stage-File`:

```powershell
function Stage-GuiLauncherExe {
    param(
        [string]$Source,
        [string]$BundleRoot
    )

    if (-not $Source) {
        return [ordered]@{
            status = 'missing'
            source_path = ''
            notes = 'Native GUI launcher executable was not provided. Run package.ps1 assemble/release so build-gui-launcher.ps1 can produce it.'
        }
    }
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Native GUI launcher executable not found: $Source"
    }

    Stage-File -Source $Source -Destination (Join-Path $BundleRoot 'EmbedAgent.exe')
    Stage-File -Source $Source -Destination (Join-Path $BundleRoot 'embedagent-gui.exe')
    return [ordered]@{
        status = 'staged'
        source_path = $Source
        notes = 'Staged native GUI launcher as EmbedAgent.exe and embedagent-gui.exe.'
    }
}
```

- [ ] **Step 4: Resolve and stage the launcher**

After resolving other manually provided paths:

```powershell
$guiLauncherExeResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $GuiLauncherExePath
```

After writing `validate-gui-smoke.cmd` and before creating component records, add:

```powershell
$guiLauncherResult = Stage-GuiLauncherExe -Source $guiLauncherExeResolved -BundleRoot $bundleRoot
```

Then add this component after `launcher_scripts`:

```powershell
$components += New-ComponentRecord -Name 'gui_launcher_exe' -StagedPath 'EmbedAgent.exe;embedagent-gui.exe' -Required $true -Status $guiLauncherResult.status -SourcePath $guiLauncherResult.source_path -Notes $guiLauncherResult.notes -AssetId ''
```

Update the `launcher_scripts` notes to keep it script-specific:

```powershell
$components += New-ComponentRecord -Name 'launcher_scripts' -StagedPath '.' -Required $true -Status 'staged' -SourcePath '' -Notes 'Generated embedagent.cmd, embedagent-tui.cmd, embedagent-gui.cmd, and validate-gui-smoke.cmd.' -AssetId ''
```

- [ ] **Step 5: Run contract tests**

Run:

```bash
uv run pytest tests/test_gui_launcher_exe_contract.py::TestGuiLauncherExeContract::test_prepare_offline_stages_native_gui_launchers tests/test_packaging_control_plane.py::TestPrepareOfflineContract::test_prepare_offline_stages_real_c_workspace_template -q
```

Expected: PASS.

- [ ] **Step 6: Manually smoke prepare staging with a mock exe**

On Windows:

```powershell
New-Item -ItemType Directory -Force build\test-tmp | Out-Null
Set-Content -LiteralPath build\test-tmp\embedagent-gui.exe -Value 'mock exe' -Encoding ASCII
pwsh -File scripts/prepare-offline.ps1 -SkipBuild -GuiLauncherExePath build\test-tmp\embedagent-gui.exe
Test-Path build\offline-staging\EmbedAgent\EmbedAgent.exe
Test-Path build\offline-staging\EmbedAgent\embedagent-gui.exe
```

Expected: both `Test-Path` commands print `True`.

- [ ] **Step 7: Commit staging changes**

```bash
git add scripts/prepare-offline.ps1 tests/test_packaging_control_plane.py tests/test_gui_launcher_exe_contract.py
git commit -m "feat: stage native GUI launcher in offline bundle"
```

---

### Task 5: Validate And Smoke The Native Launcher Entry Point

**Files:**
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `scripts/check-bundle-dependencies.py`
- Modify: `scripts/validate-gui-smoke.py`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_gui_smoke_contract.py`
- Modify: `tests/test_gui_launcher_exe_contract.py`

- [ ] **Step 1: Update static validation checks**

In `scripts/validate-offline-bundle.ps1`, add after the existing GUI `.cmd` launcher static check:

```powershell
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'EmbedAgent.exe') -Code 'bundle.launcher.gui_exe_user' -Message 'Native GUI user launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'embedagent-gui.exe') -Code 'bundle.launcher.gui_exe_cli' -Message 'Native GUI CLI launcher present.' -TreatAsCompleteGate $true
```

Add `gui_launcher_exe` to the strict component gate list:

```powershell
$completeGateComponents = @('python_runtime', 'python_packages', 'mingit_portable', 'ripgrep', 'universal_ctags', 'llvm_clang_bundle', 'webview2_fixed_runtime', 'gui_launcher_exe')
```

- [ ] **Step 2: Add dynamic launcher checks**

Add this helper before the dynamic checks block:

```powershell
function Invoke-GuiHelpCheck {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [string]$LauncherFile,
        [string]$Code
    )

    $launcher = Join-Path $BundleRoot $LauncherFile
    if (-not (Test-Path -LiteralPath $launcher)) {
        return
    }
    Push-Location $BundleRoot
    try {
        $output = & $launcher --help 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Add-Result -Results $Results -Level 'pass' -Code $Code -Message ("{0} --help succeeded." -f $LauncherFile)
        }
        else {
            Add-Result -Results $Results -Level 'fail' -Code $Code -Message ("{0} --help failed ({1}): {2}" -f $LauncherFile, $exitCode, ($output | Out-String).Trim())
        }
    }
    catch {
        Add-Result -Results $Results -Level 'fail' -Code $Code -Message ("{0} --help threw: {1}" -f $LauncherFile, $_.Exception.Message)
    }
    finally {
        Pop-Location
    }
}
```

Inside `if (-not $SkipDynamicChecks)`, before the existing `.cmd` check, call:

```powershell
Invoke-GuiHelpCheck -Results $results -BundleRoot $BundleRoot -LauncherFile 'EmbedAgent.exe' -Code 'dynamic.gui_launcher_exe_user'
Invoke-GuiHelpCheck -Results $results -BundleRoot $BundleRoot -LauncherFile 'embedagent-gui.exe' -Code 'dynamic.gui_launcher_exe_cli'
```

Keep the existing `.cmd` dynamic check so console diagnostics still work.

- [ ] **Step 3: Update dependency checker launchers**

In `scripts/check-bundle-dependencies.py`, change `check_launchers` to:

```python
def check_launchers(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check launcher entry points exist."""
    errors = []
    launchers = [
        "EmbedAgent.exe",
        "embedagent-gui.exe",
        "embedagent.cmd",
        "embedagent-tui.cmd",
        "embedagent-gui.cmd",
    ]

    for launcher in launchers:
        if not (bundle_root / launcher).exists():
            errors.append(f"Missing launcher: {launcher}")

    return len(errors) == 0, errors
```

- [ ] **Step 4: Update GUI smoke launcher selection**

In `scripts/validate-gui-smoke.py`, replace the `bundle_root` branch in `_build_command` with:

```python
    if bundle_root:
        native_launcher = os.path.join(bundle_root, "embedagent-gui.exe")
        cmd_launcher = os.path.join(bundle_root, "embedagent-gui.cmd")
        launcher = native_launcher if os.path.isfile(native_launcher) else cmd_launcher
        if not os.path.isfile(launcher):
            raise RuntimeError(
                "GUI launcher not found in bundle: %s or %s" % (native_launcher, cmd_launcher)
            )
        return {
            "command": [
                launcher,
                "--workspace",
                workspace_dir,
                "--model",
                "gui-smoke-model",
                "--base-url",
                "http://127.0.0.1:%d/v1" % model_port,
                "--port",
                str(gui_port),
                "--timeout",
                "20",
                "--max-turns",
                "2",
            ],
            "cwd": bundle_root,
            "env": dict(os.environ),
        }
```

- [ ] **Step 5: Update mock bundles in tests**

In `tests/test_packaging_control_plane.py`, any mock complete bundle that expects dependency checker success must include:

```python
"EmbedAgent.exe",
"embedagent-gui.exe",
```

in the mocked path list alongside `embedagent-gui.cmd`.

- [ ] **Step 6: Run focused validation tests**

Run:

```bash
uv run pytest tests/test_gui_launcher_exe_contract.py tests/test_gui_smoke_contract.py -q
```

Expected: PASS.

Run on Windows:

```bash
uv run pytest tests/test_packaging_control_plane.py::TestStageJsonReports::test_dependency_checker_accepts_runtime_contract_complete_mock_bundle tests/test_packaging_control_plane.py::TestStageJsonReports::test_validate_offline_bundle_flags_gui_launcher_contract_drift tests/test_packaging_control_plane.py::TestStageJsonReports::test_validate_offline_bundle_fails_strict_for_missing_runtime_contract_tool -q
```

Expected: PASS.

- [ ] **Step 7: Commit validation and smoke changes**

```bash
git add scripts/validate-offline-bundle.ps1 scripts/check-bundle-dependencies.py scripts/validate-gui-smoke.py tests/test_packaging_control_plane.py tests/test_gui_smoke_contract.py tests/test_gui_launcher_exe_contract.py
git commit -m "feat: validate native GUI launcher entry points"
```

---

### Task 6: Update Durable Packaging Documentation And ADR

**Files:**
- Create: `docs/adrs/0005-gui-native-launcher-in-portable-bundle.md`
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/modules/packaging-and-deployment.md`
- Modify: `docs/guides/win7-gui-validation.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Add ADR 0005**

Create `docs/adrs/0005-gui-native-launcher-in-portable-bundle.md`:

```markdown
# ADR 0005: GUI Native Launcher In Portable Bundle

## Status

Accepted

## Context

EmbedAgent's release baseline is a one-folder portable Windows 7 x64 offline
bundle. The GUI currently starts through `embedagent-gui.cmd`, which correctly
sets the bundled Python, site-packages, WebView2 Fixed Version 109, and tool
PATH environment.

That script entry point is useful for diagnostics, but normal users expect a
native application entry point they can double-click from the bundle root.

## Decision

Add a native Win32 GUI launcher executable to the existing portable bundle:

- `EmbedAgent.exe` for user-facing double-click startup
- `embedagent-gui.exe` for script-friendly GUI startup
- `embedagent-gui.cmd` remains as a diagnostic fallback

The launcher is a thin startup shim only. It resolves the bundle root, sets the
same environment as `embedagent-gui.cmd`, checks bundled Python and WebView2,
forwards arguments to `app/embedagent/frontend/gui/launcher.py`, waits for the
Python process, and returns its exit code.

The product remains a one-folder portable bundle. This ADR does not adopt
PyInstaller, Nuitka, Electron, an installer-first strategy, or a one-file exe
deployment model.

## Consequences

Positive:

- users get a native GUI entry point
- support still has `.cmd` launchers for visible console diagnostics
- the bundle remains inspectable and contract-validated
- Agent Core and GUI runtime architecture remain unchanged

Trade-offs:

- release packaging now has a build-time compiler requirement for the launcher
- validators must check both native exe launchers and `.cmd` launchers
- real Windows 7 smoke remains required to prove the launcher binary is portable

## Follow-Up

1. Keep `validate-offline-bundle.ps1` and `check-bundle-dependencies.py` aligned
   with the launcher set.
2. Keep `validate-gui-smoke.py` preferring `embedagent-gui.exe` for bundle
   tests.
3. Do not replace the portable bundle with one-file freezing unless a separate
   ADR supersedes ADR 0001 and this decision.
```

- [ ] **Step 2: Update packaging module bundle tree**

In `docs/modules/packaging-and-deployment.md`, change the bundle tree entry from:

```text
├── embedagent.cmd / embedagent-tui.cmd / embedagent-gui.cmd
```

to:

```text
├── EmbedAgent.exe / embedagent-gui.exe
├── embedagent.cmd / embedagent-tui.cmd / embedagent-gui.cmd
```

Add `Native GUI launcher` to the component table:

```markdown
| Native GUI launcher | `EmbedAgent.exe`, `embedagent-gui.exe` | integrated |
```

Add `scripts/build-gui-launcher.ps1` and `scripts/launcher/embedagent_gui_launcher.cpp` to Code Mapping.

- [ ] **Step 3: Update Win7 GUI validation guide**

In `docs/guides/win7-gui-validation.md`, update suggested commands to:

```cmd
EmbedAgent.exe --help
embedagent-gui.exe --help
embedagent-gui.cmd --help
validate-gui-smoke.cmd
validate-gui-smoke.cmd --windowed --auto-close-seconds 8
```

Add pass criteria:

```markdown
- `EmbedAgent.exe --help` returns exit code `0`
- `embedagent-gui.exe --help` returns exit code `0`
- `embedagent-gui.cmd --help` remains available for diagnostics
```

- [ ] **Step 4: Update global docs**

In `README.md` and `docs/overall-solution-architecture.md`, add one sentence to the bundling model:

```markdown
The GUI bundle includes a thin native Win32 launcher (`EmbedAgent.exe` / `embedagent-gui.exe`) for double-click startup, while Python, WebView2, LLVM/Clang, MinGit, ripgrep, and Universal Ctags remain explicit files in the portable bundle.
```

In `docs/implementation-roadmap.md`, add the launcher to recent GUI app-shell or offline packaging stabilization notes:

```markdown
- Offline GUI packaging now includes a native Win32 launcher exe in the portable bundle, preserving the one-folder delivery model while improving double-click startup.
```

- [ ] **Step 5: Add tracker and change-log entries**

Add a new top entry to `docs/development-tracker.md`:

```markdown
### 2026-06-22 - GUI Native Bundle Launcher

- Offline GUI startup now has a native Win32 launcher entry point in the portable bundle: `EmbedAgent.exe` for user double-click startup and `embedagent-gui.exe` for scriptable GUI startup.
- The launcher is a thin environment/setup shim over the existing Python GUI launcher; it does not freeze Agent Core or change GUI backend/frontend semantics.
- `embedagent-gui.cmd` remains available for visible-console diagnostics and support.
- Packaging validators and GUI smoke tests now treat the native launcher as the preferred bundle GUI entry point while preserving WebView2 Fixed Version 109 and one-folder offline delivery.
```

Add a new top entry to `docs/design-change-log.md`:

```markdown
### DC-192

- 日期：2026-06-22
- 变更主题：GUI native launcher in portable offline bundle
- 变更摘要：
  - The portable offline bundle now includes `EmbedAgent.exe` and `embedagent-gui.exe` as thin native GUI launchers.
  - The launchers set the same bundle environment as `embedagent-gui.cmd`, check bundled Python and WebView2 Fixed Version runtime, and forward to the existing Python GUI launcher.
  - The one-folder portable bundle remains the release baseline; this does not adopt PyInstaller, Nuitka, Electron, installer-first packaging, or one-file exe delivery.
- 影响范围：
  - `scripts/launcher/embedagent_gui_launcher.cpp`
  - `scripts/build-gui-launcher.ps1`
  - `scripts/package.config.json`
  - `scripts/package-lib.ps1`
  - `scripts/prepare-offline.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `scripts/check-bundle-dependencies.py`
  - `scripts/validate-gui-smoke.py`
  - `docs/adrs/0005-gui-native-launcher-in-portable-bundle.md`
- 关联文档：
  - `docs/adrs/0001-offline-portable-bundle-baseline.md`
  - `docs/adrs/0005-gui-native-launcher-in-portable-bundle.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/guides/win7-gui-validation.md`
- 是否需要 ADR：是；native launcher exe changes the long-lived bundle entry-point strategy while preserving the portable bundle baseline.
```

- [ ] **Step 6: Run doc-oriented checks**

Run:

```bash
uv run pytest tests/test_gui_launcher_exe_contract.py tests/test_gui_smoke_contract.py -q
```

Expected: PASS.

Run:

```bash
rg -n "EmbedAgent.exe|embedagent-gui.exe|build-gui-launcher|0005-gui-native" README.md docs scripts tests
```

Expected: results appear in source, packaging docs, ADR, validation guide, and tests.

- [ ] **Step 7: Commit documentation updates**

```bash
git add README.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/modules/packaging-and-deployment.md docs/guides/win7-gui-validation.md docs/development-tracker.md docs/design-change-log.md docs/adrs/0005-gui-native-launcher-in-portable-bundle.md
git commit -m "docs: document native GUI bundle launcher"
```

---

### Task 7: End-To-End Verification And Release-Gate Notes

**Files:**
- No required source changes unless verification exposes a defect.

- [ ] **Step 1: Run Python and packaging contract tests**

Run:

```bash
uv run pytest tests/test_gui_launcher_exe_contract.py tests/test_gui_smoke_contract.py tests/test_packaging_control_plane.py -q
```

Expected: PASS on Windows with PowerShell available. On non-Windows, Windows-only packaging tests are skipped according to their decorators.

- [ ] **Step 2: Run lint checks for touched Python tests/scripts**

Run:

```bash
uv run ruff check tests/test_gui_launcher_exe_contract.py tests/test_gui_smoke_contract.py tests/test_packaging_control_plane.py scripts/check-bundle-dependencies.py scripts/validate-gui-smoke.py
```

Expected: PASS.

- [ ] **Step 3: Build the launcher if a compiler is available**

Run:

```powershell
pwsh -File scripts/build-gui-launcher.ps1
```

Expected with compiler configured: `build/offline-cache/gui-launcher/embedagent-gui.exe` exists.

If it fails with `No launcher compiler found`, record that local verification could not compile the launcher on this machine. Do not claim compiled-launcher verification passed.

- [ ] **Step 4: Run dev assemble when offline assets are available**

Run:

```powershell
pwsh -File scripts/package.ps1 assemble -Profile dev
```

Expected when required offline assets and launcher compiler are available: assemble succeeds and `build/offline-dist/embedagent-win7-x64-dev\EmbedAgent.exe` exists.

If offline asset cache or compiler is unavailable, record the exact blocker from the command output.

- [ ] **Step 5: Run bundle verification when assemble succeeds**

Run:

```powershell
pwsh -File scripts/package.ps1 verify -Profile dev
```

Expected: PASS or DEV_ONLY-compatible result for dev profile.

For release builds:

```powershell
pwsh -File scripts/package.ps1 release -Profile release
```

Expected when all release assets are present: READY.

- [ ] **Step 6: Run native launcher help checks from the bundle root**

When a bundle has been assembled:

```cmd
cd build\offline-dist\embedagent-win7-x64-dev
EmbedAgent.exe --help
embedagent-gui.exe --help
embedagent-gui.cmd --help
```

Expected: each returns exit code `0`.

- [ ] **Step 7: Run GUI smoke if a runnable bundle exists**

Run:

```cmd
validate-gui-smoke.cmd
```

Expected: JSON includes `assistant_text` containing `GUI smoke reply`, tool events, permission/user-input flows, and `/review` success.

On real Windows 7:

```cmd
validate-gui-smoke.cmd --windowed --auto-close-seconds 8
```

Expected: `renderer_report.renderer == "edgechromium"` and `renderer_report.runtime_source == "bundle"`.

- [ ] **Step 8: Final status check**

Run:

```bash
git status --short
```

Expected: clean worktree after all task commits.

If any verification was skipped because a compiler, offline asset cache, or real Win7 host was unavailable, include that explicitly in the final implementation summary.
