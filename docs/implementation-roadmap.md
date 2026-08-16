# Implementation Roadmap

> 状态：`active`
> 类型：`roadmap`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-16`
> 详细当前状态：`docs/current-status.md`

## Purpose

这里只保留尚未完成的项目、先后约束和退出条件。已完成阶段及其过程记录位于 `docs/archive/`。

## P0: Release Acceptance

- 对 `minimal-cli`，在干净 Windows 7 SP1 x64 环境运行 staged `embedagent.cmd` gate，验证 `run`/`chat`/`sessions`、read tool、permission/user-input continuation、restore、blocked exit、bundle runtime 与计划 application identity。
- 对 `cpp-desktop`，在独立干净 Windows 7 SP1 x64 环境运行同一 staged CLI contract，并验证 Fixed Version WebView2 109 窗口化 GUI 和 bundle-local C smoke。
- 每份报告必须匹配该 flavor 的 release identity、bundle plan/Agent lock hash 与精确 gate set；不得用另一个 flavor 的证据替代。
- 仅当两个 official release flavor 各自被 `validate-release-evidence.py` 报告为 `ACCEPTED` 时退出本阶段。

## P1: Real C/C++ Project Validation

- 选取有代表性的 C 与 C++ 工作区。
- 验证 recipe 发现、Clang 诊断、构建/测试、权限、恢复与离线流程。
- 在宣称真实项目验证完成前，先固定项目语料、证据格式和退出条件。

## P2: Test And CI Follow-Up

- 只关闭有可复核证据的活跃 CI 切片。
- frontend session-event 回归必须在共享 Python/JavaScript contract 与真实 staged launcher 路径复现；不得用 shell-local timing workaround、重试或第二个 cursor 掩盖发布边界问题。
- 在现有固定测试分区稳定后，按所有者拆分大型测试资产和后续切片。

## Later: Optional Enterprise/Intranet Adapters

- 仅通过 provider、workflow package、extension 或被动 telemetry sink 接入。
- 不得成为 Agent Core 或默认离线运行的依赖。

## Sequencing Rules

- 始终保持 Python 3.8、Windows 7、离线运行和六发行包边界。
- `-Profile` 只改变 assurance，`-Flavor` 只改变产品内容；默认 flavor 保持 `cpp-desktop`。
- 不重新引入已退役的兼容路径。
- 归档历史不得参与当前工作排序。
