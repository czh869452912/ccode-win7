$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot 'activate-bundled-llvm.ps1')

$probeDir = Join-Path $projectRoot 'toolchains\probe_script'
New-Item -ItemType Directory -Force -Path $probeDir | Out-Null
$sourcePath = Join-Path $probeDir 'main.c'
try {
@"
int add(int a, int b) {
    return a + b;
}

int main(void) {
    return add(1, 2);
}
"@ | Set-Content -Path $sourcePath -Encoding ASCII

    clang --version
    clang-tidy --version
    llvm-profdata --version
    clang -c $sourcePath -o (Join-Path $probeDir 'main.obj')
    clang --analyze -Xanalyzer -analyzer-output=text $sourcePath
    clang-tidy $sourcePath --
    Write-Host 'Bundled LLVM smoke test completed.'
}
finally {
    if (Test-Path $probeDir) {
        Remove-Item $probeDir -Recurse -Force
    }
}
