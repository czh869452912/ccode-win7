# Permissions And Context

## Metadata

> 状态：`active`
> 类型：`module`
> 负责人：`project maintainers`
> 最后同步日期：`2026-07-19`
> 对应代码范围：`packages/embedagent-core/src/embedagent_core/permissions.py`, `packages/embedagent-host/src/embedagent_host/runtime/context.py`, `packages/embedagent-host/src/embedagent_host/runtime/workspace_intelligence.py`

## 1. Purpose And Scope

本模块文档说明权限决策、上下文预算与 workspace intelligence 的协作关系，覆盖 `PermissionPolicy`、`ContextManager` 与 `WorkspaceIntelligenceProvider` / `WorkspaceIntelligenceBroker`。

## 2. Responsibilities

- permission rule matching and explanation rendering
- context budgeting and reducer routing
- workspace intelligence evidence assembly
- permission enforcement for extension-registered tools through runtime catalog metadata
- extension context patching through `AgentExtensionHost`
- extension pre/post tool hooks around `AgentToolActionService`

该模块确保工具审批、消息组装与 workspace 证据注入围绕统一规则运行，而不是由 prompt 文本隐式驱动。

## 3. Code Mapping

- Core 目录：`packages/embedagent-core/src/embedagent_core/`
- Runtime 目录：`src/embedagent/`
- 入口文件：`packages/embedagent-core/src/embedagent_core/permissions.py`, `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- 核心对象：`PermissionPolicy`、`ContextManager`、`WorkspaceIntelligenceProvider`、`WorkspaceIntelligenceBroker`、`AgentExtensionHost`、`AgentToolActionService`
- 上游依赖：query engine、tool runtime
- 下游影响：tool approval UX、message assembly、verify context quality
- 相关测试：`tests/test_permissions.py`、`tests/test_context_config.py`、`tests/test_query_engine_refactor.py`、`tests/test_architecture.py`、`tests/test_capability_extensions.py`、`tests/test_dynamic_tool_registration.py`
- 相关契约：`docs/permission-model.md`、`docs/overall-solution-architecture.md`

## 4. Dependencies And Consumers

上游依赖：

- `packages/embedagent-core/src/embedagent_core/query_engine.py`
- `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`
- `packages/embedagent-core/src/embedagent_core/agent_extension_host.py`
- `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`

下游消费者：

- tool approval / ask-user UX
- model message assembly
- diagnostics / quality evidence summary
- verify 模式与 review 相关上下文质量

## 5. Data / Control Flow

`AgentExtensionHost` 先应用 extension context hooks；`AgentToolActionService` 在执行 tool action 时套用 extension before/after tool hooks，并通过 `PermissionPolicy` 对 built-in 与 extension-registered tools 做同一套权限决策。`ToolRuntime` 产出 observations 后，`ContextManager` 与 workspace intelligence 共同组装最终提供给模型的消息上下文。

```mermaid
sequenceDiagram
    participant QE as QueryEngine
    participant AEH as AgentExtensionHost
    participant ATS as AgentToolActionService
    participant PP as PermissionPolicy
    participant TR as ToolRuntime
    participant CM as ContextManager
    QE->>AEH: apply context hooks
    QE->>ATS: execute tool action
    ATS->>AEH: before tool hooks
    ATS->>PP: evaluate action
    ATS->>TR: execute runtime tool
    ATS->>AEH: after tool result hooks
    TR->>CM: observation
```

## 6. Verification And Tests

推荐回归入口：

- `tests/test_permissions.py`
- `tests/test_context_config.py`
- `tests/test_query_engine_refactor.py`
- `tests/test_architecture.py`
- `tests/test_capability_extensions.py`
- `tests/test_dynamic_tool_registration.py`

当 permission 分类、解释文本、extension hook order、context budgeting、reducer 路径或 workspace intelligence 证据聚合变化时，应优先重跑这些测试。

## 7. Change Triggers

以下变化必须同步更新本文件：

- 权限规则匹配结构变化
- explanation text 语义变化
- extension-registered tool permission 分类或 hook 执行路径变化
- context budgeting / reducer routing 变化
- workspace intelligence provider/broker 结构变化
- tool approval UX 或 message assembly 边界变化

## 8. Related Documents

- `docs/permission-model.md`
- `docs/overall-solution-architecture.md`
- `docs/references/code-doc-matrix.md`
- `docs/references/glossary.md`
