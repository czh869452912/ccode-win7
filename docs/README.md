# 文档导航

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-04-09`
> 对应代码范围：`README.md`, `AGENTS.md`, `docs/`

## 1. 文档分层

- `docs/superpowers/`：当前切片说明书，服务本轮设计、计划、实施与 review。
- `docs/` 活动文档：长期 `source-of-truth`，记录当前官方口径、模块边界和维护规则。
- `docs/archive/`：历史留痕，保存已完成切片的设计、计划、分析和复盘材料。

## 2. 项目级官方文档

- `overall-solution-architecture.md`
- `implementation-roadmap.md`
- `development-tracker.md`
- `design-change-log.md`
- `mode-schema.md`
- `tool-contracts.md`
- `permission-model.md`
- `frontend-protocol.md`
- `agent-harness-v2.md`

这些文档定义项目级长期真相，不由单轮 `superpowers` 文档替代。

## 3. 模块文档

- `modules/README.md`
- `modules/agent-core.md`
- `modules/session-runtime.md`
- `modules/harness.md`
- `modules/tools-and-tooling.md`
- `modules/permissions-and-context.md`
- `modules/protocol-and-core.md`
- `modules/frontend-tui.md`
- `modules/frontend-gui.md`
- `modules/packaging-and-deployment.md`

模块文档负责把代码目录、入口文件、数据流、测试入口和相关契约文档稳定地绑定起来。

## 4. 操作指南

- `guides/README.md`
- `guides/configuration-guide.md`
- `guides/intranet-deployment.md`
- `guides/llm-adapter.md`
- `guides/win7-gui-validation.md`
- `guides/win7-preflight-checklist.md`

指南文档提供配置示例、操作步骤和兼容性记录，是对模块文档和工作流文档的补充。

## 5. 工作流文档

- `workflows/README.md`
- `workflows/code-doc-sync.md`
- `workflows/architecture-change-process.md`
- `workflows/release-doc-checklist.md`

工作流文档定义“怎么做事”，例如怎样从 `superpowers` 设计回写到全局文档，以及发布前如何检查文档完整性。

## 5. 参考与模板

- `references/glossary.md`
- `references/code-doc-matrix.md`
- `references/diagrams-conventions.md`
- `templates/architecture-doc-template.md`
- `templates/module-doc-template.md`
- `templates/workflow-doc-template.md`
- `templates/adr-template.md`
- `templates/change-entry-template.md`

参考文档提供统一语言和约束，模板文档提供统一骨架和最小结构。

## 6. Archive 使用规则

- `archive` 只保存历史材料，不承载当前官方口径。
- 活动文档不得依赖 `archive` 作为当前真相源。
- 每轮切片完成后，应先同步全局项目文档和模块文档，再归档对应 `superpowers` 材料。
- Completed self-extensible Agent Core slice materials belong under `docs/archive/self-extensible-agent-core/` after their durable conclusions are synchronized into active source-of-truth docs and module docs.
