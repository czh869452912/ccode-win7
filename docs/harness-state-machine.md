# EmbedAgent Harness State Machine

> 更新日期：2026-03-29
> 适用阶段：Phase 3 模式系统 v2

---

## 1. 文档目标

记录当前模式切换机制的触发方式和循环行为，作为后续 Harness 扩展的起点。

本版本覆盖：

- 用户显式 `/mode <name>`
- `ask_user` 选项触发的模式切换
- 循环行为与保护机制

> **v2 变更**：`switch_mode` LLM 工具已移除。LLM 不再能主动切换模式。

---

## 2. 模式切换触发方式

### 2.1 用户显式切换（`/mode <name>`）

规则：

1. 用户消息以 `/mode <name>` 开头，CLI/TUI 先解析目标模式
2. 若命令后没有其他内容，直接返回"已切换到 `<name>` 模式"
3. 若命令后仍有正文，则以该模式作为本轮会话的初始模式继续执行
4. 未知模式名自动回落到 `explore`，不报错

### 2.2 ask_user 选项触发切换

规则：

1. 任何模式均可调用 `ask_user`（所有模式都包含该工具）
2. `ask_user` 的选项可携带 `option_N_mode` 字段（目标模式名）
3. 用户选择该选项后，Loop 自动：
   - 追加新模式的 system prompt 到会话
   - 更新 `current_mode`
   - 继续下一轮（context 和历史完整保留，不重置）
4. 这是 LLM 能"建议"模式切换的唯一合法路径——LLM 提问，用户决定

---

## 3. 当前循环

```text
start
  → choose initial mode (default: explore)
  → append mode system prompt
  → send messages + filtered tools to model
  → if no action: finish
  → if action == ask_user:
      → pause loop, request user input
      → if user selected an option with mode field: append new mode prompt + update current_mode
      → append ask_user observation + continue
  → if action not allowed in current mode: return blocked observation + continue
  → if action in (write_file, edit_file) and path not in writable_globs: return blocked observation + continue
  → else execute tool in ToolRuntime + append observation + continue
```

---

## 4. 保护行为

### 4.1 工具过滤

- 模型只能看到当前模式 `allowed_tools` 中列出的工具
- `switch_mode` 工具不存在；LLM 若试图调用，会得到 `mode_tool_blocked` 错误

### 4.2 违规工具调用拦截

- 即使模型错误调用了当前模式不可用的工具，Loop 也会返回失败 Observation，不执行

### 4.3 写入范围拦截

- `write_file` / `edit_file` 额外检查目标路径是否匹配当前模式的 `writable_globs`
- `explore` 和 `verify` 模式的 `writable_globs` 为空，等效于强制只读

### 4.4 未知模式回落

- `require_mode(slug)` 遇到未知 slug 时回落到 `explore`，并输出警告日志
- 防止恢复旧 session（含已删除模式名如 `orchestra`）时崩溃

---

## 5. 模式切换后的上下文行为

模式切换**不重置会话历史**：

- 原有 user/assistant/tool 消息全部保留
- 切换仅追加一条新的 system message（新模式的提示词）
- `ContextManager` 在上下文压缩时会保留最近的 system message（即当前模式）

---

## 6. 当前结论

Phase 3 v2 的 Harness 具备：

- 5 模式注册（config-driven，可扩展）
- 用户主导的模式切换（`/mode` + `ask_user` 选项）
- 工具过滤与写入边界约束
- 未知模式安全回落

后续 Phase 5+ 可继续叠加：

- 更完整的上下文压缩与模式工件交接
- Doom Loop Guard 增强
- 多步任务规划支持
