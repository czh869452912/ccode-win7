# Implementation Roadmap

> 状态：`active`
> 类型：`roadmap`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-19`
> 详细当前状态：`docs/current-status.md`

## Purpose

这里只保留尚未完成的项目、先后约束和退出条件。已完成阶段及其过程记录位于 `docs/archive/`。

## P0: Release Acceptance

- 对 `minimal-cli`，在干净 Windows 7 SP1 x64 环境运行 staged `embedagent.cmd` gate，验证 `run`/`chat`/`sessions`、read tool、permission/user-input continuation、restore、blocked exit、bundle runtime 与计划 application identity。
- 对 `cpp-desktop`，在独立干净 Windows 7 SP1 x64 环境运行同一 staged CLI contract，并验证 Fixed Version WebView2 109 窗口化 GUI 和 bundle-local C smoke。
- 每份报告必须匹配该 flavor 的 release identity、bundle plan/Agent lock hash 与精确 gate set；不得用另一个 flavor 的证据替代。
- 仅当两个 official release flavor 各自被 `validate-release-evidence.py` 报告为 `ACCEPTED` 时退出本阶段。

## P1: Public Contract And Repository Boundary Convergence

- 依次执行 `docs/superpowers/plans/2026-08-17-public-contract-and-repository-boundary-convergence.md` 的 contract freeze、mode/profile removal、capability-driven shell、safe diagnostics 和 isolated C++ export proof。
- `agent_application_v1`、registration entry、selected distribution、runtime requirement、asset 和 gate 必须由同一份 compiled plan/lock 表达；不恢复固定 wheel 数量或隐式 C++ 注册。
- 只有 Core/Protocol/C++ isolated wheel smoke、版本化 release metadata 和 product consumption test 全部通过，才进入物理 repository split 的独立决策。
- Phase 3 的 selected closure、safe failure DTO 和 root-scope quiescent shutdown 已完成并有独立 contract/lifecycle/architecture tests；后续只补 application-scoped runtime requirement、C++ isolated wheel 和 Win7 evidence，不再扩展第二套 runtime owner。
- Phase 4 的 generic mode/profile/provider removal 已完成：Host construction 和 capability projection 只消费显式 application runtime contribution、model client 与 tool runtime，generic context 不提供默认 workspace provider 或 mode，缺失组合以 typed configuration failure 终止。后续不恢复 profile-to-runtime synthesis 或 Host-selected application/provider。

## P2: Real C/C++ Project Validation

- 选取有代表性的 C 与 C++ 工作区。
- 验证 recipe 发现、Clang 诊断、构建/测试、权限、恢复与离线流程。
- 在宣称真实项目验证完成前，先固定项目语料、证据格式和退出条件。

## P3: Test And CI Follow-Up

- 只关闭有可复核证据的活跃 CI 切片。
- frontend session-event 回归必须在共享 Python/JavaScript contract 与真实 staged launcher 路径复现；不得用 shell-local timing workaround、重试或第二个 cursor 掩盖发布边界问题。
- 在现有固定测试分区稳定后，按所有者拆分大型测试资产和后续切片。

## Later: Optional Enterprise/Intranet Adapters

- 仅通过 provider、workflow package、extension 或被动 telemetry sink 接入。
- 不得成为 Agent Core 或默认离线运行的依赖。

## Sequencing Rules

- 始终保持 Python 3.8、Windows 7、离线运行和 plan-selected distribution closure 边界。
- `-Profile` 只改变 assurance，`-Flavor` 只改变产品内容；默认 flavor 为 `minimal-cli`，C/C++ desktop 必须显式选择。
- 不重新引入已退役的兼容路径。
- 归档历史不得参与当前工作排序。
