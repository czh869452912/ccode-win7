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

function New-PackageContext {
    param(
        [string]$ProjectRoot,
        [object]$Config,
        [string]$ConfigPath,
        [string]$Command,
        [string]$RequestedProfile,
        [string]$BundleRoot,
        [string]$OutputRoot,
        [string]$ArtifactName,
        [bool]$AllowDownload,
        [bool]$NoZip,
        [bool]$Strict
    )

    $effectiveProfile = if ($RequestedProfile) {
        $RequestedProfile
    }
    elseif ($Command -eq 'release') {
        'release'
    }
    else {
        [string]$Config.default_profile
    }

    $profileConfig = $Config.profiles.$effectiveProfile
    if (-not $profileConfig) {
        throw "Unknown packaging profile: $effectiveProfile"
    }

    return [ordered]@{
        project_root = $ProjectRoot
        config_path = $ConfigPath
        config = $Config
        command = $Command
        profile = $effectiveProfile
        profile_config = $profileConfig
        bundle_root = $BundleRoot
        output_root = $OutputRoot
        artifact_name = $(if ($ArtifactName) { $ArtifactName } else { [string]$profileConfig.artifact_name })
        allow_download = $AllowDownload -or [bool]$profileConfig.allow_download
        no_zip = $NoZip
        strict = $Strict
    }
}

function Invoke-PackageDoctor {
    param(
        [hashtable]$Context
    )

    $report = New-PackageReport -Command 'doctor' -Profile $Context.profile
    $doctorChecks = @()

    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.asset_manifest)
    $toolingRootChecks = @(
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.export_dependencies))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.prepare_bundle))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.build_bundle))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.validate_bundle))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.check_dependencies))
    )

    $doctorChecks += [ordered]@{ name = 'config'; ok = (Test-Path -LiteralPath $Context.config_path); path = $Context.config_path }
    $doctorChecks += [ordered]@{ name = 'asset_manifest'; ok = (Test-Path -LiteralPath $assetManifestPath); path = $assetManifestPath }
    foreach ($toolPath in $toolingRootChecks) {
        $doctorChecks += [ordered]@{ name = ('tool:' + [System.IO.Path]::GetFileName($toolPath)); ok = (Test-Path -LiteralPath $toolPath); path = $toolPath }
    }

    foreach ($check in $doctorChecks) {
        if (-not $check.ok) {
            $report.blocking_issues += ('Missing required path: ' + $check.path)
        }
    }

    $report.doctor_checks = $doctorChecks
    Complete-PackageReport -Report ([ref]$report)
    return $report
}
