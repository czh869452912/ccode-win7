[CmdletBinding()]
param(
    [string]$SourcePath = "",
    [string]$OutputPath = "",
    [string]$CompilerPath = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-ProjectPath {
    param(
        [string]$ProjectRoot,
        [string]$Value
    )

    if (-not $Value) {
        return $null
    }
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }
    return Join-Path $ProjectRoot $Value
}

function Resolve-CompilerPath {
    param(
        [string]$CompilerPath
    )

    if ($CompilerPath) {
        if (-not (Test-Path -LiteralPath $CompilerPath)) {
            throw "Configured launcher compiler not found: $CompilerPath"
        }
        return (Resolve-Path -LiteralPath $CompilerPath).Path
    }

    if ($env:EMBEDAGENT_LAUNCHER_CC) {
        $envCompiler = [string]$env:EMBEDAGENT_LAUNCHER_CC
        if (Test-Path -LiteralPath $envCompiler) {
            return (Resolve-Path -LiteralPath $envCompiler).Path
        }
        $envCommand = Get-Command $envCompiler -ErrorAction SilentlyContinue
        if ($envCommand -and $envCommand.Source) {
            return $envCommand.Source
        }
        throw "EMBEDAGENT_LAUNCHER_CC does not resolve to a compiler: $envCompiler"
    }

    foreach ($candidate in @('cl.exe', 'clang-cl.exe')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            return $command.Source
        }
    }

    throw "No launcher compiler found. Set -CompilerPath or EMBEDAGENT_LAUNCHER_CC to cl.exe or clang-cl.exe."
}

function Resolve-VsDevCmdPath {
    $vswhereCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft Visual Studio\Installer\vswhere.exe')
    )

    foreach ($vswhere in $vswhereCandidates) {
        if (-not (Test-Path -LiteralPath $vswhere)) {
            continue
        }
        $installationPath = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null | Select-Object -First 1)
        if (-not $installationPath) {
            continue
        }
        $candidate = Join-Path $installationPath 'Common7\Tools\VsDevCmd.bat'
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return ''
}

function Invoke-Compiler {
    param(
        [string]$Compiler,
        [string[]]$Arguments
    )

    $compilerFile = Split-Path -Leaf $Compiler
    if ($compilerFile -ieq 'cl.exe') {
        & $Compiler @Arguments
        $script:LauncherCompilerExitCode = $LASTEXITCODE
        return
    }

    $vsDevCmd = Resolve-VsDevCmdPath
    if ($vsDevCmd) {
        $command = 'call "{0}" -arch=x64 -host_arch=x64 >nul && cl.exe {1}' -f $vsDevCmd, (($Arguments | ForEach-Object { '"' + ($_ -replace '"', '\"') + '"' }) -join ' ')
        & cmd.exe /d /s /c $command
        $script:LauncherCompilerExitCode = $LASTEXITCODE
        return
    }

    & $Compiler @Arguments
    $script:LauncherCompilerExitCode = $LASTEXITCODE
    return
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$sourceResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $SourcePath
if (-not $sourceResolved) {
    $sourceResolved = Join-Path $projectRoot 'scripts\launcher\embedagent_gui_launcher.cpp'
}
if (-not (Test-Path -LiteralPath $sourceResolved)) {
    throw "GUI launcher source not found: $sourceResolved"
}
$sourceResolved = (Resolve-Path -LiteralPath $sourceResolved).Path

$outputResolved = Resolve-ProjectPath -ProjectRoot $projectRoot -Value $OutputPath
if (-not $outputResolved) {
    $outputResolved = Join-Path $projectRoot 'build\offline-cache\gui-launcher\embedagent-gui.exe'
}
$outputParent = Split-Path -Parent $outputResolved
if (-not (Test-Path -LiteralPath $outputParent)) {
    New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
}

$compiler = Resolve-CompilerPath -CompilerPath $CompilerPath
$objectPath = [System.IO.Path]::ChangeExtension($outputResolved, '.obj')
$programDatabase = [System.IO.Path]::ChangeExtension($outputResolved, '.pdb')

Write-Host "[launcher] Building native GUI launcher..."
Write-Host "[launcher]   Source:   $sourceResolved"
Write-Host "[launcher]   Output:   $outputResolved"
Write-Host "[launcher]   Compiler: $compiler"

$arguments = @(
    '/nologo',
    '/W4',
    '/EHsc',
    '/MT',
    ('/Fo' + $objectPath),
    ('/Fd' + $programDatabase),
    $sourceResolved,
    '/link',
    '/NOLOGO',
    '/SUBSYSTEM:WINDOWS,6.01',
    '/Brepro',
    ('/OUT:' + $outputResolved),
    'shell32.lib',
    'user32.lib'
)

$script:LauncherCompilerExitCode = 0
Invoke-Compiler -Compiler $compiler -Arguments $arguments
$exitCode = $script:LauncherCompilerExitCode
if ($exitCode -ne 0) {
    throw "Native GUI launcher build failed with exit code $exitCode."
}
if (-not (Test-Path -LiteralPath $outputResolved)) {
    throw "Native GUI launcher compiler did not produce output: $outputResolved"
}

Write-Host "[launcher] Native GUI launcher ready: $outputResolved"
