# EmbedAgent 零依赖打包完整指南

> 目标：构建完全自包含、零外部依赖、开箱即用的离线 bundle
> 适用：物理隔离内网环境（无互联网，仅有内网大模型服务）
> 更新日期：2026-03-30

---

## 1. 打包流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 导出 Python 依赖                                        │
│  python scripts/export-dependencies.py                          │
│  └── 生成: build/offline-cache/site-packages-export/            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  Step 2: 准备离线 bundle                                        │
│  powershell -File scripts/prepare-offline.ps1                   │
│  └── 生成: build/offline-staging/EmbedAgent/                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  Step 3: 构建最终 zip                                           │
│  powershell -File scripts/build-offline-bundle.ps1              │
│  └── 生成: build/offline-dist/embedagent-win7-x64.zip           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  Step 4: 验证 bundle                                            │
│  powershell -File scripts/validate-offline-bundle.ps1           │
│  └── 确保: 零依赖、完整性、可运行                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 详细步骤

### 2.1 环境准备

确保开发环境已安装：

```powershell
# Python 3.8（用于运行导出脚本）
python --version  # 3.8.x

# PowerShell 5.1+（用于打包脚本）
$PSVersionTable.PSVersion  # 5.1 或更高

# 工作目录
cd ccode-win7
```

### 2.2 导出 Python 依赖

这是关键步骤，确保**所有**依赖（包括传递依赖）都被包含：

```powershell
# 导出完整依赖（包括传递依赖）
python scripts\export-dependencies.py `
    --output-dir build\offline-cache\site-packages-export `
    --python-version 3.8

# 输出：
# - build/offline-cache/site-packages-export/site-packages/
# - build/offline-cache/site-packages-export/requirements-pinned.txt
# - build/offline-cache/site-packages-export/site-packages-manifest.json
```

**验证导出的依赖**：

```powershell
# 检查关键包是否存在
python scripts\export-dependencies.py `
    --output-dir build\offline-cache\site-packages-export `
    --verify-only
```

### 2.3 准备离线 Bundle

使用导出的 site-packages 和其他资产：

```powershell
# 方式 1：使用预下载的资产（推荐）
powershell -File scripts\prepare-offline.ps1 `
    -AssetIds python_embedded_x64,mingit_x64,ripgrep_x64,universal_ctags_x64 `
    -SitePackagesRoot build\offline-cache\site-packages-export\site-packages `
    -LlvmRoot toolchains\llvm\current

# 方式 2：允许下载资产（首次打包）
powershell -File scripts\prepare-offline.ps1 `
    -AssetIds python_embedded_x64,mingit_x64,ripgrep_x64,universal_ctags_x64 `
    -SitePackagesRoot build\offline-cache\site-packages-export\site-packages `
    -LlvmRoot toolchains\llvm\current `
    -AllowDownload

# 输出：build/offline-staging/EmbedAgent/
```

**关键参数说明**：

| 参数 | 说明 |
|------|------|
| `-AssetIds` | 要包含的第三方资产 |
| `-SitePackagesRoot` | 导出的 Python site-packages 目录 |
| `-LlvmRoot` | LLVM/Clang 工具链位置 |
| `-AllowDownload` | 允许下载缺失的资产 |

### 2.4 构建最终 Zip

```powershell
powershell -File scripts\build-offline-bundle.ps1

# 输出：
# - build/offline-dist/embedagent-win7-x64-<timestamp>/
# - build/offline-dist/embedagent-win7-x64-<timestamp>.zip
```

### 2.5 验证 Bundle

**严格验证（推荐用于正式发布）**：

```powershell
powershell -File scripts\validate-offline-bundle.ps1 -RequireComplete
```

**快速验证（开发调试）**：

```powershell
# 检查依赖完整性
python scripts\check-bundle-dependencies.py build\offline-dist\embedagent-win7-x64-<timestamp>

# 或运行完整验证
powershell -File scripts\validate-offline-bundle.ps1
```

---

## 3. Bundle 内容验证

### 3.1 依赖完整性检查清单

运行 `scripts/check-bundle-dependencies.py` 会检查：

- [x] Python 3.8.10 embeddable x64
- [x] 完整 site-packages（含传递依赖）
- [x] MinGit 2.46.2
- [x] ripgrep 14.1.1
- [x] Universal Ctags p6.2.20251116.0
- [x] LLVM/Clang 工具链
- [x] Launcher 脚本（embedagent.cmd, embedagent-tui.cmd, embedagent-gui.cmd）
- [x] 配置文件模板
- [x] 内网部署文档
- [x] GUI 静态文件
- [x] Bundle manifest

### 3.2 手动验证步骤

在**干净的 Windows 7 x64** 机器上：

```powershell
# 1. 确保没有 Python/Git/LLVM 在 PATH 中
Get-Command python -ErrorAction SilentlyContinue  # 应返回空
Get-Command git -ErrorAction SilentlyContinue     # 应返回空
Get-Command clang -ErrorAction SilentlyContinue   # 应返回空

# 2. 解压 bundle
Expand-Archive -Path embedagent-win7-x64.zip -DestinationPath C:\Tools

# 3. 验证依赖检查
python C:\Tools\EmbedAgent\scripts\check-bundle-dependencies.py C:\Tools\EmbedAgent

# 4. 测试 CLI
C:\Tools\EmbedAgent\embedagent.cmd --help

# 5. 测试工具链版本检测
C:\Tools\EmbedAgent\embedagent.cmd --version

# 6. 配置内网模型服务
notepad C:\Users\%USERNAME%\.embedagent\config.json

# 7. 运行实际任务
C:\Tools\EmbedAgent\embedagent.cmd --workspace D:\Project --model qwen3.5-coder "Hello"
```

---

## 4. 内网部署配置

### 4.1 配置文件位置

| 位置 | 用途 |
|------|------|
| `config/config.json.template` | Bundle 内置模板 |
| `~/.embedagent/config.json` | 用户级配置（内网部署时修改） |
| `.embedagent/config.json` | 项目级配置 |

### 4.2 内网模型服务配置示例

编辑 `%USERPROFILE%\.embedagent\config.json`：

```json
{
  "base_url": "http://192.168.1.100:8000/v1",
  "api_key": "sk-internal-key",
  "model": "qwen3.5-coder",
  "timeout": 120,
  "max_context_tokens": 32000,
  "reserve_output_tokens": 3000,
  "default_mode": "code"
}
```

---

## 5. 零依赖验证

### 5.1 验证清单

部署后确认目标机：

- [ ] 无 Python 安装或 Python 未在 PATH
- [ ] 无 Git 安装
- [ ] 无 LLVM/Clang 安装
- [ ] 无 Visual Studio 安装
- [ ] 无 Node.js 安装
- [ ] 无互联网连接
- [ ] Bundle 可独立运行
- [ ] 可连接内网大模型服务

### 5.2 自动化验证脚本

```powershell
# 在目标机上运行
C:\Tools\EmbedAgent\embedagent.cmd --self-test
```

预期输出：
```
✓ Python runtime: OK
✓ Site packages: OK (XX packages)
✓ Git: OK (bundled)
✓ ripgrep: OK (bundled)
✓ ctags: OK (bundled)
✓ Clang: OK (bundled)
✓ LLM connection: OK (192.168.1.100:8000)
All systems operational.
```

---

## 6. 故障排除

### 6.1 打包阶段

**问题**：`export-dependencies.py` 下载失败

**解决**：
```powershell
# 手动下载 wheel 并放入缓存
python -m pip download -d build/offline-cache/wheels <package-name>
```

**问题**：site-packages 大小过大

**解决**：
```powershell
# 移除开发/测试依赖
python scripts/export-dependencies.py --exclude-dev
```

### 6.2 部署阶段

**问题**：启动时提示缺少 DLL

**解决**：安装 Visual C++ Redistributable（可随 bundle 分发 `vcredist_x64.exe`）

**问题**：GUI 启动失败

**解决**：
- Windows 7 需安装 WebView2 Runtime，或使用 TUI 模式
- 检查 `embedagent-gui.cmd` 是否正确设置了 PYTHONPATH

**问题**：无法连接内网模型服务

**解决**：
1. 确认内网服务地址可达：`ping 192.168.1.100`
2. 确认端口开放：`telnet 192.168.1.100 8000`
3. 检查 config.json 格式是否正确

---

## 7. Bundle 大小优化

### 7.1 当前大小估算

| 组件 | 大小 |
|------|------|
| Python 3.8 embeddable | ~15 MB |
| Python site-packages | ~30-50 MB |
| MinGit | ~40 MB |
| ripgrep | ~5 MB |
| ctags | ~2 MB |
| LLVM/Clang | ~200-300 MB |
| EmbedAgent 代码 | ~1 MB |
| **总计** | **~300-450 MB** |

### 7.2 优化建议

1. **精简 Clang**：只包含必要的工具（clang, clang-tidy, llvm-cov）
2. **分离 GUI/TUI**：提供 CLI-only 版本（减少 ~20MB）
3. **压缩**：zip 压缩后通常可减少 30-40%

---

## 8. 完整构建命令

一键构建脚本：

```powershell
# build-offline.ps1
param(
    [string]$OutputName = "embedagent-win7-x64-$(Get-Date -Format 'yyyyMMddHHmm')"
)

$ErrorActionPreference = 'Stop'

Write-Host "=== EmbedAgent Offline Bundle Build ===" -ForegroundColor Green

# Step 1: Export dependencies
Write-Host "`n[1/4] Exporting Python dependencies..." -ForegroundColor Yellow
python scripts\export-dependencies.py `
    --output-dir build\offline-cache\site-packages-export `
    --python-version 3.8

# Step 2: Prepare bundle
Write-Host "`n[2/4] Preparing offline bundle..." -ForegroundColor Yellow
powershell -File scripts\prepare-offline.ps1 `
    -AssetIds python_embedded_x64,mingit_x64,ripgrep_x64,universal_ctags_x64 `
    -SitePackagesRoot build\offline-cache\site-packages-export\site-packages `
    -LlvmRoot toolchains\llvm\current `
    -AllowDownload

# Step 3: Build zip
Write-Host "`n[3/4] Building distribution zip..." -ForegroundColor Yellow
powershell -File scripts\build-offline-bundle.ps1

# Step 4: Validate
Write-Host "`n[4/4] Validating bundle..." -ForegroundColor Yellow
$bundleDir = Get-ChildItem build\offline-dist -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python scripts\check-bundle-dependencies.py $bundleDir.FullName

Write-Host "`n=== Build Complete ===" -ForegroundColor Green
Write-Host "Output: build\offline-dist\$OutputName.zip"
```

---

**确保零外部依赖，开箱即用！**
