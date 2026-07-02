# Code-Doc Matrix

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-06-17`
> 对应代码范围：`src/embedagent/`, `docs/`

| Code Area | Primary Paths | Global Docs | Module Docs | Workflow / Reference Docs |
|---|---|---|---|---|
| Agent Core / Host | `src/embedagent_core/`, `src/embedagent_host/`, `src/embedagent/session_runtime.py` | `docs/overall-solution-architecture.md`, `docs/agent-harness-v2.md` | `docs/modules/agent-core.md` | `docs/references/glossary.md`, `docs/workflows/code-doc-sync.md` |
| Session Runtime | `src/embedagent/session.py`, `src/embedagent/session_history.py`, `src/embedagent/session_projector.py`, `src/embedagent/transcript_store.py` | `docs/overall-solution-architecture.md`, `docs/frontend-protocol.md` | `docs/modules/session-runtime.md` | `docs/references/glossary.md`, `docs/references/diagrams-conventions.md` |
| Harness | `src/embedagent/workflow_packages/c_cpp/` | `docs/overall-solution-architecture.md`, `docs/mode-schema.md`, `docs/agent-harness-v2.md` | `docs/modules/harness.md` | `docs/references/glossary.md`, `docs/workflows/architecture-change-process.md` |
| Tools / Tooling | `src/embedagent/tools/`, `src/embedagent/tooling/` | `docs/tool-contracts.md`, `docs/overall-solution-architecture.md` | `docs/modules/tools-and-tooling.md` | `docs/references/code-doc-matrix.md`, `docs/workflows/code-doc-sync.md` |
| Permissions / Context | `src/embedagent_core/permissions.py`, `src/embedagent/context.py`, `src/embedagent/workspace_intelligence.py` | `docs/permission-model.md`, `docs/overall-solution-architecture.md` | `docs/modules/permissions-and-context.md` | `docs/references/glossary.md`, `docs/references/diagrams-conventions.md` |
| Protocol / Core | `src/embedagent/protocol/`, `src/embedagent/core/` | `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md` | `docs/modules/protocol-and-core.md` | `docs/workflows/architecture-change-process.md` |
| Frontend TUI | `src/embedagent/frontend/tui/` | `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md` | `docs/modules/frontend-tui.md` | `docs/references/diagrams-conventions.md` |
| Frontend GUI | `src/embedagent/frontend/gui/` | `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md` | `docs/modules/frontend-gui.md` | `docs/references/diagrams-conventions.md`, `docs/workflows/release-doc-checklist.md` |
| Packaging / Deployment | `scripts/`, `docs/guides/`, packaging docs, Win7 validation docs | `README.md`, `docs/implementation-roadmap.md` | `docs/modules/packaging-and-deployment.md` | `docs/workflows/release-doc-checklist.md`, `docs/references/glossary.md` |
