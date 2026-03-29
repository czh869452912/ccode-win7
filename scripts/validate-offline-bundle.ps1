[CmdletBinding()]
param(
    [string]$ArtifactName = 'embedagent-win7-x64',
    [string]$BundleRoot = "",
    [string]$ZipPath = "",
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

function Test-PathOrRecord {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$Path,
        [string]$Code,
        [string]$Message,
        [bool]$Required
    )

    if (Test-Path -LiteralPath $Path) {
        Add-Result -Results $Results -Level 'pass' -Code $Code -Message $Message
        return $true
    }

    $level = if ($Required) { 'fail' } else { 'warn' }
    Add-Result -Results $Results -Level $level -Code $Code -Message ('Missing path: {0}' -f $Path)
    return $false
}

function Invoke-CommandCheck {
    param(
        [System.Collections.ArrayList]$Results,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Code
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        Add-Result -Results $Results -Level 'warn' -Code $Code -Message ('Skipped command check because file is missing: {0}' -f $FilePath)
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
        [string]$BundleRoot,
        [string]$ChecksumPath
    )

    $lines = Get-ChecksumLines -ChecksumPath $ChecksumPath
    if ($lines.Count -eq 0) {
        Add-Result -Results $Results -Level 'fail' -Code 'checksums.empty' -Message 'checksums.txt is missing or empty.'
        return
    }

    foreach ($line in $lines) {
        $parts = $line.Split('*', 2)
        if ($parts.Count -ne 2) {
            Add-Result -Results $Results -Level 'fail' -Code 'checksums.format' -Message ('Invalid checksum line: {0}' -f $line)
            continue
        }
        $expectedHash = $parts[0].Trim().ToLowerInvariant()
        $relativePath = $parts[1].Trim().Replace('/', '\')
        $targetPath = Join-Path $BundleRoot $relativePath
        if (-not (Test-Path -LiteralPath $targetPath)) {
            Add-Result -Results $Results -Level 'fail' -Code 'checksums.missing_file' -Message ('Missing file referenced by checksums.txt: {0}' -f $relativePath)
            continue
        }
        $actualHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            Add-Result -Results $Results -Level 'fail' -Code 'checksums.mismatch' -Message ('Checksum mismatch: {0}' -f $relativePath)
        }
    }

    if (-not @($Results | Where-Object { $_.code -like 'checksums.*' -and $_.level -eq 'fail' }).Count) {
        Add-Result -Results $Results -Level 'pass' -Code 'checksums.ok' -Message 'checksums.txt verified successfully.'
    }
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$defaultBundleRoot = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName)
$defaultZipPath = Join-Path $projectRoot ('build\offline-dist\' + $ArtifactName + '.zip')

if (-not $BundleRoot) {
    $BundleRoot = $defaultBundleRoot
}
if (-not $ZipPath) {
    $ZipPath = $defaultZipPath
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

$requiredPaths = @(
    @{ path = (Join-Path $BundleRoot 'app\embedagent'); code = 'bundle.app'; message = 'Application directory present.' },
    @{ path = (Join-Path $BundleRoot 'config\config.json'); code = 'bundle.config'; message = 'Default config template present.' },
    @{ path = (Join-Path $BundleRoot 'config\permission-rules.json'); code = 'bundle.permissions'; message = 'Default permission rules template present.' },
    @{ path = $manifestPath; code = 'bundle.manifest'; message = 'bundle-manifest.json present.' },
    @{ path = $checksumsPath; code = 'bundle.checksums'; message = 'checksums.txt present.' },
    @{ path = (Join-Path $BundleRoot 'embedagent.cmd'); code = 'bundle.launcher.cli'; message = 'CLI launcher present.' },
    @{ path = (Join-Path $BundleRoot 'embedagent-tui.cmd'); code = 'bundle.launcher.tui'; message = 'TUI launcher present.' }
)

foreach ($item in $requiredPaths) {
    [void](Test-PathOrRecord -Results $results -Path $item.path -Code $item.code -Message $item.message -Required $true)
}

$zipExists = Test-Path -LiteralPath $ZipPath
if ($zipExists) {
    Add-Result -Results $results -Level 'pass' -Code 'bundle.zip' -Message ('Zip artifact present: {0}' -f $ZipPath)
}
else {
    $zipLevel = if ($RequireComplete) { 'fail' } else { 'warn' }
    Add-Result -Results $results -Level $zipLevel -Code 'bundle.zip' -Message ('Zip artifact missing: {0}' -f $ZipPath)
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
    foreach ($component in @($manifest.components)) {
        if (-not $component.required) {
            continue
        }
        $level = 'pass'
        if ($component.status -eq 'missing') {
            $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        }
        elseif ($component.status -eq 'skipped') {
            $level = if ($RequireComplete) { 'fail' } else { 'warn' }
        }
        Add-Result -Results $results -Level $level -Code ('component.' + $component.name) -Message ('{0}: {1}' -f $component.status, $component.notes)
    }
}

if (Test-Path -LiteralPath $checksumsPath) {
    Validate-Checksums -Results $results -BundleRoot $BundleRoot -ChecksumPath $checksumsPath
}

if (-not $SkipDynamicChecks) {
    $pythonExe = Join-Path $BundleRoot 'runtime\python\python.exe'
    $rgExe = Join-Path $BundleRoot 'bin\rg\rg.exe'
    $ctagsExe = Join-Path $BundleRoot 'bin\ctags\ctags.exe'
    $clangExe = Join-Path $BundleRoot 'bin\llvm\bin\clang.exe'
    $gitExe = Get-GitExecutablePath -BundleRoot $BundleRoot

    Invoke-CommandCheck -Results $results -FilePath $pythonExe -Arguments @('--version') -Code 'dynamic.python'
    Invoke-CommandCheck -Results $results -FilePath $rgExe -Arguments @('--version') -Code 'dynamic.rg'
    Invoke-CommandCheck -Results $results -FilePath $ctagsExe -Arguments @('--version') -Code 'dynamic.ctags'
    Invoke-CommandCheck -Results $results -FilePath $clangExe -Arguments @('--version') -Code 'dynamic.clang'
    if ($gitExe) {
        Invoke-CommandCheck -Results $results -FilePath $gitExe -Arguments @('--version') -Code 'dynamic.git'
    }
    else {
        Add-Result -Results $results -Level 'warn' -Code 'dynamic.git' -Message 'Skipped git version check because git.exe was not found in the bundle.'
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
