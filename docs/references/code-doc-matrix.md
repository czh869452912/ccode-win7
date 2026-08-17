# Code-Doc Matrix

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-17`
> 对应代码范围：`packages/`, `src/embedagent/`, `scripts/`

本表是 `docs/README.md` 后的代码区域所有权索引。每行只指定一个 primary authority；路线图、状态页和归档不拥有代码行为。

| Domain | Primary code paths | Primary authority | Supporting contracts/workflows |
|---|---|---|---|
| Agent Core | `packages/embedagent-core/src/embedagent_core/`, `examples/standalone_agent.py` | `docs/platform/agent-core.md` | `docs/platform/session-runtime.md`, `docs/workflows/architecture-change-process.md` |
| Hosted session runtime | `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`, `packages/embedagent-host/src/embedagent_host/runtime/session_*.py`, `transcript_store.py` | `docs/platform/session-runtime.md` | `docs/platform/agent-core.md`, `docs/platform/frontend-protocol.md` |
| Tools and extensions | Core extension/action files, `packages/embedagent-host/src/embedagent_host/runtime/tools/`, local/project extension files | `docs/platform/tools-and-extensions.md` | `docs/platform/tool-contracts.md`, `docs/platform/permission-model.md` |
| Permissions and context | `packages/embedagent-core/src/embedagent_core/permissions.py`, `packages/embedagent-host/src/embedagent_host/runtime/context.py`, workspace intelligence | `docs/platform/permissions-and-context.md` | `docs/platform/permission-model.md` |
| Modes and profiles | `src/embedagent/modes.py`, Core/Host profile files | `docs/platform/mode-contract.md` | `docs/platform/tools-and-extensions.md` |
| Protocol and frontend ports | `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`, `frontend_ports.py`, `session_events.py`, `packages/embedagent-host/src/embedagent_host/frontend_ports.py`, `frontend_errors.py` | `docs/platform/protocol.md` | `docs/platform/frontend-protocol.md` |
| Shared shell registration | `src/embedagent/frontend/shell/` | `docs/product/composition.md` | `docs/platform/frontend-protocol.md`, `docs/platform/protocol.md` |
| Application plugin loading | `src/embedagent/application_loader.py`, `src/embedagent/hosted.py`, `packages/embedagent-core/src/embedagent_core/application.py`, `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`, `packages/embedagent-composition/src/embedagent_composition/application.py`, plugin `application.py` entries | `docs/guides/application-plugin-authoring.md` | `docs/adrs/0008-generic-agent-application-plugin-closure-export.md` |
| Shared Python client runtime | `src/embedagent/frontend/runtime/`, `tests/fixtures/session_client_runtime/` | `docs/platform/frontend-protocol.md` | `docs/platform/protocol.md`, `docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md` |
| CLI shell | `src/embedagent/cli/`, `src/embedagent/__main__.py` | `docs/product/composition.md` | `docs/platform/frontend-protocol.md`, `docs/guides/configuration-guide.md` |
| GUI shell | `src/embedagent/frontend/gui/backend/`, `webapp/src/client-runtime/`, `app-runtime/browser-app-runtime.js`, `session-runtime/session-client-runtime.js`, `components/shell/`, `components/contributions/` | `docs/platform/frontend-gui.md` | `docs/platform/frontend-protocol.md`, `docs/workflows/release-doc-checklist.md` |
| TUI shell | `src/embedagent/frontend/tui/launcher.py`, `bootstrap.py`, `frontend_adapter.py`, `shell_state.py`, `controller.py`, `reducer.py`, `layout.py`, `views/`, `contributions.py` | `docs/platform/frontend-tui.md` | `docs/platform/frontend-protocol.md` |
| C/C++ application | `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/` | `docs/applications/cpp-workflow.md` | `docs/platform/tools-and-extensions.md`, `docs/platform/mode-contract.md` |
| Product composition | `src/embedagent/product_catalog.py`, `bundle_catalog.py`, `bundle_policy.py`, product bootstrap/CLI/launchers, `packages/embedagent-composition/` | `docs/product/composition.md` | `docs/overall-solution-architecture.md`, `docs/platform/protocol.md` |
| Packaging and delivery | `scripts/compile-bundle-plan.py`, package/export/prepare/build/validate/evidence scripts, `scripts/offline-runtime-contract.json`, `config/bundle-flavors/`, distribution metadata, bundled assets | `docs/product/packaging-and-deployment.md` | `docs/guides/win7-release-runbook.md`, `docs/workflows/release-doc-checklist.md` |

所有权改变时，在同一变更中更新本表、primary authority 和 ADR（若需要长期理由）。不新增第二个全局地图。
