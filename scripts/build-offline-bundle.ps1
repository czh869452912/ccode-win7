[CmdletBinding()]
param(
    [string]$ArtifactName = 'embedagent-win7-x64',
    [string]$AssetManifestPath = 'scripts/offline-assets.json',
    [switch]$RunPrepare,
    [switch]$PrepareSkipBuild,
    [switch]$AllowDownload,
    [string[]]$AssetIds = @(),
    [switch]$NoZip,
    [switch]$Clean,
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
        [string[]]$AssetIds,
        [bool]$PrepareSkipBuild,
        [bool]$AllowDownload,
        [string]$PythonRuntimeRoot,
        [string]$SitePackagesRoot,
        [string]$MinGitRoot,
        [string]$RipgrepPath,
        [string]$CtagsPath,
        [string]$LlvmRoot
    )

    $prepareParams = @{
        AssetManifestPath = $AssetManifestPath
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
    if ($LlvmRoot) {
        $prepareParams.LlvmRoot = $LlvmRoot
    }
    & $PrepareScript @prepareParams
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
$normalizedAssetIds = Normalize-AssetIds -AssetIds $AssetIds
$buildRoot = Join-Path $projectRoot 'build'
$stagingBundleRoot = Join-Path $buildRoot 'offline-staging\EmbedAgent'
$distRoot = Join-Path $buildRoot 'offline-dist'
$distBundleRoot = Join-Path $distRoot $ArtifactName
$sourcesRoot = Join-Path $distRoot ($ArtifactName + '-sources')
$sourcesArchivesRoot = Join-Path $sourcesRoot 'archives'
$zipPath = Join-Path $distRoot ($ArtifactName + '.zip')
$prepareScript = Join-Path $PSScriptRoot 'prepare-offline.ps1'

Ensure-Directory -Path $buildRoot
Ensure-Directory -Path $distRoot

$shouldPrepare = $RunPrepare -or (-not (Test-Path -LiteralPath $stagingBundleRoot))
if ($shouldPrepare) {
    Invoke-PrepareOffline `
        -PrepareScript $prepareScript `
        -AssetManifestPath $assetManifestResolved `
        -AssetIds $normalizedAssetIds `
        -PrepareSkipBuild ([bool]$PrepareSkipBuild) `
        -AllowDownload ([bool]$AllowDownload) `
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

$stagingManifestPath = Join-Path $stagingBundleRoot 'manifests\bundle-manifest.json'
if (-not (Test-Path -LiteralPath $stagingManifestPath)) {
    throw "Staging manifest not found: $stagingManifestPath"
}

Remove-IfExists -Root $distRoot -Target $distBundleRoot
Remove-IfExists -Root $distRoot -Target $sourcesRoot
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Copy-BundleTree -Source $stagingBundleRoot -Destination $distBundleRoot

$distManifestPath = Join-Path $distBundleRoot 'manifests\bundle-manifest.json'
Update-BundleManifest `
    -ManifestPath $distManifestPath `
    -ArtifactName $ArtifactName `
    -StagingBundleRoot $stagingBundleRoot `
    -DistBundleRoot $distBundleRoot `
    -ZipPath $zipPath `
    -ZipCreated (-not $NoZip) `
    -SourcesRoot $sourcesRoot

$distChecksumsPath = Join-Path $distBundleRoot 'manifests\checksums.txt'
Write-BundleChecksums -Root $distBundleRoot -ChecksumPath $distChecksumsPath

Ensure-Directory -Path $sourcesRoot
Ensure-Directory -Path $sourcesArchivesRoot

$assetManifest = Load-AssetManifest -ManifestPath $assetManifestResolved
$distManifest = Get-Content -LiteralPath $distManifestPath -Raw | ConvertFrom-Json
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

$sourcesChecksumsPath = Join-Path $sourcesRoot 'checksums.txt'
Write-BundleChecksums -Root $sourcesRoot -ChecksumPath $sourcesChecksumsPath

$zipCreated = $false
if (-not $NoZip) {
    Create-BundleZip -SourceDirectory $distBundleRoot -ZipPath $zipPath
    $zipCreated = $true
    Update-BundleManifest `
        -ManifestPath $distManifestPath `
        -ArtifactName $ArtifactName `
        -StagingBundleRoot $stagingBundleRoot `
        -DistBundleRoot $distBundleRoot `
        -ZipPath $zipPath `
        -ZipCreated $zipCreated `
        -SourcesRoot $sourcesRoot
    Write-BundleChecksums -Root $distBundleRoot -ChecksumPath $distChecksumsPath
}

Write-Host ('Built offline bundle directory at {0}' -f $distBundleRoot)
Write-Host ('Built offline sources seed at {0}' -f $sourcesRoot)
if ($zipCreated) {
    Write-Host ('Built offline bundle zip at {0}' -f $zipPath)
}
else {
    Write-Host 'Zip generation skipped.'
}
