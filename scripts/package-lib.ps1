Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-ConfigPath {
    param(
        [string]$ProjectRoot,
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $ProjectRoot $Path
}

function Read-PackageConfig {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Package config not found: $Path"
    }
    $raw = Get-Content -LiteralPath $Path -Raw
    $config = $raw | ConvertFrom-Json
    if (-not $config.profiles.dev -or -not $config.profiles.release) {
        throw "Package config must define both dev and release profiles."
    }
    return $config
}

function New-PackageReport {
    param(
        [string]$Command,
        [string]$Profile
    )

    return [ordered]@{
        command = $Command
        profile = $Profile
        started_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        command_status = 'running'
        final_status = $null
        stages = @()
        blocking_issues = @()
        warnings = @()
    }
}

function Add-StageResult {
    param(
        [object]$Report,
        [string]$Name,
        [string]$Status,
        [int]$ExitCode,
        [hashtable]$Summary
    )

    $target = $Report
    if ($target.PSObject.Properties.Name -contains 'Value') {
        $target = $target.Value
    }
    if ($target -isnot [System.Collections.IDictionary] -and ($target.PSObject.Properties.Name -contains 'Value')) {
        $target = $target.Value
    }

    $stage = [ordered]@{
        name = $Name
        status = $Status
        exit_code = $ExitCode
        summary = $Summary
    }
    $target['stages'] += $stage
    if ($Status -eq 'fail') {
        $target['blocking_issues'] += ('Stage failed: ' + $Name)
    }
    elseif ($Status -eq 'warn') {
        $target['warnings'] += ('Stage warned: ' + $Name)
    }
}

function Complete-PackageReport {
    param(
        [object]$Report
    )

    $report = $Report
    if ($report.PSObject.Properties.Name -contains 'Value') {
        $report = $report.Value
    }
    if ($report -isnot [System.Collections.IDictionary] -and ($report.PSObject.Properties.Name -contains 'Value')) {
        $report = $report.Value
    }
    $hasFailures = @($report['blocking_issues']).Count -gt 0
    if ($report['command'] -eq 'doctor') {
        $report['command_status'] = if ($hasFailures) { 'NOT_READY' } else { 'READY' }
        $report['final_status'] = $null
        return
    }

    if ($hasFailures) {
        $report['final_status'] = 'NOT_READY'
    }
    elseif ($report['command'] -eq 'release' -or $report['profile'] -eq 'release') {
        $report['final_status'] = 'READY'
    }
    else {
        $report['final_status'] = 'DEV_ONLY'
    }
    $report['command_status'] = 'completed'
}

function Get-PackageExitCode {
    param(
        [System.Collections.IDictionary]$Report
    )

    if ($Report['command'] -eq 'doctor') {
        return $(if ($Report['command_status'] -eq 'READY') { 0 } else { 1 })
    }

    switch ($Report['final_status']) {
        'READY' { return 0 }
        'DEV_ONLY' { return 0 }
        'NOT_READY' { return 1 }
        default { return 2 }
    }
}
