# Current Status

> 状态：`active`
> 类型：`status`
> 负责人：`project maintainers`
> 最后验证日期：`2026-08-02`

## Release State

仓库侧发布状态为 `TARGET_READY`，`acceptance_status=PENDING_WIN7`，`publishable=false`。

## Current Focus

- 当前架构权威按 Agent Platform、上层 applications、EmbedAgent product 三个领域组织；C/C++ 只有一个应用权威，GUI/TUI 通过通用协议注册。
- Agent Core 工具执行已收敛为 prepare/commit/execute：稳定 invocation identity、截断输出拦截、交互 continuation 与 started-only restore 语义均由同一个 Kernel/Loop 主链拥有；Host 隐式权限默认与 `PermissionPolicy()` 一致。
- 下一 Agent Platform 切片是独立提取准备：用 standalone SDK 示例、隔离 wheel 验收和公共边界审计固定无 product/Host 依赖的 Core 使用方式，再评估物理迁仓。
- 在取得真实 Windows 7 证据前，保留目标机验收交接切片。

## Blockers

- 干净 Windows 7 SP1 x64 / WebView2 109 窗口化证据依赖外部目标机。
- 真实 C/C++ 项目验证尚未开始。

## Next Actions

1. 设计 Agent Platform 独立提取准备切片，固定 standalone SDK 入口、最小 ports 装配和隔离验收。
2. 获取并验证 Windows 7 证据报告。
3. 定义真实 C/C++ 项目语料、证据格式和退出条件。

## Evidence Boundary

本地测试和 bundle smoke 不能证明干净 Windows 7 验收；托管 Windows CI 也不能替代 Windows 7 / WebView2 bundle 证据。
