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

function Copy-VerifiedPythonWheels {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot,
        [string[]]$WheelNames
    )

    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Python wheel source directory not found: $SourceRoot"
    }
    if (@($WheelNames).Count -ne 6) {
        throw 'Exactly six verified Python wheel names are required.'
    }

    $sourceRootItem = Get-Item -LiteralPath $SourceRoot -Force
    if (($sourceRootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Python wheel source directory must not be a reparse point: $SourceRoot"
    }
    $resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationRoot)
    if ($resolvedSourceRoot -eq $destinationFullPath) {
        throw 'Python wheel source and destination directories must differ.'
    }
    if (Test-Path -LiteralPath $DestinationRoot) {
        $destinationItem = Get-Item -LiteralPath $DestinationRoot -Force
        if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Python wheel destination must not be a reparse point: $DestinationRoot"
        }
    }

    $seen = @{}
    $validatedNames = @()
    $validatedSourcePaths = @()
    foreach ($wheelName in @($WheelNames)) {
        $name = [string]$wheelName
        if (-not $name -or [System.IO.Path]::GetFileName($name) -ne $name -or -not $name.EndsWith('.whl', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Invalid verified Python wheel name: $name"
        }
        $caseKey = $name.ToUpperInvariant()
        if ($seen.ContainsKey($caseKey)) {
            throw "Duplicate verified Python wheel name: $name"
        }
        $seen[$caseKey] = $true

        $sourcePath = Join-Path $resolvedSourceRoot $name
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Verified Python wheel not found: $name"
        }
        $sourceItem = Get-Item -LiteralPath $sourcePath -Force
        if (($sourceItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Verified Python wheel must not be a reparse point: $name"
        }
        $resolvedSourcePath = (Resolve-Path -LiteralPath $sourcePath).Path
        if ((Split-Path -Parent $resolvedSourcePath) -ne $resolvedSourceRoot) {
            throw "Verified Python wheel resolves outside source directory: $name"
        }
        $validatedNames += $name
        $validatedSourcePaths += $resolvedSourcePath
    }

    foreach ($validatedSourcePath in $validatedSourcePaths) {
        $sourceItem = Get-Item -LiteralPath $validatedSourcePath -Force
        if (($sourceItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Verified Python wheel became a reparse point before copy: $validatedSourcePath"
        }
        if ((Split-Path -Parent (Resolve-Path -LiteralPath $validatedSourcePath).Path) -ne $resolvedSourceRoot) {
            throw "Verified Python wheel resolves outside source directory before copy: $validatedSourcePath"
        }
    }

    if (Test-Path -LiteralPath $DestinationRoot) {
        Remove-Item -LiteralPath $DestinationRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    for ($index = 0; $index -lt $validatedNames.Count; $index++) {
        $name = $validatedNames[$index]
        Copy-Item -LiteralPath $validatedSourcePaths[$index] -Destination (Join-Path $DestinationRoot $name) -Force
    }
    return $validatedNames
}

function Publish-VerifiedPythonWheels {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot,
        [string[]]$WheelNames,
        [string]$PythonPath,
        [string]$CheckerPath
    )

    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "Python executable not found for wheel publication: $PythonPath"
    }
    if (-not (Test-Path -LiteralPath $CheckerPath -PathType Leaf)) {
        throw "Python distribution checker not found: $CheckerPath"
    }

    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationRoot)
    $destinationParent = Split-Path -Parent $destinationFullPath
    if (-not (Test-Path -LiteralPath $destinationParent -PathType Container)) {
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }
    $destinationParentItem = Get-Item -LiteralPath $destinationParent -Force
    if (($destinationParentItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Python wheel destination parent must not be a reparse point: $destinationParent"
    }
    if (Test-Path -LiteralPath $destinationFullPath) {
        $destinationItem = Get-Item -LiteralPath $destinationFullPath -Force
        if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Python wheel destination must not be a reparse point: $destinationFullPath"
        }
        foreach ($child in @(Get-ChildItem -LiteralPath $destinationFullPath -Force)) {
            if ($child.PSIsContainer -or (($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
                throw "Existing Python wheel destination contains an unsafe entry: $($child.Name)"
            }
        }
    }

    $destinationLeaf = Split-Path -Leaf $destinationFullPath
    $uniqueId = [System.Guid]::NewGuid().ToString('N')
    $tempRoot = Join-Path $destinationParent ('.' + $destinationLeaf + '.tmp.' + $uniqueId)
    $backupRoot = Join-Path $destinationParent ('.' + $destinationLeaf + '.backup.' + $uniqueId)
    $published = $false
    $backupCreated = $false
    try {
        $null = Copy-VerifiedPythonWheels `
            -SourceRoot $SourceRoot `
            -DestinationRoot $tempRoot `
            -WheelNames $WheelNames

        $tempItem = Get-Item -LiteralPath $tempRoot -Force
        if (($tempItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Temporary Python wheel directory must not be a reparse point: $tempRoot"
        }
        $checkerOutput = @(& $PythonPath $CheckerPath --dist-dir $tempRoot)
        if ($LASTEXITCODE -ne 0) {
            throw 'copied Python wheelhouse failed validation'
        }
        $checkerReport = ($checkerOutput -join "`n") | ConvertFrom-Json
        $verifiedNames = @($checkerReport.verified_wheels)
        if (-not $checkerReport.ok -or $verifiedNames.Count -ne 6) {
            throw 'copied Python wheelhouse failed validation'
        }
        for ($index = 0; $index -lt $verifiedNames.Count; $index++) {
            if (-not [string]::Equals([string]$verifiedNames[$index], [string]$WheelNames[$index], [System.StringComparison]::OrdinalIgnoreCase)) {
                throw 'copied Python wheelhouse verified a different wheel set'
            }
        }

        $tempItem = Get-Item -LiteralPath $tempRoot -Force
        if (($tempItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Temporary Python wheel directory must not be a reparse point: $tempRoot"
        }
        if (Test-Path -LiteralPath $destinationFullPath) {
            $destinationItem = Get-Item -LiteralPath $destinationFullPath -Force
            if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Python wheel destination must not be a reparse point: $destinationFullPath"
            }
            Move-Item -LiteralPath $destinationFullPath -Destination $backupRoot
            $backupCreated = $true
        }
        try {
            Move-Item -LiteralPath $tempRoot -Destination $destinationFullPath
            $published = $true
        }
        catch {
            if ($backupCreated -and -not (Test-Path -LiteralPath $destinationFullPath)) {
                Move-Item -LiteralPath $backupRoot -Destination $destinationFullPath
                $backupCreated = $false
            }
            throw
        }
        if ($backupCreated) {
            Remove-Item -LiteralPath $backupRoot -Recurse -Force
            $backupCreated = $false
        }
        return $verifiedNames
    }
    finally {
        if (-not $published -and (Test-Path -LiteralPath $tempRoot)) {
            $tempItem = Get-Item -LiteralPath $tempRoot -Force
            if (($tempItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) {
                Remove-Item -LiteralPath $tempRoot -Recurse -Force
            }
        }
        if ($backupCreated -and -not (Test-Path -LiteralPath $destinationFullPath)) {
            Move-Item -LiteralPath $backupRoot -Destination $destinationFullPath
        }
    }
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
        artifact_status = 'provisional'
        publishable = $false
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
        $report['artifact_status'] = 'provisional'
        $report['publishable'] = $false
    }
    elseif ($report['command'] -eq 'release' -or $report['profile'] -eq 'release') {
        $report['final_status'] = 'READY'
        $report['artifact_status'] = 'verified'
        $report['publishable'] = $true
    }
    else {
        $report['final_status'] = 'DEV_ONLY'
        $report['artifact_status'] = 'provisional'
        $report['publishable'] = $false
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

function New-PackageDoctorCheck {
    param(
        [string]$Name,
        [string]$Code,
        [bool]$Ok,
        [bool]$Blocking,
        [string]$Path,
        [string]$Detail = ''
    )

    return [ordered]@{
        name = $Name
        code = $Code
        ok = $Ok
        blocking = $Blocking
        path = $Path
        detail = $Detail
    }
}

function Get-PackageDoctorChecks {
    param(
        [System.Collections.IDictionary]$Context
    )

    $releaseBlocking = [string]::Equals([string]$Context.profile, 'release', [System.StringComparison]::OrdinalIgnoreCase)
    $checks = @()
    $projectRoot = [string]$Context.project_root
    $config = $Context.config
    $configPath = [string]$Context.config_path
    $checks += New-PackageDoctorCheck -Name 'config' -Code 'config' -Ok (Test-Path -LiteralPath $configPath) -Blocking $releaseBlocking -Path $configPath
    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.paths.asset_manifest)
    $checks += New-PackageDoctorCheck -Name 'asset_manifest' -Code 'asset_manifest' -Ok (Test-Path -LiteralPath $assetManifestPath) -Blocking $releaseBlocking -Path $assetManifestPath

    $toolingPaths = @(
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.export_dependencies)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.build_gui_launcher)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.prepare_bundle)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.build_bundle)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.validate_bundle)),
        (Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.tooling.check_dependencies))
    )
    foreach ($toolPath in $toolingPaths) {
        $toolName = [System.IO.Path]::GetFileName($toolPath)
        $checks += New-PackageDoctorCheck -Name ('tool:' + $toolName) -Code ('tool.' + $toolName) -Ok (Test-Path -LiteralPath $toolPath) -Blocking $releaseBlocking -Path $toolPath
    }

    $npmOk = $false
    $npmVersion = ''
    try {
        $npmVersion = (& npm --version 2>&1 | Out-String).Trim()
        $npmOk = ($LASTEXITCODE -eq 0) -and ($npmVersion -ne '')
    }
    catch {
        $npmOk = $false
    }
    $prebuiltFrontendStatus = Get-GuiFrontendAssetStatus -ProjectRoot $projectRoot
    $prebuiltFrontendOk = [bool]$prebuiltFrontendStatus.ok
    $npmPath = if ($npmOk) { 'npm (' + $npmVersion + ')' } else { [string]$prebuiltFrontendStatus.static_root }
    $checks += New-PackageDoctorCheck -Name 'runtime:npm' -Code 'runtime.npm' -Ok ($npmOk -or $prebuiltFrontendOk) -Blocking $releaseBlocking -Path $npmPath

    $pythonPath = ''
    $pythonVersion = ''
    $pythonCandidates = @(Get-PackagePythonCandidates -ProjectRoot $projectRoot)
    if ($pythonCandidates.Count -gt 0) {
        $pythonPath = [string]$pythonCandidates[0]
        try {
            $pythonVersion = (& $pythonPath --version 2>&1 | Out-String).Trim()
        }
        catch {
            $pythonVersion = ''
        }
    }
    $pythonOk = $pythonVersion -match '^Python 3\.8\.'
    $checks += New-PackageDoctorCheck -Name 'python:version' -Code 'python.version' -Ok $pythonOk -Blocking $releaseBlocking -Path $pythonPath -Detail $pythonVersion

    $assetManifest = $null
    try {
        if (Test-Path -LiteralPath $assetManifestPath) {
            $assetManifest = Get-Content -Raw -LiteralPath $assetManifestPath | ConvertFrom-Json
        }
    }
    catch {
        $assetManifest = $null
    }
    $cacheRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path (Join-Path ([string]$config.paths.build_root) 'offline-cache')
    $requiredAssetIds = @()
    if ($Context.profile_config.required_assets) {
        $requiredAssetIds = @($Context.profile_config.required_assets)
    }
    foreach ($assetId in $requiredAssetIds) {
        $asset = @($assetManifest.assets | Where-Object { [string]$_.id -eq [string]$assetId }) | Select-Object -First 1
        $cachePath = if ($asset) { Join-Path $cacheRoot ([string]$asset.cache_relpath) } else { Join-Path $cacheRoot ([string]$assetId) }
        $cacheOk = [bool]$asset -and (Test-Path -LiteralPath $cachePath -PathType Leaf)
        if ($Context.allow_download -and -not $cacheOk) {
            $cacheOk = $true
        }
        $checks += New-PackageDoctorCheck -Name ('asset:' + $assetId) -Code ('asset.cache.' + $assetId) -Ok $cacheOk -Blocking $releaseBlocking -Path $cachePath
    }

    $webviewAsset = @($assetManifest.assets | Where-Object { [string]$_.id -eq 'webview2_fixed_runtime_x64' }) | Select-Object -First 1
    $webviewPath = if ($webviewAsset) { Join-Path $cacheRoot ([string]$webviewAsset.cache_relpath) } else { Join-Path $cacheRoot 'webview2' }
    $webviewOk = [bool]$webviewAsset -and (Test-Path -LiteralPath $webviewPath -PathType Leaf)
    if ($Context.allow_download -and -not $webviewOk) {
        $webviewOk = $true
    }
    $checks += New-PackageDoctorCheck -Name 'asset:webview2_fixed_runtime_x64' -Code 'asset.cache.webview2_fixed_runtime_x64' -Ok $webviewOk -Blocking $releaseBlocking -Path $webviewPath

    $llvmRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.paths.llvm_root)
    $llvmMain = Join-Path $llvmRoot 'bin\clang.exe'
    $checks += New-PackageDoctorCheck -Name 'toolchain:llvm' -Code 'toolchain.llvm' -Ok (Test-Path -LiteralPath $llvmMain -PathType Leaf) -Blocking $releaseBlocking -Path $llvmMain
    foreach ($childName in @('clang.exe', 'clang++.exe', 'clang-cl.exe', 'clang-tidy.exe', 'clang-analyzer.bat', 'llvm-profdata.exe', 'llvm-cov.exe')) {
        $childPath = Join-Path $llvmRoot ('bin\' + $childName)
        $checks += New-PackageDoctorCheck -Name ('toolchain:llvm:' + $childName) -Code ('toolchain.llvm.' + $childName) -Ok (Test-Path -LiteralPath $childPath -PathType Leaf) -Blocking $releaseBlocking -Path $childPath
    }

    $distributionNames = @()
    if ($Context.profile_config.PSObject.Properties.Name -contains 'required_project_distributions') {
        $distributionNames = @($Context.profile_config.required_project_distributions)
    }
    if ($distributionNames.Count -eq 0) {
        $distributionNames = @('embedagent-core', 'embedagent-protocol', 'embedagent-host', 'embedagent-composition', 'embedagent-workflow-cpp', 'embedagent')
    }
    foreach ($distributionName in $distributionNames) {
        $projectPath = if ($distributionName -eq 'embedagent') {
            Join-Path $projectRoot 'pyproject.toml'
        }
        elseif ($distributionName -eq 'embedagent-workflow-cpp') {
            Join-Path $projectRoot 'packages\embedagent-workflow-cpp\pyproject.toml'
        }
        else {
            Join-Path $projectRoot ('packages\' + $distributionName + '\pyproject.toml')
        }
        $checks += New-PackageDoctorCheck -Name ('project:' + $distributionName) -Code ('project.' + $distributionName) -Ok (Test-Path -LiteralPath $projectPath -PathType Leaf) -Blocking $releaseBlocking -Path $projectPath
    }

    $wheelhouseRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path (Join-Path ([string]$config.paths.site_packages_export_root) 'wheels')
    $wheelhouseOk = $true
    $wheelhouseDetail = 'will be created by deps'
    if (Test-Path -LiteralPath $wheelhouseRoot) {
        $wheelhouseItem = Get-Item -LiteralPath $wheelhouseRoot -Force
        $wheelhouseOk = (($wheelhouseItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0)
        if ($wheelhouseOk) {
            foreach ($entry in @(Get-ChildItem -LiteralPath $wheelhouseRoot -Force)) {
                if ($entry.PSIsContainer -or $entry.Extension -ne '.whl') {
                    $wheelhouseOk = $false
                    $wheelhouseDetail = 'unsafe entry: ' + $entry.Name
                    break
                }
            }
        }
    }
    $checks += New-PackageDoctorCheck -Name 'wheelhouse:output_root' -Code 'wheelhouse.output_root' -Ok $wheelhouseOk -Blocking $releaseBlocking -Path $wheelhouseRoot -Detail $wheelhouseDetail

    $buildRoot = Resolve-ConfigPath -ProjectRoot $projectRoot -Path ([string]$config.paths.build_root)
    $buildParent = Split-Path -Qualifier $buildRoot
    $freeBytes = 0
    $freeKnown = $false
    try {
        $driveName = $buildParent.TrimEnd('\').TrimEnd(':')
        $drive = Get-PSDrive -Name $driveName -ErrorAction Stop
        $freeBytes = [int64]$drive.Free
        $freeKnown = $true
    }
    catch {
        $freeKnown = $false
    }
    $minimumBytes = 0
    if ($Context.profile_config.PSObject.Properties.Name -contains 'minimum_free_bytes') {
        if ($Context.profile_config.minimum_free_bytes) {
            $minimumBytes = [int64]$Context.profile_config.minimum_free_bytes
        }
    }
    $freeOk = (-not $freeKnown) -or ($freeBytes -ge $minimumBytes)
    $checks += New-PackageDoctorCheck -Name 'disk:output_free_space' -Code 'disk.output_free_space' -Ok $freeOk -Blocking $releaseBlocking -Path $buildRoot -Detail ([string]$freeBytes)

    return @($checks)
}

function Invoke-PackageDoctor {
    param(
        [System.Collections.IDictionary]$Context
    )

    Write-PackageLog "[doctor] Running environment checks..."
    $report = New-PackageReport -Command 'doctor' -Profile $Context.profile
    $doctorChecks = @(Get-PackageDoctorChecks -Context $Context)
    foreach ($check in $doctorChecks) {
        $status = if ($check.ok) { 'OK' } elseif ($check.blocking) { 'FAIL' } else { 'WARN' }
        Write-PackageLog ("[doctor]   {0}: {1} ({2})" -f $check.name, $status, $check.path)
        if (-not $check.ok) {
            if ($check.blocking) {
                $report.blocking_issues += ([string]$check.code + ': ' + [string]$check.path)
            }
            else {
                $report.warnings += ([string]$check.code + ': ' + [string]$check.path)
            }
        }
    }
    $report.doctor_checks = $doctorChecks
    Complete-PackageReport -Report ([ref]$report)
    $overall = if ($report.command_status -eq 'READY') { 'READY' } else { 'NOT_READY' }
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
    $expectedDistributions = @()
    if ($Context.profile_config.PSObject.Properties.Name -contains 'required_project_distributions') {
        $expectedDistributions = @($Context.profile_config.required_project_distributions)
    }
    if ($expectedDistributions.Count -eq 0) {
        $expectedDistributions = @('embedagent-core', 'embedagent-protocol', 'embedagent-host', 'embedagent-composition', 'embedagent-workflow-cpp', 'embedagent')
    }
    $actualDistributions = @()
    if ($payload.PSObject.Properties.Name -contains 'project_distributions') {
        $actualDistributions = @($payload.project_distributions)
    }
    $actualWheels = @()
    if ($payload.PSObject.Properties.Name -contains 'project_wheels') {
        $actualWheels = @($payload.project_wheels)
    }
    $wheelHashCount = 0
    if (($payload.PSObject.Properties.Name -contains 'wheel_hashes') -and $payload.wheel_hashes) {
        $wheelHashCount = @($payload.wheel_hashes.PSObject.Properties).Count
    }
    $hasSixWheelContract = ($Context.profile_config.PSObject.Properties.Name -contains 'required_project_distributions') -or ($payload.PSObject.Properties.Name -contains 'project_distributions')
    $depsOk = if ($hasSixWheelContract) {
        [bool]$payload.ok -and $actualDistributions.Count -eq $expectedDistributions.Count -and (($actualDistributions -join '|' ) -eq ($expectedDistributions -join '|' )) -and $actualWheels.Count -eq 6 -and $wheelHashCount -eq 6
    } else {
        [bool]$payload.ok
    }
    $actualWheelHashes = $null
    if ($payload.PSObject.Properties.Name -contains 'wheel_hashes') {
        $actualWheelHashes = $payload.wheel_hashes
    }
    $summary = @{
        report = $jsonPath
        project_distributions = $actualDistributions
        project_wheels = $actualWheels
        wheel_hashes = $actualWheelHashes
        output_root = $outputRoot
    }
    if (-not $depsOk) {
        $Report.Value.blocking_issues += 'deps: exact six-wheel report handoff failed'
    }
    $depsStatus = if ($depsOk) { 'pass' } else { 'fail' }
    $depsExitCode = if ($depsOk) { 0 } else { 1 }
    Add-StageResult -Report $Report -Name 'deps' -Status $depsStatus -ExitCode $depsExitCode -Summary $summary -StageTimer $timer
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

function Invoke-ReleaseIdentity {
    param(
        [System.Collections.IDictionary]$Context
    )

    if ($Context.profile -ne 'release') {
        return $null
    }
    if (-not ($Context.config.paths.PSObject.Properties.Name -contains 'release_identity')) {
        return $null
    }
    $identityScript = Join-Path $Context.project_root 'scripts\create-release-identity.py'
    $identityPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.release_identity)
    $wheelRoot = Join-Path (Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.site_packages_export_root)) 'wheels'
    $guiStaticRoot = Join-Path $Context.project_root 'src\embedagent\frontend\gui\static'
    $assetManifestPath = Resolve-ConfigPath -ProjectRoot $Context.project_root -Path ([string]$Context.config.paths.asset_manifest)
    $runtimeContractPath = Join-Path $Context.project_root 'scripts\offline-runtime-contract.json'
    if (-not (Test-Path -LiteralPath $identityScript -PathType Leaf)) {
        throw "Release identity script not found: $identityScript"
    }
    if (-not (Test-Path -LiteralPath $wheelRoot -PathType Container)) {
        throw "Release identity wheelhouse not found: $wheelRoot"
    }
    $arguments = @(
        '--project-root', $Context.project_root,
        '--profile', $Context.profile,
        '--wheel-dir', $wheelRoot,
        '--gui-static-root', $guiStaticRoot,
        '--asset-manifest', $assetManifestPath,
        '--runtime-contract', $runtimeContractPath,
        '--output', $identityPath
    )
    $null = Invoke-StageScript -ProjectRoot $Context.project_root -ScriptPath $identityScript -Arguments $arguments
    $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
    if (@($identity.project_distributions).Count -ne 6 -or @($identity.wheels).Count -ne 6) {
        throw 'Release identity must contain exactly six project distributions and wheels.'
    }
    return [ordered]@{
        path = $identityPath
        source_revision = $identity.source_revision
        version = $identity.version
        project_wheels = @($identity.wheels | ForEach-Object { $_.filename })
    }
}
function Invoke-PackageAssemble {
    param(
        [System.Collections.IDictionary]$Context,
        [ref]$Report
    )

    Write-PackageLog "[assemble] Starting package assembly (profile: $($Context.profile))..."
    $identityTimer = New-PackageStageTimer
    try {
        $identitySummary = Invoke-ReleaseIdentity -Context $Context
        if ($identitySummary) {
            Add-StageResult -Report $Report -Name 'release_identity' -Status 'pass' -ExitCode 0 -Summary $identitySummary -StageTimer $identityTimer
        }
    }
    catch {
        Add-StageResult -Report $Report -Name 'release_identity' -Status 'fail' -ExitCode 1 -Summary @{ error = $_.Exception.Message } -StageTimer $identityTimer
        return
    }

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
