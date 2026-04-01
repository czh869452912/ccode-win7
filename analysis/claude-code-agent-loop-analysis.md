# Claude Code Agent Loop 实现分析报告

## 1. 概述

Claude Code 的 Agent Loop 是一个复杂的状态机系统，负责协调与 Claude API 的交互、工具调用执行、上下文管理和错误恢复。本报告深入分析其核心架构和实现细节。

## 2. 核心架构

### 2.1 Agent Loop 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Agent Loop 架构                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   用户输入    │────▶│  Query Loop  │────▶│  API 调用    │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│                              │                       │                      │
│                              ▼                       ▼                      │
│                       ┌──────────────┐      ┌──────────────┐               │
│                       │ 上下文压缩    │      │ 流式响应处理  │               │
│                       │ (Compact)    │      │             │               │
│                       └──────────────┘      └──────────────┘               │
│                              │                       │                      │
│                              ▼                       ▼                      │
│                       ┌──────────────┐      ┌──────────────┐               │
│                       │ 工具调用执行  │◀─────│ 助手消息解析  │               │
│                       │(Tool Exec)   │      │             │               │
│                       └──────────────┘      └──────────────┘               │
│                              │                                             │
│                              ▼                                             │
│                       ┌──────────────┐                                    │
│                       │  递归继续     │                                    │
│                       │ (Next Turn)  │                                    │
│                       └──────────────┘                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| Query Loop | `query.ts` | 主循环逻辑，协调整个 Agent 执行流程 |
| Tool Orchestration | `services/tools/toolOrchestration.ts` | 工具调用编排，管理并发执行 |
| Streaming Tool Executor | `services/tools/StreamingToolExecutor.ts` | 流式工具执行器，支持实时工具调用 |
| Tool Execution | `services/tools/toolExecution.ts` | 单个工具的执行逻辑 |
| Context Management | `services/compact/` | 上下文压缩和内存管理 |

## 3. Query Loop 详解

### 3.1 主循环结构

```typescript
// query.ts
export async function* query(params: QueryParams): AsyncGenerator<...> {
  const consumedCommandUuids: string[] = [];
  const terminal = yield* queryLoop(params, consumedCommandUuids);
  // 通知命令生命周期完成
  for (const uuid of consumedCommandUuids) {
    notifyCommandLifecycle(uuid, 'completed');
  }
  return terminal;
}

async function* queryLoop(params: QueryParams, ...): AsyncGenerator<...> {
  // 初始化状态
  let state: State = {
    messages: params.messages,
    toolUseContext: params.toolUseContext,
    autoCompactTracking: undefined,
    turnCount: 1,
    // ...
  };

  // 无限循环，直到显式返回
  while (true) {
    // 1. 上下文准备阶段
    // 2. API 调用阶段
    // 3. 响应处理阶段
    // 4. 工具执行阶段
    // 5. 状态更新/递归继续
  }
}
```

### 3.2 循环状态定义

```typescript
type State = {
  messages: Message[]                           // 当前消息历史
  toolUseContext: ToolUseContext                // 工具使用上下文
  autoCompactTracking: AutoCompactTrackingState | undefined  // 自动压缩追踪
  maxOutputTokensRecoveryCount: number          // 输出令牌恢复计数
  hasAttemptedReactiveCompact: boolean          // 是否已尝试响应式压缩
  maxOutputTokensOverride: number | undefined   // 最大输出令牌覆盖
  pendingToolUseSummary: Promise<ToolUseSummaryMessage | null> | undefined
  stopHookActive: boolean | undefined           // Stop Hook 是否激活
  turnCount: number                             // 当前轮次计数
  transition: Continue | undefined              // 上一轮继续原因
}
```

### 3.3 单次迭代流程

```
┌────────────────────────────────────────────────────────────────┐
│                      单次迭代流程                               │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. PREPARE PHASE                                               │
│     ├── 启动记忆预取 (startRelevantMemoryPrefetch)              │
│     ├── 应用工具结果预算 (applyToolResultBudget)                │
│     ├── 应用 Snip 压缩 (snipCompactIfNeeded)                   │
│     ├── 应用微压缩 (microcompactMessages)                      │
│     ├── 应用上下文折叠 (applyCollapsesIfNeeded)                │
│     └── 自动压缩检查 (autoCompactIfNeeded)                     │
│                                                                 │
│  2. API CALL PHASE                                              │
│     ├── 构建系统提示词                                          │
│     ├── 检查阻塞限制 (blocking limit)                           │
│     ├── 流式调用模型 (callModel)                               │
│     └── 处理流式响应                                             │
│         ├── 提取工具调用块                                       │
│         └── 启动流式工具执行                                     │
│                                                                 │
│  3. RESPONSE HANDLING                                           │
│     ├── 检查是否中止                                            │
│     ├── 处理提示过长错误 (Prompt Too Long)                      │
│     ├── 处理最大输出令牌错误                                     │
│     ├── 执行 Stop Hooks                                         │
│     └── 检查 Token 预算                                         │
│                                                                 │
│  4. TOOL EXECUTION PHASE                                        │
│     ├── 串行/并发工具执行决策                                    │
│     ├── 执行工具调用                                            │
│     └── 收集工具结果                                            │
│                                                                 │
│  5. NEXT TURN                                                   │
│     ├── 添加附件消息                                            │
│     ├── 刷新工具列表                                            │
│     └── 递归调用 (continue)                                     │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

## 4. 工具执行系统

### 4.1 两种执行模式

Claude Code 支持两种工具执行模式：

#### 模式 A: 传统批处理模式 (`runTools`)

```typescript
export async function* runTools(
  toolUseMessages: ToolUseBlock[],
  assistantMessages: AssistantMessage[],
  canUseTool: CanUseToolFn,
  toolUseContext: ToolUseContext,
): AsyncGenerator<MessageUpdate> {
  // 将工具调用分区为并发安全的批次
  for (const { isConcurrencySafe, blocks } of partitionToolCalls(...)) {
    if (isConcurrencySafe) {
      // 并发执行只读工具
      yield* runToolsConcurrently(blocks, ...);
    } else {
      // 串行执行写入工具
      yield* runToolsSerially(blocks, ...);
    }
  }
}
```

**分区策略：**
- 连续的安全工具合并为一个批次
- 不安全工具单独成批次
- 安全和不安全工具之间自动切换执行模式

#### 模式 B: 流式执行模式 (`StreamingToolExecutor`)

```typescript
export class StreamingToolExecutor {
  private tools: TrackedTool[] = [];
  private siblingAbortController: AbortController;
  
  // 添加工具到执行队列
  addTool(block: ToolUseBlock, assistantMessage: AssistantMessage): void {
    // 立即开始执行（如果并发条件允许）
    void this.processQueue();
  }
  
  // 获取已完成的结果
  *getCompletedResults(): Generator<MessageUpdate> {
    // 实时产出结果
  }
  
  // 等待所有工具完成
  async *getRemainingResults(): AsyncGenerator<MessageUpdate> {
    // 异步等待并产出结果
  }
}
```

**流式模式优势：**
- 工具在助手消息流式传输时就开始执行
- 减少整体延迟
- 支持实时进度更新

### 4.2 并发控制

```typescript
function getMaxToolUseConcurrency(): number {
  return (
    parseInt(process.env.CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY || '', 10) || 10
  );
}

// 并发安全条件
private canExecuteTool(isConcurrencySafe: boolean): boolean {
  const executingTools = this.tools.filter(t => t.status === 'executing');
  return (
    executingTools.length === 0 ||
    (isConcurrencySafe && executingTools.every(t => t.isConcurrencySafe))
  );
}
```

**并发规则：**
1. 只读工具可以并发执行（最多 10 个）
2. 写入工具必须串行执行
3. 写入工具执行时，不允许任何其他工具执行
4. Bash 工具错误会取消其他并发中的 Bash 工具

### 4.3 工具状态机

```
┌─────────┐    addTool()    ┌─────────┐    processQueue()   ┌──────────┐
│ 初始状态 │ ──────────────▶ │ queued  │ ─────────────────▶ │executing │
└─────────┘                 └─────────┘                    └────┬─────┘
                                                                │
                                                                │ executeTool()
                                                                ▼
┌─────────┐    yield results    ┌─────────┐    completed     ┌──────────┐
│ yielded │ ◀────────────────── │completed│ ◀────────────── │executing │
└─────────┘                     └─────────┘                  └──────────┘
```

### 4.4 错误处理和级联取消

```typescript
private async executeTool(tool: TrackedTool): Promise<void> {
  // 创建独立的 AbortController
  const toolAbortController = createChildAbortController(
    this.siblingAbortController,
  );
  
  for await (const update of generator) {
    // 检查是否被兄弟工具错误取消
    const abortReason = this.getAbortReason(tool);
    if (abortReason && !thisToolErrored) {
      // 生成合成错误消息
      messages.push(this.createSyntheticErrorMessage(...));
      break;
    }
    
    // 检测 Bash 错误并取消兄弟工具
    if (isErrorResult && tool.block.name === BASH_TOOL_NAME) {
      this.hasErrored = true;
      this.siblingAbortController.abort('sibling_error');
    }
  }
}
```

**取消类型：**
1. **sibling_error**: 兄弟 Bash 工具出错
2. **user_interrupted**: 用户中断（Ctrl+C）
3. **streaming_fallback**: 流式回退

## 5. 上下文压缩系统

### 5.1 三级压缩架构

```
┌────────────────────────────────────────────────────────────────┐
│                     上下文压缩层级                              │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: Snip Compact                                          │
│  ├── 从消息尾部删除旧消息                                        │
│  └── 基于数量的轻量级清理                                         │
│                                                                 │
│  Level 2: Micro Compact                                         │
│  ├── 基于时间的工具结果清理                                       │
│  ├── Cached Microcompact (API 层 cache_edits)                   │
│  └── 保留消息结构，仅清理内容                                     │
│                                                                 │
│  Level 3: Full Compact                                          │
│  ├── 生成对话摘要                                                │
│  ├── 使用子代理进行智能总结                                       │
│  └── 替换旧消息为摘要                                             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 压缩触发时机

```typescript
// 在每次 API 调用前执行
queryCheckpoint('query_autocompact_start');
const { compactionResult, consecutiveFailures } = await deps.autocompact(
  messagesForQuery,
  toolUseContext,
  cacheSafeParams,
  querySource,
  tracking,
  snipTokensFreed,
);
queryCheckpoint('query_autocompact_end');
```

**压缩阈值：**
- 默认阈值：有效上下文窗口 - 13,000 tokens
- 可配置：通过 `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`
- 阻塞限制：实际窗口 - 3,000 tokens

### 5.3 响应式压缩 (Reactive Compact)

当 API 返回 413 (Prompt Too Long) 时：

```typescript
if (isWithheld413) {
  // 首先尝试上下文折叠恢复
  if (feature('CONTEXT_COLLAPSE')) {
    const drained = contextCollapse.recoverFromOverflow(...);
    if (drained.committed > 0) {
      state = { ..., transition: { reason: 'collapse_drain_retry' } };
      continue;  // 重试
    }
  }
  
  // 然后尝试响应式压缩
  if (reactiveCompact) {
    const compacted = await reactiveCompact.tryReactiveCompact({...});
    if (compacted) {
      state = { ..., transition: { reason: 'reactive_compact_retry' } };
      continue;  // 重试
    }
  }
}
```

## 6. 错误恢复机制

### 6.1 错误类型与恢复策略

| 错误类型 | 恢复策略 | 实现位置 |
|----------|----------|----------|
| Prompt Too Long | 响应式压缩/上下文折叠 | `query.ts:1068-1183` |
| Max Output Tokens | 自动升级 + 恢复消息 | `query.ts:1185-1256` |
| Model Overload | 自动降级到备用模型 | `query.ts:893-951` |
| Image Size Error | 媒体恢复（压缩/剥离）| reactive compact |
| Tool Error | 合成错误结果，继续执行 | `toolExecution.ts` |

### 6.2 Max Output Tokens 恢复

```typescript
// 升级策略：8K → 64K
if (capEnabled && maxOutputTokensOverride === undefined) {
  state = {
    ...state,
    maxOutputTokensOverride: ESCALATED_MAX_TOKENS,  // 64K
    transition: { reason: 'max_output_tokens_escalate' },
  };
  continue;
}

// 恢复策略：添加恢复消息继续
if (maxOutputTokensRecoveryCount < MAX_OUTPUT_TOKENS_RECOVERY_LIMIT) {
  const recoveryMessage = createUserMessage({
    content: `Output token limit hit. Resume directly...`,
    isMeta: true,
  });
  state = {
    messages: [...messagesForQuery, ...assistantMessages, recoveryMessage],
    maxOutputTokensRecoveryCount: maxOutputTokensRecoveryCount + 1,
    transition: { reason: 'max_output_tokens_recovery' },
  };
  continue;
}
```

### 6.3 模型降级

```typescript
catch (innerError) {
  if (innerError instanceof FallbackTriggeredError && fallbackModel) {
    // 切换到备用模型
    currentModel = fallbackModel;
    attemptWithFallback = true;
    
    // 清除失败尝试的消息
    yield* yieldMissingToolResultBlocks(assistantMessages, 'Model fallback triggered');
    assistantMessages.length = 0;
    
    // 创建新的流式执行器
    streamingToolExecutor?.discard();
    streamingToolExecutor = new StreamingToolExecutor(...);
    
    // 记录降级事件
    logEvent('tengu_model_fallback_triggered', {...});
    
    continue;  // 重试
  }
}
```

## 7. 状态转换系统

### 7.1 状态转换类型

```typescript
type Continue =
  | { reason: 'next_turn' }                                    // 正常下一轮
  | { reason: 'collapse_drain_retry'; committed: number }     // 折叠恢复
  | { reason: 'reactive_compact_retry' }                       // 响应式压缩
  | { reason: 'max_output_tokens_escalate' }                  // Token 升级
  | { reason: 'max_output_tokens_recovery'; attempt: number }  // Token 恢复
  | { reason: 'stop_hook_blocking' }                          // Stop Hook 阻塞
  | { reason: 'token_budget_continuation' };                  // Token 预算继续

type Terminal =
  | { reason: 'completed' }                                    // 正常完成
  | { reason: 'blocking_limit' }                              // 阻塞限制
  | { reason: 'aborted_streaming' }                           // 流式中止
  | { reason: 'aborted_tools' }                               // 工具中止
  | { reason: 'prompt_too_long' }                             // 提示过长
  | { reason: 'image_error' }                                 // 图像错误
  | { reason: 'model_error'; error?: unknown }               // 模型错误
  | { reason: 'max_turns'; turnCount: number }               // 达到最大轮次
  | { reason: 'stop_hook_prevented' }                        // Stop Hook 阻止
  | { reason: 'hook_stopped' };                              // Hook 停止
```

### 7.2 状态转换图

```
                    ┌──────────────┐
                    │   Start      │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
               ┌────│    Loop      │◀──────────────────────────┐
               │    └──────┬───────┘                           │
               │           │                                   │
               │           ▼                                   │
               │    ┌──────────────┐     ┌──────────────┐     │
               │    │  API Call    │────▶│  Tool Use    │─────┘
               │    └──────────────┘     └──────────────┘
               │           │
               │    ┌──────┴──────┐
               │    │             │
               ▼    ▼             ▼
       ┌──────────┐      ┌──────────────┐
       │ Terminal │      │  Recovery    │
       │          │      │  Strategies  │
       │ completed│      │              │
       │ aborted  │      │ compact      │
       │ error    │      │ escalate     │
       │ max_turns│      │ fallback     │
       └──────────┘      └──────────────┘
```

## 8. 钩子系统 (Hooks)

### 8.1 Stop Hooks

```typescript
const stopHookResult = yield* handleStopHooks(
  messagesForQuery,
  assistantMessages,
  systemPrompt,
  userContext,
  systemContext,
  toolUseContext,
  querySource,
  stopHookActive,
);

if (stopHookResult.preventContinuation) {
  return { reason: 'stop_hook_prevented' };
}

if (stopHookResult.blockingErrors.length > 0) {
  // 添加阻塞错误并继续
  state = {
    messages: [...messagesForQuery, ...assistantMessages, ...stopHookResult.blockingErrors],
    transition: { reason: 'stop_hook_blocking' },
  };
  continue;
}
```

### 8.2 Tool Hooks

```typescript
export async function* runToolUse(...): AsyncGenerator<MessageUpdateLazy> {
  // PreToolUse Hooks
  for await (const update of runPreToolUseHooks(...)) {
    yield update;
  }
  
  // 实际工具调用
  const result = await tool.call(input, context, canUseTool, ...);
  
  // PostToolUse Hooks
  await runPostToolUseHooks(result, ...);
}
```

## 9. 性能优化

### 9.1 预取机制

```typescript
// 记忆预取
using pendingMemoryPrefetch = startRelevantMemoryPrefetch(
  state.messages,
  state.toolUseContext,
);

// 技能预取
const pendingSkillPrefetch = skillPrefetch?.startSkillDiscoveryPrefetch(
  null,
  messages,
  toolUseContext,
);
```

### 9.2 检查点分析

```typescript
queryCheckpoint('query_fn_entry');
queryCheckpoint('query_snip_start');
queryCheckpoint('query_microcompact_start');
queryCheckpoint('query_autocompact_start');
queryCheckpoint('query_setup_start');
queryCheckpoint('query_api_streaming_start');
queryCheckpoint('query_tool_execution_start');
```

### 9.3 延迟加载

```typescript
// 特性门控的延迟导入
const reactiveCompact = feature('REACTIVE_COMPACT')
  ? (require('./services/compact/reactiveCompact.js'))
  : null;

const contextCollapse = feature('CONTEXT_COLLAPSE')
  ? (require('./services/contextCollapse/index.js'))
  : null;
```

## 10. 安全机制

### 10.1 权限检查流程

```typescript
async function* streamedCheckPermissionsAndCallTool(...) {
  // 1. 输入验证
  const validation = await tool.validateInput?.(parsedInput.data, context);
  
  // 2. 权限检查
  const permissionResult = await canUseTool(...);
  
  // 3. 执行工具
  if (permissionResult.behavior === 'allow') {
    yield* executeToolWithTelemetry(...);
  }
}
```

### 10.2 中止传播

```typescript
// 父子 AbortController 链
toolAbortController.signal.addEventListener('abort', () => {
  if (toolAbortController.signal.reason !== 'sibling_error' &&
      !this.toolUseContext.abortController.signal.aborted) {
    // 冒泡到父级
    this.toolUseContext.abortController.abort(toolAbortController.signal.reason);
  }
}, { once: true });
```

## 11. 总结

Claude Code 的 Agent Loop 是一个经过精心设计的复杂系统，具有以下核心特点：

1. **状态机驱动**: 使用明确的状态转换管理复杂的执行流程
2. **多层次容错**: 三级压缩、多种错误恢复策略确保系统稳定性
3. **并发控制**: 智能的串行/并发工具执行平衡性能和安全性
4. **流式优化**: StreamingToolExecutor 实现真正的实时工具执行
5. **可扩展架构**: Hook 系统和特性门控支持灵活的功能扩展
6. **精细监控**: 检查点和遥测确保可观测性

这套系统使 Claude Code 能够处理长时间运行的复杂任务，同时保持稳定性和响应性。

---

*报告生成日期：2026-04-01*
*分析源码版本：Claude Code (anthropic_claude_code)*
