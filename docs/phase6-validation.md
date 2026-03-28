# Phase 6 验证说明

> 更新日期：2026-03-28
> 适用范围：Phase 6 CLI / TUI 收口与跟踪

---

## 1. 文档目标

把 Phase 6 的验证口径固定下来，避免“功能看起来差不多可用，但没有统一验法”的状态。

当前 Phase 6 的完成判定分两层：

- 自动化验证：脚本可重复执行
- 手工验证：真实控制台里交互检查

---

## 2. 自动化验证

统一入口：

```powershell
.venv\Scripts\python.exe scriptsalidate-phase6.py
```

脚本当前覆盖：

- `InProcessAdapter` 会话创建、消息提交、事件流与 `set_session_mode`
- `--tui` 在非控制台宿主里的优雅报错
- `EMBEDAGENT_TUI_HEADLESS=1` 下的真实 `prompt_toolkit` 事件循环

通过标准：

- 输出包含 `result PASS`
- 进程退出码为 `0`

---

## 3. 手工验证

由于当前宿主不是标准 Windows console，仍需在真实控制台里做一轮手工验证。

推荐终端：

- `cmd.exe`
- Windows Terminal
- 任何支持控制台缓冲区的 Windows 终端

建议命令：

```powershell
.venv\Scripts\embedagent.exe --model fake-model --tui
```

或使用真实模型：

```powershell
.venv\Scripts\embedagent.exe --base-url http://127.0.0.1:8000/v1 --model <model> --tui
```

检查点：

1. TUI 能正常进入全屏，不报控制台错误。
2. `F2` 可新建会话，`F3` 可恢复最近会话。
3. `F4` 能打开会话列表，方向键可移动，`F5` 可恢复选中会话。
4. 输入普通消息后，Transcript 会出现 `assistant / tool / context` 事件。
5. 触发权限确认时，底部提示会切到 `confirm(y/n)>`。
6. `/snapshot` 和 `/help` 侧栏可正常打开。

---

## 4. 当前结论

截至 2026-03-28，Phase 6 已具备：

- adapter 驱动 CLI
- 最小 TUI
- 自动化验证脚本
- 非控制台宿主保护
- headless 真实事件循环验证

当前未完成的收口项只剩：

- 真实控制台手工验证
- 如有必要，再补一份更贴近交付物的 TUI 使用说明
