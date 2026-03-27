# EmbedAgent Harness State Machine（Phase 3）

> 更新日期：2026-03-28
> 适用阶段：Phase 3 模式系统 v1

---

## 1. 文档目标

记录当前最小模式切换机制的触发方式和循环行为，作为后续 Harness 扩展的起点。

本版本只覆盖：

- 用户显式 `/mode <name>`
- LLM 工具调用 `switch_mode(target)`

---

## 2. 当前入口

### 2.1 用户显式切换

规则：

1. 若用户消息以 `/mode <name>` 开头，CLI 先解析目标模式
2. 若命令后没有其他内容，直接返回“已切换到 `<name>` 模式”
3. 若命令后仍有正文，则以该模式作为本轮会话的初始模式继续执行

### 2.2 LLM 工具切换

规则：

1. 所有模式都自动附加 `switch_mode`
2. 当模型调用 `switch_mode(target)` 时，Loop 不把它交给 ToolRuntime
3. Loop 直接校验目标模式是否合法
4. 校验通过后，追加新的 mode system prompt，并继续下一轮

---

## 3. 当前循环

当前主循环行为：

```text
start
  -> choose initial mode
  -> append mode system prompt
  -> send messages + filtered tools to model
  -> if no action: finish
  -> if action == switch_mode: update mode + append new prompt + continue
  -> if action not allowed in current mode: return blocked observation + continue
  -> if action == edit_file and path not in writable_globs: return blocked observation + continue
  -> else execute tool in ToolRuntime + append observation + continue
```

---

## 4. 当前保护行为

### 4.1 工具过滤

- 模型只能看到当前模式允许的工具，加上 `switch_mode`

### 4.2 违规工具调用拦截

- 即使模型错误调用了当前模式不可用的工具，Loop 也会返回失败 Observation

### 4.3 写入范围拦截

- `edit_file` 额外检查目标路径是否匹配当前模式的 `writable_globs`

---

## 5. 当前结论

Phase 3 的最小 Harness 已具备：

- 模式注册
- 模式切换
- 工具过滤
- 写入边界约束

后续 Phase 5 需要在此基础上继续叠加：

- PermissionRequest
- Doom Loop Guard
- 更完整的上下文压缩与模式工件交接
