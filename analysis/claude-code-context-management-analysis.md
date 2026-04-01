# Claude Code 上下文管理实现分析报告

## 1. 概述

本报告深入分析 Claude Code（anthropic_claude_code）项目中的上下文管理系统。上下文管理是 AI 助手的核心能力，负责维护和管理对话历史、工具定义、系统提示和内存文件等内容，确保在有限的 token 预算内高效工作。

## 2. 上下文管理架构概览

### 2.1 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                      Context Management System                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ System Context│  │ User Context │  │ Tool Registry│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Message History                        │  │
│  │  (User/Assistant/Attachment/System/Progress messages)     │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Auto Compact │  │ Micro Compact│  │ Session Memory│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 关键模块分布

| 模块 | 路径 | 职责 |
|------|------|------|
| 上下文生成 | `src/context.ts` | 系统和用户上下文的生成与缓存 |
| 上下文工具 | `src/utils/context.ts` | Token 计算、模型上下文窗口管理 |
| 上下文分析 | `src/utils/analyzeContext.ts` | 详细的上下文使用分析 |
| 上下文分析器 | `src/utils/contextAnalysis.ts` | 轻量级上下文统计分析 |
| 自动压缩 | `src/services/compact/autoCompact.ts` | 自动压缩决策逻辑 |
| 完全压缩 | `src/services/compact/compact.ts` | 完整的对话压缩实现 |
| 微压缩 | `src/services/compact/microCompact.ts` | 轻量级工具结果清理 |
| 可视化 | `src/components/ContextVisualization.tsx` | 上下文使用可视化 |

## 3. 上下文组成详解

### 3.1 系统上下文 (`getSystemContext`)

```typescript
// src/context.ts
export const getSystemContext = memoize(async (): Promise<{[k: string]: string}> => {
  const gitStatus = await getGitStatus()  // Git 状态快照
  const injection = getSystemPromptInjection()  // 缓存破坏器（仅内部使用）
  
  return {
    ...(gitStatus && { gitStatus }),
    ...(feature('BREAK_CACHE_COMMAND') && injection ? { cacheBreaker: ... } : {})
  }
})
```

**系统上下文包含：**
- **Git 状态**：当前分支、主分支、git 用户信息、状态摘要、最近提交
- **缓存破坏器**：用于强制刷新提示缓存（仅内部使用）

**特点：**
- 使用 `lodash.memoize` 缓存整个会话期间
- 在远程会话 (CCR) 中跳过 Git 状态以减少开销
- Git 状态限制在 2000 字符以内

### 3.2 用户上下文 (`getUserContext`)

```typescript
export const getUserContext = memoize(async (): Promise<{[k: string]: string}> => {
  const claudeMd = shouldDisableClaudeMd ? null : getClaudeMds(...)
  
  return {
    ...(claudeMd && { claudeMd }),
    currentDate: `Today's date is ${getLocalISODate()}.`
  }
})
```

**用户上下文包含：**
- **CLAUDE.md 文件**：项目特定的指令和上下文
- **当前日期**：ISO 格式的本地日期

**特点：**
- 支持 `--bare` 模式跳过自动发现
- 可通过环境变量完全禁用
- 缓存用于自动模式分类器

### 3.3 上下文窗口管理

```typescript
// src/utils/context.ts
export function getContextWindowForModel(model: string, betas?: string[]): number {
  // 环境变量覆盖（最高优先级）
  if (process.env.CLAUDE_CODE_MAX_CONTEXT_TOKENS) {
    return parseInt(process.env.CLAUDE_CODE_MAX_CONTEXT_TOKENS, 10)
  }
  
  // [1m] 后缀显式启用 100万 token 上下文
  if (has1mContext(model)) return 1_000_000
  
  // Beta header 启用 100万 token
  if (betas?.includes(CONTEXT_1M_BETA_HEADER) && modelSupports1M(model)) {
    return 1_000_000
  }
  
  return MODEL_CONTEXT_WINDOW_DEFAULT  // 200,000
}
```

**支持的上下文窗口大小：**
- 默认：200K tokens
- 1M 模式：1,000,000 tokens（特定模型）
- 环境变量可覆盖

## 4. 上下文压缩系统

### 4.1 三级压缩架构

Claude Code 实现了三层递进式上下文管理：

```
┌─────────────────────────────────────────────────────────────┐
│ Level 1: Micro Compact (微压缩)                               │
│ - 清理旧工具结果                                              │
│ - 基于时间或数量的轻量级清理                                   │
│ - 不修改对话结构                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓ 当微压缩不足时
┌─────────────────────────────────────────────────────────────┐
│ Level 2: Session Memory (会话内存)                            │
│ - 将旧消息移出到磁盘存储                                      │
│ - 保留最近消息在内存中                                        │
│ - 支持按需加载历史                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓ 当会话内存不足时
┌─────────────────────────────────────────────────────────────┐
│ Level 3: Full Compact (完全压缩)                              │
│ - 生成对话摘要替代详细历史                                    │
│ - 使用子代理进行智能总结                                      │
│ - 保留最近消息作为上下文窗口                                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 微压缩 (Micro Compact)

**目标：** 在不影响对话结构的前提下减少 token 使用

**实现位置：** `src/services/compact/microCompact.ts`

**两种触发模式：**

#### 4.2.1 基于时间的微压缩
```typescript
function maybeTimeBasedMicrocompact(messages: Message[], querySource: QuerySource): MicrocompactResult {
  // 当距离上次助手消息超过阈值（如 2 分钟）时触发
  const gapMinutes = (Date.now() - lastAssistantTimestamp) / 60_000
  
  if (gapMinutes >= config.gapThresholdMinutes) {
    // 清理除最近 N 个外的所有可压缩工具结果
    const clearSet = new Set(compactableIds.slice(0, -keepRecent))
    // 将工具结果内容替换为占位符
    return { messages: replaceToolResultsWithPlaceholder(messages, clearSet) }
  }
}
```

#### 4.2.2 缓存编辑微压缩（Cached MC）
```typescript
async function cachedMicrocompactPath(messages: Message[]): Promise<MicrocompactResult> {
  const state = ensureCachedMCState()
  const toolsToDelete = mod.getToolResultsToDelete(state)
  
  if (toolsToDelete.length > 0) {
    // 创建 cache_edits 块供 API 层使用
    const cacheEdits = mod.createCacheEditsBlock(state, toolsToDelete)
    pendingCacheEdits = cacheEdits
    
    // 消息内容不变，通过 API 层删除缓存
    return { messages, compactionInfo: { pendingCacheEdits: {...} } }
  }
}
```

**可压缩工具列表：**
- `Read` - 文件读取
- `Bash`/`PowerShell` - Shell 命令
- `Grep`/`Glob` - 搜索工具
- `WebSearch`/`WebFetch` - 网络工具
- `FileEdit`/`FileWrite` - 文件编辑

### 4.3 自动压缩 (Auto Compact)

**触发条件：** `src/services/compact/autoCompact.ts`

```typescript
export function getAutoCompactThreshold(model: string): number {
  const effectiveContextWindow = getEffectiveContextWindowSize(model)
  return effectiveContextWindow - AUTOCOMPACT_BUFFER_TOKENS  // 默认 13,000
}

export async function shouldAutoCompact(
  messages: Message[],
  model: string,
  querySource?: QuerySource
): Promise<boolean> {
  // 防止递归：session_memory 和 compact 查询源不触发
  if (querySource === 'session_memory' || querySource === 'compact') return false
  
  const tokenCount = tokenCountWithEstimation(messages)
  const threshold = getAutoCompactThreshold(model)
  
  return tokenCount >= threshold
}
```

**自动压缩决策流程：**

```
消息数/Token 数检查
       ↓
是否超过阈值? ──否──→ 继续正常处理
       ↓ 是
尝试会话内存压缩
       ↓
成功? ──是──→ 完成
       ↓ 否
执行完全压缩
       ↓
生成摘要消息
       ↓
保留最近消息
       ↓
重新注入附件和计划
```

### 4.4 完全压缩 (Full Compact)

**核心实现：** `src/services/compact/compact.ts`

**压缩流程：**

```typescript
export async function compactConversation(
  messages: Message[],
  context: ToolUseContext,
  cacheSafeParams: CacheSafeParams,
  suppressFollowUpQuestions: boolean,
  customInstructions?: string,
  isAutoCompact: boolean = false
): Promise<CompactionResult> {
  
  // 1. 执行 PreCompact Hooks
  const hookResult = await executePreCompactHooks(...)
  
  // 2. 流式生成摘要
  const summaryResponse = await streamCompactSummary({
    messages: messagesToSummarize,
    summaryRequest: createUserMessage({ content: compactPrompt }),
    ...
  })
  
  // 3. 清理状态
  context.readFileState.clear()
  context.loadedNestedMemoryPaths?.clear()
  
  // 4. 创建压缩后附件
  const [fileAttachments, asyncAgentAttachments] = await Promise.all([
    createPostCompactFileAttachments(...),
    createAsyncAgentAttachmentsIfNeeded(...)
  ])
  
  // 5. 重新注入关键附件
  postCompactFileAttachments.push(
    createPlanAttachmentIfNeeded(...),
    createPlanModeAttachmentIfNeeded(...),
    createSkillAttachmentIfNeeded(...)
  )
  
  // 6. 执行 SessionStart Hooks
  const hookMessages = await processSessionStartHooks('compact', ...)
  
  // 7. 创建边界标记和摘要消息
  const boundaryMarker = createCompactBoundaryMessage('auto' | 'manual', ...)
  const summaryMessages = [createUserMessage({
    content: getCompactUserSummaryMessage(summary, ...),
    isCompactSummary: true
  })]
  
  return {
    boundaryMarker,
    summaryMessages,
    attachments: postCompactFileAttachments,
    hookResults: hookMessages,
    ...
  }
}
```

**压缩提示设计：**

压缩使用专门的提示模板（`src/services/compact/prompt.ts`）指导模型生成结构化摘要：

```
NO_TOOLS_PREAMBLE（强制文本响应）
  ↓
DETAILED_ANALYSIS_INSTRUCTION（分析指导）
  ↓
BASE_COMPACT_PROMPT（9个必须部分）
  ├── 1. Primary Request and Intent（主要请求和意图）
  ├── 2. Key Technical Concepts（关键技术概念）
  ├── 3. Files and Code Sections（文件和代码段）
  ├── 4. Errors and fixes（错误和修复）
  ├── 5. Problem Solving（问题解决）
  ├── 6. All user messages（所有用户消息）
  ├── 7. Pending Tasks（待处理任务）
  ├── 8. Current Work（当前工作）
  └── 9. Optional Next Step（可选的下一步）
```

**部分压缩 (Partial Compact)：**

支持从特定消息点进行部分压缩，保留一侧的完整消息：

```typescript
export async function partialCompactConversation(
  allMessages: Message[],
  pivotIndex: number,
  direction: PartialCompactDirection = 'from'  // 'from' | 'up_to'
): Promise<CompactionResult> {
  // 'from': 保留 pivotIndex 之前的消息，总结之后的
  // 'up_to': 总结 pivotIndex 之前的消息，保留之后的
}
```

### 4.5 Prompt-Too-Long (PTL) 处理

当压缩请求本身触发提示过长错误时，有专门的降级处理：

```typescript
export function truncateHeadForPTLRetry(
  messages: Message[],
  ptlResponse: AssistantMessage
): Message[] | null {
  // 按 API 轮次分组消息
  const groups = groupMessagesByApiRound(input)
  
  // 计算需要删除的消息组数以满足 token 缺口
  let dropCount = 0
  let acc = 0
  for (const g of groups) {
    acc += roughTokenCountEstimationForMessages(g)
    dropCount++
    if (acc >= tokenGap) break
  }
  
  // 保留至少一个组，确保有内容可总结
  dropCount = Math.min(dropCount, groups.length - 1)
  return groups.slice(dropCount).flat()
}
```

## 5. 上下文分析系统

### 5.1 详细上下文分析

**实现：** `src/utils/analyzeContext.ts`

提供完整的上下文使用分解，用于 `/context` 命令：

```typescript
export interface ContextData {
  categories: ContextCategory[]      // 分类统计（系统、工具、消息等）
  totalTokens: number                // 总 token 数
  maxTokens: number                  // 最大可用 token
  percentage: number                 // 使用率百分比
  gridRows: GridSquare[][]          // 可视化网格
  model: string                      // 当前模型
  memoryFiles: MemoryFile[]         // 内存文件列表
  mcpTools: McpTool[]               // MCP 工具列表
  deferredBuiltinTools?: DeferredBuiltinTool[]  // 延迟加载的内置工具
  systemTools?: SystemToolDetail[]  // 系统工具详情
  systemPromptSections?: SystemPromptSectionDetail[]  // 系统提示部分
  agents: Agent[]                   // 自定义代理
  slashCommands?: SlashCommandInfo  // 斜杠命令信息
  skills?: SkillInfo                // Skills 信息
  messageBreakdown?: {...}          // 消息详细分解
  apiUsage: {...} | null            // API 实际使用统计
}
```

**Token 计算流程：**

```
1. countSystemTokens()
   ├── 系统提示各部分
   └── 系统上下文（Git 状态等）
   
2. countMemoryFileTokens()
   └── CLAUDE.md 文件内容
   
3. countBuiltInToolTokens()
   ├── 始终加载的工具
   └── 延迟加载的工具（仅计算已加载的）
   
4. countMcpToolTokens()
   ├── MCP 工具总数
   └── 区分已加载/延迟的工具
   
5. countCustomAgentTokens()
   └── 自定义代理定义
   
6. countSlashCommandTokens()
   └── SkillTool 命令
   
7. approximateMessageTokens()
   ├── 工具调用 token
   ├── 工具结果 token
   ├── 附件 token
   ├── 助手消息 token
   └── 用户消息 token
```

### 5.2 轻量级上下文分析

**实现：** `src/utils/contextAnalysis.ts`

用于遥测和内部统计的快速分析：

```typescript
export function analyzeContext(messages: Message[]): TokenStats {
  const stats: TokenStats = {
    toolRequests: new Map(),
    toolResults: new Map(),
    humanMessages: 0,
    assistantMessages: 0,
    localCommandOutputs: 0,
    other: 0,
    attachments: new Map(),
    duplicateFileReads: new Map(),
    total: 0
  }
  
  // 遍历所有消息和块，分类统计
  messages.forEach(msg => {
    processBlock(block, msg, stats, toolIds, readToolPaths, fileReads)
  })
  
  // 计算重复文件读取的浪费
  fileReadStats.forEach((data, path) => {
    if (data.count > 1) {
      const duplicateTokens = averageTokensPerRead * (data.count - 1)
      stats.duplicateFileReads.set(path, { count: data.count, tokens: duplicateTokens })
    }
  })
  
  return stats
}
```

## 6. 消息管理系统

### 6.1 消息类型体系

```typescript
// src/types/message.ts
type Message = 
  | UserMessage           // 用户输入
  | AssistantMessage      // 助手回复
  | AttachmentMessage     // 附件（技能发现、文件等）
  | SystemMessage         // 系统消息（紧凑边界、错误等）
  | ProgressMessage       // 进度消息
  | HookResultMessage     // Hook 结果
  | TombstoneMessage      // 墓碑消息（已删除）
```

### 6.2 紧凑边界消息

```typescript
export interface SystemCompactBoundaryMessage extends BaseSystemMessage {
  type: 'system'
  systemMessageType: 'compact_boundary'
  compactMetadata: {
    trigger: 'auto' | 'manual'
    preCompactTokenCount: number
    previousLastMessageUuid?: UUID
    preCompactDiscoveredTools?: string[]  // 保留已发现的延迟工具
    preservedSegment?: {                  // 部分压缩保留的段
      headUuid: UUID
      anchorUuid: UUID
      tailUuid: UUID
    }
  }
}
```

### 6.3 消息归一化

**API 请求前处理：** `src/utils/messages.ts`

```typescript
export function normalizeMessagesForAPI(
  messages: Message[],
  options?: NormalizeOptions
): NormalizedMessage[] {
  return messages
    .filter(msg => shouldIncludeMessage(msg, options))  // 过滤
    .map(msg => transformMessage(msg))                   // 转换
    .flat()                                              // 展平
}
```

**处理步骤：**
1. 过滤掉进度消息、虚拟消息、墓碑消息
2. 转换消息格式为 API 兼容格式
3. 处理工具调用/结果配对
4. 处理图像验证和缩放
5. 应用输出样式配置

## 7. 工具加载优化

### 7.1 延迟加载（Deferred Loading）

为减少上下文占用，支持工具的延迟加载：

```typescript
// src/tools/ToolSearchTool/prompt.ts
export function isDeferredTool(tool: Tool): boolean {
  // 特定工具（如复杂 MCP 工具）默认不加载
  // 仅在首次使用时通过 ToolSearchTool 加载
  return DEFERRED_TOOLS.has(tool.name) || tool.isDeferred
}
```

**加载流程：**
1. 初始只加载核心工具集
2. 模型通过 `ToolSearchTool` 请求加载特定工具
3. 工具定义动态添加到上下文
4. 后续调用可直接使用该工具

### 7.2 工具 Token 计算优化

```typescript
// 工具定义 Token 计算时减去固定开销
const TOOL_TOKEN_COUNT_OVERHEAD = 500

export async function countToolDefinitionTokens(
  tools: Tools,
  getToolPermissionContext: () => Promise<ToolPermissionContext>,
  agentInfo: AgentDefinitionsResult | null,
  model?: string
): Promise<number> {
  const toolSchemas = await Promise.all(
    tools.map(tool => toolToAPISchema(tool, {...}))
  )
  const result = await countTokensWithFallback([], toolSchemas)
  // 减去单次调用开销，避免重复计算
  return (result ?? 0) - TOOL_TOKEN_COUNT_OVERHEAD
}
```

## 8. 可视化与监控

### 8.1 上下文可视化组件

**实现：** `src/components/ContextVisualization.tsx`

```
┌────────────────────────────────────────────────────────────────┐
│ Context Usage                                                  │
│ ┌──────────────────────┐  Sonnet-4-6 · 45,230/200,000 (23%)   │
│ │ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝ │  Estimated usage by category         │
│ │ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝ ⛝ │                                      │
│ │ ⛝ ⛝ ⛝ ⛝ ◒ ◒ ◒ ◒    │  ⛝ System prompt: 12,340 (6.2%)    │
│ │ ◒ ◒ ◒ ◒ ◒ ◒ ◒ ◒    │  ⛝ Built-in tools: 8,920 (4.5%)    │
│ │ ◒ ◒ ◒ ◒ ◒ ◒ ◒ ◒    │  ⛝ MCP tools: 15,670 (7.8%)        │
│ │ ◒ ◒ ◒ ◒ ◒ ◒ ◒ ◒    │  ⛝ Messages: 8,300 (4.2%)          │
│ │ ◒ ◒ ◒ ◒ ◒ ⛶ ⛶ ⛶    │  ⛝ Memory files: 0 (0.0%)          │
│ └──────────────────────┘  ⛶ Free space: 154,770 (77.4%)       │
│                              ⛝ Autocompact buffer: 13,000      │
└────────────────────────────────────────────────────────────────┘
```

### 8.2 监控与告警

**Token 警告状态计算：**

```typescript
export function calculateTokenWarningState(
  tokenUsage: number,
  model: string
): {
  percentLeft: number
  isAboveWarningThreshold: boolean
  isAboveErrorThreshold: boolean
  isAboveAutoCompactThreshold: boolean
  isAtBlockingLimit: boolean
} {
  const autoCompactThreshold = getAutoCompactThreshold(model)
  const warningThreshold = threshold - WARNING_THRESHOLD_BUFFER_TOKENS  // 20K
  const errorThreshold = threshold - ERROR_THRESHOLD_BUFFER_TOKENS      // 20K
  const blockingLimit = actualContextWindow - MANUAL_COMPACT_BUFFER_TOKENS  // 3K
  
  return { ... }
}
```

## 9. 关键设计决策

### 9.1 缓存策略

| 组件 | 缓存方式 | 缓存键 | 失效时机 |
|------|----------|--------|----------|
| System Context | memoize | 无（全局单例） | 会话期间不变 |
| User Context | memoize | 无（全局单例） | 会话期间不变 |
| Git Status | memoize | 无 | 系统提示注入变化时 |
| 工具 Token 计数 | 实时计算 | 工具集合 | 每次请求 |

### 9.2 错误处理

**压缩失败降级策略：**
1. **首次失败**：记录错误，继续正常处理
2. **连续失败**：断路器触发，跳过未来尝试
3. **PTL 错误**：尝试截断头部消息重试（最多 3 次）

### 9.3 性能优化

1. **并行计算**：所有 Token 计数并行执行
2. **懒加载**：缓存编辑模块按需加载
3. **增量更新**：微压缩仅修改必要部分
4. **流式处理**：压缩摘要使用流式响应

## 10. 配置选项

### 10.1 环境变量

| 变量 | 功能 | 默认值 |
|------|------|--------|
| `CLAUDE_CODE_DISABLE_CLAUDE_MDS` | 禁用 CLAUDE.md 加载 | false |
| `CLAUDE_CODE_DISABLE_1M_CONTEXT` | 禁用 1M 上下文 | false |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | 覆盖最大上下文 token | - |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | 覆盖自动压缩窗口 | - |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | 覆盖自动压缩百分比 | - |
| `CLAUDE_CODE_BLOCKING_LIMIT_OVERRIDE` | 覆盖阻塞限制 | - |
| `DISABLE_COMPACT` | 禁用所有压缩 | false |
| `DISABLE_AUTO_COMPACT` | 仅禁用自动压缩 | false |

### 10.2 用户设置

```json
{
  "autoCompactEnabled": true,  // 启用自动压缩
  // 其他相关设置...
}
```

## 11. 总结

Claude Code 的上下文管理系统是一个多层次、智能化的系统，通过以下方式确保高效使用有限的 token 预算：

1. **分层压缩**：微压缩 → 会话内存 → 完全压缩的三级体系
2. **智能分析**：详细的上下文使用分析和可视化
3. **延迟加载**：按需加载工具，减少常驻上下文
4. **自动管理**：自动检测并执行压缩，减少用户负担
5. **容错设计**：多重降级策略确保服务连续性

这套系统使 Claude Code 能够在支持长达 100万 token 上下文的同时，保持响应速度和成本效益。

---

*报告生成日期：2026-04-01*
*分析源码版本：Claude Code (anthropic_claude_code)*
