[CmdletBinding()]
param(
    [string]$ArtifactName = 'mock-artifact',
    [string[]]$AssetIds = @(),
    [string]$BundlePlanPath = "",
    [string]$BundlePlanSha256 = "",
    [switch]$AllowDownload,
    [string]$BuildRoot = "",
    [string]$AssetCacheRoot = "",
    [string]$DepsReportPath = ""
)

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $projectRoot 'scripts\package-lib.ps1')

if (-not $AllowDownload) {
    throw 'mock build expected AllowDownload'
}
$planState = Read-VerifiedBundlePlan `
    -ProjectRoot $projectRoot `
    -BundlePlanPath $BundlePlanPath `
    -BundlePlanSha256 $BundlePlanSha256
$normalizedAssetIds = @()
foreach ($item in @($AssetIds)) {
    $normalizedAssetIds += @(([string]$item -split ',') | Where-Object { $_ } | ForEach-Object { $_.Trim() })
}
if (($normalizedAssetIds -join '|') -ne (@($planState.plan.asset_ids) -join '|')) {
    throw 'mock build AssetIds do not match the bundle plan'
}

$effectiveBuildRoot = if ($BuildRoot) { $BuildRoot } else { Join-Path $projectRoot 'build' }
$distRoot = Join-Path $effectiveBuildRoot 'offline-dist'
$bundleRoot = Join-Path $distRoot $ArtifactName
$stagingBundleRoot = Join-Path $effectiveBuildRoot 'offline-staging\EmbedAgent'
$stagingManifestPath = Join-Path $stagingBundleRoot 'manifests\bundle-manifest.json'
if (-not (Test-Path -LiteralPath $stagingManifestPath -PathType Leaf)) {
    throw "mock staging manifest not found: $stagingManifestPath"
}
$stagingManifest = Get-Content -LiteralPath $stagingManifestPath -Raw | ConvertFrom-Json
Assert-BundleManifestPlanBinding -Manifest $stagingManifest -PlanState $planState -BundleRoot $stagingBundleRoot
New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null
Copy-Item -Path (Join-Path $stagingBundleRoot '*') -Destination $bundleRoot -Recurse -Force
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
    schema_version = 2
    source_revision = ((& git -C $projectRoot rev-parse HEAD 2>$null | Out-String).Trim())
    version = '0.1.0'
    profile = 'release'
    flavor_id = [string]$planState.plan.flavor_id
    target_id = [string]$planState.plan.target_id
    bundle_plan_sha256 = [string]$planState.plan_sha256
    agent_lock_sha256 = [string]$planState.plan.agent_lock_sha256
    gate_ids = @($planState.plan.gate_ids)
    project_distributions = $names
    wheels = @($names | ForEach-Object {
        [ordered]@{
            name = $_
            filename = ($_.Replace('-', '_') + '-0.1.0-py3-none-any.whl')
            sha256 = ('a' * 64)
        }
    })
    gui_static_sha256 = $(if (@($planState.plan.shell_ids) -contains 'gui') { ('b' * 64) } else { $null })
    asset_manifest_sha256 = ('c' * 64)
    runtime_contract_sha256 = ('d' * 64)
    bundle_sha256 = $null
    zip_sha256 = $null
    tool_metadata = @{ python = '3.8' }
}
$identity | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\release-identity.json') -Encoding ASCII
$evidenceRoot = Join-Path $bundleRoot 'manifests\evidence'
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
Copy-Item `
    -LiteralPath (Join-Path $bundleRoot 'manifests\bundle-plan.json') `
    -Destination (Join-Path $evidenceRoot 'bundle-plan.json') `
    -Force
$sourcesRoot = Join-Path $distRoot ($ArtifactName + '-sources')
New-Item -ItemType Directory -Path $sourcesRoot -Force | Out-Null
foreach ($name in @('bundle-plan.json', 'agent.json', 'agent.lock.json')) {
    Copy-Item -LiteralPath (Join-Path $bundleRoot ('manifests\' + $name)) -Destination (Join-Path $sourcesRoot $name) -Force
}
$stableContent = if ($env:EMBEDAGENT_REPRO_MUTATE_SECOND -and $effectiveBuildRoot -like '*run-b*') { 'mutated' } else { 'stable' }
Set-Content -LiteralPath (Join-Path $bundleRoot 'stable.txt') -Value $stableContent -Encoding ASCII
Set-Content -LiteralPath (Join-Path $distRoot ($ArtifactName + '.zip')) -Value 'zip-sentinel' -Encoding ASCII
Write-Host "mock build complete"
