# Code-Doc Matrix

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`
> 对应代码范围：`packages/`, `src/embedagent/`, `scripts/`

本表是 `docs/README.md` 后的代码区域所有权索引。模块或契约文档拥有细节；路线图、状态页和归档材料不拥有代码行为。

| Code Area | Primary Paths | Owning Module | Contract / Workflow Authorities |
|---|---|---|---|
| Agent Core | `packages/embedagent-core/src/embedagent_core/` | `docs/modules/agent-core.md` | `docs/overall-solution-architecture.md`, `docs/workflows/architecture-change-process.md` |
| Hosted Runtime | `packages/embedagent-host/src/embedagent_host/` | `docs/modules/session-runtime.md` | `docs/modules/agent-core.md`, `docs/frontend-protocol.md` |
| C/C++ Workflow | `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/` | `docs/modules/harness.md` | `docs/agent-harness-v2.md`, `docs/mode-schema.md` |
| Tools | `packages/embedagent-host/src/embedagent_host/runtime/tools/`, `packages/embedagent-core/src/embedagent_core/tool_contracts.py` | `docs/modules/tools-and-tooling.md` | `docs/tool-contracts.md`, `docs/workflows/code-doc-sync.md` |
| Permissions / Context | `packages/embedagent-core/src/embedagent_core/permissions.py`, `packages/embedagent-host/src/embedagent_host/runtime/context.py` | `docs/modules/permissions-and-context.md` | `docs/permission-model.md` |
| Protocol | `packages/embedagent-protocol/src/embedagent_protocol/`, `src/embedagent/core/` | `docs/modules/protocol-and-core.md` | `docs/frontend-protocol.md` |
| TUI | `src/embedagent/frontend/tui/` | `docs/modules/frontend-tui.md` | `docs/frontend-protocol.md` |
| GUI | `src/embedagent/frontend/gui/` | `docs/modules/frontend-gui.md` | `docs/frontend-protocol.md`, `docs/workflows/release-doc-checklist.md` |
| Product Composition | `src/embedagent/product_catalog.py`, `src/embedagent/product_composition.py` | `docs/overall-solution-architecture.md` | `docs/modules/protocol-and-core.md` |
| Packaging / Delivery | `scripts/`, distribution metadata, bundled assets | `docs/modules/packaging-and-deployment.md` | `docs/guides/win7-release-runbook.md`, `docs/workflows/release-doc-checklist.md` |

When ownership changes, update this table and the owning authority in the same change. Do not add a second global map.
