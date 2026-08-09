[CmdletBinding()]
param(
    [string]$BundleRoot = '',
    [string]$JsonOutputPath = '',
    [string]$BundlePlanPath = '',
    [string]$BundlePlanSha256 = '',
    [switch]$SkipDynamicChecks,
    [switch]$RequireComplete
)

if (-not (Test-Path -LiteralPath $BundlePlanPath -PathType Leaf)) {
    throw 'mock validate expected BundlePlanPath'
}
$actualPlanSha256 = (Get-FileHash -LiteralPath $BundlePlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualPlanSha256 -ne $BundlePlanSha256.ToLowerInvariant()) {
    throw 'mock validate bundle plan hash mismatch'
}
$bundlePlan = Get-Content -LiteralPath $BundlePlanPath -Raw | ConvertFrom-Json
$results = @(
    [ordered]@{
        level = 'pass'
        code = 'mock.validate'
        message = 'mock validate succeeded'
    }
)
if ((-not $SkipDynamicChecks) -and (@($bundlePlan.gate_ids) -contains 'win7_cli_smoke')) {
    $results += [ordered]@{
        level = 'pass'
        code = 'dynamic.release_gate.win7_cli_smoke'
        message = 'mock CLI smoke gate succeeded'
    }
}

$payload = [ordered]@{
    ok = $true
    bundle_root = $BundleRoot
    skip_dynamic_checks = [bool]$SkipDynamicChecks
    require_complete = [bool]$RequireComplete
    fail_count = 0
    warn_count = 0
    pass_count = @($results).Count
    bundle_plan = [ordered]@{
        path = $BundlePlanPath
        source_path = $BundlePlanPath
        sha256 = $actualPlanSha256
    }
    results = $results
}

if ($JsonOutputPath) {
    $parent = Split-Path -Parent $JsonOutputPath
    if ($parent -and (-not (Test-Path -LiteralPath $parent))) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $JsonOutputPath -Encoding ASCII
}

Write-Host "mock validate complete"
