# EmbedAgent GUI + 架构综合评估与改进计划

## Context

用户报告多个严重问题，但要求评估不应局限于表面修复，而需从整体架构角度出发：agent loop 设计、工具与权限系统、提示词引导、前后端职责划分、GUI 页面架构和交互逻辑是否合理，以及如何朝最优方向演进。

---

## 第一层：架构根本问题（最高优先级）

这些是导致多个具体 bug 的深层原因，不解决这些，补丁会不断失效。

---

### A1：前端承担了不该承担的后端职责 ← 大多数 Bug 的根源

**问题**：`state-helpers.js` 的 `timelineFromEvents()` 在前端重建 timeline，`store.js` 维护流式状态机（`streamingAssistantId`, `streamingReasoningId`, `thinkingActive` 三个 ID），前端从原始事件流推断 turn 边界。

这导致：
- Reasoning 卡片合并 bug：前端重建逻辑有误
- 第二条消息续写到旧卡片：前端状态机竞态
- Turn 分组无法实现：前端无法可靠判断 turn 边界

**根本原因**：后端只发送原始事件流，将"组装成对话结构"的工作丢给前端。这是错误的职责划分。

**正确方向**：后端是对话状态的权威来源，应发送结构化的、已处理好的 timeline 数据。

**具体改动**：

① **引入显式 Turn 事件**（`inprocess_adapter.py`）：
- 新增 `turn_start` 事件（含 `turn_id`, `user_text`），在 `_run_turn` 开头发送
- 新增 `turn_end` 事件（含 `turn_id`, `final_text`, `termination_reason`），在 session_finished 前发送
- 所有后续事件（`tool_started`, `assistant_delta`, `reasoning_delta` 等）均携带 `turn_id`

② **后端 Timeline API 返回结构化数据**（`server.py`）：
`GET /api/sessions/{id}/timeline` 现在返回原始事件，应改为返回 Turn 列表：
```json
{
  "turns": [
    {
      "turn_id": "t1",
      "user_text": "...",
      "reasoning": "合并后的完整 reasoning 文本",
      "tool_calls": [{...}],
      "assistant_text": "...",
      "status": "completed"
    }
  ]
}
```
后端聚合 reasoning delta、配对 tool_start/finish，前端只负责渲染。

③ **简化前端流式状态机**（`store.js`）：
将三个 streaming ID 替换为单一 `activeBlock: { turn_id, kind, item_id } | null`。
类型：`"thinking" | "reasoning" | "text" | "tool"`。
- 进入新 turn（`turn_start`）→ 清零 `activeBlock`
- 任何 delta → 更新 `activeBlock`
- `turn_end` → 清零 `activeBlock`

**关键文件**：
- `src/embedagent/inprocess_adapter.py`（新增 turn 事件发送）
- `src/embedagent/frontend/gui/backend/server.py`（timeline API 改造）
- `webapp/src/store.js`（状态机简化）
- `webapp/src/state-helpers.js`（可大幅简化，主要逻辑移到后端）

---

### A2：Mode 系统设计缺陷——权限与工作流混用

**问题**：当前 Mode 同时承担两个职责：
1. **工作流阶段**：告诉 LLM "你现在在做什么"（探索/规格/实现/调试/验证）
2. **工具权限过滤**：控制哪些工具可用、哪些路径可写

两者混用导致以下问题：

**问题一：工具限制过于严格**
- `git_status`, `git_diff`, `git_log` 定义了但**不在任何模式的 `allowed_tools` 中**，agent 无法在任何模式下检查 git 状态
- `run_command` 只在 debug 模式，但 code 模式经常需要执行构建脚本
- `explore` 模式只有 5 个工具，连 search_text 的上下文行都没有

**问题二：模式切换流程过于复杂**
当前流程：agent 调用 `ask_user`（必须构造 UI 级别的选项 + `option_N_mode` 字段）→ 前端弹出交互面板 → 用户选择 → WebSocket 携带 `selected_mode` → 后端解析 → 触发模式切换。

这是 7 步流程，任何一步断裂（如 CallbackBridge 丢弃 `mode_changed` 事件）都导致模式切换失败。**这就是 Bug 5 的根因。**

**正确方向**：

① **分离 "工作流阶段" 与 "工具权限"**：
- 工具权限应有独立的、更细粒度的配置，与 mode 解耦
- Mode 只影响系统提示词（告知 LLM 当前任务上下文）和默认权限推荐
- 考虑以 `explore` 为基础权限集，允许其他模式叠加

② **引入独立的 `propose_mode_switch` 工具**替代 ask_user 里的 mode 参数：
```
工具：propose_mode_switch
参数：target_mode, reason
效果：向前端发送 mode_switch_proposal 事件，前端内联显示切换建议卡片
用户：点击确认/修改/忽略
后端：收到确认后调用 set_session_mode()
```
这将模式切换从 ask_user 的副功能提升为一等公民，流程变为 2 步，失效点减少。

③ **给 `code` 和 `debug` 模式添加 git 工具**：
```python
"code": {
    "allowed_tools": [...existing..., "git_status", "git_diff"],
}
```

**关键文件**：
- `src/embedagent/modes.py`（mode 定义、allowed_tools）
- `src/embedagent/interaction.py`（新增 propose_mode_switch 工具）
- `src/embedagent/loop.py`（_handle_propose_mode_switch）
- `webapp/src/components/Timeline.jsx`（模式切换建议卡片）

---

### A3：Permission 系统与 Mode 系统的用户认知冲突

**问题**：Mode 允许 `write_file`（工具在白名单中），但 PermissionPolicy 仍要求用户审批写操作。用户设置了 code 模式，期望 agent 能直接修改文件，却被权限弹窗打断，产生认知混乱。

系统提示词中有一句"模式不是权限系统；权限审批由运行时单独处理"——这是正确的架构描述，但用户和 LLM 都很难理解这种二元分离。

**正确方向**：

① **权限策略与模式绑定**：在模式配置中允许声明默认权限策略：
```python
"code": {
    "allowed_tools": [...],
    "writable_globs": [...],
    "default_permission_policy": {
        "auto_approve_writes": True,   # code 模式默认自动批写文件
        "auto_approve_commands": False  # 但命令仍需确认
    }
}
```

② **权限弹窗改为内联 Timeline 卡片**（高优先级，既改善 UX 又解决遮挡问题）：
将 `PermissionModal` 改为 timeline 内联 `kind: "permission"` 卡片，含：
- 操作描述（写哪个文件/执行什么命令）
- 批准/拒绝按钮
- "本次 session 记住选择"复选框
用户无需离开对话上下文即可审批。

---

### A4：Agent Loop 状态机不完整

**问题**：
1. **无法中途中断并提供新指示**：`cancel_session()` 只能终止，不能注入新消息。用户在 agent 执行途中想改变方向，只能等待完成或取消后重新输入。
2. **max_turns 不透明**：默认 8 轮，到达上限后 agent 停止，用户完全不知道发生了什么，也无法继续。
3. **loop_guard 对用户不可见**：连续失败 3 次被 guard 阻断后，agent 只是停止，没有解释。
4. **`cancel_session()` 缺少 `stop_event.set()`**：后端 cancel 只解除阻塞，loop 不会在当前工具调用后停止（Bug 4 的根因）。

**修复**：
- `inprocess_adapter.py` line 516：`cancel_session()` 加 `state.stop_event.set()`
- `session_finished` 事件的 payload 增加 `termination_reason` 和 `turns_used` 字段
- 前端收到 `termination_reason === "max_turns"` 时显示提示："Agent 已使用 8 轮，可继续对话"
- 前端收到 `termination_reason === "guard"` 时显示：连续失败原因（`loop_guard` 的最后一条错误信息）

---

## 第二层：具体 Bug 修复

以下是直接可实施的 bug 修复，部分是 A1-A4 架构改动的简化版本（过渡方案）。

### B1：第二条消息续写到旧卡片 ✅ Phase 1 已修复

**根因**：`local_user_message` reducer 不重置 `streamingAssistantId`。  
**文件**：`webapp/src/store.js`  
**修复**：`local_user_message` case 加 `streamingAssistantId: "", streamingReasoningId: "", thinkingActive: false`，并将现有 `streaming: true` items 设为 `streaming: false`。同时 `App.jsx` sendMessage() 开头加 `dispatch({ type: "stream_completed" })` 作为屏障。

### B2：Reasoning 卡片碎片化 ✅ Phase 2 已修复

**根因**：`state-helpers.js` 的 `timelineFromEvents()` 为每个 reasoning_delta 创建独立卡片。  
**文件**：`webapp/src/state-helpers.js`  
**修复**：用局部变量 `currentReasoningContent` 聚合连续 reasoning delta，遇到非 reasoning 事件时 flush 为单张卡片。

### B3：停止按钮缺失 ✅ Phase 1 已修复

**根因**：后端 `cancel_session()` 未调用 `stop_event.set()`；前端无 UI 入口。  
**修复**：
- 后端：`cancel_session()` 首行加 `state.stop_event.set()`
- 前端 `App.jsx`：新增 `cancelSession()` 调用 `POST /api/sessions/{id}/cancel`
- `Composer.jsx`：接受 `isRunning` + `onStop` props，`isRunning` 时显示 Stop 按钮，textarea 禁用

### B4：模式切换不生效 ✅ Phase 1 已修复

**根因**（双重）：
1. `core/adapter.py` 的 `CallbackBridge.emit` 无 `mode_changed` case，事件被丢弃
2. `inprocess_adapter.py` 从 summary 读 `current_mode` 覆盖了刚设置的新模式

**修复**：
- `CallbackBridge.emit` 加 `mode_changed` case
- 删除 `inprocess_adapter.py` 中 summary 覆盖 `current_mode` 的代码行

### B5：配色可读性 ✅ Phase 1 已修复

**文件**：`webapp/src/styles.css`  
**修复**：`.reasoning-body` 改为 `var(--ink)`，`.tool-name-badge` 固定颜色，`.option-card` 不透明背景，`.mode` 徽章加边框

---

## 第三层：提示词与工具工程问题

### P1：系统提示词信息不足 ⬜ Phase 3 待实施

当前提示词只有：模式名、模式描述、allowed_tools、writable_globs。缺少：
- 项目类型（嵌入式 C？Python 库？）
- 可用的构建命令（cmake、make、pytest？）
- 代码风格约定
- 已知约束（Windows 7 兼容、离线环境等）

**改进**：`build_system_prompt()` 从 `.embedagent/context.md` 加载项目特定上下文。

### P2：ask_user 工具职责过重 ⬜ Phase 3 待实施（通过 A2 解决）

ask_user 同时承担：用户确认、模式切换请求、一般性问题。建议分拆：
- `ask_user`：保留，只用于需要用户决策的问题
- `propose_mode_switch`：新增，专门用于请求模式切换（见 A2）

### P3：工具白名单缺失关键工具 ✅ Phase 1 已修复

- `explore` 模式加：`git_status`, `git_log`
- `code` 模式加：`git_status`, `git_diff`
- `debug` 模式加：`git_status`, `git_diff`, `git_log`

---

## 第四层：GUI 页面架构与交互设计

### G1：对话结构——缺少 Turn 边界 ✅ Phase 2 已实施

**方案**：在 `Timeline.jsx` 中按 turn 分组渲染（`groupByTurn()`），Turn Group 之间细线分隔，工具调用默认折叠（当前 turn 展开）。

### G2：ask_user 回答面板位置错误 ✅ Phase 2 已实施

**方案**：ask_user 触发 `kind: "user_input"` timeline 卡片，内联显示问题和选项按钮。

### G3：模式指示器 UX ✅ Phase 3 已实施

**方案**：
- 每个模式配色：explore=蓝, spec=紫, code=绿, debug=橙, verify=青
- 模式切换时在 timeline 插入 `kind: "system"` 卡片
- 合并 header 中的 badge + select 为单一可点击控件

### G4：缺少状态透明度 ✅ Phase 3 已实施

**方案**：
- `<StatusBar>` 显示 Turn N/max · 模式名 · 连接状态
- `termination_reason === "max_turns"` 时显示内联提示卡片
- `termination_reason === "guard"` 时显示失败摘要

---

## 实施优先级与进度

### Phase 1 ✅ 已完成（commit `0e6e3d7`）
| # | 内容 | 状态 |
|---|------|------|
| B1 | 流式续写旧卡片 | ✅ |
| B3 | 停止按钮 + cancel_session fix | ✅ |
| B4 | 模式切换不生效 | ✅ |
| P3 | 工具白名单修复（git 工具） | ✅ |
| B5 | 配色可读性 | ✅ |

### Phase 2 ✅ 已完成（commit `732c60b`）
| # | 内容 | 状态 |
|---|------|------|
| A1-基础 | 后端发送 turn_start/turn_end 事件 | ✅ |
| A1-前端 | 前端按 turn_id 分组渲染（Turn Group） | ✅ |
| B2 | Reasoning 聚合 | ✅ |
| A4 | termination_reason 透明化 | ✅ |
| G2 | ask_user 内联卡片 | ✅ |

### Phase 3 — 深层架构重构
| # | 内容 | 状态 |
|---|------|------|
| G3/G4 | 模式配色 + 状态栏 | ✅ commit `ceb2f97` |
| A3 | 权限内联卡片 | ✅ commit `ceb2f97` |
| A2 | propose_mode_switch 工具 | ⬜ 待实施 |
| P1 | 系统提示词扩充（context.md） | ⬜ 待实施 |
| A1-完整 | 后端 timeline API 结构化 Turn 数据 | ⬜ 待实施 |

---

## 关键文件路径

| 文件 | Phase | 变更方向 |
|------|-------|---------|
| `src/embedagent/inprocess_adapter.py` | 1+2+3 | cancel fix, turn 事件, termination_reason |
| `src/embedagent/core/adapter.py` | 1 | CallbackBridge 加 mode_changed case |
| `src/embedagent/modes.py` | 1+3 | 工具白名单, 权限策略绑定 |
| `src/embedagent/interaction.py` | 3 | propose_mode_switch 工具 |
| `src/embedagent/loop.py` | 3 | _handle_propose_mode_switch |
| `src/embedagent/frontend/gui/backend/server.py` | 2+3 | timeline API 结构化 |
| `webapp/src/store.js` | 1+2 | 状态机简化, turn_id |
| `webapp/src/state-helpers.js` | 2 | 简化（后端承担聚合） |
| `webapp/src/App.jsx` | 1+2+3 | cancelSession, turn 事件处理, StatusBar |
| `webapp/src/components/Timeline.jsx` | 2+3 | Turn Group, inline cards, PermissionCard |
| `webapp/src/components/Composer.jsx` | 1 | Stop 按钮 |
| `webapp/src/styles.css` | 1+3 | 配色修复, 模式配色, permission-card |

---

## 验证方式

**Phase 1 验证**：
1. 发送第一条消息，等待完成，立即发第二条 → 第二条回答出现在新卡片
2. 启动长任务，点击 Stop → agent 在当前轮结束后停止（不是卡死）
3. explore 模式，agent 提议切到 code 模式，用户选择 → header 徽章变绿，后续写文件成功
4. 刷新页面重载历史 → reasoning 显示为单张折叠卡片
5. DevTools 检查 `.reasoning-body` 颜色对比度 ≥ 4.5:1

**Phase 2 验证**：
6. 多轮对话（含工具调用）→ 每轮有明确视觉分隔，工具默认折叠
7. agent 调用 ask_user → 问题和选项出现在 timeline 而非 Inspector
8. agent 命中 max_turns → timeline 出现"已达轮次上限"提示卡片

**Phase 3 验证**：
9. agent 需要切换模式 → 调用 propose_mode_switch → timeline 出现建议卡片 → 确认后模式立即更新，无任何中间失败点
10. code 模式 agent 执行写文件 → 权限内联卡片出现在 timeline，无遮挡式 modal
11. 勾选"记住本 session" → 同类型后续权限自动批准
