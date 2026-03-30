# EmbedAgent GUI 打包配置指南

> 更新日期：2026-03-30
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

GUI 前端基于 `pywebview`，在 Windows 上需要 WebView2 Runtime：

| 环境 | 行为 |
|------|------|
| Windows 10/11 | 系统自带 WebView2 Runtime |
| Windows 7/8 | **需要额外安装** Evergreen Standalone Installer |

**Win7 打包选项**：

1. **方案 A（推荐）**：在 Win7 目标机上预装 WebView2 Runtime
   - 下载：[Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
   - 选择 "Evergreen Standalone Installer"
   - 大小：约 130MB

2. **方案 B**：使用 IE11 回退模式
   - pywebview 会自动检测 WebView2 是否可用
   - 不可用时自动回退到 IE11
   - 体验降级但可运行

3. **方案 C（bundle 内携带）**
   - 将 WebView2 Runtime 固定版本放入 bundle
   - 首次运行时静默安装
   - 增加约 130MB bundle 大小

### 2.2 当前实现

当前 GUI launcher 已实现 IE11 回退：

```python
# 尝试使用 Edge Chromium（如果安装了 WebView2）
if sys.platform == "win32":
    try:
        import webview.platforms.winforms
        webview.platforms.winforms.BUILTIN_BROWSER = 'edgechromium'
        _LOGGER.info("Using Edge Chromium (WebView2)")
    except:
        _LOGGER.info("Using default browser (IE11)")
```

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

确保 GUI 静态文件被打包，需要 `MANIFEST.in`：

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
set "PATH=%BUNDLE_ROOT%bin\git\cmd;%BUNDLE_ROOT%bin\rg;%BUNDLE_ROOT%bin\ctags;%BUNDLE_ROOT%bin\llvm\bin;%PATH%"

set "EMBEDAGENT_HOME=%USERPROFILE%\.embedagent"

"%PYTHONHOME%\python.exe" -m embedagent.frontend.gui.launcher %*
```

---

## 5. 打包检查清单

### 5.1 依赖检查

- [x] pywebview 及其依赖在 site-packages 中
- [x] fastapi 及其依赖在 site-packages 中
- [x] uvicorn 及其依赖在 site-packages 中
- [x] websockets 在 site-packages 中

### 5.2 静态文件检查

- [x] `frontend/gui/static/index.html` 在包中
- [x] `frontend/gui/static/css/style.css` 在包中
- [x] `frontend/gui/static/js/app.js` 在包中

### 5.3 启动检查

- [x] `embedagent-gui.cmd` 存在
- [ ] GUI 能正常启动（至少显示窗口）
- [x] WebSocket 连接正常
- [x] 无窗口模式 (`--headless`) 工作

### 5.4 Win7 兼容性检查

- [ ] Win7 上能启动（使用 IE11 回退）
- [ ] 或 WebView2 Runtime 已安装

---

## 6. 与 TUI 打包的差异

| 项目 | TUI | GUI |
|------|-----|-----|
| 额外依赖 | prompt_toolkit, rich | pywebview, fastapi, uvicorn, websockets |
| 静态文件 | 无 | HTML/CSS/JS |
| 二进制依赖 | 无 | WebView2 Runtime (Win7) |
| Bundle 大小增加 | ~2MB | ~15-20MB |
| Win7 兼容性 | 原生支持 | 需要 WebView2 或 IE11 回退 |

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
| Win7 WebView2 处理 | ✅ IE11 回退已实现 |
| Bundle 集成 | ✅ 已完成 prepare/build/validate 与 bundle smoke |

---

## 9. 下一步行动

1. **实现 diff 确认弹窗与后端联动** - 完成 GUI 编辑闭环
2. **补充窗口模式 smoke** - 验证实际桌面窗口可交互
3. **验证 Win7 兼容性** - 测试 IE11 / MSHTML 回退模式
