# Phase 6 验证说明

> 更新日期：2026-03-29
> 适用范围：Phase 6 CLI / TUI 收口与跟踪

---

## 1. 文档目标

把当前 Phase 6 的验证口径固定下来，避免“代码已经模块化了，但验证口径还停留在旧单文件原型”这种脱节状态。

当前 Phase 6 的完成判定分三层：

- 自动化验证：脚本可重复执行
- 单元测试：adapter / timeline / terminal frontend 模块可回归
- 手工验证：真实控制台与 Win7 宿主里的交互检查

---

## 2. 自动化验证

统一入口：

```powershell
.venv\Scripts\python.exe scripts\validate-phase6.py
```

脚本当前覆盖：

- `InProcessAdapter` 会话创建、消息提交、事件流与 `set_session_mode`
- `--tui` 在非控制台宿主里的优雅报错
- `EMBEDAGENT_TUI_HEADLESS=1` 下的真实终端前端事件循环
- `embedagent.tui` 兼容入口仍可工作

通过标准：

- 输出包含 `result PASS`
- 进程退出码为 `0`

说明：

- 非控制台宿主保护仍会向 stderr 输出一行错误提示，这属于预期行为，不影响脚本通过。

---

## 3. 单元测试

当前终端前端相关回归已纳入 `unittest discover -s tests`，新增重点包括：

- `tests/test_session_timeline.py`
  - `SessionTimelineStore` 事件持久化、trim 和最近 assistant 回复提取
- `tests/test_inprocess_adapter_frontend_api.py`
  - workspace / file / timeline / artifact / todo 前端接口
- `tests/test_terminal_frontend.py`
  - slash、`@文件`、artifact、session 补全

统一回归命令：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

---

## 4. 手工验证

由于当前宿主不是标准 Windows console，仍需在真实控制台里做一轮手工验证。

推荐宿主：

- `cmd.exe`
- Win7 下 bundled `ConEmu`
- 其他支持控制台缓冲区的 Windows 终端

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
2. Header 能显示 session / mode / status / host / git 概况。
3. `F2` 可新建会话，`F3` 可恢复最近会话。
4. `F4` 能切到会话 explorer，`F5` 可激活选中项。
5. 输入普通消息后，Timeline 会出现 `assistant / tool / context` 事件。
6. 触发权限确认时，底部提示会切到 `confirm(y/n)>`。
7. `/workspace`、`/open`、`/edit`、`/artifacts`、`/save` 等命令可工作。
8. `@文件` 补全和 slash command 补全可触发。
9. 单缓冲编辑器可打开、修改并保存文件。
10. 在 explorer 手动浏览后，滚动不会被每次刷新强制拉回底部。

---

## 5. 当前结论

截至 2026-03-29，Phase 6 已具备：

- adapter 驱动 CLI
- 模块化终端前端包 `src/embedagent/frontends/terminal/`
- `embedagent.tui` 兼容 shim
- workspace / timeline / artifact / todo 浏览接口
- `SessionTimelineStore`
- 自动化验证脚本
- headless 真实事件循环验证
- 新增单元测试覆盖前端关键模块

当前未完成的收口项仍然是：

- 真实控制台手工验证
- Win7 / ConEmu 下的真实体验检查
- 继续细化 explorer / editor / plan 交互
