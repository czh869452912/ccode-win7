[CmdletBinding()]
param(
    [string]$BundleRoot = '',
    [string]$JsonOutputPath = '',
    [switch]$SkipDynamicChecks,
    [switch]$RequireComplete
)

$payload = [ordered]@{
    ok = $true
    bundle_root = $BundleRoot
    fail_count = 0
    warn_count = 0
    pass_count = 1
    results = @(
        [ordered]@{
            level = 'pass'
            code = 'mock.validate'
            message = 'mock validate succeeded'
        }
    )
}

if ($JsonOutputPath) {
    $parent = Split-Path -Parent $JsonOutputPath
    if ($parent -and (-not (Test-Path -LiteralPath $parent))) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $JsonOutputPath -Encoding ASCII
}

Write-Host "mock validate complete"
