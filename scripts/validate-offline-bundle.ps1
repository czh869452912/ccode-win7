[CmdletBinding()]
param(
    [string]$ArtifactName = 'embedagent-win7-x64',
    [string]$BundleRoot = "",
    [string]$ZipPath = "",
    [string]$SourcesRoot = "",
    [string]$JsonOutputPath = "",
    [string]$RuntimeContractPath = "",
    [string]$BundlePlanPath = "",
    [string]$BundlePlanSha256 = "",
    [switch]$RequireComplete,
    [switch]$SkipDynamicChecks
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'package-lib.ps1')

function Add-Result {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$Level,
        [string]$Code,
        [string]$Message
    )

    [void]$Results.Add([ordered]@{
        level = $Level
        code = $Code
        message = $Message
    })
}

function Write-JsonReport {
    param(
        [string]$Path,
        [hashtable]$Payload
    )

    if (-not $Path) {
        return
    }
    $parent = Split-Path -Parent $Path
    if ($parent -and (-not (Test-Path -LiteralPath $parent))) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $jsonText = $Payload | ConvertTo-Json -Depth 8
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $jsonText, $utf8NoBom)
}

function Invoke-ComponentResult {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$Name,
        [string]$Status,
        [string]$Message,
        [bool]$TreatAsCompleteGate
    )

    $level = 'pass'
    if ($Status -eq 'missing' -or $Status -eq 'skipped' -or $Status -eq 'cached') {
        if ($TreatAsCompleteGate -and $RequireComplete) {
            $level = 'fail'
        }
        else {
            $level = 'warn'
        }
    }
    Add-Result -Results $Results -Level $level -Code ('component.' + $Name) -Message ('{0}: {1}' -f $Status, $Message)
}

function Invoke-CommandCheck {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Code,
        [bool]$TreatAsCompleteGate
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        $level = if ($TreatAsCompleteGate -and $RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code $Code -Message ('Skipped command check because file is missing: {0}' -f $FilePath)
        return
    }

    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Add-Result -Results $Results -Level 'pass' -Code $Code -Message ('Command check passed: {0} {1}' -f $FilePath, ($Arguments -join ' '))
        }
        else {
            Add-Result -Results $Results -Level 'fail' -Code $Code -Message ('Command check failed ({0}): {1}' -f $exitCode, ($output | Out-String).Trim())
        }
    }
    catch {
        Add-Result -Results $Results -Level 'fail' -Code $Code -Message ('Command check threw: {0}' -f $_.Exception.Message)
    }
}

function Get-GitExecutablePath {
    param(
        [string]$BundleRoot
    )

    $candidates = @(
        (Join-Path $BundleRoot 'bin\git\cmd\git.exe'),
        (Join-Path $BundleRoot 'bin\git\bin\git.exe'),
        (Join-Path $BundleRoot 'bin\git\git.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return ''
}

function Get-ChecksumLines {
    param(
        [string]$ChecksumPath
    )

    if (-not (Test-Path -LiteralPath $ChecksumPath)) {
        return @()
    }
    return @(Get-Content -LiteralPath $ChecksumPath | Where-Object { $_.Trim() })
}

function Get-Sha256Hash {
    param(
        [string]$Path
    )

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $hashBytes = $sha256.ComputeHash($stream)
        }
        finally {
            $sha256.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }

    return ([System.BitConverter]::ToString($hashBytes)).Replace('-', '').ToLowerInvariant()
}

function Validate-Checksums {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$Root,
        [string]$ChecksumPath,
        [string]$CodePrefix
    )

    $lines = @(Get-ChecksumLines -ChecksumPath $ChecksumPath)
    if ($lines.Count -eq 0) {
        Add-Result -Results $Results -Level 'fail' -Code ($CodePrefix + '.checksums.empty') -Message ('{0} checksums.txt is missing or empty.' -f $CodePrefix)
        return
    }

    foreach ($line in $lines) {
        $parts = @($line.Split('*', 2))
        if ($parts.Count -ne 2) {
            Add-Result -Results $Results -Level 'fail' -Code ($CodePrefix + '.checksums.format') -Message ('Invalid checksum line: {0}' -f $line)
            continue
        }
        $expectedHash = $parts[0].Trim().ToLowerInvariant()
        $relativePath = $parts[1].Trim().Replace('/', '\')
        $targetPath = Join-Path $Root $relativePath
        if (-not (Test-Path -LiteralPath $targetPath)) {
            Add-Result -Results $Results -Level 'fail' -Code ($CodePrefix + '.checksums.missing_file') -Message ('Missing file referenced by checksums.txt: {0}' -f $relativePath)
            continue
        }
        $actualHash = Get-Sha256Hash -Path $targetPath
        if ($actualHash -ne $expectedHash) {
            Add-Result -Results $Results -Level 'fail' -Code ($CodePrefix + '.checksums.mismatch') -Message ('Checksum mismatch: {0}' -f $relativePath)
        }
    }

    $checksumFailures = @($Results | Where-Object { $_.code -like ($CodePrefix + '.checksums.*') -and $_.level -eq 'fail' })
    if ($checksumFailures.Count -eq 0) {
        Add-Result -Results $Results -Level 'pass' -Code ($CodePrefix + '.checksums.ok') -Message ('{0} checksums.txt verified successfully.' -f $CodePrefix)
    }
}

function Test-StaticPath {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$Path,
        [string]$Code,
        [string]$Message,
        [bool]$TreatAsCompleteGate
    )

    if (Test-Path -LiteralPath $Path) {
        Add-Result -Results $Results -Level 'pass' -Code $Code -Message $Message
        return
    }

    $level = if ($TreatAsCompleteGate -and $RequireComplete) { 'fail' } else { 'warn' }
    Add-Result -Results $Results -Level $level -Code $Code -Message ('Missing path: {0}' -f $Path)
}

function Validate-LauncherContract {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$Path,
        [string]$Code,
        [string[]]$RequiredMarkers,
        [string]$LauncherName
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $content = Get-Content -LiteralPath $Path -Raw
    $missing = @()
    foreach ($marker in @($RequiredMarkers)) {
        if (-not $marker) {
            continue
        }
        if ($content.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
            $missing += $marker
        }
    }

    if ($missing.Count -eq 0) {
        Add-Result -Results $Results -Level 'pass' -Code $Code -Message ('{0} launcher contract verified.' -f $LauncherName)
        return
    }

    Add-Result -Results $Results -Level 'fail' -Code $Code -Message ('{0} launcher missing required markers: {1}' -f $LauncherName, ($missing -join ', '))
}

function Validate-PthFile {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$PythonRoot
    )

    $pthFile = Get-ChildItem -LiteralPath $PythonRoot -Filter 'python*._pth' -File | Select-Object -First 1
    if (-not $pthFile) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'python.pth' -Message 'python*._pth file not found.'
        return
    }

    $content = Get-Content -LiteralPath $pthFile.FullName
    $expected = @('..\..\app', '..\site-packages', 'import site')
    $missing = @()
    foreach ($line in $expected) {
        if (-not ($content -contains $line)) {
            $missing += $line
        }
    }
    if ($missing.Count -eq 0) {
        Add-Result -Results $Results -Level 'pass' -Code 'python.pth' -Message ('Embeddable ._pth patched correctly: {0}' -f $pthFile.Name)
    }
    else {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'python.pth' -Message ('Embeddable ._pth missing expected lines: {0}' -f ($missing -join ', '))
    }
}

function Read-RuntimeContract {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Runtime contract not found: $Path"
    }
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Test-JsonProperty {
    param(
        [object]$Object,
        [string]$Name
    )

    return ($null -ne $Object) -and ($Object.PSObject.Properties.Name -contains $Name)
}

function Get-JsonPropertyValue {
    param(
        [object]$Object,
        [string]$Name
    )

    if (Test-JsonProperty -Object $Object -Name $Name) {
        return $Object.PSObject.Properties[$Name].Value
    }
    return $null
}

function Get-RuntimeContractManagedTools {
    param(
        [object]$Contract,
        [object[]]$RuntimeComponentIds = @()
    )

    $tools = @()
    $selectAll = @($RuntimeComponentIds).Count -eq 0
    foreach ($component in @(Get-JsonPropertyValue -Object $Contract -Name 'runtime_components')) {
        if ($null -eq $component) {
            continue
        }
        if (-not $selectAll -and -not (@($RuntimeComponentIds) -contains [string]$component.id)) {
            continue
        }
        foreach ($tool in @(Get-JsonPropertyValue -Object $component -Name 'managed_tools')) {
            if ($null -ne $tool) {
                $tools += $tool
            }
        }
    }
    return $tools
}

function Test-ContractPathSet {
    param(
        [string]$BundleRoot,
        [object[]]$RelativePaths
    )

    foreach ($relative in @($RelativePaths)) {
        $normalized = ([string]$relative).Replace('/', '\')
        $candidate = Join-Path $BundleRoot $normalized
        if (-not (Test-Path -LiteralPath $candidate)) {
            return $false
        }
    }
    return $true
}

function Test-ContractAlternatives {
    param(
        [string]$BundleRoot,
        [object[]]$Alternatives
    )

    foreach ($alternative in @($Alternatives)) {
        if (Test-ContractPathSet -BundleRoot $BundleRoot -RelativePaths @(Get-JsonPropertyValue -Object $alternative -Name 'paths')) {
            return $true
        }
    }
    return $false
}

function Get-ContractPrimaryPath {
    param(
        [string]$BundleRoot,
        [object]$Tool
    )

    if (Test-JsonProperty -Object $Tool -Name 'alternatives') {
        foreach ($alternative in @(Get-JsonPropertyValue -Object $Tool -Name 'alternatives')) {
            $alternativePaths = @(Get-JsonPropertyValue -Object $alternative -Name 'paths')
            if (Test-ContractPathSet -BundleRoot $BundleRoot -RelativePaths $alternativePaths) {
                $firstPath = $alternativePaths | Select-Object -First 1
                return Join-Path $BundleRoot ([string]$firstPath).Replace('/', '\')
            }
        }
        return ''
    }
    $paths = @(Get-JsonPropertyValue -Object $Tool -Name 'paths')
    if ($paths.Count -eq 0) {
        return ''
    }
    return Join-Path $BundleRoot ([string]$paths[0]).Replace('/', '\')
}

function Test-RuntimeContract {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [object]$Contract,
        [object[]]$RuntimeComponentIds = @()
    )

    foreach ($tool in @(Get-RuntimeContractManagedTools -Contract $Contract -RuntimeComponentIds $RuntimeComponentIds)) {
        $toolId = [string]$tool.id
        $present = $false
        if (Test-JsonProperty -Object $tool -Name 'alternatives') {
            $present = Test-ContractAlternatives -BundleRoot $BundleRoot -Alternatives @(Get-JsonPropertyValue -Object $tool -Name 'alternatives')
        }
        else {
            $present = Test-ContractPathSet -BundleRoot $BundleRoot -RelativePaths @(Get-JsonPropertyValue -Object $tool -Name 'paths')
        }

        $level = if ($present) { 'pass' } elseif ($RequireComplete) { 'fail' } else { 'warn' }
        $message = if ($present) {
            "Runtime tool present: $toolId"
        }
        else {
            "Runtime tool missing: $toolId"
        }
        Add-Result -Results $Results -Level $level -Code ('runtime_tool.' + $toolId) -Message $message

        foreach ($child in @(Get-JsonPropertyValue -Object $tool -Name 'children')) {
            if ($null -eq $child) {
                continue
            }
            $childPath = Join-Path $BundleRoot ([string]$child.path).Replace('/', '\')
            $childPresent = Test-Path -LiteralPath $childPath
            $childLevel = if ($childPresent) { 'pass' } elseif ($RequireComplete) { 'fail' } else { 'warn' }
            $childMessage = if ($childPresent) {
                "Runtime tool child present: $toolId/$($child.id)"
            }
            else {
                "Runtime tool child missing: $toolId/$($child.id) at $($child.path)"
            }
            Add-Result -Results $Results -Level $childLevel -Code ('runtime_tool.' + $toolId + '.' + [string]$child.id) -Message $childMessage
        }
    }
}

function Invoke-RuntimeContractDynamicChecks {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [object]$Contract,
        [object[]]$RuntimeComponentIds = @()
    )

    foreach ($tool in @(Get-RuntimeContractManagedTools -Contract $Contract -RuntimeComponentIds $RuntimeComponentIds)) {
        $toolId = [string]$tool.id
        if (Test-JsonProperty -Object $tool -Name 'dynamic_check') {
            $toolPath = Get-ContractPrimaryPath -BundleRoot $BundleRoot -Tool $tool
            if ($toolPath) {
                Invoke-CommandCheck -Results $Results -FilePath $toolPath -Arguments @(Get-JsonPropertyValue -Object $tool -Name 'dynamic_check') -Code ('dynamic.runtime_tool.' + $toolId) -TreatAsCompleteGate $true
            }
        }
        foreach ($child in @(Get-JsonPropertyValue -Object $tool -Name 'children')) {
            if ($null -eq $child) {
                continue
            }
            if (-not (Test-JsonProperty -Object $child -Name 'dynamic_check')) {
                continue
            }
            $childPath = Join-Path $BundleRoot ([string]$child.path).Replace('/', '\')
            Invoke-CommandCheck -Results $Results -FilePath $childPath -Arguments @(Get-JsonPropertyValue -Object $child -Name 'dynamic_check') -Code ('dynamic.runtime_tool.' + $toolId + '.' + [string]$child.id) -TreatAsCompleteGate $true
        }
    }
}

function Get-ReleaseGateById {
    param(
        [object]$Contract,
        [string]$Id
    )

    foreach ($gate in @(Get-JsonPropertyValue -Object $Contract -Name 'release_gates')) {
        if ($null -eq $gate) {
            continue
        }
        if ([string]$gate.id -eq $Id) {
            return $gate
        }
    }
    return $null
}

function Test-ReleaseGateAssets {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [object]$Contract,
        [object[]]$GateIds
    )

    foreach ($gateId in @($GateIds)) {
        $gate = Get-ReleaseGateById -Contract $Contract -Id ([string]$gateId)
        if ($null -eq $gate) {
            $level = if ($RequireComplete) { 'fail' } else { 'warn' }
            Add-Result -Results $Results -Level $level -Code ('release_gate.' + [string]$gateId + '.contract') -Message ('Runtime contract does not declare selected release gate: {0}' -f $gateId)
            continue
        }
        foreach ($field in @('script', 'workspace', 'launcher')) {
            if (-not (Test-JsonProperty -Object $gate -Name $field)) {
                continue
            }
            $relativePath = [string](Get-JsonPropertyValue -Object $gate -Name $field)
            if (-not $relativePath) {
                continue
            }
            Test-StaticPath `
                -Results $Results `
                -Path (Join-Path $BundleRoot $relativePath.Replace('/', '\')) `
                -Code ('release_gate.' + [string]$gateId + '.' + $field) `
                -Message ('Selected release gate path present: {0}' -f $relativePath) `
                -TreatAsCompleteGate $true
        }
        if (Test-JsonProperty -Object $gate -Name 'webview2_fixed_runtime_major') {
            $expectedMajor = [int](Get-JsonPropertyValue -Object $gate -Name 'webview2_fixed_runtime_major')
            $level = if ($expectedMajor -eq 109) { 'pass' } else { 'fail' }
            Add-Result -Results $Results -Level $level -Code ('release_gate.' + [string]$gateId + '.webview2_major') -Message ('Selected Win7 GUI gate expects WebView2 major {0}.' -f $expectedMajor)
        }
    }
}

function Get-ContractLauncherById {
    param(
        [object]$Contract,
        [string]$Id
    )

    foreach ($launcher in @(Get-JsonPropertyValue -Object $Contract -Name 'launchers')) {
        if ($null -ne $launcher -and [string]$launcher.id -eq $Id) {
            return $launcher
        }
    }
    return $null
}

function Get-RuntimeComponentKnownPaths {
    param([object]$Component)

    $paths = @((Get-JsonPropertyValue -Object $Component -Name 'paths'))
    foreach ($tool in @(Get-JsonPropertyValue -Object $Component -Name 'managed_tools')) {
        if ($null -eq $tool) { continue }
        $paths += @((Get-JsonPropertyValue -Object $tool -Name 'paths'))
        foreach ($alternative in @(Get-JsonPropertyValue -Object $tool -Name 'alternatives')) {
            if ($null -ne $alternative) {
                $paths += @((Get-JsonPropertyValue -Object $alternative -Name 'paths'))
            }
        }
        foreach ($child in @(Get-JsonPropertyValue -Object $tool -Name 'children')) {
            if ($null -ne $child -and (Test-JsonProperty -Object $child -Name 'path')) {
                $paths += [string]$child.path
            }
        }
    }
    return @($paths | Where-Object { [string]$_ } | Select-Object -Unique)
}

function Test-UnplannedRuntimeContent {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [object]$Contract,
        [object]$Plan
    )

    $knownPaths = @{}
    $plannedPaths = @{}
    $selectedComponents = @($Plan.runtime_component_ids)
    foreach ($component in @(Get-JsonPropertyValue -Object $Contract -Name 'runtime_components')) {
        if ($null -eq $component) { continue }
        foreach ($relativePath in @(Get-RuntimeComponentKnownPaths -Component $component)) {
            $knownPaths[[string]$relativePath] = $true
            if ($selectedComponents -contains [string]$component.id) {
                $plannedPaths[[string]$relativePath] = $true
            }
        }
    }
    $selectedLaunchers = @($Plan.launcher_ids)
    foreach ($launcher in @(Get-JsonPropertyValue -Object $Contract -Name 'launchers')) {
        if ($null -eq $launcher -or -not [string]$launcher.path) { continue }
        $relativePath = [string]$launcher.path
        $knownPaths[$relativePath] = $true
        if ($selectedLaunchers -contains [string]$launcher.id) {
            $plannedPaths[$relativePath] = $true
        }
    }
    $selectedGates = @($Plan.gate_ids)
    foreach ($gate in @(Get-JsonPropertyValue -Object $Contract -Name 'release_gates')) {
        if ($null -eq $gate) { continue }
        foreach ($field in @('script', 'workspace', 'launcher')) {
            $relativePath = [string](Get-JsonPropertyValue -Object $gate -Name $field)
            if (-not $relativePath) { continue }
            $knownPaths[$relativePath] = $true
            if ($selectedGates -contains [string]$gate.id) {
                $plannedPaths[$relativePath] = $true
            }
        }
    }
    foreach ($relativePath in @(
        'app/embedagent/frontend/gui',
        'runtime/webview2-fixed-runtime'
    )) {
        $knownPaths[$relativePath] = $true
        if (@($Plan.shell_ids) -contains 'gui') {
            $plannedPaths[$relativePath] = $true
        }
    }
    foreach ($relativePath in @($knownPaths.Keys | Sort-Object)) {
        if ($plannedPaths.ContainsKey($relativePath)) { continue }
        $candidate = Join-Path $BundleRoot $relativePath.Replace('/', '\')
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'bundle.plan.unplanned' -Message ('Unplanned runtime content present: {0}' -f $relativePath)
    }
}

function Invoke-CppSmokeGate {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [object]$Contract
    )

    $cppGate = Get-ReleaseGateById -Contract $Contract -Id 'cpp_smoke_workspace'
    if ($null -eq $cppGate) {
        return
    }
    $pythonExe = Join-Path $BundleRoot 'runtime\python\python.exe'
    $scriptPath = Join-Path $BundleRoot ([string]$cppGate.script).Replace('/', '\')
    $workspacePath = Join-Path $BundleRoot ([string]$cppGate.workspace).Replace('/', '\')
    if (-not (Test-Path -LiteralPath $pythonExe) -or -not (Test-Path -LiteralPath $scriptPath) -or -not (Test-Path -LiteralPath $workspacePath)) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'dynamic.release_gate.cpp_smoke_workspace' -Message 'Skipped C/C++ smoke gate because python, script, or workspace is missing.'
        return
    }
    $reportPath = Join-Path $BundleRoot 'manifests\cpp-smoke-report.json'
    Push-Location $BundleRoot
    try {
        $output = & $pythonExe $scriptPath --bundle-root $BundleRoot --workspace $workspacePath --json-report $reportPath 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Add-Result -Results $Results -Level 'pass' -Code 'dynamic.release_gate.cpp_smoke_workspace' -Message ('C/C++ smoke gate passed. Report: {0}' -f $reportPath)
        }
        else {
            Add-Result -Results $Results -Level 'fail' -Code 'dynamic.release_gate.cpp_smoke_workspace' -Message ('C/C++ smoke gate failed ({0}): {1}' -f $exitCode, ($output | Out-String).Trim())
        }
    }
    catch {
        Add-Result -Results $Results -Level 'fail' -Code 'dynamic.release_gate.cpp_smoke_workspace' -Message ('C/C++ smoke gate threw: {0}' -f $_.Exception.Message)
    }
    finally {
        Pop-Location
    }
}

function Invoke-CliSmokeGate {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [object]$Contract,
        [object]$Plan
    )

    $cliGate = Get-ReleaseGateById -Contract $Contract -Id 'win7_cli_smoke'
    if ($null -eq $cliGate) {
        return
    }
    $pythonExe = Join-Path $BundleRoot 'runtime\python\python.exe'
    $scriptPath = Join-Path $BundleRoot ([string]$cliGate.script).Replace('/', '\')
    if (-not (Test-Path -LiteralPath $pythonExe) -or -not (Test-Path -LiteralPath $scriptPath)) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'dynamic.release_gate.win7_cli_smoke' -Message 'Skipped CLI smoke gate because bundled python or the smoke script is missing.'
        return
    }
    $reportPath = Join-Path $BundleRoot 'manifests\cli-smoke-report.json'
    Push-Location $BundleRoot
    try {
        $null = & $pythonExe $scriptPath --bundle-root $BundleRoot --json-report $reportPath 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0 -or -not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
            Add-Result -Results $Results -Level 'fail' -Code 'dynamic.release_gate.win7_cli_smoke' -Message ('CLI smoke gate failed with exit code {0}.' -f $exitCode)
            return
        }
        $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
        $requiredScenarios = @($cliGate.scenario_ids)
        $valid = [bool]$report.ok
        $valid = $valid -and ([int]$report.schema_version -eq [int]$cliGate.report_schema_version)
        $valid = $valid -and ([string]$report.runtime_source -eq [string]$cliGate.expected_runtime_source)
        $valid = $valid -and ([string]$report.flavor_id -eq [string]$Plan.flavor_id)
        $valid = $valid -and (@($Plan.allowed_agent_application_ids) -contains [string]$report.agent_application_id)
        $valid = $valid -and ([string]$report.command_launcher -eq [string]$cliGate.command_launcher)
        $valid = $valid -and (
            [bool]$report.system_tool_fallback_allowed -eq [bool]$cliGate.allow_system_tool_fallback
        )
        foreach ($scenarioId in $requiredScenarios) {
            $valid = $valid -and [bool](
                Get-JsonPropertyValue -Object $report.scenarios -Name ([string]$scenarioId)
            )
        }
        if ($valid) {
            Add-Result -Results $Results -Level 'pass' -Code 'dynamic.release_gate.win7_cli_smoke' -Message ('CLI smoke gate passed. Report: {0}' -f $reportPath)
        }
        else {
            Add-Result -Results $Results -Level 'fail' -Code 'dynamic.release_gate.win7_cli_smoke' -Message 'CLI smoke report does not satisfy the selected bundle plan and runtime contract.'
        }
    }
    catch {
        Add-Result -Results $Results -Level 'fail' -Code 'dynamic.release_gate.win7_cli_smoke' -Message ('CLI smoke gate could not validate its report: {0}' -f $_.Exception.GetType().Name)
    }
    finally {
        Pop-Location
    }
}

function Invoke-GuiHelpCheck {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$BundleRoot,
        [string]$LauncherFile,
        [string]$Code
    )

    $launcher = Join-Path $BundleRoot $LauncherFile
    if (-not (Test-Path -LiteralPath $launcher)) {
        return
    }
    Push-Location $BundleRoot
    try {
        $output = & $launcher --help 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Add-Result -Results $Results -Level 'pass' -Code $Code -Message ("{0} --help succeeded." -f $LauncherFile)
        }
        else {
            Add-Result -Results $Results -Level 'fail' -Code $Code -Message ("{0} --help failed ({1}): {2}" -f $LauncherFile, $exitCode, ($output | Out-String).Trim())
        }
    }
    catch {
        Add-Result -Results $Results -Level 'fail' -Code $Code -Message ("{0} --help threw: {1}" -f $LauncherFile, $_.Exception.Message)
    }
    finally {
        Pop-Location
    }
}

function Test-NoEditableBundleLinks {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$SitePackagesRoot
    )

    if (-not (Test-Path -LiteralPath $SitePackagesRoot)) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'python.editable_links' -Message 'site-packages directory not found for editable link scan.'
        return
    }

    $editableFiles = @(Get-ChildItem -LiteralPath $SitePackagesRoot -Filter '__editable__*.pth' -File -ErrorAction SilentlyContinue)
    if ($editableFiles.Count -gt 0) {
        $names = @($editableFiles | ForEach-Object { $_.Name }) -join ', '
        Add-Result -Results $Results -Level 'fail' -Code 'python.editable_links' -Message ('Bundle site-packages still contains editable path links: {0}' -f $names)
        return
    }
    Add-Result -Results $Results -Level 'pass' -Code 'python.editable_links' -Message 'Bundle site-packages contains no editable path links.'
}

function Get-TreeContentSha256 {
    param(
        [string]$Root,
        [string[]]$ExcludedRelativePaths = @()
    )

    $excluded = @($ExcludedRelativePaths | ForEach-Object { $_.Replace('/', '\') })
    $records = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $Root -Recurse -File | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($Root.Length).TrimStart('\')
        if ($excluded -contains $relative) {
            continue
        }
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $records += ($relative.Replace('\', '/') + ':' + $hash)
    }
    $payload = ($records -join "`n")
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        return ([System.BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
}

function Test-ReleaseArtifactContract {
    param(
        [System.Collections.ArrayList]$Results,
        [object]$Manifest,
        [string]$BundleRoot,
        [string]$SourcesRoot,
        [string]$ZipPath
    )

    $identityPath = Join-Path $BundleRoot 'manifests\release-identity.json'
    if (-not (Test-Path -LiteralPath $identityPath -PathType Leaf)) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'release.identity' -Message 'release-identity.json is missing from the bundle.'
        return
    }
    try {
        $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
        Add-Result -Results $Results -Level 'pass' -Code 'release.identity' -Message 'release-identity.json parsed successfully.'
    }
    catch {
        Add-Result -Results $Results -Level 'fail' -Code 'release.identity' -Message ('release-identity.json is invalid: {0}' -f $_.Exception.Message)
        return
    }

    $manifestSourceMode = ''
    if ($Manifest -and ($Manifest.PSObject.Properties.Name -contains 'source_mode')) {
        $manifestSourceMode = [string]$Manifest.source_mode
    }
    if ($manifestSourceMode -ne 'wheel-installed') {
        Add-Result -Results $Results -Level 'fail' -Code 'release.source_mode' -Message 'Bundle manifest must declare source_mode=wheel-installed.'
    }
    else {
        Add-Result -Results $Results -Level 'pass' -Code 'release.source_mode' -Message 'Bundle app was assembled from wheel-installed packages.'
    }

    $expectedDistributions = @()
    if ($Manifest -and ($Manifest.PSObject.Properties.Name -contains 'project_distributions')) {
        $expectedDistributions = @($Manifest.project_distributions)
    }
    $wheelNames = @()
    if ($Manifest -and ($Manifest.PSObject.Properties.Name -contains 'project_wheels')) {
        $wheelNames = @($Manifest.project_wheels)
    }
    $wheelHashes = $null
    if ($Manifest -and ($Manifest.PSObject.Properties.Name -contains 'wheel_hashes')) {
        $wheelHashes = $Manifest.wheel_hashes
    }
    $declaredDistributions = @()
    if ($Manifest -and ($Manifest.PSObject.Properties.Name -contains 'project_distributions')) {
        $declaredDistributions = @($Manifest.project_distributions)
    }
    if ($expectedDistributions.Count -eq 0 -or $wheelNames.Count -ne $expectedDistributions.Count -or $declaredDistributions.Count -ne $expectedDistributions.Count -or (($declaredDistributions -join '|') -ne ($expectedDistributions -join '|'))) {
        Add-Result -Results $Results -Level 'fail' -Code 'release.project_wheels' -Message 'Bundle manifest project distributions and wheels must match the selected bundle plan.'
    }
    else {
        Add-Result -Results $Results -Level 'pass' -Code 'release.project_wheels' -Message 'Bundle manifest declares the selected project wheels.'
    }
    if (-not $wheelHashes -or @($wheelHashes.PSObject.Properties).Count -ne $expectedDistributions.Count) {
        Add-Result -Results $Results -Level 'fail' -Code 'release.wheel_hashes' -Message 'Bundle manifest must declare SHA-256 for every selected project wheel.'
    }

    $sitePackages = Join-Path $BundleRoot 'runtime\site-packages'
    $duplicatePackage = Join-Path $sitePackages 'embedagent'
    $duplicateDistInfo = @(Get-ChildItem -LiteralPath $sitePackages -Directory -Filter 'embedagent-*.dist-info' -ErrorAction SilentlyContinue)
    if ((Test-Path -LiteralPath $duplicatePackage) -or $duplicateDistInfo.Count -gt 0) {
        Add-Result -Results $Results -Level 'fail' -Code 'release.duplicate_product' -Message 'runtime/site-packages contains a duplicate product package or dist-info.'
    }
    else {
        Add-Result -Results $Results -Level 'pass' -Code 'release.duplicate_product' -Message 'Product package exists only under app/embedagent.'
    }
    $packageRoots = @{
        'embedagent-core' = 'embedagent_core'
        'embedagent-protocol' = 'embedagent_protocol'
        'embedagent-host' = 'embedagent_host'
        'embedagent-composition' = 'embedagent_composition'
        'embedagent-workflow-cpp' = 'embedagent_workflow_cpp'
    }
    foreach ($lowerDistribution in $expectedDistributions) {
        if ($packageRoots.ContainsKey([string]$lowerDistribution) -and -not (Test-Path -LiteralPath (Join-Path $sitePackages $packageRoots[[string]$lowerDistribution]))) {
            Add-Result -Results $Results -Level 'fail' -Code 'release.lower_distribution' -Message ('Missing selected project distribution: {0}' -f $lowerDistribution)
        }
    }

    $wheelRoot = Join-Path $SourcesRoot 'python-wheels'
    foreach ($wheelName in $wheelNames) {
        $wheelPath = Join-Path $wheelRoot ([string]$wheelName)
        if (-not (Test-Path -LiteralPath $wheelPath -PathType Leaf)) {
            Add-Result -Results $Results -Level 'fail' -Code 'release.wheel_missing' -Message ('Missing archived project wheel: {0}' -f $wheelName)
            continue
        }
        $expectedHash = ''
        if ($wheelHashes -and ($wheelHashes.PSObject.Properties.Name -contains ([string]$wheelName))) {
            $expectedHash = [string]$wheelHashes.([string]$wheelName)
        }
        $actualHash = (Get-FileHash -LiteralPath $wheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($expectedHash -and $expectedHash.ToLowerInvariant() -eq $actualHash) {
            Add-Result -Results $Results -Level 'pass' -Code 'release.wheel_hash' -Message ('Wheel hash verified: {0}' -f $wheelName)
        }
        else {
            Add-Result -Results $Results -Level 'fail' -Code 'release.wheel_hash' -Message ('Wheel hash mismatch: {0}' -f $wheelName)
        }
    }

    $expectedHashesPath = Join-Path $BundleRoot 'manifests\evidence\expected-bundle-hashes.json'
    if (Test-Path -LiteralPath $expectedHashesPath -PathType Leaf) {
        try {
            $expectedHashes = Get-Content -LiteralPath $expectedHashesPath -Raw | ConvertFrom-Json
            $expectedBundleHash = [string]$expectedHashes.bundle_sha256
            $actualExpectedBundleHash = Get-TreeContentSha256 -Root $BundleRoot -ExcludedRelativePaths @('manifests/checksums.txt', 'manifests/evidence/expected-bundle-hashes.json', 'manifests/cli-smoke-report.json', 'manifests/cpp-smoke-report.json', 'manifests/evidence/win7-evidence.json', 'manifests/evidence/acceptance-report.json')
            if (-not $expectedBundleHash -or $expectedBundleHash.ToLowerInvariant() -ne $actualExpectedBundleHash) {
                Add-Result -Results $Results -Level 'fail' -Code 'release.bundle_sha256' -Message 'expected-bundle-hashes.json bundle_sha256 mismatch.'
            }
            else {
                Add-Result -Results $Results -Level 'pass' -Code 'release.bundle_sha256' -Message 'Bundle tree matches expected-bundle-hashes.json.'
            }
            if ($expectedHashes.release_identity_sha256) {
                $actualIdentityHash = (Get-FileHash -LiteralPath $identityPath -Algorithm SHA256).Hash.ToLowerInvariant()
                if (([string]$expectedHashes.release_identity_sha256).ToLowerInvariant() -ne $actualIdentityHash) {
                    Add-Result -Results $Results -Level 'fail' -Code 'release.identity_sha256' -Message 'Expected identity hash does not match release-identity.json.'
                }
            }
        }
        catch {
            Add-Result -Results $Results -Level 'fail' -Code 'release.expected_hashes' -Message ('expected-bundle-hashes.json is invalid: {0}' -f $_.Exception.Message)
        }
    }
    elseif ($RequireComplete) {
        Add-Result -Results $Results -Level 'fail' -Code 'release.expected_hashes' -Message 'expected-bundle-hashes.json is missing.'
    }
    $declaredBundleHash = ''
    if ($Manifest -and ($Manifest.PSObject.Properties.Name -contains 'bundle_sha256')) {
        $declaredBundleHash = [string]$Manifest.bundle_sha256
    }
    if ($declaredBundleHash) {
        $actualBundleHash = Get-TreeContentSha256 -Root $BundleRoot -ExcludedRelativePaths @('manifests/checksums.txt')
        if ($declaredBundleHash -ne $actualBundleHash) {
            Add-Result -Results $Results -Level 'fail' -Code 'release.bundle_sha256' -Message 'Declared bundle_sha256 does not match the bundle tree.'
        }
    }
    $declaredZipHash = ''
    if ($Manifest -and ($Manifest.PSObject.Properties.Name -contains 'zip_sha256')) {
        $declaredZipHash = [string]$Manifest.zip_sha256
    }
    if ($declaredZipHash) {
        if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
            Add-Result -Results $Results -Level 'fail' -Code 'release.zip_sha256' -Message 'Declared zip_sha256 has no zip artifact.'
        }
        elseif ((Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $declaredZipHash.ToLowerInvariant()) {
            Add-Result -Results $Results -Level 'fail' -Code 'release.zip_sha256' -Message 'Declared zip_sha256 does not match the zip artifact.'
        }
    }
    $artifactHashesPath = Join-Path $SourcesRoot 'artifact-hashes.json'
    if (Test-Path -LiteralPath $artifactHashesPath -PathType Leaf) {
        try {
            $artifactHashes = Get-Content -LiteralPath $artifactHashesPath -Raw | ConvertFrom-Json
            $artifactZipHash = ''
            if ($artifactHashes.PSObject.Properties.Name -contains 'zip_sha256') {
                $artifactZipHash = [string]$artifactHashes.zip_sha256
            }
            if ($artifactZipHash -and -not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
                Add-Result -Results $Results -Level 'fail' -Code 'release.zip_sha256' -Message 'artifact-hashes.json declares a zip hash but the zip is missing.'
            }
            elseif ($artifactZipHash -and (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $artifactZipHash.ToLowerInvariant()) {
                Add-Result -Results $Results -Level 'fail' -Code 'release.zip_sha256' -Message 'artifact-hashes.json zip_sha256 mismatch.'
            }
            else {
                Add-Result -Results $Results -Level 'pass' -Code 'release.zip_sha256' -Message 'Zip artifact hash matches artifact-hashes.json.'
            }
        }
        catch {
            Add-Result -Results $Results -Level 'fail' -Code 'release.artifact_hashes' -Message ('artifact-hashes.json is invalid: {0}' -f $_.Exception.Message)
        }
    }
}
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$defaultBundleRoot = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName)
$defaultZipPath = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName + '.zip')
$defaultSourcesRoot = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName + '-sources')

if (-not $RuntimeContractPath) {
    $RuntimeContractPath = Join-Path $projectRoot 'scripts\offline-runtime-contract.json'
}

if (-not $BundleRoot) {
    $BundleRoot = $defaultBundleRoot
}
if (-not $ZipPath) {
    $ZipPath = $defaultZipPath
}
if (-not $SourcesRoot) {
    $SourcesRoot = $defaultSourcesRoot
}

$results = New-Object System.Collections.ArrayList
$runtimeContract = Read-RuntimeContract -Path $RuntimeContractPath

if (-not (Test-Path -LiteralPath $BundleRoot)) {
    Add-Result -Results $results -Level 'fail' -Code 'bundle.root' -Message ('Bundle root not found: {0}' -f $BundleRoot)
}
else {
    Add-Result -Results $results -Level 'pass' -Code 'bundle.root' -Message ('Bundle root found: {0}' -f $BundleRoot)
}

$manifestPath = Join-Path $BundleRoot 'manifests\bundle-manifest.json'
$checksumsPath = Join-Path $BundleRoot 'manifests\checksums.txt'
$sourcesManifestPath = Join-Path $SourcesRoot 'assets-manifest.json'
$sourcesChecksumsPath = Join-Path $SourcesRoot 'checksums.txt'
$manifest = $null
$bundlePlan = $null
$bundlePlanHash = ''
$embeddedPlanPath = Join-Path $BundleRoot 'manifests\bundle-plan.json'
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        Add-Result -Results $results -Level 'pass' -Code 'manifest.parse' -Message 'bundle-manifest.json parsed successfully.'
        $manifestPlanHash = [string](Get-JsonPropertyValue -Object $manifest -Name 'bundle_plan_sha256')
        $expectedPlanHash = if ($BundlePlanSha256) { $BundlePlanSha256 } else { $manifestPlanHash }
        $embeddedPlanState = Read-VerifiedBundlePlan `
            -ProjectRoot $projectRoot `
            -BundlePlanPath $embeddedPlanPath `
            -BundlePlanSha256 $expectedPlanHash `
            -RuntimeContractPath $RuntimeContractPath
        if ($BundlePlanPath) {
            $sourcePlanState = Read-VerifiedBundlePlan `
                -ProjectRoot $projectRoot `
                -BundlePlanPath $BundlePlanPath `
                -BundlePlanSha256 $BundlePlanSha256 `
                -RuntimeContractPath $RuntimeContractPath
            if ([string]$sourcePlanState.plan_sha256 -ne [string]$embeddedPlanState.plan_sha256) {
                throw 'Embedded bundle plan does not match the supplied source plan.'
            }
        }
        Assert-BundleManifestPlanBinding -Manifest $manifest -PlanState $embeddedPlanState -BundleRoot $BundleRoot
        $bundlePlan = $embeddedPlanState.plan
        $bundlePlanHash = [string]$embeddedPlanState.plan_sha256
        Add-Result -Results $results -Level 'pass' -Code 'bundle.plan.binding' -Message 'Bundle plan, Agent lock, and bundle manifest are hash-bound.'
    }
    catch {
        Add-Result -Results $results -Level 'fail' -Code 'bundle.plan.binding' -Message ('Bundle plan validation failed: {0}' -f $_.Exception.Message)
    }
}

Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent') -Code 'bundle.app' -Message 'Application directory present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'config\config.json') -Code 'bundle.config' -Message 'Default config template present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'config\config.json.template') -Code 'bundle.config_template' -Message 'Config template present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'config\permission-rules.json') -Code 'bundle.permissions' -Message 'Default permission rules template present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $manifestPath -Code 'bundle.manifest' -Message 'bundle-manifest.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $checksumsPath -Code 'bundle.checksums' -Message 'checksums.txt present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $embeddedPlanPath -Code 'bundle.plan' -Message 'bundle-plan.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\agent.json') -Code 'bundle.agent' -Message 'agent.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\agent.lock.json') -Code 'bundle.agent_lock' -Message 'agent.lock.json present.' -TreatAsCompleteGate $true
if ($null -ne $bundlePlan) {
    foreach ($launcherId in @($bundlePlan.launcher_ids)) {
        $launcherRecord = Get-ContractLauncherById -Contract $runtimeContract -Id ([string]$launcherId)
        if ($null -eq $launcherRecord) {
            Add-Result -Results $results -Level 'fail' -Code ('bundle.launcher.' + [string]$launcherId) -Message ('Selected launcher is absent from the runtime contract: {0}' -f $launcherId)
            continue
        }
        Test-StaticPath `
            -Results $results `
            -Path (Join-Path $BundleRoot ([string]$launcherRecord.path).Replace('/', '\')) `
            -Code ('bundle.launcher.' + [string]$launcherId) `
            -Message ('Selected launcher present: {0}' -f $launcherRecord.path) `
            -TreatAsCompleteGate $true
    }
    $launcherMarkers = @('EMBEDAGENT_BUNDLE_ROOT')
    if (@($bundlePlan.runtime_component_ids) -contains 'mingit') { $launcherMarkers += '%BUNDLE_ROOT%bin\git\bin' }
    if (@($bundlePlan.runtime_component_ids) -contains 'llvm') { $launcherMarkers += '%BUNDLE_ROOT%bin\llvm\libexec' }
    Validate-LauncherContract -Results $results -Path (Join-Path $BundleRoot 'embedagent.cmd') -Code 'bundle.launcher.cli_contract' -RequiredMarkers $launcherMarkers -LauncherName 'CLI'
    if (@($bundlePlan.shell_ids) -contains 'gui') {
        Validate-LauncherContract -Results $results -Path (Join-Path $BundleRoot 'embedagent-gui.cmd') -Code 'bundle.launcher.gui_contract' -RequiredMarkers $launcherMarkers -LauncherName 'GUI'
    }
}
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'docs\intranet-deployment.md') -Code 'bundle.docs.intranet' -Message 'Intranet deployment guide present.' -TreatAsCompleteGate $false
if ($null -ne $bundlePlan -and @($bundlePlan.shell_ids) -contains 'gui') {
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'docs\win7-gui-validation.md') -Code 'bundle.docs.win7_gui' -Message 'Win7 GUI validation guide present.' -TreatAsCompleteGate $false
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent\frontend\gui\static\index.html') -Code 'bundle.gui.index' -Message 'GUI index.html present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent\frontend\gui\static\assets') -Code 'bundle.gui.assets' -Message 'GUI built asset directory present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent\frontend\gui\static\assets\katex\katex.min.css') -Code 'bundle.gui.katex_css' -Message 'KaTeX CSS present (formula rendering, generated by npm run build).' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'runtime\webview2-fixed-runtime\msedgewebview2.exe') -Code 'bundle.gui.webview2_runtime' -Message 'Bundled Fixed Version WebView2 runtime present.' -TreatAsCompleteGate $true
}
Test-StaticPath -Results $results -Path $SourcesRoot -Code 'sources.root' -Message 'Sources seed directory present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $sourcesManifestPath -Code 'sources.manifest' -Message 'assets-manifest.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $sourcesChecksumsPath -Code 'sources.checksums' -Message 'sources checksums.txt present.' -TreatAsCompleteGate $true
if ($null -ne $bundlePlan) {
    Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'bundle-plan.json') -Code 'sources.bundle_plan' -Message 'Sources bundle-plan.json present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'agent.json') -Code 'sources.agent' -Message 'Sources agent.json present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'agent.lock.json') -Code 'sources.agent_lock' -Message 'Sources agent.lock.json present.' -TreatAsCompleteGate $true
}
if ($null -ne $bundlePlan) {
    Test-RuntimeContract -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract -RuntimeComponentIds @($bundlePlan.runtime_component_ids)
    Test-ReleaseGateAssets -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract -GateIds @($bundlePlan.gate_ids)
    Test-UnplannedRuntimeContent -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract -Plan $bundlePlan
}

if (Test-Path -LiteralPath $ZipPath) {
    Add-Result -Results $results -Level 'pass' -Code 'bundle.zip' -Message ('Zip artifact present: {0}' -f $ZipPath)
}
else {
    $level = if ($RequireComplete) { 'fail' } else { 'warn' }
    Add-Result -Results $results -Level $level -Code 'bundle.zip' -Message ('Zip artifact missing: {0}' -f $ZipPath)
}

if ($manifest -ne $null) {
    $completeGateComponents = @('python_runtime', 'python_packages', 'mingit_portable', 'ripgrep', 'universal_ctags', 'llvm_clang_bundle', 'webview2_fixed_runtime', 'gui_launcher_exe')
    $manifestComponents = @()
    if ($manifest.PSObject.Properties.Name -contains 'components') {
        $manifestComponents = @($manifest.components)
    }
    foreach ($component in $manifestComponents) {
        if (-not $component.required) {
            continue
        }
        $treatAsGate = $completeGateComponents -contains $component.name
        Invoke-ComponentResult -Results $results -Name $component.name -Status $component.status -Message $component.notes -TreatAsCompleteGate $treatAsGate
    }
}

if (Test-Path -LiteralPath $checksumsPath) {
    Validate-Checksums -Results $results -Root $BundleRoot -ChecksumPath $checksumsPath -CodePrefix 'bundle'
}
if (Test-Path -LiteralPath $sourcesChecksumsPath) {
    Validate-Checksums -Results $results -Root $SourcesRoot -ChecksumPath $sourcesChecksumsPath -CodePrefix 'sources'
}

$pythonExe = Join-Path $BundleRoot 'runtime\python\python.exe'
$gitExe = Get-GitExecutablePath -BundleRoot $BundleRoot
$ripgrepExe = Join-Path $BundleRoot 'bin\rg\rg.exe'
$ctagsExe = Join-Path $BundleRoot 'bin\ctags\ctags.exe'
$selectedRuntimeComponentIds = if ($null -ne $bundlePlan) { @($bundlePlan.runtime_component_ids) } else { @() }
if ($selectedRuntimeComponentIds -contains 'python') {
    Test-StaticPath -Results $results -Path $pythonExe -Code 'python.exe' -Message 'Bundled python.exe present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\python-3.8.10.txt') -Code 'python.license' -Message 'Python license notice present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\python-3.8.10-embed-amd64.zip') -Code 'sources.python_archive' -Message 'Python source archive present in sources seed.' -TreatAsCompleteGate $true
}
if ($selectedRuntimeComponentIds -contains 'mingit') {
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\mingit-2.46.2.windows.1.txt') -Code 'mingit.license' -Message 'MinGit license notice present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\MinGit-2.46.2-64-bit.zip') -Code 'sources.mingit_archive' -Message 'MinGit source archive present in sources seed.' -TreatAsCompleteGate $true
    if ($gitExe) {
        Add-Result -Results $results -Level 'pass' -Code 'git.exe' -Message ('Bundled git.exe present: {0}' -f $gitExe)
    }
    else {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $results -Level $level -Code 'git.exe' -Message 'Bundled git.exe not found in expected locations.'
    }
}
if ($selectedRuntimeComponentIds -contains 'ripgrep') {
    Test-StaticPath -Results $results -Path $ripgrepExe -Code 'ripgrep.exe' -Message 'Bundled rg.exe present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\ripgrep-14.1.1.txt') -Code 'ripgrep.license' -Message 'ripgrep license notice present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\ripgrep-14.1.1-x86_64-pc-windows-msvc.zip') -Code 'sources.ripgrep_archive' -Message 'ripgrep source archive present in sources seed.' -TreatAsCompleteGate $true
}
if ($selectedRuntimeComponentIds -contains 'ctags') {
    Test-StaticPath -Results $results -Path $ctagsExe -Code 'ctags.exe' -Message 'Bundled ctags.exe present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\ctags-p6.2.20251116.0.txt') -Code 'ctags.license' -Message 'ctags license notice present.' -TreatAsCompleteGate $true
    Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\ctags-p6.2.20251116.0-x64.zip') -Code 'sources.ctags_archive' -Message 'ctags source archive present in sources seed.' -TreatAsCompleteGate $true
}

if ($selectedRuntimeComponentIds -contains 'python' -and (Test-Path -LiteralPath (Join-Path $BundleRoot 'runtime\python'))) {
    Validate-PthFile -Results $results -PythonRoot (Join-Path $BundleRoot 'runtime\python')
}
Test-NoEditableBundleLinks -Results $results -SitePackagesRoot (Join-Path $BundleRoot 'runtime\site-packages')
Test-ReleaseArtifactContract -Results $results -Manifest $manifest -BundleRoot $BundleRoot -SourcesRoot $SourcesRoot -ZipPath $ZipPath

if (-not $SkipDynamicChecks) {
    Invoke-RuntimeContractDynamicChecks -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract -RuntimeComponentIds $selectedRuntimeComponentIds
    if ($null -ne $bundlePlan -and @($bundlePlan.gate_ids) -contains 'win7_cli_smoke') {
        Invoke-CliSmokeGate -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract -Plan $bundlePlan
    }
    if ($null -ne $bundlePlan -and @($bundlePlan.gate_ids) -contains 'cpp_smoke_workspace') {
        Invoke-CppSmokeGate -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract
    }
    if ($selectedRuntimeComponentIds -contains 'python') {
        Invoke-CommandCheck -Results $results -FilePath $pythonExe -Arguments @('--version') -Code 'dynamic.python' -TreatAsCompleteGate $true
    }
    if ($selectedRuntimeComponentIds -contains 'mingit') {
        if ($gitExe) {
            Invoke-CommandCheck -Results $results -FilePath $gitExe -Arguments @('--version') -Code 'dynamic.git' -TreatAsCompleteGate $true
        }
        else {
            $level = if ($RequireComplete) { 'fail' } else { 'warn' }
            Add-Result -Results $results -Level $level -Code 'dynamic.git' -Message 'Skipped git version check because git.exe was not found in the bundle.'
        }
    }
    if ($selectedRuntimeComponentIds -contains 'ripgrep') {
        Invoke-CommandCheck -Results $results -FilePath $ripgrepExe -Arguments @('--version') -Code 'dynamic.ripgrep' -TreatAsCompleteGate $true
    }
    if ($selectedRuntimeComponentIds -contains 'ctags') {
        Invoke-CommandCheck -Results $results -FilePath $ctagsExe -Arguments @('--version') -Code 'dynamic.ctags' -TreatAsCompleteGate $true
    }

    if ($null -ne $bundlePlan -and @($bundlePlan.shell_ids) -contains 'gui') {
        Invoke-GuiHelpCheck -Results $results -BundleRoot $BundleRoot -LauncherFile 'EmbedAgent.exe' -Code 'dynamic.gui_launcher_exe_user'
        Invoke-GuiHelpCheck -Results $results -BundleRoot $BundleRoot -LauncherFile 'embedagent-gui.exe' -Code 'dynamic.gui_launcher_exe_cli'
    }

    $launcher = Join-Path $BundleRoot 'embedagent.cmd'
    if (Test-Path -LiteralPath $launcher) {
        Push-Location $BundleRoot
        try {
            $output = & cmd.exe /c '.\embedagent.cmd --help' 2>&1
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0) {
                Add-Result -Results $results -Level 'pass' -Code 'dynamic.launcher' -Message 'embedagent.cmd --help succeeded.'
            }
            else {
                Add-Result -Results $results -Level 'fail' -Code 'dynamic.launcher' -Message ('embedagent.cmd --help failed ({0}): {1}' -f $exitCode, ($output | Out-String).Trim())
            }
        }
        catch {
            Add-Result -Results $results -Level 'fail' -Code 'dynamic.launcher' -Message ('embedagent.cmd --help threw: {0}' -f $_.Exception.Message)
        }
        finally {
            Pop-Location
        }
    }

    $guiLauncher = Join-Path $BundleRoot 'embedagent-gui.cmd'
    if (Test-Path -LiteralPath $guiLauncher) {
        Push-Location $BundleRoot
        try {
            $output = & cmd.exe /c '.\embedagent-gui.cmd --help' 2>&1
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0) {
                Add-Result -Results $results -Level 'pass' -Code 'dynamic.gui_launcher' -Message 'embedagent-gui.cmd --help succeeded.'
            }
            else {
                Add-Result -Results $results -Level 'fail' -Code 'dynamic.gui_launcher' -Message ('embedagent-gui.cmd --help failed ({0}): {1}' -f $exitCode, ($output | Out-String).Trim())
            }
        }
        catch {
            Add-Result -Results $results -Level 'fail' -Code 'dynamic.gui_launcher' -Message ('embedagent-gui.cmd --help threw: {0}' -f $_.Exception.Message)
        }
        finally {
            Pop-Location
        }
    }
}

$failCount = @($results | Where-Object { $_.level -eq 'fail' }).Count
$warnCount = @($results | Where-Object { $_.level -eq 'warn' }).Count
$passCount = @($results | Where-Object { $_.level -eq 'pass' }).Count

foreach ($item in $results) {
    Write-Host ('[{0}] {1}: {2}' -f $item.level.ToUpperInvariant(), $item.code, $item.message)
}

Write-Host ('Summary: pass={0} warn={1} fail={2}' -f $passCount, $warnCount, $failCount)

$summaryPayload = [ordered]@{
    ok = ($failCount -eq 0)
    artifact_name = $ArtifactName
    bundle_root = $BundleRoot
    zip_path = $ZipPath
    sources_root = $SourcesRoot
    require_complete = [bool]$RequireComplete
    skip_dynamic_checks = [bool]$SkipDynamicChecks
    runtime_contract = [ordered]@{
        path = $RuntimeContractPath
        schema_version = $runtimeContract.schema_version
    }
    bundle_plan = [ordered]@{
        path = $embeddedPlanPath
        source_path = $BundlePlanPath
        sha256 = $bundlePlanHash
    }
    pass_count = $passCount
    warn_count = $warnCount
    fail_count = $failCount
    results = $results
}
Write-JsonReport -Path $JsonOutputPath -Payload $summaryPayload

if ($failCount -gt 0) {
    exit 1
}
