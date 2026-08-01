# Documentation Map

> 状态：`active`
> 类型：`navigation`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`

本页是唯一的全局文档地图。先按意图选择一条路径，再打开拥有该行为的模块、契约或工作流文档；不要把入口文件、临时切片或历史材料当作实现说明书。

| I need to... | Read first | Then read | Do not use as current truth |
|---|---|---|---|
| 了解系统拓扑、六发行包边界和依赖方向 | `docs/overall-solution-architecture.md` | `docs/references/code-doc-matrix.md` | 根 `README.md` 的概览、归档架构方案 |
| 修改 Agent Core 或 durable session runtime | `docs/modules/agent-core.md` | `docs/modules/session-runtime.md` | 历史 phase/spec、旧 tracker |
| 修改 C/C++ workflow、harness 或任务投影 | `docs/modules/harness.md` | `docs/agent-harness-v2.md`, `docs/mode-schema.md` | Core 入口文档、历史 harness 计划 |
| 修改工具注册、激活、执行或展示元数据 | `docs/modules/tools-and-tooling.md` | `docs/tool-contracts.md` | mode 列表、renderer 内的工具名分支 |
| 修改权限、写路径或上下文组装 | `docs/modules/permissions-and-context.md` | `docs/permission-model.md` | 工具执行结果、产品默认值推测 |
| 修改 Host/Core DTO 或跨壳层协议 | `docs/modules/protocol-and-core.md` | `docs/frontend-protocol.md` | GUI 局部状态、历史 transport 方案 |
| 修改 GUI 或 TUI 壳层 | `docs/modules/frontend-gui.md`, `docs/modules/frontend-tui.md` | `docs/frontend-protocol.md` | renderer 自造默认值、历史 parity ledger |
| 修改打包、离线资产或 Win7 发布验收 | `docs/modules/packaging-and-deployment.md` | `docs/guides/win7-release-runbook.md`, `docs/workflows/release-doc-checklist.md` | 本地测试作为 Win7 验收结论 |
| 查询当前状态、阻塞项和下一步 | `docs/current-status.md` | `docs/implementation-roadmap.md`, `docs/superpowers/README.md` | 已完成切片、历史进度流水 |
| 同步代码与文档 | `docs/workflows/code-doc-sync.md` | `docs/documentation-governance.md`, `docs/references/code-doc-matrix.md` | 在多个入口复制同一事实 |
| 记录或查询长期架构理由 | `docs/adrs/README.md` | 具体 ADR、`docs/workflows/architecture-change-process.md` | 临时 spec 的过程讨论 |
| 调查历史决策、已关闭计划或旧进度 | `docs/archive/README.md` | 对应 archive package 的 `README.md` | 将 archive 反向作为当前实现依据 |

## Authority Rule

- `README.md` 和 `AGENTS.md` 是入口与约束，只负责导航和不可协商规则。
- `docs/modules/` 与项目级 contract 文档拥有当前实现细节。
- `docs/current-status.md` 和 `docs/implementation-roadmap.md` 只保留当前状态与开放排序，旧内容直接替换而非追加。
- `docs/adrs/` 拥有长期决策理由；`docs/workflows/` 拥有协作与交付流程。
- `docs/archive/` 拥有历史。活跃实现工作不得依赖先读 archive 才能理解当前系统。

模块路径与文档所有权的细表见 `docs/references/code-doc-matrix.md`；活跃临时切片的精确列表见 `docs/superpowers/README.md`。
