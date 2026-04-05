# EmbedAgent Frontend Protocol（Phase 6）

> 更新日期：2026-04-04
> 适用阶段：Phase 6 交互层设计

---

## 1. 文档目标

定义 Frontend 与 Agent Core 之间的协议边界，保证：

- CLI / TUI / 未来 GUI 可以共用同一套 Core
- 前端不直接接触 Loop 内部状态真相
- 后续可从 In-Process 演进到 stdio JSON-RPC，而不重写 Core 逻辑

本文件聚焦协议与适配层，不展开 TUI 具体布局。

---

## 2. 设计原则

### 2.1 Core 保持单一状态真相

前端只能通过 Command 提交意图，通过 Event 接收状态变化。

前端不负责：

- 自行拼 prompt
- 自行持有会话状态真相
- 直接调用工具 Runtime
- 绕过权限系统直接执行动作

### 2.2 先做 In-Process，再做 stdio

Phase 6 的实现顺序固定为：

1. `InProcessAdapter`
2. 最小 `TUI`
3. `stdio JSON-RPC Adapter`
4. `Local HTTP + SSE Adapter`（后续，不在当前阶段）

原因：

- In-process 最轻，最适合把当前 CLI 升级为可复用交互层
- stdio 最适合作为宿主集成边界
- 先把命令/事件协议稳定下来，再考虑 HTTP

### 2.3 协议以会话为中心

所有命令和事件都围绕 `session_id` 组织。

这意味着：

- 一个前端实例可以管理多个会话
- 交互层的最小单位是 Session，而不是单条消息
- 恢复、暂停、权限确认都必须显式关联到 Session

### 2.4 Session Snapshot 是权威状态

前端不能再自己猜测 `idle / running / waiting_permission / waiting_user_input / error`。

当前约定是：

- `turn_started`
- `permission_required`
- `user_input_required`
- `mode_changed`
- `session_finished`
- `session_error`
- `session_status`

这些事件都会附带最新 `session_snapshot`，前端必须以该快照为准更新状态与模式显示。

### 2.5 GUI Active Session 采用事件日志 + 快照纠偏

当前 GUI active session 已不再只依赖零散 WebSocket 消息和局部 reducer 推断状态。

新增约束：

- WebSocket 会为 active session 推送 `type = session_event` 的统一事件 envelope
- HTTP `GET /api/sessions/{session_id}/events?after_seq=N` 负责在断线/错序后补齐增量事件
- HTTP `POST /api/sessions/{session_id}/interactions/{interaction_id}/respond` 是 GUI 唯一的交互响应入口
- Inspector 负责当前 pending interaction 的操作；Timeline 只显示交互历史摘要
- GUI snapshot 必须显式暴露 replay 能力：`timeline_replay_status`、`timeline_first_seq`、`timeline_last_seq`、`timeline_integrity`、`pending_interaction_valid`
- replay 结果必须显式区分 `replay / reload_required / degraded`，前端不得再从“空 events”反推需要 reload

---

## 3. 分阶段实现

### 3.1 Phase 6A：In-Process Adapter

目标：

- 把现有 CLI/未来 TUI 都接到同一个内存内 Adapter
- 复用当前 `AgentLoop`、`SessionSummaryStore`、`ProjectMemoryStore`

最小接口：

- `create_session`
- `submit_user_message`
- `approve_permission`
- `reject_permission`
- `resume_session`
- `cancel_session`
- `list_sessions`
- `get_session_snapshot`

### 3.2 Phase 6B：模块化终端前端

目标：

- 在 `InProcessAdapter` 之上提供可维护的终端前端包
- 让 Session、Workspace、Timeline、Artifacts、Permission 都能被直接观测

当前范围：

- `src/embedagent/frontend/tui/` 包结构（state / reducer / controller / layout / services / views）
- Explorer / Main View / Inspector / Composer 终端布局
- workspace / timeline / artifact / todo 浏览接口接入
- 会话浏览、权限确认、错误状态、上下文状态和单缓冲编辑器
- 保留 `embedagent.tui` 兼容入口

验证口径：

- `scripts/validate-phase6.py`
- `EMBEDAGENT_TUI_HEADLESS=1`
- `python -m unittest discover -s tests`
- 真实控制台手工验证
### 3.3 Phase 6C：stdio JSON-RPC Adapter

目标：

- 暴露一套宿主可调用的协议
- 允许未来桌面壳、脚本系统、外部 TUI 通过 stdio 拉起 Core

约束：

- 使用 JSON-RPC 2.0 子集
- 事件以通知形式发送
- 不依赖额外网络端口

---

## 4. 核心对象

### 4.1 Session Snapshot

前端读取 Session 时，不直接拿内部 dataclass，而是拿快照：

```json
{
  "session_id": "abc123",
  "status": "idle",
  "current_mode": "code",
  "started_at": "2026-03-28T10:00:00Z",
  "updated_at": "2026-03-28T10:02:00Z",
  "last_user_message": "继续修复编译错误",
  "last_assistant_message": "我先检查最近的编译诊断。",
  "summary_ref": ".embedagent/memory/sessions/abc123/summary.json",
  "has_pending_permission": false,
  "pending_permission": null,
  "last_error": null,
  "timeline_replay_status": "replay",
  "timeline_first_seq": 0,
  "timeline_last_seq": 0,
  "timeline_integrity": "healthy",
  "pending_interaction_valid": false
}
```

### 4.2 Permission Ticket

权限确认必须带上可追踪 ticket：

```json
{
  "permission_id": "perm_001",
  "session_id": "abc123",
  "tool_name": "run_command",
  "category": "command",
  "reason": "该操作会执行命令或工具链程序。",
  "details": {
    "command": "python -m py_compile src/embedagent/loop.py",
    "cwd": ".",
    "rule_decision": "ask"
  }
}
```

Ticket 的目标是让前端在异步交互里能明确知道：

- 当前正在确认哪个操作
- 用户的批准/拒绝要回给哪个 Session

---

## 5. Command 协议

### 5.1 通用格式

In-process 调用可以直接用 Python dict；stdio 使用 JSON-RPC 时也映射到同样的 payload。

```json
{
  "command": "submit_user_message",
  "payload": {
    "session_id": "abc123",
    "text": "继续当前任务"
  }
}
```

### 5.2 Command 列表

#### `create_session`

用途：创建新会话。

payload：

```json
{
  "mode": "code",
  "resume": "",
  "workspace": "D:/Claude-project/ccode-win7"
}
```

返回：`session_snapshot`

#### `submit_user_message`

用途：向已有会话提交用户消息，并驱动 Loop 继续执行。

payload：

```json
{
  "session_id": "abc123",
  "text": "继续修复当前问题"
}
```

#### `respond_to_interaction`

用途：统一处理 GUI 的 permission / ask-user / mode proposal 交互响应。

HTTP 入口：

```text
POST /api/sessions/{session_id}/interactions/{interaction_id}/respond
```

payload：

```json
{
  "response_kind": "approve",
  "decision": true,
  "remember": false,
  "answer": "",
  "selected_index": null,
  "selected_mode": "",
  "selected_option_text": ""
}
```

返回：

- `session_id`
- `interaction_id`
- `status`
- `snapshot`

错误语义：

- `404 session_not_found`
- `410 interaction_expired`
- `409 interaction_conflict`
- `422 invalid_request`

#### `replay_session_events`

用途：在 GUI reconnect 或事件错序后，从指定 `seq` 之后重新获取事件。

HTTP 入口：

```text
GET /api/sessions/{session_id}/events?after_seq=42
```

返回：

```json
{
  "session_id": "abc123",
  "status": "replay",
  "first_seq": 43,
  "last_seq": 57,
  "reason": "",
  "events": [
    {
      "event_id": "evt-100",
      "seq": 43,
      "created_at": "2026-04-04T08:00:00Z",
      "event_kind": "tool.started",
      "payload": {}
    }
  ]
}
```

说明：

- `status = replay`：当前 retained window 仍覆盖 `after_seq`，可直接追加事件
- `status = reload_required`：请求的 `after_seq` 早于 retained window，前端必须重新 bootstrap session
- `status = degraded`：timeline 完整性不足，前端应保守 reload 并显示 degraded 状态

返回：立即确认收到；真正执行结果通过 Event 流返回。

#### `approve_permission`

用途：批准待确认操作。

payload：

```json
{
  "session_id": "abc123",
  "permission_id": "perm_001"
}
```

#### `reject_permission`

用途：拒绝待确认操作。

payload：

```json
{
  "session_id": "abc123",
  "permission_id": "perm_001"
}
```

#### `resume_session`

用途：从已有摘要恢复会话。

payload：

```json
{
  "reference": "latest",
  "mode": "debug"
}
```

说明：

- `reference` 支持 `latest`、`session_id`、`summary.json` 路径
- `mode` 可选，留空时沿用摘要中的 `current_mode`

#### `cancel_session`

用途：终止前端对当前会话的继续推进。

说明：当前阶段只要求停止后续交互，不要求抢占中断子进程。

#### `list_sessions`

用途：列出最近可恢复会话。

payload：

```json
{
  "limit": 10
}
```

#### `get_session_snapshot`

用途：获取当前 Session 快照，用于 UI 恢复渲染。

payload：

```json
{
  "session_id": "abc123"
}
```

---

## 6. Event 协议

### 6.1 通用格式

```json
{
  "event": "tool_started",
  "session_id": "abc123",
  "payload": {
    "tool_name": "read_file",
    "arguments": {
      "path": "README.md"
    }
  }
}
```

### 6.2 Event 列表

#### `session_created`

表示 Session 已建立。

#### `session_resumed`

表示 Session 已从摘要恢复。

payload 至少包含：

- `session_snapshot`
- `resume_ref`

#### `turn_started`

表示一次新的用户提交已经开始被处理。

#### `assistant_delta`

表示流式文本增量。

payload：

```json
{
  "text": "我先检查最近的编译输出"
}
```

#### `tool_started`

表示工具即将执行。

当前 payload 必须带稳定的 `call_id`，供前端把同一工具卡片的 start / finish 正确关联起来。

#### `tool_finished`

表示工具完成，并返回结构化 Observation 摘要。

#### `permission_required`

表示当前会话进入等待人工确认状态。

payload：`permission_ticket`

同时附带 `session_snapshot`，其 `status` 应为 `waiting_permission`。

#### `user_input_required`

表示当前会话进入等待用户回答状态。

payload：`user_input_ticket`

同时附带 `session_snapshot`，其 `status` 应为 `waiting_user_input`。

#### `session_status`

表示权威状态快照刷新。

payload 至少包含：

- `session_snapshot`

#### `reasoning_delta`

表示模型显式输出的 thinking / reasoning 文本增量。

payload：

```json
{
  "text": "先检查最近的工具输出，再决定是否需要 ask_user。"
}
```

#### `thinking_state`

表示当前 turn 是否处于 thinking 阶段。

payload：

```json
{
  "active": true,
  "reason": "turn_started"
}
```

#### `context_compacted`

表示本轮构建上下文时发生了压缩。

payload 建议至少包含：

- `recent_turns`
- `summarized_turns`
- `project_memory_included`
- `approx_tokens_after`

#### `session_finished`

表示本次提交已完成，返回最终 assistant 文本和最新快照。

#### `session_error`

表示处理失败。

payload 至少包含：

- `error`
- `phase`

---

## 7. 传输层映射

### 7.1 In-Process Adapter

建议接口：

```python
class InProcessAdapter(object):
    def create_session(...): ...
    def submit_user_message(...): ...
    def approve_permission(...): ...
    def reject_permission(...): ...
    def list_sessions(...): ...
    def get_session_snapshot(...): ...
```

事件回调通过 Python callable 注入：

- `on_event(event_name, payload)`

### 7.2 stdio JSON-RPC Adapter

采用 JSON-RPC 2.0 子集：

- request: `{"jsonrpc":"2.0","id":1,"method":"create_session","params":{...}}`
- response: `{"jsonrpc":"2.0","id":1,"result":{...}}`
- event/notification: `{"jsonrpc":"2.0","method":"event.tool_started","params":{...}}`

约束：

- 只使用 UTF-8 文本
- 每个 JSON object 单独一行
- 不做 batch request

---

## 8. 错误模型

### 8.1 Command Error / Typed HTTP Error

命令执行前的参数错误或状态错误，应直接作为 command result 返回：

```json
{
  "error": {
    "code": "invalid_request",
    "message": "session_id 不存在"
  }
}
```

GUI HTTP 路径同时采用 typed status code：

- `404`：`session_not_found`
- `409`：`interaction_conflict`
- `410`：`interaction_expired`
- `422`：`invalid_request`

### 8.2 Runtime Error / Replay Degraded

Loop 内部错误、模型错误、工具错误，应通过 `session_error` Event 发出，并同步更新 Session 快照中的 `last_error`。

GUI runtime 额外约束：

- websocket enqueue / receive / parse 失败要进入 transport degraded
- replay gap 不再只用布尔值表示，前端读模型至少区分 `healthy / replay_needed / reload_required / degraded`

---

## 9. Phase 6 实现顺序

1. 先实现 `InProcessAdapter`
2. 让现有 CLI 改为调用 adapter，而不是直接组装 loop
3. 基于同一 adapter 做模块化终端前端，并补 `scripts/validate-phase6.py` 与前端单元测试
4. 最后再暴露 stdio JSON-RPC adapter

---

## 10. 当前结论

Phase 6 的关键不是“先画界面”，而是：

**先把 Frontend 与 Core 的命令/事件边界定稳。**

只要这个边界是稳定的，CLI、TUI、未来 GUI 都能复用同一个 Core，而不会再次把状态、权限和上下文逻辑分散回前端。

## 11. Frontend Browse APIs

在最小会话协议之外，Phase 6 终端前端当前还依赖以下浏览型接口：

- `get_workspace_snapshot`
- `list_workspace_tree`
- `list_workspace_children`
- `read_workspace_file`
- `write_workspace_file`
- `get_session_timeline`
- `list_artifacts`
- `read_artifact`
- `list_todos`

这些接口保持“前端读模型状态 / 工作区状态，但不绕过 Core 会话真相”的原则：

- timeline 来自持久化事件流，而不是前端临时 transcript
- artifact 浏览来自 session-local tool-result 文件本体与 `ProjectionDb (SQLite)` 提供的查询元数据
- GUI 文件树应优先使用 `list_workspace_children` 做懒加载，而不是一次性平铺整棵树
- `list_todos` 现在应显式关联 `session_id`，前端默认展示当前会话的 todo，而不是工作区全局 todo
- 文件保存仍通过 adapter 边界，不在 TUI 里直接散落文件写入逻辑



