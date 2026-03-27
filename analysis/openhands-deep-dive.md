# OpenHands 深度分析：Agent Loop、上下文管理、运行模式

> 基于源码直读，聚焦三个核心机制
> 源文件：`reference/OpenHands/openhands/`

---

## 一、Agent Loop 设计

### 1.1 整体结构

Agent Loop 的核心在 `controller/agent_controller.py`，由三个互相配合的函数构成：

```
on_event(event)          ← EventStream 回调入口
  └─ should_step(event)  ← 判断此事件是否触发下一步
       └─ _step()        ← 真正执行一次 LLM 调用
```

**关键设计**：Loop 不是 `while True` 的同步轮询，而是**事件触发式**的。每次有新 Event 进入 EventStream，`on_event` 被调用，它决定是否触发 `_step()`。

### 1.2 `should_step()` —— 什么事件触发下一步

```python
def should_step(self, event: Event) -> bool:
    if self.delegate is not None:      # 当前有子 Agent，不处理
        return False

    if isinstance(event, Action):
        # 用户发消息 → 触发
        if isinstance(event, MessageAction) and event.source == USER:
            return True
        # 压缩请求/压缩完成 → 触发
        if isinstance(event, (CondensationAction, CondensationRequestAction)):
            return True
        # 其他 Action 不触发（Agent 自己发出的，等待 Observation）
        return False

    if isinstance(event, Observation):
        # 状态变更通知 → 不触发
        if isinstance(event, AgentStateChangedObservation):
            return False
        # 其他所有 Observation → 触发（Runtime 执行完毕，可以继续）
        return True
```

**核心逻辑**：`Action（Agent发出）→ 等待 → Observation（Runtime返回）→ 触发 → 下一个Action`

这个判断隐含了一个重要假设：**每个可执行 Action 有且只有一个对应 Observation**。这通过 `_pending_action` 机制保证（见下文）。

### 1.3 `_step()` —— 一次 LLM 调用的完整流程

```
_step()
  1. 检查状态：必须是 RUNNING，否则直接返回
  2. 检查 pending_action：上一步的 Action 还没收到 Observation，等待
  3. 同步 budget_flag（花费统计）
  4. 卡死检测（_is_stuck()）→ 触发错误处理
  5. 检查控制限制（迭代次数/预算）→ 触发错误处理
  6. agent.step(state) → 调用 LLM，返回 Action
     ├─ 异常：LLMMalformedAction / LLMNoAction → 发送 ErrorObservation，返回
     └─ 异常：ContextWindowExceeded → 发送 CondensationRequestAction，返回
  7. 如果 action.runnable 且 confirmation_mode：
     └─ 安全风险分析 → HIGH 风险 → 状态置 AWAITING_USER_CONFIRMATION
  8. 设置 _pending_action = action（带时间戳）
  9. 将 action 发布到 EventStream
```

**`_pending_action` 机制**：这是避免 Agent 在 Action 执行期间再次 step 的关键。

```python
# _pending_action 是带时间戳的 (action, timestamp) 元组
# 超过 60 秒会打印警告（但不会清除）
# 只有在收到对应 Observation 时，才在 _handle_observation 中清除
if self._pending_action and self._pending_action.id == observation.cause:
    self._pending_action = None  # 清除，解锁下一次 step
```

`observation.cause == action.id` 是关联机制：每个 Observation 记录了触发它的 Action 的 ID。

### 1.4 `agent.step(state)` —— Agent 内部的 LLM 调用

这是 `codeact_agent.py` 中的 `step()` 方法，流程：

```python
def step(self, state: State) -> Action:
    # 1. 如果有 pending_actions 队列（上次 LLM 返回了多个 Action），先消耗
    if self.pending_actions:
        return self.pending_actions.popleft()

    # 2. 调用 Condenser 压缩 history（可能直接返回 CondensationAction）
    match self.condenser.condensed_history(state):
        case View(events=events):
            condensed_history = events      # 正常路径：拿到压缩后的事件列表
        case Condensation(action=action):
            return action                   # 需要压缩：直接返回压缩 Action，跳过 LLM 调用

    # 3. 构建 messages（history → LLM 消息格式）
    messages = self._get_messages(condensed_history, ...)

    # 4. LLM 调用
    response = self.llm.completion(messages=messages, tools=self.tools)

    # 5. 解析 response → Action 列表
    actions = self.response_to_actions(response)

    # 6. 放入 pending 队列，返回第一个
    for action in actions: self.pending_actions.append(action)
    return self.pending_actions.popleft()
```

**重要设计**：LLM 可能在一次回复中返回**多个工具调用**（如先 think 再 bash）。这些被放入 `pending_actions` 队列，由 Controller 逐个分发执行，每次一个。

### 1.5 卡死检测（StuckDetector）

检测 5 种卡死模式，按顺序判断：

| 场景 | 触发条件 | 典型案例 |
|------|---------|---------|
| `repeating_action_observation` | 连续 4 对完全相同的 Action-Observation | 重复读同一文件 |
| `repeating_action_error` | 同一 Action 连续产生 3 次 ErrorObservation | 命令持续报错 |
| `monologue` | Agent 连续发出 3 条相同的 MessageAction，中间无 Observation | 自言自语 |
| `action_observation_pattern` | 最近 6 步中，奇数步相同、偶数步相同（交替循环） | A→B→A→B→A→B |
| `context_window_error` | 连续 10 次 CondensationObservation 之间没有其他事件 | 压缩后还是超限 |

比较两个 Event 是否"相同"时，会忽略 PID（`_eq_no_pid`），避免把"同命令不同进程号"误判为不同。

交互模式（`headless_mode=False`）下，只检测**最后一条用户消息之后**的历史，避免把新任务误判为旧循环。

卡死后的恢复选项（3 选 1）：
1. 从循环开始点截断历史，重试
2. 保留历史，重新注入最后一条用户消息
3. 直接停止

---

## 二、上下文管理设计

### 2.1 整体架构

上下文管理涉及三个层次：

```
State.history（全量 Event 列表）
    ↓ Condenser（压缩策略）
condensed_history（压缩后 Event 列表）
    ↓ ConversationMemory.process_events()
messages（LLM API 格式）
    ↓ truncate_content（单条内容截断）
最终发送给 LLM 的 messages
```

### 2.2 Condenser 架构

**抽象层**：

```python
class Condenser(ABC):
    def condense(self, view: View) -> View | Condensation:
        # 返回 View：直接使用这些 events
        # 返回 Condensation：包含一个 CondensationAction，让 Controller 先执行它
        ...

class RollingCondenser(Condenser, ABC):
    def should_condense(self, view: View) -> bool: ...  # 触发条件
    def get_condensation(self, view: View) -> Condensation: ...  # 压缩逻辑

    def condense(self, view):
        if self.should_condense(view):
            return self.get_condensation(view)  # 需要压缩
        return view                              # 不需要，原样返回
```

**关键机制**：压缩不是原地修改 `state.history`，而是通过往 EventStream 里添加一个 `CondensationAction` 来标记"这些 Event ID 已被遗忘"。下次 `condensed_history()` 调用时，`View` 的构建会跳过被标记的 ID。这使 history 永远是 append-only 的，压缩是逻辑上的。

**触发路径（两条）**：

路径 A：上下文超限时的被动触发
```
LLM 返回 ContextWindowExceededError
→ _step() 捕获
→ 发布 CondensationRequestAction 到 EventStream
→ on_event() 检测到 → should_step() = True
→ _step() → agent.step()
→ condenser.condensed_history() 看到 unhandled_condensation_request
→ 返回 Condensation（包含 CondensationAction）
→ agent.step() 直接返回该 CondensationAction（不调用 LLM）
→ Controller 将 CondensationAction 发布到 EventStream
→ View 更新（标记被遗忘的 IDs）
→ 再次触发 step → 这次用压缩后的 history 正常调用 LLM
```

路径 B：主动压缩（LLM 请求）
```
Agent 在 step 中调用 condenser.condensed_history()
→ should_condense() 判断：事件数超过 max_size
→ 返回 Condensation，agent.step() 直接返回 CondensationAction
→ 同路径 A 后半段
```

### 2.3 ConversationWindowCondenser（默认压缩器）

**触发条件**：存在未处理的 `CondensationRequestAction`（即上下文超限时）

**压缩策略**：
1. 保留**必须保留**的 Events：SystemMessage、第一条用户消息、对应的 RecallAction+Observation
2. 剩余非必要 Events 中，只保留**后半部分**（`num_non_essential // 2`）
3. 生成 `CondensationAction`，其中 `forgotten_event_ids` 列出要丢弃的 Event ID

**注意**：不生成摘要，只是丢弃。被丢弃的信息**永久消失**。这是最简单、无需 LLM 的压缩方式。

### 2.4 LLMSummarizingCondenser（LLM 摘要压缩器）

**触发条件**：`len(view) > max_size`（默认 100 个事件）

**压缩策略**：
```
保留前 keep_first 个 events（必要上下文）
中间部分（keep_first 到 -events_from_tail）→ 调用 LLM 生成摘要
                                             → 摘要以 AgentCondensationObservation 形式插入
保留后 events_from_tail 个 events（最近上下文）
```

压缩后大小约为 `max_size // 2`。

**摘要 Prompt 结构**（对我们的项目有参考价值）：
```
USER_CONTEXT: 用户需求和目标
TASK_TRACKING: 活跃任务 ID 和状态（必须保留任务 ID！）
COMPLETED: 已完成任务
PENDING: 待做任务
CURRENT_STATE: 当前变量/数据结构
CODE_STATE: 文件路径、函数签名
TESTS: 失败用例、错误信息
CHANGES: 代码变更
DEPS: 依赖关系
VERSION_CONTROL_STATUS: 分支、PR、提交历史
```

### 2.5 单条内容截断（max_message_chars）

在 `ConversationMemory.process_events()` 中，每条 Observation 的内容会被截断：

```python
if len(content) > max_message_chars:
    content = truncate_content(content, max_message_chars)
    # 截断方式：保留前半 + "...[截断]..." + 后半
    # 在单词边界截断，不截断 Unicode
```

这与 Condenser 是**正交的**两层保护：
- Condenser 控制**有多少 Events 进入上下文**
- max_message_chars 控制**每个 Event 的内容有多长**

### 2.6 完整 History 的不可变性

`state.history` 是 append-only 的，从不删除。
- Condenser 遗忘 = 在 EventStream 中标记 `forgotten_event_ids`
- 每次 `condensed_history()` 调用，`View` 根据这些标记过滤

**优势**：
- 可以随时回放完整 history（调试、审计）
- Condenser 策略可以切换，不影响已记录的 history
- 崩溃恢复：只需重载 history，不会丢失任何数据

---

## 三、运行模式设计

### 3.1 AgentConfig 开关矩阵

OpenHands 通过 `AgentConfig` 的布尔字段控制功能开关，而非不同类/子类：

```python
class AgentConfig(BaseModel):
    # 运行环境
    cli_mode: bool = False           # CLI 模式（区别于 Web 模式）
    headless_mode: bool = True       # 无交互模式（自动化测试）

    # 工具开关
    enable_cmd: bool = True          # Bash 工具
    enable_think: bool = True        # Think 工具（推理记录）
    enable_finish: bool = True       # Finish 工具
    enable_editor: bool = True       # 文件编辑工具
    enable_llm_editor: bool = False  # LLM 编辑工具（已废弃）
    enable_browsing: bool = True     # 浏览器工具
    enable_jupyter: bool = True      # Jupyter 工具
    enable_mcp: bool = True          # MCP 工具
    enable_condensation_request: bool = False  # 允许 Agent 主动请求压缩

    # 行为开关
    enable_plan_mode: bool = True    # 规划模式（长期任务）
    enable_stuck_detection: bool = True       # 卡死检测
    enable_history_truncation: bool = True    # 自动截断历史
    enable_som_visual_browsing: bool = True   # 视觉浏览
    enable_prompt_extensions: bool = True     # Prompt 扩展

    # 压缩器配置（Strategy 对象，不是布尔）
    condenser: CondenserConfig = ConversationWindowCondenserConfig()
```

工具列表是在 `_get_tools()` 中**运行时**根据这些开关动态构建的，而非继承或注册。

### 3.2 Plan Mode（规划模式）

`enable_plan_mode=True` 时：

1. **System Prompt 切换**：
   ```python
   @property
   def resolved_system_prompt_filename(self):
       if self.enable_plan_mode and self.system_prompt_filename == 'system_prompt.j2':
           return 'system_prompt_long_horizon.j2'  # 换成长期任务 prompt
       return self.system_prompt_filename
   ```

2. **增加 TaskTracker 工具**：
   ```python
   if self.config.enable_plan_mode:
       tools.append(create_task_tracker_tool(use_short_tool_desc))
   ```

3. **TaskTracker 工具的操作**：`add_task / start_task / complete_task / list_tasks / get_task_status`

TaskTracker 的状态完全通过 Tool Call + Observation 在 history 中维护，Agent 自己"记住"任务列表。

### 3.3 Confirmation Mode（确认模式）

`confirmation_mode=True` 时，可执行 Action 在发布前需通过安全分析：

```
action.runnable=True → 有安全分析器?
    ├─ 有 → 调用 SecurityAnalyzer → 返回 HIGH/MEDIUM/LOW
    └─ 无 → 设为 UNKNOWN（默认 fail-safe）

security_risk == HIGH 或 UNKNOWN → 状态设为 AWAITING_USER_CONFIRMATION
→ 等待用户确认或拒绝
    ├─ 确认 → 状态恢复 RUNNING → action 发布执行
    └─ 拒绝 → 状态设为 AWAITING_USER_INPUT → 等待新指令
```

**CLI Mode 的特殊处理**：
```python
if self.agent.config.cli_mode:
    action.confirmation_state = AWAITING_CONFIRMATION
    # CLI 自己在界面里处理确认，不走 Controller 的确认流程
```

这是因为 CLI 和 Web 的用户交互方式不同，CLI 模式下确认逻辑在 TUI 层而不是 Controller 层。

### 3.4 Headless Mode（无头模式）

`headless_mode=True`（默认，用于自动化/CI）：
- StuckDetector 检查**全部** history
- 没有交互式用户输入机制

`headless_mode=False`（交互模式）：
- StuckDetector 只检查**最后一条用户消息之后**的 history（避免把新任务误判为旧循环）
- 卡死后可弹出 3 选 1 的恢复对话框

### 3.5 Delegate Mode（委托模式）

当 Agent 执行 `AgentDelegateAction` 时：

```python
# 创建子 Controller
self.delegate = AgentController(
    sid=self.id + '-delegate',
    agent=delegate_agent,
    event_stream=self.event_stream,   # 共享同一个 EventStream！
    initial_state=state,
    is_delegate=True,                  # 关键标记
    ...
)

# is_delegate=True 的效果：
# 1. 不自己订阅 EventStream（由父 Controller 转发）
# 2. 与父 Controller 共享 iteration_flag 和 metrics
```

父 Controller 在 `on_event()` 中检测是否有活跃的 delegate，如果有就转发事件给 delegate 而不自己处理：

```python
def on_event(self, event):
    if self.delegate is not None:
        delegate_state = self.delegate.get_agent_state()
        if delegate_state not in (FINISHED, ERROR, REJECTED):
            self.delegate._on_event(event)  # 转发给 delegate
            return
        else:
            self.end_delegate()            # delegate 完成，恢复父 Agent
            return
    # 正常处理
    self._on_event(event)
```

### 3.6 Replay Mode（重放模式）

`replay_events` 参数传入历史 Action 列表，`ReplayManager` 接管：

```python
if self._replay_manager.should_replay():
    action = self._replay_manager.step()  # 从历史中取 Action
else:
    action = self.agent.step(self.state)  # 正常调用 LLM
```

用于：测试、调试、从 checkpoint 恢复执行。

---

## 四、三个机制的关联图

```
用户输入
  │
  ▼
EventStream.add_event(MessageAction, source=USER)
  │
  ▼
on_event() → should_step() = True
  │
  ▼
_step()
  ├─ [Guard] 检查 agent_state == RUNNING
  ├─ [Guard] 检查 _pending_action == None
  ├─ [Guard] StuckDetector.is_stuck()  ─────────── headless/interactive 行为不同
  ├─ [Guard] iteration/budget 控制限制
  │
  ▼
agent.step(state)
  ├─ condenser.condensed_history(state) ─────────── 上下文管理入口
  │     ├─ should_condense()? No  → View(events)   正常 events
  │     └─ should_condense()? Yes → Condensation   返回压缩 Action（跳过 LLM）
  │
  ├─ ConversationMemory.process_events() ─────────── history → LLM messages
  │     └─ truncate_content(max_message_chars) ───── 单条内容截断
  │
  └─ llm.completion() → response_to_actions() → Action

Action 发布到 EventStream
  │
  ├─ [confirmation_mode] 安全分析 → 等待确认 ─────── 确认模式
  │
  ▼
Runtime 执行 Action
  │
  ▼
Observation 发布到 EventStream
  │
  ▼
on_event() → should_step() = True
  │         _pending_action = None（已收到 Observation）
  ▼
下一次 _step()（循环）
```

---

## 五、对我们项目的核心启示

### Agent Loop 设计决策

1. **同步 > 异步**：OpenHands 用 asyncio，但我们选同步阻塞。关键在于保持 `pending_action` 的单线程互斥语义。同步实现更简单：直接 `action = execute(action)` 等待返回。

2. **卡死检测不要省略**：5 种场景不一定全实现，但至少实现"同 Action 连续 3 次错误"和"同 Action 重复 4 次"。对嵌入式 C 的编译循环场景（改了又编译失败）特别有用。

3. **`_pending_action` 的意义**：确保一次 step 对应一个 Action 的执行期间，不会发生二次 step。同步实现下这是天然的，但仍要在概念上保留这个状态。

### 上下文管理决策

4. **压缩器从最简开始**：先用纯截断（`ConversationWindowCondenser` 的逻辑），即：保留 system prompt + 第一条用户消息 + 最近 N 个 events。无需 LLM，无需摘要。

5. **单条内容截断是必须的**：`max_message_chars` 截断不能省。一次 `gcc` 编译错误可能输出几千行，必须截断后半部分。

6. **History 不可变原则**：`state.history` 只追加，不修改。压缩通过维护一个 `forgotten_ids: set` 来实现逻辑遗忘。这对调试和错误恢复非常重要。

### 运行模式决策

7. **用配置开关而非类继承控制功能**：所有工具开关都是 `AgentConfig` 的布尔字段，工具列表运行时动态构建。这比子类化灵活得多。

8. **Plan Mode 的本质是 Prompt + 工具**：只是换了 System Prompt 文件 + 加了 TaskTracker 工具，其余逻辑完全相同。我们可以直接复用这个思路。

9. **Confirmation Mode 在 TUI 场景下的对应物**：我们的 TUI 里，危险操作（如删文件、git reset）应当在执行前显示确认提示，这与 OpenHands 的 AWAITING_USER_CONFIRMATION 状态语义完全一致，只是交互层不同。
