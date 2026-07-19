[CmdletBinding()]
param(
    [string]$ArtifactName = 'mock-artifact',
    [string[]]$AssetIds = @(),
    [switch]$AllowDownload,
    [string]$BuildRoot = "",
    [string]$AssetCacheRoot = "",
    [string]$DepsReportPath = ""
)

if (@($AssetIds).Count -eq 0) {
    throw 'mock build expected AssetIds'
}
if (-not $AllowDownload) {
    throw 'mock build expected AllowDownload'
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$effectiveBuildRoot = if ($BuildRoot) { $BuildRoot } else { Join-Path $projectRoot 'build' }
$distRoot = Join-Path $effectiveBuildRoot 'offline-dist'
$bundleRoot = Join-Path $distRoot $ArtifactName
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'manifests') -Force | Out-Null
@{
    schema_version = 2
    components = @()
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\bundle-manifest.json') -Encoding ASCII
Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\checksums.txt') -Value @() -Encoding ASCII
$names = @(
    'embedagent-core',
    'embedagent-protocol',
    'embedagent-host',
    'embedagent-composition',
    'embedagent-workflow-cpp',
    'embedagent'
)
$identity = [ordered]@{
    schema_version = 1
    source_revision = ((& git -C $projectRoot rev-parse HEAD 2>$null | Out-String).Trim())
    version = '0.1.0'
    profile = 'release'
    project_distributions = $names
    wheels = @($names | ForEach-Object {
        [ordered]@{
            name = $_
            filename = ($_.Replace('-', '_') + '-0.1.0-py3-none-any.whl')
            sha256 = ('a' * 64)
        }
    })
    gui_static_sha256 = ('b' * 64)
    asset_manifest_sha256 = ('c' * 64)
    runtime_contract_sha256 = ('d' * 64)
    bundle_sha256 = $null
    zip_sha256 = $null
    tool_metadata = @{ python = '3.8' }
}
$identity | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\release-identity.json') -Encoding ASCII
$stableContent = if ($env:EMBEDAGENT_REPRO_MUTATE_SECOND -and $effectiveBuildRoot -like '*run-b*') { 'mutated' } else { 'stable' }
Set-Content -LiteralPath (Join-Path $bundleRoot 'stable.txt') -Value $stableContent -Encoding ASCII
Set-Content -LiteralPath (Join-Path $distRoot ($ArtifactName + '.zip')) -Value 'zip-sentinel' -Encoding ASCII
Write-Host "mock build complete"
