[CmdletBinding()]
param(
    [string]$ArtifactName = 'embedagent-win7-x64',
    [switch]$RunPrepare,
    [switch]$PrepareSkipBuild,
    [switch]$NoZip,
    [switch]$Clean,
    [string]$PythonRuntimeRoot = "",
    [string]$SitePackagesRoot = "",
    [string]$MinGitRoot = "",
    [string]$RipgrepPath = "",
    [string]$CtagsPath = "",
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
    Remove-Item -LiteralPath $Target -Recurse -Force
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

function Update-BundleManifest {
    param(
        [string]$ManifestPath,
        [string]$ArtifactName,
        [string]$StagingBundleRoot,
        [string]$DistBundleRoot,
        [string]$ZipPath,
        [bool]$ZipCreated
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
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding ASCII
}

function Write-BundleChecksums {
    param(
        [string]$BundleRoot
    )

    $checksumPath = Join-Path $BundleRoot 'manifests\checksums.txt'
    $filesToHash = Get-ChildItem -LiteralPath $BundleRoot -Recurse -File |
        Where-Object { $_.FullName -ne $checksumPath } |
        Sort-Object FullName
    $checksumLines = @()
    foreach ($file in $filesToHash) {
        $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
        $relative = $file.FullName.Substring($BundleRoot.Length).TrimStart('\')
        $checksumLines += ('{0} *{1}' -f $hash.Hash.ToLowerInvariant(), $relative.Replace('\', '/'))
    }
    Set-Content -LiteralPath $checksumPath -Value $checksumLines -Encoding ASCII
}

function Invoke-PrepareOffline {
    param(
        [string]$PrepareScript,
        [bool]$PrepareSkipBuild,
        [string]$PythonRuntimeRoot,
        [string]$SitePackagesRoot,
        [string]$MinGitRoot,
        [string]$RipgrepPath,
        [string]$CtagsPath,
        [string]$LlvmRoot
    )

    $prepareParams = @{}
    if ($PrepareSkipBuild) {
        $prepareParams.SkipBuild = $true
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
$buildRoot = Join-Path $projectRoot 'build'
$stagingBundleRoot = Join-Path $buildRoot 'offline-staging\EmbedAgent'
$distRoot = Join-Path $buildRoot 'offline-dist'
$distBundleRoot = Join-Path $distRoot $ArtifactName
$zipPath = Join-Path $distRoot ($ArtifactName + '.zip')
$prepareScript = Join-Path $PSScriptRoot 'prepare-offline.ps1'

Ensure-Directory -Path $buildRoot
Ensure-Directory -Path $distRoot

$shouldPrepare = $RunPrepare -or (-not (Test-Path -LiteralPath $stagingBundleRoot))
if ($shouldPrepare) {
    Invoke-PrepareOffline `
        -PrepareScript $prepareScript `
        -PrepareSkipBuild ([bool]$PrepareSkipBuild) `
        -PythonRuntimeRoot $PythonRuntimeRoot `
        -SitePackagesRoot $SitePackagesRoot `
        -MinGitRoot $MinGitRoot `
        -RipgrepPath $RipgrepPath `
        -CtagsPath $CtagsPath `
        -LlvmRoot $LlvmRoot
}

if (-not (Test-Path -LiteralPath $stagingBundleRoot)) {
    throw "Staging bundle not found: $stagingBundleRoot"
}

$stagingManifestPath = Join-Path $stagingBundleRoot 'manifests\bundle-manifest.json'
if (-not (Test-Path -LiteralPath $stagingManifestPath)) {
    throw "Staging manifest not found: $stagingManifestPath"
}

if ($Clean) {
    Remove-IfExists -Root $distRoot -Target $distBundleRoot
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
}
else {
    Remove-IfExists -Root $distRoot -Target $distBundleRoot
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
}

Copy-BundleTree -Source $stagingBundleRoot -Destination $distBundleRoot

$distManifestPath = Join-Path $distBundleRoot 'manifests\bundle-manifest.json'
Update-BundleManifest `
    -ManifestPath $distManifestPath `
    -ArtifactName $ArtifactName `
    -StagingBundleRoot $stagingBundleRoot `
    -DistBundleRoot $distBundleRoot `
    -ZipPath $zipPath `
    -ZipCreated (-not $NoZip)

Write-BundleChecksums -BundleRoot $distBundleRoot

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
        -ZipCreated $zipCreated
    Write-BundleChecksums -BundleRoot $distBundleRoot
}

Write-Host ('Built offline bundle directory at {0}' -f $distBundleRoot)
if ($zipCreated) {
    Write-Host ('Built offline bundle zip at {0}' -f $zipPath)
}
else {
    Write-Host 'Zip generation skipped.'
}
