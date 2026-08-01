# Current Status

> 状态：`active`
> 类型：`status`
> 负责人：`project maintainers`
> 最后验证日期：`2026-08-01`

## Release State

仓库侧发布状态为 `TARGET_READY`，`acceptance_status=PENDING_WIN7`，`publishable=false`。

## Current Focus

- 当前架构权威按 Agent Platform、上层 applications、EmbedAgent product 三个领域组织；C/C++ 只有一个应用权威，GUI/TUI 通过通用协议注册。
- 在取得真实 Windows 7 证据前，保留目标机验收交接切片。

## Blockers

- 干净 Windows 7 SP1 x64 / WebView2 109 窗口化证据依赖外部目标机。
- 真实 C/C++ 项目验证尚未开始。

## Next Actions

1. 获取并验证 Windows 7 证据报告。
2. 定义真实 C/C++ 项目语料、证据格式和退出条件。

## Evidence Boundary

本地测试和 bundle smoke 不能证明干净 Windows 7 验收；托管 Windows CI 也不能替代 Windows 7 / WebView2 bundle 证据。
