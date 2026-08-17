[CmdletBinding()]
param(
    [string]$AssetManifestPath = "scripts/offline-assets.json",
    [string[]]$AssetIds = @(),
    [string]$BundlePlanPath = "",
    [string]$BundlePlanSha256 = "",
    [switch]$AllowDownload,
    [string]$PythonRuntimeRoot = "",
    [string]$SitePackagesRoot = "",
    [string]$MinGitRoot = "",
    [string]$RipgrepPath = "",
    [string]$CtagsPath = "",
    [string]$WebView2RuntimeRoot = "",
    [string]$LlvmRoot = "",
    [string]$GuiLauncherExePath = "",
    [string]$BuildRoot = "",
    [string]$AssetCacheRoot = "",
    [string]$ReleaseIdentityPath = "",
    [switch]$SkipBuild,
    [switch]$Clean
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'package-lib.ps1')

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

function Remove-ProjectEditableArtifacts {
    param(
        [string]$SitePackagesRoot,
        [string]$ProjectRoot
    )

    if (-not (Test-Path -LiteralPath $SitePackagesRoot)) {
        return
    }

    $normalizedProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
    Get-ChildItem -LiteralPath $SitePackagesRoot -Filter '*.pth' -File | ForEach-Object {
        $path = $_.FullName
        $content = @()
        try {
            $content = @(Get-Content -LiteralPath $path -ErrorAction Stop)
        }
        catch {
            return
        }

        $shouldRemove = $false
        foreach ($line in $content) {
            $trimmed = "$line".Trim()
            if (-not $trimmed) {
                continue
            }
            if ($trimmed.StartsWith('import ', [System.StringComparison]::OrdinalIgnoreCase)) {
                continue
            }
            $candidate = $trimmed
            if (-not [System.IO.Path]::IsPathRooted($candidate)) {
                continue
            }
            try {
                $resolved = [System.IO.Path]::GetFullPath($candidate)
            }
            catch {
                continue
            }
            if ($resolved -eq $normalizedProjectRoot -or $resolved.StartsWith($normalizedProjectRoot.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
                $shouldRemove = $true
                break
            }
        }

        if ($shouldRemove) {
            Remove-Item -LiteralPath $path -Force
        }
    }
}

function Get-ProjectWheelMetadata {
    param(
        [string]$SitePackagesRoot,
        [object]$BundlePlan
    )

    $wheelRoot = Join-Path (Split-Path -Parent $SitePackagesRoot) 'wheels'
    if (-not (Test-Path -LiteralPath $wheelRoot -PathType Container)) {
        throw "Checked project wheelhouse not found: $wheelRoot"
    }
    if ($null -eq $BundlePlan -or @($BundlePlan.project_distribution_ids).Count -eq 0) {
        throw 'Bundle plan project distributions are required.'
    }
    $expected = [ordered]@{}
    foreach ($distribution in @($BundlePlan.project_distribution_ids)) {
        $name = [string]$distribution
        $prefix = $name.Replace('-', '_')
        if ($name -eq 'embedagent-shell') { $prefix = 'embedagent_shell' }
        $expected[$name] = $prefix + '-*.whl'
    }
    $allWheels = @(Get-ChildItem -LiteralPath $wheelRoot -Filter '*.whl' -File)
    if ($allWheels.Count -ne $expected.Count) {
        throw ('Expected the selected project wheel count ({0}), found {1} in {2}' -f $expected.Count, $allWheels.Count, $wheelRoot)
    }
    $wheelNames = @()
    $wheelHashes = [ordered]@{}
    foreach ($distribution in $expected.Keys) {
        $matches = @(Get-ChildItem -LiteralPath $wheelRoot -Filter $expected[$distribution] -File)
        if ($matches.Count -ne 1) {
            throw ('Expected exactly one wheel for {0}, found {1}' -f $distribution, $matches.Count)
        }
        $wheel = $matches[0]
        $wheelNames += $wheel.Name
        $wheelHashes[$wheel.Name] = (Get-FileHash -LiteralPath $wheel.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return [ordered]@{
        project_wheels = $wheelNames
        wheel_hashes = $wheelHashes
        wheelhouse_path = $wheelRoot
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
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ArchivePath, $DestinationPath)
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
$planState = Read-VerifiedBundlePlan `
    -ProjectRoot $projectRoot `
    -BundlePlanPath $BundlePlanPath `
    -BundlePlanSha256 $BundlePlanSha256 `
    -AssetManifestPath $assetManifestResolved
$bundlePlan = $planState.plan
$normalizedAssetIds = Normalize-AssetIds -AssetIds $AssetIds
if (($normalizedAssetIds -join '|') -ne (@($bundlePlan.asset_ids) -join '|')) {
    throw 'AssetIds do not match the verified bundle plan.'
}
$requestedAssetIds = @($bundlePlan.asset_ids)
$assetManifest = $planState.asset_manifest
$hasTui = @($bundlePlan.shell_ids) -contains 'tui'
$hasGui = @($bundlePlan.shell_ids) -contains 'gui'
$hasCppGate = @($bundlePlan.gate_ids) -contains 'cpp_smoke_workspace'
$hasGuiGate = @($bundlePlan.gate_ids) -contains 'gui_headless_smoke'
$hasCliSmokeGate = @($bundlePlan.gate_ids) -contains 'win7_cli_smoke'
$hasPythonRuntime = @($bundlePlan.runtime_component_ids) -contains 'python'
$hasMinGit = @($bundlePlan.runtime_component_ids) -contains 'mingit'
$hasRipgrep = @($bundlePlan.runtime_component_ids) -contains 'ripgrep'
$hasCtags = @($bundlePlan.runtime_component_ids) -contains 'ctags'
$configTemplatePath = Join-Path $projectRoot ('config\bundle-flavors\{0}.json' -f [string]$bundlePlan.config_template_id)
if (-not (Test-Path -LiteralPath $configTemplatePath -PathType Leaf)) {
    throw "Bundle config template not found: $configTemplatePath"
}
$configTemplate = Get-Content -LiteralPath $configTemplatePath -Raw | ConvertFrom-Json
if ($configTemplate.PSObject.Properties.Name -contains 'api_key') {
    throw 'Bundle config templates must not contain an api_key property.'
}
$buildRoot = if ($BuildRoot) {
    if ([System.IO.Path]::IsPathRooted($BuildRoot)) { $BuildRoot } else { Join-Path $projectRoot $BuildRoot }
}
else {
    Join-Path $projectRoot 'build'
}
$cacheRoot = if ($AssetCacheRoot) {
    if ([System.IO.Path]::IsPathRooted($AssetCacheRoot)) { $AssetCacheRoot } else { Join-Path $projectRoot $AssetCacheRoot }
}
else {
    Join-Path $buildRoot 'offline-cache'
}
$stagingRoot = Join-Path $buildRoot 'offline-staging'
$distRoot = Join-Path $buildRoot 'offline-dist'
$bundleRoot = Join-Path $stagingRoot 'EmbedAgent'
$licenseDir = Join-Path $bundleRoot 'manifests\licenses'

Write-Host "[prepare] Starting offline bundle preparation..."
Write-Host "[prepare] Project root: $projectRoot"
Write-Host "[prepare] Build root: $buildRoot"
Write-Host "[prepare] Staging bundle: $bundleRoot"

Ensure-Directory -Path $buildRoot
Ensure-Directory -Path $cacheRoot
Ensure-Directory -Path $distRoot
Reset-Directory -Root $stagingRoot -Target $bundleRoot

$paths = @(
    'app',
    'bin',
    'config',
    'data',
    'docs',
    'manifests',
    'manifests\licenses',
    'runtime',
    'runtime\site-packages',
    'tools',
    'tools\validation'
)
if ($hasPythonRuntime) { $paths += 'runtime\python' }
if ($hasMinGit) { $paths += 'bin\git' }
if ($hasRipgrep) { $paths += 'bin\rg' }
if ($hasCtags) { $paths += 'bin\ctags' }
if (@($bundlePlan.runtime_component_ids) -contains 'llvm') { $paths += 'bin\llvm' }
if (@($bundlePlan.runtime_component_ids) -contains 'webview2') { $paths += 'runtime\webview2-fixed-runtime' }
if ($hasCppGate) { $paths += 'data\workspace-template' }
Write-Host "[prepare] Creating bundle directory structure ($($paths.Count) paths)..."
foreach ($relative in $paths) {
    Ensure-Directory -Path (Join-Path $bundleRoot $relative)
}
Stage-File -Source $planState.plan_path -Destination (Join-Path $bundleRoot 'manifests\bundle-plan.json')
Stage-File -Source $planState.agent_manifest_path -Destination (Join-Path $bundleRoot 'manifests\agent.json')
Stage-File -Source $planState.agent_lock_path -Destination (Join-Path $bundleRoot 'manifests\agent.lock.json')

if ($hasGui) {
    Write-Host "[prepare] Ensuring GUI frontend assets..."
    $guiFrontendStatus = Ensure-GuiFrontendAssets -ProjectRoot $projectRoot
    if (-not $guiFrontendStatus.ok) {
        $missingLabel = @($guiFrontendStatus.missing) -join ', '
        $reason = [string]$guiFrontendStatus.reason
        throw ('GUI static assets are incomplete and could not be prepared. Reason={0}; Missing={1}; StaticRoot={2}' -f $reason, $missingLabel, $guiFrontendStatus.static_root)
    }
    Write-Host "[prepare]   GUI assets: $($guiFrontendStatus.mode) (ok=$($guiFrontendStatus.ok))"
}

if (-not $SitePackagesRoot) {
    $candidateSitePackages = Join-Path $projectRoot 'build\offline-cache\site-packages-export\site-packages'
    if (Test-Path -LiteralPath $candidateSitePackages) {
        $SitePackagesRoot = $candidateSitePackages
    }
}
$sitePackagesPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $SitePackagesRoot
$installedAppRoot = if ($sitePackagesPath) { Join-Path $sitePackagesPath 'embedagent' } else { '' }
if (-not $installedAppRoot -or -not (Test-Path -LiteralPath $installedAppRoot)) {
    throw 'Installed embedagent distribution not found. Run package.ps1 deps or provide -SitePackagesRoot from export-dependencies.py.'
}
$installedGuiStaticRoot = Join-Path $installedAppRoot 'frontend\gui\static'
if ($hasGui -and -not (Test-Path -LiteralPath $installedGuiStaticRoot)) {
    throw "Installed embedagent distribution is missing frontend\gui\static: $installedGuiStaticRoot"
}

Write-Host "[prepare] Staging installed application distribution..."
$stagedAppRoot = Join-Path $bundleRoot 'app\embedagent'
Stage-Directory -Source $installedAppRoot -Destination $stagedAppRoot
Remove-TransientPythonArtifacts -Root $stagedAppRoot
if (-not $hasGui) {
    $unselectedGuiRoot = Join-Path $stagedAppRoot 'frontend\gui'
    if (Test-Path -LiteralPath $unselectedGuiRoot) {
        Remove-Item -LiteralPath $unselectedGuiRoot -Recurse -Force
    }
}
Write-Host "[prepare]   App code staged to $stagedAppRoot"

Write-Host "[prepare] Staging documentation..."

$configurationGuide = Join-Path $projectRoot 'docs\guides\configuration-guide.md'
$preflightGuide = Join-Path $projectRoot 'docs\guides\win7-preflight-checklist.md'
$intranetGuide = Join-Path $projectRoot 'docs\guides\intranet-deployment.md'
$win7GuiGuide = Join-Path $projectRoot 'docs\guides\win7-gui-validation.md'
if (Test-Path -LiteralPath $configurationGuide) {
    Stage-File -Source $configurationGuide -Destination (Join-Path $bundleRoot 'docs\configuration-guide.md')
}
if (Test-Path -LiteralPath $preflightGuide) {
    Stage-File -Source $preflightGuide -Destination (Join-Path $bundleRoot 'docs\win7-preflight-checklist.md')
}
if (Test-Path -LiteralPath $intranetGuide) {
    Stage-File -Source $intranetGuide -Destination (Join-Path $bundleRoot 'docs\intranet-deployment.md')
}
if ($hasGui -and (Test-Path -LiteralPath $win7GuiGuide)) {
    Stage-File -Source $win7GuiGuide -Destination (Join-Path $bundleRoot 'docs\win7-gui-validation.md')
}

$guiSmokeScript = Join-Path $projectRoot 'scripts\validate-gui-smoke.py'
if ($hasGuiGate -and (Test-Path -LiteralPath $guiSmokeScript)) {
    Stage-File -Source $guiSmokeScript -Destination (Join-Path $bundleRoot 'tools\validation\validate-gui-smoke.py')
}
$cppSmokeScript = Join-Path $projectRoot 'scripts\validate-cpp-smoke.py'
if ($hasCppGate -and (Test-Path -LiteralPath $cppSmokeScript)) {
    Stage-File -Source $cppSmokeScript -Destination (Join-Path $bundleRoot 'tools\validation\validate-cpp-smoke.py')
}
$cliSmokeScript = Join-Path $projectRoot 'scripts\validate-cli-smoke.py'
if ($hasCliSmokeGate -and (Test-Path -LiteralPath $cliSmokeScript)) {
    Stage-File -Source $cliSmokeScript -Destination (Join-Path $bundleRoot 'tools\validation\validate-cli-smoke.py')
}
$releaseEvidenceScript = Join-Path $projectRoot 'scripts\validate-release-evidence.py'
if (Test-Path -LiteralPath $releaseEvidenceScript) {
    Stage-File -Source $releaseEvidenceScript -Destination (Join-Path $bundleRoot 'tools\validation\validate-release-evidence.py')
}$releaseIdentityHelper = Join-Path $projectRoot 'scripts\release_identity.py'
if (Test-Path -LiteralPath $releaseIdentityHelper) {
    Stage-File -Source $releaseIdentityHelper -Destination (Join-Path $bundleRoot 'tools\validation\release_identity.py')
}
$win7Runbook = Join-Path $projectRoot 'docs\guides\win7-release-runbook.md'
if (Test-Path -LiteralPath $win7Runbook) {
    Stage-File -Source $win7Runbook -Destination (Join-Path $bundleRoot 'manifests\evidence\win7-runbook.md')
}

Stage-File -Source $configTemplatePath -Destination (Join-Path $bundleRoot 'config\config.json')
Stage-File -Source $configTemplatePath -Destination (Join-Path $bundleRoot 'config\config.json.template')

$defaultPermissionRules = @'
{
  "schema_version": 1,
  "rules": []
}
'@
Write-TextFile -Path (Join-Path $bundleRoot 'config\permission-rules.json') -Content ($defaultPermissionRules.Trim() + "`r`n")

if ($hasCppGate) {
$workspaceTemplateReadme = @'
# EmbedAgent Offline C Smoke Workspace

This workspace is a tiny C project for validating the bundled offline runtime.
It can be replaced with a real project, but it is intentionally buildable as-is.

Suggested first prompt:

```
/mode build 构建这个 C 项目并解释结果
```

Manual clang smoke command from this directory:

```
..\..\bin\llvm\bin\clang.exe main.c -o embedagent-smoke.exe
```
'@
Write-TextFile -Path (Join-Path $bundleRoot 'data\workspace-template\README.md') -Content ($workspaceTemplateReadme.Trim() + "`r`n")

$workspaceTemplateMain = @'
#include <stdio.h>

static int add(int left, int right)
{
    return left + right;
}

int main(void)
{
    printf("embedagent smoke: %d\n", add(2, 3));
    return 0;
}
'@
Write-TextFile -Path (Join-Path $bundleRoot 'data\workspace-template\main.c') -Content ($workspaceTemplateMain.Trim() + "`r`n")
}

$runtimePathEntries = @()
if ($hasMinGit) {
    $runtimePathEntries += @('%BUNDLE_ROOT%bin\git\cmd', '%BUNDLE_ROOT%bin\git\bin')
}
if ($hasRipgrep) { $runtimePathEntries += '%BUNDLE_ROOT%bin\rg' }
if ($hasCtags) { $runtimePathEntries += '%BUNDLE_ROOT%bin\ctags' }
if (@($bundlePlan.runtime_component_ids) -contains 'llvm') {
    $runtimePathEntries += @('%BUNDLE_ROOT%bin\llvm\bin', '%BUNDLE_ROOT%bin\llvm\libexec')
}
$runtimePath = if ($runtimePathEntries.Count -gt 0) {
    ($runtimePathEntries -join ';') + ';%PATH%'
}
else {
    '%PATH%'
}

$launcherCli = @"
@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "EMBEDAGENT_BUNDLE_ROOT=%BUNDLE_ROOT%"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"
set "PATH=$runtimePath"
"%BUNDLE_ROOT%runtime\python\python.exe" -m embedagent %*
"@
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent.cmd') -Content ($launcherCli.Trim() + "`r`n")

if ($hasTui) {
$launcherTui = @"
@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "EMBEDAGENT_BUNDLE_ROOT=%BUNDLE_ROOT%"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"
set "PATH=$runtimePath"
"%PYTHONHOME%\python.exe" -m embedagent.frontend.tui.launcher %*
"@
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent-tui.cmd') -Content ($launcherTui.Trim() + "`r`n")
}

if ($hasGui) {
$launcherGui = @"
@echo off
setlocal

set "BUNDLE_ROOT=%~dp0"
set "EMBEDAGENT_BUNDLE_ROOT=%BUNDLE_ROOT%"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"

set "PATH=$runtimePath"

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

"%PYTHONHOME%\python.exe" "%BUNDLE_ROOT%app\embedagent\frontend\gui\launcher.py" %*
"@
Write-TextFile -Path (Join-Path $bundleRoot 'embedagent-gui.cmd') -Content ($launcherGui.Trim() + "`r`n")
}

if ($hasGuiGate) {
$launcherGuiSmoke = @'
@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"
"%PYTHONHOME%\python.exe" "%BUNDLE_ROOT%tools\validation\validate-gui-smoke.py" --bundle-root "%BUNDLE_ROOT%" --require-fixed-webview2 %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'validate-gui-smoke.cmd') -Content ($launcherGuiSmoke.Trim() + "`r`n")
}

if ($hasCppGate) {
$launcherCppSmoke = @'
@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"
"%PYTHONHOME%\python.exe" "%BUNDLE_ROOT%tools\validation\validate-cpp-smoke.py" --bundle-root "%BUNDLE_ROOT%" %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'validate-cpp-smoke.cmd') -Content ($launcherCppSmoke.Trim() + "`r`n")
}

if ($hasCliSmokeGate) {
$launcherCliSmoke = @'
@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"
"%PYTHONHOME%\python.exe" "%BUNDLE_ROOT%tools\validation\validate-cli-smoke.py" --bundle-root "%BUNDLE_ROOT%" %*
'@
Write-TextFile -Path (Join-Path $bundleRoot 'validate-cli-smoke.cmd') -Content ($launcherCliSmoke.Trim() + "`r`n")
}

$licensesReadme = @'
Third-party license notices for bundled assets are written here during prepare.
'@
Write-TextFile -Path (Join-Path $licenseDir 'README.txt') -Content ($licensesReadme.Trim() + "`r`n")

Write-Host "[prepare] Generating config templates and launcher scripts..."

$defaultLlvmRoot = Join-Path $projectRoot 'toolchains\llvm\current'
if ($hasCppGate -and -not $LlvmRoot -and (Test-Path -LiteralPath $defaultLlvmRoot)) {
    $LlvmRoot = $defaultLlvmRoot
}
$resolvedAssets = @()
$components = @()

$pythonRuntimePath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $PythonRuntimeRoot
$minGitPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $MinGitRoot
$ripgrepResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $RipgrepPath
$ctagsResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $CtagsPath
$webView2RuntimePath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $WebView2RuntimeRoot
$llvmPath = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $LlvmRoot
$guiLauncherExeResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $GuiLauncherExePath
$guiLauncherResult = $null
if ($hasGui) {
    $guiLauncherResult = Stage-GuiLauncherExe -Source $guiLauncherExeResolved -BundleRoot $bundleRoot
}

$components += New-ComponentRecord -Name 'app_code' -StagedPath 'app\embedagent' -Required $true -Status 'staged' -SourcePath $installedAppRoot -Notes 'Copied from the wheel-installed product distribution while preserving the GUI static layout.' -AssetId ''
$components += New-ComponentRecord -Name 'docs_bundle' -StagedPath 'docs' -Required $true -Status 'staged' -SourcePath (Join-Path $projectRoot 'docs') -Notes 'Copied common deployment documentation plus shell-specific guides selected by the bundle plan.' -AssetId ''
$components += New-ComponentRecord -Name 'config_templates' -StagedPath 'config' -Required $true -Status 'staged' -SourcePath '' -Notes 'Generated default config and permission rules templates.' -AssetId ''
$components += New-ComponentRecord -Name 'launcher_scripts' -StagedPath '.' -Required $true -Status 'staged' -SourcePath '' -Notes ('Generated launchers selected by the bundle plan: ' + (@($bundlePlan.launcher_ids) -join ', ')) -AssetId ''
if ($hasGui) {
    $components += New-ComponentRecord -Name 'gui_launcher_exe' -StagedPath 'EmbedAgent.exe;embedagent-gui.exe' -Required $true -Status $guiLauncherResult.status -SourcePath $guiLauncherResult.source_path -Notes $guiLauncherResult.notes -AssetId ''
}
$components += New-ComponentRecord -Name 'validation_tools' -StagedPath 'tools\validation' -Required $true -Status 'staged' -SourcePath '' -Notes ('Copied validators selected by release gates: ' + (@($bundlePlan.gate_ids) -join ', ')) -AssetId ''

Write-Host "[prepare] Resolving runtime assets..."
Write-Host "[prepare]   Requested assets: $($requestedAssetIds -join ', ')"

$usePythonAsset = $requestedAssetIds -contains 'python_embedded_x64'
Write-Host "[prepare]   python_runtime..."
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

Write-Host "[prepare]   python_packages..."
if ($sitePackagesPath) {
    if (-not $SkipBuild) {
        Stage-Directory -Source $sitePackagesPath -Destination (Join-Path $bundleRoot 'runtime\site-packages')
        Remove-TransientPythonArtifacts -Root (Join-Path $bundleRoot 'runtime\site-packages')
        Remove-ProjectEditableArtifacts -SitePackagesRoot (Join-Path $bundleRoot 'runtime\site-packages') -ProjectRoot $projectRoot
        $duplicateProductPackage = Join-Path $bundleRoot 'runtime\site-packages\embedagent'
        $duplicateProductDistInfo = @(Get-ChildItem -LiteralPath (Join-Path $bundleRoot 'runtime\site-packages') -Directory -Filter 'embedagent-*.dist-info' -ErrorAction SilentlyContinue)
        if (Test-Path -LiteralPath $duplicateProductPackage) {
            Remove-Item -LiteralPath $duplicateProductPackage -Recurse -Force
        }
        foreach ($distInfo in $duplicateProductDistInfo) {
            Remove-Item -LiteralPath $distInfo.FullName -Recurse -Force
        }
        if ((Test-Path -LiteralPath $duplicateProductPackage) -or @((Get-ChildItem -LiteralPath (Join-Path $bundleRoot 'runtime\site-packages') -Directory -Filter 'embedagent-*.dist-info' -ErrorAction SilentlyContinue)).Count -gt 0) {
            throw 'duplicate product package or dist-info remains in runtime/site-packages'
        }
        $packageRoots = @{
            'embedagent-core' = 'embedagent_core'
            'embedagent-protocol' = 'embedagent_protocol'
            'embedagent-host' = 'embedagent_host'
            'embedagent-composition' = 'embedagent_composition'
            'embedagent-workflow-cpp' = 'embedagent_workflow_cpp'
        }
        foreach ($lowerDistribution in @($bundlePlan.project_distribution_ids)) {
            if ($packageRoots.ContainsKey([string]$lowerDistribution) -and -not (Test-Path -LiteralPath (Join-Path $bundleRoot ('runtime\site-packages\' + $packageRoots[[string]$lowerDistribution])))) {
                throw ('selected project distribution missing from runtime/site-packages: {0}' -f $lowerDistribution)
            }
        }
    }
    $status = if ($SkipBuild) { 'skipped' } else { 'staged' }
    $note = if ($SkipBuild) { 'Site-packages copy skipped by -SkipBuild.' } else { 'Copied wheel-installed site-packages, removed editable links, and kept the product package in app/embedagent.' }
    $components += New-ComponentRecord -Name 'python_packages' -StagedPath 'runtime\site-packages' -Required $true -Status $status -SourcePath $sitePackagesPath -Notes $note -AssetId ''
}
else {
    $components += New-ComponentRecord -Name 'python_packages' -StagedPath 'runtime\site-packages' -Required $true -Status 'missing' -SourcePath '' -Notes 'Provide -SitePackagesRoot or rely on a future export step.' -AssetId ''
}

if ($hasMinGit) {
Write-Host "[prepare]   mingit_portable..."
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
}

if ($hasRipgrep) {
Write-Host "[prepare]   ripgrep..."
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
}

if ($hasCtags) {
Write-Host "[prepare]   universal_ctags..."
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
}

if ($hasGui) {
Write-Host "[prepare]   webview2_fixed_runtime..."
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
}

if ($hasCppGate) {
Write-Host "[prepare]   llvm_clang_bundle..."
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
}

$projectWheelMetadata = [ordered]@{
    project_wheels = @()
    wheel_hashes = [ordered]@{}
    wheelhouse_path = ''
}
if ($sitePackagesPath -and -not $SkipBuild) {
    $projectWheelMetadata = Get-ProjectWheelMetadata -SitePackagesRoot $sitePackagesPath -BundlePlan $bundlePlan
}
$releaseIdentitySource = if ($ReleaseIdentityPath) {
    if ([System.IO.Path]::IsPathRooted($ReleaseIdentityPath)) { $ReleaseIdentityPath } else { Join-Path $projectRoot $ReleaseIdentityPath }
}
else {
    Join-Path $projectRoot 'manifests\release-identity.json'
}
$identityPath = ''
if (Test-Path -LiteralPath $releaseIdentitySource -PathType Leaf) {
    Stage-File -Source $releaseIdentitySource -Destination (Join-Path $bundleRoot 'manifests\release-identity.json')
    $identityPath = 'manifests/release-identity.json'
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
    flavor_id = [string]$bundlePlan.flavor_id
    bundle_plan_sha256 = [string]$planState.plan_sha256
    agent_lock_sha256 = [string]$bundlePlan.agent_lock_sha256
    allowed_agent_application_ids = @($bundlePlan.allowed_agent_application_ids)
    shell_ids = @($bundlePlan.shell_ids)
    runtime_component_ids = @($bundlePlan.runtime_component_ids)
    resolved_asset_ids = @($bundlePlan.asset_ids)
    python_feature_ids = @($bundlePlan.python_feature_ids)
    staged_launcher_ids = @($bundlePlan.launcher_ids)
    gate_ids = @($bundlePlan.gate_ids)
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
    project_wheels = $projectWheelMetadata.project_wheels
    wheel_hashes = $projectWheelMetadata.wheel_hashes
    wheelhouse_path = $projectWheelMetadata.wheelhouse_path
    identity_path = $identityPath
    source_mode = 'wheel-installed'
    project_distributions = @($bundlePlan.project_distribution_ids)
}

Write-Host "[prepare] Writing bundle manifest and checksums..."
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

Write-Host ""
Write-Host "=========================================="
Write-Host "[prepare] Offline bundle preparation complete"
Write-Host "  Bundle: $bundleRoot"
Write-Host "  Staged: $($summary.staged)"
Write-Host "  Skipped: $($summary.skipped)"
Write-Host "  Cached: $($summary.cached)"
Write-Host "  Missing: $($summary.missing)"
if ($requiredMissing.Count -gt 0) {
    Write-Host "  Missing components:"
    foreach ($item in $requiredMissing) {
        Write-Host ('    - {0}: {1}' -f $item.name, $item.notes)
    }
}
Write-Host "=========================================="
