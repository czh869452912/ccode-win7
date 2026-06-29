Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Write-PackageLog {
    param([string]$Message)
    if (-not $Global:PackageJsonMode) {
        Write-Host $Message
    }
}

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

function New-PackageStageTimer {
    $started = Get-Date
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    return [ordered]@{
        started_at = $started.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        stopwatch = $stopwatch
    }
}

function Add-StageResult {
    param(
        [object]$Report,
        [string]$Name,
        [string]$Status,
        [int]$ExitCode,
        [hashtable]$Summary,
        [object]$StageTimer = $null
    )

    $target = $Report
    if ($target.PSObject.Properties.Name -contains 'Value') {
        $target = $target.Value
    }
    if ($target -isnot [System.Collections.IDictionary] -and ($target.PSObject.Properties.Name -contains 'Value')) {
        $target = $target.Value
    }

    $finished = Get-Date
    $startedAt = $finished.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $durationMs = 0
    if ($StageTimer -and $StageTimer -is [System.Collections.IDictionary]) {
        if ($StageTimer.Contains('started_at')) {
            $startedAt = [string]$StageTimer['started_at']
        }
        if ($StageTimer.Contains('stopwatch') -and $StageTimer['stopwatch']) {
            $timer = $StageTimer['stopwatch']
            $timer.Stop()
            $durationMs = [int64]$timer.ElapsedMilliseconds
        }
    }

    $stage = [ordered]@{
        name = $Name
        status = $Status
        exit_code = $ExitCode
        started_at = $startedAt
        finished_at = $finished.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        duration_ms = $durationMs
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

function Get-GuiStaticAssetStatus {
    param(
        [string]$StaticRoot
    )

    $assetsRoot = Join-Path $StaticRoot 'assets'
    $required = [ordered]@{
        'index.html' = (Join-Path $StaticRoot 'index.html')
        'app.js' = (Join-Path $assetsRoot 'app.js')
        'app.css' = (Join-Path $assetsRoot 'app.css')
        'katex.min.css' = (Join-Path $assetsRoot 'katex\katex.min.css')
    }
    $missing = @()
    foreach ($name in $required.Keys) {
        if (-not (Test-Path -LiteralPath $required[$name])) {
            $missing += $name
        }
    }
    return [ordered]@{
        ok = ($missing.Count -eq 0)
        static_root = $StaticRoot
        assets_root = $assetsRoot
        paths = $required
        missing = $missing
    }
}

function Get-GuiFrontendAssetStatus {
    param(
        [string]$ProjectRoot
    )

    $staticRoot = Join-Path $ProjectRoot 'src\embedagent\frontend\gui\static'
    $status = Get-GuiStaticAssetStatus -StaticRoot $staticRoot
    $status['project_root'] = $ProjectRoot
    $status['webapp_root'] = Join-Path $ProjectRoot 'src\embedagent\frontend\gui\webapp'
    return $status
}

function Get-GuiBundleAssetStatus {
    param(
        [string]$BundleRoot
    )

    $staticRoot = Join-Path $BundleRoot 'app\embedagent\frontend\gui\static'
    $status = Get-GuiStaticAssetStatus -StaticRoot $staticRoot
    $status['bundle_root'] = $BundleRoot
    return $status
}

function Ensure-GuiFrontendAssets {
    param(
        [string]$ProjectRoot,
        [switch]$ForceBuild
    )

    $before = Get-GuiFrontendAssetStatus -ProjectRoot $ProjectRoot
    if ($before.ok -and (-not $ForceBuild)) {
        return [ordered]@{
            ok = $true
            mode = 'prebuilt'
            static_root = $before.static_root
            assets_root = $before.assets_root
            missing = @()
        }
    }

    $webappDir = [string]$before.webapp_root
    if (-not (Test-Path -LiteralPath $webappDir)) {
        return [ordered]@{
            ok = $false
            mode = 'missing'
            reason = 'webapp_dir_missing'
            static_root = $before.static_root
            missing = @($before.missing)
            path = $webappDir
        }
    }

    $npmCmd = 'npm'
    try {
        $npmVersion = (& $npmCmd --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $npmVersion) {
            throw 'npm --version failed'
        }
    }
    catch {
        return [ordered]@{
            ok = $false
            mode = 'missing'
            reason = 'npm_not_found'
            static_root = $before.static_root
            missing = @($before.missing)
            hint = 'Install Node.js >= 18 on the build machine or restore prebuilt GUI static assets.'
        }
    }

    Push-Location $webappDir
    try {
        $oldEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $installOutput = & $npmCmd install --force 2>&1
            $installExit = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $oldEap
        }
        if ($installExit -ne 0) {
            return [ordered]@{
                ok = $false
                mode = 'build_failed'
                reason = 'npm_install_failed'
                static_root = $before.static_root
                missing = @($before.missing)
                npm_version = $npmVersion
                error = ('npm install --force failed (exit {0}): {1}' -f $installExit, ($installOutput | Out-String).Trim())
            }
        }
        $oldEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $buildOutput = & $npmCmd run build 2>&1
            $buildExit = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $oldEap
        }
        if ($buildExit -ne 0) {
            return [ordered]@{
                ok = $false
                mode = 'build_failed'
                reason = 'npm_build_failed'
                static_root = $before.static_root
                missing = @($before.missing)
                npm_version = $npmVersion
                error = ('npm run build failed (exit {0}): {1}' -f $LASTEXITCODE, ($buildOutput | Out-String).Trim())
            }
        }
    }
    finally {
        Pop-Location
    }

    $after = Get-GuiFrontendAssetStatus -ProjectRoot $ProjectRoot
    if (-not $after.ok) {
        return [ordered]@{
            ok = $false
            mode = 'build_failed'
            reason = 'assets_missing_after_build'
            static_root = $after.static_root
            missing = @($after.missing)
            npm_version = $npmVersion
        }
    }

    return [ordered]@{
        ok = $true
        mode = 'rebuilt'
        static_root = $after.static_root
        assets_root = $after.assets_root
        missing = @()
        npm_version = $npmVersion
    }
}

function Invoke-PackageDoctor {
    param(
        [System.Collections.IDictionary]$Context
    )

    Write-PackageLog "[doctor] Running environment checks..."
    $report = New-PackageReport -Command 'doctor' -Profile $Context.profile
    $doctorChecks = @()

    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.asset_manifest)
    $toolingRootChecks = @(
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.export_dependencies))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.build_gui_launcher))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.prepare_bundle))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.build_bundle))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.validate_bundle))
        (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.tooling.check_dependencies))
    )

    $doctorChecks += [ordered]@{ name = 'config'; ok = (Test-Path -LiteralPath $Context.config_path); path = $Context.config_path }
    $doctorChecks += [ordered]@{ name = 'asset_manifest'; ok = (Test-Path -LiteralPath $assetManifestPath); path = $assetManifestPath }
    Write-PackageLog "[doctor] Checking configuration files..." 
    foreach ($toolPath in $toolingRootChecks) {
        $doctorChecks += [ordered]@{ name = ('tool:' + [System.IO.Path]::GetFileName($toolPath)); ok = (Test-Path -LiteralPath $toolPath); path = $toolPath }
    }

    # Check that Node.js / npm are available on the build machine, or that
    # complete prebuilt GUI static assets already exist in the source tree.
    $npmOk = $false
    $npmVersion = ''
    try {
        $npmVersion = (& npm --version 2>&1 | Out-String).Trim()
        $npmOk = ($LASTEXITCODE -eq 0) -and ($npmVersion -ne '')
    } catch { $npmOk = $false }
    $prebuiltFrontendStatus = Get-GuiFrontendAssetStatus -ProjectRoot $Context.project_root
    $prebuiltFrontendOk = [bool]$prebuiltFrontendStatus.ok
    $doctorChecks += [ordered]@{
        name = 'runtime:npm'
        ok = ($npmOk -or $prebuiltFrontendOk)
        path = if ($npmOk) { "npm ($npmVersion)" } else { "prebuilt frontend assets present at $($prebuiltFrontendStatus.static_root)" }
    }

    foreach ($check in $doctorChecks) {
        $status = if ($check.ok) { "OK" } else { "FAIL" }
        Write-PackageLog ("[doctor]   {0}: {1} ({2})" -f $check.name, $status, $check.path)
        if (-not $check.ok) {
            if ($check.name -eq 'runtime:npm') {
                $report.warnings += ('Optional runtime unavailable: ' + $check.path)
            }
            else {
                $report.blocking_issues += ('Missing required path: ' + $check.path)
            }
        }
    }

    $report.doctor_checks = $doctorChecks
    Complete-PackageReport -Report ([ref]$report)
    $overall = if ($report.command_status -eq 'READY') { "READY" } else { "NOT_READY" }
    Write-PackageLog ("[doctor] Overall status: {0}" -f $overall)
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
    Write-Output -NoEnumerate @($resolved)
    return
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
        Write-PackageLog ("[stage] Invoking {0}..." -f $ScriptPath)
        $procArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) + $Arguments
        if ($Global:PackageJsonMode) {
            # In JSON mode, capture output so it does not pollute stdout.
            $null = & $powerShellPath @procArgs 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw ('PowerShell stage script failed: {0} (exit {1})' -f $ScriptPath, $LASTEXITCODE)
            }
        } else {
            & $powerShellPath @procArgs
            $exitCode = $LASTEXITCODE
            Write-PackageLog ("[stage]   exited {0}: {1}" -f $exitCode, $ScriptPath)
            if ($exitCode -ne 0) {
                throw ('PowerShell stage script failed: {0} (exit {1})' -f $ScriptPath, $exitCode)
            }
        }
        return
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
    $timer = New-PackageStageTimer
    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $scriptPath -Arguments @('--output-dir', $outputRoot, '--json-report', $jsonPath)
    $payload = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    Add-StageResult -Report $Report -Name 'deps' -Status $(if ($payload.ok) { 'pass' } else { 'fail' }) -ExitCode $(if ($payload.ok) { 0 } else { 1 }) -Summary @{ report = $jsonPath } -StageTimer $timer
}

function Invoke-FrontendBuild {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[assemble] Building GUI frontend assets..."
    $timer = New-PackageStageTimer
    $result = Ensure-GuiFrontendAssets -ProjectRoot $Context.project_root -ForceBuild
    if (-not $result.ok) {
        Write-PackageLog ("[assemble]   frontend_build FAILED: {0}" -f $result.reason)
        Add-StageResult -Report $Report -Name 'frontend_build' -Status 'fail' -ExitCode 1 -Summary $result -StageTimer $timer
        return
    }
    Write-PackageLog ("[assemble]   frontend_build OK ({0})" -f $result.mode)
    Add-StageResult -Report $Report -Name 'frontend_build' -Status 'pass' -ExitCode 0 -Summary $result -StageTimer $timer
}

function Get-GuiLauncherOutputPath {
    param(
        [System.Collections.IDictionary]$Context
    )

    $outputRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.gui_launcher_build_root)
    return Join-Path $outputRoot 'embedagent-gui.exe'
}

function Invoke-GuiLauncherBuild {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    $scriptPath = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.build_gui_launcher)
    $outputPath = Get-GuiLauncherOutputPath -Context $Context
    $summary = @{
        script = $scriptPath
        output = $outputPath
    }

    Write-PackageLog "[assemble] Building native GUI launcher..."
    $timer = New-PackageStageTimer
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $scriptPath -Arguments @('-OutputPath', $outputPath)
    }
    catch {
        $summary.error = $_.Exception.Message
        Write-PackageLog ("[assemble]   gui_launcher_build FAILED: {0}" -f $_.Exception.Message)
        Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'fail' -ExitCode 1 -Summary $summary -StageTimer $timer
        return ''
    }

    if (-not (Test-Path -LiteralPath $outputPath)) {
        $summary.error = 'launcher_output_missing'
        Write-PackageLog ("[assemble]   gui_launcher_build FAILED: output missing at {0}" -f $outputPath)
        Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'fail' -ExitCode 1 -Summary $summary -StageTimer $timer
        return ''
    }

    Write-PackageLog ("[assemble]   gui_launcher_build OK ({0})" -f $outputPath)
    Add-StageResult -Report $Report -Name 'gui_launcher_build' -Status 'pass' -ExitCode 0 -Summary $summary -StageTimer $timer
    return $outputPath
}

function Invoke-PackageAssemble {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[assemble] Starting package assembly (profile: $($Context.profile))..."

    if ([bool]$Context.profile_config.run_frontend_build) {
        Invoke-FrontendBuild -Context $Context -Report $Report
        if (@($Report.Value.blocking_issues).Count -gt 0) { return }
    }

    $guiLauncherExePath = ''
    if ([bool]$Context.profile_config.run_gui_launcher_build) {
        $guiLauncherExePath = Invoke-GuiLauncherBuild -Context $Context -Report $Report
        if (@($Report.Value.blocking_issues).Count -gt 0) { return }
    }

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
    if ($guiLauncherExePath) {
        $prepareArgs += '-GuiLauncherExePath'
        $prepareArgs += $guiLauncherExePath
    }
    $sitePackagesRoot = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.site_packages_root)
    if ($sitePackagesRoot -and (Test-Path -LiteralPath $sitePackagesRoot)) {
        $prepareArgs += '-SitePackagesRoot'
        $prepareArgs += $sitePackagesRoot
    }

    $buildArgs = @('-ArtifactName', [string]$Context.artifact_name)
    if (@($requiredAssetIds).Count -gt 0) {
        $buildArgs += '-AssetIds'
        $buildArgs += ($requiredAssetIds -join ',')
    }
    if ([bool]$Context.allow_download) {
        $buildArgs += '-AllowDownload'
    }

    Write-PackageLog "[assemble] Running prepare-offline.ps1..."
    $prepareTimer = New-PackageStageTimer
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $preparePath -Arguments $prepareArgs
    }
    catch {
        Write-PackageLog ("[assemble]   prepare FAILED: {0}" -f $_.Exception.Message)
        Add-StageResult -Report $Report -Name 'prepare' -Status 'fail' -ExitCode 1 -Summary @{ script = $preparePath; site_packages_root = $sitePackagesRoot; error = $_.Exception.Message } -StageTimer $prepareTimer
        return
    }
    Write-PackageLog "[assemble]   prepare OK"
    Add-StageResult -Report $Report -Name 'prepare' -Status 'pass' -ExitCode 0 -Summary @{ script = $preparePath; site_packages_root = $sitePackagesRoot } -StageTimer $prepareTimer

    Write-PackageLog "[assemble] Running build-offline-bundle.ps1..."
    $buildTimer = New-PackageStageTimer
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $buildPath -Arguments $buildArgs
    }
    catch {
        Write-PackageLog ("[assemble]   build FAILED: {0}" -f $_.Exception.Message)
        Add-StageResult -Report $Report -Name 'build' -Status 'fail' -ExitCode 1 -Summary @{ script = $buildPath; artifact_name = $Context.artifact_name; error = $_.Exception.Message } -StageTimer $buildTimer
        return
    }
    Write-PackageLog "[assemble]   build OK"
    Add-StageResult -Report $Report -Name 'build' -Status 'pass' -ExitCode 0 -Summary @{ script = $buildPath; artifact_name = $Context.artifact_name } -StageTimer $buildTimer

    Write-PackageLog "[assemble] Package assembly complete"
}

function Invoke-PackageVerify {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[verify] Starting bundle verification..."
    $bundleRoot = if ($Context.bundle_root) {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path $Context.bundle_root
    }
    else {
        Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.dist_bundle_root)
    }
    if (-not (Test-Path -LiteralPath $bundleRoot)) {
        Write-PackageLog ("[verify]   FAIL: Bundle root not found: {0}" -f $bundleRoot)
        Add-StageResult -Report $Report -Name 'verify' -Status 'fail' -ExitCode 1 -Summary @{ reason = 'bundle_root_missing'; bundle_root = $bundleRoot }
        return
    }

    $validateScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.validate_bundle)
    $checkScript = Resolve-ToolPath -Context $Context -RelativePath ([string]$Context.config.tooling.check_dependencies)
    $validateJson = New-ReportPath -Context $Context -StageName 'validate'
    $checkJson = New-ReportPath -Context $Context -StageName 'check'

    Write-PackageLog "[verify] Running validate-offline-bundle.ps1..."
    $verifyTimer = New-PackageStageTimer
    $validateArgs = @('-BundleRoot', $bundleRoot, '-JsonOutputPath', $validateJson)
    if (-not [bool]$Context.profile_config.run_dynamic_checks) {
        $validateArgs += '-SkipDynamicChecks'
    }
    if ([bool]$Context.profile_config.require_complete -or [bool]$Context.strict) {
        $validateArgs += '-RequireComplete'
    }
    try {
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $validateScript -Arguments $validateArgs
        $validatePayload = Get-Content -LiteralPath $validateJson -Raw | ConvertFrom-Json
        Write-PackageLog ("[verify]   validate: {0}" -f $(if ($validatePayload.ok) { "OK" } else { "FAIL" }))

        Write-PackageLog "[verify] Running check-bundle-dependencies.py..."
        $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $checkScript -Arguments @($bundleRoot, '--json-report', $checkJson)
        $checkPayload = Get-Content -LiteralPath $checkJson -Raw | ConvertFrom-Json
        Write-PackageLog ("[verify]   dependencies: {0}" -f $(if ($checkPayload.ok) { "OK" } else { "FAIL" }))
    }
    catch {
        Add-StageResult -Report $Report -Name 'verify' -Status 'fail' -ExitCode 1 -Summary @{
            bundle_root = $bundleRoot
            validate_report = $validateJson
            dependency_report = $checkJson
            error = $_.Exception.Message
        } -StageTimer $verifyTimer
        return
    }

    $verifyOk = ([bool]$validatePayload.ok) -and ([bool]$checkPayload.ok)
    Add-StageResult -Report $Report -Name 'verify' -Status $(if ($verifyOk) { 'pass' } else { 'fail' }) -ExitCode $(if ($verifyOk) { 0 } else { 1 }) -Summary @{
        bundle_root = $bundleRoot
        validate_report = $validateJson
        dependency_report = $checkJson
    } -StageTimer $verifyTimer
    Write-PackageLog ("[verify] Overall: {0}" -f $(if ($verifyOk) { "PASS" } else { "FAIL" }))
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

    Write-PackageLog ""
    Write-PackageLog ("=== Package Command: {0} (profile: {1}) ===" -f $Context.command, $Context.profile)
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
    $statusStr = $report.command_status
    if ($report.final_status) {
        $statusStr = $report.final_status
    }
    Write-PackageLog ("=== Command finished: {0} ===" -f $statusStr)
    Write-PackageLog ""
    return $report
}
