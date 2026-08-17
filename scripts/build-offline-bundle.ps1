[CmdletBinding()]
param(
    [string]$ArtifactName = 'embedagent-win7-x64',
    [string]$AssetManifestPath = 'scripts/offline-assets.json',
    [string]$BundlePlanPath = "",
    [string]$BundlePlanSha256 = "",
    [switch]$RunPrepare,
    [switch]$PrepareSkipBuild,
    [switch]$AllowDownload,
    [string[]]$AssetIds = @(),
    [switch]$NoZip,
    [switch]$Clean,
    [string]$BuildRoot = "",
    [string]$AssetCacheRoot = "",
    [string]$ReleaseIdentityPath = "",
    [string]$DepsReportPath = "",
    [string]$PythonRuntimeRoot = "",
    [string]$SitePackagesRoot = "",
    [string]$MinGitRoot = "",
    [string]$RipgrepPath = "",
    [string]$CtagsPath = "",
    [string]$WebView2RuntimeRoot = "",
    [string]$LlvmRoot = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'package-lib.ps1')

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

function Remove-IfExists {
    param(
        [string]$Root,
        [string]$Target
    )

    if (-not (Test-Path -LiteralPath $Target)) {
        return
    }
    Assert-ChildPath -Root $Root -Child $Target
    Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $Target) {
        throw "Failed to remove target: $Target"
    }
}

function Copy-BundleTree {
    param(
        [string]$Source,
        [string]$Destination
    )

    $parent = Split-Path -Parent $Destination
    Ensure-Directory -Path $parent
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -Path (Join-Path $Source '*') -Destination $Destination -Recurse -Force
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
    return (Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json)
}

function Update-BundleManifest {
    param(
        [string]$ManifestPath,
        [string]$ArtifactName,
        [string]$StagingBundleRoot,
        [string]$DistBundleRoot,
        [string]$ZipPath,
        [bool]$ZipCreated,
        [string]$SourcesRoot
    )

    $raw = Get-Content -LiteralPath $ManifestPath -Raw
    $manifest = $raw | ConvertFrom-Json
    $manifest | Add-Member -NotePropertyName artifact_name -NotePropertyValue $ArtifactName -Force
    $manifest | Add-Member -NotePropertyName build_stage -NotePropertyValue 'dist' -Force
    $manifest | Add-Member -NotePropertyName staging_bundle_root -NotePropertyValue $StagingBundleRoot -Force
    $manifest.bundle_root = $DistBundleRoot
    $manifest | Add-Member -NotePropertyName built_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')) -Force
    $manifest | Add-Member -NotePropertyName zip_path -NotePropertyValue $ZipPath -Force
    $manifest | Add-Member -NotePropertyName zip_created -NotePropertyValue $ZipCreated -Force
    $manifest | Add-Member -NotePropertyName sources_root -NotePropertyValue $SourcesRoot -Force
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ManifestPath -Encoding ASCII
}

function Get-BundleTreeSha256 {
    param(
        [string]$Root,
        [string[]]$ExcludedRelativePaths = @()
    )

    $excluded = @('manifests\checksums.txt') + @($ExcludedRelativePaths | ForEach-Object { $_.Replace('/', '\') })
    $records = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $Root -Recurse -File | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($Root.Length).TrimStart('\')
        if ($excluded -contains $relative) {
            continue
        }
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $records += ($relative.Replace('\', '/') + ':' + $hash)
    }
    $payload = ($records -join "`n")
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($payload)))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
}
function Write-BundleChecksums {
    param(
        [string]$Root,
        [string]$ChecksumPath
    )

    $filesToHash = Get-ChildItem -LiteralPath $Root -Recurse -File |
        Where-Object { $_.FullName -ne $ChecksumPath } |
        Sort-Object FullName
    $checksumLines = @()
    foreach ($file in $filesToHash) {
        $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
        $relative = $file.FullName.Substring($Root.Length).TrimStart('\')
        $checksumLines += ('{0} *{1}' -f $hash.Hash.ToLowerInvariant(), $relative.Replace('\', '/'))
    }
    Set-Content -LiteralPath $ChecksumPath -Value $checksumLines -Encoding ASCII
}

function Invoke-PrepareOffline {
    param(
        [string]$PrepareScript,
        [string]$AssetManifestPath,
        [string]$BundlePlanPath,
        [string]$BundlePlanSha256,
        [string[]]$AssetIds,
        [bool]$PrepareSkipBuild,
        [bool]$AllowDownload,
        [string]$BuildRoot,
        [string]$AssetCacheRoot,
        [string]$ReleaseIdentityPath,
        [string]$PythonRuntimeRoot,
        [string]$SitePackagesRoot,
        [string]$MinGitRoot,
        [string]$RipgrepPath,
        [string]$CtagsPath,
        [string]$WebView2RuntimeRoot,
        [string]$LlvmRoot
    )

    $prepareParams = @{
        AssetManifestPath = $AssetManifestPath
        BundlePlanPath = $BundlePlanPath
        BundlePlanSha256 = $BundlePlanSha256
    }
    if (@($AssetIds).Count -gt 0) {
        $prepareParams.AssetIds = $AssetIds
    }
    if ($PrepareSkipBuild) {
        $prepareParams.SkipBuild = $true
    }
    if ($AllowDownload) {
        $prepareParams.AllowDownload = $true
    }
    if ($BuildRoot) {
        $prepareParams.BuildRoot = $BuildRoot
    }
    if ($AssetCacheRoot) {
        $prepareParams.AssetCacheRoot = $AssetCacheRoot
    }
    if ($ReleaseIdentityPath) {
        $prepareParams.ReleaseIdentityPath = $ReleaseIdentityPath
    }
    if ($PythonRuntimeRoot) {
        $prepareParams.PythonRuntimeRoot = $PythonRuntimeRoot
    }
    if ($SitePackagesRoot) {
        $prepareParams.SitePackagesRoot = $SitePackagesRoot
    }
    if ($MinGitRoot) {
        $prepareParams.MinGitRoot = $MinGitRoot
    }
    if ($RipgrepPath) {
        $prepareParams.RipgrepPath = $RipgrepPath
    }
    if ($CtagsPath) {
        $prepareParams.CtagsPath = $CtagsPath
    }
    if ($WebView2RuntimeRoot) {
        $prepareParams.WebView2RuntimeRoot = $WebView2RuntimeRoot
    }
    if ($LlvmRoot) {
        $prepareParams.LlvmRoot = $LlvmRoot
    }
    & $PrepareScript @prepareParams
}

function Copy-OptionalReleaseFile {
    param(
        [string]$Source,
        [string[]]$Destinations
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        return @()
    }
    $copied = @()
    foreach ($destination in @($Destinations)) {
        $parent = Split-Path -Parent $destination
        Ensure-Directory -Path $parent
        Copy-Item -LiteralPath $Source -Destination $destination -Force
        $copied += $destination
    }
    return $copied
}
function Create-BundleZip {
    param(
        [string]$SourceDirectory,
        [string]$ZipPath
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $SourceDirectory,
        $ZipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$assetManifestResolved = if ([System.IO.Path]::IsPathRooted($AssetManifestPath)) { $AssetManifestPath } else { Join-Path $projectRoot $AssetManifestPath }
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
$hasGui = @($bundlePlan.shell_ids) -contains 'gui'
$buildRoot = if ($BuildRoot) {
    if ([System.IO.Path]::IsPathRooted($BuildRoot)) { $BuildRoot } else { Join-Path $projectRoot $BuildRoot }
}
else {
    Join-Path $projectRoot 'build'
}
$stagingBundleRoot = Join-Path $buildRoot 'offline-staging\EmbedAgent'
$distRoot = Join-Path $buildRoot 'offline-dist'
$distBundleRoot = Join-Path $distRoot $ArtifactName
$sourcesRoot = Join-Path $distRoot ($ArtifactName + '-sources')
$sourcesArchivesRoot = Join-Path $sourcesRoot 'archives'
$defaultPythonWheelsSourceRoot = Join-Path $projectRoot 'build\offline-cache\site-packages-export\wheels'
$pythonWheelsSourceRoot = $defaultPythonWheelsSourceRoot
if ($SitePackagesRoot) {
    $sitePackagesCandidate = $SitePackagesRoot
    if (-not [System.IO.Path]::IsPathRooted($sitePackagesCandidate)) {
        $sitePackagesCandidate = Join-Path $projectRoot $sitePackagesCandidate
    }
    $pythonWheelsSourceRoot = Join-Path (Split-Path -Parent $sitePackagesCandidate) 'wheels'
}
$pythonWheelsArchiveRoot = Join-Path $sourcesRoot 'python-wheels'
$zipPath = Join-Path $distRoot ($ArtifactName + '.zip')
$prepareScript = Join-Path $PSScriptRoot 'prepare-offline.ps1'

Ensure-Directory -Path $buildRoot
Ensure-Directory -Path $distRoot

$shouldPrepare = $RunPrepare -or (-not (Test-Path -LiteralPath $stagingBundleRoot))
if ($shouldPrepare) {
    Invoke-PrepareOffline `
        -PrepareScript $prepareScript `
        -AssetManifestPath $assetManifestResolved `
        -BundlePlanPath $BundlePlanPath `
        -BundlePlanSha256 $BundlePlanSha256 `
        -AssetIds $normalizedAssetIds `
        -PrepareSkipBuild ([bool]$PrepareSkipBuild) `
        -AllowDownload ([bool]$AllowDownload) `
        -BuildRoot $buildRoot `
        -AssetCacheRoot $AssetCacheRoot `
        -ReleaseIdentityPath $ReleaseIdentityPath `
        -PythonRuntimeRoot $PythonRuntimeRoot `
        -SitePackagesRoot $SitePackagesRoot `
        -MinGitRoot $MinGitRoot `
        -RipgrepPath $RipgrepPath `
        -CtagsPath $CtagsPath `
        -WebView2RuntimeRoot $WebView2RuntimeRoot `
        -LlvmRoot $LlvmRoot
}

if (-not (Test-Path -LiteralPath $stagingBundleRoot)) {
    throw "Staging bundle not found: $stagingBundleRoot"
}

Write-Host "[build] Validating staging bundle..."
if ($hasGui) {
    $stagingGuiStatus = Get-GuiBundleAssetStatus -BundleRoot $stagingBundleRoot
    if (-not $stagingGuiStatus.ok) {
        $missingLabel = @($stagingGuiStatus.missing) -join ', '
        throw ('Staging bundle is missing required GUI static assets. Missing={0}; StaticRoot={1}. Re-run build-offline-bundle.ps1 with -RunPrepare or rebuild the GUI frontend first.' -f $missingLabel, $stagingGuiStatus.static_root)
    }
}
Write-Host "[build]   Staging bundle OK"

$stagingManifestPath = Join-Path $stagingBundleRoot 'manifests\bundle-manifest.json'
if (-not (Test-Path -LiteralPath $stagingManifestPath)) {
    throw "Staging manifest not found: $stagingManifestPath"
}
$stagingManifest = Get-Content -LiteralPath $stagingManifestPath -Raw | ConvertFrom-Json
Assert-BundleManifestPlanBinding -Manifest $stagingManifest -PlanState $planState -BundleRoot $stagingBundleRoot

Write-Host "[build] Cleaning dist directory..."
Remove-IfExists -Root $distRoot -Target $distBundleRoot
Remove-IfExists -Root $distRoot -Target $sourcesRoot
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Write-Host "[build] Copying staging bundle to dist..."
Copy-BundleTree -Source $stagingBundleRoot -Destination $distBundleRoot

Write-Host "[build] Updating bundle manifest..."
$distManifestPath = Join-Path $distBundleRoot 'manifests\bundle-manifest.json'
Update-BundleManifest `
    -ManifestPath $distManifestPath `
    -ArtifactName $ArtifactName `
    -StagingBundleRoot $stagingBundleRoot `
    -DistBundleRoot $distBundleRoot `
    -ZipPath $zipPath `
    -ZipCreated (-not $NoZip) `
    -SourcesRoot $sourcesRoot

Write-Host "[build] Writing dist checksums..."
$distChecksumsPath = Join-Path $distBundleRoot 'manifests\checksums.txt'
Write-BundleChecksums -Root $distBundleRoot -ChecksumPath $distChecksumsPath

Write-Host "[build] Preparing sources archive..."
Ensure-Directory -Path $sourcesRoot
Ensure-Directory -Path $sourcesArchivesRoot
foreach ($name in @('bundle-plan.json', 'agent.json', 'agent.lock.json')) {
    Copy-Item `
        -LiteralPath (Join-Path $stagingBundleRoot ('manifests\' + $name)) `
        -Destination (Join-Path $sourcesRoot $name) `
        -Force
}

if (-not (Test-Path -LiteralPath $pythonWheelsSourceRoot)) {
    throw "Checked Python wheelhouse not found: $pythonWheelsSourceRoot"
}
$pythonDistributionChecker = Join-Path $projectRoot 'scripts\check-python-distributions.py'
$packagePython = Resolve-PackagePythonPath -ProjectRoot $projectRoot
$checkerOutput = @(& $packagePython $pythonDistributionChecker --dist-dir $pythonWheelsSourceRoot --bundle-plan (Join-Path $stagingBundleRoot 'manifests\bundle-plan.json'))
if ($LASTEXITCODE -ne 0) {
    throw "Python distribution wheelhouse failed validation: $pythonWheelsSourceRoot"
}
$checkerReport = ($checkerOutput -join "`n") | ConvertFrom-Json
if (-not $checkerReport.ok -or @($checkerReport.verified_wheels).Count -ne @($bundlePlan.project_distribution_ids).Count) {
    throw "Python distribution checker did not return the selected verified_wheels: $pythonWheelsSourceRoot"
}
Write-Host "[build] Archiving checked Python wheels..."
$null = Publish-VerifiedPythonWheels `
    -SourceRoot $pythonWheelsSourceRoot `
    -DestinationRoot $pythonWheelsArchiveRoot `
    -WheelNames @($checkerReport.verified_wheels) `
    -PythonPath $packagePython `
    -CheckerPath $pythonDistributionChecker `
    -BundlePlanPath (Join-Path $stagingBundleRoot 'manifests\bundle-plan.json')

$checkerReportPath = Join-Path $sourcesRoot 'checker-report.json'
$checkerOutputText = $checkerOutput -join "`n"
Set-Content -LiteralPath $checkerReportPath -Value ($checkerOutputText + "`n") -Encoding ASCII
$projectWheels = @($checkerReport.verified_wheels)
$projectDistributions = @($bundlePlan.project_distribution_ids)
$wheelHashes = [ordered]@{}
foreach ($wheelName in $projectWheels) {
    $wheelPath = Join-Path $pythonWheelsSourceRoot ([string]$wheelName)
    $wheelHashes[[string]$wheelName] = (Get-FileHash -LiteralPath $wheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
}
$identitySourcePath = if ($ReleaseIdentityPath) {
    if ([System.IO.Path]::IsPathRooted($ReleaseIdentityPath)) { $ReleaseIdentityPath } else { Join-Path $projectRoot $ReleaseIdentityPath }
}
else {
    Join-Path $projectRoot 'manifests\release-identity.json'
}
$targetReportSchemaSource = Join-Path $projectRoot 'scripts\target-report.schema.json'
$depsReportSource = if ($DepsReportPath) {
    if ([System.IO.Path]::IsPathRooted($DepsReportPath)) { $DepsReportPath } else { Join-Path $projectRoot $DepsReportPath }
}
else {
    Join-Path $projectRoot 'build\offline-reports\deps.json'
}
$identityCopied = @(Copy-OptionalReleaseFile -Source $identitySourcePath -Destinations @(
    (Join-Path $sourcesRoot 'release-identity.json'),
    (Join-Path $distBundleRoot 'manifests\release-identity.json'),
    (Join-Path $distBundleRoot 'manifests\evidence\release-identity.json')
))
$evidencePlanPath = Join-Path $distBundleRoot 'manifests\evidence\bundle-plan.json'
Copy-Item `
    -LiteralPath (Join-Path $stagingBundleRoot 'manifests\bundle-plan.json') `
    -Destination $evidencePlanPath `
    -Force
$schemaCopied = @(Copy-OptionalReleaseFile -Source $targetReportSchemaSource -Destinations @(
    (Join-Path $sourcesRoot 'target-report.schema.json'),
    (Join-Path $distBundleRoot 'manifests\evidence\target-report.schema.json')
))
$depsCopied = @(Copy-OptionalReleaseFile -Source $depsReportSource -Destinations @(
    (Join-Path $sourcesRoot 'deps-report.json'),
    (Join-Path $distBundleRoot 'manifests\deps-report.json')
))

$assetManifest = Load-AssetManifest -ManifestPath $assetManifestResolved
$distManifest = Get-Content -LiteralPath $distManifestPath -Raw | ConvertFrom-Json
$distManifest | Add-Member -NotePropertyName project_distributions -NotePropertyValue $projectDistributions -Force
$distManifest | Add-Member -NotePropertyName project_wheels -NotePropertyValue $projectWheels -Force
$distManifest | Add-Member -NotePropertyName wheel_hashes -NotePropertyValue $wheelHashes -Force
$distManifest | Add-Member -NotePropertyName identity_path -NotePropertyValue $(if ($identityCopied.Count -gt 0) { 'manifests/release-identity.json' } else { '' }) -Force
$distManifest | Add-Member -NotePropertyName source_mode -NotePropertyValue 'wheel-installed' -Force
$distManifest | Add-Member -NotePropertyName artifact_status -NotePropertyValue 'provisional' -Force
$distManifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $distManifestPath -Encoding ASCII
$expectedHashesPath = Join-Path $distBundleRoot 'manifests\evidence\expected-bundle-hashes.json'
$expectedHashes = [ordered]@{
    schema_version = 1
    artifact_name = $ArtifactName
    flavor_id = [string]$bundlePlan.flavor_id
    target_id = [string]$bundlePlan.target_id
    bundle_plan_sha256 = [string]$planState.plan_sha256
    agent_lock_sha256 = [string]$bundlePlan.agent_lock_sha256
    gate_ids = @($bundlePlan.gate_ids)
    release_identity_sha256 = $(if (Test-Path -LiteralPath (Join-Path $distBundleRoot 'manifests\release-identity.json')) { (Get-FileHash -LiteralPath (Join-Path $distBundleRoot 'manifests\release-identity.json') -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null })
    bundle_sha256 = $null
    zip_sha256 = $null
    hash_scope = 'bundle tree excluding checksums, generated smoke/acceptance reports, and this file; zip hash is the external sidecar value'
}
$expectedHashes | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $expectedHashesPath -Encoding ASCII
$expectedHashes.bundle_sha256 = Get-BundleTreeSha256 -Root $distBundleRoot -ExcludedRelativePaths @('manifests/evidence/expected-bundle-hashes.json', 'manifests/cli-smoke-report.json', 'manifests/cpp-smoke-report.json', 'manifests/evidence/win7-evidence.json', 'manifests/evidence/acceptance-report.json')
$expectedHashes | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $expectedHashesPath -Encoding ASCII
Copy-Item -LiteralPath $expectedHashesPath -Destination (Join-Path $sourcesRoot 'expected-bundle-hashes.json') -Force
Write-BundleChecksums -Root $distBundleRoot -ChecksumPath $distChecksumsPath
$resolvedAssetIds = @()
foreach ($asset in @($distManifest.resolved_assets)) {
    if ($asset.id) {
        $resolvedAssetIds += $asset.id
    }
}
$resolvedAssetIds = @($resolvedAssetIds | Select-Object -Unique)

$selectedAssets = @()
foreach ($asset in @($assetManifest.assets)) {
    if ($resolvedAssetIds -contains $asset.id) {
        $selectedAssets += $asset
    }
}

$sourcesManifest = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    artifact_name = $ArtifactName
    assets = $selectedAssets
    project_distributions = $projectDistributions
    project_wheels = $projectWheels
    wheel_hashes = $wheelHashes
    identity_path = $(if ($identityCopied.Count -gt 0) { 'release-identity.json' } else { '' })
    checker_report_path = 'checker-report.json'
    deps_report_path = $(if ($depsCopied.Count -gt 0) { 'deps-report.json' } else { '' })
    target_report_schema_path = $(if ($schemaCopied.Count -gt 0) { 'target-report.schema.json' } else { '' })
    source_mode = 'wheel-installed'
}
$sourcesManifestPath = Join-Path $sourcesRoot 'assets-manifest.json'
$sourcesManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $sourcesManifestPath -Encoding ASCII

foreach ($asset in @($distManifest.resolved_assets)) {
    if (-not $asset.cache_archive_path) {
        continue
    }
    if (-not (Test-Path -LiteralPath $asset.cache_archive_path)) {
        continue
    }
    $archiveName = Split-Path -Leaf $asset.cache_archive_path
    Copy-Item -LiteralPath $asset.cache_archive_path -Destination (Join-Path $sourcesArchivesRoot $archiveName) -Force
}

Write-Host "[build] Writing sources checksums..."
$sourcesChecksumsPath = Join-Path $sourcesRoot 'checksums.txt'
Write-BundleChecksums -Root $sourcesRoot -ChecksumPath $sourcesChecksumsPath

$zipCreated = $false
if (-not $NoZip) {
    Write-Host "[build] Creating distribution zip archive..."
    Create-BundleZip -SourceDirectory $distBundleRoot -ZipPath $zipPath
    $zipCreated = $true

    Write-Host "[build]   Zip created"
}

$artifactHashesPath = Join-Path $sourcesRoot 'artifact-hashes.json'
$artifactHashes = [ordered]@{
    schema_version = 1
    artifact_name = $ArtifactName
    flavor_id = [string]$bundlePlan.flavor_id
    target_id = [string]$bundlePlan.target_id
    bundle_plan_sha256 = [string]$planState.plan_sha256
    agent_lock_sha256 = [string]$bundlePlan.agent_lock_sha256
    gate_ids = @($bundlePlan.gate_ids)
    bundle_sha256 = Get-BundleTreeSha256 -Root $distBundleRoot -ExcludedRelativePaths @('manifests/evidence/expected-bundle-hashes.json', 'manifests/cli-smoke-report.json', 'manifests/cpp-smoke-report.json', 'manifests/evidence/win7-evidence.json', 'manifests/evidence/acceptance-report.json')
    zip_sha256 = $(if ($zipCreated) { (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null })
    identity_sha256 = $(if (Test-Path -LiteralPath (Join-Path $distBundleRoot 'manifests\release-identity.json')) { (Get-FileHash -LiteralPath (Join-Path $distBundleRoot 'manifests\release-identity.json') -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null })
}
$artifactHashes | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $artifactHashesPath -Encoding ASCII
$artifactHashes | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $sourcesRoot 'expected-bundle-hashes.json') -Encoding ASCII
Write-BundleChecksums -Root $sourcesRoot -ChecksumPath $sourcesChecksumsPath
Write-Host ""
Write-Host "=========================================="
Write-Host "[build] Offline bundle build complete"
Write-Host "  Bundle dir: $distBundleRoot"
Write-Host "  Sources: $sourcesRoot"
if ($zipCreated) {
    Write-Host "  Zip: $zipPath"
}
else {
    Write-Host "  Zip: skipped"
}
Write-Host "=========================================="
