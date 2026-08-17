# Documentation Map

> 状态：`active`
> 类型：`navigation`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-09`

本页是唯一的全局文档地图。先判断修改的是通用 Agent 平台、上层应用还是 EmbedAgent 产品组合，再进入对应领域；入口文件、临时切片和历史材料都不是实现说明书。

| 意图 | 首要权威 | 补充权威 |
|---|---|---|
| 了解系统拓扑、selected distributions 和依赖方向 | `docs/overall-solution-architecture.md` | `docs/references/code-doc-matrix.md` |
| 修改通用 Agent Core 或持久会话 | `docs/platform/agent-core.md` | `docs/platform/session-runtime.md` |
| 修改通用工具、扩展或运行时目录 | `docs/platform/tools-and-extensions.md` | `docs/platform/tool-contracts.md` |
| 修改权限、写路径或上下文组装 | `docs/platform/permissions-and-context.md` | `docs/platform/permission-model.md` |
| 修改 Core/Host 或 Host/UI 协议 | `docs/platform/protocol.md` | `docs/platform/frontend-protocol.md` |
| 修改可注册 GUI/TUI 交互层 | `docs/platform/frontend-gui.md`, `docs/platform/frontend-tui.md` | `docs/platform/frontend-protocol.md` |
| 修改通用模式契约或独立底座方向 | `docs/platform/mode-contract.md` | `docs/platform/agent-platform-blueprint.md` |
| 修改 C/C++ 工作流、任务图或质量证据 | `docs/applications/cpp-workflow.md` | `docs/applications/README.md` |
| 修改 EmbedAgent 默认组合与启动 | `docs/product/composition.md` | `docs/product/README.md` |
| 修改 plan-driven 构建、离线资产或 Win7 交付 | `docs/product/packaging-and-deployment.md` | `docs/guides/win7-release-runbook.md` |
| 编写 application plugin 或注册入口 | `docs/guides/application-plugin-authoring.md` | `docs/adrs/0008-generic-agent-application-plugin-closure-export.md` |
| 查询当前阻塞与下一步 | `docs/current-status.md` | `docs/implementation-roadmap.md`, `docs/superpowers/README.md` |
| 同步代码与文档 | `docs/workflows/code-doc-sync.md` | `docs/documentation-governance.md`, `docs/references/code-doc-matrix.md` |
| 查询长期架构理由 | `docs/adrs/README.md` | `docs/workflows/architecture-change-process.md` |
| 调查已关闭工作 | `docs/archive/README.md` | 对应 archive package 的 `README.md` |

## Domain Indexes

- `docs/platform/README.md`：可独立复用的 Agent 底座及通用交互契约。
- `docs/applications/README.md`：建立在平台上的工作流应用。
- `docs/product/README.md`：EmbedAgent 产品组合、默认选择与交付。

## Authority Rule

- `README.md` 和 `AGENTS.md` 只负责入口与不可协商约束。
- `docs/platform/`、`docs/applications/`、`docs/product/` 分别拥有平台、应用、产品当前真相；同一事实只能由其中一个领域拥有。
- `docs/current-status.md` 和 `docs/implementation-roadmap.md` 只保留当前状态与开放排序，旧内容直接替换。
- `docs/adrs/` 拥有长期理由，`docs/workflows/` 拥有协作流程，`docs/archive/` 只拥有历史。
- 活跃实现不得通过旧路径兼容页或 archive 才能发现当前行为。

详细所有权见 `docs/references/code-doc-matrix.md`；活跃临时切片见 `docs/superpowers/README.md`。
