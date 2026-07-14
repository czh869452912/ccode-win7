# Code-Doc Matrix

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-06-17`
> 对应代码范围：`src/embedagent/`, `docs/`

| Code Area | Primary Paths | Global Docs | Module Docs | Workflow / Reference Docs |
|---|---|---|---|---|
| Agent Core / Host | `packages/embedagent-core/src/embedagent_core/`, `packages/embedagent-host/src/embedagent_host/` | `docs/overall-solution-architecture.md`, `docs/agent-harness-v2.md` | `docs/modules/agent-core.md` | `docs/references/glossary.md`, `docs/workflows/code-doc-sync.md` |
| Session Runtime | `packages/embedagent-core/src/embedagent_core/session.py`, `packages/embedagent-host/src/embedagent_host/runtime/session_history.py`, `packages/embedagent-host/src/embedagent_host/runtime/session_projector.py`, `packages/embedagent-host/src/embedagent_host/runtime/transcript_store.py` | `docs/overall-solution-architecture.md`, `docs/frontend-protocol.md` | `docs/modules/session-runtime.md` | `docs/references/glossary.md`, `docs/references/diagrams-conventions.md` |
| Harness | `src/embedagent/workflow_packages/c_cpp/` | `docs/overall-solution-architecture.md`, `docs/mode-schema.md`, `docs/agent-harness-v2.md` | `docs/modules/harness.md` | `docs/references/glossary.md`, `docs/workflows/architecture-change-process.md` |
| Tools / Tooling | `packages/embedagent-host/src/embedagent_host/runtime/tools/`, `src/embedagent/tooling/` | `docs/tool-contracts.md`, `docs/overall-solution-architecture.md` | `docs/modules/tools-and-tooling.md` | `docs/references/code-doc-matrix.md`, `docs/workflows/code-doc-sync.md` |
| Permissions / Context | `packages/embedagent-core/src/embedagent_core/permissions.py`, `packages/embedagent-host/src/embedagent_host/runtime/context.py`, `packages/embedagent-host/src/embedagent_host/runtime/workspace_intelligence.py` | `docs/permission-model.md`, `docs/overall-solution-architecture.md` | `docs/modules/permissions-and-context.md` | `docs/references/glossary.md`, `docs/references/diagrams-conventions.md` |
| Protocol / Core | `packages/embedagent-protocol/src/embedagent_protocol/`, `src/embedagent/core/` | `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md` | `docs/modules/protocol-and-core.md` | `docs/workflows/architecture-change-process.md` |
| Frontend TUI | `src/embedagent/frontend/tui/` | `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md` | `docs/modules/frontend-tui.md` | `docs/references/diagrams-conventions.md` |
| Frontend GUI | `src/embedagent/frontend/gui/` | `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md` | `docs/modules/frontend-gui.md` | `docs/references/diagrams-conventions.md`, `docs/workflows/release-doc-checklist.md` |
| Packaging / Deployment | `scripts/`, `docs/guides/`, packaging docs, Win7 validation docs | `README.md`, `docs/implementation-roadmap.md` | `docs/modules/packaging-and-deployment.md` | `docs/workflows/release-doc-checklist.md`, `docs/references/glossary.md` |
