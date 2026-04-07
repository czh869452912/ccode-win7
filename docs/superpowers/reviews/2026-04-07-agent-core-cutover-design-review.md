# Agent Core Ownership Cutover 设计审查报告

**审查日期**: 2026-04-07
**审查对象**: `docs/superpowers/specs/2026-04-07-agent-core-cutover-design.md`
**对比参照**: `reference/claude-code` 源码
**审查结论**: 方案整体设计合理，问题诊断精准，实施方向正确。

---

## 一、总体判断

该方案准确地指出了当前 EmbedAgent 核心在架构层面的结构性病灶：

- `QueryEngine` 是每轮新建（per-turn），而非会话级（per-session）持有。
- Adapter 与 Engine 双重生成 `turn_id` / `step_id`，双重注入 harness message。
- Permission resume 直接调用 `tools.execute()`，绕过完整的 action pipeline。
- Task 状态（`current_phase`、`task_summary`、`task_items`）飘在 `ManagedSession` 中，没有持久化进入 `Session`。
- Transcript append 存在 O(n) 写放大：每次写入前都通过 `_scan_events()` 重新扫描整个 JSONL 文件。
- `todo` 词汇在运行时残留（`todos.py`、`task_status` renderer key 等）。

方案提出的 **"一个 domain 只有一个 owner"** 的原则，以及 **" durable truth 与 UI projection 必须分离"** 的分层思想，是根治这些问题的正确方向。由于产品尚未发布、明确不需要 legacy 兼容，这种"无 fallback、无 shim"的激进切变是合理且值得执行的。

---

## 二、分项对照评估

### 1. Engine 所有权切分（Phase 1）— 完全正确且优先级最高

#### 当前代码事实

- `InProcessAdapter._run_turn_v2()` 在 **每次用户输入时新建 `QueryEngine`**（`inprocess_adapter.py:2060`）。
- Engine 被传入 `session_lock=state.lock`，但本身不持有任何会话级状态。
- `ManagedSession` 中 **没有 `engine` 字段**。

#### Claude Code 参考

- Claude Code 的 `QueryEngine`（`src/QueryEngine.ts`）是 **per-conversation** 的，持有 `mutableMessages`（可变消息列表）、`readFileState`（文件读取缓存）、`abortController`、`permissionDenials`（记录被拒工具以辅助后续决策）、`totalUsage` 等。
- 这避免了每次 turn 重建时重新初始化缓存和跟踪状态，保证了会话内的执行一致性。

#### 评估与建议

方案要求 `ManagedSession` 持有稳定 `engine` 引用，与 Claude Code 的设计一致。**这是所有改动的根基，优先级最高。**

> **优化建议**：在切到 per-session engine 时，同步审查 `QueryEngine.__init__` 中的状态。例如 `_maintenance_counter` 当前在 `__init__` 中初始化为 0，由于之前每 turn 重建引擎，该计数器实际上不会被正确累积。切到 per-session 后，这些状态才会真正生效，需确保其业务语义仍是预期的。

---

### 2. ID 统一（turn_id / step_id / interaction_id）— 方案正确，但有一个隐藏陷阱

#### 当前代码事实

| ID | Adapter 生成 | Engine 生成 | 写入 transcript 来源 |
|---|---|---|---|
| `turn_id` | ✅ `inprocess_adapter.py:2050` | ✅ `query_engine.py:418` | Adapter 的传给 `session.add_user_message()`；Engine 生成的用于 `message` event 和 `step_started` event |
| `step_id` | ✅ Adapter 回调 `on_step_start` (2090) | ✅ `query_engine.py:537` | Engine 调用 `session.begin_step(step_id)` 时，实际使用的是 adapter 回调里生成的 `current_step["step_id"]` |
| `interaction_id` | ❌ | ✅ `session.py:181` (`PendingInteraction`) | Session 生成 |
| `permission_id` | ✅ `perm_...` (2279) | ❌ | Adapter 独自生成，与 `PendingInteraction.interaction_id` 不一致 |
| `request_id` (user input) | ✅ `ask_...` (2304) | ❌ | Adapter 独自生成 |

**核心问题**：Adapter 和 Engine 各自生成 `turn_id`。`Adapter` 在 2050 行生成一个用于前端事件，`QueryEngine.submit_turn()` 又在 418 行生成一个自己的 `turn_id`，并通过 `_append_message_event` 写入 transcript。虽然 `session.add_user_message()` 接收了 adapter 的 turn_id，但 engine 内部事件（如 `step_started`）记录的 turn_id 与 adapter 事件中的 turn_id 在来源上是分离的。

此外，**`PermissionTicket.permission_id` 和 `UserInputTicket.request_id` 是 Adapter 层面独立生成的**，与 `PendingInteraction.interaction_id`（`pi-...`）不是同一个值。这破坏了方案所要求的"transcript、event stream、session history、frontend timeline 都是同一个执行对象的投影"。

#### Claude Code 参考

- Claude Code 没有显式的 "step" 粒度 ID，它用 `queryTracking.chainId/depth` 跟踪递归深度。
- `turnId` 是 autocompact 窗口跟踪用的，在 compact 成功后由 `query.ts` 生成。
- Message 级别的 UUID 几乎统一由底层 `randomUUID()` 生成。

#### 评估与建议

方案要求 **"Engine 是唯一来源"** 是正确的。但需注意：当前的 `PermissionTicket` / `UserInputTicket` 拥有独立的 ID 命名空间，方案中 9.3 节提到的 `PendingInteraction.request_payload` 必须携带 `turn_id`、`step_id`、`interaction_id`，这是修复 identity 分裂的关键。

> **优化建议**：
> 1. 删除 Adapter 层对 `turn_id` 和 `step_id` 的生成逻辑。`on_step_start` 回调应从 Engine 接收已生成的 `step_id`，而不是在回调内部新建一个。
> 2. `PermissionTicket.permission_id` 和 `UserInputTicket.request_id` 应该直接等于 `PendingInteraction.interaction_id`（或建立严格的 1:1 映射）。Adapter 的 ticket 对象只是投影层包装，不应拥有自己的 identity。
> 3. 将 `PendingInteraction.request_payload` 规范化为严格的 execution checkpoint，包含：
>    - `action` (序列化)
>    - `turn_id`
>    - `step_id`
>    - `interaction_id`
>    - `kind`
>    - 交互特有的请求数据
>
>    这样 transcript replay 和 live resume 才能共用同一套信息模型。

---

### 3. Harness Message 双重注入 — 确实存在，但比文档描述的更隐蔽

#### 当前代码事实

- **Adapter 层**：`InProcessAdapter._append_harness_messages()` (248) 存在，在 `create_session()` (343) 中调用。
- **Engine 层**：`QueryEngine._append_harness_messages()` (188) 也存在，在 `submit_turn()` (415) 和 `resume_pending()` (475) 中调用。
- 两者都实现了"如果已存在相同 `mode_name` + `discipline_label` 的 `harness_prompt` system message 则跳过"的去重逻辑。

这意味着：**功能上目前不会插入重复 harness message**，但架构上存在两处独立维护的相同逻辑，属于所有权分裂。

#### 评估与建议

> **优化建议**：切到 engine per-session 后，harness message 注入完全归 Engine 所有。Adapter 层的 `_append_harness_messages` 应删除。`create_session()` 中需要在初始化 engine 时触发一次等效的 harness injection，或者由 engine 在首次 `submit_turn()`（即使 `user_text` 为空）时自动完成。

---

### 4. Permission Resume Bypass（Phase 2）— 当前代码中最严重的设计缺陷

#### 当前代码事实

`QueryEngine._resume_interaction()`（`query_engine.py:1059-1151`）中对 permission 的处理：

```python
if pending.kind == "permission":
    approved = bool(resolution.get("approved"))
    observation = (
        self.tools.execute(action.name, action.arguments)   # ← 直接执行！
        if approved
        else self._failure_observation(...)
    )
```

这段代码完全**绕过了**：
- 当前 mode 允许的工具检查（mode tool availability）
- Permission policy 的重新评估（如果规则在 suspend 期间发生变化）
- Mode/path write validation（如 `is_path_writable`）
- 任何 `_execute_action` 中可能存在的 pre/post hook

这意味着 approval 时的执行语义与首次执行语义不一致，是架构不安全的根源。

#### Claude Code 参考

- Claude Code 在 **REPL/交互模式** 下，orphaned permission 会被 enqueue 回正常输入队列，**重新进入主 pipeline**。
- 但在 **SDK/headless 模式** 下，Claude Code 也存在 bypass：通过 `handleOrphanedPermission()` 构造一个 fake `canUseTool`，直接调用 `runTools()`。

#### 评估与建议

你的方案比 Claude Code 的 SDK 路径更进一步，要求任何 resume 都必须重新走完整 pipeline。**这是正确的，而且技术上完全可以做到，应当执行。**

> **优化建议**：
> 修改 `_resume_interaction`，让它不再直接调用 `self.tools.execute()`。流程应改为：
> 1. 将 resolution 写入 transcript/session（当前已做）。
> 2. 从 `pending.request_payload` 重构出 `Action`。
> 3. 调用 `_execute_action(session, action, current_mode, ...)` 执行该 action。
>
> 但必须解决一个细节问题：`_execute_action` 内部会再次调用 `permission_policy.evaluate()`，如果此时用户已经批准，policy 可能再次 ask 怎么办？
>
> **解决方案**：在 resume 路径中，调用 engine 时传入的 `permission_handler` 回调不再询问用户，而是直接返回预先决定的布尔值（approved/rejected）。因为 permission resolution 的调用方已经知道答案，所以这个短路是合理的。这样 `_execute_action` 的完整逻辑被保留，但 permission 交互被安全地跳过。
>
> 这就实现了方案 9.2 所要求的：
> > "Approval only changes the pending interaction resolution. The engine must still run the pending action through: current mode checks, current write policy checks, runtime execution."

---

### 5. TaskGraph 作为 Session Truth（Phase 3）— 方向正确，但实现复杂度被低估

#### 当前代码事实

- `Session` 类中**没有 `task_graph` 字段**（`session.py:251-259`）。
- `task_status` 工具调用时，动态生成 `TaskGraph`（`harness/runner.py:50`），其数据来源于 `HarnessRunner.describe_mode()` 返回的 `HarnessModeContext`。
- `ManagedSession` 持有 `current_phase`、`discipline_profile`、`current_activity`、`task_summary`、`task_items`（157-186）。每次 turn 结束后，`_refresh_harness_state()` 根据 `describe_mode` 的结果更新这些字段，并通过 `task_store.save_task_snapshot()` 写入 sidecar JSON。

当前 harness 本质上是无状态的：给定 `(mode, phase, observations)`，返回固定的 prompt 和 task summary。

#### Claude Code 参考

- Claude Code 的 `AppState.tasks` 是任务 truth。UI（如 `TeammateSpinnerTree`、`ShellDetailDialog`）只是读取 `AppState.tasks` 做投影。
- Harness（如 `LocalShellTask`、`LocalAgentTask`）通过 `registerTask` / `updateTaskState` 写入 truth。

#### 评估与建议

方案要求 `Session.task_graph` 成为 truth，`task_status` 和 `SessionSnapshot` 只是 projection。这个方向与 Claude Code 一致，是对的。

> **风险与优化建议**：
> 当前 `HarnessRunner.describe_mode()` 是**无状态纯函数**。如果要让 `TaskGraph` 成为 session truth，需要把它从"渲染函数"改造成"可增量突变的状态对象"：
>
> 1. 给 `Session` 添加 `task_graph: Optional[TaskGraph]` 字段。
> 2. 在 phase 推进时（`advance_phase` 或 harness 观察到特定 tool result 时），直接修改 `session.task_graph` 的节点状态。
> 3. `task_status` 工具改为读取 `session.task_graph`，而不是调用 `tools.describe_mode`。
> 4. `ManagedSession` 中的 `current_phase`、`discipline_profile`、`task_summary`、`task_items` 应全部删除，由 `SessionSnapshotProjector` 从 `session.task_graph` 实时投影。
>
> **关键设计点**：需要明确定义 **harness 如何更新 task_graph**。建议不要让 `describe_mode()` 同时承担"生成 prompt"和"更新状态"两个职责。可以做如下拆分：
> - `describe_mode(...)` → 只读，用于生成 prompt units。
> - `update_task_graph(session, observations, ...) -> TaskGraphDiff` → 由 engine 在 turn 边界（或每个 action 执行后）显式调用，负责突变 `session.task_graph`。
>
> 否则，你很容易又陷入"harness 是 truth"的旧路径。

---

### 6. Mode Fail-Fast（方案 12.3）— 修改简单但影响面大

#### 当前代码事实

`modes.py:228-238`：

```python
def require_mode(mode_name: str) -> Dict[str, object]:
    if mode_name in MODE_REGISTRY:
        return MODE_REGISTRY[mode_name]
    _LOG.warning("Unknown mode %r, falling back to %r", mode_name, DEFAULT_MODE)
    return MODE_REGISTRY[DEFAULT_MODE]
```

这与方案要求的"Unknown modes must fail immediately"直接矛盾。

#### 评估与建议

既然明确声明不兼容 legacy，这段 silent fallback 应直接改为抛出异常：

```python
raise ValueError("Unknown mode: %r" % mode_name)
```

> **风险**：当前测试代码、`SessionRestorer` 的恢复路径、某些 slash command 可能隐式依赖这个 fallback。需要全局搜索 `require_mode` 调用，确认所有上游都能处理异常。这是清理工作，不复杂，但务必做全。

---

### 7. Persistence Hot Path（Phase 4）— 问题属实，修复方案可直接采纳

#### 当前代码事实

`TranscriptStore.append_event()`（`transcript_store.py:41-71`）每次调用：

1. `_repair_tail(path)`
2. `_next_seq(path)` → 调用 `self.load_events(path)` → 调用 `_scan_events(path)` → **完整读取并解析整个 JSONL 文件**
3. `seq = events[-1].get("seq") + 1`

这意味着每次 append 都是 O(n)。随着会话变长，写延迟线性增长。对于长会话（数万条 event），这是不可接受的。

`SessionTimelineStore` 也极可能有相同问题，但本次未详细审阅其源码。

#### Claude Code 参考

- Claude Code 的 `sessionStorage.ts` 使用 `Project` 单例管理 per-file write queue，lazy flush（100ms 定时器），不会每次 append 都读取文件。它只在加载/恢复时读取一次。

#### 评估与建议

方案 13.4 的优化建议完全正确：
> - open or restore session file
> - scan once
> - cache `last_seq` in process
> - increment in memory on append

> **优化建议**：
> 在 `TranscriptStore` 中增加进程级缓存：
> ```python
> self._seq_cache: Dict[str, int] = {}   # path -> last_seq
> ```
> - `load_events()` 后更新缓存。
> - `append_event()` 时优先使用缓存并 `+1`。
> - 当文件发生 truncate/repair 时，重新 scan 并更新缓存。
>
> 更进一步，可以引入小额 write buffer：将 50-100ms 内的多次 `append_event` 合并为一次 `write()` + `flush()`，减少 fsync 次数。Claude Code 的 lazy flush 模式对此类问题已被证明非常有效。

---

## 三、与 Claude Code 源码的关键差异与启示

| 维度 | Claude Code | 当前系统 / 你的方案 | 启示 |
|------|-------------|---------------------|------|
| **Engine 生命周期** | Per-conversation | 当前 per-turn，方案改为 per-session | 与方案一致 |
| **递归/Step 模型** | `queryLoop` 递归，无显式 step_id，用 `queryTracking.depth` | 显式 step loop，`step_id` 用于 frontend timeline | 可以保留 step_id，但统一生成源即可 |
| **Permission Resume** | REPL 重入 pipeline，SDK 存在 bypass | 方案要求全部重入 pipeline | 比 Claude Code 更严格，值得做 |
| **State 分层** | `bootstrap/state` (进程级) → `AppState` (UI级) → `ToolUseContext` (loop级) | 方案提出 `ManagedSession` (runtime host) → `Session` (conversation truth) → Projectors | 分层思想一致 |
| **Task 状态** | `AppState.tasks` 是 truth | 方案提出 `Session.task_graph` 是 truth | 一致，但需注意增量更新机制设计 |
| **Transcript 写** | 批量队列 + lazy flush | 当前单条 + 全文件扫描，方案改为缓存 seq | 优化方向正确 |

**一个重要观察**：Claude Code 的 `QueryEngine` 耦合了更多会话级能力（文件缓存、token budget、auto-compact 决策），而你们的 `QueryEngine` 目前相对单薄。在改为 per-session 后，可以考虑把 `ContextManager` 的缓存状态、loop guard 历史、`intelligence_broker` 的查询缓存等也纳入 engine 生命周期，减少 per-turn 状态重建开销。但这属于优化，不应在 Phase 1 中一次性做太多。

---

## 四、风险点与实施优化建议

### 高风险点

#### 1. Phase 1 与 Phase 2 的紧密耦合
Engine per-session 是 resume re-enter pipeline 的前提。如果 Phase 1 完成后 engine API 仍是 `submit_turn` / `resume_pending` 这种分离入口，Phase 2 的改动会触及两处。建议 Phase 1 收尾时就把这两个入口统一为 `submit_user_turn()` / `resume_interaction()`。

#### 2. Adapter 缩容的边界模糊
方案要求 Adapter 收缩为"protocol translation + callback bridge + slash dispatch + projector calls"。但当前 `InProcessAdapter` 是 2000 多行的大文件，包含 session registry、worker thread、stop/cancel、状态刷新、持久化等。如果把这些都搬到新的 `SessionRuntimeManager`，需要注意：
- `SessionRuntimeManager` 和 Adapter 之间的调用关系要单向，避免循环依赖。
- 不要制造一个新的"什么都管"的中间层。

#### 3. TaskGraph 状态突变的实现细节
当前 `TaskGraph.for_mode(...)` 是纯函数，返回新的 TaskGraph 实例。入 `Session` 后，它必须支持增量突变。如果 `TaskNode` 是不可变的 dataclass，需要先改成可变，或设计 `session.task_graph = session.task_graph.with_updated_node(...)` 的函数式更新模式。

### 额外优化建议

#### A. 最小化启动 Phase 1
不要一上来就重写 engine 的 public API。可以先做最小改动：
1. 在 `ManagedSession` 中添加 `engine: Optional[QueryEngine] = None`。
2. 在 `_run_turn_v2()` 中，先检查 `state.engine`，若不存在则创建并保存；存在则复用。
3. 验证复用稳定后，再统一为 `submit_user_turn` / `resume_interaction`。

#### B. 规范化 InteractionCheckpoint
建议为 `PendingInteraction.request_payload` 引入强类型：

```python
@dataclass
class InteractionCheckpoint:
    action: Action
    turn_id: str
    step_id: str
    interaction_id: str
    kind: str
    request_data: Dict[str, Any]
```

这样 transcript replay 和 live resume 都能依赖同一 schema，避免 ad-hoc dict 解析。

#### C. TimelineStore 同步优化
方案只点名了 `TranscriptStore`，但 `SessionTimelineStore` 的 append 路径也很可能有相同的 `_next_seq` 全文件扫描问题。建议在 Phase 4 中一并修复。

#### D. SessionSnapshotProjector 的无状态设计
`SessionSnapshotProjector` 应设计为纯函数，输入 `ManagedSession` + `Session`，输出 `SessionSnapshot`。这样前端 bootstrap 可以按需调用，不会因为 projector 的调用附带副作用（如修改 `ManagedSession` 的状态）。

---

## 五、结论与推荐实施顺序

该方案是一份**高水准的架构重构设计**，准确地诊断了当前系统的结构性问题，提出的"单一 truth 源"原则对症下药。

**核心结论**：
1. **Phase 1 是一切后续改动的基础** — Engine per-session 是最关键的里程碑。
2. **Permission resume re-enter pipeline 是技术上最深但最值得的改动** — 不要妥协为像 Claude Code SDK 那样的 bypass。
3. **TaskGraph 入 Session 的复杂度可能被低估** — 需提前设计 harness 更新 graph 的机制，切勿让 `describe_mode` 继续兼任状态更新职责。
4. **Persistence hot path 修复最独立** — 可以最早实施，立即见效。

**推荐实施顺序**（以周为单位）：

| 阶段 | 工作内容 | 预期产出 |
|------|----------|----------|
| **Week 1** | Phase 1 (Engine ownership) + Phase 4 (Persistence seq cache) | `ManagedSession` 持有稳定 engine；transcript append 不再扫描全文件 |
| **Week 2** | Phase 2 (Interaction/permission unified pipeline) | Permission resume 和 user_input resume 均重新进入 `_execute_action` |
| **Week 3** | Phase 3 (TaskGraph truth + todo cleanup) | `Session` 新增 `task_graph`；`todos.py` 删除；snapshot/task_status 改为投影 |

**最后强调**：既然明确 **不考虑 legacy 兼容**，实施过程中应贯彻"fail fast"原则。不要添加任何 silent fallback、双路径 shim、或"临时兼容"代码。方案中的严格性（strict restore、unknown mode 立即报错、timeline 缺失不影响 resume）应一以贯之。
