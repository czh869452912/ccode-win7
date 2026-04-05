# Transcript-Truth Tool Result Persistence Cutover — 影响面与风险分析

> 日期：2026-04-05
> 来源设计文档：`docs/superpowers/specs/2026-04-05-transcript-truth-tool-result-cutover-design.md`
> 分析范围：代码库中受本次架构切变影响的所有核心模块、前端接口、恢复路径及清理策略

---

## 1. 当前代码中的根因定位

### 1.1 竞争热点确认

问题日志中的 `WinError 2` / `WinError 32` 来自 `artifacts.py` 中 `ArtifactStore._write_index()` 对 `index.json` 的固定名称临时文件替换：

```python
# src/embedagent/artifacts.py:219-222
def _write_index(self, payload: Dict[str, Any]) -> None:
    if not os.path.isdir(self.root):
        os.makedirs(self.root)
    _atomic_write_json(self.index_path, payload)

# _atomic_write_json:15-20
def _atomic_write_json(path: str, payload: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ...)
    os.replace(tmp, path)
```

当同一 step 的并行 `read_file` / `search_text` 同时完成时，`StreamingToolExecutor._run_parallel()` 启动的多个线程同时调用：

```
ToolRuntime.execute()
  -> ToolContext.shrink_observation()
       -> artifact_store.write_text() / write_json()
            -> _write_payload() -> _update_index() -> _write_index() -> _atomic_write_json()
```

多个线程竞争同一个 `artifacts/index.json.tmp` 文件和 `os.replace` 重命名操作。在 Windows 上，`os.replace` 对正在被其他句柄访问的目标文件会抛出 `WinError 32`；如果前一个线程的 `tmp` 文件刚好在替换后被删除/覆盖，后一个线程的 `os.replace` 会因源文件不存在而抛出 `WinError 2`。

### 1.2 设计层面的三重失效

1. **read-only 工具在运行时产生副作用**：`read_file` 被标记为 `read_only + concurrency_safe`，但 `shrink_observation()` 在工具执行后立刻写磁盘索引，违反了副作用-free 的语义承诺。
2. **并行执行共享单一可变文件热点**：所有工具共享 `artifacts/index.json` 这一个可变 JSON 索引。
3. **投影失败可回灌为工具失败**：当前 `shrink_observation()` 发生在 `ToolRuntime.execute()` 的主路径中（`tools/runtime.py:416`），如果 artifact 写失败，异常会被捕获并包装为 `Observation(success=False, ...)`，从而将本应是“投影层次要问题”的失败变成了“主工具执行失败”。

---

## 2. 影响面分析（按文件）

### 2.1 必须新建的核心模块

| 新文件 | 职责 | 与现有代码的对接点 |
|--------|------|-------------------|
| `src/embedagent/tool_commit.py` | 单写者 commit 层：接收 `Action + RawObservation + Session + ContextAssemblyResult`，执行 sanitize、字段外化、transcript 追加、projection 刷新 | 替换 `query_engine.py` 中 `_record_tool_observation` 的后半段逻辑；被 `query_engine._run_loop` 在每个 batch 结束后串行调用 |
| `src/embedagent/tool_result_store.py` | session-local immutable 文件存储：按 `session_id/tool_call_id/field_name.txt|json` 写入，保证 write-if-absent | 被 `tool_commit.py` 调用；替换 `ArtifactStore.write_text/write_json` 的底层行为 |
| `src/embedagent/projection_db.py` | SQLite projection 管理：包含 schema 升级、`tool_result_projection`、`session_projection`、project-memory 读模型 | 被 `tool_commit.py` 在 truth 提交后异步/同步刷新；替换 `ArtifactStore.index.json` 作为 listing 来源 |

### 2.2 必须修改的现有模块

#### `src/embedagent/artifacts.py` — 高风险
- **当前状态**：`ArtifactStore` 是 workspace-wide shared mutable 索引 + 文件 sanitize 的唯一入口。
- **变化**：设计方案要求“merged final state must not keep it as a live truth dependency”。
- **风险**：文件可直接删除或仅保留非 truth 的兼容 shim，但 `sanitizer` 逻辑（`_OPENAI_KEY_RE` 等）被 `SessionSummaryStore`、`ProjectMemoryStore` 多处复用。若直接删文件，需将 sanitize 逻辑迁移到新的共享位置（如 `tool_commit.py` 或独立 util）。

#### `src/embedagent/tools/_base.py` — 高风险
- **当前状态**：`ToolContext.shrink_observation()` 在工具 handler 返回后**立即**执行，直接写 `artifact_store`。
- **变化**：必须拆分为“执行层只返回 `RawObservation`（data 中保留完整原始字段）”，commit 层稍后决定哪些字段外化。
- **风险**：
  - 所有工具的 `handler` 当前不感知 shrink 逻辑，改变的是 `ToolRuntime.execute()` 的调用方式。但 `tools/_base.py` 中 `MAX_INLINE_ARTIFACT_TEXT_CHARS` 等常量需要被 commit 层复用。
  - `shrink_text_field` / `shrink_list_field` 当前在 observation 上直接修改 `data[field_name]` 为 preview 并注入 `field_name + "_artifact_ref"`。新设计改为注入 `field_name + "_stored_path"`，这一字段名改动会波及整个下游链。

#### `src/embedagent/tools/runtime.py` — 中高风险
- **当前状态**（`runtime.py:416`）：`observation = self._ctx.shrink_observation(tool.handler(arguments))`
- **变化**：`execute()` 不再调用 `shrink_observation()`，改为直接返回原始 observation。
- **风险**：`ToolRuntime` 的公共接口 `execute()` / `execute_with_interrupt()` 的返回语义会发生变化（从已 shrink 变为未 shrink）。所有调用方（`query_engine.py`、`inprocess_adapter.py` 等）必须确保自己进入 commit 层。漏改一处会导致大 payload 直接进入 LLM context，引发 token 超限。

#### `src/embedagent/query_engine.py` — 极高风险
- **当前状态**：`_record_tool_observation()` 在同一临界区内既追加 transcript event，又调用 `session.add_observation()`，还调用 `_persist_summary()`（后者触发 `SessionSummaryStore.persist` + `ProjectMemoryStore.refresh`）。
- **变化**：需要将事件流拆分为：
  1. `StreamingToolExecutor` 并行执行原始工具（返回 `RawObservation`）
  2. 串行 commit 层逐个处理 observation（写 tool-result 文件 → 追加 transcript `tool_result` + `content_replacement` → 更新 memory session → 触发 projection refresh）
- **风险**：
  - `_record_tool_observation` 当前在 `session_lock` 保护下运行，且同时做 transcript 写和 SQLite projection 写。新设计中 projection 必须在 transcript 之后，且 projection 失败不得向上抛错。
  - `_persist_summary()` 目前与 tool observation 强耦合。切分后，`QueryEngine` 需要显式在每个 batch/turn 结束时触发一次 summary refresh，而不是每次 tool finish 都触发。
  - `loop_guard.record(action, observation)` 当前使用的是已 shrink 后的 observation。如果 commit 层在 loop_guard 之后才执行，需要确认 loop_guard 对 `success` / `error` 的判定是否仍正确（原始 observation 和 shrink 后的 observation 在 success/error 上应完全一致）。

#### `src/embedagent/session.py` — 中风险
- **当前状态**：`add_observation()` 中 `replaced_by_refs` 的默认来源是 `_artifact_refs_from_observation()`，后者扫描 `data` 中所有以 `_artifact_ref` 结尾的字段。
- **变化**：如果使用新的 `_stored_path` 字段名，此处必须同步修改。
- **风险**：`TranscriptMessage.replaced_by_refs` 用于 `context.py` 中的 context assembly 和 resume replay。如果字段名切换遗漏，resume 时无法正确还原外部化引用，可能导致大文件内容重新被完整加载进 prompt。

#### `src/embedagent/context.py` — 极高风险
- **当前状态**：遍布多处硬编码的 `_artifact_ref` 后缀依赖。典型位置：
  - `MessageReducers._reduce_file()`（`content_artifact_ref`）
  - `MessageReducers._reduce_list()`（`files_artifact_ref`）
  - `MessageReducers._reduce_search()`（`matches_artifact_ref`）
  - `MessageReducers._reduce_command()`（`stdout_artifact_ref`, `stderr_artifact_ref`）
  - `MessageReducers._reduce_diagnostics_tool()`（`diagnostics_artifact_ref`）
  - `ContextManager._compact_tool_message_with_replacements()` 中大量基于 `_artifact_ref` 收集 `replacement["artifact_refs"]`，并生成 `replacement_text`
  - `ContextManager._analyze_context()` 通过 `_artifact_ref` 统计 replacement_count
- **变化**：
  - 要么将 `_artifact_ref` 全局替换为 `_stored_path`，要么保留旧字段名但由 commit 层在写入时同时填充（兼容性 hack，不推荐）。
  - `_compact_tool_message_with_replacements()` 生成 replacement text 的逻辑需要从 transcript 的 `content_replacement` 事件读取，而不是在 resume 时重新推导。当前代码在 context assembly 时**动态推导** replacement text，这意味着 resume 后的 replacement text 可能因代码逻辑变化而与原 session 不同（这正是设计方案 8.1 节指出的 drift 风险）。
- **风险**：`context.py` 是 prompt 组装的核心路径，任何字段名或 replacement 语义的错误都会直接影响 LLM 的输入，导致行为不可预测。

#### `src/embedagent/transcript_store.py` — 中风险
- **当前状态**：已支持 `append_event()`，使用 per-transcript-file 的 `threading.RLock` 保证串行追加。
- **变化**：需要新增支持 `content_replacement` 事件的精确持久化（其实当前 `query_engine.py` 已经写入了 `content_replacement`，但存储的是 `assembly.replacements` 列表，未显式包含 `stored_path` 和 `replacement_text` 的完整映射）。
- **风险**：
  - `TranscriptStore` 当前没有 schema migration 机制。如果 `content_replacement` payload 形状改变，旧 transcript 中已有的 `content_replacement` 事件与新事件会共存。`session_restore.py` 必须能同时解析新旧两种形状，或者 hard cutover 直接丢弃旧 session（设计方案已明确不迁移旧 session）。
  - commit 层现在会频繁 append `tool_result` + `content_replacement` 事件，追加频率与原来相同，但每个 observation 可能产生 1~N 个 `content_replacement`（如果多个字段被外化）。需测试 transcript 文件在高频追加下的 tail repair 稳定性。

#### `src/embedagent/session_restore.py` — 高风险
- **当前状态**：`SessionRestorer.restore()` 从 transcript replay 恢复 `Session`。对于 `content_replacement` 事件，它调用 `session.record_content_replacement()` 将 payload 存入 `session.content_replacements`，随后 `ContextManager` 在 build_messages 时读取该列表来填充 replacement。
- **变化**：设计方案要求“exact replacement text is restored from transcript without recomputation drift”。当前 restore 流程确实已经 replay `content_replacement` 事件，但 `ContextManager` 在 resume 后仍可能重新推导 replacement text（因为它在 `_compact_tool_message_with_replacements` 中基于 observation data 动态生成）。需要确保 resume 后的 context assembly**直接使用** transcript 中保存的 `replacement_text`，而不是重新走 `_compact_tool_message_with_replacements` 的推导逻辑。
- **风险**：
  - 旧 session 的 transcript 中的 `content_replacement` 事件格式与新格式可能不一致。hard cutover 策略下不可 resume 旧 session，这意味着 `resume_session` 必须在检测到旧格式时明确拒绝，而不是静默降级。
  - `inprocess_adapter.py` 中的 `resume_session()` 当前有 transcript missing → summary-based degraded replay 的降级路径。设计方案要求删除 summary-based resume fallback，这需要修改 `inprocess_adapter.py`。

#### `src/embedagent/session_store.py` — 中风险
- **当前状态**：`SessionSummaryStore` 是 `summary.json` + `sessions/index.json` 的读写器。它通过 `_collect_recent_artifacts()`、`_observation_snapshot()`、`_paths_from_observation()` 扫描 observation data 中的 `_artifact_ref` 字段来收集 artifact 引用。
- **变化**：
  - 字段名需要适配 `_stored_path`。
  - `summary.json` 被降级为可选 projection，但 `inprocess_adapter.get_session_snapshot()` 仍大量读取 summary 数据来填充前端状态。在 projection DB 尚未完全替代 summary listing 之前，summary  dumping 仍需短期保留。
- **风险**：`cleanup()` 使用 `_atomic_write_json` 写 `sessions/index.json`，这是另一个共享可变 JSON 索引。设计方案虽未明确要求删除 `sessions/index.json`，但按照同一原则，它也应被 SQLite 替代或至少不再作为 truth。建议在切变中一并移除 `sessions/index.json` 的写依赖，至少不将其作为 resume 的 truth。

#### `src/embedagent/project_memory.py` — 中风险
- **当前状态**：使用 `_artifact_refs()` 方法从 observation data 中提取 `_artifact_ref` 字段保存到 issue 记录中。
- **变化**：需要改为识别 `_stored_path`。
- **风险**：`refresh()` 方法在每次 `_persist_summary()` 时被调用，当前将 recipes/issues 写为 JSON 文件。设计方案要求 project-memory 改为 SQLite 表（`project_memory_recipe`、`project_memory_issue`）。`project_memory.py` 当前的所有读写逻辑需要被 `projection_db.py` 替代或重构。这是一个较大的变动面，但 projection 失败不应影响主流程成功。

#### `src/embedagent/memory_maintenance.py` — 中高风险
- **当前状态**：`run()` 调用 `summary_store.cleanup()`、`project_memory_store.cleanup()`、然后收集 active artifact refs 调用 `artifact_store.cleanup(active_refs)`。
- **变化**：`ArtifactStore` 消失后，cleanup 的来源和方式都要改变：
  - active refs 的来源应从 `projection_db` 的 `tool_result_projection` 表查询，或者直接从 transcript replay 推导。
  - 清理对象从 `artifacts/` 目录变为 `sessions/<session_id>/tool-results/` 目录。
- **风险**：如果 cleanup 逻辑错误，可能误删当前活跃 session 的 tool-result 文件，导致 resume 时 replacement 指向不存在的文件，触发 restore 失败。

#### `src/embedagent/inprocess_adapter.py` — 极高风险
- **当前状态**：
  - `list_artifacts()` 和 `read_artifact()` 直接调用 `self.tools.artifact_store` 暴露给前端 API（`inprocess_adapter.py:838-842`）。
  - `resume_session()` 优先尝试 `summary_store.load_summary(reference)`，如果 transcript missing 则走 degraded replay（`timeline_replay_status: "degraded"`），并生成一个空 session。
- **变化**：
  - `list_artifacts()` / `read_artifact()` 必须改为查询 `projection_db`。
  - `resume_session()` 必须改为仅通过 `transcript.jsonl` 恢复，删除 summary-based fallback。如果 transcript 不存在，应明确报错而不是生成空 session。
- **风险**：
  - 前端 Inspector（TUI/GUI）依赖 `list_artifacts` API 返回的 listing 结构。如果新 backend 返回的字段名或结构不同，前端解析可能失败。
  - 旧格式 session 的恢复路径被移除，用户升级后将无法继续之前未完成的会话。需要在产品层面给出明确提示。

---

## 3. 前端/UI 对接风险

### 3.1 GUI 前端

在 `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx:597-618` 中，前端直接使用 `diff_artifact_ref` 判断是否存在 artifact 详情可查看。新的字段名如果是 `diff_stored_path`，前端逻辑必须同步更新，否则 Inspector 中的 artifact 展开/下载按钮会消失。

### 3.2 TUI 前端

`src/embedagent/frontend/tui/reducer.py:111` 和 `views/inspector.py:53-56` 引用了 `selected_artifact_ref` 状态字段。虽然 TUI 展示的是字符串文本，但如果 backend adapter (`inprocess_adapter`) 的 `list_artifacts()` 返回的字段名从 `path` 变为 `stored_path`，TUI 的 inspector 列表渲染也需要同步修改。

### 3.3 API 契约风险

`inprocess_adapter.py` 中的 `list_artifacts` 和 `read_artifact` 是 frontend API 的公开端点。若临时采用分支本地 shim 过渡，需确保前端不会在 merge 后仍调用已删除的 `ArtifactStore` 方法。建议在裁剪旧路径前，先完成 `projection_db` 对这两个 API 的支撑。

---

## 4. Windows 特定问题

### 4.1 `os.replace` 的跨目录限制

Windows 7 + Python 3.8 下，`os.replace` **不能跨文件系统/驱动器**工作。新设计避免了跨目录重命名共享文件，但仍需注意：`tool_result_store.py` 若采用“不同目录临时文件 + 重命名到目标”策略，必须保证 tmp 文件与目标文件在同一目录内。

**建议**：session-local 文件直接写入目标路径（`tool-results/<call_id>/content.txt`），不再使用 tmp-rename 模式。因为同一 `tool_call_id + field_name` 只会被写一次，不存在并发覆盖需求。

### 4.2 目录创建的竞态

```python
os.makedirs(directory, exist_ok=True)
```

在 Python 3.8 的 Windows 实现中，如果两个线程同时尝试创建同一目录树，`exist_ok=True` 通常能处理 `FileExistsError`，但如果路径的中间节点以特定时序被创建，仍可能抛出异常。`tool_result_store.py` 应在创建目录时捕获 `OSError`/`FileExistsError` 并做防御性重试。

### 4.3 SQLite 文件锁与单写者

Windows 上 SQLite 的默认文件锁行为比 POSIX 更严格。如果 commit 层未能严格保证单写者，多个线程同时写入 `projections.sqlite3` 可能遇到 `database is locked` 错误。

**建议**：在 `query_engine.py` 或 `inprocess_adapter.py` 中，用一个显式的 `threading.Lock` 保护整个 commit 层调用（写 transcript + 写 tool-result 文件 + 写 SQLite），而不是依赖 SQLite 的 WAL 模式（Python 3.8 默认 WAL 可能未在所有 Windows 环境下启用）。

### 4.4 句柄保持时间

Windows 对打开文件的删除/重命名比 Unix 更敏感。当前 artifact 写失败的一个可能原因是 `_update_index()` 在读取 `index.json` 后句柄保持时间过长（虽然代码中使用的是 `with open(...)` 上下文管理器，理论上应立即关闭，但 `os.replace` 仍可能因进程内其他线程持有句柄而失败）。新设计移除了共享 JSON index，彻底根除了这一类问题。

---

## 5. 与系统其余部分的对接风险

### 5.1 Session Timeline / Event Stream

`SessionTimelineStore` 当前独立于 transcript store，记录事件流用于 TUI timeline 展示。`tool_commit.py` 在追加 transcript event 时，也需考虑是否需要同步追加 timeline event。如果 timeline store 仍依赖 summary 或 artifact index 的某些元数据，则需要同步适配。

### 5.2 Plan Store / Todo Store

`plan_store.py` 和 `todo_store.py` 当前不直接依赖 artifact store，但 `inprocess_adapter.py` 在 `create_session()` 和 `resume_session()` 时会调用 `todo_store.ensure_session_todos()`。若 resume 路径被 hard cutover 限制（旧 session 不可 resume），todo 的 seed_from_legacy 逻辑可能也需要收紧。

### 5.3 Workspace Intelligence Broker

`WorkspaceIntelligenceBroker` 在 `query_engine._build_context()` 中被调用，当前通过 `session` 和 `tools` 收集信息。只要 `session` 的 `add_observation()` 接口保持稳定（success/error/data 结构不变），intelligence broker 不应受直接影响。但如果 observation `data` 中的字段名从 `_artifact_ref` 变为 `_stored_path`，broker 中若有基于 artifact_ref 的解析逻辑，则需同步更新。

### 5.4 Context Assembly 中的 Budget 与 Analysis

`ContextManager._analyze_context()` 通过扫描 `_artifact_ref` 计算 `artifact_replacement_count`。若字段名改变，该统计会归零，可能导致上下文分析报告失真。此外，`_budget_for_chars()` 依赖的是 message content 的字符数。commit 层的 replacement text 如果比原 content 更长或更短，会影响 budget 估算。这也是设计方案要求“将 replacement text 原样持久化”的原因之一——确保 resume 时 budget 保持一致。

---

## 6. 测试覆盖缺口

### 6.1 当前已有测试

- `tests/test_query_engine_refactor.py`
- `tests/test_inprocess_adapter_frontend_api.py`

这两组测试需要扩展以下用例：
1. 同一 step 内并行调用 3+ 个 `read_file` 不再引发 artifact index 竞争错误。
2. projection_db 写入失败（如通过 mock 抛 `sqlite3.OperationalError`）不会将 observation 的 `success` 变为 `False`。
3. `summary.json` 被删除后，resume 仍能完全通过 `transcript.jsonl` 成功恢复。
4. 旧格式 session 被拒绝 resume（返回明确的错误而非 degraded replay）。

### 6.2 需要新增测试

- `tests/test_tool_commit.py`：验证 commit 层的串行语义、字段外化策略、content_replacement 事件格式、projection 刷新失败不抛错。
- `tests/test_tool_result_store.py`：验证 per-session/per-tool_call_id 目录隔离、write-if-absent 语义、Windows 目录竞态防御。
- `tests/test_projection_db.py`：验证 schema 创建、`tool_result_projection` 和 `session_projection` 的 CRUD、project-memory 表读写、删除 SQLite 后从 transcript 重建的能力。
- `tests/test_session_restore_cutover.py`：验证新格式 transcript 的 resume 与原 session 的 prompt 完全一致（精确 replacement text 回归）。

### 6.3 集成测试缺口

当前没有覆盖以下场景的端到端测试：
- **transcript + tool-results 重建投影**：删除 `projections.sqlite3` 和所有 `summary.json`，仅保留 `transcript.jsonl` 和 `tool-results/` 文件，验证系统能否自动重建 listing 和 resume。
- **cleanup 不删除活跃文件**：模拟一个 aging session 被 cleanup 扫描，验证其 `tool-results/` 目录不会被误删。
- **多字段外化**：一个工具调用同时产生大 `stdout`、`stderr`、`diagnostics`，验证 3 个字段分别被外化到独立文件，且 replacement text 正确引用。

---

## 7. 结论与建议

### 7.1 方案能否有效解决问题？

**能。** 该方案直击当前并发出错的根因：
- 移除 `artifacts/index.json` 共享可变索引 → 消除竞争热点。
- 移除固定名称临时文件 `*.tmp` 的 `os.replace` → 消除 Windows 上的 `WinError 2/32`。
- 工具执行层不再调用 `shrink_observation()` → read-only 工具真正无副作用，并行安全。
- 单写者 commit 层 → 所有共享磁盘写操作串行化，避免并发文件系统冲突。

### 7.2 最大的实施风险是什么？

1. **`context.py` 的字段名切换和 replacement drift 控制**：这是 prompt 正确性的生死线。如果 `_artifact_ref` 到 `_stored_path` 的迁移遗漏了任意一处，resume 或 context assembly 时就会出现大 payload 泄漏或 replacement text 错误。
2. **前端 API 的 artifact listing 来源切换**：`inprocess_adapter.py` 的 `list_artifacts` / `read_artifact` 必须无缝切换到 SQLite，否则前端 Inspector 会白屏或功能缺失。
3. **旧 session resume 路径的移除**：这是 hard cutover 的显著 UX 影响，需要与前端/产品层对齐，避免用户升级后发现历史会话不可恢复。

### 7.3 实施顺序建议（风险最小化）

1. **先建新基座**：实现 `tool_result_store.py` 和 `projection_db.py`（不接入主流程），并配齐单元测试。
2. **改造执行层**：修改 `tools/runtime.py` 去掉 `shrink_observation()`，确保 `execute()` 返回原始 observation；此时 `query_engine.py` 的 commit 层尚未接入，临时用一个 adapter 在 `query_engine` 中做兼容 shrink。
3. **实现 commit 层**：在 `query_engine.py` 中引入 `ToolCommit`，将 `_record_tool_observation` 的 transcript 写、session 更新、projection 刷新迁移进去。
4. **适配 context assembly**：修改 `context.py` 支持 `_stored_path` 和 transcript-persisted replacement text，确保 resume 无 drift。
5. **替换前端 listing 来源**：将 `inprocess_adapter.py` 的 `list_artifacts` / `read_artifact` 切换到 `projection_db`。
6. **清理旧路径**：删除或废弃 `artifacts.py`、移除 summary-based resume fallback、更新 memory_maintenance 的 cleanup 逻辑。
7. **端到端回归**：跑通新增集成测试，确认并行 read_file 不再报错、projection 失败不降级 tool success、旧 session 被拒绝 resume。

---

*分析完成。本文件应与设计文档 `docs/superpowers/specs/2026-04-05-transcript-truth-tool-result-cutover-design.md` 一并阅读，作为实施前的检查清单使用。*