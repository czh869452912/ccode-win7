# Win7 GUI 验证步骤

> 更新日期：2026-03-30
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
embedagent-gui.cmd --help
validate-gui-smoke.cmd
validate-gui-smoke.cmd --windowed --auto-close-seconds 8
```

如果需要显式工作区：

```cmd
validate-gui-smoke.cmd --workspace D:\EmbedAgentWorkspace
validate-gui-smoke.cmd --workspace D:\EmbedAgentWorkspace --windowed --auto-close-seconds 8
```

---

## 4. 通过标准

### 4.1 基础启动

- `embedagent-gui.cmd --help` 返回退出码 `0`
- 不出现 `ImportError`、`ModuleNotFoundError`、`No module named fastapi/webview`

### 4.2 headless smoke

`validate-gui-smoke.cmd` 的 JSON 输出中应满足：

- `assistant_text` 包含 `GUI smoke reply`
- `session_statuses` 至少覆盖 `running`、`waiting_permission`、`waiting_user_input`、`idle`
- `tool_events` 同时包含 `tool_start` 与 `tool_finish`
- `first_session_todos == 1`
- `second_session_todos == 0`

### 4.3 windowed smoke

`validate-gui-smoke.cmd --windowed --auto-close-seconds 8` 的 JSON 输出中应满足：

- `assistant_text` 包含 `GUI smoke reply`
- `renderer_report.renderer == "edgechromium"`
- `renderer_report.runtime_source == "bundle"`

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

embedagent-gui.cmd --help：
- 退出码：
- 结果：

validate-gui-smoke.cmd：
- 退出码：
- assistant_text：
- session_statuses：
- tool_events：
- first_session_todos：
- second_session_todos：

validate-gui-smoke.cmd --windowed --auto-close-seconds 8：
- 退出码：
- assistant_text：
- renderer_report.renderer：
- renderer_report.runtime_source：
- 观察到的窗口行为：

结论：
- [ ] Win7 GUI 可用
- [ ] WebView2 路径可用
- [ ] bundle 内 Chromium 路径可用
```

---

## 6. 回填位置

- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/gui-packaging.md`
- `docs/phase6-validation.md`
