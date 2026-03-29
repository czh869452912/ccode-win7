# EmbedAgent Permission Model（Phase 5）

> 更新日期：2026-03-28（规则细化版）
> 适用阶段：Phase 5 权限模型

---

## 1. 文档目标

记录当前已经落地的权限控制策略、规则文件格式，以及 CLI 如何向用户请求批准。

本版本已经覆盖：

- 文件写入确认
- 命令与工具链执行确认
- allow / ask / deny 三值规则
- 用户拒绝后的结构化 Observation

---

## 2. 当前策略

### 2.1 默认允许

以下工具默认直接允许：

- `read_file`
- `list_files`
- `search_text`
- `ask_user`
- `git_status`
- `git_diff`
- `git_log`
- `report_quality`
- `switch_mode`

说明：

- `switch_mode` 虽然默认安全，但只会在 `orchestra` 模式暴露
- `ask_user` 属于用户交互，不属于权限审批链路

### 2.2 默认需要确认

以下工具在没有命中显式 allow 规则、且未开启自动批准时，会触发权限确认：

- `write_file`
- `edit_file`
- `run_command`
- `compile_project`
- `run_tests`
- `run_clang_tidy`
- `run_clang_analyzer`
- `collect_coverage`

### 2.3 规则优先于默认策略

当前权限判断顺序是：

1. 先匹配权限规则文件
2. 若命中 `allow` / `ask` / `deny`，以规则结果为准
3. 若未命中规则，再回退到默认工具分类策略

这意味着：

- 即使启用了 `--approve-commands`，命中 `deny` 规则的命令仍会被拒绝
- 即使某类操作通常会自动放行，也可以通过 `ask` 规则强制确认

---

## 3. 规则文件

默认规则文件路径：

- `.embedagent/permission-rules.json`

也可以通过 CLI 的 `--permission-rules` 显式指定。

### 3.1 规则格式

```json
{
  "schema_version": 1,
  "rules": [
    {
      "decision": "deny",
      "category": "write",
      "tool_names": ["edit_file"],
      "path_globs": ["README.md"],
      "reason": "README 不允许被自动修改。"
    },
    {
      "decision": "allow",
      "category": "write",
      "tool_names": ["edit_file"],
      "path_globs": ["src/*.py", "src/**/*.py"],
      "reason": "允许修改源码目录。"
    },
    {
      "decision": "ask",
      "category": "command",
      "tool_names": ["run_command"],
      "command_patterns": ["python"],
      "reason": "执行 Python 命令需要人工确认。"
    }
  ]
}
```

### 3.2 当前支持字段

- `decision`: `allow` / `ask` / `deny`
- `category`: `write` / `command` / `safe` / `other`
- `tool_names`: 工具名列表
- `path_globs`: 路径 glob 列表
- `cwd_globs`: 工作目录 glob 列表
- `command_patterns`: 命令正则列表
- `reason`: 命中规则后的提示文本

规则按文件顺序匹配，命中第一条即停止。

---

## 4. CLI 控制项

当前 CLI 支持：

- `--approve-all`
- `--approve-writes`
- `--approve-commands`
- `--permission-rules`

若未使用自动批准参数，且命中了 `ask` 或默认确认路径，CLI 会在执行前提示用户确认。

---

## 5. 拒绝时的行为

当前有两类拒绝：

### 5.1 规则拒绝（deny）

- 不再询问用户
- Loop 返回失败 Observation
- Observation 中包含 `permission_decision = "deny"`

### 5.2 用户拒绝（ask -> No）

- Loop 不会直接崩溃
- 系统返回失败 Observation
- Observation 中包含 `permission_decision = "ask"`、`permission_required`、`category`、`reason`、`details`

这样模型可以区分：

- 是规则层直接拒绝
- 还是本轮需要人工确认但用户没批准

### 5.3 用户输入（`ask_user`）

- `ask_user` 不走 permission approval
- 前端会单独进入 `waiting_user_input` 状态
- Loop 收到回答后会把用户选择写回 Observation；若该选项附带 mode，loop 会同步切到对应模式

---

## 6. 与模式系统的关系

模式边界仍然先于权限系统生效。

也就是说：

- 若当前 mode 根本不允许某工具或路径，系统会先被模式拦截
- 只有通过 mode 检查后，才会进入权限规则判断

这保证了：

- mode 负责职责边界
- permission 负责风险控制

---

## 7. 当前结论

Phase 5 的权限模型已经从“最小确认版”升级为“规则驱动版”：

- 高风险动作前确认
- 自动批准开关
- allow / ask / deny 三值规则
- 路径和命令模式匹配
- 拒绝后的结构化反馈

后续还可以继续补：

- 规则持久化编辑入口
- 更强的命令白名单 / 黑名单模板
- 规则命中审计与统计
