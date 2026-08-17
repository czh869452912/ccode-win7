# Pi-Shaped Generic Agent Architecture Archive

> 状态：`archive`
> 类型：`completed and superseded architecture slice`
> 关闭日期：`2026-08-17`

本包保存 Pi 风格通用 Agent、application plugin、selected dependency closure 和通用 shell
收敛阶段的审查、设计、handoff 与实施计划。它只用于历史追溯，不承载当前实现真相。

## Contents

- `2026-08-16-pi-shaped-generic-agent-architecture-report.md`：架构审查报告。
- `2026-08-16-pi-shaped-generic-agent-architecture-design.md`：已接受的目标架构规格。
- `2026-08-16-pi-shaped-generic-agent-architecture-handoff.md`：阶段交接记录。
- `2026-08-17-generic-agent-application-plugin-closure-export.md`：application plugin 与闭包导出的实施计划。
- `2026-08-17-final-architecture-convergence.md`：本轮最终运行时组合收敛计划。

## Closed Boundary

- `ApplicationRuntimeContribution` 和显式 `registration_entry` 已成为应用运行时组合边界。
- Product 只提供通用 shell/bootstrap；C/C++ 运行时贡献由选中的 workflow plugin 提供。
- bundle plan 的 selected distribution closure 已成为导出、staging、检查和 smoke 的共同输入。
- 通用 Agent 可以在不加载 C++ workflow 的情况下构建和运行；C++ application 仍可作为显式选项加入。

## Superseded Debt

归档计划中的未完成 mode/profile、协议 capability 投影、结构化诊断和独立仓库导出事项不视为
已完成实现。它们已经从本包的执行上下文中移出，下一阶段以活动计划
`docs/superpowers/plans/2026-08-17-public-contract-and-repository-boundary-convergence.md`
为唯一执行入口。

## Current Authorities

当前行为和排序只查阅：

- `docs/overall-solution-architecture.md`
- `docs/platform/agent-core.md`
- `docs/platform/protocol.md`
- `docs/applications/cpp-workflow.md`
- `docs/product/composition.md`
- `docs/product/packaging-and-deployment.md`
- `docs/current-status.md`
- `docs/implementation-roadmap.md`
