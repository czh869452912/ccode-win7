# Win7 GUI 验证步骤

> 更新日期：2026-03-30
> 适用对象：已解压的离线 bundle，在真实 Windows 7 目标机上执行

---

## 1. 目标

确认以下三件事：

- GUI launcher 在 Win7 上可启动
- `pywebview` 实际使用的渲染器是 `edgechromium` 或 `mshtml`
- bundle 内 GUI 前后端闭环可用

---

## 2. 前置条件

- 已解压 `embedagent-win7-x64.zip`
- 已准备一个临时工作目录，例如 `D:\EmbedAgentWorkspace`
- 若目标机已安装 WebView2 Runtime，优先验证 `edgechromium`
- 若目标机未安装 WebView2 Runtime，验证 `mshtml` / IE11 回退

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

- `assistant_text` 为 `GUI smoke reply`
- `model_requests` 为 `1`
- `session_statuses` 包含 `idle`

### 4.3 windowed smoke

`validate-gui-smoke.cmd --windowed --auto-close-seconds 8` 的 JSON 输出中应满足：

- `assistant_text` 为 `GUI smoke reply`
- `renderer_report.renderer` 为 `edgechromium` 或 `mshtml`

说明：

- `edgechromium` 表示 WebView2 生效
- `mshtml` 表示 IE11 / MSHTML 回退生效

---

## 5. 记录模板

请记录以下结果并回填到项目文档：

```text
验证日期：
验证机器：
Windows 版本：
是否安装 WebView2：

embedagent-gui.cmd --help：
- 退出码：
- 结果：

validate-gui-smoke.cmd：
- 退出码：
- assistant_text：
- session_statuses：

validate-gui-smoke.cmd --windowed --auto-close-seconds 8：
- 退出码：
- assistant_text：
- renderer_report.renderer：
- 观察到的窗口行为：

结论：
- [ ] Win7 GUI 可用
- [ ] WebView2 路径可用
- [ ] IE11 / MSHTML 回退可用
```

---

## 6. 回填位置

- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/gui-packaging.md`
- `docs/phase6-validation.md`
