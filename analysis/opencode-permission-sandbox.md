# OpenCode 权限管理与执行沙箱分析

> 聚焦：权限规则结构、评估算法、分层机制、工具执行隔离
> 面向轻量化嵌入式 C 编程 Agent 的设计参考

---

## 一、权限规则数据结构

### 1.1 核心类型

```typescript
// 三值动作
Action = "allow" | "deny" | "ask"

// 单条规则
Rule = {
  permission: string,  // 权限标识符，支持通配符
  pattern:    string,  // 资源路径或调用字符串，支持通配符
  action:     Action,
}

// 规则集 = Rule[]
Ruleset = Rule[]
```

### 1.2 权限请求结构

```typescript
Request = {
  id:         PermissionID,
  sessionID:  SessionID,
  permission: string,      // 权限类型："bash" | "edit" | "read" | "external_directory" | ...
  patterns:   string[],    // 本次请求的资源列表（可多个）
  always:     string[],    // 用户选择 "always" 时写入规则的模式
  metadata:   object,      // 展示给用户的上下文（diff、路径等）
  tool?: { messageID, callID }
}

Reply = "once" | "always" | "reject"
```

**`patterns` vs `always` 的区别**：
- `patterns`：本次请求实际涉及的资源（精确路径，如 `/project/src/main.c`）
- `always`：若用户选 "always"，写入规则集的通配模式（如 `src/*.c`）

用户看到的是 `patterns`，持久化的是 `always`，两者可以不同，实现"精确确认、宽泛授权"。

---

## 二、通配符语法

来自 `util/wildcard.ts`，规则：

| 语法 | 含义 |
|------|------|
| `*` | 匹配任意字符序列（包括空） |
| `?` | 匹配单个任意字符 |
| `空格*`（尾部） | 使尾部可选：`git *` 匹配 `git` 和 `git checkout main` |
| `/` | 跨平台统一为正斜杠 |
| Windows | 大小写不敏感（`si` 标志），Unix 大小写敏感 |

**示例**：
```
"bash"          匹配  "bash"          （精确权限类型）
"*"             匹配  "bash"/"edit"   （任意权限）
"*.env"         匹配  ".env"          但不匹配 ".env.local"
"*.env.*"       匹配  ".env.local"    ".env.production"
"git *"         匹配  "git"           "git checkout main"
"npm run *"     匹配  "npm run dev"   "npm run build"
```

实现为正则：`* → .*`，`? → .`，尾部 ` .*` → `( .*)?`，两端加 `^...$`。

---

## 三、规则评估算法

### 3.1 核心算法（`permission/evaluate.ts`）

```typescript
function evaluate(permission: string, pattern: string, ...rulesets: Rule[][]): Rule {
  const rules = rulesets.flat()
  const match = rules.findLast(
    (rule) =>
      Wildcard.match(permission, rule.permission) &&
      Wildcard.match(pattern,    rule.pattern)
  )
  return match ?? { action: "ask", permission, pattern: "*" }
}
```

关键点：
1. **展平**所有规则集为单一数组
2. **`findLast`**：最后匹配的规则胜出（后定义覆盖先定义）
3. **双重通配**：`permission` 字段和 `pattern` 字段都要匹配
4. **默认 `ask`**：无匹配时不是 allow 也不是 deny，而是询问用户

### 3.2 为什么是 findLast 而不是 findFirst

```
规则数组（按定义顺序排列）:
  [0] { permission:"*",    pattern:"*",       action:"allow" }  ← 全局默认
  [1] { permission:"read", pattern:"*.env",   action:"ask"   }  ← 更具体的覆盖
  [2] { permission:"read", pattern:"*.env.example", action:"allow" }  ← 再次覆盖

请求：permission="read", pattern=".env.example"
  规则[0]: "*" 匹配 "read" ✓, "*" 匹配 ".env.example" ✓  → allow
  规则[1]: "read" 匹配 "read" ✓, "*.env" 匹配 ".env.example" ✗  → 跳过
  规则[2]: "read" 匹配 "read" ✓, "*.env.example" 匹配 ".env.example" ✓  → allow
  findLast → 规则[2] → allow  ✓ 正确

如果用 findFirst → 规则[0] → allow  （虽然结果相同，但原因不对）
```

`findLast` 使得"越具体的规则优先级越高"，只要把它放在数组后面即可。

---

## 四、权限分层机制

### 4.1 四层规则栈（优先级从低到高）

```
Layer 1: 全局硬编码默认值（最低优先）
  └── 构成基础安全底线

Layer 2: Agent 自身规则（硬编码在 agent 定义里）
  └── 按 Agent 职责定制

Layer 3: 用户配置（config.json 的 permission 字段）
  └── 用户对所有 Agent 的全局覆盖

Layer 4: Session 运行时 approved（最高优先）
  └── 本次会话中用户 "always" 批准积累的规则
```

实际合并方式（`Permission.merge()`）：
```typescript
// build Agent 示例
permission = Permission.merge(
  defaults,   // Layer 1 + 2 合并
  user,       // Layer 3
)
// session approved 在 evaluate 调用时额外传入：
evaluate(permission, pattern, ruleset, approved)
//                                     ↑ Layer 4，最后传入，findLast 下优先级最高
```

### 4.2 全局默认规则（`agent/agent.ts`）

```typescript
defaults = {
  "*":                    "allow",   // 默认全允许
  "doom_loop":            "ask",     // 重复调用检测
  "external_directory": {
    "*":                  "ask",     // 项目外目录需询问
    // 白名单目录（系统目录、home 等）: "allow"
  },
  "question":             "deny",
  "plan_enter":           "deny",
  "plan_exit":            "deny",
  "read": {
    "*":                  "allow",
    "*.env":              "ask",     // .env 文件需询问
    "*.env.*":            "ask",     // .env.local 等需询问
    "*.env.example":      "allow",   // .env.example 无密钥，允许
  },
}
```

### 4.3 各 Agent 的权限差异

```
build（默认主 Agent）
  在 defaults 基础上追加:
    question:   allow
    plan_enter: allow
  → 几乎全权限，可以做任何事

plan（只读规划模式）
  在 defaults 基础上追加:
    question:   allow
    plan_exit:  allow
    edit: {
      "*":                    deny    ← 禁止一切写入
      ".opencode/plans/*.md": allow   ← 只允许写规划文档
    }
  → 只读，只能写规划 Markdown

explore（搜索子 Agent）
  在 defaults 基础上追加:
    "*": deny                         ← 先全禁
    grep/glob/read/bash/webfetch: allow  ← 白名单开放
  → 纯只读，搜索用途

general（通用子 Agent）
  在 defaults 基础上追加:
    todowrite: deny                   ← 不允许维护 TODO
  → 基本全权限但不能管理任务

compaction（压缩内务 Agent）
  在 defaults 基础上追加:
    "*": deny                         ← 全禁工具
  → 纯文本生成，不执行任何工具
```

---

## 五、Session 运行时授权机制

### 5.1 "always" 授权的存储与应用

```python
# 内存结构（session 生命周期内）
approved: List[Rule] = []   # 本 session 积累的 always 规则
pending:  Dict[id, Request] # 等待用户响应的挂起请求

# 用户选择 "always" 时：
for pattern in request.always:
    approved.append({
        permission: request.permission,
        pattern:    pattern,
        action:     "allow"
    })

# 回溯：检查当前 pending 里是否有能被新规则覆盖的请求
for pending_req in pending.values():
    if pending_req.sessionID != current_sessionID:
        continue   # 只影响同一 session
    if all(evaluate(p, approved) == "allow" for p in pending_req.patterns):
        auto_approve(pending_req)  # 自动批准，无需用户再操作
```

**重要限制**：
- 仅存在于**内存**中，重启后消失
- 仅作用于**同一 session**
- 必须 `patterns` 中**所有项**都被覆盖才触发回溯批准

### 5.2 "reject" 的连锁效应

```python
if reply == "reject":
    fail(request)   # 本请求抛 RejectedError
    # 取消同 session 内所有 pending 请求
    for req in pending.values():
        if req.sessionID == current_sessionID:
            cancel(req)
    # processor 设置 blocked=True → loop 返回 "stop" → 终止
```

用户一次拒绝 = 终止整个 Agent 执行轮次，防止 Agent 在拒绝后继续尝试其他危险操作。

---

## 六、Bash 工具执行控制

### 6.1 超时机制

```typescript
DEFAULT_TIMEOUT = 2 * 60 * 1000  // 2分钟，可通过环境变量覆盖

// 工具执行时：
const timer = setTimeout(() => {
    timedOut = true
    kill()           // 触发进程树终止
}, timeout + 100)   // +100ms 宽限期
```

- 默认 2 分钟，可通过 `OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS` 覆盖
- 单次调用可传 `timeout` 参数覆盖
- 超时后走进程树终止流程

### 6.2 进程终止策略

```
Unix:
  ① kill(-pid, SIGTERM)   发给整个进程组（-pid = 进程组 ID）
  ② 等待 200ms
  ③ kill(-pid, SIGKILL)   若仍存活则强杀
  ④ fallback: 仅终止主进程（如 -pid 失败）

Windows:
  taskkill /pid <pid> /f /t
  /f = 强制
  /t = 终止子进程树
```

**设计要点**：用进程组/进程树终止，防止子进程孤儿（如 `bash -c "sleep 100 &"`）。

### 6.3 命令权限分析（调用前的权限检查）

bash 工具在执行前用 **tree-sitter 解析命令**，提取需要检查的信息：

```
输入命令: "git checkout -b feature/my-branch"

① 语法解析（tree-sitter bash parser）
   → 识别命令节点: ["git", "checkout", "-b", "feature/my-branch"]

② 文件路径提取（针对 cd/rm/cp/mv/cat 等）
   → 若目标路径在项目外 → 加入 external_directory 权限检查

③ 命令规范化（BashArity）
   → git: arity=2 → 取前2个 token → "git checkout"
   → always 模式: "git checkout *"

④ 发起权限请求:
   ctx.ask({
     permission: "bash",
     patterns: ["git checkout -b feature/my-branch"],  // 精确命令
     always:   ["git checkout *"],                     // 规范化通配
   })
```

**BashArity 映射（部分）**：
```
git:        2   →  "git checkout *", "git commit *", "git push *"
npm run:    3   →  "npm run dev", "npm run build *"
docker:     2   →  "docker run *", "docker build *"
```

### 6.4 外部目录检测

```python
# 路径是否在项目内的判断
def contains_path(filepath):
    # 不能通过 ".." 从项目根目录到达该路径
    return not relative(instance.directory, filepath).startswith("..")

# 若路径在项目外，发起 external_directory 权限请求
if not contains_path(target_path):
    parent_glob = os.path.join(parent_dir, "*")
    ctx.ask(
        permission = "external_directory",
        patterns   = [parent_glob],   # e.g., "/home/user/other-project/*"
        always     = [parent_glob],
    )
```

### 6.5 输出截断

| 限制项 | 数值 | 说明 |
|--------|------|------|
| 元数据输出上限 | 30KB | 用于 UI 流式展示，截断后加 `...` |
| 实际工具返回 | 完整 | Agent 收到完整输出 |

没有对命令输出做强制截断（Agent 自己可以读到完整输出），截断只影响 UI 元数据。

### 6.6 无 OS 级沙箱

**OpenCode 完全没有**：
- chroot / jail
- Docker / 容器
- seccomp / AppArmor / SELinux
- 虚拟机隔离

所有执行控制**完全依赖权限系统**。这是一个明确的设计取舍：面向开发者的工具，假设用户信任本地进程，不做 OS 级隔离。

---

## 七、文件操作工具的安全机制

### 7.1 路径安全（所有文件工具共用）

```python
# assertExternalDirectory()
def assert_external_directory(ctx, filepath):
    if instance.contains_path(filepath):
        return   # 项目内，无需检查

    # 项目外，需要询问
    parent_glob = os.path.join(os.path.dirname(filepath), "*")
    ctx.ask(
        permission = "external_directory",
        patterns   = [parent_glob],
        always     = [parent_glob],
    )
```

"包含"的判断基于路径相对关系，防止路径穿越（`../../etc/passwd`）。

### 7.2 edit 工具

```
执行前检查:
  ① oldString == newString → 报错（无变更）
  ② 目标是目录 → 报错
  ③ assertExternalDirectory()
  ④ 生成 diff（用于展示给用户）
  ⑤ ctx.ask({ permission:"edit", patterns:[相对路径], always:["*"] })

执行后:
  ⑥ 写入文件
  ⑦ 触发 LSP 诊断（可选）
  ⑧ 触发格式化（可选）
```

`always: ["*"]` 意味着用户一旦选择 "always" 批准任意一次 edit，后续所有 edit 都自动通过。

### 7.3 write 工具

与 edit 相同的权限检查流程，但：
- 使用同一个 `"edit"` 权限（不是独立的 `"write"` 权限）
- 会先读取已有内容生成 diff 展示给用户（即使是覆写）

### 7.4 read 工具

```
执行前:
  ctx.ask({ permission:"read", patterns:[filepath], always:["*"] })

输出限制:
  默认最多 2000 行
  单行最多 2000 字符
  总量最多 50KB
  支持 offset 参数分段读取
```

`.env` 文件的限制**不在 read 工具里**，而在全局默认规则里：
```
read.*.env      → ask   （每次都要问）
read.*.env.*    → ask   （每次都要问）
read.*.env.example → allow （无需问）
```

---

## 八、权限系统完整数据流

```
工具调用 ctx.ask({ permission, patterns, always, metadata })
    ↓
Permission.ask():
    for each pattern in patterns:
        rule = evaluate(permission, pattern, agent_ruleset, session_approved)
        ├── action == "deny"  → 抛 DeniedError，工具终止
        ├── action == "allow" → 继续下一个 pattern
        └── action == "ask"   → 进入挂起队列，等待用户

    ← 等待用户响应 →

    reply == "reject":
        抛 RejectedError
        取消 session 内所有 pending 请求
        processor.blocked = true → loop 返回 "stop"

    reply == "once":
        Deferred.succeed()  工具继续执行

    reply == "always":
        Deferred.succeed()  工具继续执行
        for pattern in request.always:
            session_approved.append({ permission, pattern, action:"allow" })
        回溯检查 pending 中可被新规则覆盖的请求，自动批准
```

---

## 九、对我们系统的设计建议

### 9.1 权限规则结构：完全采纳

```python
@dataclass
class Rule:
    permission: str   # "bash" | "edit" | "read" | "git" | "*"
    pattern:    str   # 资源路径或命令字符串，支持通配符
    action:     str   # "allow" | "deny" | "ask"

def evaluate(permission: str, pattern: str, *rulesets: list[Rule]) -> Rule:
    rules = [r for rs in rulesets for r in rs]
    match = None
    for rule in rules:          # 等价于 findLast
        if (wildcard_match(permission, rule.permission) and
            wildcard_match(pattern, rule.pattern)):
            match = rule
    return match or Rule("*", "*", "ask")
```

### 9.2 嵌入式 C 场景的默认规则建议

```python
DEFAULT_RULES = [
    # 基础：全允许
    Rule("*",    "*",           "allow"),

    # 文件读取：敏感配置需确认
    Rule("read", "*.key",       "ask"),
    Rule("read", "*.pem",       "ask"),
    Rule("read", "*.p12",       "ask"),

    # 编辑：项目外需确认
    Rule("external_directory", "*", "ask"),

    # 危险 bash 命令：需确认
    Rule("bash", "rm *",         "ask"),
    Rule("bash", "rm -rf *",     "deny"),  # 直接禁止递归删除
    Rule("bash", "git reset *",  "ask"),
    Rule("bash", "git clean *",  "ask"),
    Rule("bash", "git push *",   "ask"),   # 推送需确认

    # 编译/测试：直接允许（高频，不需每次确认）
    Rule("bash", "make *",       "allow"),
    Rule("bash", "gcc *",        "allow"),
    Rule("bash", "arm-none-eabi-gcc *", "allow"),
    Rule("bash", "openocd *",    "allow"),
]
```

### 9.3 进程管理：采纳 Windows 方案

Windows 7 下：
```python
import subprocess

def kill_process_tree(pid: int):
    subprocess.run(
        ["taskkill", "/pid", str(pid), "/f", "/t"],
        capture_output=True
    )
```

超时默认 **5 分钟**（嵌入式编译可能较慢），编译任务可配置更长。

### 9.4 不需要 OS 级沙箱

与 OpenCode 相同的取舍：内网隔离环境 + 本地开发者使用，权限系统足够，OS 级沙箱增加复杂度而无必要。

### 9.5 "always" 机制：简化实现

OpenCode 的 `always` 实现较复杂（回溯批准、patterns vs always 分离）。我们可以简化：

```python
# 简化版：always 就是把规则写入 session 级规则集
def handle_always_reply(permission: str, pattern: str, session_rules: list):
    session_rules.append(Rule(permission, pattern, "allow"))
    # 不做回溯，下次遇到相同请求直接通过即可
```

不做回溯不影响功能，只是已挂起的同类请求需要用户再批准一次，可接受。
