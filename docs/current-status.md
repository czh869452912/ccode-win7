# Current Status

> 状态：`active`
> 类型：`status`
> 负责人：`project maintainers`
> 最后验证日期：`2026-08-03`

## Release State

仓库侧发布状态为 `TARGET_READY`，`acceptance_status=PENDING_WIN7`，`publishable=false`。

## Current Focus

- 当前架构权威按 Agent Platform、上层 applications、EmbedAgent product 三个领域组织；C/C++ 只有一个应用权威。
- Agent Core 工具执行已收敛为 prepare/commit/execute：稳定 invocation identity、截断输出拦截、交互 continuation 与 started-only restore 语义均由同一个 Kernel/Loop 主链拥有；Host 隐式权限默认与 `PermissionPolicy()` 一致。
- Agent Platform 独立提取准备已成为可执行能力：Core 根包公开显式 ports 和安全默认值，`examples/standalone_agent.py` 演示同一 durable session 的运行、挂起与恢复，`core_only` wheel smoke 直接运行该示例并确认所有上层分发不可发现。
- GUI 传输主链使用 Host 原子 `event_cursor`、activation generation、buffered gap recovery 和 close-owned WebSocket lifecycle，bootstrap 与 live events 不再维护双重 cursor 或恢复入口；当前开放条件是 GUI/TUI 协议唯一入口、共享注册、最小 workbench 与应用语义隔离，TUI 仍使用固定 command/surface catalog。
- 物理迁仓尚未开始；它需要独立仓库设计、版本与发布契约及 EmbedAgent 消费方式的单独决策，不属于已完成的提取准备。
- 在取得真实 Windows 7 证据前，保留目标机验收交接切片。

## Blockers

- 干净 Windows 7 SP1 x64 / WebView2 109 窗口化证据依赖外部目标机。
- 真实 C/C++ 项目验证尚未开始。

## Next Actions

1. 完成 GUI/TUI 前端 shell 剩余收敛：协议唯一入口、共享注册、Pi 式最小体验和应用隔离。
2. 在环境可用后获取并验证 Windows 7 证据报告。
3. 定义真实 C/C++ 项目语料、证据格式和退出条件。

## Evidence Boundary

本地测试和 bundle smoke 不能证明干净 Windows 7 验收；托管 Windows CI 也不能替代 Windows 7 / WebView2 bundle 证据。
