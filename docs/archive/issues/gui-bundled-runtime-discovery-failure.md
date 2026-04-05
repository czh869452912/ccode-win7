# GUI 离线包运行时环境发现失败问题分析

## 1. 问题现象 (Summary)

使用离线打包后的 `embedagent-gui.cmd` 启动 GUI 时，前端界面显示所有 bundled 运行时均无法找到：
- `python_exe` — 未找到
- `git_exe` — 未找到
- `rg_exe` — 未找到
- `ctags_exe` — 未找到
- `llvm_root` — 未找到
- `bundle_root` — 为空

然而，这些工具实际上均已正确打包在 `build/offline-dist/embedagent-win7-x64/runtime/` 与 `bin/` 目录下。

## 2. 影响范围 (Impact)

- **前端功能**：运行时面板显示全部缺失，用户产生环境未就绪的误导。
- **命令执行**：由于 `ToolContext.build_process_env()` 不会将 bundled 工具的 `bin` 目录注入 `PATH`，所有通过 Tool 执行的命令（如 `rg`、`clang`、`git`）均无法命中 bundled 版本，只能依赖系统 PATH（若未开启 fallback 则直接报错）。
- **CLI/TUI 不受影响**：`embedagent.cmd` 与 `embedagent-tui.cmd` 遵循了正确的环境变量契约，能正常发现 bundled 运行时。

## 3. 根因分析 (Root Cause Analysis)

### 3.1 环境变量契约断裂

在离线包启动体系中，Python 运行时通过环境变量 `EMBEDAGENT_BUNDLE_ROOT` 来识别自身是否处于离线包中以及包根目录位置。

对比三个启动脚本（以及生成它们的 `prepare-offline.ps1`）：

| 启动入口 | 是否设置 `EMBEDAGENT_BUNDLE_ROOT` | 说明 |
|---------|----------------------------------|------|
| `embedagent.cmd` (CLI) | ✅ 是 | `prepare-offline.ps1:617` 显式设置 |
| `embedagent-tui.cmd` (TUI) | ✅ 间接 | 通过 `call embedagent.cmd` 继承 |
| `embedagent-gui.cmd` (GUI) | ❌ **否** | 模板与构建脚本均遗漏 |

`embedagent-gui.cmd` 仅设置了局部变量 `BUNDLE_ROOT`，未将其导出为 `EMBEDAGENT_BUNDLE_ROOT` 环境变量：

```batch
; scripts/templates/embedagent-gui.cmd (问题代码)
set "BUNDLE_ROOT=%~dp0"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
; 缺失: set "EMBEDAGENT_BUNDLE_ROOT=%BUNDLE_ROOT%"
```

### 3.2 Python 侧 bundle root 检测的双轨行为

代码库中存在**两套**不同的 bundle root 检测逻辑，它们的行为不一致：

#### A. `launcher.py` 中的 `_bundle_root()`（GUI 启动器自用）
文件：`src/embedagent/frontend/gui/launcher.py:131-138`

```python
def _bundle_root() -> str:
    env_root = os.environ.get("EMBEDAGENT_BUNDLE_ROOT", "").strip()
    if env_root:
        return os.path.realpath(env_root)
    candidate = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    return candidate
```

该函数**存在 fallback**：若环境变量未设置，会根据 `launcher.py` 的物理路径向上回溯 4 层目录推测 bundle root。因此：
- GUI 能正常启动
- WebView2 运行时发现能正常工作
- `_running_from_bundle()` 返回 True

#### B. `ToolContext.bundle_root()`（决定工具运行时路径）
文件：`src/embedagent/tools/_base.py:303-310`

```python
def bundle_root(self) -> Optional[str]:
    env_root = os.environ.get("EMBEDAGENT_BUNDLE_ROOT", "").strip()
    if not env_root:
        return None
    resolved = os.path.realpath(env_root)
    if not os.path.isdir(resolved):
        return None
    return resolved
```

该函数**没有任何 fallback**。一旦 `EMBEDAGENT_BUNDLE_ROOT` 缺失，立即返回 `None`。这是**真正的致命缺陷所在**。

### 3.3 连锁反应

`ToolContext.bundle_root()` 返回 `None` 后引发的连锁失败：

1. **`_managed_tool_candidates()`**：所有 `if bundle_root:` 条件分支被跳过，导致不会检查 `bundle_root/bin/` 与 `bundle_root/runtime/` 下的候选路径。
2. **`resolve_managed_tool_path()`**：找不到任何 bundled 工具的可执行文件。
3. **`runtime_environment_snapshot()`**：
   - `bundle_root` 为空字符串
   - 各 `*_exe` / `llvm_root` 为空字符串
   - `tool_sources` 全部为空
   - `fallback_warnings` 中可能包含 "未找到托管工具" 提示
4. **`build_process_env()`**：因 `prepend`（managed_search_path_entries）为空，不会将 bundled 工具目录注入子进程 `PATH`。
5. **`run_subprocess()` / `run_shell_tool()`**：执行如 `rg`、`clang` 等命令时无法命中 bundled 版本。

## 4. 复现步骤 (Reproduction)

1. 执行打包脚本，生成 `build/offline-dist/embedagent-win7-x64/`。
2. 确认包内 `runtime/python`、`bin/rg`、`bin/ctags`、`bin/llvm`、`bin/git` 均已存在。
3. 在项目目录下通过 PowerShell 直接调用：
   ```powershell
   D:\Claude-project\ccode-win7\build\offline-dist\embedagent-win7-x64\embedagent-gui.cmd
   ```
4. 打开 GUI 的 "运行环境" / "Inspector" 面板，观察到 `bundle_root` 为空，所有工具显示 "未找到"。

## 5. 修复建议 (Remediation)

### 5.1 短期修复（治标）

在 `embedagent-gui.cmd` 中加入与 CLI 一致的行：

```batch
set "BUNDLE_ROOT=%~dp0"
set "EMBEDAGENT_BUNDLE_ROOT=%BUNDLE_ROOT%"
set "PYTHONHOME=%BUNDLE_ROOT%runtime\python"
```

需要同时修改两处：
- `scripts/templates/embedagent-gui.cmd`（模板源）
- `scripts/prepare-offline.ps1` 中的 `$launcherGui` 变量定义段（构建脚本生成逻辑，约第 633 行附近）

### 5.2 防御性修复（治本）

`ToolContext.bundle_root()` 目前过度依赖单一环境变量，缺少 `launcher.py` 中已有的基于文件路径的 fallback。建议增加类似的 fallback 逻辑，例如：

```python
def bundle_root(self) -> Optional[str]:
    env_root = os.environ.get("EMBEDAGENT_BUNDLE_ROOT", "").strip()
    if env_root:
        resolved = os.path.realpath(env_root)
        if os.path.isdir(resolved):
            return resolved
        return None
    # Fallback: 根据 embedagent 安装位置推测 bundle root
    candidate = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    if os.path.isdir(os.path.join(candidate, "runtime")) and os.path.isdir(os.path.join(candidate, "app")):
        return candidate
    return None
```

这样可以避免因未来其他启动入口（如被外部直接以 `python -m` 调用）再次触发同类问题。

## 6. 相关代码引用 (References)

- `scripts/prepare-offline.ps1:613-623` — `$launcherCli` 正确定义
- `scripts/prepare-offline.ps1:633-655` — `$launcherGui` 遗漏 `EMBEDAGENT_BUNDLE_ROOT`
- `scripts/templates/embedagent-gui.cmd` — GUI 启动模板（缺失环境变量）
- `src/embedagent/frontend/gui/launcher.py:131-138` — `_bundle_root()`（有 fallback）
- `src/embedagent/tools/_base.py:303-310` — `ToolContext.bundle_root()`（无 fallback）
- `src/embedagent/tools/_base.py:328-355` — `_managed_tool_candidates()`（依赖 `bundle_root()`）
- `src/embedagent/tools/_base.py:424-471` — `runtime_environment_snapshot()`（汇总展示运行时状态）
- `src/embedagent/tools/_base.py:507-518` — `build_process_env()`（构建子进程环境）
