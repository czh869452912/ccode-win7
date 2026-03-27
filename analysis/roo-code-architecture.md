# Roo-Code 架构分析

> 分析目的：为轻量化嵌入式C语言开发智能体平台提供设计参考
> 分析时间：2026-03-27
> 原项目：Roo-Code（VS Code 扩展，~33,000 LOC）

---

## 一、总体架构

Roo-Code 是基于 **VS Code 扩展 API** 的 monorepo 项目，核心分层如下：

```
src/
├── core/           # 核心 Agent 逻辑（循环、工具、上下文）
├── api/            # LLM 提供商抽象层
├── extension.ts    # VS Code 入口
├── integrations/   # 终端、编辑器集成
├── services/       # MCP、检查点、代码索引
└── shared/         # 类型、模式、工具定义

packages/
├── core/           # 导出的工具库
├── types/          # 统一类型定义
└── ipc/            # 进程间通信
```

**对我们项目的启示**：其核心 Agent 逻辑（`src/core/`）与 VS Code 耦合较少，
是可以直接借鉴的部分；UI 层、扩展框架则完全不需要。

---

## 二、Agent 循环设计

### 2.1 核心循环结构

```
initiateTaskLoop()
└── recursivelyMakeClineRequests()
    ├── 构建环境详情（文件树、当前目录、时间等）
    ├── 将用户消息追加到 API 历史
    ├── attemptApiRequest()  ← 流式调用 LLM
    │   ├── 处理推理块（thinking chunks）
    │   ├── 解析流式工具调用（NativeToolCallParser）
    │   ├── 执行工具（askApproval + pushToolResult 回调）
    │   └── 检测 context_window_exceeded → 自动重试
    ├── presentAssistantMessage()  ← 格式化输出
    └── 返回 didEndLoop

若 !didEndLoop → 追加 "未使用工具" 消息 → 继续循环
```

### 2.2 关键机制

| 机制 | 说明 | 是否借鉴 |
|------|------|---------|
| **基于栈的重试** | 压栈重试，支持指数退避 | ✅ 必须 |
| **连续错误检测** | 连续无工具调用超阈值则报错 | ✅ 必须 |
| **工具重复检测** | 防止同一工具无限循环 | ✅ 必须 |
| **流式响应处理** | 流式解析工具调用，实时更新 UI | ✅ 必须（TUI 实时刷新） |
| **任务完成判断** | `attempt_completion` 工具触发 | ✅ 必须 |

### 2.3 循环终止条件

1. Agent 调用 `attempt_completion` 工具
2. 用户中止（abort 信号）
3. 连续错误超过阈值
4. 上下文压缩失败（无法继续）

---

## 三、工具系统

### 3.1 工具基类设计

```typescript
abstract class BaseTool<TName extends ToolName> {
  abstract readonly name: TName

  // 工具执行入口（由循环调用）
  async handle(task, block, callbacks): Promise<void>

  // 工具核心逻辑（子类实现）
  abstract execute(params, task, callbacks): Promise<void>

  // 流式部分更新（可选，用于实时 UI 反馈）
  async handlePartial(task, block): Promise<void>
}
```

**三个回调构成工具与循环的接口：**
- `askApproval(toolName, params)` → 等待用户确认
- `pushToolResult(result)` → 将结果注入对话历史
- `handleError(operation, error)` → 统一错误处理

### 3.2 Roo-Code 内置工具清单（23个）

| 类别 | 工具 | 我们需要 |
|------|------|---------|
| 文件读取 | `read_file`（支持行范围） | ✅ |
| 文件写入 | `write_to_file` | ✅ |
| 文件编辑 | `edit_file`, `apply_diff` | ✅ |
| 文件搜索 | `list_files`, `search_files`, `search_and_replace` | ✅ |
| 命令执行 | `execute_command`, `read_command_output` | ✅ |
| 任务管理 | `attempt_completion`, `ask_followup_question`, `update_todo_list` | ✅ |
| 代码搜索 | `codebase_search`（语义搜索） | ⚠️ 可选 |
| 子任务 | `new_task`（任务委托） | ⚠️ 后期扩展 |
| MCP工具 | `use_mcp_tool` | ❌ 不需要 |
| 模式切换 | `switch_mode`, `run_slash_command` | ⚠️ 简化版 |

**我们需要的最小工具集（9个）：**
`read_file`, `write_to_file`, `edit_file`, `list_files`, `search_files`,
`execute_command`, `attempt_completion`, `ask_followup_question`, `update_todo_list`

### 3.3 工具注册模式

```typescript
// 工厂函数模式，按名称查找
const toolRegistry = new Map<ToolName, BaseTool<any>>()

function getToolByName(name: ToolName): BaseTool<any> {
  return toolRegistry.get(name) ?? (() => { throw new Error(`Unknown tool: ${name}`) })()
}
```

---

## 四、上下文管理

### 4.1 三层上下文策略

```
Token 使用量
     │
     ▼ 超过阈值（默认 85%）
┌──────────────────────────────────────┐
│  Tier 1: 自动对话摘要（Auto-Condensation）│
│  - 调用 LLM 生成摘要                  │
│  - 插入 Summary 消息替代历史           │
│  - 原消息标记 condenseParent，保留     │
└──────────────────────────────────────┘
     │ 摘要失败 / 仍超出
     ▼
┌──────────────────────────────────────┐
│  Tier 2: 滑动窗口截断（Truncation）    │
│  - 删除 50% 历史消息（标记而非删除）   │
│  - 插入截断标记                       │
└──────────────────────────────────────┘
     │ API 返回 context_window_exceeded
     ▼
┌──────────────────────────────────────┐
│  Tier 3: 强制压缩（75% 减少）         │
│  - 最多重试 3 次                      │
└──────────────────────────────────────┘
```

### 4.2 关键设计：非破坏性历史

所有截断/摘要操作都是**标记式**，不真正删除消息：

```typescript
// 摘要时
messages.forEach(msg => msg.condenseParent = condenseId)

// 截断时
messages.forEach(msg => msg.truncationParent = truncationId)

// 发送 API 请求前过滤隐藏消息
getEffectiveApiHistory() // 只返回未被标记的消息
```

**优势**：支持回退（rewind）到任意历史点，不丢失数据。

### 4.3 Token 计算公式

```
可用 Token = 上下文窗口 × (1 - 10% 缓冲) - 最大输出 Token
```

---

## 五、LLM 提供商抽象

### 5.1 统一接口

```typescript
interface ApiHandler {
  // 核心：创建流式消息
  createMessage(
    systemPrompt: string,
    messages: MessageParam[],
    metadata?: Metadata
  ): AsyncGenerator<ApiChunk>

  // 辅助
  getModel(): { id: string; info: ModelInfo }
  countTokens(content: ContentBlock[]): Promise<number>
}
```

### 5.2 提供商层次结构

```
BaseProvider (抽象)
├── AnthropicHandler          ← 原生工具调用，推荐
├── OpenAiHandler             ← 标准 OpenAI 接口
├── BaseOpenAiCompatibleProvider
│   ├── DeepSeekHandler
│   ├── MoonshotHandler
│   └── OllamaHandler         ← 本地模型，我们优先
├── GeminiHandler
└── ...（30+ 提供商）
```

**对我们的建议**：
- 优先实现 **Ollama / LM Studio** 适配（本地模型，离网可用）
- 次优实现 **Anthropic Claude API**（API 密钥接入）
- 接口设计保持与 Roo-Code 一致，未来可直接移植其他提供商

### 5.3 流式块类型

```typescript
type ApiChunk =
  | { type: "text"; text: string }
  | { type: "usage"; inputTokens: number; outputTokens: number }
  | { type: "reasoning"; reasoning: string }
```

---

## 六、文件操作

### 6.1 分层设计

```
Layer 1 - 基础 IO：read_file, write_to_file
Layer 2 - 智能编辑：edit_file（find-replace），apply_diff（多块替换）
Layer 3 - 访问控制：.rooignore（忽略文件），.rooprotected（只读保护）
```

### 6.2 Diff 策略模式

```typescript
interface DiffStrategy {
  apply(original: string, diff: string): DiffResult
}

class MultiSearchReplaceDiffStrategy implements DiffStrategy {
  // 搜索精确文本块并替换
  // 支持多块同时替换
  // 带相似度匹配容错
}
```

**可借鉴**：Diff 策略插件化设计，初期用简单 find-replace，后期可升级。

### 6.3 行范围读取

`read_file` 支持 `start_line` / `end_line` 参数，对大型头文件/源文件非常有用，
避免将整个文件塞入上下文。

---

## 七、命令执行

### 7.1 Roo-Code 的方式（VS Code 集成）

```
ExecuteCommandTool
└── VS Code Terminal API（xterm.js 集成）
    ├── Shell integration（高级：获取退出码、精确输出）
    └── Fallback：基础 Terminal 写入
```

### 7.2 我们应采用的方式（独立进程）

```
ExecuteCommandTool
└── Node.js child_process.spawn()
    ├── 实时 stdout/stderr 流
    ├── 超时处理
    ├── 退出码捕获
    └── 输出持久化到任务目录
```

**关键特性需保留**：
- 实时流式输出（TUI 实时刷新编译错误）
- 超时机制（编译卡死时可中断）
- 工作目录（cwd）支持
- 输出捕获（后续可用 `read_command_output` 重读）

---

## 八、Git 集成

Roo-Code 的 Git 支持**极简**：

```typescript
// 仅用于获取工作区信息，注入系统提示
getWorkspaceGitInfo() => {
  branch: string,
  repoRoot: string,
  uncommittedChanges: number
}
```

实际 git 操作完全依赖 `execute_command` 工具（Agent 自己拼命令行）。

**对我们的建议**：
- 可以同样思路，不封装高级 git API
- 但可额外提供几个专用 git 工具：
  - `git_status` → 结构化输出（避免 Agent 自己解析）
  - `git_diff` → 带文件过滤
  - `git_commit` → 带确认
  - `git_log` → 简化历史查看
  - `git_revert` → 安全的文件级回退

---

## 九、TODO/任务管理

### 9.1 数据结构

```typescript
interface TodoItem {
  id: string
  content: string
  status: "pending" | "in_progress" | "completed" | "cancelled"
  priority: "high" | "medium" | "low"
}
```

### 9.2 持久化方式

- 存储在 Task 对象的内存中（`task.todoList`）
- 随对话历史一起序列化到磁盘
- 通过 `update_todo_list` 工具由 Agent 自主维护
- 恢复任务时从历史中重建

### 9.3 最佳实践

Roo-Code 的 AGENTS.md 强调：
> "TODO list must be updated before EVERY tool call"

Agent 在每次工具调用前必须先更新 TODO 状态，确保规划可见、进度可追踪。

---

## 十、消息持久化

### 10.1 目录结构

```
globalStorage/tasks/<taskId>/
├── conversation_history.json   # API 消息历史（发给 LLM 的）
├── ui_messages.json            # UI 消息（显示给用户的）
├── todo_list.json              # TODO 列表快照
└── command-output/             # 命令输出文件
    └── <commandId>.txt
```

### 10.2 双轨历史设计

| 类型 | 用途 | 内容 |
|------|------|------|
| `apiConversationHistory` | 发送给 LLM | 符合 API 格式的消息 |
| `clineMessages` | 显示给用户 | 含工具调用详情、状态、思考过程 |

两者独立存储，独立过滤，但按时间戳关联。

---

## 十一、可借鉴的关键设计模式

### 模式1：事件驱动架构

```typescript
class Task extends EventEmitter<TaskEvents> {
  // 发出：TaskStarted, TokenUsageUpdated, UserMessage, etc.
}
```
**用途**：解耦 Agent 循环与 TUI 渲染，TUI 订阅事件更新界面。

### 模式2：非破坏性历史

```typescript
// 标记而非删除，支持 rewind
message.truncationParent = truncationId
message.condenseParent = condenseId
```
**用途**：支持用户查看/回滚任意历史点，容错性强。

### 模式3：流式解析器管道

```typescript
NativeToolCallParser.processRawChunk(chunk)
// 缓冲不完整 JSON → 事件触发完整工具调用
```
**用途**：解析 LLM 流式工具调用，实现实时 TUI 进度显示。

### 模式4：基于栈的重试

```typescript
const stack = [{userContent, retryAttempt: 0}]
while (stack.length > 0) {
  const item = stack.pop()
  // 出错时压入新 item（retryAttempt++）
}
```
**用途**：优雅处理 API 错误、上下文超出、工具执行失败。

### 模式5：工具批准回调

```typescript
// 工具在执行前挂起，等待用户确认
const approved = await callbacks.askApproval("write_to_file", {path, content})
if (!approved) return
```
**用途**：危险操作（文件写入、命令执行）强制用户确认，TUI 下显示确认提示。

### 模式6：环境详情注入

每次 LLM 请求前动态构建系统提示的"环境详情"部分：
```
当前时间: 2026-03-27 10:30:00
工作目录: /project/firmware
Git 分支: main（3个未提交更改）
操作系统: Linux 5.4 / Windows 7
可用工具: [列表]
```
**用途**：让 LLM 了解当前上下文，减少幻觉。

---

## 十二、对我们项目的建议

### 12.1 可直接复用的设计

| 设计 | 复用方式 |
|------|---------|
| Agent 循环结构 | 完整复用其状态机逻辑，去除 VS Code 依赖 |
| 工具基类+回调接口 | 直接复用 `BaseTool` 模式 |
| 上下文管理三层策略 | 必须实现（对小型本地模型尤其重要） |
| LLM 提供商接口 | 复用 `ApiHandler` 接口设计 |
| TODO 数据结构 | 直接复用 `TodoItem` 结构 |
| 双轨历史设计 | 复用（API历史 vs 显示历史分离） |
| 非破坏性历史标记 | 复用（支持 git revert 类的会话回退） |

### 12.2 需要替换的部分

| Roo-Code 组件 | 我们的替代方案 |
|--------------|--------------|
| VS Code Webview UI | TUI（如 Python curses / Go tview / Rust tui-rs） |
| VS Code Terminal API | `child_process.spawn()` 直接调用 |
| VS Code Extension API | 无（直接 Node.js / Python 进程） |
| VS Code 文件监视 | 轮询或 fs.watch |
| MCP 服务器 | 不需要 |
| 云服务/遥测 | 不需要 |
| Marketplace/更新 | 不需要 |

### 12.3 新增的嵌入式专用工具

| 工具 | 说明 |
|------|------|
| `compile_c` | 封装 gcc/arm-none-eabi-gcc，结构化输出编译错误 |
| `run_make` | 执行 Makefile，解析错误 |
| `read_map_file` | 解析链接器 .map 文件 |
| `git_status` / `git_diff` | 结构化 git 信息（避免 Agent 解析原始输出） |
| `read_doc` | 读取 PDF/HTML 文档（离线） |
| `search_symbol` | 在 C 代码中查找符号定义/引用（ctags 集成） |

### 12.4 规模估算

| 模块 | Roo-Code LOC | 我们需要 LOC |
|------|-------------|-------------|
| Agent 循环 | ~3,800 | ~1,500 |
| 工具系统（9个工具） | ~2,500 | ~800 |
| 上下文管理 | ~800 | ~600 |
| LLM 适配（2个提供商） | ~8,000+ | ~600 |
| TUI 界面 | N/A | ~1,000 |
| 消息持久化 | ~1,200 | ~400 |
| **合计** | **~33,000** | **~5,000** |

---

## 十三、参考文件位置（Roo-Code 源码）

| 关键概念 | 文件位置 |
|---------|---------|
| Agent 主循环 | `src/core/task/Task.ts` |
| 工具基类 | `src/core/tools/BaseTool.ts` |
| 上下文管理 | `src/core/context-management/` |
| LLM 接口 | `src/api/index.ts`, `src/api/providers/` |
| TODO 工具 | `src/core/tools/UpdateTodoListTool.ts` |
| 消息管理 | `src/core/task/MessageManager.ts` |
| 流式解析 | `src/core/assistant-message/NativeToolCallParser.ts` |
| 环境详情 | `src/core/prompts/system.ts` |
| Git 工具 | `src/utils/git.ts` |
| 命令执行 | `src/core/tools/ExecuteCommandTool.ts` |
