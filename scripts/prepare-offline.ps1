[CmdletBinding()]
param(
    [string]$PythonRuntimeRoot = "",
    [string]$SitePackagesRoot = "",
    [string]$MinGitRoot = "",
    [string]$RipgrepPath = "",
    [string]$CtagsPath = "",
    [string]$LlvmRoot = "",
    [switch]$SkipBuild,
    [switch]$Clean
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-ProjectPath {
    param(
        [string]$ProjectRoot,
        [string]$Value
    )

    if (-not $Value) {
        return $null
    }

    $candidate = $Value
    if (-not [System.IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path $ProjectRoot $candidate
    }
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "Path not found: $Value"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Ensure-Directory {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Assert-ChildPath {
    param(
        [string]$Root,
        [string]$Child
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    $resolvedChild = (Resolve-Path -LiteralPath $Child).Path
    $prefix = $resolvedRoot.TrimEnd('\') + '\'
    if (
        ($resolvedChild -ne $resolvedRoot) -and
        (-not $resolvedChild.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase))
    ) {
        throw "Refusing to operate outside root. Root=$resolvedRoot Child=$resolvedChild"
    }
}

function Reset-Directory {
    param(
        [string]$Root,
        [string]$Target
    )

    Ensure-Directory -Path $Root
    if (Test-Path -LiteralPath $Target) {
        Assert-ChildPath -Root $Root -Child $Target
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
}

function Stage-Directory {
    param(
        [string]$Source,
        [string]$Destination
    )

    $parent = Split-Path -Parent $Destination
    Ensure-Directory -Path $parent
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Stage-File {
    param(
        [string]$Source,
        [string]$Destination
    )

    $parent = Split-Path -Parent $Destination
    Ensure-Directory -Path $parent
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Remove-TransientPythonArtifacts {
    param(
        [string]$Root
    )

    if (-not (Test-Path -LiteralPath $Root)) {
        return
    }

    Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force |
        Where-Object { $_.Name -eq '__pycache__' } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }

    Get-ChildItem -LiteralPath $Root -Recurse -File -Force |
        Where-Object { $_.Extension -in '.pyc', '.pyo' } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
        }
}

function Write-TextFile {
    param(
        [string]$Path,
        [string]$Content
    )

    $parent = Split-Path -Parent $Path
    Ensure-Directory -Path $parent
    Set-Content -LiteralPath $Path -Value $Content -Encoding ASCII
}

function New-ComponentRecord {
    param(
        [string]$Name,
        [string]$StagedPath,
        [bool]$Required,
        [string]$Status,
        [string]$SourcePath,
        [string]$Notes
    )

    return [ordered]@{
        name = $Name
        staged_path = $StagedPath
        required = $Required
        status = $Status
        source_path = $SourcePath
        notes = $Notes
    }
}

function Coalesce-String {
    param(
        [string]$Value
    )

    if ($null -eq $Value) {
        return ''
    }
    return $Value
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$buildRoot = Join-Path $projectRoot 'build'
$cacheRoot = Join-Path $buildRoot 'offline-cache'
$stagingRoot = Join-Path $buildRoot 'offline-staging'
$distRoot = Join-Path $buildRoot 'offline-dist'
$bundleRoot = Join-Path $stagingRoot 'EmbedAgent'

Ensure-Directory -Path $buildRoot
Ensure-Directory -Path $cacheRoot
Ensure-Directory -Path $distRoot

if ($Clean) {
    Reset-Directory -Root $stagingRoot -Target $bundleRoot
}
else {
    Reset-Directory -Root $stagingRoot -Target $bundleRoot
}

$paths = @(
    'app',
    'bin',
    'bin\git',
    'bin\rg',
    'bin\ctags',
    'bin\llvm',
    'config',
    'data',
    'data\workspace-template',
    'docs',
    'manifests',
    'manifests\licenses',
    'runtime',
    'runtime\python',
    'runtime\site-packages'
)
foreach ($relative in $paths) {
    Ensure-Directory -Path (Join-Path $bundleRoot $relative)
}

$sourceAppRoot = Join-Path $projectRoot 'src\embedagent'
$stagedAppRoot = Join-Path $bundleRoot 'app\embedagent'
Stage-Directory -Source $sourceAppRoot -Destination $stagedAppRoot
Remove-TransientPythonArtifacts -Root $stagedAppRoot

$configurationGuide = Join-Path $projectRoot 'docs\configuration-guide.md'
$preflightGuide = Join-Path $projectRoot 'docs\win7-preflight-checklist.md'
Stage-File -Source $configurationGuide -Destination (Join-Path $bundleRoot 'docs\configuration-guide.md')
Stage-File -Source $preflightGuide -Destination (Join-Path $bundleRoot 'docs\win7-preflight-checklist.md')

$defaultConfig = @'
{
  "base_url": "http://127.0.0.1:8000/v1",
  "api_key": "",
  "model": "",
  "timeout": 120,
  "default_mode": "code"
}
'@
Write-TextFile -Path (Join-Path $bundleRoot 'config\config.json') -Content $defaultConfig.Trim() + "`r`n"

$defaultPermissionRules = @'
{
  "schema_version": 1,
  "rules": []
}
'@
Write-TextFile -Path (Join-Path $bundleRoot 'config\permission-rules.json') -Content $defaultPermissionRules.Trim() + "`r`n"

$workspaceTemplateReadme = @'
This directory is a placeholder for an unpacked demo or smoke-test workspace.
Copy or replace it with a real project before first use.
'@
Write-TextFile -Path (Join-Path $bundleRoot 'data\workspace-template\README.txt') -Content $workspaceTemplateReadme.Trim() + "`r`n"

$launcherCli = @'
@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "EMBEDAGENT_BUNDLE_ROOT=%BUNDLE_ROOT%"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PATH=%BUNDLE_ROOT%bin\git\cmd;%BUNDLE_ROOT%bin\git\bin;%BUNDLE_ROOT%bin\rg;%BUNDLE_ROOT%bin\ctags;%BUNDLE_ROOT%bin\llvm\bin;%BUNDLE_ROOT%bin\llvm\libexec;%PATH%"
"%BUNDLE_ROOT%runtime\python\python.exe" -m embedagent %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent.cmd') -Content $launcherCli.Trim() + "`r`n"

$launcherTui = @'
@echo off
setlocal
call "%~dp0embedagent.cmd" --tui %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent-tui.cmd') -Content $launcherTui.Trim() + "`r`n"

$licensesReadme = @'
Third-party license files should be copied into this directory during the full
offline bundle build. This placeholder exists so the staging layout is stable
before external assets are collected.
'@
Write-TextFile -Path (Join-Path $bundleRoot 'manifests\licenses\README.txt') -Content $licensesReadme.Trim() + "`r`n"

$defaultLlvmRoot = Join-Path $projectRoot 'toolchains\llvm\current'
if (-not $LlvmRoot -and (Test-Path -LiteralPath $defaultLlvmRoot)) {
    $LlvmRoot = $defaultLlvmRoot
}
if (-not $SitePackagesRoot) {
    $candidateSitePackages = Join-Path $projectRoot '.venv\Lib\site-packages'
    if (Test-Path -LiteralPath $candidateSitePackages) {
        $SitePackagesRoot = $candidateSitePackages
    }
}

$pythonRuntimePath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $PythonRuntimeRoot
$sitePackagesPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $SitePackagesRoot
$minGitPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $MinGitRoot
$ripgrepResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $RipgrepPath
$ctagsResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $CtagsPath
$llvmPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $LlvmRoot

$components = @()
$components += New-ComponentRecord -Name 'app_code' -StagedPath 'app\embedagent' -Required $true -Status 'staged' -SourcePath $sourceAppRoot -Notes 'Copied from src/embedagent.'
$components += New-ComponentRecord -Name 'docs_bundle' -StagedPath 'docs' -Required $true -Status 'staged' -SourcePath (Join-Path $projectRoot 'docs') -Notes 'Copied configuration and preflight docs.'
$components += New-ComponentRecord -Name 'config_templates' -StagedPath 'config' -Required $true -Status 'staged' -SourcePath '' -Notes 'Generated default config and permission rules templates.'
$components += New-ComponentRecord -Name 'launcher_scripts' -StagedPath '.' -Required $true -Status 'staged' -SourcePath '' -Notes 'Generated embedagent.cmd and embedagent-tui.cmd.'

if ((-not $SkipBuild) -and $pythonRuntimePath) {
    Stage-Directory -Source $pythonRuntimePath -Destination (Join-Path $bundleRoot 'runtime\python')
    $components += New-ComponentRecord -Name 'python_runtime' -StagedPath 'runtime\python' -Required $true -Status 'staged' -SourcePath $pythonRuntimePath -Notes 'Copied embeddable Python runtime.'
}
else {
    $status = 'missing'
    $notes = 'Provide -PythonRuntimeRoot to stage the embeddable Python runtime.'
    if ($SkipBuild -and $pythonRuntimePath) {
        $status = 'skipped'
        $notes = 'Runtime copy skipped by -SkipBuild.'
    }
    $components += New-ComponentRecord -Name 'python_runtime' -StagedPath 'runtime\python' -Required $true -Status $status -SourcePath (Coalesce-String -Value $pythonRuntimePath) -Notes $notes
}

if ((-not $SkipBuild) -and $sitePackagesPath) {
    Stage-Directory -Source $sitePackagesPath -Destination (Join-Path $bundleRoot 'runtime\site-packages')
    $components += New-ComponentRecord -Name 'python_packages' -StagedPath 'runtime\site-packages' -Required $true -Status 'staged' -SourcePath $sitePackagesPath -Notes 'Copied vendored site-packages root.'
}
else {
    $status = 'missing'
    $notes = 'Provide -SitePackagesRoot or rely on a future export step.'
    if ($SkipBuild -and $sitePackagesPath) {
        $status = 'skipped'
        $notes = 'Site-packages copy skipped by -SkipBuild.'
    }
    $components += New-ComponentRecord -Name 'python_packages' -StagedPath 'runtime\site-packages' -Required $true -Status $status -SourcePath (Coalesce-String -Value $sitePackagesPath) -Notes $notes
}

if ((-not $SkipBuild) -and $minGitPath) {
    Stage-Directory -Source $minGitPath -Destination (Join-Path $bundleRoot 'bin\git')
    $components += New-ComponentRecord -Name 'mingit_portable' -StagedPath 'bin\git' -Required $true -Status 'staged' -SourcePath $minGitPath -Notes 'Copied MinGit/Portable Git root.'
}
else {
    $status = 'missing'
    $notes = 'Provide -MinGitRoot to stage bundled Git.'
    if ($SkipBuild -and $minGitPath) {
        $status = 'skipped'
        $notes = 'Git copy skipped by -SkipBuild.'
    }
    $components += New-ComponentRecord -Name 'mingit_portable' -StagedPath 'bin\git' -Required $true -Status $status -SourcePath (Coalesce-String -Value $minGitPath) -Notes $notes
}

if ((-not $SkipBuild) -and $ripgrepResolved) {
    if ((Get-Item -LiteralPath $ripgrepResolved).PSIsContainer) {
        Stage-Directory -Source $ripgrepResolved -Destination (Join-Path $bundleRoot 'bin\rg')
    }
    else {
        Stage-File -Source $ripgrepResolved -Destination (Join-Path $bundleRoot 'bin\rg\rg.exe')
    }
    $components += New-ComponentRecord -Name 'ripgrep' -StagedPath 'bin\rg' -Required $true -Status 'staged' -SourcePath $ripgrepResolved -Notes 'Copied ripgrep executable or directory.'
}
else {
    $status = 'missing'
    $notes = 'Provide -RipgrepPath to stage rg.exe.'
    if ($SkipBuild -and $ripgrepResolved) {
        $status = 'skipped'
        $notes = 'ripgrep copy skipped by -SkipBuild.'
    }
    $components += New-ComponentRecord -Name 'ripgrep' -StagedPath 'bin\rg' -Required $true -Status $status -SourcePath (Coalesce-String -Value $ripgrepResolved) -Notes $notes
}

if ((-not $SkipBuild) -and $ctagsResolved) {
    if ((Get-Item -LiteralPath $ctagsResolved).PSIsContainer) {
        Stage-Directory -Source $ctagsResolved -Destination (Join-Path $bundleRoot 'bin\ctags')
    }
    else {
        Stage-File -Source $ctagsResolved -Destination (Join-Path $bundleRoot 'bin\ctags\ctags.exe')
    }
    $components += New-ComponentRecord -Name 'universal_ctags' -StagedPath 'bin\ctags' -Required $true -Status 'staged' -SourcePath $ctagsResolved -Notes 'Copied Universal Ctags executable or directory.'
}
else {
    $status = 'missing'
    $notes = 'Provide -CtagsPath to stage ctags.exe.'
    if ($SkipBuild -and $ctagsResolved) {
        $status = 'skipped'
        $notes = 'Universal Ctags copy skipped by -SkipBuild.'
    }
    $components += New-ComponentRecord -Name 'universal_ctags' -StagedPath 'bin\ctags' -Required $true -Status $status -SourcePath (Coalesce-String -Value $ctagsResolved) -Notes $notes
}

if ((-not $SkipBuild) -and $llvmPath) {
    Stage-Directory -Source $llvmPath -Destination (Join-Path $bundleRoot 'bin\llvm')
    $components += New-ComponentRecord -Name 'llvm_clang_bundle' -StagedPath 'bin\llvm' -Required $true -Status 'staged' -SourcePath $llvmPath -Notes 'Copied current LLVM/Clang bundle; composition remains provisional until Win7 validation.'
}
else {
    $status = 'missing'
    $notes = 'Provide -LlvmRoot to stage the LLVM/Clang bundle.'
    if ($SkipBuild -and $llvmPath) {
        $status = 'skipped'
        $notes = 'LLVM copy skipped by -SkipBuild.'
    }
    $components += New-ComponentRecord -Name 'llvm_clang_bundle' -StagedPath 'bin\llvm' -Required $true -Status $status -SourcePath (Coalesce-String -Value $llvmPath) -Notes $notes
}

$requiredMissing = @($components | Where-Object { $_.required -and $_.status -eq 'missing' })
$summary = [ordered]@{
    staged = @($components | Where-Object { $_.status -eq 'staged' }).Count
    skipped = @($components | Where-Object { $_.status -eq 'skipped' }).Count
    missing = $requiredMissing.Count
}

$manifest = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    project_root = $projectRoot
    build_root = $buildRoot
    bundle_root = $bundleRoot
    skip_build = [bool]$SkipBuild
    summary = $summary
    components = $components
}

$manifestPath = Join-Path $bundleRoot 'manifests\bundle-manifest.json'
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding ASCII

$checksumPath = Join-Path $bundleRoot 'manifests\checksums.txt'
$filesToHash = Get-ChildItem -LiteralPath $bundleRoot -Recurse -File |
    Where-Object { $_.FullName -ne $checksumPath } |
    Sort-Object FullName
$checksumLines = @()
foreach ($file in $filesToHash) {
    $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
    $relative = $file.FullName.Substring($bundleRoot.Length).TrimStart('\')
    $checksumLines += ('{0} *{1}' -f $hash.Hash.ToLowerInvariant(), $relative.Replace('\', '/'))
}
Set-Content -LiteralPath $checksumPath -Value $checksumLines -Encoding ASCII

Write-Host ('Prepared offline staging bundle at {0}' -f $bundleRoot)
Write-Host ('Required components missing: {0}' -f $requiredMissing.Count)
foreach ($item in $requiredMissing) {
    Write-Host ('  - {0}: {1}' -f $item.name, $item.notes)
}
