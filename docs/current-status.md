# Current Status

> 状态：`active`
> 类型：`status`
> 负责人：`project maintainers`
> 最后验证日期：`2026-08-17`

## Release State

仓库侧两个官方 release flavor 均保持 `acceptance_status=PENDING_WIN7`、`publishable=false`。本地仓库门禁只能产生 plan-bound candidate；每个 flavor 只有在各自 clean-machine Windows 7 报告通过 evidence validator 后才可成为 `ACCEPTED`。

## Current Focus

- 当前架构权威按 Agent Platform、上层 applications、EmbedAgent product 三个领域组织；C/C++ 只有一个应用权威。
- application runtime 已收敛为 Core 的 `ApplicationRuntimeContribution` 与显式 `registration_entry`：generic product registration 只提供通用 runtime/shell，C/C++ profile、runtime definition、workspace detectors、workflow package id 和 shell/extension contributions 只由选中的 workflow plugin 提供。Host 只把贡献适配成内部 registry record，bundle plan 不再通过产品内置 C/C++ record 推断运行时能力。
- 产品打包已从固定 full bundle 收敛为 official recipe -> immutable bundle plan -> export/stage/validate/identity/evidence/runtime policy 单链。`minimal-cli` 只激活 `embedagent.generic` 与 CLI，并投影 Core/Protocol/Host/Shell 的 selected closure；`cpp-desktop` 才加入 `embedagent-workflow-cpp` 与 C++/desktop closure。composition compiler 是 build-time 工具，不是默认运行时依赖。
- `-Profile` 与 `-Flavor` 已正交：dev 不创建 zip、只执行静态检查并保持 `DEV_ONLY`；release 创建 zip 并运行 plan-selected gates。两个 release flavor 共用真实 staged `embedagent.cmd` gate，覆盖 `run`/`chat`/`sessions`、工具、permission/user-input、resume 与 blocked exit；desktop 另有 C++/GUI gates。application 和 shell override 在 bundle 中按计划 fail closed。
- Agent Core 工具执行已收敛为 prepare/commit/execute：稳定 invocation identity、截断输出拦截、交互 continuation 与 started-only restore 语义均由同一个 Kernel/Loop 主链拥有；Host 隐式权限默认与 `PermissionPolicy()` 一致。
- Agent Platform 独立提取准备已成为可执行能力：Core 根包公开显式 ports 和安全默认值，`examples/standalone_agent.py` 演示同一 durable session 的运行、挂起与恢复，`core_only` wheel smoke 直接运行该示例并确认所有上层分发不可发现。
- Protocol 公开聚焦 `FrontendSessionPort`、`FrontendWorkspacePort` 与 `SessionEventSink`；Host 只提供进程内实现并在构造时绑定一个 canonical envelope sink，不再暴露 aggregate frontend facade、per-call handler 或 resolver callback。
- CLI 与 TUI 共用 Python `SessionClientRuntime`；GUI 使用 browser-only JavaScript `SessionClientRuntime`。两种实现通过同一 JSON fixture 验证 activation、returned-bootstrap transaction、cursor、recovery、interaction、terminal evidence、generation、close、reentrant dispatch 和 sink failure。每端只保留一个 sync phase 与 ordered event queue；runtime action 成功投递后才提交 cursor/lifecycle/terminal，投递失败不推进 event 并使 generation fail closed。Host bound sink failure 向发布调用者传播，不再静默丢失。controller 不拥有 bootstrap 安装，frontend runtime 不拥有 durable session truth。
- CLI 只有显式 `chat`、`run` 和 `sessions` grammar。`run` 提供稳定 text/JSON result 与 `0/2/3/4/130` exit contract，遇到交互只返回 blocked；CLI 不转发 TUI/GUI，不保留常驻 Agent 状态，也不导入其他 shell。
- strict DTO path 只产出 `snake_case` version 1 bootstrap 和 canonical envelope。product composition 编译唯一 `ShellDescriptor` 供 CLI/TUI/GUI 消费，本地固定 catalog、fallback 和 frontend translation layer 已删除。
- 所有 shell 使用同一个产品 launch-config composition：built-in < `~/.embedagent/config.json` < workspace config < `EMBEDAGENT_*` < explicit shell arguments。launcher 不自行加载 config。
- GUI/TUI 核心体验已收敛为 session、连续 timeline、composer/mode/command、blocking interaction 和 status。terminal、source control、preview、file browser 与独立 diff 只通过可选 contribution 注册；移除全部 secondary contributions 后最小 Agent shell 仍可独立使用。
- Protocol、Host 和前端只投影 `SessionSnapshot.workflow_state`；C/C++ phase、discipline、TaskGraph 与 task 语义只由 workflow package 拥有。活动源码与文档不再使用迁移阶段命名或已删除的永久 panel/drawer 状态。
- 物理迁仓尚未开始；它需要独立仓库设计、版本与发布契约及 EmbedAgent 消费方式的单独决策，不属于已完成的提取准备。
- 在分别取得两个 official release flavor 的真实 Windows 7 证据前，保留目标机验收交接切片。

## Blockers

- `minimal-cli` 的干净 Windows 7 SP1 x64 bundle-local CLI smoke 证据依赖外部目标机。
- `cpp-desktop` 的干净 Windows 7 SP1 x64 / WebView2 109 窗口化与 bundle-local C smoke 证据依赖外部目标机。
- 真实 C/C++ 项目验证尚未开始。

## Next Actions

1. 按 `docs/superpowers/plans/2026-08-17-public-contract-and-repository-boundary-convergence.md` 的顺序冻结 application contract，并移除 Core/Host 的 mode/profile 与隐式 provider 债务。
2. 让 Protocol、CLI、TUI、GUI 只消费 selected capability projection，再完成安全诊断 DTO 与 application-scoped runtime requirement 校验。
3. 对 `cpp-desktop` 执行 Core/Protocol/C++ isolated wheel proof；只有公共契约、版本化 lock 和独立 smoke 全部通过后，才评估物理拆库。
4. 并行保留 `minimal-cli`/`cpp-desktop` 的 Windows 7 目标机证据和真实 C/C++ 项目验证，不以本地 smoke 替代交付验收。

## Evidence Boundary

本地测试和 bundle smoke 不能证明干净 Windows 7 验收；托管 Windows CI 也不能替代 Windows 7 / WebView2 bundle 证据。
