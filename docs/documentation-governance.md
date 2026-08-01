# Documentation Governance

> 状态：`active`
> 类型：`governance`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`

## Purpose

文档体系的目标是让人和智能体用最小上下文定位当前权威，而不是保存实施流水。一个事实只能有一个所有者；入口负责路由，权威文档负责细节，历史材料负责追溯。

## Five Layers

| Layer | Documents | Responsibility |
|---|---|---|
| Entry | `README.md`, `AGENTS.md` | 产品入口、命令、不可协商约束；不展开领域细节 |
| Map | `docs/README.md` | 唯一全局意图地图；路由到权威 |
| Authority | overall architecture, `docs/platform/`, `docs/applications/`, `docs/product/`, guides, workflows, ADRs | 当前架构、行为、操作和决策理由 |
| Current work | `docs/current-status.md`, `docs/implementation-roadmap.md`, `docs/superpowers/README.md` | 当前状态、开放顺序、精确活跃切片 |
| History | `docs/archive/`, `analysis/` | 已完成计划、证据、旧快照和调查材料 |

活跃实现不得依赖阅读 History 才能发现当前行为。

## One Fact, One Owner

- 跨层拓扑只由总体架构拥有；局部实现由对应 platform/application/product authority 或契约文档拥有。
- 操作步骤由 guide 或 workflow 拥有；长期决策理由由 ADR 拥有。
- Entry 和 Map 只写最短摘要与链接，不复制文件清单、控制器说明或完整契约。
- 当事实变化时更新所有者；只有路由变化才更新 `docs/README.md` 和代码-文档矩阵。
- 冲突时，以拥有该事实的当前 authority 为准，并删除其他活跃文档中的重复表述。

## Current Work Is Replace-In-Place

- `docs/current-status.md` 只保存现在的发布状态、焦点、阻塞项、下一步和证据边界。状态变化时替换旧内容，不追加日期日志。
- `docs/implementation-roadmap.md` 只保存开放项目、顺序约束和退出条件。项目关闭后移除，不保留完成清单。
- `docs/superpowers/README.md` 必须精确列出尚有开放验收条件的 spec/plan 文件。
- 切片关闭时，先把可持续结论同步到 authority，再将 spec/plan 移入带 `README.md` 的 archive package，并从活跃索引删除。

## ADR Rule

当变化包含长期约束、至少两个有意义的备选方案或难以从代码推导的理由时，新增或更新 ADR。ADR 记录背景、选择、替代项和后果，不承担当前进度或实施步骤。

## Context Budgets

| Document | Maximum words |
|---|---:|
| `README.md` | 1500 |
| `AGENTS.md` | 2500 |
| `docs/README.md` | 1000 |
| `docs/overall-solution-architecture.md` | 3000 |
| `docs/implementation-roadmap.md` | 1000 |
| `docs/current-status.md` | 750 |

超出预算必须在同一变更中拆分到明确所有者并恢复预算；不能以“信息完整”为由让入口或全局权威持续膨胀。

## Code-Doc Sync

代码变更只更新受影响的所有者：公共契约、跨领域所有权、操作流程、配置/发布行为或当前优先级发生变化时，分别更新 domain authority/contract、guide/workflow、ADR 或 current-work 文档。不要求每次变更追加全局 tracker 或 change log。

流程见 `docs/workflows/code-doc-sync.md`；详细所有权见 `docs/references/code-doc-matrix.md`。

## Archive Policy

- Archive 保存已完成切片、关闭审计、历史快照和验收证据，不承载当前官方口径。
- 每个 archive package 必须列出材料、归档原因和当前权威入口。
- 活跃文档可以把 `docs/archive/README.md` 作为历史调查入口，但不能把具体归档文件作为当前契约。
- Git 历史足以保存普通文案演变；只有具有调查、决策或验收价值的材料才进入 archive。
