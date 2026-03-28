param(
    [string]$Root = ""
)

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $Root) {
    $Root = Join-Path $projectRoot 'toolchains\llvm\current'
}
$resolvedRoot = Resolve-Path $Root
$binDir = Join-Path $resolvedRoot 'bin'
$libexecDir = Join-Path $resolvedRoot 'libexec'

$pathParts = @($binDir)
if (Test-Path $libexecDir) {
    $pathParts += $libexecDir
}
if ($env:PATH) {
    $pathParts += $env:PATH
}

$env:EMBEDAGENT_LLVM_ROOT = $resolvedRoot
$env:PATH = [string]::Join([IO.Path]::PathSeparator, $pathParts)

Write-Host "EMBEDAGENT_LLVM_ROOT=$env:EMBEDAGENT_LLVM_ROOT"
Write-Host "Bundled LLVM toolchain activated."
