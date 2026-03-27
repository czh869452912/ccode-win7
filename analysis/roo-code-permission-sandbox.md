# Roo-Code 权限管理与运行沙箱分析

> 聚焦：工具批准机制、文件访问控制、命令执行限制、自动批准配置
> 参考源码：`src/core/auto-approval/`, `src/core/ignore/`, `src/core/protect/`, `src/core/task/Task.ts`

---

## 一、整体安全架构

Roo-Code 采用**纵深防御**策略，分为四个层次：

```
用户请求执行操作
       │
       ▼
┌──────────────────────────────────┐
│  Layer 1：文件读取访问控制        │
│  RooIgnoreController (.rooignore) │
│  阻止 LLM 读取敏感文件            │
└──────────────────────────────────┘
       │ 通过
       ▼
┌──────────────────────────────────┐
│  Layer 2：命令注入检测            │
│  containsDangerousSubstitution()  │
│  拦截 shell 注入模式              │
└──────────────────────────────────┘
       │ 通过
       ▼
┌──────────────────────────────────┐
│  Layer 3：工具批准（ask/answer）  │
│  自动批准 or 等待用户确认         │
│  受 allowedCommands/保护文件控制  │
└──────────────────────────────────┘
       │ 批准
       ▼
┌──────────────────────────────────┐
│  Layer 4：写入保护                │
│  RooProtectedController           │
│  配置文件强制人工确认             │
└──────────────────────────────────┘
```

---

## 二、工具批准系统（ask/answer 模式）

### 2.1 核心 ask() 方法

```typescript
// Task.ts
async ask(
  type: ClineAsk,
  text?: string,
  partial?: boolean,
  progressStatus?: ToolProgressStatus,
  isProtected?: boolean,  // ← 是否为受保护操作，强制人工确认
): Promise<{ response: ClineAskResponse; text?: string; images?: string[] }>
```

执行流程：
1. 调用 `checkAutoApproval()` 检查是否满足自动批准条件
2. 若满足 → 直接返回 `"yesButtonClicked"`，不阻塞循环
3. 若不满足 → 创建 ClineMessage，**阻塞等待**用户点击确认/拒绝

### 2.2 工具回调接口（BaseTool 视角）

```typescript
// BaseTool.ts
interface ToolCallbacks {
  askApproval: AskApproval       // 请求用户批准
  handleError: HandleError       // 工具执行错误
  pushToolResult: PushToolResult // 将结果注入对话历史
}

// presentAssistantMessage.ts — askApproval 的实际实现
const askApproval = async (type, partialMessage, progressStatus, isProtected) => {
  const { response, text, images } = await cline.ask(type, partialMessage, false, progressStatus, isProtected)

  if (response !== "yesButtonClicked") {
    // 用户拒绝 → 注入拒绝结果，设置 didRejectTool = true
    pushToolResult(formatResponse.toolDenied())
    cline.didRejectTool = true
    return false
  }
  return true  // 批准 → 工具继续执行
}
```

用户拒绝后，`didRejectTool = true` 信号会影响后续循环行为（通常触发一条提示让 LLM 知晓）。

### 2.3 自动批准的分类与粒度

`checkAutoApproval()` 按操作类型分别决策：

| 自动批准开关 | 控制范围 | 默认值 |
|------------|---------|--------|
| `autoApprovalEnabled` | 总开关 | false |
| `alwaysAllowReadOnly` | read_file, list_files, search_files | false |
| `alwaysAllowReadOnlyOutsideWorkspace` | 工作区外的只读操作 | false |
| `alwaysAllowWrite` | 文件写入/编辑 | false |
| `alwaysAllowWriteOutsideWorkspace` | 工作区外的写入 | false |
| `alwaysAllowWriteProtected` | 覆写受保护配置文件 | false |
| `alwaysAllowExecute` | execute_command | false |
| `alwaysAllowMcp` | MCP 工具调用 | false |
| `alwaysAllowModeSwitch` | 切换模式 | false |
| `alwaysAllowSubtasks` | new_task / finish_task | false |
| `alwaysAllowFollowupQuestions` | ask_followup_question | false |
| `allowedCommands` | 命令前缀白名单（列表） | [] |
| `deniedCommands` | 命令前缀黑名单（列表） | [] |

**始终自动批准**（无法关闭）：
- `update_todo_list` — TODO 维护无需确认
- `run_slash_command`（skill 工具）— 预装技能无需确认

### 2.4 受保护操作的特殊处理

当 `isProtected = true` 时，**自动批准完全失效**，即使 `alwaysAllowWrite = true` 也必须人工点击：

```typescript
// checkAutoApproval() 内部
if (isProtected && !settings.alwaysAllowWriteProtected) {
  return false  // 强制进入人工确认流程
}
```

---

## 三、文件读取访问控制（.rooignore）

### 3.1 RooIgnoreController

**实现文件**：`src/core/ignore/RooIgnoreController.ts`

基于 `ignore` npm 包（与 .gitignore 语法完全兼容），控制 LLM 可读取的文件范围。

```typescript
validateAccess(filePath: string): boolean {
  if (!this.rooIgnoreContent) return true  // 无 .rooignore → 全部允许

  const absolutePath = path.resolve(this.cwd, filePath)
  // 关键：解析符号链接，防止 symlink 绕过
  const realPath = fsSync.realpathSync(absolutePath)
  const relativePath = path.relative(this.cwd, realPath).toPosix()

  return !this.ignoreInstance.ignores(relativePath)  // 未被忽略 → 允许
}
```

**防 symlink 绕过**：所有路径先解析为真实路径再匹配，无法通过软链接跳出限制。

### 3.2 命令中的文件访问检测

`validateCommand()` 检测命令行中是否访问了被忽略的文件：

```typescript
validateCommand(command: string): string | undefined {
  // 监控的命令：cat, less, more, head, tail, grep, awk, sed
  //            get-content, gc, type（PowerShell）, select-string, sls
  // 返回 undefined → 命令允许
  // 返回 filePath → 阻止（含被拦截的文件路径）
}
```

### 3.3 .rooignore 语法

与 .gitignore 完全一致：
```
# 忽略所有密钥文件
*.key
*.pem
secrets/

# 忽略编译产物（LLM 不需要读）
build/
*.o
*.elf

# 忽略大型二进制
firmware.bin
```

**UI 反馈**：被忽略的文件在文件树中显示 🔒 标记。

---

## 四、文件写入保护（.rooprotected 系统）

### 4.1 RooProtectedController

**实现文件**：`src/core/protect/RooProtectedController.ts`

防止 AI 自动修改项目配置文件，即使开启了 `alwaysAllowWrite` 也需要人工二次确认。

**硬编码保护模式**（不可被 .rooignore 覆盖）：

```typescript
private static readonly PROTECTED_PATTERNS = [
  ".rooignore",         // 忽略规则文件
  ".roomodes",          // 模式配置
  ".roorules*",         // 规则文件
  ".clinerules*",       // 兼容 Cline 规则
  ".roo/**",            // Roo 配置目录
  ".vscode/**",         // VS Code 配置
  "*.code-workspace",   // 工作区文件
  ".rooprotected",      // 保护规则文件本身
  "AGENTS.md",          // Agent 指令文件
  "AGENT.md",
]
```

```typescript
isWriteProtected(filePath: string): boolean {
  const relativePath = path.relative(this.cwd, path.resolve(this.cwd, filePath)).toPosix()
  if (relativePath.startsWith("..")) return false  // 工作区外不适用
  return this.ignoreInstance.ignores(relativePath)
}
```

**UI 反馈**：受保护文件显示 🛡️ 标记，确认对话框有特殊警告样式。

---

## 五、命令执行安全

### 5.1 Shell 注入检测

**实现文件**：`src/core/auto-approval/commands.ts`

`containsDangerousSubstitution()` 检测以下危险模式：

```typescript
// 检测的危险模式
const checks = {
  // ${var@P} — Prompt 字符串展开，可执行命令
  dangerousParameterExpansion: /\$\{[^}]*@[PQEAa][^}]*\}/,

  // ${var=value\140...} — 含转义序列的赋值（八进制\140 = 反引号）
  octalEscapeInAssignment: /\$\{[^}]*[=+\-?][^}]*\\[0-7]{3}[^}]*\}/,
  hexEscapeInAssignment: /\$\{[^}]*[=+\-?][^}]*\\x[0-9a-fA-F]{2}[^}]*\}/,
  unicodeEscapeInAssignment: /\$\{[^}]*[=+\-?][^}]*\\u[0-9a-fA-F]{4}[^}]*\}/,

  // ${!var} — 间接变量引用，可导致代码执行
  indirectExpansion: /\$\{![^}]+\}/,

  // <<<$(...) — Here-string 含命令替换
  hereStringWithSubstitution: /<<<\s*(\$\(|`)/,

  // =(...) — Zsh 进程替换
  zshProcessSubstitution: /(?:(?<=^)|(?<=[\s;|&(<]))=\([^)]+\)/,

  // *(e:...:) — Zsh glob 限定符
  zshGlobQualifier: /[*?+@!]\(e:[^:]+:\)/,
}
```

一旦检测到任意危险模式，**无论白名单如何配置**，都强制进入人工确认。

### 5.2 命令白名单的最长前缀匹配算法

```typescript
getCommandDecision(command, allowedCommands, deniedCommands): "auto_approve" | "auto_deny" | "ask_user"
```

**执行步骤**：

1. **先检测危险模式**：有危险 → 直接 `ask_user`
2. **拆分命令链**：按 `&&`, `||`, `;`, `|`, `&` 分割
3. **逐个子命令决策**：对每个子命令，找到最长匹配前缀
4. **任一拒绝则全拒绝**：`any(deny) → auto_deny`
5. **全部批准才批准**：`all(approve) → auto_approve`

**最长前缀匹配决策表**：

| 白名单最长匹配 | 黑名单最长匹配 | 结果 | 说明 |
|-------------|-------------|------|------|
| 有 | 无 | `auto_approve` | 只命中白名单 |
| 无 | 有 | `auto_deny` | 只命中黑名单 |
| 有（更长） | 有（更短） | `auto_approve` | 白名单更具体 |
| 有（更短） | 有（更长） | `auto_deny` | 黑名单更具体 |
| 无 | 无 | `ask_user` | 无规则 → 询问用户 |

**示例**：

```
allowedCommands = ["git"]
deniedCommands  = ["git push"]

"git status"           → auto_approve  (git 命中白名单，无黑名单匹配)
"git push origin main" → auto_deny     (git push 命中黑名单，比 git 更长)
"git status && rm -rf" → auto_deny     (rm -rf 无白名单匹配)
'echo "${var@P}"'      → ask_user      (危险模式检测)
```

### 5.3 双超时机制

```
命令开始执行
    │
    ├──── agentTimeout（Agent 超时）
    │         │ 时间到
    │         ▼
    │     命令转为后台运行
    │     循环继续（命令仍在执行）
    │
    └──── userTimeout（用户配置超时）
              │ 时间到
              ▼
          强制终止命令（kill process）
          抛出超时错误

注意：两个计时器独立运行
用户超时即使在 Agent 超时后也保持激活（安全兜底）
```

**配置**：
- `commandExecutionTimeout`：全局超时秒数（0 = 不限制）
- `commandTimeoutAllowlist`：豁免超时的命令前缀列表（如 `make`, `cmake --build`）

---

## 六、沙箱能力边界总结

| 安全层 | 机制 | 强制性 | 可配置绕过？ |
|--------|------|--------|------------|
| **文件读取限制** | .rooignore 模式匹配 | 工具层强制 | 需手动修改 .rooignore |
| **受保护文件写入** | 硬编码模式，isProtected 标记 | 强制人工确认 | 需开启 `alwaysAllowWriteProtected` |
| **Shell 注入** | 危险替换模式检测 | 强制人工确认 | 不可绕过 |
| **命令白名单** | 最长前缀匹配 | 影响自动批准决策 | 可修改白/黑名单 |
| **命令超时** | 双超时计时器 | 用户超时为硬限制 | 可加入豁免列表 |
| **工具批准** | ask/answer 阻塞 | 无批准不执行 | 可开启自动批准 |
| **路径逃逸** | symlink 真实路径解析 | 强制 | 不可绕过 |

---

## 七、对我们项目的启示

### 7.1 必须实现的安全机制

1. **工具批准回调**：`askApproval` 模式必须实现，危险操作（写文件、执行命令）在 TUI 显示确认提示
2. **命令超时**：嵌入式开发中 `make` / `flash` 等命令可能长时间运行，必须有超时兜底
3. **路径检查**：避免 Agent 写入工作区外的文件（防止误操作系统目录）

### 7.2 可以简化的部分

| Roo-Code 机制 | 我们的处理建议 |
|-------------|-------------|
| .rooignore（动态文件监听） | 简化为启动时读取一次配置文件 |
| .rooprotected（硬编码模式） | 只保护项目配置文件（CLAUDE.md 等） |
| MCP 的 alwaysAllow | 无 MCP，不需要 |
| 工作区外写入开关 | 直接禁止（嵌入式项目边界清晰） |
| followupAutoApproveTimeoutMs | 可选，降低复杂度 |

### 7.3 嵌入式场景的特殊需求

```
建议增加的安全控制：

1. 编译器路径白名单
   - 只允许调用配置的 gcc/arm-none-eabi-gcc 路径
   - 防止 LLM 安装任意工具链

2. 烧录命令保护
   - openocd / J-Link 命令强制人工确认
   - 防止意外烧录错误固件

3. Git 操作保护
   - git push / git reset --hard 强制确认
   - git commit 可自动批准（低风险）

4. 禁止的操作
   - rm -rf（删除整个目录）
   - 修改 Makefile 中的目标设备配置
```

### 7.4 自动批准的推荐默认配置（嵌入式场景）

```yaml
autoApproval:
  enabled: true
  alwaysAllowReadOnly: true        # 读文件无需确认（常见操作）
  alwaysAllowWrite: false          # 写文件需要确认（默认安全）
  alwaysAllowExecute: false        # 命令需要确认（默认安全）

  allowedCommands:
    - "gcc"
    - "make"
    - "arm-none-eabi-gcc"
    - "arm-none-eabi-size"
    - "git status"
    - "git diff"
    - "git log"
    - "git add"
    - "git commit"
    - "ctags"

  deniedCommands:
    - "rm -rf"
    - "git push"
    - "git reset --hard"
    - "openocd"          # 烧录操作，强制确认
    - "JLinkExe"
    - "sudo"

  protectedFiles:
    - "Makefile"
    - "*.ld"             # 链接脚本，改错了无法编译
    - ".gitconfig"
    - "openocd.cfg"
```
