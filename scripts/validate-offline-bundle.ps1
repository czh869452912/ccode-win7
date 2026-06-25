[CmdletBinding()]
param(
    [string]$ArtifactName = 'embedagent-win7-x64',
    [string]$BundleRoot = "",
    [string]$ZipPath = "",
    [string]$SourcesRoot = "",
    [string]$JsonOutputPath = "",
    [string]$RuntimeContractPath = "",
    [switch]$RequireComplete,
    [switch]$SkipDynamicChecks
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

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
        $actualHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
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
        [object]$Contract
    )

    foreach ($tool in @($Contract.required_tools)) {
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
        [object]$Contract
    )

    foreach ($tool in @($Contract.required_tools)) {
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
        [object]$Contract
    )

    $cppGate = Get-ReleaseGateById -Contract $Contract -Id 'cpp_smoke_workspace'
    if ($null -eq $cppGate) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'release_gate.cpp_smoke_workspace.contract' -Message 'Runtime contract does not declare cpp_smoke_workspace release gate.'
    }
    else {
        Test-StaticPath -Results $Results -Path (Join-Path $BundleRoot ([string]$cppGate.script).Replace('/', '\')) -Code 'release_gate.cpp_smoke_workspace.script' -Message 'C/C++ smoke validation script present.' -TreatAsCompleteGate $true
        Test-StaticPath -Results $Results -Path (Join-Path $BundleRoot ([string]$cppGate.workspace).Replace('/', '\')) -Code 'release_gate.cpp_smoke_workspace.workspace' -Message 'C/C++ smoke workspace present.' -TreatAsCompleteGate $true
        Test-StaticPath -Results $Results -Path (Join-Path $BundleRoot ([string]$cppGate.launcher).Replace('/', '\')) -Code 'release_gate.cpp_smoke_workspace.launcher' -Message 'C/C++ smoke launcher present.' -TreatAsCompleteGate $true
    }

    $guiGate = Get-ReleaseGateById -Contract $Contract -Id 'gui_headless_smoke'
    if ($null -eq $guiGate) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'release_gate.gui_headless_smoke.contract' -Message 'Runtime contract does not declare gui_headless_smoke release gate.'
    }
    else {
        Test-StaticPath -Results $Results -Path (Join-Path $BundleRoot ([string]$guiGate.script).Replace('/', '\')) -Code 'release_gate.gui_headless_smoke.script' -Message 'GUI smoke validation script present.' -TreatAsCompleteGate $true
        Test-StaticPath -Results $Results -Path (Join-Path $BundleRoot ([string]$guiGate.launcher).Replace('/', '\')) -Code 'release_gate.gui_headless_smoke.launcher' -Message 'GUI smoke launcher present.' -TreatAsCompleteGate $true
    }

    $win7Gate = Get-ReleaseGateById -Contract $Contract -Id 'win7_windowed_gui_smoke'
    if ($null -eq $win7Gate) {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $Results -Level $level -Code 'release_gate.win7_windowed_gui_smoke.contract' -Message 'Runtime contract does not declare win7_windowed_gui_smoke release gate.'
    }
    else {
        $expectedMajor = [int]$win7Gate.webview2_fixed_runtime_major
        if ($expectedMajor -eq 109) {
            Add-Result -Results $Results -Level 'pass' -Code 'release_gate.win7_windowed_gui_smoke.webview2_major' -Message 'Win7 GUI release gate expects WebView2 Fixed Version major 109.'
        }
        else {
            Add-Result -Results $Results -Level 'fail' -Code 'release_gate.win7_windowed_gui_smoke.webview2_major' -Message ('Win7 GUI release gate must expect WebView2 major 109, got {0}.' -f $expectedMajor)
        }
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

Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent') -Code 'bundle.app' -Message 'Application directory present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'config\config.json') -Code 'bundle.config' -Message 'Default config template present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'config\config.json.template') -Code 'bundle.config_template' -Message 'Config template present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'config\permission-rules.json') -Code 'bundle.permissions' -Message 'Default permission rules template present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $manifestPath -Code 'bundle.manifest' -Message 'bundle-manifest.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $checksumsPath -Code 'bundle.checksums' -Message 'checksums.txt present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'embedagent.cmd') -Code 'bundle.launcher.cli' -Message 'CLI launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'embedagent-tui.cmd') -Code 'bundle.launcher.tui' -Message 'TUI launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'embedagent-gui.cmd') -Code 'bundle.launcher.gui' -Message 'GUI launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'EmbedAgent.exe') -Code 'bundle.launcher.gui_exe_user' -Message 'Native GUI user launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'embedagent-gui.exe') -Code 'bundle.launcher.gui_exe_cli' -Message 'Native GUI CLI launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'validate-gui-smoke.cmd') -Code 'bundle.launcher.gui_smoke' -Message 'GUI smoke launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'validate-cpp-smoke.cmd') -Code 'bundle.launcher.cpp_smoke' -Message 'C/C++ smoke launcher present.' -TreatAsCompleteGate $true
Validate-LauncherContract -Results $results -Path (Join-Path $BundleRoot 'embedagent.cmd') -Code 'bundle.launcher.cli_contract' -RequiredMarkers @(
    'EMBEDAGENT_BUNDLE_ROOT',
    '%BUNDLE_ROOT%bin\git\bin',
    '%BUNDLE_ROOT%bin\llvm\libexec'
) -LauncherName 'CLI'
Validate-LauncherContract -Results $results -Path (Join-Path $BundleRoot 'embedagent-gui.cmd') -Code 'bundle.launcher.gui_contract' -RequiredMarkers @(
    'EMBEDAGENT_BUNDLE_ROOT',
    '%BUNDLE_ROOT%bin\git\bin',
    '%BUNDLE_ROOT%bin\llvm\libexec'
) -LauncherName 'GUI'
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'docs\intranet-deployment.md') -Code 'bundle.docs.intranet' -Message 'Intranet deployment guide present.' -TreatAsCompleteGate $false
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'docs\win7-gui-validation.md') -Code 'bundle.docs.win7_gui' -Message 'Win7 GUI validation guide present.' -TreatAsCompleteGate $false
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent\frontend\gui\static\index.html') -Code 'bundle.gui.index' -Message 'GUI index.html present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent\frontend\gui\static\assets') -Code 'bundle.gui.assets' -Message 'GUI built asset directory present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'app\embedagent\frontend\gui\static\assets\katex\katex.min.css') -Code 'bundle.gui.katex_css' -Message 'KaTeX CSS present (formula rendering, generated by npm run build).' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'runtime\webview2-fixed-runtime\msedgewebview2.exe') -Code 'bundle.gui.webview2_runtime' -Message 'Bundled Fixed Version WebView2 runtime present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'tools\validation\validate-gui-smoke.py') -Code 'bundle.gui.smoke_script' -Message 'GUI smoke validation script present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'tools\validation\validate-cpp-smoke.py') -Code 'bundle.cpp.smoke_script' -Message 'C/C++ smoke validation script present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $SourcesRoot -Code 'sources.root' -Message 'Sources seed directory present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $sourcesManifestPath -Code 'sources.manifest' -Message 'assets-manifest.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $sourcesChecksumsPath -Code 'sources.checksums' -Message 'sources checksums.txt present.' -TreatAsCompleteGate $true
Test-RuntimeContract -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract
Test-ReleaseGateAssets -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract

if (Test-Path -LiteralPath $ZipPath) {
    Add-Result -Results $results -Level 'pass' -Code 'bundle.zip' -Message ('Zip artifact present: {0}' -f $ZipPath)
}
else {
    $level = if ($RequireComplete) { 'fail' } else { 'warn' }
    Add-Result -Results $results -Level $level -Code 'bundle.zip' -Message ('Zip artifact missing: {0}' -f $ZipPath)
}

$manifest = $null
if (Test-Path -LiteralPath $manifestPath) {
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        Add-Result -Results $results -Level 'pass' -Code 'manifest.parse' -Message 'bundle-manifest.json parsed successfully.'
    }
    catch {
        Add-Result -Results $results -Level 'fail' -Code 'manifest.parse' -Message ('Failed to parse bundle-manifest.json: {0}' -f $_.Exception.Message)
    }
}

if ($manifest -ne $null) {
    $completeGateComponents = @('python_runtime', 'python_packages', 'mingit_portable', 'ripgrep', 'universal_ctags', 'llvm_clang_bundle', 'webview2_fixed_runtime', 'gui_launcher_exe')
    foreach ($component in @($manifest.components)) {
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
Test-StaticPath -Results $results -Path $pythonExe -Code 'python.exe' -Message 'Bundled python.exe present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\python-3.8.10.txt') -Code 'python.license' -Message 'Python license notice present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\mingit-2.46.2.windows.1.txt') -Code 'mingit.license' -Message 'MinGit license notice present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $ripgrepExe -Code 'ripgrep.exe' -Message 'Bundled rg.exe present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $ctagsExe -Code 'ctags.exe' -Message 'Bundled ctags.exe present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\ripgrep-14.1.1.txt') -Code 'ripgrep.license' -Message 'ripgrep license notice present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'manifests\licenses\ctags-p6.2.20251116.0.txt') -Code 'ctags.license' -Message 'ctags license notice present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\python-3.8.10-embed-amd64.zip') -Code 'sources.python_archive' -Message 'Python source archive present in sources seed.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\MinGit-2.46.2-64-bit.zip') -Code 'sources.mingit_archive' -Message 'MinGit source archive present in sources seed.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\ripgrep-14.1.1-x86_64-pc-windows-msvc.zip') -Code 'sources.ripgrep_archive' -Message 'ripgrep source archive present in sources seed.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $SourcesRoot 'archives\ctags-p6.2.20251116.0-x64.zip') -Code 'sources.ctags_archive' -Message 'ctags source archive present in sources seed.' -TreatAsCompleteGate $true

if ($gitExe) {
    Add-Result -Results $results -Level 'pass' -Code 'git.exe' -Message ('Bundled git.exe present: {0}' -f $gitExe)
}
else {
    $level = if ($RequireComplete) { 'fail' } else { 'warn' }
    Add-Result -Results $results -Level $level -Code 'git.exe' -Message 'Bundled git.exe not found in expected locations.'
}

if (Test-Path -LiteralPath (Join-Path $BundleRoot 'runtime\python')) {
    Validate-PthFile -Results $results -PythonRoot (Join-Path $BundleRoot 'runtime\python')
}
Test-NoEditableBundleLinks -Results $results -SitePackagesRoot (Join-Path $BundleRoot 'runtime\site-packages')

if (-not $SkipDynamicChecks) {
    Invoke-RuntimeContractDynamicChecks -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract
    Invoke-CppSmokeGate -Results $results -BundleRoot $BundleRoot -Contract $runtimeContract
    Invoke-CommandCheck -Results $results -FilePath $pythonExe -Arguments @('--version') -Code 'dynamic.python' -TreatAsCompleteGate $true
    if ($gitExe) {
        Invoke-CommandCheck -Results $results -FilePath $gitExe -Arguments @('--version') -Code 'dynamic.git' -TreatAsCompleteGate $true
    }
    else {
        $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        Add-Result -Results $results -Level $level -Code 'dynamic.git' -Message 'Skipped git version check because git.exe was not found in the bundle.'
    }
    Invoke-CommandCheck -Results $results -FilePath $ripgrepExe -Arguments @('--version') -Code 'dynamic.ripgrep' -TreatAsCompleteGate $true
    Invoke-CommandCheck -Results $results -FilePath $ctagsExe -Arguments @('--version') -Code 'dynamic.ctags' -TreatAsCompleteGate $true

    # Dynamic checks: EmbedAgent.exe --help and embedagent-gui.exe --help.
    Invoke-GuiHelpCheck -Results $results -BundleRoot $BundleRoot -LauncherFile 'EmbedAgent.exe' -Code 'dynamic.gui_launcher_exe_user'
    Invoke-GuiHelpCheck -Results $results -BundleRoot $BundleRoot -LauncherFile 'embedagent-gui.exe' -Code 'dynamic.gui_launcher_exe_cli'

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
    pass_count = $passCount
    warn_count = $warnCount
    fail_count = $failCount
    results = $results
}
Write-JsonReport -Path $JsonOutputPath -Payload $summaryPayload

if ($failCount -gt 0) {
    exit 1
}
