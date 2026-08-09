[CmdletBinding()]
param(
    [string[]]$AssetIds = @(),
    [switch]$AllowDownload,
    [string]$SitePackagesRoot = "",
    [string]$BuildRoot = "",
    [string]$AssetCacheRoot = "",
    [string]$GuiLauncherExePath = ""
)

if (@($AssetIds).Count -eq 0) {
    throw 'mock prepare expected AssetIds'
}
if (-not $AllowDownload) {
    throw 'mock prepare expected AllowDownload'
}
if (-not $SitePackagesRoot) {
    throw 'mock prepare expected SitePackagesRoot'
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$effectiveBuildRoot = if ($BuildRoot) { $BuildRoot } else { Join-Path $projectRoot 'build' }
$bundleRoot = Join-Path $effectiveBuildRoot 'offline-staging\EmbedAgent'
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'manifests') -Force | Out-Null
@{
    schema_version = 2
    components = @()
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\bundle-manifest.json') -Encoding ASCII
Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\checksums.txt') -Value @() -Encoding ASCII
Write-Host "mock prepare complete"
