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
    ('/OUT:' + $outputResolved),
    'shell32.lib',
    'user32.lib'
)

& $compiler @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Native GUI launcher build failed with exit code $LASTEXITCODE."
}
if (-not (Test-Path -LiteralPath $outputResolved)) {
    throw "Native GUI launcher compiler did not produce output: $outputResolved"
}

Write-Host "[launcher] Native GUI launcher ready: $outputResolved"
