[CmdletBinding()]
param(
    [string]$ArtifactName = 'mock-artifact'
)

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$distRoot = Join-Path $projectRoot 'build\offline-dist'
$bundleRoot = Join-Path $distRoot $ArtifactName
New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'manifests') -Force | Out-Null
@{
    schema_version = 2
    components = @()
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\bundle-manifest.json') -Encoding ASCII
Set-Content -LiteralPath (Join-Path $bundleRoot 'manifests\checksums.txt') -Value @() -Encoding ASCII
Set-Content -LiteralPath (Join-Path $distRoot ($ArtifactName + '.zip')) -Value 'zip-sentinel' -Encoding ASCII
Write-Host "mock build complete"
