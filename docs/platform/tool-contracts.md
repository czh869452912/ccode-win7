# Tool Contracts

## Metadata

> 状态：`active`
> 类型：`platform contract`
> 负责人：`Agent platform maintainers`
> 最后同步日期：`2026-08-01`
> 对应代码范围：`packages/embedagent-core/src/embedagent_core/tool_contracts.py`, `packages/embedagent-host/src/embedagent_host/runtime/tools/`

## 1. Contract Shape

每个正式工具契约包含：

- 稳定 name 和 model-facing description；
- JSON-safe parameter schema；
- 结构化 `Observation` shape；
- runtime catalog metadata；
- permission category；
- source/provenance metadata。

`ToolRuntime` catalog entry 是 permission category、execution facets、presentation facets 和 context/read-model invalidations 的唯一真相。Mode、permission policy、adapter 和 renderer 不得按工具名维护平行分类表。

## 2. Platform Tool Vocabulary

| Tool | Purpose | Core parameters |
|---|---|---|
| `read_file` | 读取单个文本文件 | `path` |
| `list_dir` | 浅层、可分页目录列表 | `path`, `limit`, `offset` |
| `glob_files` | 文件名/路径匹配 | `path`, `pattern`, `limit`, `offset` |
| `grep_text` | 文本内容搜索 | `path`, `query`, `limit`, `offset` |
| `write_file` | 整文件写入 | `path`, `content`, `overwrite` |
| `edit_file` | 精确文本替换 | `path`, `old_text`, `new_text` |
| `author_local_capability` | 创建 workspace-bound 本地能力文件 | `kind`, `name`, content/options |
| `bash` | 执行经 sanitizer 处理的显式命令 | `command`, optional `cwd`, `timeout_sec` |
| `ask_user` | 创建显式用户交互 | `question`, optional options |

上层应用工具在各自 application authority 中定义，但必须使用本文档的同一 catalog、schema、observation、permission 和 history 契约。

## 3. Observation

official tool 返回结构化 observation，通用字段包括：

- `success`；
- `error`；
- `tool_name`；
- tool-specific `data`。

command observation 记录 stdout/stderr encoding、replacement count、mojibake hints、tail-preserving truncation 和可选 `full_output_ref`。可诊断的失败应给出 `error_kind`、`outcome_class`、`retryable` 和 `suggested_next_step`。普通非零退出或 timeout 是给下一轮的证据，不自动等于 agent hard stop。

list/search observation 应使用 `preview`, `returned_count`, `total_count`, `has_more`, `next_offset`, `result_ref`。大输出不得仅以 raw terminal dump 进入 prompt、telemetry 或 diagnostics。

## 4. Catalog Facets

catalog entry 可包含：

- `permission_category`；
- read-only / concurrency / timeout execution metadata；
- `preview_arg`, `changed_path_arg`, labels, renderer keys；
- `context_reducer_key` 和 `read_model_invalidations`；
- source type 与 source id。

安全展示 metadata 只影响 UI。invalidations 只请求刷新读模型。它们都不能激活工具、授权、执行工具或改变 workflow state。

## 5. Activation And Provider Snapshot

registration 不使工具自动可见。`AgentExtensionHost` 组合 mode contract 和 `ExtensionManager` 的 active names，并以显式 `tool_names` 调用 `ToolRuntime.schemas_for(...)`。

`ProviderStepService` 在 context assembly 和 schema projection 之后创建冻结 `TurnSnapshot`，provider 只消费 `snapshot.messages` 和 `snapshot.tool_schemas`。snapshot diagnostics 可记录安全名称、计数与 provenance，不得包含 prompt/skill body、source contents、raw tool output、credential 或 approval secret。

## 6. Extension Hooks And Dynamic Tools

`tool_call` hook 可以拒绝 active action 或返回新 arguments；`tool_result` hook 可以替换 observation 或提供受限 workflow patch。hooks 只有通过 `ExtensionCapability` 显式声明才有效，且不跳过 mode、permission、write-path 或 active-tool checks。

动态工具注册至少提供：

- `ToolDefinition`；
- valid `permission_category`；
- source metadata；
- 需要时提供 mode/workflow visibility、execution、presentation 和 invalidation metadata。

扩展不能替换内建工具。catalog 对未声明 facets 生成保守默认。`capability_descriptors()` 和 `runtime_config.active_tool_names` 是诊断/回放读模型，不是 active-tool policy shortcut。

## 7. Interaction And Resumption

`ask_user`、permission request 和 mode proposal 可以使 turn 挂起。恢复后 action 必须重新进入 `AgentToolActionService` 的同一串行管道，重做 active-tool、hook、permission 和 path 检查，不从 Host 或 UI 直接调度 handler。

## 8. Durable Presentation

每个 tool call 的历史展示快照保留：

- `tool_label`；
- `permission_category`；
- `supports_diff_preview`；
- `progress_renderer_key`；
- `result_renderer_key`；
- `source_type`；
- `source_id`。

`tool_start`, `tool_finish` 和 interaction events 保留 engine-issued `turn_id`, `step_id`, `step_index`。adapter 和 frontend 不得创建替代 step identity。

## 9. External Boundaries

运行时子进程只能使用 `scripts/offline-runtime-contract.json` 中的 bundled binaries。命令消毒只通过 `get_command_sanitizer()`。内网 service、provider、Git 和 telemetry 使用显式 adapter/sink 及 `network` / `telemetry` 权限，不伪装成 `read` 或 `other`。

## 10. Verification

- `tests/test_tools_package.py`
- `tests/test_tool_execution.py`
- `tests/test_tools_package.py`
- `tests/test_dynamic_tool_registration.py`
- `tests/test_turn_snapshot.py`
- `tests/test_agent_tool_effects.py`
- `tests/test_hosted_interaction_service.py`

## 11. Related Documents

- `docs/platform/tools-and-extensions.md`
- `docs/platform/permission-model.md`
- `docs/platform/frontend-protocol.md`
