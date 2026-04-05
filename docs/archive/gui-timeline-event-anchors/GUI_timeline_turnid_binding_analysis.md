# GUI Timeline 中 turnId/stepId 绑定缺失的深入分析

## 1. 执行摘要

本分析针对 GUI 时间线（Timeline）组件中出现的“卡片错误堆叠/游离”现象进行代码审查。根本原因是：**多个后端事件在生成 WebSocket 消息时未携带 `turn_id` / `step_id`，前端接收后也未做修正或补全，导致 `projector.js` 的分组逻辑将每个事件孤立为独立的 fallback group。**

这与截图中大量 "上下文已压缩" 卡片、以及 `/命令` 结果经常跑到错误位置（或单独成组）的问题同源。

---

## 2. 受影响的消息类型总览

| 消息类型 | 后端含 turn_id/step_id？ | 前端补全？ | 对 Timeline 的影响 |
|---|---|---|---|
| `CONTEXT_COMPACTED` | ❌ 无 | ❌ 未补 | **高** — 每个卡片孤立成群，造成视觉堆叠 |
| `COMMAND_RESULT` (/命令) | ❌ 无（协议层缺失 + 发送时机在 turn 之前） | ⚠️ 部分（依赖 `activeTurnId`） | **中** — 实时流可能绑定到当前 turn；但从事件日志恢复时完全游离，落入 `sessionFallbackItems` |
| `SESSION_ERROR` | ❌ 无 | ❌ 未补 | **中** — 错误卡片孤立为独立 group 或 trailing item，无法与出错的 step 对齐 |
| `PERMISSION_REQUEST` | ⚠️ 后端 event payload 有，但协议 dataclass 缺失 | ❌ 未补 | **低** — Timeline 不直接渲染该类型，但 Inspector 中缺少 turn/step 上下文；event log 路径可间接保留 |
| `USER_INPUT_REQUEST` | ⚠️ 后端 event payload 有，但协议 dataclass 缺失 | ❌ 未补 | **低** — 同上 |
| `PLAN_UPDATED` | ❌ 无 | N/A | **无** — 不写入 Timeline，仅影响 Inspector |
| `ASSISTANT_DELTA` | ✅ 有 | ✅ 已用 | 正常 |
| `REASONING_DELTA` | ✅ 有 | ✅ 已用 | 正常 |
| `TOOL_START/FINISH` | ✅ 有 | ✅ 已用 | 正常 |

---

## 3. 各消息类型的详细链路分析

### 3.1 CONTEXT_COMPACTED（“上下文已压缩”大量堆叠的根源）

#### 3.1.1 后端触发逻辑过度宽松

**文件：** `src/embedagent/context.py:522`

```python
compacted = bool(old_turns) or bool(reduced_tool_messages) or (used_chars < chars_before)
```

- `old_turns` 在常规上下文构建中**总是非空**（只要会话长度超过 `max_recent_turns`），因此 `compacted` 经常被置为 `True`。
- 这导致**几乎每个 Step** 都会触发一次 `context_compacted` 事件。

**文件：** `src/embedagent/inprocess_adapter.py:2107`

```python
self._emit_with_snapshot(event_handler, "context_compacted", state, {
    "recent_turns": ...,
    "summarized_turns": ...,
    "approx_tokens_after": ...,
    "analysis": ...,
})
```

**问题：** payload 中**没有** `turn_id` 或 `step_id`。

#### 3.1.2 协议层丢失了 turn/step 绑定

**文件：** `src/embedagent/core/adapter.py:188-201`

```python
elif event_name == "context_compacted":
    msg = Message(
        id=str(uuid.uuid4()),
        type=MessageType.CONTEXT_COMPACTED,
        content=f"Context compacted: {stats} turns kept",
        metadata={...},  # 无 turn_id / step_id
    )
    self.frontend.on_message(msg)
```

**文件：** `src/embedagent/frontend/gui/backend/server.py:202-211`

```python
def on_message(self, message: Message) -> None:
    self._dispatch_message({
        "type": "message",
        "data": {
            "id": message.id,
            "type": message.type.name,   # -> "CONTEXT_COMPACTED"
            "content": message.content,
            "metadata": message.metadata   # 仍无 turn_id / step_id
        }
    })
```

#### 3.1.3 前端接收后未补全

**文件：** `src/embedagent/frontend/gui/webapp/src/App.jsx:755-764`

```javascript
if (type === "message" && data.type === "CONTEXT_COMPACTED") {
  dispatch({
    type: "context_compacted",
    id: data.id || makeEventId("context"),
    content: data.content || "",
    recentTurns: metadata.recent_turns,
    summarizedTurns: metadata.summarized_turns,
    approxTokensAfter: metadata.approx_tokens_after,
    // ⚠️ 缺失 turnId / stepId / stepIndex
  });
}
```

#### 3.1.4 Store & Timeline 投影导致每个卡片独立成群

**文件：** `src/embedagent/frontend/gui/webapp/src/store.js:449-461`

```javascript
case "context_compacted":
  timeline: state.timeline.concat({
    id: action.id || makeEventId("context"),
    kind: "compact",
    content: action.content || "",
    recentTurns: action.recentTurns,
    summarizedTurns: action.summarizedTurns,
    approxTokensAfter: action.approxTokensAfter,
    ...rawProjectionMeta(),
    // ⚠️ 无 turnId / stepId
  }),
```

**文件：** `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js:135-143`

```javascript
function getTurnGroup(groups, turnMap, item) {
  const fallbackId = item.kind === "user" ? item.id : `session-${item.id}`;
  const key = item.turnId || fallbackId;
  if (!turnMap.has(key)) {
    const group = createTurnGroup(key);
    turnMap.set(key, group);
    groups.push(group);
  }
  return turnMap.get(key);
}
```

- 由于 `kind === "compact"` 且没有 `turnId`，`key` 变成 `session-{唯一随机id}`。
- **每个 compact 卡片都会创建自己独有的 turn group**。
- 在 `projectTurnGroups` 中它们会被放入 `group.trailingTurnItems`（因为 steps 长度可能 >0）或 `group.leadingSystemItems`（如果 steps=0）。
- 最终渲染为多个紧挨的 `<div class="turn-group">`，每个只含一个 `CompactCard`，形成截图中的“压缩墙”。

---

### 3.2 COMMAND_RESULT（/命令结果游离/错位）

#### 3.2.1 slash 命令在 turn 生成之前执行，注定无 turn_id

**文件：** `src/embedagent/inprocess_adapter.py:907-956`（`submit_user_message`）

```python
dispatch = self._dispatch_input(state, text, event_handler, permission_resolver)
if dispatch.get("handled") and not dispatch.get("continue_with_text"):
    return self.get_session_snapshot(session_id)
# ... 随后才调用 _run_turn / _run_turn_v2（在此处生成 turn_id）
```

- `_dispatch_input` 负责识别并执行 `/clear`、`/diff`、`/review`、`/workspace`、`/mode` 等 slash 命令。
- `turn_id` 是在 `_run_turn_v2` 内部调用 `_generate_turn_id()` 时才产生的，因此**所有 slash 命令在触发时都不存在当前 turn 上下文**。

#### 3.2.2 后端 emit 时不含 turn/step，且协议 dataclass 同样缺失

**文件：** `src/embedagent/inprocess_adapter.py:1829-1841`

```python
def _emit_command_result(...):
    payload = {
        "command_name": result.command_name,
        "success": result.success,
        "message": result.message,
        "data": result.data,
        # ⚠️ 无 turn_id / step_id（因为 3.2.1 的原因，此时还没有）
    }
    self._emit_with_snapshot(event_handler, "command_result", state, payload)
```

此外，**协议层 dataclass 也未定义这些字段**：

**文件：** `src/embedagent/protocol/__init__.py:95-102`

```python
@dataclass
class CommandResult:
    command_name: str
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
```

- 即使未来想补传 `turn_id`，`CommandResult` 类本身也缺少字段，无法通过 `FrontendCallbacks.on_command_result` 接口传递。

#### 3.2.3 协议层与 WebSocket 层继续丢失

**文件：** `src/embedagent/core/adapter.py:150-158`

```python
elif event_name == "command_result":
    self.frontend.on_command_result(
        CommandResult(..., data=payload.get("data", {}))
    )
```

**文件：** `src/embedagent/frontend/gui/backend/server.py:358-367`

```python
def on_command_result(self, result: CommandResult) -> None:
    self._dispatch_message({
        "type": "command_result",
        "data": {
            "command_name": result.command_name,
            "success": result.success,
            "message": result.message,
            "data": result.data,
            # ⚠️ 仍无 turn_id / step_id
        }
    })
```

#### 3.2.4 前端实时处理：依赖 activeTurnId，存在竞争

**文件：** `src/embedagent/frontend/gui/webapp/src/App.jsx:607-614`

```javascript
dispatch({
  type: "command_result",
  id: makeEventId("cmd"),
  commandName: data.command_name || "",
  success: Boolean(data.success),
  message: data.message || "",
  data: data.data || {},
  // ⚠️ 未显式传 turnId
});
```

**文件：** `src/embedagent/frontend/gui/webapp/src/store.js:468-486`

```javascript
case "command_result": {
  const turnId = resolveTimelineAnchor({
    explicitTurnId: action.turnId || "",
    activeTurnId: state.activeTurnId,
    timeline: state.timeline,
  });
  ...
  state.timeline.concat({
    kind: "command_result",
    turnId,   // <- 依赖 state.activeTurnId
    ...
  })
}
```

- 在**实时 WebSocket 流**中，如果命令恰好在当前 turn 运行中触发，`activeTurnId` 大概率正确，`command_result` 会绑定到当前 turn。
- 但如果命令是在 session 恢复、或跨 step 的异步收尾中触发，`activeTurnId` 可能已经变化，导致**绑定到错误的 turn**。

#### 3.2.5 从事件日志恢复时：完全游离

**文件：** `src/embedagent/frontend/gui/webapp/src/state-helpers.js:243-253`

```javascript
} else if (eventName === "command_result") {
  flushReasoning();
  items.push({
    id: record.event_id,
    kind: "command_result",
    commandName: payload.command_name || "",
    content: payload.message || "",
    data: payload.data || {},
    success: Boolean(payload.success),
    projectionSource: "raw_events",
    // ⚠️ 无 turnId
  });
}
```

- 当用户刷新页面、或后端需要 `reload_required` 重新加载 Timeline 时，事件从 `timeline.jsonl` 被读取。
- 由于原始 event 没有 `turn_id`，`timelineFromEvents` 生成的 `command_result` item 也没有 `turnId`。

**文件：** `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js:177-179`

```javascript
if (item.kind === "command_result" && !item.turnId) {
  group.sessionFallbackItems.push({ ...item, kind: "command_result_fallback" });
  continue;
}
```

- 无 `turnId` 的 `command_result` 被降级为 `command_result_fallback`，塞入 `sessionFallbackItems`。
- 在 `TurnGroup` 中，`sessionFallbackItems` 被渲染在 turn 的最后方（像补丁一样挂在 session 底部），**无法与发出该命令的具体 turn 对齐**。

---

### 3.3 SESSION_ERROR（错误消息游离）

#### 3.3.1 后端触发

**文件：** `src/embedagent/inprocess_adapter.py:2180`

```python
self._emit_with_snapshot(event_handler, "session_error", state, {
    "error": str(exc), "phase": "loop"
    # 无 turn_id / step_id
})
```

#### 3.3.2 协议层转换

**文件：** `src/embedagent/core/adapter.py:118-127`

```python
elif event_name == "session_error":
    msg = Message(
        id=str(uuid.uuid4()),
        type=MessageType.ERROR,
        content=payload.get("error", "Unknown error")
    )
    self.frontend.on_message(msg)
```

无 `turn_id` / `step_id`。

#### 3.3.3 前端处理

**文件：** `src/embedagent/frontend/gui/webapp/src/App.jsx:746-751`

```javascript
if (type === "message" && data.type === "ERROR") {
  dispatch({
    type: "session_error",
    id: data.id || makeEventId("error"),
    error: data.content || "Error",
    // 无 turnId
  });
}
```

**文件：** `src/embedagent/frontend/gui/webapp/src/store.js:435-448`

生成的 timeline item 为 `kind: "system"`，**无 turnId**。

#### 3.3.4 Timeline 投影结果

- `projectTurnGroups` 会把无 `turnId` 的 `system` 项放入 `group.trailingTurnItems`（若当前 group 已有 step）或 `leadingSystemItems`（若 group 为空）。
- 由于没有 `turnId`，它会被附加到**当前正在处理的那个 group**（按遍历顺序通常是最后一个 group）。
- 如果 session 中有多个 turn，错误消息可能挂在最后一个 turn 上，而不是真正出错的那个 turn/step。

---

### 3.4 PERMISSION_REQUEST（协议 dataclass 缺失 turn_id/step_id）

#### 3.4.1 后端 event payload 实际包含 turn/step

**文件：** `src/embedagent/inprocess_adapter.py:2111`

```python
self._emit_with_snapshot(event_handler, "permission_required", state, {
    "permission": ticket.to_dict(),
    "turn_id": turn_id,
    "step_id": current_step["step_id"],
    "step_index": current_step["step_index"],
})
```

→ 后端 `_emit_with_snapshot` 的 payload **确实包含** `turn_id` / `step_id` / `step_index`。

#### 3.4.2 协议层 dataclass 截断了这些字段

**文件：** `src/embedagent/core/adapter.py`

`core/adapter.py` 在收到 `permission_required` 事件后，会将其转换为 `PermissionRequest` dataclass，再调用 `self.frontend.on_permission_request(request)`。

**文件：** `src/embedagent/protocol/__init__.py:76-83`

```python
@dataclass
class PermissionRequest:
    permission_id: str
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
```

- `PermissionRequest` **没有** `turn_id`、`step_id`、`step_index` 字段。
- 因此 `core/adapter.py` 在构建该对象时，无论原始 payload 里有什么，这些字段都会被**丢弃**。

#### 3.4.3 GUI Server 只能转发它收到的内容

**文件：** `src/embedagent/frontend/gui/backend/server.py:269-283`

```python
def on_permission_request(self, request: PermissionRequest) -> bool:
    ...
    queued = self._dispatch_message({
        "type": "permission_request",
        "data": {
            "permission_id": request.permission_id,
            "tool_name": request.tool_name,
            "category": request.category,
            "reason": request.reason,
            "details": request.details
            # 无 turn_id / step_id（因为 request 对象本身就没有）
        }
    })
```

**结果：**
- 直接 WebSocket 弹窗路径上，前端永远收不到 `turn_id` / `step_id`，Inspector 里无法显示“第 X 步”。
- **补救路径：** 同一事件同时会通过 `_emit_with_snapshot` -> `_emit` -> `timelineStore.append_event`，完整 payload（含 `turn_id`）被保留在 `timeline.jsonl` 中。在 `session_event` 重放机制中，`build_session_event` 保留了完整 payload，因此 Timeline 的 `projectEventLogTimeline` **最终**能间接拿到正确的 `turnId` / `stepId`。

---

### 3.5 USER_INPUT_REQUEST（与 permission 同样的协议层缺失）

**文件：** `src/embedagent/inprocess_adapter.py:2123`

```python
self._emit_with_snapshot(event_handler, "user_input_required", state, {
    "user_input": ticket.to_dict(),
    "turn_id": turn_id,
    "step_id": current_step["step_id"],
    "step_index": current_step["step_index"],
})
```

**文件：** `src/embedagent/protocol/__init__.py:86-92`

```python
@dataclass
class UserInputRequest:
    request_id: str
    tool_name: str
    question: str
    options: List[Dict[str, Any]] = field(default_factory=list)
```

- 与 `PermissionRequest` 完全一致：`UserInputRequest` dataclass 缺少 `turn_id` / `step_id` 字段。

**文件：** `src/embedagent/frontend/gui/backend/server.py:292-305`

```python
def on_user_input_request(self, request: UserInputRequest) -> ...:
    queued = self._dispatch_message({
        "type": "user_input_request",
        "data": {
            "request_id": request.request_id,
            "tool_name": request.tool_name,
            "question": request.question,
            "options": request.options
            # 无 turn_id / step_id
        }
    })
```

影响与 `permission_request` 相同：直接弹窗路径丢失了 step 上下文，但 event log 路径补回了。

---

## 4. 问题的共同模式

以上所有问题可归为 **三类系统性的 turnId/stepId 缺失**：

### 模式 A：后端本来就没传
- `CONTEXT_COMPACTED`
- `SESSION_ERROR`

### 模式 B：协议层 dataclass 字段缺失，导致有数据也传不过去
- `PERMISSION_REQUEST`（`PermissionRequest` 没有 `turn_id`/`step_id`）
- `USER_INPUT_REQUEST`（`UserInputRequest` 没有 `turn_id`/`step_id`）
- `COMMAND_RESULT`（`CommandResult` 没有 `turn_id`/`step_id`，且 slash 命令发送时还没生成 `turn_id`）

### 模式 C：前端 event-log 恢复路径未补齐
- `command_result` 从 `timelineFromEvents` 恢复时无 `turnId`
- `context_compacted` 从 `timelineFromEvents` 恢复时无 `turnId`
- `session_error` 从 `timelineFromEvents` 恢复时无 `turnId`

---

## 5. 影响的临床表现

| 现象 | 直接原因 |
|---|---|
| 大量“上下文已压缩”卡片竖直堆叠 | 模式 A + C：每个 `compact` 无 `turnId`，被 `projector.js` 分配为独立 group |
| `/diff`、`/review` 命令结果跑到底部或悬浮在错误 turn | 模式 B + C：`command_result` 依赖 `activeTurnId` 或降级为 `sessionFallbackItems` |
| 错误消息无法与出错的 step 对齐 | 模式 A + C：`session_error` 无 `turnId`，只能挂在遍历顺序最后的 group |
| Inspector 中权限请求缺少“第 X 步”上下文 | 模式 B：协议 dataclass 截断了 `step_id`，直接 WebSocket 路径无法传递 |

---

## 6. 修复方向建议

### 6.1 后端：统一在 emit 时注入当前 turn/step 坐标

在 `inprocess_adapter.py` 中，以下函数应在 payload 中自动加入 `turn_id`、`step_id`、`step_index`：

- `_emit_with_snapshot(..., "context_compacted", ...)` 中的 payload
- `_emit_with_snapshot(..., "session_error", ...)` 中的 payload

**推荐做法：** 在 `submit_user_message` / `_run_session_loop` 的局部闭包中，`turn_id` 和 `current_step` 已经可用。可直接注入：

```python
payload.setdefault("turn_id", turn_id)
payload.setdefault("step_id", current_step.get("step_id", ""))
payload.setdefault("step_index", current_step.get("step_index", 0))
```

### 6.2 后端：为 slash 命令补充 turn 上下文（架构调整）

`COMMAND_RESULT` 的特殊性在于 slash 命令在 `_dispatch_input` 阶段执行，此时 `turn_id` 尚未生成。

**可选方案：**
1. **延迟发送：** 将 `command_result` 暂存，等 `_run_turn_v2` 生成 `turn_id` 后再关联并发送。
2. **预生成 turn_id：** 在 `_dispatch_input` 之前就调用 `_generate_turn_id()`，使整个 user message 生命周期共享同一个 `turn_id`。
3. **仅绑定到 session：** 如果不追求精确到 turn，至少绑定到 `session_id`，前端作为 `sessionFallbackItems` 展示。

### 6.3 后端：减少不必要的 `context_compacted` 触发

**文件：** `src/embedagent/context.py:522`

当前 `compacted = bool(old_turns) or ...` 导致常规摘要也被视为 compaction 事件。

建议修改：只有**真正 forced/reactive** compact（如 `force_compact=True` 或 `hard_trimmed=True`）时才让 `ContextBuildResult.compacted = True`，或在前端协议中区分“常规摘要”和“压缩通知”。

### 6.4 协议层：补全 dataclass 缺失字段

**文件：** `src/embedagent/protocol/__init__.py`

为 `PermissionRequest`、`UserInputRequest`、`CommandResult` 增加字段：

```python
@dataclass
class PermissionRequest:
    permission_id: str
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0
```

同时更新 `core/adapter.py` 中构建这些对象时的字段映射，以及 `server.py` 的 WebSocket 转发逻辑。

### 6.5 前端：事件日志恢复路径补全

**文件：** `src/embedagent/frontend/gui/webapp/src/state-helpers.js`

`timelineFromEvents` 中对 `command_result`、`context_compacted`、`session_error` 的解析逻辑应补充读取 `payload.turn_id`、`payload.step_id`：

```javascript
} else if (eventName === "command_result") {
  items.push({
    ...,
    turnId: payload.turn_id || "",
    stepId: payload.step_id || "",
    stepIndex: payload.step_index || 0,
  });
}
```

### 6.6 前端：WebSocket 实时接收路径补全

**文件：** `src/embedagent/frontend/gui/webapp/src/App.jsx`

- `CONTEXT_COMPACTED` 的 dispatch 应附加 `turnId: state.activeTurnId` 等（如果后端尚未修复）。
- `SESSION_ERROR` 同理。
- `COMMAND_RESULT` 可考虑优先使用后端传入的 `data.turn_id`：

  ```javascript
  dispatch({
    type: "command_result",
    turnId: data.turn_id || state.activeTurnId || "",
    stepId: data.step_id || "",
    ...
  });
  ```

---

## 7. 关键代码引用索引

| 功能 | 文件路径 | 行号 |
|---|---|---|
| `context_compacted` 过度触发 | `src/embedagent/context.py` | ~522 |
| `context_compacted` 后端 emit | `src/embedagent/inprocess_adapter.py` | ~2107 |
| `context_compacted` 协议层转换 | `src/embedagent/core/adapter.py` | ~188-201 |
| `context_compacted` WebSocket 广播 | `src/embedagent/frontend/gui/backend/server.py` | ~202-211 |
| `context_compacted` 前端接收 | `src/embedagent/frontend/gui/webapp/src/App.jsx` | ~755-764 |
| `context_compacted` reducer | `src/embedagent/frontend/gui/webapp/src/store.js` | ~449-461 |
| `context_compacted` event-log 恢复 | `src/embedagent/frontend/gui/webapp/src/state-helpers.js` | ~223-233 |
| slash 命令在 turn 之前执行 | `src/embedagent/inprocess_adapter.py` | ~907-956 |
| `command_result` 后端 emit | `src/embedagent/inprocess_adapter.py` | ~1829-1841 |
| `command_result` WebSocket 广播 | `src/embedagent/frontend/gui/backend/server.py` | ~358-367 |
| `command_result` 前端接收 | `src/embedagent/frontend/gui/webapp/src/App.jsx` | ~607-614 |
| `command_result` reducer | `src/embedagent/frontend/gui/webapp/src/store.js` | ~468-486 |
| `command_result` event-log 恢复 | `src/embedagent/frontend/gui/webapp/src/state-helpers.js` | ~243-253 |
| `session_error` 后端 emit | `src/embedagent/inprocess_adapter.py` | ~2180 |
| `session_error` 协议层转换 | `src/embedagent/core/adapter.py` | ~118-127 |
| `session_error` 前端接收 | `src/embedagent/frontend/gui/webapp/src/App.jsx` | ~746-751 |
| `session_error` reducer | `src/embedagent/frontend/gui/webapp/src/store.js` | ~435-448 |
| `session_error` event-log 恢复 | `src/embedagent/frontend/gui/webapp/src/state-helpers.js` | ~234-242 |
| `PermissionRequest` dataclass 缺失 | `src/embedagent/protocol/__init__.py` | ~76-83 |
| `UserInputRequest` dataclass 缺失 | `src/embedagent/protocol/__init__.py` | ~86-92 |
| `CommandResult` dataclass 缺失 | `src/embedagent/protocol/__init__.py` | ~95-102 |
| Timeline 分组逻辑（fallback） | `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js` | ~135-143, 168-212 |

---

*分析完成日期：2026-04-05*
*复核修正日期：2026-04-05*

---

# 9. 修复落地状态（2026-04-05）

## 9.1 结果

本报告识别出的主问题已按“统一事件锚点契约 + slash/workflow 命令正式 turn 化”的方案完成落地。

已完成的关键修复：

- `CommandResult`、`PermissionRequest`、`UserInputRequest` 统一补齐 `turn_id / step_id / step_index`
- `context_compacted` 与 `session_error` 的后端 emit、协议转换、WebSocket 转发、前端 reducer、raw replay 路径已补齐 turn/step 坐标
- slash/workflow 命令在 `_dispatch_input` 前预生成 `turn_id`，handled-only 命令会发出 `turn_start / turn_end`
- 命令侧工具执行与命令侧权限请求现在也会继承同一 `turn_id`
- `build_structured_timeline()` 开始保留 turn-level `transitions / tool_calls`
- `timelineFromTurns()` 开始投影 turn-level `command_result / context_compacted / session_error`，以及 turn-level command tool calls
- `permission_request` 前端本地追加的 `interaction.created` 已补齐 turn/step 字段，与 `user_input_request` 结构对齐
- `context.py` 已移除 `compacted = bool(old_turns) ...` 这一误触发条件

## 9.2 仍保留但已降级的风险

- `interaction.created` 仍然存在“backend raw event + frontend local append”双轨来源，但两边结构现已对齐，并按 `interaction_id` 去重
- `projector.js` 的 fallback 逻辑仍然存在，但在本轮目标事件上已不再是主路径；现在只有真正缺锚点的异常数据才会走 fallback

## 9.3 定向验证

已执行并通过：

```powershell
python tests/test_architecture.py
python tests/test_gui_sync.py
python tests/test_inprocess_adapter_frontend_api.py
python tests/test_context_config.py
python tests/test_gui_runtime.py
python tests/test_gui_backend_api.py
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

## 9.4 结论

本 issue 当前不再处于“问题待确认”状态，而是进入“已修复，待 Win7 / 真实 GUI 宿主进一步观察体验细节”的状态。

---

# 8. 现状复核报告（2026-04-05）

## 8.1 复核方法

对报告中涉及的全部后端 emit 点、协议层转换、WebSocket 广播、前端实时接收、Redux reducer、event-log 恢复及 Timeline 投影逻辑进行了逐行代码比对。比对基准为当前 `main` 分支最新代码。

## 8.2 核心结论：问题全部未修复

下表汇总了各消息类型在 8 个关键链节点的现状（❌ 表示与初版分析一致，问题仍然存在；✅ 表示无需修复或已修复）：

| 消息类型 | 后端 emit 含 turn/step？ | 协议层 dataclass 有字段？ | WebSocket 转发含 turn/step？ | 前端实时接收补全？ | reducer 保存 turn/step？ | event-log 恢复补全？ | Timeline 影响 |
|---|---|---|---|---|---|---|---|
| `CONTEXT_COMPACTED` | ❌ 无 | N/A（Message 通用） | ❌ 无（metadata 未注入） | ❌ 未补 | ❌ 未补 | ❌ 未补 | **高** — 仍为独立 group 堆叠 |
| `COMMAND_RESULT` | ❌ 无 | ❌ `CommandResult` 缺失字段 | ❌ 无 | ❌ 未补 | ⚠️ 依赖 `activeTurnId` | ❌ 未补 | **中** — 仍为 fallback 或错绑 |
| `SESSION_ERROR` | ❌ 无 | N/A（Message 通用） | ❌ 无 | ❌ 未补 | ❌ 未补 | ❌ 未补 | **中** — 仍挂到最后一个 group |
| `PERMISSION_REQUEST` | ✅ `inprocess_adapter.py` 实际有 | ❌ `PermissionRequest` 缺失字段 | ❌ 无（被 dataclass 截断） | ❌ `App.jsx` 未读取 | N/A（弹窗逻辑） | ✅ 原生 event 有，但前端追加的 `interaction.created` 缺失 | **低** — Inspector 与原生 event log 数据源不一致 |
| `USER_INPUT_REQUEST` | ✅ `inprocess_adapter.py` 实际有 | ❌ `UserInputRequest` 缺失字段 | ❌ 无（被 dataclass 截断） | ✅ `App.jsx` 已尝试读取 | N/A（弹窗逻辑） | ⚠️ 原生 event 有，前端 `interaction.created` 已补 | **低** — 前端已准备好，但后端协议层截断导致实际为空 |
| `ASSISTANT_DELTA` / `REASONING_DELTA` / `TOOL_START/FINISH` | ✅ 有 | ✅ 有 | ✅ 有 | ✅ 有 | ✅ 有 | ✅ 有 | 正常 |

**总体判断：** 三类系统性缺失（模式 A、B、C）在当前代码中**原封不动存在**，没有任何一处被修复。

## 8.3 逐链路现状细节

### 8.3.1 `CONTEXT_COMPACTED` — 全部未变

- **过度触发：** `src/embedagent/context.py:522` 的 `compacted = bool(old_turns) or bool(reduced_tool_messages) or (used_chars < chars_before)` 逻辑保持原样。只要会话长度超过 `max_recent_turns`，`old_turns` 非空就会使 `compacted` 为 `True`，几乎每个 step 都会触发一次。
- **后端 emit：** `src/embedagent/inprocess_adapter.py:2104` 的 payload 仍然只包含 `recent_turns`、`summarized_turns`、`approx_tokens_after`、`analysis`，**没有** `turn_id` / `step_id`。
- **协议层：** `src/embedagent/core/adapter.py:188-201` 构建 `Message` 时 metadata 未注入 turn/step 坐标。
- **WebSocket：** `src/embedagent/frontend/gui/backend/server.py:202-211` 的 `on_message` 直接透传 `message.metadata`，由于没有注入，自然为空。
- **前端实时：** `src/embedagent/frontend/gui/webapp/src/App.jsx:755-764` dispatch 时**仍未附加** `turnId` / `stepId` / `stepIndex`。
- **reducer：** `src/embedagent/frontend/gui/webapp/src/store.js:449-461` timeline item 仍然缺少 turn/step 字段。
- **event-log 恢复：** `src/embedagent/frontend/gui/webapp/src/state-helpers.js:223-233` 仍然未从 `payload` 读取 `turn_id` / `step_id` / `step_index`。
- **投影影响：** `projector.js:135-143` 中 `kind === "compact"` 且无 `turnId` 时，key 仍为 `session-{唯一随机id}`，导致**每个 compact 卡片都创建独立 turn group**。`projector.js:190-196` 将其放入 `trailingTurnItems`（若 group 已有 step）或 `leadingSystemItems`（若 group 为空），渲染为多个紧挨的 `<div class="turn-group">`，视觉堆叠现象不变。

### 8.3.2 `COMMAND_RESULT` — 全部未变

- **slash 命令仍无 turn 上下文：** `src/embedagent/inprocess_adapter.py:907-956`（`submit_user_message`）中 `_dispatch_input` 仍在 `_run_turn` 之前执行，`turn_id` 尚未生成。`_emit_command_result`（`~1826-1838`）payload 中仍然**没有** `turn_id` / `step_id`。
- **协议层 dataclass：** `src/embedagent/protocol/__init__.py:95-102` 的 `CommandResult` 仍然只有 `command_name`、`success`、`message`、`data` 四个字段，**未增加** `turn_id` / `step_id` / `step_index`。
- **协议层转换：** `src/embedagent/core/adapter.py:150-158` 构造 `CommandResult` 时自然无法传递这些字段。
- **WebSocket：** `src/embedagent/frontend/gui/backend/server.py:358-367` 的 `on_command_result` 仍然只转发老四样。
- **前端实时：** `src/embedagent/frontend/gui/webapp/src/App.jsx:606-614` dispatch `command_result` 时**仍未显式附加** `turnId` / `stepId`。
- **reducer：** `src/embedagent/frontend/gui/webapp/src/store.js:468-486` 仍然通过 `resolveTimelineAnchor({ explicitTurnId: action.turnId || "", activeTurnId: state.activeTurnId, timeline: state.timeline })` 决策。这意味着实时流中只能依赖 `activeTurnId`，后者若因异步/跨 step 发生变化就会绑定到错误 turn。
- **event-log 恢复：** `src/embedagent/frontend/gui/webapp/src/state-helpers.js:243-253` 生成的 `command_result` item 仍然没有 `turnId`。
- **投影影响：** `projector.js:177-179` 对无 `turnId` 的 `command_result` 仍然降级为 `command_result_fallback` 并塞入 `sessionFallbackItems`，无法与具体 turn 对齐。

### 8.3.3 `SESSION_ERROR` — 全部未变

- **后端 emit：** `src/embedagent/inprocess_adapter.py:2177` payload `{"error": str(exc), "phase": "loop"}` 仍然**没有** `turn_id` / `step_id`。
- **协议层：** `src/embedagent/core/adapter.py:118-127` 构建 `Message(type=MessageType.ERROR)` 时没有注入 turn/step。
- **前端实时：** `src/embedagent/frontend/gui/webapp/src/App.jsx:746-751` dispatch `session_error` 时**没有** `turnId`。
- **reducer：** `src/embedagent/frontend/gui/webapp/src/store.js:435-448` 生成的 `kind: "system"` item **没有** `turnId`。
- **event-log 恢复：** `src/embedagent/frontend/gui/webapp/src/state-helpers.js:234-242` 仍然未读取 `payload.turn_id` 等字段。
- **投影影响：** `projector.js:190-196` 对无 `turnId` 的 `system` 项仍然根据当前 group 的 steps 数量决定放入 `leadingSystemItems` 或 `trailingTurnItems`。由于遍历顺序，它会挂在**最后处理的 group** 上，无法保证与真正出错的 step 对齐。

### 8.3.4 `PERMISSION_REQUEST` — 协议截断未变，前端出现不一致

- **后端 emit：** `src/embedagent/inprocess_adapter.py:2108` 的 payload **确实包含** `turn_id`、`step_id`、`step_index`（与初版分析一致，这一头是好的）。
- **协议层 dataclass：** `src/embedagent/protocol/__init__.py:76-83` 的 `PermissionRequest` 仍然**没有**这些字段，导致 `core/adapter.py` 构建对象时丢弃它们。
- **WebSocket：** `src/embedagent/frontend/gui/backend/server.py:269-283` 的 `on_permission_request` 由于 dataclass 缺失，只能转发 `permission_id`、`tool_name`、`category`、`reason`、`details`。
- **前端实时（新增发现）：** 与 `user_input_request` 不同，`App.jsx:550-569` 中处理 `permission_request` 的 dispatch **没有**读取 `data.turn_id` / `data.step_id` / `data.step_index`。这意味着即使后端未来修复了协议层，前端的 permission 实时路径也**尚未准备好**消费这些字段，需要额外补正。
- **event-log 双源不一致（新增发现）：** 前端 `App.jsx:553-568` 在收到 `permission_request` 时会往本地 event log 追加一个 `interaction.created` 事件，但其 payload 中**没有** `turn_id` / `step_id` / `step_index`。而原生后端事件 `permission_required`（写入 `timeline.jsonl`）是**有**这些字段的。`timelineFromEvents` **不处理** `interaction.created` 事件，因此 Timeline 投影走的是原生后端事件（有坐标），Inspector 走的是前端追加的 `interaction.created`（无坐标）。这种**双源不一致**会导致 Inspector 中权限请求缺少“第 X 步”上下文，与 Timeline 显示错位。

### 8.3.5 `USER_INPUT_REQUEST` — 前端已局部补全，但被后端截断

- **后端 emit：** `src/embedagent/inprocess_adapter.py:2120` payload **确实包含** `turn_id`、`step_id`、`step_index`。
- **协议层 dataclass：** `src/embedagent/protocol/__init__.py:86-92` 的 `UserInputRequest` 仍然**没有**这些字段。
- **WebSocket：** `src/embedagent/frontend/gui/backend/server.py:292-305` 同样因 dataclass 截断而无法转发。
- **前端实时（变更点）：** `App.jsx:573-583` 现在已经读取 `data.turn_id` / `data.step_id` / `data.step_index` 并传递给 reducer（`type: "user_input_request"`）。这说明前端代码已经“准备好”接收这些字段。**但由于 server.py 不转发，实际运行时这些数据永远为空字符串/零。**
- **event-log：** `App.jsx:584-602` 追加的 `interaction.created` 事件 payload 中已经包含 `turn_id` / `step_id` / `step_index`，与 `permission_request` 形成鲜明对比，进一步说明两者在前端处理上存在** inconsistency**。

## 8.4 `projector.js` 分组逻辑现状

`src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js` 的 `getTurnGroup` 和 `projectTurnGroups` 与初版分析时**一字未改**：

- `getTurnGroup`（`~135-143`）：`fallbackId` 对非 `user` kind 的项生成 `session-{item.id}`，导致无 `turnId` 的 `compact` 和 `system` 项仍然各自拥有唯一 group key。
- `projectTurnGroups`（`~168-212`）：对 `command_result` 的无 `turnId` 降级逻辑、对 `system`/`compact` 的 `steps.length` 判断逻辑均未变化。报告初版中描述的所有临床表现（压缩墙、命令结果游离、错误消息错位）在当前代码下**仍然会出现**。

## 8.5 新增潜在风险

1. **permission / user_input 前端处理不一致**
   `user_input_request` 已在 `App.jsx` 实时路径和 `interaction.created` event log 中补全 turn/step 字段，但 `permission_request` 两边都缺失。未来修复后端协议层时，容易遗漏 permission 前端的补全工作，导致 Inspector 中 permission 仍然缺少 step 上下文。

2. **`interaction.created` 与原生后端 event 的双源风险**
   前端本地追加的 `interaction.created` 事件与后端 `timeline.jsonl` 中的原生 `permission_required` / `user_input_required` 事件并存。由于 `timelineFromEvents` 不消费 `interaction.created`，Timeline 投影和 Inspector 实际上依赖的是两套数据源。若未来 event log 被用于 Timeline 完整回放，需确保不会重复渲染或坐标冲突。

3. **`command_result` 的 `activeTurnId` 竞争在并发/快速输入时加剧**
   若用户在 turn 运行过程中快速发送新消息或切换 session，`activeTurnId` 可能已被更新为下一个 turn，`command_result` 会错误绑定到后续 turn。由于 `projector.js` 的 `sessionFallbackItems` 渲染位置固定在 session 底部，视觉错位会非常明显。

4. **修复 `context_compacted` 触发频率前，单独补传 `turn_id` 只能部分缓解**
   即使给每个 `context_compacted` 事件补上了 `turn_id`，只要 `compacted = True` 的判断逻辑不变，每个 step 仍然会产生一个 compact 卡片。虽然它们会归到同一 turn group 的 `trailingTurnItems` 中（不再各自成群），但大量卡片仍会纵向堆叠在同一 turn 内。建议将“补传坐标”与“降低触发频率”作为**同一批修复**合并处理。

## 8.6 修复优先级建议（维持并微调）

基于现状复核，建议按以下优先级推进：

1. **P0 — 协议层补全 dataclass 字段**
   为 `PermissionRequest`、`UserInputRequest`、`CommandResult` 统一增加 `turn_id`、`step_id`、`step_index`。这是解锁所有下游修复的**阻塞性前置条件**。

2. **P0 — 后端 emit 补全 `turn_id` / `step_id`**
   - `context_compacted` 的 payload（`inprocess_adapter.py:2104`）
   - `session_error` 的 payload（`inprocess_adapter.py:2177`）
   同时更新 `core/adapter.py` 中对应事件的字段映射，以及 `server.py` 的转发逻辑。

3. **P1 — 前端实时路径和 event-log 恢复路径补全**
   - `App.jsx`：`session_error`、`context_compacted`、`command_result` 的 dispatch 附加 `turnId` / `stepId`（若后端尚未部署，可先用 `state.activeTurnId` 兜底）。
   - `App.jsx`：`permission_request` 的 dispatch 补全 `turn_id` / `step_id` 读取，与 `user_input_request` 对齐。
   - `store.js`：三个 reducer 中保存 turn/step 字段。
   - `state-helpers.js`：event-log 恢复时读取 `payload.turn_id` / `payload.step_id` / `payload.step_index`。

4. **P1 — 降低 `context_compacted` 触发频率**
   修改 `context.py:522`，将 `bool(old_turns)` 从 `compacted` 判定中移除，或增加“是否真正发生硬截断/强制压缩”的条件，避免常规 summary 被标记为 compaction。

5. **P2 — `COMMAND_RESULT` 架构调整**
   选择以下方案之一为 slash 命令补充 turn 上下文：
   - **延迟发送：** 暂存 `command_result`，等 `_run_turn_v2` 生成 `turn_id` 后关联再 emit。
   - **预生成 turn_id：** 在 `_dispatch_input` 之前生成 `turn_id`，使整个 user message 生命周期共享同一 ID。

6. **P2 — 统一 interaction event 数据源**
   评估是否让 `timelineFromEvents` 也消费 `interaction.created`，或统一让 Inspector 直接读取原生后端 event 的 turn/step 坐标，消除双源不一致。
