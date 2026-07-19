# Harness

## Metadata

> 状态：`active`
> 类型：`module`
> 负责人：`project maintainers`
> 最后同步日期：`2026-07-19`
> 对应代码范围：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/`

## 1. Purpose And Scope

本模块文档说明默认 C/C++ Harness 负责的执行纪律和任务结构。Harness 是 bundled built-in workflow extension，覆盖 C/C++ workflow discipline defaults、phase advancement、prompt stack、`TaskGraph` 内部状态与通用 workflow 投影；它不拥有全局 `embedagent.modes` facade。

## 2. Responsibilities

- C/C++ workflow discipline/profile behavior behind the default application
- discipline defaults
- phase advancement
- prompt stack construction
- task graph generation
- CMake/Make/Ninja workspace recipe detection and `run_recipe` projection
- C/C++ workspace-profile file/build-system detection
- bundled C/C++ workflow extension integration
- generic `Session.workflow_state["workflow"]` projection

Harness 的职责是把 workflow 结构从 ad-hoc prompt 行为中抽离出来，形成稳定的 `mode + discipline_profile + execution_phase + TaskGraph` 正式模型。

The default C/C++ harness is the bundled built-in workflow package. Hosted product paths install it through the default C/C++ `AgentApplication` in `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py`; a bare `QueryEngine` does not import or construct it. The legacy/global `embedagent.modes` facade is backed by the Generic Agent profile, while the C/C++ application supplies the package-owned profile from `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/agent_profile.py` to hosted runtime mode policy and the package-owned workspace-profile detector from `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_profile.py` to hosted workspace profiling. Harness internals may own `TaskGraph`, C/C++ recipe detection, workspace-profile file signals, and `run_recipe` projection, but Agent Core and frontend consumers receive only generic workflow/read-model payloads. Harness hooks, package manifest collection, context reducer registration, workspace recipe projection, active tools, tool registration, task loading, managed-session refresh, and extension-owned `task_status` handling are declared through explicit `ExtensionCapability` records returned by `CHarnessWorkflowExtension.extension_capabilities()`, then reached from host code through `AgentApplication.refresh_managed_session()`.

## 3. Code Mapping

- 目录：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/`
- 入口文件：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- application record：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application_record.py`
- profile：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/agent_profile.py`
- 核心对象：`default_c_cpp_agent_application_record()`、`default_c_cpp_agent_profile()`、`CCppWorkspaceProfileDetector`、`CHarnessWorkflowExtension`、`HarnessRunner`、`TaskGraph`、`build_workflow_projection()`、`advance_phase()` / `advance_until_stable()`
- 上游依赖：`AgentApplication`、`ExtensionManager`、agent profile mode policy
- 下游影响：`task_status`、session snapshots、frontend runtime
- workflow-owned recipes：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_recipes.py`、`recipe_ops.py`
- workflow-owned workspace profile detector：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_profile.py`
- 相关测试：`tests/test_harness_runner_taskgraph.py`、`tests/test_harness_runner_debug.py`、`tests/test_harness_runner_verify.py`、`tests/test_harness_task_projection.py`、`tests/test_harness_contracts.py`
- 相关契约：`docs/agent-harness-v2.md`、`docs/mode-schema.md`、`docs/tool-contracts.md`

## 4. Dependencies And Consumers

上游依赖：

- `packages/embedagent-core/src/embedagent_core/query_engine.py`
- `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py`

下游消费者：

- session task snapshot
- `task_status`
- frontend runtime / task 面板
- tool pack 选择和 phase 约束
- workspace recipe projection for `/recipes`, `/run`, `list_recipes`, and `run_recipe`
- `Session.workflow_state["workflow"]`

## 5. Data / Control Flow

Hosted product paths 通过 `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py` 把 bundled C harness 安装进 selected `AgentApplication.extension_manager`。`CHarnessWorkflowExtension` 内部使用 `HarnessRunner` / `TaskGraph`，通过 `extension_capabilities()` 声明 prompt/state/tool/task 相关能力，再通过 harness-owned workflow projection 把状态写入 `Session.workflow_state["workflow"]`，供 `task_status`、session snapshot 和 frontend tasks 使用。

```mermaid
flowchart TD
    A["c_cpp/application.py"] --> B["AgentApplication.extension_manager"]
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
- `tests/test_agent_profiles.py`

当 mode 词汇、phase 推进、task projection 或 discipline behavior 改变时，应优先重跑这些测试。

## 7. Change Triggers

以下变化必须同步更新本文件：

- C/C++ application profile or workflow discipline changes
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
