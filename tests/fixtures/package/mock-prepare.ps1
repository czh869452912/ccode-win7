[CmdletBinding()]
param(
    [string[]]$AssetIds = @(),
    [string]$BundlePlanPath = "",
    [string]$BundlePlanSha256 = "",
    [switch]$AllowDownload,
    [string]$SitePackagesRoot = "",
    [string]$BuildRoot = "",
    [string]$AssetCacheRoot = "",
    [string]$GuiLauncherExePath = ""
)

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $projectRoot 'scripts\package-lib.ps1')

if (-not $AllowDownload) {
    throw 'mock prepare expected AllowDownload'
}
if (-not $SitePackagesRoot) {
    throw 'mock prepare expected SitePackagesRoot'
}

$planState = Read-VerifiedBundlePlan `
    -ProjectRoot $projectRoot `
    -BundlePlanPath $BundlePlanPath `
    -BundlePlanSha256 $BundlePlanSha256
$bundlePlan = $planState.plan
$normalizedAssetIds = @()
foreach ($item in @($AssetIds)) {
    $normalizedAssetIds += @(([string]$item -split ',') | Where-Object { $_ } | ForEach-Object { $_.Trim() })
}
if (($normalizedAssetIds -join '|') -ne (@($bundlePlan.asset_ids) -join '|')) {
    throw 'mock prepare AssetIds do not match the bundle plan'
}

$effectiveBuildRoot = if ($BuildRoot) { $BuildRoot } else { Join-Path $projectRoot 'build' }
$bundleRoot = Join-Path $effectiveBuildRoot 'offline-staging\EmbedAgent'
$manifestRoot = Join-Path $bundleRoot 'manifests'
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'manifests') -Force | Out-Null
foreach ($source in @(
    $planState.plan_path,
    $planState.agent_manifest_path,
    $planState.agent_lock_path
)) {
    Copy-Item -LiteralPath $source -Destination (Join-Path $manifestRoot (Split-Path -Leaf $source)) -Force
}

$configTemplatePath = Join-Path $projectRoot ('config\bundle-flavors\{0}.json' -f [string]$bundlePlan.config_template_id)
if (-not (Test-Path -LiteralPath $configTemplatePath -PathType Leaf)) {
    throw "mock config template not found: $configTemplatePath"
}
$configTemplate = Get-Content -LiteralPath $configTemplatePath -Raw | ConvertFrom-Json
if ($configTemplate.PSObject.Properties.Name -contains 'api_key') {
    throw 'mock config template must not contain api_key'
}
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'config') -Force | Out-Null
Copy-Item -LiteralPath $configTemplatePath -Destination (Join-Path $bundleRoot 'config\config.json') -Force
Copy-Item -LiteralPath $configTemplatePath -Destination (Join-Path $bundleRoot 'config\config.json.template') -Force

function Stage-MockRuntimePath {
    param([string]$RelativePath)

    $target = Join-Path $bundleRoot $RelativePath.Replace('/', '\')
    if ([System.IO.Path]::GetExtension($target)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Set-Content -LiteralPath $target -Value $RelativePath -Encoding ASCII
    }
    else {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
}

foreach ($launcherId in @($bundlePlan.launcher_ids)) {
    $launcher = @($planState.runtime_contract.launchers | Where-Object { [string]$_.id -eq [string]$launcherId })[0]
    $launcherPath = Join-Path $bundleRoot ([string]$launcher.path).Replace('/', '\')
    Set-Content -LiteralPath $launcherPath -Value ([string]$launcherId) -Encoding ASCII
}
foreach ($runtimeComponentId in @($bundlePlan.runtime_component_ids)) {
    $runtimeComponent = @($planState.runtime_contract.runtime_components | Where-Object { [string]$_.id -eq [string]$runtimeComponentId })[0]
    foreach ($relativePath in @($runtimeComponent.paths)) {
        Stage-MockRuntimePath -RelativePath ([string]$relativePath)
    }
    foreach ($tool in @($runtimeComponent.managed_tools)) {
        if ($tool.PSObject.Properties.Name -contains 'paths') {
            foreach ($relativePath in @($tool.paths)) {
                Stage-MockRuntimePath -RelativePath ([string]$relativePath)
            }
        }
        if (($tool.PSObject.Properties.Name -contains 'alternatives') -and @($tool.alternatives).Count -gt 0) {
            foreach ($relativePath in @($tool.alternatives[0].paths)) {
                Stage-MockRuntimePath -RelativePath ([string]$relativePath)
            }
        }
        if ($tool.PSObject.Properties.Name -contains 'children') {
            foreach ($child in @($tool.children)) {
                if ($child.path) {
                    Stage-MockRuntimePath -RelativePath ([string]$child.path)
                }
            }
        }
    }
}
if (@($bundlePlan.runtime_component_ids) -contains 'webview2') {
    Set-Content -LiteralPath (Join-Path $bundleRoot 'runtime\webview2-fixed-runtime\msedgewebview2.exe') -Value 'webview2' -Encoding ASCII
}
if (@($bundlePlan.gate_ids) -contains 'cpp_smoke_workspace') {
    New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'data\workspace-template') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $bundleRoot 'data\workspace-template\main.c') -Value 'int main(void) { return 0; }' -Encoding ASCII
    New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'tools\validation') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $bundleRoot 'tools\validation\validate-cpp-smoke.py') -Value '# fixture' -Encoding ASCII
}
if (@($bundlePlan.gate_ids) -contains 'gui_headless_smoke') {
    New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'tools\validation') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $bundleRoot 'tools\validation\validate-gui-smoke.py') -Value '# fixture' -Encoding ASCII
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
    components = @()
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $manifestRoot 'bundle-manifest.json') -Encoding ASCII
Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\checksums.txt') -Value @() -Encoding ASCII
Write-Host "mock prepare complete"
