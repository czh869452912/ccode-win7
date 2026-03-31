[CmdletBinding()]
param(
    # 禁止网络下载（须手动预置 build/bootstrap-cache 中的缓存文件）
    [switch]$NoDownload,

    # 下载缓存目录（默认 build/bootstrap-cache，与 offline-cache 平级）
    [string]$BootstrapCacheRoot = "build/bootstrap-cache",

    # LLVM 目标安装根目录（默认 toolchains/llvm/current）
    [string]$LlvmTargetRoot = "toolchains/llvm/current",

    # 显式指定 7za.exe 路径（跳过自动查找与下载）
    [string]$SevenZipPath = "",

    # 跳过 Python venv 创建步骤（仅安装 LLVM）
    [switch]$SkipPython,

    # 跳过 LLVM 工具链步骤（仅建 venv）
    [switch]$SkipLlvm,

    # 强制重新下载（忽略已有缓存与 SHA256 缓存命中）
    [switch]$Force,

    # 仅验证已有环境，不做任何修改
    [switch]$Verify
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

function Write-Step {
    param([string]$Message)
    Write-Host "[bootstrap] $Message"
}

function Write-StepWarn {
    param([string]$Message)
    Write-Host "[bootstrap] WARNING: $Message" -ForegroundColor Yellow
}

function Write-StepError {
    param([string]$Message)
    Write-Host "[bootstrap] ERROR: $Message" -ForegroundColor Red
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Test-FileSha256 {
    param(
        [string]$Path,
        [string]$ExpectedSha256
    )
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $actual -eq $ExpectedSha256.ToLowerInvariant()
}

function Get-FileSha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Download-File {
    param(
        [string]$Url,
        [string]$TargetPath
    )
    $parent = Split-Path -Parent $TargetPath
    Ensure-Directory -Path $parent
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-Step "  Downloading: $Url"
    Invoke-WebRequest -Uri $Url -OutFile $TargetPath -UseBasicParsing
}

function Normalize-ExtractedRoot {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root)) { return }
    $items      = @(Get-ChildItem -LiteralPath $Root -Force)
    $dirs       = @($items | Where-Object { $_.PSIsContainer })
    $files      = @($items | Where-Object { -not $_.PSIsContainer })
    if ($dirs.Count -ne 1 -or $files.Count -ne 0) { return }
    $nested     = $dirs[0].FullName
    $nestedItems = @(Get-ChildItem -LiteralPath $nested -Force)
    foreach ($item in $nestedItems) {
        Move-Item -LiteralPath $item.FullName -Destination $Root -Force
    }
    Remove-Item -LiteralPath $nested -Recurse -Force
}

function Invoke-7zExtract {
    param(
        [string]$SevenZipExe,
        [string]$ArchivePath,
        [string]$DestinationPath
    )
    Ensure-Directory -Path $DestinationPath
    $output = & $SevenZipExe x $ArchivePath "-o$DestinationPath" -y 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "7za extraction failed (exit $LASTEXITCODE) for: $ArchivePath`n$output"
    }
}

function Merge-LlvmBinaries {
    param(
        [string]$SourceBinDir,
        [string]$TargetBinDir,
        [string[]]$Patterns,
        [bool]$OverwriteExisting = $true
    )
    Ensure-Directory -Path $TargetBinDir
    foreach ($pattern in $Patterns) {
        $hits = @(Get-ChildItem -LiteralPath $SourceBinDir -Filter $pattern -File -ErrorAction SilentlyContinue)
        foreach ($file in $hits) {
            $dest = Join-Path $TargetBinDir $file.Name
            if ((-not $OverwriteExisting) -and (Test-Path -LiteralPath $dest)) { continue }
            Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
        }
    }
}

# ---------------------------------------------------------------------------
# Step 3 helper: 查找或下载 7za.exe
# ---------------------------------------------------------------------------

function Resolve-7za {
    param(
        [string]$ExplicitPath,
        [string]$CacheRoot,
        [string]$AssetManifestPath,
        [bool]$AllowDownload,
        [bool]$ForceDownload
    )

    # 1. 显式路径
    if ($ExplicitPath) {
        if (Test-Path -LiteralPath $ExplicitPath) {
            Write-Step "  Using explicit 7za path: $ExplicitPath"
            return $ExplicitPath
        }
        throw "Explicit -SevenZipPath not found: $ExplicitPath"
    }

    # 2. PATH 中的系统 7z / 7za
    foreach ($name in @('7z', '7za')) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) {
            Write-Step "  Using system $name from PATH: $($found.Source)"
            return $found.Source
        }
    }

    # 3. 缓存中的 7za.exe
    $cachedExe = Join-Path $CacheRoot '7za\7za.exe'
    if ((Test-Path -LiteralPath $cachedExe) -and (-not $ForceDownload)) {
        Write-Step "  Using cached 7za.exe: $cachedExe"
        return $cachedExe
    }

    # 4. 下载
    if (-not $AllowDownload) {
        throw ("7za.exe not found and -NoDownload is set.`n" +
               "Please install 7-Zip (https://www.7-zip.org/) or place 7za.exe in PATH,`n" +
               "or pre-download the extra package to: $CacheRoot\7za\7z2409-extra.zip`n" +
               "then re-run without -NoDownload.")
    }

    # 从 offline-assets.json 读取 7za_standalone 条目
    if (-not (Test-Path -LiteralPath $AssetManifestPath)) {
        throw "Asset manifest not found: $AssetManifestPath"
    }
    $manifest = Get-Content -LiteralPath $AssetManifestPath -Raw | ConvertFrom-Json
    $asset = $null
    foreach ($a in @($manifest.assets)) {
        if ($a.id -eq '7za_standalone') { $asset = $a; break }
    }
    if (-not $asset) {
        throw "Asset '7za_standalone' not found in: $AssetManifestPath"
    }

    $zipCachePath = Join-Path $CacheRoot $asset.cache_relpath
    if (-not (Test-Path -LiteralPath $zipCachePath) -or $ForceDownload) {
        Download-File -Url $asset.upstream_url -TargetPath $zipCachePath
    }

    # SHA256 校验（若 manifest 中已填写）
    if ($asset.sha256) {
        if (-not (Test-FileSha256 -Path $zipCachePath -ExpectedSha256 $asset.sha256)) {
            $actual = Get-FileSha256 -Path $zipCachePath
            throw ("SHA256 mismatch for 7za extra zip.`n" +
                   "  Expected : $($asset.sha256)`n" +
                   "  Actual   : $actual`n" +
                   "  File     : $zipCachePath")
        }
    } else {
        $computed = Get-FileSha256 -Path $zipCachePath
        Write-StepWarn ("7za_standalone sha256 is empty in offline-assets.json.`n" +
                        "  Computed SHA256: $computed`n" +
                        "  Please fill in offline-assets.json > 7za_standalone > sha256.")
    }

    # 解压 zip（PowerShell 原生，无需 7za）
    $extractDir = Join-Path $CacheRoot '7za\extracted'
    if (Test-Path -LiteralPath $extractDir) {
        Remove-Item -LiteralPath $extractDir -Recurse -Force
    }
    Expand-Archive -LiteralPath $zipCachePath -DestinationPath $extractDir -Force

    # 找到 7za.exe
    $exeInExtract = Get-ChildItem -LiteralPath $extractDir -Filter '7za.exe' -Recurse -File | Select-Object -First 1
    if (-not $exeInExtract) {
        throw "7za.exe not found in extracted archive: $zipCachePath"
    }

    $finalExe = $cachedExe
    Ensure-Directory -Path (Split-Path -Parent $finalExe)
    Copy-Item -LiteralPath $exeInExtract.FullName -Destination $finalExe -Force
    Remove-Item -LiteralPath $extractDir -Recurse -Force

    Write-Step "  7za.exe ready: $finalExe"
    return $finalExe
}

# ---------------------------------------------------------------------------
# Step 4/5 helper: 下载 + 校验单个 LLVM 组件
# ---------------------------------------------------------------------------

function Get-LlvmComponent {
    param(
        [string]$ComponentName,
        [object]$Component,
        [string]$CacheRoot,
        [bool]$AllowDownload,
        [bool]$ForceDownload
    )

    $cachePath = Join-Path $CacheRoot $Component.cache_relpath
    $hasCache  = Test-Path -LiteralPath $cachePath

    if ($hasCache -and (-not $ForceDownload)) {
        if ($Component.sha256) {
            if (Test-FileSha256 -Path $cachePath -ExpectedSha256 $Component.sha256) {
                Write-Step "  [$componentName] Cache hit: $cachePath"
                return $cachePath
            }
            Write-StepWarn "[$componentName] Cache SHA256 mismatch, re-downloading."
        } else {
            Write-Step "  [$componentName] Cache hit (no SHA256 in manifest): $cachePath"
            return $cachePath
        }
    }

    if (-not $AllowDownload) {
        throw ("[$componentName] Archive missing and -NoDownload is set.`n" +
               "  Please pre-download to: $cachePath`n" +
               "  URL: $($Component.source)")
    }

    Download-File -Url $Component.source -TargetPath $cachePath

    if ($Component.sha256) {
        if (-not (Test-FileSha256 -Path $cachePath -ExpectedSha256 $Component.sha256)) {
            $actual = Get-FileSha256 -Path $cachePath
            throw ("SHA256 mismatch for [$componentName].`n" +
                   "  Expected : $($Component.sha256)`n" +
                   "  Actual   : $actual`n" +
                   "  File     : $cachePath")
        }
        Write-Step "  [$componentName] SHA256 verified."
    } else {
        $computed = Get-FileSha256 -Path $cachePath
        Write-StepWarn ("[$componentName] sha256 is empty in toolchains/manifest.json.`n" +
                        "  Computed SHA256: $computed`n" +
                        "  Please fill in manifest.json > components > $componentName > sha256.")
    }

    return $cachePath
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

$projectRoot        = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$assetManifestPath  = Join-Path $projectRoot 'scripts\offline-assets.json'
$llvmManifestPath   = Join-Path $projectRoot 'toolchains\manifest.json'

if (-not [System.IO.Path]::IsPathRooted($BootstrapCacheRoot)) {
    $BootstrapCacheRoot = Join-Path $projectRoot $BootstrapCacheRoot
}
if (-not [System.IO.Path]::IsPathRooted($LlvmTargetRoot)) {
    $LlvmTargetRoot = Join-Path $projectRoot $LlvmTargetRoot
}

$allowDownload = -not $NoDownload.IsPresent

Write-Host ''
Write-Host '[bootstrap] ================================================'
Write-Host '[bootstrap] EmbedAgent dev-env bootstrap'
Write-Host "[bootstrap] Project root : $projectRoot"
Write-Host "[bootstrap] Cache root   : $BootstrapCacheRoot"
Write-Host '[bootstrap] ================================================'

# ---------------------------------------------------------------------------
# Step 1: 先决条件检查
# ---------------------------------------------------------------------------

Write-Step 'Step 1/7: Checking prerequisites...'

# PowerShell 版本
if ($PSVersionTable.PSVersion.Major -lt 5 -or
    ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -lt 1)) {
    throw "PowerShell 5.1 or later is required. Current: $($PSVersionTable.PSVersion)"
}
Write-Step "  PowerShell $($PSVersionTable.PSVersion) OK"

# uv（仅在需要 Python 时检查）
if (-not $SkipPython -and -not $Verify) {
    $uvCmd = Get-Command 'uv' -ErrorAction SilentlyContinue
    if (-not $uvCmd) {
        throw ("'uv' not found in PATH.`n" +
               "Install uv from: https://docs.astral.sh/uv/getting-started/installation/`n" +
               "  Windows (PowerShell): irm https://astral.sh/uv/install.ps1 | iex")
    }
    $uvVersion = (& uv --version 2>&1) -join ''
    Write-Step "  uv: $uvVersion"
}

# 磁盘空间粗估（LLVM ~1.2 GB + Python ~200 MB + bundle assets ~600 MB）
$drive       = Split-Path -Qualifier $projectRoot
$driveInfo   = [System.IO.DriveInfo]::new($drive)
$freeGB      = [math]::Round($driveInfo.AvailableFreeSpace / 1GB, 1)
if ($freeGB -lt 2) {
    Write-StepWarn "Low disk space on $drive`: $freeGB GB free. Recommend at least 2 GB."
} else {
    Write-Step "  Disk free on $drive`: $freeGB GB"
}

if ($Verify) {
    Write-Step 'Step 2-7 skipped (-Verify mode). Running verification only...'
}

# ---------------------------------------------------------------------------
# Step 2: Python venv (uv sync)
# ---------------------------------------------------------------------------

if (-not $SkipPython -and -not $Verify) {
    Write-Step 'Step 2/7: Creating Python venv with uv...'

    $venvRoot        = Join-Path $projectRoot '.venv'
    $sitePackages    = Join-Path $venvRoot 'Lib\site-packages'
    $venvValid       = (Test-Path -LiteralPath $sitePackages)

    if ($venvValid -and -not $Force) {
        Write-Step "  .venv already exists and has site-packages — skipping (use -Force to recreate)."
    } else {
        if ($venvValid -and $Force) {
            Write-Step '  -Force: removing existing .venv...'
            Remove-Item -LiteralPath $venvRoot -Recurse -Force
        }

        Write-Step '  Running: uv sync  (this will download Python 3.8.10 if not cached by uv)'
        $uvOutput = & uv sync --project $projectRoot 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "uv sync failed (exit $LASTEXITCODE).`nOutput:`n$($uvOutput -join "`n")"
        }

        if (-not (Test-Path -LiteralPath $sitePackages)) {
            throw ".venv\Lib\site-packages not found after uv sync. Check uv output above."
        }
        Write-Step "  Python venv ready: $venvRoot"
    }
    Write-Step "  site-packages : $sitePackages"
} elseif ($SkipPython) {
    Write-Step 'Step 2/7: Python venv skipped (-SkipPython).'
}

# ---------------------------------------------------------------------------
# Step 3: 解决 7za.exe
# ---------------------------------------------------------------------------

$sevenZipExe = $null
if (-not $SkipLlvm -and -not $Verify) {
    Write-Step 'Step 3/7: Resolving 7za.exe...'
    $sevenZipExe = Resolve-7za `
        -ExplicitPath    $SevenZipPath `
        -CacheRoot       $BootstrapCacheRoot `
        -AssetManifestPath $assetManifestPath `
        -AllowDownload   $allowDownload `
        -ForceDownload   $Force.IsPresent
} elseif (-not $SkipLlvm) {
    # Verify mode: just check
    $cachedExe = Join-Path $BootstrapCacheRoot '7za\7za.exe'
    foreach ($name in @('7z', '7za')) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) { $sevenZipExe = $found.Source; break }
    }
    if (-not $sevenZipExe -and (Test-Path -LiteralPath $cachedExe)) {
        $sevenZipExe = $cachedExe
    }
}

# ---------------------------------------------------------------------------
# Step 4: 下载 LLVM 组件
# ---------------------------------------------------------------------------

$clangCachePath    = $null
$clangTidyCache    = $null
$llvmBigCachePath  = $null   # shared by llvm_cov + llvm_profdata

if (-not $SkipLlvm -and -not $Verify) {
    Write-Step 'Step 4/7: Downloading LLVM component archives...'

    if (-not (Test-Path -LiteralPath $llvmManifestPath)) {
        throw "LLVM manifest not found: $llvmManifestPath"
    }
    $llvmManifest = Get-Content -LiteralPath $llvmManifestPath -Raw | ConvertFrom-Json
    $comps        = $llvmManifest.components

    Ensure-Directory -Path $BootstrapCacheRoot

    # clang 7z
    Write-Step '  [1/3] clang 20.1.8 (7z, ~300 MB)...'
    $clangCachePath = Get-LlvmComponent `
        -ComponentName 'clang' -Component $comps.clang `
        -CacheRoot $BootstrapCacheRoot -AllowDownload $allowDownload -ForceDownload $Force.IsPresent

    # clang-tidy exe
    Write-Step '  [2/3] clang-tidy 20.1.0 (exe, ~80 MB)...'
    $clangTidyCache = Get-LlvmComponent `
        -ComponentName 'clang_tidy' -Component $comps.clang_tidy `
        -CacheRoot $BootstrapCacheRoot -AllowDownload $allowDownload -ForceDownload $Force.IsPresent

    # llvm-21 7z (cov + profdata; same archive)
    Write-Step '  [3/3] LLVM 21.1.8 (7z, ~500 MB, for llvm-cov + llvm-profdata)...'
    $llvmBigCachePath = Get-LlvmComponent `
        -ComponentName 'llvm_cov' -Component $comps.llvm_cov `
        -CacheRoot $BootstrapCacheRoot -AllowDownload $allowDownload -ForceDownload $Force.IsPresent
}

# ---------------------------------------------------------------------------
# Step 5: 解压 + 组装 toolchains/llvm/current/bin/
# ---------------------------------------------------------------------------

if (-not $SkipLlvm -and -not $Verify) {
    Write-Step 'Step 5/7: Extracting and assembling LLVM toolchain...'

    $llvmBinDir  = Join-Path $LlvmTargetRoot 'bin'
    $extractBase = Join-Path $BootstrapCacheRoot 'llvm-extract'

    Ensure-Directory -Path $llvmBinDir

    # --- 5a: 解压 clang 7z ---
    $clangExtractDir = Join-Path $extractBase 'clang'
    Write-Step '  Extracting clang archive...'
    if (Test-Path -LiteralPath $clangExtractDir) {
        Remove-Item -LiteralPath $clangExtractDir -Recurse -Force
    }
    Invoke-7zExtract -SevenZipExe $sevenZipExe -ArchivePath $clangCachePath -DestinationPath $clangExtractDir
    Normalize-ExtractedRoot -Root $clangExtractDir

    $clangBin = Join-Path $clangExtractDir 'bin'
    if (-not (Test-Path -LiteralPath $clangBin)) {
        throw "Expected bin/ not found after extracting clang archive at: $clangExtractDir"
    }

    Write-Step '  Copying clang binaries...'
    Merge-LlvmBinaries -SourceBinDir $clangBin -TargetBinDir $llvmBinDir `
        -Patterns @('*.exe', '*.dll') -OverwriteExisting $true

    # --- 5b: 解压 LLVM 21 7z ---
    $llvm21ExtractDir = Join-Path $extractBase 'llvm21'
    Write-Step '  Extracting LLVM 21 archive...'
    if (Test-Path -LiteralPath $llvm21ExtractDir) {
        Remove-Item -LiteralPath $llvm21ExtractDir -Recurse -Force
    }
    Invoke-7zExtract -SevenZipExe $sevenZipExe -ArchivePath $llvmBigCachePath -DestinationPath $llvm21ExtractDir
    Normalize-ExtractedRoot -Root $llvm21ExtractDir

    $llvm21Bin = Join-Path $llvm21ExtractDir 'bin'
    if (-not (Test-Path -LiteralPath $llvm21Bin)) {
        throw "Expected bin/ not found after extracting LLVM 21 archive at: $llvm21ExtractDir"
    }

    Write-Step '  Copying llvm-cov and llvm-profdata (not overwriting clang tools)...'
    Merge-LlvmBinaries -SourceBinDir $llvm21Bin -TargetBinDir $llvmBinDir `
        -Patterns @('llvm-cov.exe', 'llvm-profdata.exe', 'lld-link.exe') -OverwriteExisting $false

    # --- 5c: clang-tidy exe ---
    Write-Step '  Copying clang-tidy...'
    $clangTidyDest = Join-Path $llvmBinDir 'clang-tidy.exe'
    Copy-Item -LiteralPath $clangTidyCache -Destination $clangTidyDest -Force

    # --- 5d: 清理临时解压目录 ---
    Write-Step '  Cleaning up extract temp dirs...'
    Remove-Item -LiteralPath $clangExtractDir  -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $llvm21ExtractDir -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# Step 6: 写 clang-analyzer.bat
# ---------------------------------------------------------------------------

if (-not $SkipLlvm -and -not $Verify) {
    Write-Step 'Step 6/7: Writing clang-analyzer.bat...'
    $analyzerBat = Join-Path $LlvmTargetRoot 'bin\clang-analyzer.bat'
    $content     = "@echo off`r`nclang.exe --analyze %*`r`n"
    [System.IO.File]::WriteAllText($analyzerBat, $content, [System.Text.Encoding]::ASCII)
    Write-Step "  Written: $analyzerBat"
}

# ---------------------------------------------------------------------------
# Step 7: 验证 + 摘要
# ---------------------------------------------------------------------------

Write-Step 'Step 7/7: Verifying installation...'

$errors = @()

# Python venv 检查
if (-not $SkipPython) {
    $sitePackages = Join-Path $projectRoot '.venv\Lib\site-packages'
    if (Test-Path -LiteralPath $sitePackages) {
        $pkgCount = @(Get-ChildItem -LiteralPath $sitePackages -Directory).Count
        Write-Step "  .venv/Lib/site-packages : OK ($pkgCount package dirs)"
    } else {
        $errors += 'Python site-packages not found: ' + $sitePackages
        Write-StepError 'Python site-packages NOT found.'
    }
}

# LLVM 工具验证
if (-not $SkipLlvm) {
    $tools = @(
        @{ Name = 'clang';         Exe = 'clang.exe'         },
        @{ Name = 'clang-tidy';    Exe = 'clang-tidy.exe'    },
        @{ Name = 'llvm-cov';      Exe = 'llvm-cov.exe'      },
        @{ Name = 'llvm-profdata'; Exe = 'llvm-profdata.exe' },
        @{ Name = 'clang-analyzer'; Exe = 'clang-analyzer.bat' }
    )

    $llvmBinDir = Join-Path $LlvmTargetRoot 'bin'
    $env:PATH = "$llvmBinDir;$($env:PATH)"

    foreach ($tool in $tools) {
        $toolPath = Join-Path $llvmBinDir $tool.Exe
        if (-not (Test-Path -LiteralPath $toolPath)) {
            $errors += "$($tool.Name) not found: $toolPath"
            Write-StepError "  $($tool.Name) : NOT FOUND"
            continue
        }
        if ($tool.Exe.EndsWith('.exe')) {
            $ver = (& $toolPath --version 2>&1) | Select-Object -First 1
            Write-Step "  $($tool.Name) : $ver"
        } else {
            Write-Step "  $($tool.Name) : OK (bat)"
        }
    }
}

# 最终摘要
Write-Host ''
Write-Host '[bootstrap] ================================================'
if ($errors.Count -gt 0) {
    Write-Host '[bootstrap] Bootstrap INCOMPLETE — errors:' -ForegroundColor Red
    foreach ($e in $errors) {
        Write-Host "[bootstrap]   - $e" -ForegroundColor Red
    }
} else {
    Write-Host '[bootstrap] Bootstrap COMPLETE.' -ForegroundColor Green
    if (-not $SkipPython) {
        Write-Host "[bootstrap]   Python venv     : $projectRoot\.venv  (Python 3.8.10)"
        Write-Host "[bootstrap]   site-packages   : $projectRoot\.venv\Lib\site-packages"
    }
    if (-not $SkipLlvm) {
        Write-Host "[bootstrap]   LLVM root       : $LlvmTargetRoot"
    }
    Write-Host ''
    Write-Host '[bootstrap] Next step — package the offline bundle:'
    Write-Host '[bootstrap]   .\scripts\prepare-offline.ps1 `'
    Write-Host '[bootstrap]     -AllowDownload `'
    Write-Host '[bootstrap]     -AssetIds "python_embedded_x64,mingit_x64,ripgrep_x64,universal_ctags_x64,webview2_fixed_runtime_x64"'
}
Write-Host '[bootstrap] ================================================'
Write-Host ''

if ($errors.Count -gt 0) {
    exit 1
}
