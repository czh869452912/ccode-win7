# Agent Core Ownership Cutover 设计审查报告（第二轮）

**审查日期**: 2026-04-07
**审查对象**: `docs/archive/agent-core-cutover/2026-04-07-agent-core-cutover-design.md`（已吸收第一轮增强点后的版本）
**审查结论**: 文档质量显著提升，核心原则清晰，但在实施前必须补齐 5 个高优先级细节。

---

## 一、本轮改进的认可

相比第一轮，更新后的设计文档在以下方面已完全达到可实施标准：

- **7.1 Session ownership** 明确补充了 per-session engine 后的 session-scoped state 审计要求（maintenance counters、loop-level caches）。
- **9.3 Interaction payload contract** 明确禁止 interaction/ticket 创建第二套 identity namespace，要求 ticket id 等于或与 `PendingInteraction.interaction_id` 严格 1:1 映射。
- **11.4 Harness relationship** 将 harness 拆分为只读的 `describe_mode(...)` 和更新 truth 的 `update_task_graph(...)`，职责边界明确。
- **14.1 Snapshot projector** 以强制约束形式声明 projector 必须无副作用、不得突变 `ManagedSession` / `Session` / transcript / replay state。
- **13.4 Sequence-number optimization** 明确 seq cache 优化可以早于大范围 persistence cutover 独立落地。

这些增强点精准地消除了第一轮审查中识别出的主要架构模糊地带。

---

## 二、高优先级：必须在实施前澄清的 5 个问题

### 1. Engine 公共 API 缺少 `session initialization` 的入口

**文档现状**：
- 8.2 宣称 engine 公共 API 缩减为 `submit_user_turn(...)` 和 `resume_interaction(...)` 两个入口。
- 8.5 又要求 "Session initialization becomes an engine-owned concern"，包括 workspace profile、mode system prompt、harness prompt units 的注入。

**矛盾点**：如果只有两个入口，且 `submit_user_turn` 语义上处理用户输入 turn，那么 session 刚创建后、首次用户输入到达前的**初始系统消息注入**应该在何时触发？

- 若依赖 `submit_user_turn` 的副作用完成初始化，但 `user_text` 可能为空（前端仅请求 bootstrap 时），则初始化逻辑与 turn 逻辑发生隐式耦合。
- 若要求 adapter 在 engine 创建前手动注入这些消息，则违背了 8.5 "engine-owned initialization" 的要求。

**建议**：
- 将 engine public API 明确为 **三个入口**：
  1. `initialize_session(session: Session, mode: str, workflow_state: str = "chat") -> None` —— 负责注入 profile、mode prompt、harness messages。
  2. `submit_user_turn(session: Session, user_text: str, ...) -> QueryTurnResult`
  3. `resume_interaction(session: Session, resolution: dict, ...) -> QueryTurnResult`
- 这样 `ManagedSession` 创建流程为：`create Session -> engine.initialize_session(session, mode) -> persist -> bootstrap`。

---

### 2. Resume re-enter pipeline 的「重复 ask」陷阱未给出解法

**文档现状**：
- 9.2 和 10.3 明确要求 resume 时 action 必须重新进入 `_execute_action` pipeline，经过 mode checks、write policy checks、runtime execution。
- 但未说明如何解决 `_execute_action` 内部 `permission_policy.evaluate()` 可能再次返回 `"ask"` 的问题。

**陷阱分析**：
- 若 resume 时直接调用 `_execute_action(...)`，而 `permission_handler` 是一个普通的 user-prompt 回调，则 policy 可能再次判定为 "ask"，导致：
  - 无限循环（inline resolver 返回 None 时），或
  - 重复挂起（生成新的 pending interaction）。
- 当前代码正是为了避免这个问题，才在 `_resume_interaction` 中直接调用 `self.tools.execute(action.name, action.arguments)` —— 但这就是 bypass 的根源。

**建议**：
- 在 9.2 或 10.3 中补充明确的**短路机制**，文字示例：

> "When `resume_interaction` re-enters the action pipeline, the engine must wrap the original `permission_handler` with a synthetic resolver that returns the pre-resolved decision (`approved` or `rejected`) for the pending action. This ensures that `_execute_action` executes all validation stages without re-suspending on the same interaction."

- 实施层面，可以在 `_resume_interaction` 内部构造一个新的 `permission_handler` 闭包，拦截 `request.tool_name` 和 `details` 与 pending action 匹配时，直接返回缓存的布尔值。

---

### 3. `update_task_graph(...)` 的签名、调用方和调用时机完全缺失

**文档现状**：
- 11.4 提出了 harness 职责拆分：
  - `describe_mode(...)` → read-only
  - `update_task_graph(...)` → mutates or functionally updates `Session.task_graph`
- 但对该函数的输入、输出、调用者、调用频率、更新语义均未定义。

**缺失的关键信息**：
- 完整函数签名是什么？接收哪些参数？
- **谁调用它？** Engine？HarnessRunner？Adapter？
- **何时调用？** 每个 action 后？每个 step 后？每个 turn 后？
- **是就地突变还是函数式更新？** 11.4 原文 "mutates or functionally updates" 两边都说了，会让实施者无所适从。

**建议**：
- 在 11.4 中追加规范化的签名与调用约定，例如：

```python
def update_task_graph(
    session: Session,
    current_mode: str,
    observations: List[Observation],
) -> None:
    """Mutate session.task_graph in place based on the latest turn observations.

    Called by the engine at the end of each turn, immediately before
    session persistence and snapshot emission.
    """
```

- 明确调用时机：
  > "The engine calls `update_task_graph(session, current_mode, turn_observations)` at the end of each turn, before persisting the session."

- **推荐选择就地突变（in-place mutation）**。因为 `Session` 本身是可变 dataclass（messages/turns 都是 append 语义），如果 `task_graph` 采用函数式更新，会与现有代码风格割裂，还会引入不必要的对象替换开销。

---

### 4. `interaction_runtime.py` 的职责边界非常模糊

**文档现状**：
- 15.3 计划新增 `interaction_runtime.py`，描述为 "interaction ticket mapping and resume glue"。

**问题**：
- 9.3 已明确要求 interaction identity 完全统一：`ticket.id == PendingInteraction.interaction_id`，不允许第二套命名空间。
- 如果 identity 没有分裂，那 "ticket mapping" 这个职责应该非常薄——可能只是把前端 `/approve` 或 `/reply` 请求里的 `interaction_id` 解包并路由到 `SessionRuntimeManager.resume_interaction(session_id, ...)`。
- 一个仅做参数解包和路由的模块是否值得独立文件？如果它最终又持有自己的 interaction cache 或状态，就会演变成新的 adapter 碎片，违背本次 cutover 的初衷。

**建议**：
- 在 15.3 中为 `interaction_runtime.py` 追加严格的职责范围说明，例如：

  > "This module contains minimal routing glue that unpacks frontend interaction responses and forwards them to `SessionRuntimeManager.resume_interaction(session_id, interaction_id, resolution)`. It must not create identifiers, cache interaction state, or perform protocol translation beyond argument unpacking. If the implementation collapses to fewer than 30 lines, it should be merged into `session_runtime.py` rather than kept as a separate file."

- 或者，直接取消该文件，将路由逻辑合并到 `session_runtime.py` 的 `SessionRuntimeManager` 中，避免过早的文件拆分。

---

### 5. Step ID 分裂的具体机制需要基于代码精确对齐

**文档现状**：
- 4.2 描述为："The engine records one `step_id` into transcript/session state, while the adapter emits a separate `step_id` into frontend events."

**你的核对**：
- 你认为 `Session.begin_step(...)` 里的 step_id 是 engine 生成的，不是 adapter 反灌的。

**代码层面的精确事实**：
- Engine `_run_loop()`（`query_engine.py:537`）生成 `step_id = "s-" + uuid.uuid4().hex[:12]`。
- 随后 `session.begin_step(step_id=step_id)`（548行）将该 step_id 写入 session。
- 但 `on_step_start(step_index)` 回调（549行）**只传递了 `step_index`，没有传递 `step_id`**。
- Adapter 的 `on_step_start` 闭包（`inprocess_adapter.py:2089`）收到回调后，自己生成一个全新 step_id：
  ```python
  current_step["step_id"] = "s-" + uuid.uuid4().hex[:12]
  ```
- 这个 adapter 生成的 step_id 被用于所有后续前端事件（`assistant_delta`、`tool_started`、`tool_finished`、`step_end` 等）。

**结论**：文档 4.2 的描述是准确的。transcript/session 中的 step_id 来自 engine，而前端 timeline/event stream 中的 step_id 来自 adapter，两者确实是不同的 UUID。

**修复关键点**：
- 不是"禁止 adapter 生成 step_id"这么简单，而是要把 `on_step_start` 的回调签名从 `Callable[[int], None]` 升级为 `Callable[[str, int], None]`（或传一个结构体），让 engine 把自己的 `step_id` 显式传递给 adapter。

**建议**：
- 在 8.4 "Engine callbacks" 中补充明确的签名要求：

  > "Callback signatures must be updated to receive engine-generated identifiers. For example, `on_step_start` must receive both `step_id: str` and `step_index: int`, so that the adapter cannot synthesize a separate step identifier."

---

## 三、中等优先级建议

### A. Phase 1 与 Phase 2 的边界建议收紧

文档 16 中 Phase 1 的 done when 包含 "public execution entry points are session-oriented rather than turn-reconstructing"。这意味着 Phase 1 就要引入 `resume_interaction` 入口。但如果这个入口只是把原来的 `resume_pending` 逻辑换个名字搬进去，bypass 问题仍然保留，那么这个入口就不是真正 session-oriented 的。

**建议**：二选一：
1. 将 Phase 1 和 Phase 2 合并为 "Phase 1-2: Engine ownership and unified execution"；或
2. 明确 Phase 1 的 `resume_interaction` **仅做入口整理和命名统一**，bypass 的实质性修复划入 Phase 2。

### B. Lock 所有权应进一步内聚到 Engine

当前 `QueryEngine` 的 `session_lock` 由 adapter 创建并传入（`session_lock=state.lock`）。当 engine 变为 per-session 后，这把锁应该**内化为 engine 的属性**，adapter 不应再持有或直接操作它。

**建议**：在 7.1 或 8.1 中补充：
> "The engine owns the lock that guards `Session` mutation. The adapter does not create, hold, or pass the session lock to the engine. The engine manages all concurrency boundaries around the session."

### C. `SessionRestorer` / `SessionHistoryAssembler` 对 timeline 的隐式依赖需要验证

文档 13.3 说 "history reconstruction must not depend on timeline"，这是目标状态。但当前代码中 `SessionHistoryAssembler` 或 `SessionRestorer` 是否仍把 timeline 作为 ordering 的补充来源，需要确认。

**建议**：在 Phase 4 的 done when 中增加一条验证项：
> "- Verified that `SessionRestorer` and `SessionHistoryAssembler` read from `transcript.jsonl` only, with no fallback to `timeline.jsonl`."

### D. 补充一份「Session-scoped vs Turn-scoped state」检查清单

7.1 已提到 maintenance counters 和 loop-level caches，但还有其他值得审计的项：

| 状态 | 推荐的归属 | 原因 |
|------|------------|------|
| `_maintenance_counter` | session-scoped | 依赖引擎生命周期才能正确累积 |
| `readFileState` / context caches | session-scoped | 避免重复读取，减少 LLM token 消耗 |
| `permissionDenials` 历史 | session-scoped | 辅助后续 permission 决策 |
| `LoopGuard` | turn-scoped | 防止单次 turn 内的无限递归，不跨 turn |
| per-turn retry counters | turn-scoped | 每次 LLM call 独立重试 |
| `totalUsage` / token budget | session-scoped | 全局预算跟踪 |

**建议**：在 7.1 末尾增加一张类似的简明表格，作为实施检查清单。

---

## 四、总结

更新后的设计文档在以下方面已经具备了进入编码阶段的基础：

- Engine 所有权、Session 边界、投影层纯度等核心原则定义清晰。
- Interaction identity 统一、TaskGraph truth 转移、Harness 职责拆分的方向正确。
- Persistence seq cache 可以独立落地的策略合理，降低了切变风险。

但**在正式编码前，强烈建议先把上述 5 个高优先级问题补充到文档中**：

1. **Engine API 的初始化入口**：明确是 `initialize_session` 还是隐含在 `submit_user_turn` 中。
2. **Resume pipeline 的 permission 短路机制**：说明如何通过 synthetic handler 避免重复 ask。
3. **`update_task_graph` 的完整契约**：签名、调用方、调用时机、就地突变语义。
4. **`interaction_runtime.py` 的精确职责范围**：避免沦为新的 adapter 碎片。
5. **`on_step_start` 回调签名升级**：必须显式接收 `step_id: str` 才能根治 step identity 分裂。

补充这 5 处细节后，文档将足够精确，可以按 Phase 1 → Phase 2 → Phase 3 → Phase 4 的顺序直接推进到实施阶段。
