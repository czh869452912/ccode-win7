[CmdletBinding()]
param(
    [string]$OutputPath = ""
)

if (-not $OutputPath) {
    throw 'mock GUI launcher build expected OutputPath'
}

$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
Set-Content -LiteralPath $OutputPath -Value 'mock gui launcher' -Encoding ASCII
Write-Host "mock GUI launcher build complete"
