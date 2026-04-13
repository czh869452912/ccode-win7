# 2026-04-13 GUI / Session Runtime 静态审查问题清单

> 类型：`issue-analysis`
> 审查方式：`static-only`
> 日期：`2026-04-13`
> 相关范围：`src/embedagent/frontend/gui/`、`src/embedagent/core/adapter.py`、`src/embedagent/inprocess_adapter.py`

## 1. 审查结论

本轮仅做静态代码复核，不包含运行验证、集成测试或回归测试。

结论如下：

- 已确认 **6 个明确问题**。
- 另识别出 **2 个高置信潜在问题**，需要后续实现或验证时一并处理。
- 当前最优先的问题是：
  - 多会话事件串线
  - 交互卡片投影错误
  - 回放事件契约漂移

## 2. 已确认问题

### 2.1 高风险：多会话 WebSocket 事件会互相污染

**问题描述**

GUI 后端将 WebSocket 消息广播给所有连接，前端消费时又不按 `session_id` 过滤。只要浏览器当前打开的是会话 B，而后台会话 A 仍在推送状态，B 的界面就可能被 A 的 live 事件或快照覆盖。

**静态证据**

- `src/embedagent/frontend/gui/backend/server.py:209`
  - `broadcast()` 直接向全部连接发送消息，没有会话绑定。
- `src/embedagent/frontend/gui/backend/server.py:356`
  - `session_status` 推送中包含完整 `session_snapshot`，但仍是全局广播。
- `src/embedagent/frontend/gui/backend/server.py:255`
  - `tool_start` 等 live 事件未携带 `session_id`。
- `src/embedagent/frontend/gui/backend/server.py:382`
  - `stream_delta`、`reasoning_delta`、`thinking_state` 也未带 `session_id`。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:421`
  - `handleSocketMessage()` 对 `session_event` 不按会话过滤。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:448`
  - `session_status` 到来后直接更新当前前端状态。
- `src/embedagent/frontend/gui/webapp/src/store.js:145`
  - `session_snapshot` reducer 会直接用收到的 `snapshot.session_id` 覆盖 `currentSessionId`。

**影响**

- 当前会话可能被别的会话状态覆盖。
- live timeline、工具状态、thinking 状态、interaction 状态都可能串线。
- 多标签页 / 多窗口 / 多会话恢复场景下问题尤为明显。

**修复方向**

- 后端建立“连接 -> session”绑定，按会话单播或分组广播。
- 所有 live 消息统一携带 `session_id`。
- 前端在消费所有 session-scoped 消息前，先做 `session_id` 过滤。

### 2.2 高风险：`user_input` 会生成重复卡片，且其中一张是坏卡片

**问题描述**

store 写入的 timeline item 使用嵌套 `request` 结构，而 runtime projector 读取交互卡片时按顶层字段读取 `request_id` / `question` / `tool_name`。结果是：

- dedupe 失效
- 会出现一张随机 id 的空交互卡
- 随后又叠加真正的 `interaction.created` 卡片

该问题不仅影响普通 `user_input`，也影响 `propose_mode_switch` 这类 mode switch proposal 卡片。

**静态证据**

- `src/embedagent/frontend/gui/webapp/src/store.js:420`
  - `user_input_request` 写入 `{ kind, request, answered }`。
- `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js:10`
  - `toInteractionTimelineItem()` 按顶层 `payload.request_id` / `payload.question` 取值。
- `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js:61`
  - `projectBootstrapTimeline()` 会把 `user_input` / `mode_switch_proposal` 直接送进 projector。
- `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js:105`
  - `mergeTimelineItems()` 基于错误的 `interactionId` 做去重。
- `src/embedagent/frontend/gui/webapp/src/state-helpers.js:333`
  - 历史 permission 卡片也是 `{ kind, request }` 结构。
- `src/embedagent/frontend/gui/webapp/src/state-helpers.js:346`
  - 历史 user input 卡片同样使用 `{ kind, request }` 结构。

**影响**

- 时间线出现空白或随机 id 卡片。
- dedupe 失效后交互卡重复出现。
- interaction 解析逻辑和 bootstrap timeline 语义不一致。

**修复方向**

- 统一交互卡片 DTO；要么全部扁平化，要么 projector 正式支持 `{ request }` 结构。
- 用单一 `interaction_id` 作为 interaction projection 的唯一键。

### 2.3 中风险：GUI 默认模式与项目基线不一致

**问题描述**

项目基线明确规定默认模式是 `explore`，但 GUI 前后端和相关前端 fallback 仍广泛默认 `build`。

**静态证据**

- `AGENTS.md:110`
  - 默认入口模式应为 `explore`。
- `src/embedagent/frontend/gui/webapp/src/store.js:28`
  - `requestedMode` 默认是 `build`。
- `src/embedagent/frontend/gui/backend/server.py:540`
  - `create_session(mode: str = "build")`。
- `src/embedagent/frontend/gui/backend/server.py:546`
  - `resume_session(..., mode: str = "build")`。
- `src/embedagent/frontend/gui/webapp/src/state-helpers.js:541`
  - `normalizeSessionPayload()` 对 `current_mode` fallback 为 `build`。
- `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js:251`
  - runtime 投影 fallback 为 `build`。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:869`
  - session list item fallback 为 `build`。
- `src/embedagent/frontend/gui/launcher.py:235`
  - GUI launcher 默认 mode 仍为 `build`。

**影响**

- GUI 首次创建会话时直接偏离官方 mode policy。
- 文档、协议、前端显示、启动器行为不一致。

**修复方向**

- 将 GUI 相关默认 mode 与 fallback 统一切到 `explore`。
- 以 `src/embedagent/modes.py` 与官方文档为基准做一次全链路清理。

### 2.4 中风险：`step_start` / `step_end` 事件链路在 GUI 中基本不可达

**问题描述**

`InProcessAdapter` 明确发出 step 生命周期事件，前端 `App.jsx` 也写了对应处理分支，但 core -> GUI backend 的协议桥只转发了 turn 级事件，导致 step 级事件在 GUI live 链路中断裂。

**静态证据**

- `src/embedagent/inprocess_adapter.py:1396`
  - 明确发 `step_start`。
- `src/embedagent/inprocess_adapter.py:1399`
  - 明确发 `step_end`。
- `src/embedagent/core/adapter.py:310`
  - 仅将 `turn_start` / `turn_end` 转给 `on_turn_event()`。
- `src/embedagent/frontend/gui/backend/session_events.py:6`
  - GUI event map 虽然定义了 `step.started` / `step.finished`。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:704`
  - 前端存在 `step_start` / `step_end` 处理分支，但实际后端几乎不会发到这里。

**影响**

- GUI 无法可靠反映 step 生命周期。
- step 级交互、工具分组和 timeline anchor 更容易漂移。

**修复方向**

- 在 core adapter 中补齐 step 级事件转发。
- 或者删除前端死分支，彻底收敛到唯一正式事件模型。

### 2.5 中风险：文件读取错误被包装成 `200 OK`，前端表现为静默空白

**问题描述**

后端 `read_file` 接口把异常变成 `200 + {"error": ...}`，前端 `fetchJson()` 只看 HTTP 状态，`openFile()` 又直接按成功路径展示内容，最终常见表现是预览空白而不是明确错误。

**静态证据**

- `src/embedagent/frontend/gui/backend/server.py:634`
  - `read_file()` 捕获异常后返回 `{ "error": str(e) }`。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:138`
  - `fetchJson()` 仅在 `!res.ok` 时抛错。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:219`
  - `openFile()` 直接取 `payload.content || ""`。

**影响**

- 文件不存在、权限失败或读取异常时，用户看不到清晰错误。
- 交互体验上会误判为“文件为空”。

**修复方向**

- 后端改为抛出明确的 HTTP 错误状态。
- 前端对 `{ error }` 结构做兜底处理，避免静默渲染空内容。

### 2.6 设计漂移：交互响应仍保留 REST / WebSocket 双路径与全局 `_current_session_id`

**问题描述**

webapp 当前实际通过 REST 响应 interaction，但后端仍保留 WebSocket 响应分支，并依赖全局 `_current_session_id`。该设计会持续制造多会话漂移风险。

**静态证据**

- `src/embedagent/frontend/gui/webapp/src/App.jsx:777`
  - interaction 响应走 REST `/interactions/{interaction_id}/respond`。
- `src/embedagent/frontend/gui/backend/server.py:687`
  - 后端仍保留 WebSocket `permission_response` / `user_input_response` 处理入口。
- `src/embedagent/frontend/gui/backend/server.py:477`
  - `GUIBackend` 维护全局 `_current_session_id`。

**影响**

- 形成双路径行为漂移。
- 多会话下容易把权限记忆或 interaction 响应路由到错误 session。

**修复方向**

- 收敛到单一正式 interaction 响应路径。
- 删除或彻底隔离 `_current_session_id` 这类全局态。

## 3. 额外识别的高置信潜在问题

### 3.1 回放接口与 live projector 的 `event_kind` 契约不一致

**问题描述**

断线恢复接口 `/api/sessions/{id}/events` 返回的 `event_kind` 来自 timeline 原始事件名直接替换下划线，例如：

- `turn_start` -> `turn.start`
- `permission_required` -> `permission.required`
- `user_input_required` -> `user.input.required`

但前端 live 路径和 runtime projector 识别的是：

- `turn.started`
- `transition.recorded`
- `interaction.created`
- `interaction.resolved`

这会导致 replay 拉回来的事件虽然成功到达前端，但很难被既有逻辑按预期消费。

**静态证据**

- `src/embedagent/inprocess_adapter.py:745`
  - replay 返回 `str(record.get("event") or "").replace("_", ".")`。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:328`
  - `recoverSessionReplay()` 直接把 replay items 送入 event log。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:430`
  - `session_event` 只识别 `turn.started` / `transition.recorded` 等命名。
- `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js:70`
  - projector 仅识别 `interaction.created` / `interaction.resolved`。

**影响**

- 断线恢复后 timeline 与 live 状态可能不一致。
- replay 机制可能“看起来可用”，实际无法补齐关键语义。

**建议**

- 统一 replay 与 live 的 `event_kind` 词汇表。
- 优先以 `session_events.py` 的 GUI event mapping 为唯一外显命名源。

### 3.2 bootstrap 历史恢复可能丢失 step 级交互 / 错误卡片

**问题描述**

`SessionHistoryAssembler` 会把 step 级 transition 放进 `step.transitions`，但 GUI `loadSession()` 调用 `timelineFromTurns(history.turns, [])` 时没有把任何事件传给 `events` 参数，而 `timelineFromTurns()` 仅通过额外的 `events` 参数去生成 step 级 permission / user input 卡片，本身并不消费 `step.transitions`。

**静态证据**

- `src/embedagent/session_history.py:65`
  - assembler 会序列化 `step.transitions`。
- `src/embedagent/frontend/gui/webapp/src/App.jsx:183`
  - `loadSession()` 调用 `timelineFromTurns(history.turns || [], [], ...)`。
- `src/embedagent/frontend/gui/webapp/src/state-helpers.js:365`
  - `timelineFromTurns()` 的 step 级 event cards 来自单独 `events` 参数。
- `src/embedagent/frontend/gui/webapp/src/state-helpers.js:497`
  - 仅将 `eventCardsByStep[stepId]` 注入 step timeline。

**影响**

- bootstrap 历史时间线可能漏掉 step 级交互卡与错误卡。
- 与“`SessionHistoryAssembler` 是唯一 GUI 历史序列化器”的官方口径不完全一致。

**建议**

- 让 `timelineFromTurns()` 正式消费 `step.transitions`。
- 或者在 bootstrap payload 中提供前端可直接消费的统一 timeline DTO，避免双重投影。

## 4. 建议修复优先级

### P0

- 多会话事件串线
- `user_input` / `mode_switch_proposal` 投影错误
- replay `event_kind` 契约漂移

### P1

- GUI 默认 mode 切回 `explore`
- `step_start` / `step_end` 正式事件链路补齐或收敛
- `read_file` 错误状态规范化

### P2

- interaction 响应双路径收敛
- bootstrap 历史 step 级投影统一

## 5. 备注

- 本文档是静态审查结论记录，不等价于运行时复现报告。
- 若后续进入修复切片，应补充：
  - focused 单元测试
  - webapp runtime / projector 回归测试
  - 多会话 GUI 手动验证
  - 断线恢复与 bootstrap 一致性验证
