# OpenHands 平台架构分析与借鉴

> 分析版本：OpenHands V0（`reference/OpenHands/`）
> 分析目标：为轻量化 C 语言辅助编程 Agent 平台提取可借鉴的设计模式
> 注意：OpenHands V0 官方已宣布于 2026-04-01 废弃，迁移至 V1/Agent SDK，但其核心架构模式仍有高度参考价值

---

## 一、整体架构概览

OpenHands 的核心架构可以用一句话总结：**事件驱动的反应式 Agent 循环，配合可组合的工具集和可替换的记忆压缩策略**。

```
用户输入
   ↓
EventStream（事件总线）
   ↓
AgentController.on_event() → should_step() → _step()
   ↓
Agent.step(state) → LLM 调用 → response_to_actions()
   ↓
Action（动作对象）→ EventStream 发布
   ↓
Runtime 执行（Bash/文件读写/Git）
   ↓
Observation（观察对象）→ EventStream 发布
   ↓
（循环）
```

关键文件：
- `openhands/controller/agent_controller.py` — 主控循环（1392 行）
- `openhands/agenthub/codeact_agent/codeact_agent.py` — 主 Agent 实现
- `openhands/events/` — 事件/动作/观察类型定义

---

## 二、核心设计模式详解

### 2.1 事件驱动架构（Event-Driven Architecture）

**设计要点**：Agent 不主动拉取状态，而是被动接收事件推送并作出反应。所有状态变更都流经统一的 EventStream。

```
EventStream.add_event(action) → 触发所有订阅者的 on_event()
```

**优势**：
- 动作可回放、可审计、可调试
- 关注点彻底分离（生成 vs 执行 vs 记录）
- 便于暂停/恢复（序列化 event history 即可）

**对我们项目的借鉴价值**：★★★★★

即使是极简实现，也应保持 **动作生成** 与 **动作执行** 分离的原则。一个最简版的事件系统可以仅是一个带类型标记的 dataclass 列表：

```python
@dataclass
class Event:
    id: int
    timestamp: str
    source: str  # "agent" | "runtime" | "user"

@dataclass
class Action(Event):
    pass

@dataclass
class Observation(Event):
    content: str
```

---

### 2.2 Action/Observation 类型体系

**设计要点**：将 Agent 能做的事情（Action）和外界返回的结果（Observation）都建模为类型化对象，而非字符串。

OpenHands 的 Action 类型（节选，对嵌入式 C 项目有用的部分）：

| Action 类型 | 对应操作 | 我们是否需要 |
|------------|---------|-----------|
| `CmdRunAction` | 执行 Shell 命令（编译、测试） | ✅ 核心 |
| `FileReadAction` | 读取文件内容 | ✅ 核心 |
| `FileWriteAction` | 写入文件 | ✅ 核心 |
| `FileEditAction` | str-replace 方式编辑文件 | ✅ 核心 |
| `AgentThinkAction` | Agent 内部推理（不执行，仅记录） | ✅ 建议保留 |
| `AgentFinishAction` | 任务完成，退出循环 | ✅ 必须 |
| `TaskTrackingAction` | TODO 任务管理 | ✅ 必须 |
| `BrowseURLAction` | 网页访问 | ❌ 不需要 |
| `IPythonRunCellAction` | Python Jupyter 执行 | ❌ 不需要 |

Observation 类型（对应需要的 Action）：

| Observation 类型 | 含义 |
|-----------------|------|
| `CmdOutputObservation` | Shell 命令输出（含 exit_code） |
| `FileReadObservation` | 文件内容 |
| `FileEditObservation` | 编辑结果确认 |
| `ErrorObservation` | 错误信息 |
| `TaskTrackingObservation` | 任务状态更新 |

**对我们项目的借鉴价值**：★★★★★

直接沿用这套 Action/Observation 设计哲学，但只实现需要的子集。

---

### 2.3 LLM 调用层抽象

**设计要点**：`LLM` 类封装了所有 LLM 调用，包括重试、截断、Token 计数、多 Provider 路由。

```python
# openhands/llm/llm.py 核心接口
class LLM:
    def completion(self, messages, tools=None, **kwargs) -> ModelResponse:
        # 内部包含：重试、truncation、metrics 记录
        ...
```

**重要的 LLMConfig 字段**（`openhands/core/config/llm_config.py`）：

```python
class LLMConfig:
    model: str                    # 模型 ID
    api_key: str                  # API Key
    base_url: str                 # 支持本地/离线 LLM（如 Ollama）
    max_output_tokens: int        # 最大输出 tokens
    max_message_chars: int        # 单条消息最大字符数（防上下文爆炸）
    num_retries: int              # 重试次数
    temperature: float
    native_tool_calling: bool     # 是否使用原生函数调用
```

**重试策略**（`openhands/llm/retry_mixin.py`）：
- 重试条件：`APIConnectionError`, `RateLimitError`, `ServiceUnavailableError`, 超时
- 策略：指数退避 `base_delay * (multiplier ^ attempt)`，带上下限

**对我们项目的借鉴价值**：★★★★☆

我们的离线内网环境同样需要：
1. `base_url` 指向本地 LLM（如 Ollama 或本地 API 服务）
2. 重试逻辑（本地 LLM 也可能超时）
3. `max_message_chars` 截断（防止大文件读取撑爆上下文）

---

### 2.4 消息构建（History → LLM Messages）

**设计要点**：`ConversationMemory.process_events()` 负责将 event history 转换为 LLM 的 messages 列表。

关键逻辑：
1. `Action`（来自 agent）→ `assistant` 角色消息
2. `Observation`（来自 runtime）→ `tool`/`user` 角色消息
3. 大型 Observation 按 `max_message_chars` 截断
4. 连续 user 消息之间插入换行

**对我们项目的借鉴价值**：★★★★★

这部分是 Agent 循环的核心，必须自己实现。设计要点：
- History 是 Event 列表，每次 LLM 调用前实时转换为 messages
- 文件读取等大内容必须截断，否则长会话必然 OOM

---

### 2.5 状态管理（State）

**设计要点**：`State` dataclass 持有所有运行时状态。

```python
# openhands/controller/state/state.py
@dataclass
class State:
    history: list[Event]           # 完整事件历史（压缩前）
    agent_state: AgentState        # LOADING/RUNNING/PAUSED/FINISHED/ERROR
    iteration_flag: IterationControlFlag   # 迭代次数控制
    budget_flag: BudgetControlFlag         # 花费上限控制
    metrics: Metrics               # Token 用量、费用、延迟
    extra_data: dict               # 扩展元数据（压缩器使用）
```

**AgentState 枚举**：
```
LOADING → RUNNING ↔ PAUSED → FINISHED
                 ↘ ERROR ↗
                 ↘ AWAITING_USER_INPUT ↗
```

**对我们项目的借鉴价值**：★★★★☆

状态机设计值得保留，尤其是 `AWAITING_USER_INPUT` 状态——TUI 场景下用户随时可能中断，需要明确的暂停/继续机制。

---

### 2.6 工具调用转换（Function Calling Conversion）

**设计要点**：`response_to_actions()` 将 LLM 的工具调用响应转换为 Action 对象。

```python
# openhands/agenthub/codeact_agent/function_calling.py
def response_to_actions(response, mcp_tool_names) -> list[Action]:
    # 解析 LLM 返回的 tool_calls
    # 验证参数有效性
    # 映射 tool name → Action 类
    # 抛出 FunctionCallValidationError 处理错误
```

工具定义格式（JSON Schema）：
```python
{
    'type': 'function',
    'function': {
        'name': 'bash',
        'description': '...',
        'parameters': {
            'type': 'object',
            'properties': {
                'command': {'type': 'string', 'description': '...'},
            },
            'required': ['command']
        }
    }
}
```

**对我们项目的借鉴价值**：★★★★★

工具定义 = 数据（JSON Schema），而非代码继承层级。这种设计便于：
- 在 System Prompt 中向 LLM 声明工具集
- 动态增减工具（不同任务启用不同工具子集）
- 支持无原生函数调用能力的 LLM（fallback 到 prompt 解析）

---

### 2.7 上下文压缩策略（Condenser）

**设计要点**：Strategy 模式，多种压缩器可组合，负责在上下文窗口接近上限时压缩 history。

```python
# openhands/memory/condenser/condenser.py
class Condenser(ABC):
    @abstractmethod
    def condense(self, view: View) -> View | Condensation:
        ...
```

内置压缩器：

| 压缩器 | 策略 |
|--------|------|
| `ConversationWindowCondenser` | 只保留最近 N 条事件 |
| `RecentEventsCondenser` | 保留尾部若干事件 |
| `ObservationMaskingCondenser` | 过滤低价值观察（如成功的简单命令） |
| `LLMSummarizingCondenser` | 用 LLM 生成摘要替换旧历史 |
| `LLMAttentionCondenser` | LLM 评分筛选重要事件 |
| `PipelineCondenser` | 串联多个压缩器 |
| `NoOpCondenser` | 不压缩（测试用） |

触发时机：
1. 每次 step 前调用 `condenser.condensed_history(state)`
2. LLM 返回上下文超限错误时，触发 `CondensationRequestAction`

**对我们项目的借鉴价值**：★★★★☆

对于内网离线场景，本地 LLM 上下文窗口通常较小（8k-32k）。
最简实现：先用 `ConversationWindowCondenser`（滑动窗口），后续可升级为 `LLMSummarizingCondenser`。
关键：**压缩逻辑要与主循环解耦**，保持策略可替换。

---

### 2.8 卡死检测（Stuck Detection）

**设计要点**：`StuckDetector` 检测 Agent 是否在重复执行相同动作。

触发条件：连续若干次 step 产生相同的 Action（类型 + 参数相同）。

处理选项：
- 重置状态，附上最后一条消息重新开始
- 直接停止，提示用户

**对我们项目的借鉴价值**：★★★★☆

嵌入式开发场景下，Agent 可能陷入「编译失败→修改→编译失败」的循环。卡死检测是必要的安全阀。最简实现：连续 N 次相同 Action 类型时中断并通知用户。

---

### 2.9 迭代次数与预算控制

**设计要点**：双重硬限制，防止失控。

```python
class IterationControlFlag:
    max_iterations: int        # 单次任务最大步数
    current_iteration: int

class BudgetControlFlag:
    max_budget: float          # 最大花费（USD）
    current_spend: float
```

**对我们项目的借鉴价值**：★★★★★

离线本地 LLM 没有费用问题，但迭代次数限制仍然必要（防止无限循环消耗时间）。可简化为单一的 `max_iterations` 配置项。

---

### 2.10 任务追踪工具（Task Tracker）

**设计要点**：Agent 可通过工具调用来管理自身的 TODO 列表，作为内部规划状态。

```python
# openhands/agenthub/codeact_agent/tools/task_tracker.py
# 支持操作：
# - add_task(description)
# - start_task(task_id)
# - complete_task(task_id)
# - list_tasks()
# - get_task_status(task_id)
```

任务状态以 `TaskTrackingObservation` 形式返回，保留在 history 中，LLM 可感知进度。

**对我们项目的借鉴价值**：★★★★★

这是实现「Agent 自主规划」的关键工具。必须实现，但可以简化（只需增/删/查即可）。

---

## 三、可直接借鉴的实现细节

### 3.1 工具调用 Fallback（无原生函数调用支持时）

OpenHands 支持在不支持 native tool calling 的 LLM 上运行：
- 将工具 Schema 嵌入 System Prompt（XML 或 JSON 格式描述）
- 解析 LLM 的文本输出，提取工具调用

这对本地小模型（如 Qwen2.5-Coder、DeepSeek-Coder）非常重要。

### 3.2 大文件内容截断

```python
# 关键配置
max_message_chars: int = 10000  # 单条观察内容最大字符数

# 截断逻辑（在 observation → message 转换时）
def truncate_content(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    half = max_chars // 2
    return content[:half] + "\n...[截断]...\n" + content[-half:]
```

### 3.3 Shell 命令超时控制

`CmdRunAction` 支持 `timeout` 参数，避免编译等长时操作阻塞循环。

### 3.4 文件编辑策略（str-replace 而非全量覆写）

OpenHands 的 `FileEditAction` 使用 str-replace 语义：
```json
{
    "command": "str_replace",
    "path": "/src/main.c",
    "old_str": "int x = 0;",
    "new_str": "int x = 1;"
}
```

优势：Token 消耗少、改动精确、diff 清晰。对 C 语言源码修改场景非常适合。

---

## 四、不建议借鉴的部分

| 组件 | 原因 |
|------|------|
| Docker Runtime | 我们目标是原生 Windows 7 运行，不需要容器 |
| Kubernetes Runtime | 同上 |
| Browser 相关 Action | 离线内网，无需网页访问 |
| Jupyter/IPython | 不需要 Python 执行环境 |
| MCP（Model Context Protocol）| 复杂度高，初期不需要 |
| 多 Agent 委托系统 | 单 Agent 足够，多 Agent 是未来扩展点 |
| 远程存储/S3 | 本地文件系统即可 |
| Web Server/REST API | TUI 直接调用，不需要 HTTP 层 |

---

## 五、对我们项目架构的具体建议

基于以上分析，建议我们的项目采用以下分层架构：

```
┌─────────────────────────────────────┐
│           TUI 层（呈现/交互）          │
│  任务列表 │ 输出面板 │ 用户输入       │
├─────────────────────────────────────┤
│         Agent Controller 层          │
│  主循环 │ 状态机 │ 卡死检测 │ 迭代限制 │
├─────────────────────────────────────┤
│           Agent 层                   │
│  System Prompt │ 工具定义 │ 消息构建  │
├─────────────────────────────────────┤
│           LLM 层                     │
│  API 调用 │ 重试 │ Token 统计        │
├─────────────────────────────────────┤
│           Runtime 层（工具执行）       │
│  Bash │ 文件读写 │ Git │ 编译        │
├─────────────────────────────────────┤
│           Event/State 层             │
│  EventStream │ History │ 压缩器      │
└─────────────────────────────────────┘
```

### 最小可运行核心（MVP）所需组件

1. **Event 系统**：`Event`, `Action`, `Observation` 基类 + 核心子类
2. **State**：history 列表 + agent_state 枚举 + iteration 计数
3. **LLM 调用**：封装 HTTP POST（兼容 OpenAI API），带重试
4. **消息构建**：history → messages 转换函数，带截断
5. **Runtime**：subprocess 执行 + 文件读写（标准库即可）
6. **工具定义**：bash / file_read / file_edit / task_tracker / finish 共 5 个
7. **主循环**：step() 函数，调用 LLM → 解析 Action → 执行 → 观察
8. **TUI**：curses 或 rich 库实现基础界面

### Windows 7 兼容性注意点（来自 OpenHands 的反面教材）

OpenHands 大量使用了：
- Python 3.12+ 特性（`match` 语句、`dataclass` 高级用法）
- `asyncio` 全异步架构
- Docker 容器化

我们应当：
- 使用 Python 3.8（Windows 7 最后支持版本）
- 避免 `asyncio`，改用同步阻塞调用（TUI 单线程即可）
- 文件操作、subprocess 调用均用标准库，无需第三方 Runtime

---

## 六、总结

OpenHands 最核心的可借鉴思想：

1. **Action/Observation 类型化**：不要用字符串传递动作，用类型化对象
2. **生成与执行分离**：LLM 生成 Action，Runtime 执行 Action，两者解耦
3. **History 驱动上下文**：每次 LLM 调用都从完整 history 重建消息，而非维护对话状态
4. **工具即数据**：工具定义是 JSON Schema，而非代码继承
5. **压缩器策略模式**：上下文压缩逻辑可替换，从 Window → LLM Summary 渐进升级
6. **卡死检测 + 迭代限制**：安全阀，防止失控循环
7. **Task Tracker 作为 Agent 内部规划**：TODO 管理是 Agent 自主性的基础

这七条原则完全适用于我们的轻量化目标，且实现成本低。
