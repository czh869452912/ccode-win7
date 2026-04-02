[CmdletBinding()]
param(
    [string[]]$AssetIds = @(),
    [switch]$AllowDownload
)

if (@($AssetIds).Count -eq 0) {
    throw 'mock prepare expected AssetIds'
}
if (-not $AllowDownload) {
    throw 'mock prepare expected AllowDownload'
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$bundleRoot = Join-Path $projectRoot 'build\offline-staging\EmbedAgent'
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'manifests') -Force | Out-Null
@{
    schema_version = 2
    components = @()
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\bundle-manifest.json') -Encoding ASCII
Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\checksums.txt') -Value @() -Encoding ASCII
Write-Host "mock prepare complete"
