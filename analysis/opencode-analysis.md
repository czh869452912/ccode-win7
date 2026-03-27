# OpenCode 平台架构分析与可借鉴设计

> 分析对象：`reference/opencode`
> 分析日期：2026-03-27
> 分析目标：为轻量化 Windows 7 嵌入式 C 语言 Agentic Coding 平台提取可借鉴的设计

---

## 一、项目总体结构

OpenCode 是基于 **Bun + Turbo 的 Monorepo**，核心语言为 TypeScript。

```
packages/
  opencode/       # 核心 CLI + Agent 系统（主体，272 个 TS 文件）
  sdk/js/         # JS 客户端 SDK
  app/            # Web UI（SolidJS）
  desktop/        # Tauri 桌面端
  desktop-electron/ # Electron 桌面端
  ui/             # 共享 UI 组件
  plugin/         # 插件接口定义
  util/           # 公共工具库
```

**对我们的参考**：我们目标平台是单一 Python/C 进程，无需 Monorepo。但其 `packages/opencode` 的内部模块划分值得学习。

---

## 二、核心 Agent Loop 设计

### 2.1 Agent 定义

Agent 是**配置驱动**的，不是硬编码的。每个 Agent 具有：

```typescript
{
  mode: "primary" | "subagent" | "all",
  permission: PermissionRuleset,   // 工具访问控制
  model: { providerID, modelID },  // 可覆盖的模型选择
  prompt: string,                  // 自定义系统提示
  temperature, topP,               // LLM 参数
  steps: number,                   // 最大执行步数
}
```

**内置 Agent 类型**：
| Agent | 用途 |
|-------|------|
| `build` | 默认主 Agent，有 question/plan 权限 |
| `plan` | 只读规划模式 |
| `general` | 通用多步任务 |
| `explore` | 代码浏览/搜索专用 |
| `compaction` | 上下文窗口压缩（隐藏） |
| `title` | 会话标题生成（隐藏） |
| `summary` | 会话摘要生成（隐藏） |

**可借鉴**：
- ✅ Agent 配置化（而不是硬编码）便于扩展
- ✅ 专用隐藏 Agent 处理内务（compaction、summary）是个好模式
- ✅ `steps` 上限防止无限循环

### 2.2 消息处理流程

```
用户输入
  → Session.sendMessage()
    → 构建消息历史 (含系统提示)
    → 计算 Token 数
    → 检查是否需要 Compaction
    → 调用 LLM Stream
      → 处理流式响应 (文本 / 工具调用)
        → 工具调用 → 权限检查 → 执行 → 结果追加
        → 循环直到 stop 或 steps 耗尽
    → 持久化到 SQLite
    → 发布 Bus 事件
```

**可借鉴**：
- ✅ 流式处理 + 工具调用交织的主循环结构清晰
- ✅ 每次迭代后持久化，防止崩溃丢失进度

---

## 三、工具系统设计

### 3.1 工具定义接口

```typescript
Tool.Info {
  id: string
  init: (ctx?) => Promise<{
    description: string
    parameters: z.ZodType       // Zod schema 验证
    execute(args, ctx): Promise<{
      title: string
      metadata: M
      output: string
      attachments?: FilePart[]
    }>
    formatValidationError?: (error) => string
  }>
}
```

每个工具调用时的 **Context** 包含：
- `sessionID`, `messageID`, `callID` — 追踪标识
- `abort` — AbortSignal，支持取消
- `messages` — 完整消息历史（工具可读取上下文）
- `metadata()` — 更新工具运行时元数据
- `ask()` — 请求用户权限

### 3.2 内置工具列表

| 工具 | 功能 |
|------|------|
| `bash` | Shell 执行，含超时、截断、元数据 |
| `edit` | 基于 diff 的文件编辑，保留行尾 |
| `read` | 文件读取，含截断和范围选择 |
| `write` | 文件写入/创建 |
| `glob` | 文件模式匹配 |
| `grep` | 代码内容搜索 |
| `websearch` | 网络搜索（受限） |
| `task` | TODO 任务管理 |

**可借鉴**：
- ✅ 工具接口统一，`execute → { title, output, metadata }` 的返回结构简洁
- ✅ AbortSignal 贯穿工具层，支持优雅取消
- ✅ `ask()` 权限请求内嵌于工具 Context，不需要外部协调
- ✅ 工具输出有截断保护（MAX_LINES/MAX_BYTES）
- ⚠️ 对我们：不需要 websearch、task 等；bash/edit/read/write/glob/grep 是核心，可直接对应

### 3.3 工具权限系统

权限规则采用**通配符模式匹配**：

```
规则 = { pattern: "bash(rm -rf *)", behavior: "deny" }
决策 = allow | deny | ask（三值）
优先级 = 后定义规则覆盖先前规则（findLast 语义）
```

权限来源层次（从低到高）：
1. 默认全允许
2. 全局用户配置
3. 项目级 `.opencode/config.json`
4. Agent 专属覆盖

**可借鉴**：
- ✅ 三值权限（allow/deny/ask）比二值更灵活
- ✅ 通配符模式匹配工具调用字符串（而不只是工具名）
- ✅ 分层覆盖，项目级可收窄全局权限

---

## 四、会话与上下文管理

### 4.1 消息结构

消息由多个 **Parts** 组成（鉴别联合类型）：

| Part 类型 | 内容 |
|-----------|------|
| `TextPart` | 文本，含时间戳 |
| `ReasoningPart` | 推理 token（如 o1） |
| `ToolPart` | 工具调用，含状态机 |
| `FilePart` | 文件附件 |
| `SnapshotPart` | 工作区快照 |
| `PatchPart` | Git patch |

`ToolPart` 的状态机：
```
pending → running → completed
                 → failed
                 → user-denied
                 → partial
```

**可借鉴**：
- ✅ Part-based 消息结构比扁平 JSON 更结构化，便于渲染不同类型内容
- ✅ ToolPart 的状态机清晰表达工具执行生命周期

### 4.2 上下文压缩（Compaction）

自动 Compaction 触发逻辑：
1. 每轮对话后计算总 token 数
2. 超过模型可用上下文时触发
3. 调用专用 `compaction` Agent 生成摘要
4. 剪除旧的工具输出（PRUNE_MINIMUM = 20k tokens）
5. **保护**：最近 2 轮对话 + 关键工具（skill）不被剪除

**可借鉴**：
- ✅ Compaction 作为独立 Agent 处理，主流程不耦合
- ✅ 保护最近 N 轮的策略简单有效
- ✅ 自动触发而非手动管理

---

## 五、持久化设计

### 5.1 存储方案

- **数据库**：SQLite + Drizzle ORM
- **位置**：`~/.opencode/opencode.db`
- **关键 PRAGMA**：
  ```sql
  PRAGMA journal_mode = WAL;      -- 写时不阻塞读
  PRAGMA synchronous = NORMAL;    -- 性能与安全平衡
  PRAGMA busy_timeout = 5000;     -- 防锁死
  PRAGMA cache_size = -64000;     -- 64MB 缓存
  ```

**表结构**：
- `sessions` — 会话元数据
- `messages` — 消息记录
- `parts` — 消息 Parts（独立表）
- `permissions` — 权限记录
- `projects`, `accounts`, `auth` 等

### 5.2 快照与回退

- 每次文件编辑前保存 `SnapshotPart`
- 记录 `{ additions, deletions, files, diffs }`
- 支持基于快照的 Revert

**可借鉴**：
- ✅ SQLite 是 Windows 7 兼容的理想选择，无需额外服务
- ✅ WAL 模式 + 合理 PRAGMA 是最佳实践
- ✅ 快照 + diff 存储于 Parts 而不是独立文件，简化管理
- ✅ 对我们：SQLite 存会话+消息+Parts，每次 edit 记录 patch，支持 git revert

---

## 六、配置系统

### 6.1 配置优先级（从低到高）

1. 默认值
2. 全局用户配置（`~/.opencode/config.json`）
3. 项目配置（`.opencode/config.json`）
4. 环境变量

### 6.2 配置内容

```typescript
{
  default_agent: string,
  agent: Record<string, AgentConfig>,
  provider: Record<string, ProviderConfig>,
  permission: PermissionRuleset,
  instructions: string[],    // 追加系统提示的文件路径
  plugin: string[],          // 插件列表
  compaction: { auto, reserved, prune },
}
```

**可借鉴**：
- ✅ 项目级 `.opencode/config.json` 覆盖全局配置的分层设计
- ✅ `instructions` 作为文件路径列表追加系统提示，无需修改主配置
- ✅ 对我们：`.agent/config.toml`（全局）+ `.agent/project.toml`（项目级）

---

## 七、错误处理模式

### 7.1 结构化错误类型

```typescript
class NamedError extends Error {
  name: string        // 错误类型标识
  data: ZodSchema     // 结构化错误数据
  cause?: Error       // 因果链
  toObject(): object  // 可序列化
}
```

**主要错误类型**：
| 类型 | 含义 |
|------|------|
| `OutputLengthError` | 输出超过截断限制 |
| `AbortedError` | 用户/信号取消 |
| `StructuredOutputError` | JSON schema 解析失败（触发重试） |
| `AuthError` | Provider 认证失败 |
| `ContextOverflowError` | Token 超限 |
| `RejectedError` | 用户拒绝权限 |

**可借鉴**：
- ✅ 有名字的结构化错误比裸 Exception 更易处理
- ✅ 因果链支持（`.cause`）便于调试
- ✅ 各层错误的传播策略：工具层→部分结果，会话层→存库，CLI层→格式化输出

---

## 八、事件总线（Bus）

**模式**：发布/订阅（PubSub）

- 所有跨层通信通过 Bus 事件传播
- 事件类型用 Zod schema 定义，类型安全
- 支持 Callback 和 Stream 两种订阅方式
- 全局 Bus 支持跨实例事件（如多客户端场景）

**关键事件**：
- `Session.Created`, `Session.Updated`
- `Message.Created`, `Message.Updated`
- `ToolPart.Updated` (状态变更)
- `SessionCompaction.Compacted`

**可借鉴**：
- ✅ 解耦 Agent Loop 与 UI/持久化层
- ✅ 对我们：即使是 TUI，也可用简单的 event queue 解耦 agent 执行与界面刷新

---

## 九、TUI 实现参考

OpenCode 自身的 TUI 使用了 `@opentui/core`（基于 SolidJS 的终端 UI 库），相对重量级。

但其 CLI 输出模块 (`src/cli/ui.ts`) 展示了轻量 TUI 的基本要素：
- ANSI 颜色/样式封装
- 图标+颜色编码的消息类型区分
- 进度 spinner（`opentui-spinner`）

**对我们的参考**：
- OpenCode 的 TUI 方案对 Windows 7 不适用（依赖现代 Node.js）
- 我们需要用 Python 的 `curses` 或 `prompt_toolkit`，或 C 的 ncurses
- 但其 **UI 信息架构**（会话列表、消息流、工具状态、权限询问）值得借鉴

---

## 十、LSP 与格式化集成

- **LSP**：`src/lsp/server.ts`，在 edit 完成后检查诊断（错误/警告）
- **格式化**：`src/format/`，支持 prettier 等格式化器，edit 后自动触发
- **文件监视**：chokidar 监控外部文件变更，与 edit 工具联动防冲突

**对我们的参考**：
- 嵌入式 C 开发场景下，LSP 集成（clangd）有价值但非必须
- 编译器（gcc/arm-gcc）输出解析比 LSP 更直接
- 文件监视在单用户场景下可简化

---

## 十一、版本控制集成

**文件**：`src/project/vcs.ts`

- 调用系统 `git` 命令（非库）
- 功能：status、diff、commit、log、revert
- Session 的 `summary` 字段记录本次会话的文件变更统计

**可借鉴**：
- ✅ 调用系统 git 而不是嵌入 git 库，对 Windows 7 最兼容
- ✅ 每次会话记录变更摘要（additions/deletions/files）

---

## 十二、可借鉴设计汇总

### 核心架构决策（高优先）

| # | 设计 | 具体做法 | 来自 |
|---|------|----------|------|
| 1 | **配置驱动的 Agent** | Agent 类型、权限、模型、步数均可配置 | `agent/agent.ts` |
| 2 | **Part-based 消息结构** | 消息 = 多个 Parts（文本/工具/文件/补丁） | `session/message-v2.ts` |
| 3 | **工具 Context 注入** | 每次工具调用携带 sessionID/abort/ask 等 | `tool/tool.ts` |
| 4 | **三值权限系统** | allow/deny/ask + 通配符模式 | `permission/evaluate.ts` |
| 5 | **SQLite 持久化** | WAL 模式，sessions+messages+parts 三表 | `storage/db.ts` |
| 6 | **自动 Compaction** | token 超限时调专用 Agent 压缩，保护最近 N 轮 | `session/compaction.ts` |
| 7 | **结构化错误类型** | 有名字、有数据、有因果链的错误 | `util/error.ts` |
| 8 | **调用系统 git** | 不内嵌 git 库，直接 subprocess 调 git | `project/vcs.ts` |

### Agent Loop 细节（中优先）

| # | 设计 | 具体做法 |
|---|------|----------|
| 9 | **steps 上限** | 每个 Agent 配置最大执行步数，防无限循环 |
| 10 | **AbortSignal 贯穿** | 从 session 到工具层，支持随时取消 |
| 11 | **ToolPart 状态机** | pending→running→completed/failed/user-denied |
| 12 | **工具输出截断** | MAX_LINES 和 MAX_BYTES 双重保护 |
| 13 | **专用内务 Agent** | compaction/summary/title 用独立 Agent 处理 |

### 轻量化建议（针对我们的场景）

| OpenCode 功能 | 我们的处理 |
|--------------|-----------|
| Effect-TS FP 框架 | 不采用，Python 直接实现 |
| Vercel AI SDK（多 Provider） | 直接用 Anthropic SDK，单 Provider |
| Web UI / Desktop App | 不需要，纯 TUI |
| LSP 集成（实时诊断） | 可选，优先用编译器输出 |
| Plugin 系统 | 暂不需要，工具集固定 |
| 文件监视（chokidar） | 简化，仅在 edit 前后比较 |
| 网络搜索工具 | 不需要（内网隔离） |
| 会话共享/云同步 | 不需要 |
| MCP 协议 | 暂不需要 |

---

## 十三、对我们系统的架构建议

基于 OpenCode 的设计经验，结合我们的约束（Windows 7、内网、嵌入式 C、轻量化），建议如下架构：

```
┌─────────────────────────────────────────┐
│              TUI 层 (Python curses)      │
│  会话列表 | 消息流 | 工具状态 | 权限询问  │
└──────────────────┬──────────────────────┘
                   │ 事件队列
┌──────────────────▼──────────────────────┐
│           Agent Loop 核心               │
│  配置驱动 | steps 上限 | AbortSignal    │
└──────────────────┬──────────────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
┌─────▼────┐ ┌────▼────┐ ┌─────▼────┐
│  工具层  │ │ 权限层  │ │  LLM 层  │
│bash/edit │ │三值规则 │ │Anthropic │
│read/write│ │通配符   │ │  SDK     │
│glob/grep │ │ask 交互 │ │流式处理  │
└─────┬────┘ └─────────┘ └──────────┘
      │
┌─────▼──────────────────────────────────┐
│           SQLite 持久化                 │
│  sessions | messages | parts | perms   │
│  WAL 模式 | 快照/Patch | git 变更摘要  │
└────────────────────────────────────────┘
```

**核心工具集**（嵌入式 C 场景）：
- `read` — 读文件（含行范围）
- `write` — 写/创建文件
- `edit` — 基于 diff 的精确编辑
- `bash` — 执行 gcc/make/测试命令
- `glob` — 文件模式搜索
- `grep` — 代码内容搜索
- `git` — git 操作（status/diff/commit/log/checkout）
- `todo` — TODO 任务维护（Agent 自主规划必需）
