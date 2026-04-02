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
        [System.Collections.IDictionary]$Context
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

function Resolve-ToolPath {
    param(
        [System.Collections.IDictionary]$Context,
        [string]$RelativePath
    )

    return Resolve-ConfigPath -ProjectRoot $Context.project_root -Path $RelativePath
}

function Get-PackageRequiredAssetIds {
    param(
        [System.Collections.IDictionary]$Context
    )

    $requiredAssets = @()
    if ($Context.profile_config -and $Context.profile_config.required_assets) {
        foreach ($assetId in @($Context.profile_config.required_assets)) {
            $value = "$assetId".Trim()
            if ($value) {
                $requiredAssets += $value
            }
        }
    }
    return @($requiredAssets | Select-Object -Unique)
}

function Get-PackagePythonCandidates {
    param(
        [string]$ProjectRoot
    )

    $candidates = @()
    if ($env:EMBEDAGENT_PYTHON) {
        $candidates += [string]$env:EMBEDAGENT_PYTHON
    }
    if ($ProjectRoot) {
        $candidates += (Join-Path $ProjectRoot '.venv\Scripts\python.exe')
    }

    $resolved = @()
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $resolved += (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $resolved
}

function Resolve-PackagePythonPath {
    param(
        [string]$ProjectRoot
    )

    $candidates = Get-PackagePythonCandidates -ProjectRoot $ProjectRoot
    if (@($candidates).Count -eq 0) {
        $expectedPath = if ($ProjectRoot) {
            Join-Path $ProjectRoot '.venv\Scripts\python.exe'
        }
        else {
            '.venv\Scripts\python.exe'
        }
        throw ('Expected project virtualenv Python at {0} or an explicit EMBEDAGENT_PYTHON override. Run ''uv sync --python 3.8.10'' to provision the locked environment.' -f $expectedPath)
    }
    return $candidates[0]
}

function Resolve-PackagePowerShellPath {
    $currentProcess = Get-Process -Id $PID -ErrorAction SilentlyContinue
    if ($currentProcess -and $currentProcess.Path -and (Test-Path -LiteralPath $currentProcess.Path)) {
        return $currentProcess.Path
    }

    foreach ($commandName in @('pwsh', 'powershell')) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source)) {
            return $command.Source
        }
    }

    throw 'PowerShell executable not found for packaging.'
}

function Invoke-StageScript {
    param(
        [string]$ProjectRoot,
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    $extension = [System.IO.Path]::GetExtension($ScriptPath).ToLowerInvariant()
    if ($extension -eq '.py') {
        $pythonCandidates = Get-PackagePythonCandidates -ProjectRoot $ProjectRoot
        if (@($pythonCandidates).Count -eq 0) {
            $null = Resolve-PackagePythonPath -ProjectRoot $ProjectRoot
        }

        $errors = @()
        foreach ($pythonPath in $pythonCandidates) {
            try {
                $result = & $pythonPath $ScriptPath @Arguments 2>&1
                if ($LASTEXITCODE -eq 0) {
                    return $result
                }
                $errors += ('{0} exited with code {1}' -f $pythonPath, $LASTEXITCODE)
            }
            catch {
                $errors += ('{0} failed: {1}' -f $pythonPath, $_.Exception.Message)
            }
        }
        throw ('Python stage script failed for all candidates. ' + ($errors -join '; '))
    }
    if ($extension -eq '.ps1') {
        $powerShellPath = Resolve-PackagePowerShellPath
        $result = & $powerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @Arguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw ('PowerShell stage script failed: {0} (exit {1})' -f $ScriptPath, $LASTEXITCODE)
        }
        return $result
    }
    throw "Unsupported stage script extension: $ScriptPath"
}

function New-ReportPath {
    param(
        [System.Collections.IDictionary]$Context,
        [string]$StageName
    )

    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    if (-not (Test-Path -LiteralPath $reportsRoot)) {
        New-Item -ItemType Directory -Path $reportsRoot -Force | Out-Null
    }
    return Join-Path $reportsRoot ($StageName + '.json')
}

function Invoke-PackageDeps {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    $scriptPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.export_dependencies)
    $jsonPath = New-ReportPath -Context $Context -StageName 'deps'
    $outputRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.site_packages_export_root)
    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $scriptPath -Arguments @('--output-dir', $outputRoot, '--json-report', $jsonPath)
    $payload = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    Add-StageResult -Report $Report -Name 'deps' -Status $(if ($payload.ok) { 'pass' } else { 'fail' }) -ExitCode $(if ($payload.ok) { 0 } else { 1 }) -Summary @{ report = $jsonPath }
}

function Invoke-PackageAssemble {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    $preparePath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.prepare_bundle)
    $buildPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.build_bundle)
    $requiredAssetIds = Get-PackageRequiredAssetIds -Context $Context
    $prepareArgs = @()
    if (@($requiredAssetIds).Count -gt 0) {
        $prepareArgs += '-AssetIds'
        $prepareArgs += ($requiredAssetIds -join ',')
    }
    if ([bool]$Context.allow_download) {
        $prepareArgs += '-AllowDownload'
    }

    $buildArgs = @('-ArtifactName', [string]$Context.artifact_name)
    if (@($requiredAssetIds).Count -gt 0) {
        $buildArgs += '-AssetIds'
        $buildArgs += ($requiredAssetIds -join ',')
    }
    if ([bool]$Context.allow_download) {
        $buildArgs += '-AllowDownload'
    }

    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $preparePath -Arguments $prepareArgs
    Add-StageResult -Report $Report -Name 'prepare' -Status 'pass' -ExitCode 0 -Summary @{ script = $preparePath }
    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $buildPath -Arguments $buildArgs
    Add-StageResult -Report $Report -Name 'build' -Status 'pass' -ExitCode 0 -Summary @{ script = $buildPath; artifact_name = $Context.artifact_name }
}

function Invoke-PackageVerify {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    $bundleRoot = if ($Context.bundle_root) {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path $Context.bundle_root
    }
    else {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.dist_bundle_root)
    }
    if (-not (Test-Path -LiteralPath $bundleRoot)) {
        Add-StageResult -Report $Report -Name 'verify' -Status 'fail' -ExitCode 1 -Summary @{ reason = 'bundle_root_missing'; bundle_root = $bundleRoot }
        return
    }

    $validateScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.validate_bundle)
    $checkScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.check_dependencies)
    $validateJson = New-ReportPath -Context $Context -StageName 'validate'
    $checkJson = New-ReportPath -Context $Context -StageName 'check'

    $validateArgs = @('-BundleRoot', $bundleRoot, '-JsonOutputPath', $validateJson, '-SkipDynamicChecks')
    if ([bool]$Context.profile_config.require_complete -or [bool]$Context.strict) {
        $validateArgs += '-RequireComplete'
    }
    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $validateScript -Arguments $validateArgs
    $validatePayload = Get-Content -LiteralPath $validateJson -Raw | ConvertFrom-Json

    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $checkScript -Arguments @($bundleRoot, '--json-report', $checkJson)
    $checkPayload = Get-Content -LiteralPath $checkJson -Raw | ConvertFrom-Json

    $verifyOk = ([bool]$validatePayload.ok) -and ([bool]$checkPayload.ok)
    Add-StageResult -Report $Report -Name 'verify' -Status $(if ($verifyOk) { 'pass' } else { 'fail' }) -ExitCode $(if ($verifyOk) { 0 } else { 1 }) -Summary @{
        bundle_root = $bundleRoot
        validate_report = $validateJson
        dependency_report = $checkJson
    }
}

function Write-PackageReport {
    param(
        [System.Collections.IDictionary]$Context,
        [System.Collections.IDictionary]$Report
    )

    $reportsRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.reports_root)
    if (-not (Test-Path -LiteralPath $reportsRoot)) {
        New-Item -ItemType Directory -Path $reportsRoot -Force | Out-Null
    }
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
    $reportPath = Join-Path $reportsRoot ($timestamp + '-' + $Context.command + '.json')
    $latestPath = Join-Path $reportsRoot 'latest.json'
    $Report.report_path = $reportPath
    $Report.generated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $json = $Report | ConvertTo-Json -Depth 10
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($reportPath, $json, $utf8NoBom)
    [System.IO.File]::WriteAllText($latestPath, $json, $utf8NoBom)
    return $reportPath
}

function Invoke-PackageCommand {
    param(
        [System.Collections.IDictionary]$Context
    )

    $report = New-PackageReport -Command $Context.command -Profile $Context.profile
    switch ($Context.command) {
        'deps' {
            Invoke-PackageDeps -Context $Context -Report ([ref]$report)
        }
        'assemble' {
            Invoke-PackageAssemble -Context $Context -Report ([ref]$report)
        }
        'verify' {
            Invoke-PackageVerify -Context $Context -Report ([ref]$report)
        }
        'release' {
            Invoke-PackageDeps -Context $Context -Report ([ref]$report)
            if (@($report.blocking_issues).Count -eq 0) {
                Invoke-PackageAssemble -Context $Context -Report ([ref]$report)
            }
            if (@($report.blocking_issues).Count -eq 0) {
                Invoke-PackageVerify -Context $Context -Report ([ref]$report)
            }
        }
        default {
            throw "Unsupported packaging command: $($Context.command)"
        }
    }
    Complete-PackageReport -Report ([ref]$report)
    $null = Write-PackageReport -Context $Context -Report $report
    return $report
}
