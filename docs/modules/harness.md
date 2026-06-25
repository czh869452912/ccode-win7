# Harness

## Metadata

> 状态：`active`
> 类型：`module`
> 负责人：`project maintainers`
> 最后同步日期：`2026-06-12`
> 对应代码范围：`src/embedagent/harness/`

## 1. Purpose And Scope

本模块文档说明默认 C/C++ Harness 负责的执行纪律和任务结构。Harness 是 bundled built-in workflow extension，覆盖 mode registry、discipline defaults、phase advancement、prompt stack、`TaskGraph` 内部状态与通用 workflow 投影。

## 2. Responsibilities

- mode registry
- discipline defaults
- phase advancement
- prompt stack construction
- task graph generation
- bundled C/C++ workflow extension integration
- generic `Session.workflow_state["workflow"]` projection

Harness 的职责是把 workflow 结构从 ad-hoc prompt 行为中抽离出来，形成稳定的 `mode + discipline_profile + execution_phase + TaskGraph` 正式模型。

The default C/C++ harness is the bundled built-in workflow extension. Hosted product paths install it through `src/embedagent/default_extensions.py`; a bare `QueryEngine` does not import or construct it. Harness internals may own `TaskGraph`, but Agent Core and frontend consumers receive only the generic `Session.workflow_state["workflow"]` projection. Harness hooks, package manifest collection, context reducer registration, active tools, tool registration, task loading, and extension-owned `task_status` handling are declared through explicit `ExtensionCapability` records returned by `CHarnessWorkflowExtension.extension_capabilities()`.

## 3. Code Mapping

- 目录：`src/embedagent/harness/`
- 入口文件：`src/embedagent/harness/extension.py`
- 核心对象：`CHarnessWorkflowExtension`、`HarnessRunner`、`TaskGraph`、`build_workflow_projection()`、`advance_phase()` / `advance_until_stable()`
- 上游依赖：`default_extensions.py`、`ExtensionManager`、`modes.py`
- 下游影响：`task_status`、session snapshots、frontend runtime
- 相关测试：`tests/test_harness_runner_taskgraph.py`、`tests/test_harness_runner_debug.py`、`tests/test_harness_runner_verify.py`、`tests/test_harness_task_projection.py`、`tests/test_harness_contracts.py`
- 相关契约：`docs/agent-harness-v2.md`、`docs/mode-schema.md`、`docs/tool-contracts.md`

## 4. Dependencies And Consumers

上游依赖：

- `src/embedagent/query_engine.py`
- `src/embedagent/modes.py`

下游消费者：

- session task snapshot
- `task_status`
- frontend runtime / task 面板
- tool pack 选择和 phase 约束
- `Session.workflow_state["workflow"]`

## 5. Data / Control Flow

Hosted product paths 通过 `default_extensions.py` 把 bundled C harness 安装进 shared `ExtensionManager`。`CHarnessWorkflowExtension` 内部使用 `HarnessRunner` / `TaskGraph`，通过 `extension_capabilities()` 声明 prompt/state/tool/task 相关能力，再通过 harness-owned workflow projection 把状态写入 `Session.workflow_state["workflow"]`，供 `task_status`、session snapshot 和 frontend tasks 使用。

```mermaid
flowchart TD
    A["default_extensions.py"] --> B["ExtensionManager"]
    B --> C["CHarnessWorkflowExtension"]
    C --> D["HarnessRunner / TaskGraph"]
    D --> E["harness workflow projection"]
    E --> F["Session.workflow_state['workflow']"]
    F --> G["task_status / session snapshot / frontend tasks"]
```

## 6. Verification And Tests

推荐回归入口：

- `tests/test_harness_runner_taskgraph.py`
- `tests/test_harness_runner_debug.py`
- `tests/test_harness_runner_verify.py`
- `tests/test_harness_task_projection.py`
- `tests/test_harness_contracts.py`
- `tests/test_modes.py`

当 mode 词汇、phase 推进、task projection 或 discipline behavior 改变时，应优先重跑这些测试。

## 7. Change Triggers

以下变化必须同步更新本文件：

- mode registry 变化
- `discipline_profile` 或 `execution_phase` 语义变化
- `TaskGraph` 结构变化
- bundled C harness extension 装配路径变化
- phase advancement 规则变化
- task projection 到 session snapshot 的路径变化

## 8. Related Documents

- `docs/agent-harness-v2.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/references/code-doc-matrix.md`
- `docs/references/glossary.md`
