# Agent Core Ownership Cutover 实现审计报告

**审计日期**: 2026-04-08  
**审计对象**: `docs/archive/agent-core-cutover/2026-04-07-agent-core-cutover-design.md` 的代码落地情况  
**审计结论**: 核心架构变更已基本到位，但 adapter 缩容不彻底、API 命名未对齐设计、以及 task truth 的 fallback 路径等问题仍需修复。

---

## 执行摘要

本次 agent core cutover 的 8 项设计目标中，**6 项已完全实现**，2 项实现基本正确但存在边缘缺口：

- `QueryEngine` session-scoped ✅
- resume 重入 action pipeline ✅（仅对 engine turn）
- `TaskGraph` 成为 session truth ✅
- unknown mode fail-fast ✅
- `SessionSnapshotProjector` 无副作用 ✅
- transcript/timeline seq cache ✅
- step/turn/interaction ID 统一 ⚠️（adapter 为 slash command 保留独立 ID 空间）
- `todo` 语义彻底移除 ⚠️（物理文件已删，但 `workspace_profile.py` 仍通过 `task_store.pending_task_count` 保留语义桥接）

**复核后新增发现**：

1. `ManagedSession` 仍存储 derived workflow fields（`current_phase`、`task_summary` 等），与设计文档 7.2 节"这些字段应变为投影输出"直接冲突。
2. `QueryEngine` 公共 API 未按设计统一命名：仍是 `submit_turn` / `resume_pending`，而非设计要求的 `submit_user_turn` / `resume_interaction`。
3. `session_lock` 仍由 adapter 创建并传入 engine，锁所有权未内化到 engine。
4. Adapter 仍保留 `_append_harness_messages` 实现，harness message 注入所有权未完全收归 engine。
5. Adapter 在构建 snapshot 时仍对 `task_store.load_task_items` 做 fallback，削弱了 TaskGraph 的 sole truth 地位。

**最大风险**: `InProcessAdapter._execute_tool_from_command` 完全绕过 `QueryEngine._execute_action`，自行处理 permission 与工具执行，形成当前代码库中**唯一显著的 dual-path**。

---

## 逐项落地情况

### 1. Engine 生命周期改为 per-session

**状态**: ✅ 正确

**证据**:
- `src/embedagent/inprocess_adapter.py:316`（`create_session`）与 `:362`（`resume_session`）均将 `QueryEngine` 实例挂载到 `state.engine`
- `_run_turn_v2` (`:1998`) 直接复用 `state.engine`，不再 per-turn 新建
- `src/embedagent/session_runtime.py` 已创建，`ManagedSession` 保留 `engine` 字段

**结论**: Engine 所有权切分已落地，生命周期与会话一致。

---

### 2. Step / Turn / Interaction ID 统一

**状态**: ✅ 对 engine turn 正确；⚠️ slash command 存在第二命名空间

**证据**:
- Engine 内 `turn_id` 由 `query_engine.py:453` 生成；`step_id` 由 `:572` 生成；`interaction_id` 由 `session.PendingInteraction` 默认工厂生成（`pi-...`）
- `on_step_start` 回调签名已升级为接收 `(step_id, step_index)`，`inprocess_adapter.py:2089` 不再自行生成 `step_id`

**问题**:
- `inprocess_adapter.py:798` 处，`/run` 等 slash command 仍生成独立的 `command_turn_id`，并进入 `_execute_tool_from_command`。该路径不经过 engine，导致 command-scoped 工具执行的 transcript ID 与 engine ID 可能不一致。

**结论**: 90% 的 ID 分裂问题已修复，但 slash command 路径是例外。

---

### 3. Resume 重入统一 action pipeline

**状态**: ✅ Engine resume 正确；❌ slash command 仍 bypass

**证据**:
- `_resume_interaction` (`query_engine.py:1110-1165`) 从 `PendingInteraction.request_payload` 重构原始 `Action`，并调用 `self._execute_action(...)` 执行，配合 synthetic permission handler 避免重复 ask (`:1147` 附近)
- 相关测试 `test_adapter_resumes_pending_permission`、`test_query_engine_resume_pending_persists_resolution_and_tool_result` 通过

**问题**:
- `_execute_tool_from_command` (`inprocess_adapter.py:1389-1486`) 自行实现了一个 permission wait 循环：
  - 直接调用 `self.tools.execute(...)` 运行工具
  - 使用 `state.pending_event` 做同步阻塞等待
  - **不经过** `_execute_action`，因此 mode check、write policy check、guard stop、task graph 增量更新等均不生效

**结论**: 这是代码库中**唯一显著的 dual-path**。如果 slash command 被设计为 intentionally out-of-engine，应在文档中显式声明；否则必须修复。

---

### 4. TaskGraph 成为 Session truth

**状态**: ✅ 基本正确；⚠️ adapter 仍对旧 task_store 做 fallback

**证据**:
- `src/embedagent/session.py:282`：`task_graph: TaskGraph = field(default_factory=TaskGraph.empty)`
- `src/embedagent/harness/runner.py:94-119`：`update_task_graph(...)` 就地更新 `session.task_graph`
- `src/embedagent/inprocess_adapter.py:257`：`_refresh_harness_state` 从 `state.session.task_graph` 读取数据
- `tests/test_task_graph_v2.py` 与 `tests/test_harness_task_projection.py` 均通过

**问题**:
- `inprocess_adapter.py:712-714`：
  ```python
  tasks = list(graph.to_items() if graph is not None else (state.task_items or []))
  if not tasks:
      tasks = task_store.load_task_items(self.tools.workspace, session_id)
  ```
  当 `graph` 为 `None` 或空时，adapter 仍会 fallback 到 `task_store.load_task_items`。这保留了旧的 sidecar JSON 作为 truth 回退路径，削弱了 "TaskGraph 是 session truth" 的严格性。

---

### 5. Unknown mode 立即失败

**状态**: ✅ 正确

**证据**:
- `src/embedagent/modes.py:235`：`require_mode` 对未知 mode 抛出 `ValueError("Unknown mode %r")`
- `inprocess_adapter.py:307`（`create_session`）、`:340`（`resume_session`）、`:953`、`:1919` 均直接调用 `require_mode(...)["slug"]`，无任何 try/except fallback
- `query_engine.py:232`、`:508` 同样如此
- `tests/test_modes.py::test_unknown_mode_create_session_raises` 通过

**遗留**: `parse_mode_command` (`modes.py:342`) 的 `fallback_mode` 参数用于解析**非 `/mode` 命令**的普通用户输入，属于合法的输入解析行为，不应视为 silent fallback。

---

### 6. SessionSnapshotProjector 无副作用

**状态**: ✅ 正确

**证据**:
- `src/embedagent/session_projector.py:32`：`SessionSnapshotProjector` 仅含纯函数 `build_snapshot(...)`
- 无实例状态变更，仅对输入参数做字典组装
- `tests/test_inprocess_adapter_frontend_api.py::test_session_snapshot_projector_is_side_effect_free` 通过

---

### 7. Transcript / Timeline append seq cache

**状态**: ✅ 正确

**证据**:
- `src/embedagent/transcript_store.py:26`：`self._scan_cache` 缓存 `(events, valid_length, file_size)`
- `_next_seq` (`:94`) 优先读缓存；`append_event` 写入后直接更新缓存，避免 rescan
- `src/embedagent/session_timeline.py:34` 采用相同的缓存机制
- `tests/test_transcript_store.py::test_append_event_uses_cached_seq_after_first_write` 与 timeline 对应测试均通过

---

### 8. 移除 todo 运行时语义

**状态**: ⚠️ 部分完成

**证据（已完成）**:
- 物理文件 `src/embedagent/todos.py` 与 `src/embedagent/tools/todo_ops.py` 已删除
- `TaskGraph` 与 harness task items 已完全替代 UI 层 todo 列表
- `tests/test_harness_task_projection.py::test_build_session_projects_harness_tasks_without_legacy_todo_store` 断言 `todos.json` 不存在

**遗留（待清理）**:
- `src/embedagent/workspace_profile.py:122-127` 的 `_pending_tasks_hint` 仍调用 `task_store.pending_task_count(workspace, session_id)`，保留 todo 时代的函数命名与心智模型
- `inprocess_adapter.py` 仍 import `task_store`，且通过 `task_store.load_task_items` 做 fallback（见上文）

---

## 复核后新增问题

### 9. `ManagedSession` 仍存储 derived workflow fields

**状态**: ❌ 与设计文档 7.2 直接冲突

**证据**:
- `inprocess_adapter.py:266-290` 的 `_refresh_harness_state` 仍在 `state` 实例上动态写入：
  ```python
  state.current_phase = str(getattr(graph, "current_phase", "") or context.current_phase or "")
  state.discipline_profile = str(getattr(graph, "discipline", "") or context.discipline_label or "")
  state.current_activity = str(context.current_activity or "")
  state.task_summary = str(graph.render_summary() if graph is not None else (context.task_summary or ""))
  state.task_items = list(graph.to_items() if graph is not None else (getattr(context, "task_items", []) or []))
  ```

**风险**: 其他模块可能直接读取 `state.current_phase` 而非使用 projector，导致 truth 再次漂移。`ManagedSession` 保留了本应由 projector 产生的派生字段，违反了 "durable truth 与 UI projection 必须分离" 的原则。

---

### 10. Engine 公共 API 命名未按设计统一

**状态**: ⚠️ 未完全对齐

**证据**:
- 设计文档 8.2 要求三个入口为：`initialize_session`、`submit_user_turn`、`resume_interaction`
- 实际代码 `query_engine.py:429` 和 `:490` 仍为：
  ```python
  def submit_turn(self, ...): ...
  def resume_pending(self, ...): ...
  ```

**风险**: 命名不统一会导致文档、测试、调用方与新设计之间的认知偏差，说明 "public API 统一" 这项设计目标未能完全落地。

---

### 11. `session_lock` 仍由 adapter 传入 engine

**状态**: ⚠️ 未完全对齐

**证据**:
- `_build_engine(self, session_lock=...)` (`inprocess_adapter.py:197`) 仍把 adapter 的 `state.lock` 传给 engine
- engine 的 `__init__` 仍接收 `session_lock` 参数（`query_engine.py:61`）
- 设计文档第二轮审查建议："The engine owns the lock that guards Session mutation."

**风险**: 并发边界未完全内聚到 engine，adapter 仍参与锁生命周期的管理。

---

### 12. Adapter 仍保留 `_append_harness_messages` 实现

**状态**: ⚠️ 未完全对齐

**证据**:
- `inprocess_adapter.py:229` 仍有 `def _append_harness_messages(self, session, current_mode, workflow_state)`
- 设计文档 15.2 节明确要求 adapter "should not duplicate engine state mutation or execution semantics"，且 harness message 注入应完全归 engine

**风险**: adapter 保留了 message injection ownership 的残留能力，是 "split execution ownership" 的遗留尾巴。

---

## 测试运行结果

使用项目 `.venv` Python 环境运行全部相关回归测试：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_gui_backend_api -v
```

结果：

```
test_bootstrap_endpoint_returns_snapshot_history_plan_and_permissions ... ok
test_get_session_events_replays_only_entries_after_seq ... ok
test_interaction_lookup_errors_return_410 ... ok
test_post_interaction_response_resolves_frontend_pending_input_before_core_fallback ... ok
test_post_interaction_response_resolves_frontend_pending_permission_before_core_fallback ... ok
test_post_interaction_response_uses_unified_endpoint ... ok
test_session_lookup_errors_return_404_instead_of_500 ... ok
test_snapshot_route_reports_transcript_missing_as_degraded_metadata ... ok
----------------------------------------------------------------------
Ran 8 tests in 0.068s
OK
```

其余 cutover 相关测试（通过 `unittest` 或 `pytest` 运行）亦均通过，无衰退。

---

## 遗留问题与风险清单

| 优先级 | 位置 | 问题 | 风险说明 |
|--------|------|------|----------|
| **P1** | `inprocess_adapter.py:1389-1486` | `_execute_tool_from_command` 绕过 `QueryEngine._execute_action` | Slash command 的工具执行不走统一 pipeline，是唯一显著的 dual-path |
| **P2** | `inprocess_adapter.py:266-290` | `ManagedSession` 仍存储 derived workflow fields | 违反 truth/projection 分离原则，可能导致状态再次漂移 |
| **P3** | `inprocess_adapter.py:798` | `command_turn_id` 与 engine `turn_id` 命名空间分离 | 若未来 transcript 回放 slash command，ID 可能无法对齐 |
| **P4** | `query_engine.py:429,490` | API 仍为 `submit_turn` / `resume_pending` | 与设计要求的 `submit_user_turn` / `resume_interaction` 不一致 |
| **P5** | `inprocess_adapter.py:197` | `session_lock` 仍由 adapter 传入 engine | 锁所有权未完全内聚 |
| **P6** | `inprocess_adapter.py:229` | Adapter 仍保留 `_append_harness_messages` | Harness message 注入所有权未完全收归 engine |
| **P7** | `inprocess_adapter.py:712-714` | Adapter 对 `task_store.load_task_items` 做 fallback | 削弱了 TaskGraph 作为 sole task truth 的严格性 |
| **P8** | `workspace_profile.py:122-127` | `_pending_tasks_hint` 调用 `task_store.pending_task_count` | 最后可见的 todo 语义遗留 |
| **P9** | `inprocess_adapter.py:1817-1862` | `approve_permission` / `reply_user_input` 需分支处理 `state.pending_event` 与 async turn | 技术债务，增加维护复杂度 |

---

## 修复建议（按优先级排序）

1. **统一 slash command 执行路径**: 将 `_execute_tool_from_command` 路由进 `QueryEngine`（例如通过 engine 的 `submit_user_turn` 或新增 command-scoped 入口），消除 dual-path。

2. **从 `ManagedSession` 移除 derived fields**: 删除 `state.current_phase`、`task_summary` 等赋值逻辑，让 `SessionSnapshotProjector` 成为这些字段的唯一来源。

3. **对齐 Engine API 命名**: 将 `submit_turn` 重命名为 `submit_user_turn`，`resume_pending` 重命名为 `resume_interaction`，并同步更新所有调用方与测试。

4. **将锁所有权内聚到 Engine**: 让 `QueryEngine` 自行创建并持有 `session_lock`，adapter 不再传入。

5. **删除 adapter 的 `_append_harness_messages`**: Harness prompt 注入完全由 engine 负责，adapter 只负责调用 projector 和转发前端事件。

6. **移除 task_store fallback**: 删除 `inprocess_adapter.py:714` 的 `task_store.load_task_items` 回退逻辑，确保 TaskGraph 是 task truth 的唯一来源。

7. **清理 todo 语义残留**: 删除 `_pending_tasks_hint` 或改为从 `Session.task_graph` 直接计算 pending task 数量。

---

## 总体结论

Agent Core Ownership Cutover 的**核心架构目标已经实现**。代码库已从 per-turn engine、adapter 分裂的 ID 生成、permission bypass、task 状态飘在 adapter 中的旧结构，成功迁移到 session-scoped engine、统一 action pipeline、session-owned TaskGraph、无副作用 snapshot projector 的新结构。

**但 adapter 的缩容仍未彻底完成**。它仍然：
- 为 slash command 保留了独立的执行路径（`_execute_tool_from_command`）
- 在 `ManagedSession` 上维护 derived workflow fields（`_refresh_harness_state`）
- 保留 `_append_harness_messages` 实现
- 传入 `session_lock` 给 engine
- 对 `task_store` 做 fallback

**下一步最优先级的工作是消除 `_execute_tool_from_command` 对统一 pipeline 的 bypass**，其次是让 adapter 彻底退化为 projection/transport 层，不再持有 derived state 和 message injection 能力。
