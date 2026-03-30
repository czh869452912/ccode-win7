[CmdletBinding()]
param(
    [string]$AssetManifestPath = "scripts/offline-assets.json",
    [string[]]$AssetIds = @(),
    [switch]$AllowDownload,
    [string]$PythonRuntimeRoot = "",
    [string]$SitePackagesRoot = "",
    [string]$MinGitRoot = "",
    [string]$RipgrepPath = "",
    [string]$CtagsPath = "",
    [string]$WebView2RuntimeRoot = "",
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
        Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $Target) {
            throw "Failed to reset directory: $Target"
        }
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
        [string]$Notes,
        [string]$AssetId
    )

    return [ordered]@{
        name = $Name
        staged_path = $StagedPath
        required = $Required
        status = $Status
        source_path = $SourcePath
        notes = $Notes
        asset_id = $AssetId
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

function Normalize-AssetIds {
    param(
        [string[]]$AssetIds
    )

    $normalized = @()
    foreach ($item in @($AssetIds)) {
        if (-not $item) {
            continue
        }
        $parts = @($item -split ',')
        foreach ($part in $parts) {
            $value = ($part | ForEach-Object { "$_".Trim() })
            if ($value) {
                $normalized += $value
            }
        }
    }
    return $normalized
}

function Load-AssetManifest {
    param(
        [string]$ManifestPath
    )

    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        throw "Asset manifest not found: $ManifestPath"
    }

    $payload = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if (-not $payload.assets) {
        throw "Asset manifest does not contain an assets array."
    }
    return $payload
}

function Find-AssetRecord {
    param(
        [object]$Manifest,
        [string]$AssetId
    )

    foreach ($asset in @($Manifest.assets)) {
        if ($asset.id -eq $AssetId) {
            return $asset
        }
    }
    throw "Asset id not found in manifest: $AssetId"
}

function Get-AssetCachePath {
    param(
        [string]$CacheRoot,
        [object]$Asset
    )

    return Join-Path $CacheRoot $Asset.cache_relpath
}

function Test-FileSha256 {
    param(
        [string]$Path,
        [string]$ExpectedSha256
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $actual -eq $ExpectedSha256.ToLowerInvariant()
}

function Download-AssetArchive {
    param(
        [object]$Asset,
        [string]$TargetPath
    )

    $parent = Split-Path -Parent $TargetPath
    Ensure-Directory -Path $parent
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Asset.upstream_url -OutFile $TargetPath -UseBasicParsing
}

function Extract-ZipArchive {
    param(
        [string]$ArchivePath,
        [string]$DestinationRoot,
        [string]$DestinationPath
    )

    Reset-Directory -Root $DestinationRoot -Target $DestinationPath
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $DestinationPath -Force
}

function Promote-ExtractedSubdirectory {
    param(
        [string]$Root,
        [string]$SubdirectoryRelpath
    )

    if (-not $SubdirectoryRelpath) {
        return
    }

    $normalized = $SubdirectoryRelpath.Replace('/', '\')
    $nestedRoot = Join-Path $Root $normalized
    if (-not (Test-Path -LiteralPath $nestedRoot)) {
        throw "Extracted asset subdirectory not found: $nestedRoot"
    }

    $tempRoot = Join-Path (Split-Path -Parent $Root) ([System.IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    Copy-Item -Path (Join-Path $nestedRoot '*') -Destination $tempRoot -Recurse -Force

    Get-ChildItem -LiteralPath $Root -Force | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
    Get-ChildItem -LiteralPath $tempRoot -Force | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination $Root -Force
    }
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}

function Normalize-ExtractedRoot {
    param(
        [string]$Root
    )

    if (-not (Test-Path -LiteralPath $Root)) {
        return
    }

    $items = @(Get-ChildItem -LiteralPath $Root -Force)
    $directories = @($items | Where-Object { $_.PSIsContainer })
    $files = @($items | Where-Object { -not $_.PSIsContainer })

    if ($directories.Count -ne 1 -or $files.Count -ne 0) {
        return
    }

    $nestedRoot = $directories[0].FullName
    $nestedItems = @(Get-ChildItem -LiteralPath $nestedRoot -Force)
    foreach ($item in $nestedItems) {
        Move-Item -LiteralPath $item.FullName -Destination $Root -Force
    }
    Remove-Item -LiteralPath $nestedRoot -Recurse -Force
}

function Patch-EmbeddablePython {
    param(
        [string]$PythonRoot
    )

    $pthFile = Get-ChildItem -LiteralPath $PythonRoot -Filter 'python*._pth' -File | Select-Object -First 1
    if (-not $pthFile) {
        throw "Embeddable Python ._pth file not found under $PythonRoot"
    }

    $zipFile = Get-ChildItem -LiteralPath $PythonRoot -Filter 'python*.zip' -File | Select-Object -First 1
    if (-not $zipFile) {
        throw "Embeddable Python standard-library zip not found under $PythonRoot"
    }

    $lines = @(
        $zipFile.Name,
        '.',
        '..\site-packages',
        '..\..\app',
        'import site'
    )
    Write-TextFile -Path $pthFile.FullName -Content ([string]::Join("`r`n", $lines) + "`r`n")
}

function Get-LicensePrefix {
    param(
        [object]$Asset
    )

    switch ($Asset.kind) {
        'python_runtime' { return 'python' }
        'git_portable' { return 'mingit' }
        'search_tool' { return 'ripgrep' }
        'symbol_indexer' { return 'ctags' }
        'webview2_runtime' { return 'webview2' }
        default { return $Asset.id }
    }
}

function Write-LicenseNotice {
    param(
        [string]$LicenseDir,
        [string]$Prefix,
        [object]$Asset
    )

    $safeVersion = ($Asset.version -replace '[^0-9A-Za-z\.-]', '_')
    $path = Join-Path $LicenseDir ($Prefix + '-' + $safeVersion + '.txt')
    $content = @(
        ('asset_id: ' + $Asset.id),
        ('version: ' + $Asset.version),
        ('upstream_url: ' + $Asset.upstream_url),
        ('license_name: ' + $Asset.license_name),
        ('license_url: ' + $Asset.license_url),
        ('sha256: ' + $Asset.sha256),
        ('notes: ' + $Asset.notes)
    )
    Write-TextFile -Path $path -Content ([string]::Join("`r`n", $content) + "`r`n")
}

function Resolve-AssetForStaging {
    param(
        [object]$Asset,
        [string]$CacheRoot,
        [string]$BundleRoot,
        [string]$LicenseDir,
        [bool]$AllowDownload,
        [bool]$SkipBuild
    )

    $cacheArchivePath = Get-AssetCachePath -CacheRoot $CacheRoot -Asset $Asset
    $stagedPath = Join-Path $BundleRoot $Asset.stage_relpath

    if (-not (Test-Path -LiteralPath $cacheArchivePath)) {
        if ($SkipBuild) {
            return [ordered]@{
                asset_id = $Asset.id
                status = 'missing'
                notes = 'Cached archive missing and -SkipBuild is set.'
                cache_archive_path = $cacheArchivePath
                staged_path = $stagedPath
            }
        }
        if (-not $AllowDownload) {
            return [ordered]@{
                asset_id = $Asset.id
                status = 'missing'
                notes = 'Cached archive missing; rerun with -AllowDownload or seed offline-cache manually.'
                cache_archive_path = $cacheArchivePath
                staged_path = $stagedPath
            }
        }
        Download-AssetArchive -Asset $Asset -TargetPath $cacheArchivePath
    }

    if (-not (Test-FileSha256 -Path $cacheArchivePath -ExpectedSha256 $Asset.sha256)) {
        throw "SHA256 mismatch for asset $($Asset.id): $cacheArchivePath"
    }

    if (-not $SkipBuild) {
        if ($Asset.archive_type -notin @('zip', 'nupkg')) {
            throw "Unsupported archive_type '$($Asset.archive_type)' for asset $($Asset.id)"
        }
        Extract-ZipArchive -ArchivePath $cacheArchivePath -DestinationRoot $BundleRoot -DestinationPath $stagedPath
        if ($Asset.PSObject.Properties.Name -contains 'extract_subdir_relpath') {
            Promote-ExtractedSubdirectory -Root $stagedPath -SubdirectoryRelpath ([string]$Asset.extract_subdir_relpath)
        }
        Normalize-ExtractedRoot -Root $stagedPath
        if ($Asset.kind -eq 'python_runtime') {
            Patch-EmbeddablePython -PythonRoot $stagedPath
        }
        $licensePrefix = Get-LicensePrefix -Asset $Asset
        Write-LicenseNotice -LicenseDir $LicenseDir -Prefix $licensePrefix -Asset $Asset
        return [ordered]@{
            asset_id = $Asset.id
            status = 'staged'
            notes = 'Asset extracted from offline-cache.'
            cache_archive_path = $cacheArchivePath
            staged_path = $stagedPath
        }
    }

    return [ordered]@{
        asset_id = $Asset.id
        status = 'cached'
        notes = 'Asset archive verified in offline-cache; extraction skipped by -SkipBuild.'
        cache_archive_path = $cacheArchivePath
        staged_path = $stagedPath
    }
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$assetManifestResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $AssetManifestPath
$buildRoot = Join-Path $projectRoot 'build'
$cacheRoot = Join-Path $buildRoot 'offline-cache'
$stagingRoot = Join-Path $buildRoot 'offline-staging'
$distRoot = Join-Path $buildRoot 'offline-dist'
$bundleRoot = Join-Path $stagingRoot 'EmbedAgent'
$licenseDir = Join-Path $bundleRoot 'manifests\licenses'

Ensure-Directory -Path $buildRoot
Ensure-Directory -Path $cacheRoot
Ensure-Directory -Path $distRoot
Reset-Directory -Root $stagingRoot -Target $bundleRoot

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
    'runtime\site-packages',
    'runtime\webview2-fixed-runtime',
    'tools',
    'tools\validation'
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
$intranetGuide = Join-Path $projectRoot 'docs\intranet-deployment.md'
$win7GuiGuide = Join-Path $projectRoot 'docs\win7-gui-validation.md'
Stage-File -Source $configurationGuide -Destination (Join-Path $bundleRoot 'docs\configuration-guide.md')
Stage-File -Source $preflightGuide -Destination (Join-Path $bundleRoot 'docs\win7-preflight-checklist.md')
if (Test-Path -LiteralPath $intranetGuide) {
    Stage-File -Source $intranetGuide -Destination (Join-Path $bundleRoot 'docs\intranet-deployment.md')
}
if (Test-Path -LiteralPath $win7GuiGuide) {
    Stage-File -Source $win7GuiGuide -Destination (Join-Path $bundleRoot 'docs\win7-gui-validation.md')
}

$guiSmokeScript = Join-Path $projectRoot 'scripts\validate-gui-smoke.py'
if (Test-Path -LiteralPath $guiSmokeScript) {
    Stage-File -Source $guiSmokeScript -Destination (Join-Path $bundleRoot 'tools\validation\validate-gui-smoke.py')
}

$defaultConfig = @'
{
  "_comment": "EmbedAgent Configuration - Update for your internal LLM service",
  "base_url": "http://192.168.1.100:8000/v1",
  "api_key": "sk-internal",
  "model": "qwen3.5-coder",
  "timeout": 120,
  "max_context_tokens": 32000,
  "reserve_output_tokens": 3000,
  "chars_per_token": 3.0,
  "max_turns": 8,
  "default_mode": "code"
}
'@
Write-TextFile -Path (Join-Path $bundleRoot 'config\config.json.template') -Content ($defaultConfig.Trim() + "`r`n")

# Also create a minimal config.json for quick start
$minimalConfig = @'
{
  "base_url": "http://192.168.1.100:8000/v1",
  "api_key": "",
  "model": "",
  "timeout": 120,
  "default_mode": "code"
}
'@
Write-TextFile -Path (Join-Path $bundleRoot 'config\config.json') -Content ($minimalConfig.Trim() + "`r`n")

$defaultPermissionRules = @'
{
  "schema_version": 1,
  "rules": []
}
'@
Write-TextFile -Path (Join-Path $bundleRoot 'config\permission-rules.json') -Content ($defaultPermissionRules.Trim() + "`r`n")

$workspaceTemplateReadme = @'
This directory is a placeholder for an unpacked demo or smoke-test workspace.
Copy or replace it with a real project before first use.
'@
Write-TextFile -Path (Join-Path $bundleRoot 'data\workspace-template\README.txt') -Content ($workspaceTemplateReadme.Trim() + "`r`n")

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
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent.cmd') -Content ($launcherCli.Trim() + "`r`n")

$launcherTui = @'
@echo off
setlocal
call "%~dp0embedagent.cmd" --tui %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent-tui.cmd') -Content ($launcherTui.Trim() + "`r`n")

$launcherGui = @'
@echo off
setlocal EnableDelayedExpansion

set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"

set "PATH=%BUNDLE_ROOT%bin\git\cmd;%BUNDLE_ROOT%bin\rg;%BUNDLE_ROOT%bin\ctags;%BUNDLE_ROOT%bin\llvm\bin;%PATH%"

if not defined EMBEDAGENT_HOME (
    set "EMBEDAGENT_HOME=%USERPROFILE%\.embedagent"
)

if not exist "%PYTHONHOME%\python.exe" (
    echo Error: Python runtime not found in %PYTHONHOME%
    exit /b 1
)

if not exist "%BUNDLE_ROOT%runtime\webview2-fixed-runtime\msedgewebview2.exe" (
    echo Error: Bundled Fixed Version WebView2 runtime not found.
    echo GUI no longer falls back to IE11. Please use TUI/CLI or repair the bundle.
    exit /b 1
)

"%PYTHONHOME%\python.exe" -m embedagent.frontend.gui.launcher %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent-gui.cmd') -Content ($launcherGui.Trim() + "`r`n")

$launcherGuiSmoke = @'
@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
"%PYTHONHOME%\python.exe" "%BUNDLE_ROOT%tools\validation\validate-gui-smoke.py" --bundle-root "%BUNDLE_ROOT%" %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'validate-gui-smoke.cmd') -Content ($launcherGuiSmoke.Trim() + "`r`n")

$licensesReadme = @'
Third-party license notices for bundled assets are written here during prepare.
'@
Write-TextFile -Path (Join-Path $licenseDir 'README.txt') -Content ($licensesReadme.Trim() + "`r`n")

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

$normalizedAssetIds = Normalize-AssetIds -AssetIds $AssetIds
$assetManifest = Load-AssetManifest -ManifestPath $assetManifestResolved
$requestedAssetIds = @($normalizedAssetIds)
$resolvedAssets = @()
$components = @()

$pythonRuntimePath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $PythonRuntimeRoot
$sitePackagesPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $SitePackagesRoot
$minGitPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $MinGitRoot
$ripgrepResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $RipgrepPath
$ctagsResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $CtagsPath
$webView2RuntimePath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $WebView2RuntimeRoot
$llvmPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $LlvmRoot

$components += New-ComponentRecord -Name 'app_code' -StagedPath 'app\embedagent' -Required $true -Status 'staged' -SourcePath $sourceAppRoot -Notes 'Copied from src/embedagent.' -AssetId ''
$components += New-ComponentRecord -Name 'docs_bundle' -StagedPath 'docs' -Required $true -Status 'staged' -SourcePath (Join-Path $projectRoot 'docs') -Notes 'Copied configuration, preflight, intranet, and Win7 GUI validation docs.' -AssetId ''
$components += New-ComponentRecord -Name 'config_templates' -StagedPath 'config' -Required $true -Status 'staged' -SourcePath '' -Notes 'Generated default config and permission rules templates.' -AssetId ''
$components += New-ComponentRecord -Name 'launcher_scripts' -StagedPath '.' -Required $true -Status 'staged' -SourcePath '' -Notes 'Generated embedagent.cmd, embedagent-tui.cmd, embedagent-gui.cmd, and validate-gui-smoke.cmd.' -AssetId ''
$components += New-ComponentRecord -Name 'validation_tools' -StagedPath 'tools\validation' -Required $true -Status 'staged' -SourcePath $guiSmokeScript -Notes 'Copied bundle-local GUI smoke validation script.' -AssetId ''

$usePythonAsset = $requestedAssetIds -contains 'python_embedded_x64'
if ($usePythonAsset) {
    $pythonAsset = Find-AssetRecord -Manifest $assetManifest -AssetId 'python_embedded_x64'
    $resolved = Resolve-AssetForStaging -Asset $pythonAsset -CacheRoot $cacheRoot -BundleRoot $bundleRoot -LicenseDir $licenseDir -AllowDownload ([bool]$AllowDownload) -SkipBuild ([bool]$SkipBuild)
    $resolvedAssets += [ordered]@{
        id = $pythonAsset.id
        version = $pythonAsset.version
        kind = $pythonAsset.kind
        platform = $pythonAsset.platform
        upstream_url = $pythonAsset.upstream_url
        sha256 = $pythonAsset.sha256
        archive_type = $pythonAsset.archive_type
        cache_relpath = $pythonAsset.cache_relpath
        stage_relpath = $pythonAsset.stage_relpath
        license_name = $pythonAsset.license_name
        license_url = $pythonAsset.license_url
        notes = $pythonAsset.notes
        cache_archive_path = $resolved.cache_archive_path
        staged_path = $resolved.staged_path
        source_mode = 'asset_manifest'
        status = $resolved.status
    }
    $components += New-ComponentRecord -Name 'python_runtime' -StagedPath $pythonAsset.stage_relpath -Required $true -Status $resolved.status -SourcePath $resolved.cache_archive_path -Notes $resolved.notes -AssetId $pythonAsset.id
}
elseif ($pythonRuntimePath) {
    if (-not $SkipBuild) {
        Stage-Directory -Source $pythonRuntimePath -Destination (Join-Path $bundleRoot 'runtime\python')
        Patch-EmbeddablePython -PythonRoot (Join-Path $bundleRoot 'runtime\python')
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'Manual runtime path provided; extraction skipped by -SkipBuild.' } else { 'Copied embeddable Python runtime from manual path.' }
    $components += New-ComponentRecord -Name 'python_runtime' -StagedPath 'runtime\python' -Required $true -Status $status -SourcePath $pythonRuntimePath -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'python_runtime' -StagedPath 'runtime\python' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -PythonRuntimeRoot or request python_embedded_x64 via -AssetIds.' -AssetId ''
}

if ($sitePackagesPath) {
    if (-not $SkipBuild) {
        Stage-Directory -Source $sitePackagesPath -Destination (Join-Path $bundleRoot 'runtime\site-packages')
        Remove-TransientPythonArtifacts -Root (Join-Path $bundleRoot 'runtime\site-packages')
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'Site-packages copy skipped by -SkipBuild.' } else { 'Copied vendored site-packages root.' }
    $components += New-ComponentRecord -Name 'python_packages' -StagedPath 'runtime\site-packages' -Required $true -Status $status -SourcePath $sitePackagesPath -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'python_packages' -StagedPath 'runtime\site-packages' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -SitePackagesRoot or rely on a future export step.' -AssetId ''
}

$useMinGitAsset = $requestedAssetIds -contains 'mingit_x64'
if ($useMinGitAsset) {
    $gitAsset = Find-AssetRecord -Manifest $assetManifest -AssetId 'mingit_x64'
    $resolved = Resolve-AssetForStaging -Asset $gitAsset -CacheRoot $cacheRoot -BundleRoot $bundleRoot -LicenseDir $licenseDir -AllowDownload ([bool]$AllowDownload) -SkipBuild ([bool]$SkipBuild)
    $resolvedAssets += [ordered]@{
        id = $gitAsset.id
        version = $gitAsset.version
        kind = $gitAsset.kind
        platform = $gitAsset.platform
        upstream_url = $gitAsset.upstream_url
        sha256 = $gitAsset.sha256
        archive_type = $gitAsset.archive_type
        cache_relpath = $gitAsset.cache_relpath
        stage_relpath = $gitAsset.stage_relpath
        license_name = $gitAsset.license_name
        license_url = $gitAsset.license_url
        notes = $gitAsset.notes
        cache_archive_path = $resolved.cache_archive_path
        staged_path = $resolved.staged_path
        source_mode = 'asset_manifest'
        status = $resolved.status
    }
    $components += New-ComponentRecord -Name 'mingit_portable' -StagedPath $gitAsset.stage_relpath -Required $true -Status $resolved.status -SourcePath $resolved.cache_archive_path -Notes $resolved.notes -AssetId $gitAsset.id
}
elseif ($minGitPath) {
    if (-not $SkipBuild) {
        Stage-Directory -Source $minGitPath -Destination (Join-Path $bundleRoot 'bin\git')
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'Git copy skipped by -SkipBuild.' } else { 'Copied MinGit/Portable Git root from manual path.' }
    $components += New-ComponentRecord -Name 'mingit_portable' -StagedPath 'bin\git' -Required $true -Status $status -SourcePath $minGitPath -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'mingit_portable' -StagedPath 'bin\git' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -MinGitRoot or request mingit_x64 via -AssetIds.' -AssetId ''
}

$useRipgrepAsset = $requestedAssetIds -contains 'ripgrep_x64'
if ($useRipgrepAsset) {
    $rgAsset = Find-AssetRecord -Manifest $assetManifest -AssetId 'ripgrep_x64'
    $resolved = Resolve-AssetForStaging -Asset $rgAsset -CacheRoot $cacheRoot -BundleRoot $bundleRoot -LicenseDir $licenseDir -AllowDownload ([bool]$AllowDownload) -SkipBuild ([bool]$SkipBuild)
    $resolvedAssets += [ordered]@{
        id = $rgAsset.id
        version = $rgAsset.version
        kind = $rgAsset.kind
        platform = $rgAsset.platform
        upstream_url = $rgAsset.upstream_url
        sha256 = $rgAsset.sha256
        archive_type = $rgAsset.archive_type
        cache_relpath = $rgAsset.cache_relpath
        stage_relpath = $rgAsset.stage_relpath
        license_name = $rgAsset.license_name
        license_url = $rgAsset.license_url
        notes = $rgAsset.notes
        cache_archive_path = $resolved.cache_archive_path
        staged_path = $resolved.staged_path
        source_mode = 'asset_manifest'
        status = $resolved.status
    }
    $components += New-ComponentRecord -Name 'ripgrep' -StagedPath $rgAsset.stage_relpath -Required $true -Status $resolved.status -SourcePath $resolved.cache_archive_path -Notes $resolved.notes -AssetId $rgAsset.id
}
elseif ($ripgrepResolved) {
    if (-not $SkipBuild) {
        if ((Get-Item -LiteralPath $ripgrepResolved).PSIsContainer) {
            Stage-Directory -Source $ripgrepResolved -Destination (Join-Path $bundleRoot 'bin\rg')
        }
        else {
            Stage-File -Source $ripgrepResolved -Destination (Join-Path $bundleRoot 'bin\rg\rg.exe')
        }
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'ripgrep copy skipped by -SkipBuild.' } else { 'Copied ripgrep executable or directory.' }
    $components += New-ComponentRecord -Name 'ripgrep' -StagedPath 'bin\rg' -Required $true -Status $status -SourcePath $ripgrepResolved -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'ripgrep' -StagedPath 'bin\rg' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -RipgrepPath or request ripgrep_x64 via -AssetIds.' -AssetId ''
}

$useCtagsAsset = $requestedAssetIds -contains 'universal_ctags_x64'
if ($useCtagsAsset) {
    $ctagsAsset = Find-AssetRecord -Manifest $assetManifest -AssetId 'universal_ctags_x64'
    $resolved = Resolve-AssetForStaging -Asset $ctagsAsset -CacheRoot $cacheRoot -BundleRoot $bundleRoot -LicenseDir $licenseDir -AllowDownload ([bool]$AllowDownload) -SkipBuild ([bool]$SkipBuild)
    $resolvedAssets += [ordered]@{
        id = $ctagsAsset.id
        version = $ctagsAsset.version
        kind = $ctagsAsset.kind
        platform = $ctagsAsset.platform
        upstream_url = $ctagsAsset.upstream_url
        sha256 = $ctagsAsset.sha256
        archive_type = $ctagsAsset.archive_type
        cache_relpath = $ctagsAsset.cache_relpath
        stage_relpath = $ctagsAsset.stage_relpath
        license_name = $ctagsAsset.license_name
        license_url = $ctagsAsset.license_url
        notes = $ctagsAsset.notes
        cache_archive_path = $resolved.cache_archive_path
        staged_path = $resolved.staged_path
        source_mode = 'asset_manifest'
        status = $resolved.status
    }
    $components += New-ComponentRecord -Name 'universal_ctags' -StagedPath $ctagsAsset.stage_relpath -Required $true -Status $resolved.status -SourcePath $resolved.cache_archive_path -Notes $resolved.notes -AssetId $ctagsAsset.id
}
elseif ($ctagsResolved) {
    if (-not $SkipBuild) {
        if ((Get-Item -LiteralPath $ctagsResolved).PSIsContainer) {
            Stage-Directory -Source $ctagsResolved -Destination (Join-Path $bundleRoot 'bin\ctags')
        }
        else {
            Stage-File -Source $ctagsResolved -Destination (Join-Path $bundleRoot 'bin\ctags\ctags.exe')
        }
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'Universal Ctags copy skipped by -SkipBuild.' } else { 'Copied Universal Ctags executable or directory.' }
    $components += New-ComponentRecord -Name 'universal_ctags' -StagedPath 'bin\ctags' -Required $true -Status $status -SourcePath $ctagsResolved -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'universal_ctags' -StagedPath 'bin\ctags' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -CtagsPath or request universal_ctags_x64 via -AssetIds.' -AssetId ''
}

$useWebView2Asset = $requestedAssetIds -contains 'webview2_fixed_runtime_x64'
if ($useWebView2Asset) {
    $webView2Asset = Find-AssetRecord -Manifest $assetManifest -AssetId 'webview2_fixed_runtime_x64'
    $resolved = Resolve-AssetForStaging -Asset $webView2Asset -CacheRoot $cacheRoot -BundleRoot $bundleRoot -LicenseDir $licenseDir -AllowDownload ([bool]$AllowDownload) -SkipBuild ([bool]$SkipBuild)
    $resolvedAssets += [ordered]@{
        id = $webView2Asset.id
        version = $webView2Asset.version
        kind = $webView2Asset.kind
        platform = $webView2Asset.platform
        upstream_url = $webView2Asset.upstream_url
        sha256 = $webView2Asset.sha256
        archive_type = $webView2Asset.archive_type
        cache_relpath = $webView2Asset.cache_relpath
        stage_relpath = $webView2Asset.stage_relpath
        license_name = $webView2Asset.license_name
        license_url = $webView2Asset.license_url
        notes = $webView2Asset.notes
        cache_archive_path = $resolved.cache_archive_path
        staged_path = $resolved.staged_path
        source_mode = 'asset_manifest'
        status = $resolved.status
    }
    $components += New-ComponentRecord -Name 'webview2_fixed_runtime' -StagedPath $webView2Asset.stage_relpath -Required $true -Status $resolved.status -SourcePath $resolved.cache_archive_path -Notes $resolved.notes -AssetId $webView2Asset.id
}
elseif ($webView2RuntimePath) {
    if (-not $SkipBuild) {
        Stage-Directory -Source $webView2RuntimePath -Destination (Join-Path $bundleRoot 'runtime\webview2-fixed-runtime')
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'WebView2 fixed runtime copy skipped by -SkipBuild.' } else { 'Copied WebView2 fixed runtime root from manual path.' }
    $components += New-ComponentRecord -Name 'webview2_fixed_runtime' -StagedPath 'runtime\webview2-fixed-runtime' -Required $true -Status $status -SourcePath $webView2RuntimePath -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'webview2_fixed_runtime' -StagedPath 'runtime\webview2-fixed-runtime' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -WebView2RuntimeRoot or request webview2_fixed_runtime_x64 via -AssetIds.' -AssetId ''
}

if ($llvmPath) {
    if (-not $SkipBuild) {
        Stage-Directory -Source $llvmPath -Destination (Join-Path $bundleRoot 'bin\llvm')
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'LLVM copy skipped by -SkipBuild.' } else { 'Copied current LLVM/Clang bundle; composition remains provisional until Win7 validation.' }
    $components += New-ComponentRecord -Name 'llvm_clang_bundle' -StagedPath 'bin\llvm' -Required $true -Status $status -SourcePath $llvmPath -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'llvm_clang_bundle' -StagedPath 'bin\llvm' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -LlvmRoot to stage the LLVM/Clang bundle.' -AssetId ''
}

$requiredMissing = @($components | Where-Object { $_.required -and $_.status -eq 'missing' })
$summary = [ordered]@{
    staged = @($components | Where-Object { $_.status -eq 'staged' }).Count
    skipped = @($components | Where-Object { $_.status -eq 'skipped' }).Count
    cached = @($components | Where-Object { $_.status -eq 'cached' }).Count
    missing = $requiredMissing.Count
}

$manifest = [ordered]@{
    schema_version = 2
    generated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    project_root = $projectRoot
    build_root = $buildRoot
    bundle_root = $bundleRoot
    asset_manifest_path = $assetManifestResolved
    requested_asset_ids = $requestedAssetIds
    skip_build = [bool]$SkipBuild
    summary = $summary
    resolved_assets = $resolvedAssets
    components = $components
}

$manifestPath = Join-Path $bundleRoot 'manifests\bundle-manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding ASCII

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
