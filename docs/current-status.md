# Current Status

> 状态：`active`
> 类型：`status`
> 负责人：`project maintainers`
> 最后验证日期：`2026-08-09`

## Release State

仓库侧发布状态为 `TARGET_READY`，`acceptance_status=PENDING_WIN7`，`publishable=false`。

## Current Focus

- 当前架构权威按 Agent Platform、上层 applications、EmbedAgent product 三个领域组织；C/C++ 只有一个应用权威。
- Agent Core 工具执行已收敛为 prepare/commit/execute：稳定 invocation identity、截断输出拦截、交互 continuation 与 started-only restore 语义均由同一个 Kernel/Loop 主链拥有；Host 隐式权限默认与 `PermissionPolicy()` 一致。
- Agent Platform 独立提取准备已成为可执行能力：Core 根包公开显式 ports 和安全默认值，`examples/standalone_agent.py` 演示同一 durable session 的运行、挂起与恢复，`core_only` wheel smoke 直接运行该示例并确认所有上层分发不可发现。
- GUI `ProtocolAdapter` / `ClientRuntime` 与 TUI `TerminalRuntime` 是各自唯一 effect owner；strict DTO path 只产出 `snake_case` version 1 bootstrap 和 canonical envelope。product composition 编译唯一 `ShellDescriptor` 供 GUI/TUI 消费，本地固定 catalog 和 fallback 已删除。
- GUI/TUI 核心体验已收敛为 session、连续 timeline、composer/mode/command、blocking interaction 和 status。terminal、source control、preview、file browser 与独立 diff 只通过可选 contribution 注册；移除全部 secondary contributions 后最小 Agent shell 仍可独立使用。
- Protocol、Host 和前端只投影 `SessionSnapshot.workflow_state`；C/C++ phase、discipline、TaskGraph 与 task 语义只由 workflow package 拥有。活动源码与文档不再使用迁移阶段命名或已删除的永久 panel/drawer 状态。
- 物理迁仓尚未开始；它需要独立仓库设计、版本与发布契约及 EmbedAgent 消费方式的单独决策，不属于已完成的提取准备。
- 在取得真实 Windows 7 证据前，保留目标机验收交接切片。

## Blockers

- 干净 Windows 7 SP1 x64 / WebView2 109 窗口化证据依赖外部目标机。
- 真实 C/C++ 项目验证尚未开始。

## Next Actions

1. 定义真实 C/C++ 项目语料、证据格式和退出条件，然后执行首轮项目验证。
2. 在环境可用后获取并验证 Windows 7 证据报告。
3. 只在现有分区出现可复核问题时继续拆分测试/CI 技术债。

## Evidence Boundary

本地测试和 bundle smoke 不能证明干净 Windows 7 验收；托管 Windows CI 也不能替代 Windows 7 / WebView2 bundle 证据。
