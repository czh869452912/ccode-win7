# EmbedAgent GUI 打包配置指南

> 更新日期：2026-03-31（Bundle 对齐 / WebView2 / editable-path 清理修订）
> 适用：Phase 7 离线打包

---

## 1. GUI 依赖清单

GUI 前端依赖以下 Python 包（不在基础依赖中，需额外安装）：

| 包名 | 版本建议 | 用途 | 打包方式 |
|------|----------|------|----------|
| `pywebview` | >=4.0 | WebView 窗口 | vendored site-packages |
| `fastapi` | >=0.100 | HTTP 后端 | vendored site-packages |
| `uvicorn` | >=0.23 | ASGI 服务器 | vendored site-packages |
| `websockets` | >=11.0 | WebSocket 支持 | vendored site-packages |
| `pydantic` | >=2.0 | FastAPI 依赖 | vendored site-packages |
| `starlette` | >=0.27 | FastAPI 依赖 | vendored site-packages |
| `anyio` | >=3.0 | ASGI 依赖 | vendored site-packages |
| `click` | >=8.0 | uvicorn 依赖 | vendored site-packages |
| `h11` | >=0.14 | HTTP 协议 | vendored site-packages |
| `python-dotenv` | >=0.19 | uvicorn 依赖 | vendored site-packages |
| `typing-extensions` | >=4.0 | 类型支持 | vendored site-packages |

---

## 2. Windows 7 兼容性说明

### 2.1 WebView2 Runtime（重要）

GUI 当前正式基线不再是“系统有就用，没有就 IE11 回退”，而是：

- **bundle 内携带 Fixed Version WebView2 109**
- GUI launcher 显式把 `pywebview` 的 `WEBVIEW2_RUNTIME_PATH` 指向该目录
- 若 bundle 运行时缺失或 Chromium 初始化失败，GUI 直接报错并要求改用 TUI/CLI

原因：

- Win7/8/8.1 上 WebView2 的最后支持线是 **109**
- 现代 GUI 壳层依赖 Chromium 级能力
- IE11 / `mshtml` 不再作为完整 GUI 的可接受兜底路径

### 2.2 当前实现

当前 GUI launcher 已实现：

- bundle 根目录下自动探测 `runtime/webview2-fixed-runtime`、`runtime/webview2`、`bin/webview2-fixed-runtime` 等候选目录
- 若命中 bundle runtime，则强制 `edgechromium`
- 在 bundle 模式下，若未命中 runtime，则显式失败，不再静默回退到 IE11
- renderer report 会额外记录 `runtime_source`、`runtime_path` 与 `bundle_required`

---

## 3. 打包配置更新

### 3.1 pyproject.toml 依赖配置

建议将 GUI 依赖设为可选依赖组：

```toml
[project.optional-dependencies]
gui = [
    "pywebview>=4.0",
    "fastapi>=0.100",
    "uvicorn[standard]>=0.23",
    "websockets>=11.0",
]
```

或作为完整打包的必需依赖：

```toml
dependencies = [
    "prompt-toolkit==3.0.52",
    "rich==14.3.3",
    "pywebview>=4.0",
    "fastapi>=0.100",
    "uvicorn[standard]>=0.23",
    "websockets>=11.0",
]
```

### 3.2 静态文件打包

当前 GUI 静态资源来源已改为：

- 源码：`src/embedagent/frontend/gui/webapp/`（React + Vite）
- 产物：`src/embedagent/frontend/gui/static/`

推荐构建命令：

```powershell
cd src\embedagent\frontend\gui\webapp
npm install
npm run build
```

构建后仍按现有方式把 `static/` 打进包内。确保 GUI 静态文件被打包，需要 `MANIFEST.in`：

```
recursive-include src/embedagent/frontend/gui/static *
```

或在 `pyproject.toml` 中：

```toml
[tool.setuptools.package-data]
embedagent = [
    "frontend/gui/static/**/*",
]
```

---

## 4. Bundle 目录布局（含 GUI）

```text
EmbedAgent/
├── embedagent.cmd              # CLI 入口
├── embedagent-tui.cmd          # TUI 入口
├── embedagent-gui.cmd          # GUI 入口（新增）
├── manifests/
│   ├── bundle-manifest.json
│   ├── checksums.txt
│   └── licenses/
├── runtime/
│   ├── python/
│   ├── webview2-fixed-runtime/   # Win7 Chromium 基线（109）
│   └── site-packages/          # 包含 GUI 依赖
├── app/
│   └── embedagent/
│       └── frontend/
│           └── gui/
│               └── static/     # HTML/CSS/JS 资源
├── bin/
│   ├── git/
│   ├── rg/
│   ├── ctags/
│   └── llvm/
├── config/
└── docs/
```

### 4.1 GUI Launcher CMD

`embedagent-gui.cmd` 示例：

```batch
@echo off
setlocal EnableDelayedExpansion

set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
set "PYTHONPATH=%BUNDLE_ROOT%app;%BUNDLE_ROOT%runtime\site-packages"
set "PYTHONNOUSERSITE=1"
set "PATH=%BUNDLE_ROOT%bin\git\cmd;%BUNDLE_ROOT%bin\rg;%BUNDLE_ROOT%bin\ctags;%BUNDLE_ROOT%bin\llvm\bin;%PATH%"

set "EMBEDAGENT_HOME=%USERPROFILE%\.embedagent"

"%PYTHONHOME%\python.exe" "%BUNDLE_ROOT%app\embedagent\frontend\gui\launcher.py" %*
```

补充说明：

- GUI launcher 现在直接执行 bundle 内 `launcher.py`，避免 `runpy` / 宿主 Python 环境干扰
- `PYTHONNOUSERSITE=1` 必须保留，避免用户级 site-packages 污染 bundle 运行时
- bundle 的 `runtime/site-packages/` 中不应残留 `__editable__*.pth`

---

## 5. 打包检查清单

### 5.1 依赖检查

- [x] pywebview 及其依赖在 site-packages 中
- [x] fastapi 及其依赖在 site-packages 中
- [x] uvicorn 及其依赖在 site-packages 中
- [x] websockets 在 site-packages 中
- [x] `runtime/site-packages/` 中无 `__editable__*.pth`

### 5.2 静态文件检查

- [x] `frontend/gui/static/index.html` 在包中
- [x] `frontend/gui/static/assets/*` 在包中

### 5.3 启动检查

- [x] `embedagent-gui.cmd` 存在
- [x] GUI 能正常启动（当前环境 windowed smoke 已通过）
- [x] WebSocket 连接正常
- [x] 无窗口模式 (`--headless`) 工作

### 5.4 Win7 兼容性检查

- [ ] Win7 上能启动 bundle 内 Fixed Version WebView2 109
- [ ] `renderer_report.runtime_source == "bundle"`
- [ ] Chromium 初始化失败时，GUI 会明确提示改用 TUI/CLI

---

## 6. 与 TUI 打包的差异

| 项目 | TUI | GUI |
|------|-----|-----|
| 额外依赖 | prompt_toolkit, rich | pywebview, fastapi, uvicorn, websockets |
| 静态文件 | 无 | HTML/CSS/JS |
| 二进制依赖 | 无 | Fixed Version WebView2 109 (Win7) |
| Bundle 大小增加 | ~2MB | ~15-20MB |
| Win7 兼容性 | 原生支持 | 需要 bundle 内 Chromium 运行时 |

---

## 7. 推荐打包策略

### 7.1 单 Bundle 策略（推荐）

同时包含 TUI 和 GUI：

- 优点：用户可自行选择
- 缺点：bundle 增加约 15-20MB
- 适用：大多数场景

### 7.2 分离 Bundle 策略

- `embedagent-win7-x64-cli.zip` - 仅 CLI/TUI
- `embedagent-win7-x64-gui.zip` - 包含 GUI
- 适用：对 bundle 大小敏感的场景

---

## 8. 当前状态

| 项目 | 状态 |
|------|------|
| GUI 代码实现 | ✅ 完成 |
| GUI 依赖声明 | ✅ 已更新并完成当前环境安装验证 |
| 静态文件打包配置 | ✅ 已通过 package-data + bundle 验证 |
| GUI launcher CMD | ✅ 已创建并接入 bundle |
| Win7 WebView2 处理 | ✅ 已切换到 bundle 内 Fixed Version WebView2 基线，缺失 runtime 时显式失败 |
| Bundle 集成 | ✅ 已完成 prepare/build/validate、bundle smoke 和 bundle-local 验证入口 |

---

## 9. 下一步行动

1. **实现 diff 确认弹窗与后端联动** - 完成 GUI 编辑闭环
2. **在 Win7 执行 `validate-gui-smoke.cmd --windowed`** - 记录 `renderer_report.renderer` 与 `renderer_report.runtime_source`
3. **回填 Win7 验证结果** - 同步到 tracker / change-log / packaging 文档
