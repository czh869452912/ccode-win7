# TUI Frontend

## Metadata

> 状态：`active`
> 类型：`platform implementation`
> 负责人：`TUI maintainers`
> 最后同步日期：`2026-08-09`
> 对应代码范围：`src/embedagent/frontend/tui/`

## 1. Purpose And Boundary

TUI 是公开 Hosted Session 边界之上的终端 shell 实现，使用 `prompt_toolkit` 和 `rich` 提供键盘优先、低颜色可回退的最小 Agent 体验。`TerminalRuntime` 将 `HostedSessionHost` 公开方法适配为与 GUI 相同的 canonical bootstrap/envelope 语义；TUI 与 GUI 消费同一个 product-compiled `ShellDescriptor`，不维护本地产品 catalog。

## 2. Architecture

| Component | Ownership |
|---|---|
| `launcher.py`, `bootstrap.py` | 接收产品组合与公开 `HostedSessionHost`，创建 `TerminalRuntime` 并启动 terminal app |
| `runtime.py` | 唯一 Host/effect owner；session activation、bootstrap cursor、event buffering/gap recovery、interaction/session/workspace calls 和 close |
| `app.py` | `TerminalApp` 生命周期、runtime action binding 和组件容器 |
| `frontend_adapter.py` | `TUIFrontend` 将 canonical `SessionEventEnvelope` 投影到 reducer |
| `controller.py`, `commands.py`, `shell_state.py` | 用户输入、runtime action dispatch 和 descriptor-backed command/keybinding 投影 |
| `state.py`, `reducer.py` | 可丢失终端投影与纯状态转换 |
| `layout.py`, `views/` | header、timeline、composer、status 四区布局及 command/interaction overlays |
| `contributions.py` | 已注册 secondary surface 的 renderer-key 映射；不拥有 capability policy |

```mermaid
flowchart LR
    P["product composition"] --> B["TUI bootstrap"]
    B --> H["HostedSessionHost"]
    H --> T["TerminalRuntime"]
    T -->|runtime actions| F["TUIFrontend / controller"]
    F --> R["pure reducer"]
    R --> S["TerminalState"]
    S --> V["capability-driven views"]
```

## 3. Registration And Event Handling

`run_tui()` 构造一个 `TerminalRuntime(session_host, dispatch=...)`，再把 runtime action dispatcher 单次绑定到 `TerminalController`。session create/resume/submit 只把 `TerminalRuntime.on_session_event(envelope)` 注册给 Host；TUI 不再暴露三参数 event callback，也不读取 `session_host.adapter`。

`TerminalRuntime` 在 session 启动或切换前建立新 generation，缓冲 bootstrap 期间的 live envelopes，以 Host `event_cursor` 安装 projection，并只释放连续事件；sequence gap 通过同一 bootstrap 路径恢复。`TUIFrontend.on_session_event(...)` 只消费 runtime 转发的 canonical envelope，根据 event kind 更新 timeline、snapshot、context diagnostics 和 pending interaction。

bootstrap history 替换 terminal projection；terminal buffer 不是可恢复 transcript。close 后 runtime 拒绝新操作并忽略晚到事件。

## 4. Minimal Shell And Contributions

TUI 固定核心只有 header、scrollable timeline、replaceable composer/interaction region 和一行 status。command palette 与 blocking interaction 以 overlay 出现。`TerminalState` 从 `ShellDescriptor` 初始化命令、快捷键和已注册的 secondary contributions；空 descriptor 不创建 explorer、editor、inspector、terminal、source-control、task 或 preview 状态。

secondary contribution 通过 `ContributionState` 和 renderer registry 覆盖显示，不占用永久宽度或高度。删除 descriptor 会同时删除其命令、快捷键、状态和视图。raw console 或低颜色 host 下必须保持核心操作可用；终端支持差异是 presentation fallback，不是第二套产品能力。

## 5. State And Interactions

`TerminalState` 只保存 session、timeline、composer、status、overlay、descriptor-backed shell state 和按 id 注册的 contribution state。permission/user-input response 通过 `TerminalRuntime.respond_to_interaction(...)` 提交，仅在 resolved event 或后续 bootstrap/snapshot 到达后清除 pending state。

reducer 保持纯函数，不导入 Host 对象、执行工具或修改权限规则。

## 6. Verification

- `tests/test_architecture.py`
- `tests/test_terminal_frontend.py`
- `tests/test_tui_activity_timeline.py`
- `tests/test_tui_runtime.py`
- `tests/test_session_truth_boundaries.py`
- `tests/test_session_event_protocol.py`

## 7. Related Documents

- `docs/platform/frontend-protocol.md`
- `docs/platform/protocol.md`
- `docs/platform/frontend-gui.md`
- `docs/product/composition.md`
