# Win7 GUI 验证步骤

> 更新日期：2026-07-19
> 适用对象：已解压的离线 bundle，在真实 Windows 7 目标机上执行

---

## 1. 目标

确认以下三件事：

- GUI launcher 在 Win7 上可启动
- `pywebview` 实际使用的是 bundle 内 `edgechromium`
- bundle 内 GUI 前后端闭环可用

---

## 2. 前置条件

- 已解压 `embedagent-win7-x64.zip`
- 已准备一个临时工作目录，例如 `D:\EmbedAgentWorkspace`
- bundle 内已包含 Fixed Version WebView2 109
- 当前口径不再接受 `mshtml` / IE11 回退作为完整 GUI 通过标准

---

## 3. 建议命令

在 bundle 根目录执行：

```cmd
EmbedAgent.exe --help
embedagent-gui.exe --help
embedagent-gui.cmd --help
validate-gui-smoke.cmd
validate-gui-smoke.cmd --windowed --auto-close-seconds 8
validate-cpp-smoke.cmd
```

如果需要显式工作区：

```cmd
validate-gui-smoke.cmd --workspace D:\EmbedAgentWorkspace
validate-gui-smoke.cmd --workspace D:\EmbedAgentWorkspace --windowed --auto-close-seconds 8
validate-cpp-smoke.cmd --workspace data\workspace-template
```

说明：`validate-gui-smoke.cmd` 默认传入 `--require-fixed-webview2`，bundle 验收必须拒绝缺失 Fixed Version WebView2 109 的 GUI 路径。`validate-cpp-smoke.cmd` 用 bundle 内 Clang 编译 bundled C smoke workspace，不能把系统 PATH 上的 clang 当作发布证明。

---

## 4. 通过标准

### 4.1 基础启动

- `EmbedAgent.exe --help` 返回退出码 `0`
- `embedagent-gui.exe --help` 返回退出码 `0`
- `embedagent-gui.cmd --help` 返回退出码 `0`
- `embedagent-gui.cmd` 仍保留为可见控制台诊断入口
- 不出现 `ImportError`、`ModuleNotFoundError`、`No module named fastapi/webview`

### 4.2 headless smoke

`validate-gui-smoke.cmd` 的 JSON 输出中应满足：

- `assistant_text` 包含 `GUI smoke reply`
- `session_statuses` 至少覆盖 `running`、`waiting_permission`、`waiting_user_input`、`idle`
- `tool_events` 同时包含 `tool_start` 与 `tool_finish`
- `command_results` 中包含 `command_name == "review"` 且 `success == true`
- `first_session_tasks == 1`
- `second_session_tasks == 0`

### 4.3 windowed smoke

`validate-gui-smoke.cmd --windowed --auto-close-seconds 8` 的 JSON 输出中应满足：

- `assistant_text` 包含 `GUI smoke reply`
- `command_results` 中包含 `command_name == "review"` 且 `success == true`
- `renderer_report.renderer == "edgechromium"`
- `renderer_report.runtime_source == "bundle"`
- `fixed_webview2.expected_runtime_major == 109`
- `fixed_webview2.exists == true`

### 4.4 C/C++ smoke

`validate-cpp-smoke.cmd` 的 JSON 输出中应满足：

- `ok == true`
- `runtime_source == "bundle"`
- `source_path` 指向 `data\workspace-template\main.c`
- `object_path` 指向 `.embedagent\smoke-build\main.obj`
- `allow_system_tool_fallback == false`

说明：

- `edgechromium` 表示 bundle 内 WebView2 Fixed Version 生效
- 若渲染器不是 `edgechromium`，当前 GUI 口径应判定为失败

---

## 5. 记录模板

请记录以下结果并回填到项目文档：

```text
验证日期：
验证机器：
Windows 版本：
bundle 是否包含 WebView2 Fixed Version 109：

EmbedAgent.exe --help：
- 退出码：
- 结果：

embedagent-gui.exe --help：
- 退出码：
- 结果：

embedagent-gui.cmd --help：
- 退出码：
- 结果：

validate-gui-smoke.cmd：
- 退出码：
- assistant_text：
- session_statuses：
- tool_events：
- first_session_tasks：
- second_session_tasks：

validate-gui-smoke.cmd --windowed --auto-close-seconds 8：
- 退出码：
- assistant_text：
- renderer_report.renderer：
- renderer_report.runtime_source：
- fixed_webview2.expected_runtime_major：
- fixed_webview2.exists：
- 观察到的窗口行为：

validate-cpp-smoke.cmd：
- 退出码：
- runtime_source：
- clang：
- object_path：

结论：
- [ ] Win7 GUI 可用
- [ ] WebView2 路径可用
- [ ] bundle 内 Chromium 路径可用
- [ ] bundle 内 Clang 可编译 C smoke workspace
```

---

## 6. 回填位置

- `docs/current-status.md`
- `docs/guides/win7-release-runbook.md`
- `docs/product/packaging-and-deployment.md`
- `docs/platform/frontend-gui.md`
---

## 7. 生成验收报告

窗口化 smoke 必须使用 `--require-fixed-webview2`，并把 `renderer == edgechromium`、`runtime_source == bundle`、WebView2 major 109 和退出码写入 `manifests\evidence\win7-evidence.json`。同时合并 `validate-cpp-smoke.cmd` 的 bundle Clang 结果，明确 `system_tool_fallback == false`。

完成后运行：

```cmd
runtime\python\python.exe tools\validation\validate-release-evidence.py --identity manifests\release-identity.json --report manifests\evidence\win7-evidence.json --json-report manifests\evidence\acceptance-report.json
```

回传结构化 JSON 和机器环境摘要即可，不回传 API key、prompt、源文件或原始工具输出。
