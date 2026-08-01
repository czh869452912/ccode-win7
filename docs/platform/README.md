# Agent Platform

> 状态：`active`
> 类型：`domain index`
> 负责人：`Agent platform maintainers`

`docs/platform/` 记录可独立复用的 Agent 底座当前真相。它不假设 C/C++、EmbedAgent 产品壳或某一种前端实现。

| 意图 | 权威文档 |
|---|---|
| Agent 公开 SDK 与转轮内核 | `docs/platform/agent-core.md` |
| 持久会话、交易与唯一历史真相 | `docs/platform/session-runtime.md` |
| 工具、扩展与运行时目录 | `docs/platform/tools-and-extensions.md`, `docs/platform/tool-contracts.md` |
| 权限、路径守卫与上下文 | `docs/platform/permissions-and-context.md`, `docs/platform/permission-model.md` |
| Core/Host 和 Host/UI 协议 | `docs/platform/protocol.md`, `docs/platform/frontend-protocol.md` |
| 可注册 GUI/TUI 交互层 | `docs/platform/frontend-gui.md`, `docs/platform/frontend-tui.md` |
| 通用模式契约与独立底座方向 | `docs/platform/mode-contract.md`, `docs/platform/agent-platform-blueprint.md` |

上层工作流只能通过平台公开契约参与。平台文档不得枚举某个应用的工具名、任务状态或交付规则。
