# Roo-Code 深度分析：Agent循环 / 上下文管理 / 模式系统

> 基于源码精读，聚焦三个核心机制的实现细节
> 参考源码：`src/core/task/Task.ts`, `src/core/context-management/`, `packages/types/src/mode.ts`

---

## 一、Agent 循环（Agent Loop）

### 1.1 核心结构：基于栈的迭代（非递归）

Roo-Code 的循环不是真正的递归，而是**显式栈驱动的 while 循环**，位于 `Task.ts` 的 `recursivelyMakeClineRequests()`：

```typescript
const stack: StackItem[] = [{ userContent, includeFileDetails, retryAttempt: 0 }]

while (stack.length > 0) {
  const currentItem = stack.pop()!
  // 处理请求...
  // 需要重试时压入新 item：
  stack.push({ userContent, includeFileDetails, retryAttempt: N + 1 })
}
```

**StackItem 携带的状态：**
- `userContent` — 本轮用户内容
- `includeFileDetails` — 是否附加文件树详情
- `retryAttempt` — 当前重试次数（用于指数退避）
- `userMessageWasRemoved?` — 是否因空响应移除了用户消息

### 1.2 完整数据流

```
用户消息
  │
  ▼
① 追加到 API 历史
  addToApiConversationHistory({ role: "user", content })
  │
  ▼
② attemptApiRequest(retryAttempt)
  ├── manageContext(...)           ← 上下文管理（可能压缩/截断，见第二章）
  ├── getEffectiveApiHistory(...)  ← 过滤隐藏消息
  ├── 构建 systemPrompt + tools
  └── api.createMessage(...)       ← 调用 LLM，返回流
  │
  ▼
③ 流式处理（逐 chunk 消费）
  ├── "text"          → 追加到 assistantMessage 文本
  ├── "reasoning"     → 推理过程（thinking tokens）
  ├── "usage"         → 更新 token 计数（防抖发送）
  └── "tool_call_partial" → NativeToolCallParser 解析
        │
        ▼ tool_call_start 事件触发
④ presentAssistantMessage()  ← 流式期间立即执行工具
  ├── 校验工具参数
  ├── askApproval() 等待用户确认（危险操作）
  ├── 执行工具逻辑
  └── 将结果追加到 userMessageContent（tool_result）
  │
  ▼
⑤ 流结束
  ├── 保存 assistant 消息到历史
  ├── userMessageContent 即为下一轮的 userContent
  └── 若 didEndLoop=false → 继续 while 循环
```

**关键设计：工具在流式过程中立即执行**，不等待整个响应完成。这使得 TUI 可以实时显示工具执行进度。

### 1.3 循环终止条件

| 条件 | 处理方式 |
|------|---------|
| Agent 调用 `attempt_completion` | `didEndLoop = true`，退出 while |
| 用户 abort | `this.abort = true`，下次 chunk 检测到后 break |
| 连续错误超限 | `consecutiveMistakeCount >= limit` → ask 用户是否继续 |
| 上下文压缩失败（3次） | 抛出异常，任务终止 |
| 栈为空 | while 自然退出 |

### 1.4 "未使用工具"的处理

LLM 只输出文本、未调用任何工具时：

```
consecutiveNoToolUseCount++
consecutiveMistakeCount++

if (consecutiveMistakeCount >= DEFAULT_CONSECUTIVE_MISTAKE_LIMIT) {
  // 向用户询问："模型似乎卡住了，是否继续？"
  await this.ask("mistake_limit_reached", ...)
  // 若用户选继续 → 重置计数，追加提示后继续循环
  // 若用户取消 → 抛出异常
}
```

默认限制：`DEFAULT_CONSECUTIVE_MISTAKE_LIMIT = 10`

### 1.5 错误处理分类

```
API 错误
├── context_window_exceeded
│   ├── retryAttempt < 3 → handleContextWindowExceededError() → 强制截断75% → 重试
│   └── >= 3 次 → 抛出，任务失败
│
├── 速率限制 / 一般 API 错误
│   ├── autoApproval 开启 → 指数退避后自动重试（max 10 分钟）
│   └── 手动模式 → ask("api_req_failed") 等待用户决定
│
├── 流中断（mid-stream failure）
│   ├── 优雅关闭流
│   └── 压回栈，重试（带退避）
│
└── 工具执行错误
    └── 封装为 tool_result { is_error: true } 注入历史，让 LLM 自行处理
```

### 1.6 指数退避实现

```typescript
const exponentialDelay = Math.min(
  Math.ceil(baseDelay * Math.pow(2, retryAttempt)),
  600  // 最大 600 秒（10分钟）
)

// 带倒计时 UI 更新
for (let i = exponentialDelay; i > 0; i--) {
  await this.say("api_req_rate_limited", JSON.stringify({ seconds: i }), undefined, true)
  await delay(1000)
}
```

**对 TUI 的启示**：倒计时每秒更新一次 UI，需要 TUI 支持局部刷新。

### 1.7 用户批准机制（ask/answer 模式）

危险工具执行前挂起循环，等待用户响应：

```typescript
// 工具内部
const { response } = await this.ask("tool", {
  tool: "write_to_file",
  path: filePath,
  // ...
})

if (response !== "yesButtonClicked") {
  // 用户拒绝 → pushToolResult("Tool was rejected")
  return
}
// 用户批准 → 继续执行
```

`ask()` 是 **async/await 阻塞**，循环在此处暂停，直到用户在 UI 点击确认/拒绝。

**TUI 实现要点**：需要一个 "等待用户输入" 的异步信号机制（如 Promise + 键盘事件）。

### 1.8 Abort/取消机制

```typescript
// 任意时刻可设置
this.abort = true

// 循环开头检测
if (this.abort) {
  if (!this.abandoned) await abortStream("user_cancelled")
  break
}

// 流处理中每个 chunk 也检测
```

---

## 二、上下文管理（Context Management）

### 2.1 三层防御架构

```
Token 使用量 / 上下文窗口占比
         │
         ▼  超过 threshold（默认 80%）
┌─────────────────────────────────────┐
│  Layer 1：自动摘要（Auto-Condense）  │
│  - 调用 LLM 生成摘要                │
│  - 摘要替代历史消息（非破坏性）      │
│  - 保留命令块、文件定义等关键内容    │
└─────────────────────────────────────┘
         │  摘要失败 / 仍超出
         ▼
┌─────────────────────────────────────┐
│  Layer 2：滑动窗口截断（Truncation） │
│  - 删除 50% 中段消息（非破坏性）     │
│  - 插入截断标记                      │
└─────────────────────────────────────┘
         │  API 返回 context_window_exceeded
         ▼
┌─────────────────────────────────────┐
│  Layer 3：强制截断（75% 减少）       │
│  - 最多重试 3 次                     │
└─────────────────────────────────────┘
```

### 2.2 触发时机与阈值计算

**触发位置**：`attemptApiRequest()` 中，每次 API 调用**前**执行：

```typescript
// 在 API 请求前检查
const contextManagementWillRun = willManageContext({ ... })
if (contextManagementWillRun) {
  // 通知 UI："正在压缩上下文..."
}
await manageContext({ ... })
// 执行完后才发起 API 请求
```

**阈值计算**（`willManageContext()`）：

```typescript
const contextPercent = (prevContextTokens / contextWindow) * 100
const allowedTokens = contextWindow * (1 - 0.10) - reservedTokens
                                          ↑ 10% 安全缓冲

return contextPercent >= effectiveThreshold || prevContextTokens > allowedTokens
```

阈值优先级：用户单独配置（按 profile）> 全局设置（默认 80%）

### 2.3 摘要生成细节

**摘要系统提示**（单独的 LLM 调用，不带工具）：
```
"You are a helpful AI assistant tasked with summarizing conversations.
CRITICAL: This is a summarization-only request. DO NOT call any tools..."
```

**摘要保留策略**：

| 内容 | 是否保留 | 原因 |
|------|---------|------|
| `<command>` 块 | ✅ 完整保留 | 活跃工作流 |
| 已读文件的代码定义 | ✅ 保留（folded context） | 代码上下文 |
| 环境详情（自动触发时） | ✅ 保留 | 工作目录、OS 等 |
| 图像块 | ❌ 移除 | 节省 token |
| 普通对话消息 | ✅ 摘要化 | 压缩但不丢失 |

**摘要消息结构**：

```typescript
{
  role: "user",
  content: [
    { type: "text", text: "## Conversation Summary\n{摘要内容}" },
    // 追加：命令块（<system-reminder>包裹）
    // 追加：文件代码定义
    // 追加：环境详情（自动触发时）
  ],
  isSummary: true,
  condenseId: "xxx",  // 关联被替代的消息
}
```

### 2.4 非破坏性历史标记

所有操作都**标记而非删除**：

```typescript
// 摘要时：被替代的消息打上标记
messages.forEach(msg => {
  if (shouldCondense(msg)) msg.condenseParent = condenseId
})

// 截断时：被隐藏的消息打上标记
messages.forEach(msg => {
  if (shouldTruncate(msg)) msg.truncationParent = truncationId
})
```

**好处**：
- 支持任意点 rewind（移除标记即恢复）
- 调试可见（可查看"被隐藏"的历史）
- 不影响持久化（全量保存，按需过滤）

### 2.5 `getEffectiveApiHistory()` — 核心过滤函数

发送给 LLM 前，对历史做过滤：

```typescript
function getEffectiveApiHistory(messages: ApiMessage[]): ApiMessage[] {
  const lastSummary = findLast(messages, msg => msg.isSummary)

  if (lastSummary) {
    // 有摘要：只返回摘要起始之后的消息（真正的"新起点"）
    let fresh = messages.slice(summaryIndex)
    // 过滤掉孤立的 tool_result（其 tool_use 在摘要之前）
    fresh = filterOrphanToolResults(fresh)
    // 过滤掉被截断的消息
    return fresh.filter(msg => !msg.truncationParent)
  }

  // 无摘要：过滤被摘要/截断标记的消息
  return messages.filter(msg =>
    !msg.condenseParent &&
    !msg.truncationParent
  )
}
```

**孤立 tool_result 处理**（重要边界情况）：

```
摘要前：[tool_use id=A] → 摘要 → [tool_result tool_use_id=A]

发送给 LLM 时，摘要后的 tool_result A 没有对应的 tool_use A
→ 必须过滤掉，否则 API 报错
```

### 2.6 截断算法（滑动窗口）

```typescript
// 获取可见消息（排除已截断的）
const visibleIndices = messages
  .map((msg, i) => [msg, i])
  .filter(([msg]) => !msg.truncationParent && !msg.isTruncationMarker)
  .map(([, i]) => i)

// 计算移除数量（默认 50%，向偶数取整保持 user/assistant 配对）
const toRemove = Math.floor(visibleIndices.length * 0.5)
const toRemoveEven = toRemove - (toRemove % 2)

// 标记中间段（跳过第一条消息）
const indicesToTruncate = new Set(visibleIndices.slice(1, toRemoveEven + 1))
messages.forEach((msg, i) => {
  if (indicesToTruncate.has(i)) msg.truncationParent = truncationId
})

// 插入截断标记
insertTruncationMarker(at: firstKeptMessage.ts - 1)
```

**偶数取整**是关键：确保 user/assistant 消息成对移除，避免历史顺序错乱。

### 2.7 Tool Results 的特殊处理

`flushPendingToolResultsToHistory()` 使用轮询等待：

```typescript
await pWaitFor(
  () => this.assistantMessageSavedToHistory || this.abort,
  { timeout: 30_000 }
)
```

**原因**：tool_result 必须在对应 tool_use 之后出现在历史中。
流式响应时，assistant 消息的保存可能略晚于工具执行完成。

---

## 三、模式系统（Modes System）

### 3.1 模式数据结构

```typescript
type ModeConfig = {
  slug: string              // 标识符，如 "code", "architect"
  name: string              // 显示名，如 "💻 Code"
  roleDefinition: string    // 注入系统提示的角色描述（核心）
  customInstructions?: string  // 模式专属附加指令
  whenToUse?: string        // UI 提示：何时使用此模式
  description?: string      // 简短描述
  groups: GroupEntry[]      // 允许的工具组
  source?: "global" | "project"  // 配置来源
}

// 工具组可携带限制
type GroupEntry =
  | "read"                                    // 简单：工具组名
  | ["edit", { fileRegex: "\\.md$" }]        // 带限制：只能编辑 .md 文件
```

### 3.2 五个内置模式对比

| 模式 | Slug | 可用工具组 | 核心职责 |
|------|------|----------|---------|
| **Code** | `code` | read, edit, command, mcp | 全能编码 |
| **Architect** | `architect` | read, edit(仅.md), mcp | 规划、架构设计 |
| **Ask** | `ask` | read, mcp | 只读问答分析 |
| **Debug** | `debug` | read, edit, command, mcp | 系统化调试 |
| **Orchestrator** | `orchestrator` | （无直接工具） | 分解任务、委托子任务 |

**工具组包含的工具**：

| 组名 | 包含工具 |
|------|---------|
| `read` | read_file, list_files, search_files, codebase_search |
| `edit` | write_to_file, edit_file, apply_diff, search_and_replace |
| `command` | execute_command, read_command_output |
| `mcp` | use_mcp_tool, access_mcp_resource |

**始终可用的工具**（所有模式）：
`attempt_completion`, `ask_followup_question`, `switch_mode`, `update_todo_list`, `new_task`

### 3.3 模式对系统提示的影响

```typescript
// SYSTEM_PROMPT() 构建时：
const { roleDefinition, baseInstructions } = getModeSelection(mode, customModePrompts, customModes)

systemPrompt = [
  roleDefinition,           // ← 模式角色描述（最前面）
  environmentDetails,       // 工作目录、OS、时间等
  toolDocumentation,        // 当前模式可用工具的文档
  baseInstructions,         // ← 模式专属指令
  globalCustomInstructions, // 用户全局指令
].join("\n\n")
```

**模式切换时：**
- 下一次 API 请求使用新的系统提示
- 当前对话历史**完整保留**（不清空）
- LLM "继承"所有历史上下文，但角色定义变了

### 3.4 模式切换实现

```typescript
// 工具：switch_mode
class SwitchModeTool extends BaseTool<"switch_mode"> {
  async execute({ mode_slug, reason }, task, callbacks) {
    const provider = task.providerRef.deref()
    await provider.handleModeSwitch(mode_slug)
    // 通知 UI 更新显示
    // 下一个 API 请求自动使用新模式的系统提示
  }
}
```

或用户通过 `/` 命令直接切换：

```typescript
// 处理 slash 命令时
const { mode: slashCommandMode } = parseSlashCommand(userInput)
if (slashCommandMode) {
  await provider.handleModeSwitch(slashCommandMode)
}
```

**模式切换不重置历史**，所以可以做到：
1. 在 Architect 模式中规划任务（写 .md）
2. 切换到 Code 模式实现
3. 切换到 Debug 模式排查
4. 全程上下文连贯

### 3.5 文件限制（fileRegex）执行

```typescript
// edit 操作时检查
if (modeFileRegex && !new RegExp(modeFileRegex).test(filePath)) {
  throw new FileRestrictionError(
    currentMode,
    modeFileRegex,
    description,
    filePath,
    toolName
  )
  // 错误信息：
  // "Tool 'edit_file' in mode 'architect' can only edit files matching: \.md$. Got: src/main.c"
}
```

### 3.6 自定义模式（.roomodes）

项目根目录的 `.roomodes` 文件定义项目专属模式：

```yaml
customModes:
  - slug: c-expert
    name: "⚡ C Expert"
    roleDefinition: "You are an expert embedded C developer..."
    customInstructions: |
      - Always check for buffer overflows
      - Prefer stack allocation over heap
      - Use MISRA C guidelines where applicable
    groups:
      - read
      - command
      - ["edit", { fileRegex: "\\.(c|h|ld|mk|Makefile)$" }]
    source: project
```

**用于我们项目的直接价值**：直接定义 `c-embedded` 模式，限定只能编辑 `.c/.h/.ld` 等文件。

---

## 四、三个机制的整合关系

```
用户消息
    │
    ▼
[模式系统] 决定：
  ├── 哪些工具可用（groups）
  ├── 系统提示内容（roleDefinition + customInstructions）
  └── 文件编辑限制（fileRegex）
    │
    ▼
[Agent 循环] 执行：
  ├── 构建请求（含当前模式的系统提示）
  ├── 流式调用 LLM
  ├── 解析 + 执行工具（受模式限制）
  ├── ask/answer 挂起等待用户批准
  └── 循环直到完成 / 报错 / 取消
    │
    ▼ 每次 API 调用前
[上下文管理] 保障：
  ├── 检测 token 超阈值 → 摘要（保留关键内容）
  ├── 摘要失败 → 截断（保留首尾）
  ├── getEffectiveApiHistory() 过滤隐藏消息
  └── 确保发给 LLM 的历史始终合法
```

---

## 五、对我们项目的关键启示

### 5.1 Agent 循环设计建议

1. **用显式栈代替递归**：更清晰的重试追踪，避免栈溢出
2. **流式处理中即时执行工具**：提升 TUI 响应感
3. **ask/answer 挂起模式**：危险操作必须，实现为 Promise + 键盘输入
4. **连续错误计数器**：防止无限循环是必须的安全机制
5. **指数退避最大限制**：本地模型不需要，但 API 接入时必要

### 5.2 上下文管理建议

1. **三层策略完整实现**：本地小模型（如 Qwen 7B）上下文窗口只有 8K-32K，更需要主动管理
2. **非破坏性标记**：为未来的"会话回放/回退"功能预留空间
3. **偶数截断**：保证 user/assistant 配对，这是容易被忽略的细节
4. **孤立 tool_result 处理**：摘要边界处理，否则 API 会报错

### 5.3 模式系统简化建议

针对嵌入式C开发，建议三个模式：

| 模式 | 工具权限 | 文件限制 |
|------|---------|---------|
| **Plan**（规划） | read, edit(仅.md) | 只能写文档 |
| **Code**（编码） | read, edit, command | 只能改 .c/.h/.ld/.mk |
| **Debug**（调试） | read, edit, command | 同上，但系统提示强调调试思路 |

**不建议实现 Orchestrator 模式**（子任务委托复杂度高），未来扩展时再加。

### 5.4 模式切换与历史共享

**历史共享（不重置）是对的**：
- 规划阶段已读的文档内容，编码阶段无需重新读
- 调试时能看到之前写了什么代码

但可以在切换时注入一条 system 消息告知 LLM 模式已变更，帮助它调整行为。
