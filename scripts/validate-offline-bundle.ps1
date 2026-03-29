[CmdletBinding()]
param(
    [string]$ArtifactName = 'embedagent-win7-x64',
    [string]$BundleRoot = "",
    [string]$ZipPath = "",
    [string]$SourcesRoot = "",
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

    $lines = Get-ChecksumLines -ChecksumPath $ChecksumPath
    if ($lines.Count -eq 0) {
        Add-Result -Results $Results -Level 'fail' -Code ($CodePrefix + '.checksums.empty') -Message ('{0} checksums.txt is missing or empty.' -f $CodePrefix)
        return
    }

    foreach ($line in $lines) {
        $parts = $line.Split('*', 2)
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

    if (-not @($Results | Where-Object { $_.code -like ($CodePrefix + '.checksums.*') -and $_.level -eq 'fail' }).Count) {
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

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$defaultBundleRoot = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName)
$defaultZipPath = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName + '.zip')
$defaultSourcesRoot = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName + '-sources')

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
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'config\permission-rules.json') -Code 'bundle.permissions' -Message 'Default permission rules template present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $manifestPath -Code 'bundle.manifest' -Message 'bundle-manifest.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $checksumsPath -Code 'bundle.checksums' -Message 'checksums.txt present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'embedagent.cmd') -Code 'bundle.launcher.cli' -Message 'CLI launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path (Join-Path $BundleRoot 'embedagent-tui.cmd') -Code 'bundle.launcher.tui' -Message 'TUI launcher present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $SourcesRoot -Code 'sources.root' -Message 'Sources seed directory present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $sourcesManifestPath -Code 'sources.manifest' -Message 'assets-manifest.json present.' -TreatAsCompleteGate $true
Test-StaticPath -Results $results -Path $sourcesChecksumsPath -Code 'sources.checksums' -Message 'sources checksums.txt present.' -TreatAsCompleteGate $true

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
    $completeGateComponents = @('python_runtime', 'python_packages', 'mingit_portable', 'ripgrep', 'universal_ctags')
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

if (-not $SkipDynamicChecks) {
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
}

$failCount = @($results | Where-Object { $_.level -eq 'fail' }).Count
$warnCount = @($results | Where-Object { $_.level -eq 'warn' }).Count
$passCount = @($results | Where-Object { $_.level -eq 'pass' }).Count

foreach ($item in $results) {
    Write-Host ('[{0}] {1}: {2}' -f $item.level.ToUpperInvariant(), $item.code, $item.message)
}

Write-Host ('Summary: pass={0} warn={1} fail={2}' -f $passCount, $warnCount, $failCount)

if ($failCount -gt 0) {
    exit 1
}
