# EmbedAgent Win7 部署前检查清单

> 更新日期：2026-06-25
> 适用阶段：Phase 7 目标机验收

---

## 1. 文档目标

本清单用于在 Windows 7 目标机上执行部署前和首次运行前检查，确保离线 bundle 真正满足：

- 目标机只需 Windows 7
- 无需预装 Python / Git / LLVM / Node / Docker
- 解压后可直接运行

本清单默认对应 `docs/modules/packaging-and-deployment.md` 中定义的 portable bundle 布局。

---

## 2. 目标机前提

### 2.1 操作系统

- Windows 7 SP1
- 优先以 x64 为首个交付目标
- 本地用户具备在目标目录解压和写入文件的权限

### 2.2 推荐宿主环境

- `cmd.exe`
- ConEmu
- 其他支持标准控制台缓冲区的 Windows 终端

### 2.3 内网模型前提

若现场需要连接内网模型服务，还需要确认：

- 目标机到模型服务地址可达
- `base_url`、`api_key`、`model` 已准备好
- 模型服务协议与当前 OpenAI-compatible adapter 兼容

---

## 3. 部署前静态检查

在把 bundle 复制到目标机前，先在构建机确认：

1. zip 包可以完整解压。
2. `manifests/bundle-manifest.json` 存在。
3. `manifests/checksums.txt` 存在。
4. `runtime/python/python.exe` 存在。
5. `runtime/site-packages/` 存在。
6. `app/embedagent/` 存在。
7. `bin/git/`、`bin/rg/`、`bin/ctags/`、`bin/llvm/` 存在。
8. `config/config.json` 与 `config/permission-rules.json` 模板存在。
9. 构建机已运行 `scripts/validate-offline-bundle.ps1 -RequireComplete`，并确认报告中的 `runtime_contract.schema_version == 1`。
10. 构建机已运行 `scripts/check-bundle-dependencies.py <bundle-root>`，并确认 External Tools / Release Gates / runtime contract 检查通过。
11. release profile 不得依赖系统 PATH 兜底：`scripts/offline-runtime-contract.json` 中的 `release_gates` 必须保持 `allow_system_tool_fallback: false`。

---

## 4. 目标机首次解压检查

把 bundle 解压到目标机后，先确认：

1. 解压路径不包含需要管理员权限的系统目录。
2. 解压路径可读可写。
3. bundle 根目录下的 launcher 可见：
   - `embedagent.cmd`
   - `embedagent-tui.cmd`
   - `validate-cpp-smoke.cmd`
   - `validate-gui-smoke.cmd`
4. `runtime/python/` 下的 Python 文件完整存在。
5. `bin/llvm/bin/`、`bin/git/`、`bin/rg/`、`bin/ctags/` 下的可执行文件存在。
6. `bin/llvm/bin/clang.exe`、`clang++.exe`、`clang-cl.exe`、`clang-tidy.exe`、`clang-analyzer.bat`、`llvm-profdata.exe`、`llvm-cov.exe` 均存在。

---

## 5. 目标机命令级检查

以下命令为**计划中的目标机验收命令**，假定 Phase 7 bundle 已按设计完成：

```powershell
embedagent.cmd --help
embedagent.cmd --list-sessions --workspace .\workspace-smoke
bin\llvm\bin\clang.exe --version
bin\llvm\bin\clang++.exe --version
bin\llvm\bin\clang-cl.exe --version
bin\llvm\bin\clang-tidy.exe --version
bin\llvm\bin\llvm-profdata.exe --version
bin\llvm\bin\llvm-cov.exe --version
bin\rg\rg.exe --version
bin\ctags\ctags.exe --version
validate-cpp-smoke.cmd
```

若 MinGit 目录采用 `cmd\git.exe` 布局，则增加：

```powershell
bin\git\cmd\git.exe --version
```

检查目标：

- CLI 可以启动，不报缺少 Python 或模块导入错误。
- 每个 bundle 内带动态检查的工具都能独立输出版本号。
- `clang-analyzer.bat` 存在且路径与 `scripts/offline-runtime-contract.json` 一致。
- `validate-cpp-smoke.cmd` 使用 bundle 内 `bin\llvm\bin\clang.exe` 编译 `data\workspace-template\main.c`，并在 `manifests\cpp-smoke-report.json` 记录 `runtime_source == "bundle"`。
- launcher 已正确设置 PATH，不依赖系统环境。

---

## 6. Win7 兼容性专项检查

### 6.1 运行库与补丁

重点核对：

- 是否满足 Python 3.8 在 Win7 上的前置补丁要求
- bundle 是否已随带需要的 CRT / UCRT 本地 DLL
- 不依赖目标机额外安装 VC++ Runtime

### 6.2 控制台宿主

重点核对：

1. `embedagent.cmd` 可正常进入普通 CLI。
2. `embedagent-tui.cmd` 在目标宿主下可进入 TUI。
3. 若 TUI 因宿主不兼容失败，报错信息应清晰、可诊断。

### 6.3 文件与目录写入

重点核对：

- 工作区目录可创建 `.embedagent/`
- 会话摘要、artifact、todo、project memory 可落盘
- 不需要管理员权限即可写入当前工作区

---

## 7. 首轮人工验收清单

| 检查项 | 通过标准 |
|------|----------|
| CLI 启动 | `embedagent.cmd --help` 正常返回 |
| 会话目录创建 | 运行后可生成 `.embedagent/` |
| Python 依赖加载 | 无 `ImportError` / `ModuleNotFoundError` |
| LLVM/Clang 可见 | `clang.exe --version` 可运行 |
| C smoke workspace | `validate-cpp-smoke.cmd` 返回 `0` 且报告 runtime_source 为 `bundle` |
| Git 可见 | `git.exe --version` 可运行 |
| 搜索工具可见 | `rg.exe` / `ctags.exe` 可运行 |
| TUI 启动 | 在支持宿主下进入全屏或给出清晰错误 |
| 配置可覆盖 | 可通过模板配置或项目级 `.embedagent/config.json` 调整 |

---

## 8. 验收记录模板

建议每次目标机验收至少记录：

| 字段 | 示例 |
|------|------|
| 验收日期 | `2026-03-29` |
| 机器标识 | `win7-sp1-x64-vm01` |
| bundle 版本 | `embedagent-win7-x64-20260329` |
| 操作人 | `tester-a` |
| 控制台宿主 | `cmd.exe` / `ConEmu` |
| C smoke 结果 | `validate-cpp-smoke.cmd pass/fail` |
| GUI smoke 结果 | `validate-gui-smoke.cmd pass/fail` |
| 结果 | `pass` / `fail` |
| 备注 | `TUI 正常 / 缺少 DLL / 模型地址不可达` |

---

## 9. 当前结论

Phase 7 的目标机验收不应该从“现场试试看能不能跑”开始，而应该按固定清单逐项核对：

- bundle 完整性
- Python 与外部工具存在性
- C/C++ smoke workspace 能由 bundle 内 Clang 编译
- Win7 运行库与控制台宿主条件
- CLI/TUI 的首次启动表现

只有这样，Phase 7 才能证明“离线交付”不是开发机偶然可运行，而是可复制、可审计、可验收的正式交付能力。
---

## 10. Phase 7 结构化证据回传

目标机验收必须返回与当前 release identity 绑定的 `win7-evidence.json`。报告至少包含 Windows 7 SP1 AMD64、WebView2 109 bundle runtime、`edgechromium` windowed smoke、bundle Clang C smoke、命令退出码以及空的 `blocking_errors`。

在 bundle 根目录使用 bundle 内 Python 离线验证：

```cmd
runtime\python\python.exe tools\validation\validate-release-evidence.py --identity manifests\release-identity.json --report manifests\evidence\win7-evidence.json --json-report manifests\evidence\acceptance-report.json
```

只有 `acceptance-report.json` 的 `status` 为 `ACCEPTED` 才能形成 Win7 交付结论。构建机或 Windows 10 上的同类结果只能作为诊断，不能替代真实 Win7 SP1 x64 证据。
