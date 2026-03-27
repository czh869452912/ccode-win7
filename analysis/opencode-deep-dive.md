# OpenCode 深度分析：Agent Loop、上下文管理与模式设计

> 聚焦于核心机制，面向轻量化嵌入式 C 编程 Agent 的设计参考

---

## 一、Agent Loop 完整控制流

### 1.1 入口结构

Agent Loop 的核心在 `session/prompt.ts` 的 `SessionPrompt.loop()` 函数，整体是一个 **while(true) 大循环**，内部包含多个提前退出点：

```
loop(sessionID)
  ├── 初始化步骤计数器、消息缓冲
  └── while (true):
        ├── [退出检查] lastAssistant.finish 非工具 && 早于 lastUser → break
        ├── [特殊任务] 有待处理 SubtaskPart → 执行子任务 → continue
        ├── [压缩任务] 有待处理 Compaction → 执行压缩 → continue
        ├── resolveTools()  解析本轮可用工具集
        ├── 创建 AssistantMessage 骨架
        ├── SessionProcessor.process()  ← 核心：流式处理 + 工具执行
        │     返回 "continue" | "stop" | "compact"
        ├── if "compact" → SessionCompaction.process() → continue
        ├── if "stop"    → break
        └── else         → 下一轮迭代
```

### 1.2 SessionProcessor.process() 内部流程

这是真正处理 LLM 流式响应的地方，本质是一个**事件驱动的状态机**：

```
process():
  retry_loop:
    stream = LLM.stream(messages, tools, system)

    for event in stream.fullStream:
      "start"              → session.status = busy
      "reasoning-start/delta/end" → 创建/更新 ReasoningPart
      "tool-input-start/delta/end" → 追踪工具输入流

      "tool-call"          → [关键路径]
        ① 检测 doom loop（最近3次工具调用完全相同 → ask权限）
        ② ToolPart 状态: pending → running
        ③ Permission.ask() ← 若权限规则为 ask，此处挂起等用户回应
        ④ Tool.execute(args, ctx)
        ⑤ ToolPart 状态: running → completed / error

      "text-start/delta/end" → 创建/更新 TextPart

      "step-finish"        → 计算 tokens/cost，检查是否需要 compaction

      "error"              → 判断是否可重试
        可重试: sleep(指数退避) → continue retry_loop
        不可重试: assistantMessage.error = err → break

      "finish"             → 记录 finish reason (stop/tool-calls/length/error)

    catch(e):
      if retryable(e): 重试
      else: 标记错误, break

  return:
    needsCompaction → "compact"
    blocked         → "stop"    (权限被拒)
    error           → "stop"
    else            → "continue"
```

### 1.3 LLM.stream() 调用准备

在真正调 LLM 之前，需要组装：

```
LLM.stream():
  1. 系统提示拼接顺序（优先级从低到高）:
       agent.prompt → provider.prompt → custom_system → user_system

  2. 工具过滤:
       所有注册工具 → 按 agent.permission + session.permission 过滤
       → 得到本轮可用工具集

  3. 消息转换:
       MessageV2[] → ModelMessage[]（适配不同 provider 格式）
       ├── 已压缩的工具输出 → "[Old tool result content cleared]"
       ├── 错误的 AssistantMessage → 跳过（除非有非错误 parts）
       └── 中断的工具 → "[Tool execution was interrupted]"

  4. 调用 ai.streamText():
       model, messages, tools, toolChoice, maxOutputTokens, ...
```

### 1.4 循环终止条件

| 条件 | 触发位置 | 说明 |
|------|---------|------|
| 正常完成 | loop() 入口检查 | lastAssistant.finish 为 stop/error/length 且早于 lastUser |
| 权限拒绝 | processor → blocked=true | 用户拒绝权限请求 |
| 不可重试错误 | processor → error | API 错误、Auth 错误等 |
| 结构化输出完成 | loop() 专项检查 | JSON schema 模式下 StructuredOutput 工具被调用 |
| steps 上限 | loop() 步数检查 | 配置了 agent.steps = N |
| 主动 break | processor → "stop" | 由上述任一条件触发 |

---

## 二、上下文管理设计

### 2.1 Token 追踪

OpenCode 使用**双轨制**：
- **实际 token 计数**：LLM API 返回的 `usage.inputTokens`，在 `step-finish` 事件中更新到 AssistantMessage
- **估算 token 数**：`Math.round(text.length / 4)`，仅用于 prune 决策（快速判断，无需调 API）

溢出判断：
```python
# 伪代码
usable_tokens = model.context_limit - reserved_tokens
reserved_tokens = min(config.reserved ?? 20000, model.max_output_tokens)

if current_input_tokens >= usable_tokens:
    trigger_compaction()
```

**设计要点**：预留 reserved tokens 保证模型还能生成输出，不只是卡在输入上限。

### 2.2 Compaction 流程详解

Compaction 分两个阶段：**Prune（剪枝）** 和 **Summarize（摘要）**。

#### 阶段一：Prune

```
prune(sessionID):
  从最新消息往历史方向遍历
  找到最后一条 summary 消息之前的所有 ToolPart 输出

  满足以下条件才剪除:
    ① 总 token 数 > PRUNE_MINIMUM (20k)
    ② 可以剪除的 token 数 > 40k   ← 防止无效剪枝

  剪除 = 给 ToolPart 打上 time.compacted 时间戳
        （软删除，不物理删除，转换时替换为占位符）
```

**保护策略**：
- 最近 2 轮对话不剪除
- skill 类工具输出不剪除
- 已有 summary 消息之后的内容不剪除

#### 阶段二：Summarize

```
compaction_process(sessionID):
  1. prune()  ← 先剪除冗余工具输出

  2. 调用专用 "compaction" Agent:
       prompt = 要求模型输出结构化摘要:
         - Goal: 用户目标
         - Instructions: 重要指令
         - Discoveries: 发现的关键信息
         - Accomplished: 已完成的事项
         - Files: 修改过的文件

  3. 摘要结果存入 AssistantMessage (summary=true)

  4. 自动续跑（auto=true 时）:
       if 有 replay 消息（原始用户输入）:
           创建新 UserMessage 携带原始内容
       else:
           创建合成 UserMessage: "Continue where we left off."

  5. 发布 Event.Compacted
```

### 2.3 系统提示构建

系统提示的拼接顺序（从上到下追加）：
```
1. Agent 自身 prompt（agent.prompt 字段）
2. Provider 级 prompt（某些 provider 有特殊前缀）
3. 会话级 custom system（用户传入）
4. 环境信息（SystemPrompt.environment()）
   - 操作系统、工作目录、日期时间
   - 已安装工具、语言运行时
5. 可用技能列表（SystemPrompt.skills()）
6. Instruction 文件内容（config.instructions[] 中的文件路径）
7. 结构化输出指令（若 format.type === "json_schema"）
```

**关键设计**：`config.instructions` 是文件路径数组，Agent 启动时动态读取文件内容追加到系统提示，实现项目级定制而无需修改代码。

---

## 三、消息数据结构

### 3.1 消息的双层结构

```
Message（消息头）
  ├── role: "user" | "assistant"
  ├── id, sessionID, time
  ├── agent, model (providerID + modelID)
  └── [assistant only] finish, tokens, cost, error, summary

Part（消息体，一条消息可有多个 Part）
  ├── TextPart      — 文本响应，含时间戳
  ├── ReasoningPart — 推理 token（如 Claude 扩展思考）
  ├── ToolPart      — 工具调用，含完整状态机
  ├── FilePart      — 附件文件
  ├── StepStartPart — 快照边界标记（记录执行前文件状态）
  ├── PatchPart     — 文件变更 patch
  ├── CompactionPart — 压缩标记
  └── RetryPart     — 重试记录
```

### 3.2 ToolPart 状态机

```
       创建工具调用
           ↓
       [pending]
           ↓ 开始执行
       [running]
           ↓              ↓              ↓           ↓
    [completed]        [error]     [user-denied]  [partial]
    含 output          含 errorText   含 reason    含部分 output
```

状态转换时机：
- `pending` → `running`：Tool.execute() 开始调用
- `running` → `completed`：Tool.execute() 正常返回
- `running` → `error`：Tool.execute() 抛出异常
- `running` → `user-denied`：Permission.ask() 被用户拒绝
- 任意 → `partial`：stream 中途被 abort

### 3.3 消息转 ModelMessage 时的特殊处理

```python
# 伪代码：关键转换规则
for message in history:
    if message.role == "assistant":
        if message.error and not message.has_non_error_parts:
            skip()  # 纯错误消息不发给模型

        for part in message.parts:
            if part.type == "tool" and part.time.compacted:
                output = "[Old tool result content cleared]"
            elif part.type == "tool" and part.status == "pending/running":
                output = "[Tool execution was interrupted]"
```

---

## 四、Agent 模式设计

### 4.1 五种内置 Agent

```
build (primary, 默认主 Agent)
  permissions:
    allow: question, plan-entry, *（所有工具默认允许）
    deny:  plan-exit, .env 文件访问
  特点: 可用全部工具，面向实际编码任务

plan (primary, hidden)
  permissions:
    allow: question, plan-exit
    deny:  所有 edit 类工具（除 .opencode/plans/*.md）
  特点: 只读规划模式，防止规划阶段意外修改文件

general (subagent)
  permissions:
    deny: todowrite
  特点: 通用子任务执行，不能维护 TODO（防循环依赖）

explore (subagent)
  permissions:
    allow: grep, glob, bash, read, webfetch, websearch
    deny:  * （其余全拒绝）
  特点: 超轻量搜索 Agent，只读，快速返回

compaction (primary, hidden)
  permissions:
    deny: * （所有工具全拒绝）
  特点: 纯文本摘要，不执行任何工具
```

### 4.2 primary vs subagent 的本质区别

| 维度 | primary | subagent |
|------|---------|----------|
| 调用方式 | 用户直接选择 | 由 task 工具触发，loop() 内部处理 |
| 维护 TODO | 可以（build 默认允许） | general 明确禁止 |
| 会话归属 | 独立主 Agent | 嵌套在父 Agent 消息流中 |
| 结果返回 | 持续输出直到用户终止 | 返回文本结果给调用它的工具 |

### 4.3 子任务（Subtask）执行机制

子任务不是递归调用，而是在**同一个 loop 迭代中的特殊分支**：

```
loop() 发现 pending SubtaskPart:
  1. TaskTool.init() 获取任务执行器
  2. 创建新 AssistantMessage（mode = task.agent）
  3. 为这条消息创建 ToolPart（状态: pending）
  4. 执行 TaskTool（内部会调 LLM，可能多轮）
  5. 捕获结果 → 更新 ToolPart（completed/error）
  6. if task.command:
       创建合成 UserMessage 要求主 Agent 总结结果
  7. continue 主 loop
```

**设计意图**：子任务的结果作为工具调用结果回到主 Agent 的上下文，主 Agent 可以基于子任务结果继续规划。

### 4.4 Plan 模式的工作方式

Plan 模式不是一个单独的程序流，而是通过**权限锁定**实现：

```
进入 plan 模式:
  session.agent = "plan"
  plan Agent 的 permission deny 掉所有写操作
  → Agent 只能读取、搜索、思考，无法修改文件

退出 plan 模式:
  plan Agent 调用 "plan-exit" 工具
  → 通过权限规则 allow(plan-exit) 才能触发
  → 切换回 build Agent
```

---

## 五、权限系统细节

### 5.1 规则评估算法

```python
def evaluate(permission, pattern, *rulesets):
    rules = flatten(rulesets)
    # findLast: 后定义的规则优先（覆盖语义）
    match = last(r for r in rules
                 if wildcard_match(permission, r.permission)
                 and wildcard_match(pattern, r.pattern))
    return match.action if match else "ask"  # 默认为 ask

# 示例：
# permission="bash", pattern="rm -rf /"
# 规则: [{permission:"*", pattern:"*", action:"allow"},
#         {permission:"bash", pattern:"rm*", action:"ask"}]
# 结果: "ask"（后者更具体，覆盖前者）
```

### 5.2 权限请求的三种响应

```
用户收到 Event.Asked（权限请求事件）后:

"once":
  允许本次调用
  不添加到规则集

"always":
  允许本次调用
  向 session.permission 添加 {action:"allow", permission:X, pattern:Y}
  同 session 内相同权限的 pending 请求自动批准

"reject":
  拒绝本次调用（RejectedError）
  取消 session 内所有 pending 权限请求
  processor 设置 blocked=true → loop 终止
```

### 5.3 Doom Loop 检测

```python
# 连续3次完全相同的工具调用 → 强制权限询问
recent_tools = last_3_tool_parts()
if all(t.tool == recent_tools[0].tool and
       t.input == recent_tools[0].input
       for t in recent_tools):
    ctx.ask(permission="doom_loop", ...)
```

---

## 六、对我们系统的关键启示

### 6.1 Agent Loop 设计决策

**采纳**：
1. **while(true) + 多退出点**比状态机更简单直接，适合我们用 Python 实现
2. **steps 上限**是必要的安全阀，防止嵌入式调试场景中工具调用无限循环
3. **processor 返回语义值**（continue/stop/compact）而不是抛异常，控制流清晰
4. **doom loop 检测**（连续 N 次相同调用）对嵌入式场景很重要（如反复调同一编译命令失败）

**简化**：
- 去掉 subtask/subagent 的 pending part 机制，我们用简单的同步调用即可
- retry_loop 简化：最多重试 2 次，不做指数退避（内网场景网络稳定）

### 6.2 上下文管理决策

**采纳**：
1. **reserved tokens 预留**：我们也需要预留输出空间（建议预留 4k-8k）
2. **软删除 + 占位符**：compacted 的工具输出替换为 "[已清理]"，不物理删除历史记录
3. **保护最近 N 轮**：N=2 是合理默认值
4. **专用 compaction Agent**：系统提示更聚焦，不污染主 Agent 的上下文

**调整**：
- token 估算用 `len(text) / 3.5`（中文比英文密度高）
- compaction 摘要格式针对嵌入式 C 定制：增加"当前编译状态"、"未解决的错误"字段

### 6.3 模式设计决策

OpenCode 的模式本质是**通过权限差异区分角色**，我们可以类比：

| OpenCode Agent | 我们的对应模式 |
|----------------|--------------|
| build (默认) | `code` 模式：可读写、编译、测试 |
| plan (只读规划) | `plan` 模式：只读，输出规划文档 |
| explore (搜索) | 可选：快速代码搜索，只用 grep/glob/read |
| compaction (内务) | `compact` 模式：内部使用，用户不可见 |

**关键设计**：模式 = 权限集合的别名，切换模式 = 切换权限集合，不需要不同的代码路径。

### 6.4 消息结构决策

**采纳**：
- Part-based 结构：`TextPart` + `ToolPart`（含状态机）+ `PatchPart`
- ToolPart 的 5 态状态机（pending/running/completed/error/user-denied）
- AssistantMessage 记录 tokens、cost、finish_reason

**简化**：
- 去掉 ReasoningPart（我们不需要扩展思考）
- 去掉 SnapshotPart（用 git diff 替代）
- 去掉 SubtaskPart（简化子任务机制）

### 6.5 权限系统决策

**采纳核心**：
- 三值决策（allow/deny/ask）
- 通配符模式匹配工具调用字符串
- "always" 响应将规则写入 session 级规则集

**初期简化**：
- 内置工具集固定，初期用静态白名单即可
- 危险操作（如 `git reset --hard`、`rm`）默认 ask，其余 allow
- 不需要运行时规则优先级覆盖，配置文件中写死即可

---

## 七、我们的 Agent Loop 伪代码草案

基于 OpenCode 的设计，适配 Python + Windows 7 + 嵌入式 C 场景：

```python
def agent_loop(session_id: str, max_steps: int = 50) -> Message:
    step = 0

    while True:
        # 退出检查
        last_assistant = get_last_assistant(session_id)
        last_user = get_last_user(session_id)

        if (last_assistant and
            last_assistant.finish in ("stop", "length") and
            last_assistant.id < last_user.id):
            break

        if step >= max_steps:
            break

        # 上下文检查
        tokens = estimate_tokens(session_id)
        if is_overflow(tokens, model_context_limit):
            compact(session_id)
            continue

        # 工具集解析
        tools = get_allowed_tools(current_agent.permissions)

        # 流式调用 LLM
        result = process_stream(session_id, tools)

        if result == "stop":
            break
        elif result == "compact":
            compact(session_id)

        step += 1

    return get_last_assistant(session_id)


def process_stream(session_id, tools) -> str:
    """返回 'continue' | 'stop' | 'compact'"""

    messages = build_model_messages(session_id)
    system = build_system_prompt(current_agent)

    needs_compact = False
    blocked = False

    for event in llm_stream(messages, tools, system):
        if event.type == "tool_call":
            tool_part = create_tool_part(event, status="pending")

            # 权限检查
            try:
                check_permission(event.tool, event.args)
            except DeniedError:
                tool_part.status = "user-denied"
                blocked = True
                break

            # Doom loop 检测
            if is_doom_loop(session_id, event.tool, event.args):
                if not ask_permission("doom_loop"):
                    blocked = True
                    break

            # 执行工具
            tool_part.status = "running"
            try:
                result = execute_tool(event.tool, event.args)
                tool_part.status = "completed"
                tool_part.output = result
            except Exception as e:
                tool_part.status = "error"
                tool_part.error = str(e)

        elif event.type == "text_delta":
            update_text_part(event.delta)

        elif event.type == "step_finish":
            update_tokens(event.usage)
            if is_overflow(event.usage.input_tokens, model_context_limit):
                needs_compact = True
                break

        elif event.type == "finish":
            save_finish_reason(event.reason)

    if needs_compact:
        return "compact"
    if blocked:
        return "stop"
    return "continue"
```
