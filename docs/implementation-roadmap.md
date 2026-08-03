# Implementation Roadmap

> 状态：`active`
> 类型：`roadmap`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-03`
> 详细当前状态：`docs/current-status.md`

## Purpose

这里只保留尚未完成的项目、先后约束和退出条件。已完成阶段及其过程记录位于 `docs/archive/`。

## P0: Frontend Shell Convergence

- 让 GUI ProtocolAdapter/ClientRuntime 和 TUI TerminalRuntime 成为各自唯一 effect owner。
- 由 product composition 编译 GUI/TUI 共用的 shell descriptors，删除固定 catalog 和 fallback。
- 将核心体验收敛为 Pi 式 session、timeline、composer、interaction、command 和 status 工作面；其他能力改为可选 contribution。
- 删除双 wire shape、C/C++ 通用层展开字段、`t3/parity` 命名和旧路径。
- 仅当移除全部上层 contribution 后 GUI/TUI 仍可作为稳定最小 Agent shell 工作时退出本阶段。

## P1: Release Acceptance

- 在干净的 Windows 7 SP1 x64 环境完成窗口化 GUI 冒烟。
- 验证打包的 Fixed Version WebView2 109 和 bundle-local C smoke。
- 生成并校验与制品哈希绑定的证据。
- 仅当 `validate-release-evidence.py` 报告 `ACCEPTED` 时退出本阶段。

## P2: Real C/C++ Project Validation

- 选取有代表性的 C 与 C++ 工作区。
- 验证 recipe 发现、Clang 诊断、构建/测试、权限、恢复与离线流程。
- 在宣称真实项目验证完成前，先固定项目语料、证据格式和退出条件。

## P3: Test And CI Follow-Up

- 只关闭有可复核证据的活跃 CI 切片。
- 在现有固定测试分区稳定后，按所有者拆分大型测试资产和后续切片。

## Later: Optional Enterprise/Intranet Adapters

- 仅通过 provider、workflow package、extension 或被动 telemetry sink 接入。
- 不得成为 Agent Core 或默认离线运行的依赖。

## Sequencing Rules

- 始终保持 Python 3.8、Windows 7、离线运行和六发行包边界。
- 不重新引入已退役的兼容路径。
- 归档历史不得参与当前工作排序。
