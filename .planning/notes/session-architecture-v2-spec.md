---
title: "EmbedAgent Session & Conversation Architecture v2"
date: "2026-05-03"
status: "DRAFT — pending review"
references:
  - "reference/claude-code/ — JSONL transcript, parentUuid chain, 6-state tool lifecycle"
  - "reference/codex/ — ThreadItem model, item lifecycle events, HistoryCell trait"
  - "reference/Roo-Code/ — Auto-approval, git checkpoints, diff view"
  - "reference/superpowers/ — Plan execution, verification gates"
  - "reference/get-shit-done/ — Wave execution, file-based state"
---

# EmbedAgent Session & Conversation Architecture v2

## 设计原则

1. **对话流是核心数据模型** — 所有信息（消息、工具调用、文件改动）都是对话中的 item
2. **扁平优于嵌套** — `Item[]` 数组替代 `Turn→Step→ToolCall` 嵌套
3. **文件级持久化** — JSONL transcript 是唯一 truth，离线友好、git 版本控制
4. **实时可观测** — 工具调用有完整生命周期事件（started→updated→completed|failed）
5. **渐进式重构** — 保持向后兼容，逐步迁移，不打破现有功能

---

## 参考工程模式综合

### 采纳模式

| 模式 | 来源 | 应用到 EmbedAgent |
|------|------|-------------------|
| JSONL typed transcript | Claude Code | `transcript.jsonl` 格式升级 |
| parentUuid message chain | Claude Code | 消息恢复和完整性验证 |
| 6-state tool lifecycle | Claude Code | `queued→in_progress→completed\|failed\|rejected` |
| ThreadItem 扁平模型 | Codex | `Session.items[]` 替代嵌套结构 |
| item.started/updated/completed | Codex | 实时流式事件 |
| HistoryCell trait | Codex TUI | 前端 Timeline 渲染模型 |
| Auto-approval + guardrails | Roo Code | `PermissionPolicy` 增强 |
| Git-based checkpoints | Roo Code | 破坏性操作前 snapshot |
| DiffView with line numbers | Roo Code + Codex | 文件改动 inline 展示 |
| Wave execution | GSD | 复杂任务的并行/依赖执行 |
| File-based state | GSD + Claude Code | `.planning/` + `.embedagent/memory/` |

### 避免模式

| 反模式 | 来源 | 避免原因 |
|--------|------|----------|
| 多 agent 事件系统 | OpenHands | 复杂度、服务器依赖、违反 Win7/离线 |
| 数据库级存储 | OpenHands + OpenCode | SQLite 设置复杂、Windows 7 脆弱 |
| 固定 workflow track | 当前 EmbedAgent | 与用户意图驱动冲突 |
| max_turns=8 硬限制 | 当前 EmbedAgent | 标杆产品无此模式 |
| 深层嵌套 turns/steps | 当前 EmbedAgent | 前端解析复杂、用户体验差 |

---

## 新架构设计

### 1. Transcript 格式（schema_version=2）

```jsonl
// Session metadata
{"schema_version":2,"type":"session_meta","session_id":"sess-abc","payload":{"current_mode":"build","started_at":"2026-05-03T10:00:00Z"}}

// User message
{"schema_version":2,"type":"user","event_id":"evt-001","seq":1,"ts":"2026-05-03T10:00:00Z","payload":{"content":"帮我实现一个排序函数","message_id":"msg-001","parent_message_id":"","turn_id":"turn-001"}}

// Assistant message (with tool calls)
{"schema_version":2,"type":"assistant","event_id":"evt-002","seq":2,"ts":"2026-05-03T10:00:01Z","payload":{"content":"我来帮你实现。首先查看现有代码结构。","message_id":"msg-002","parent_message_id":"msg-001","turn_id":"turn-001","step_id":"step-001","actions":[{"name":"list_dir","arguments":{"path":"."},"call_id":"call-001"}]}}

// Tool use started
{"schema_version":2,"type":"tool_use","event_id":"evt-003","seq":3,"ts":"2026-05-03T10:00:01Z","payload":{"tool_name":"list_dir","call_id":"call-001","arguments":{"path":"."},"parent_message_id":"msg-002","turn_id":"turn-001","step_id":"step-001","status":"in_progress"}}

// Tool result
{"schema_version":2,"type":"tool_result","event_id":"evt-004","seq":4,"ts":"2026-05-03T10:00:02Z","payload":{"tool_name":"list_dir","call_id":"call-001","success":true,"data":{"items":[]},"parent_message_id":"msg-002","turn_id":"turn-001","step_id":"step-001","status":"completed"}}

// Command execution started (Codex-style)
{"schema_version":2,"type":"command_execution","event_id":"evt-005","seq":5,"ts":"2026-05-03T10:00:03Z","payload":{"command":"clang test.c","call_id":"call-002","parent_message_id":"msg-003","status":"in_progress"}}

// Command output update (streamed)
{"schema_version":2,"type":"command_execution_update","event_id":"evt-006","seq":6,"ts":"2026-05-03T10:00:04Z","payload":{"call_id":"call-002","output":"compiling...","status":"in_progress"}}

// Command completed
{"schema_version":2,"type":"command_execution","event_id":"evt-007","seq":7,"ts":"2026-05-03T10:00:05Z","payload":{"command":"clang test.c","call_id":"call-002","parent_message_id":"msg-003","status":"completed","exit_code":0,"aggregated_output":"compilation successful"}}

// File change (patch)
{"schema_version":2,"type":"file_change","event_id":"evt-008","seq":8,"ts":"2026-05-03T10:00:06Z","payload":{"changes":[{"path":"src/sort.c","kind":"add"}],"status":"completed","parent_message_id":"msg-004"}}

// Context compaction
{"schema_version":2,"type":"compact","event_id":"evt-009","seq":9,"ts":"2026-05-03T10:00:07Z","payload":{"summary_text":"Previous context summarized","compacted_turn_count":5,"recent_turns":3}}

// Interaction (permission/user_input)
{"schema_version":2,"type":"interaction","event_id":"evt-010","seq":10,"ts":"2026-05-03T10:00:08Z","payload":{"kind":"permission","interaction_id":"perm-001","tool_name":"write_file","request_payload":{...},"status":"pending"}}
```

#### 格式改进点

| 改进 | 说明 |
|------|------|
| 显式 `type` | `user`/`assistant`/`tool_use`/`tool_result`/`command_execution`/`file_change`/`compact`/`interaction`/... |
| `parent_message_id` chain | 形成完整父子链，支持 resume 和完整性验证 |
| `status` 字段 | `in_progress`/`completed`/`failed`/`rejected`，支持实时流式 |
| `call_id` 关联 | tool_use 和 tool_result 通过 `call_id` 关联，不依赖 turn/step 嵌套 |
| 增量更新 | `command_execution_update` 支持流式输出，无需等 completion |

### 2. Session 模型（目标架构）

当前模型（嵌套）：
```python
Session
  turns: Turn[]
    steps: AgentStep[]
      tool_calls: ToolCallRecord[]
        observation: Observation
```

目标模型（扁平，向后兼容）：
```python
Session
  items: SessionItem[]           # 新增：扁平 item 数组（主要接口）
  turns: Turn[]                  # 保留：向后兼容
    steps: AgentStep[]           # 保留：向后兼容
  
@dataclass
class SessionItem:
    id: str                      # 唯一 ID
    type: str                    # user/assistant/tool_use/tool_result/...
    content: str = ""            # 文本内容
    status: str = ""            # in_progress/completed/failed/rejected
    parent_id: str = ""         # 父 item ID（形成链）
    turn_id: str = ""           # 所属 turn
    step_id: str = ""           # 所属 step（可选）
    tool_name: str = ""         # 工具名称（工具相关 item）
    call_id: str = ""           # 调用 ID（关联 tool_use/tool_result）
    data: Dict = field(default_factory=dict)  # 结构化数据
    created_at: str = ""        # 创建时间
    metadata: Dict = field(default_factory=dict)
```

**迁移策略：**
1. 阶段 1：保持 `Turn`/`Step` 模型，新增 `SessionItem` 并同步更新
2. 阶段 2：前端逐步切换到 `items[]` 接口
3. 阶段 3：后端核心逻辑逐步切换到 `items[]`
4. 阶段 4：移除旧嵌套模型（如果不再需要）

### 3. History Assembler 输出（扁平化）

当前输出（嵌套）：
```json
{"turns": [{"turn_id": "t-1", "user_text": "hi", "steps": [{"step_id": "s-1", "assistant_text": "hello", "tool_calls": [...]}]}]}
```

新输出（扁平）：
```json
{
  "items": [
    {"type": "user", "id": "msg-1", "content": "帮我实现一个排序函数", "turn_id": "turn-1"},
    {"type": "assistant", "id": "msg-2", "parent_id": "msg-1", "content": "我来查看现有代码结构。", "turn_id": "turn-1", "step_id": "step-1"},
    {"type": "tool_use", "id": "call-1", "parent_id": "msg-2", "tool_name": "list_dir", "arguments": {"path": "."}, "status": "completed", "turn_id": "turn-1", "step_id": "step-1"},
    {"type": "tool_result", "id": "msg-3", "parent_id": "call-1", "tool_name": "list_dir", "success": true, "data": {...}, "status": "completed", "turn_id": "turn-1", "step_id": "step-1"},
    {"type": "assistant", "id": "msg-4", "parent_id": "msg-3", "content": "好的，我来创建 sort.c", "turn_id": "turn-1", "step_id": "step-1"},
    {"type": "file_change", "id": "change-1", "parent_id": "msg-4", "changes": [{"path": "src/sort.c", "kind": "add"}], "status": "completed", "turn_id": "turn-1"}
  ],
  "current_interaction": null,
  "integrity": {"status": "healthy", ...}
}
```

**前端收益：**
- Timeline 直接遍历 `items` 渲染，无需 `turns → steps → tool_calls` 解析
- 每个 item 是独立渲染单元，采用 Codex HistoryCell 模式
- 支持实时更新：收到 `item.updated` 事件时直接更新对应 item

### 4. Tool 生命周期（6-state）

基于 Claude Code 和 Codex 的综合：

```
queued          → 已请求，等待执行
in_progress     → 正在执行（可流式更新）
completed       → 执行成功
failed          → 执行失败（有错误信息）
rejected        → 用户拒绝（权限未批准）
discarded       → 被系统丢弃（如用户取消）
```

事件流：
```
tool_call (assistant 请求) 
  → tool_use started (status: in_progress)
    → [可选] tool_use updated (增量输出)
    → tool_result (status: completed|failed)
  → 或 permission_required (等待用户)
    → tool_use rejected (status: rejected)
  → 或 user cancelled
    → tool_use discarded (status: discarded)
```

### 5. Session 恢复策略

基于 Claude Code parentUuid chain + best_effort 容错：

```python
class SessionRestorer:
    def restore(self, events, best_effort=True):
        # 1. 按 seq 排序（防御性）
        # 2. 构建 parent_uuid → item 索引
        # 3. 逐条解析：
        #    - 成功：添加到 session
        #    - 失败：如果 best_effort=True，记录警告并跳过；否则抛出异常
        # 4. 验证 parent chain：缺失的 parent 在 best_effort 模式下留空
        # 5. 返回恢复结果（成功数/跳过数/原因）
```

### 6. Diff 展示规范

基于 Codex TUI + Roo Code：

**最小可行：**
- 统一 diff 格式（unified diff）
- 行号 + gutter 标记（`+` / `-` / ` `）
- 语法高亮（highlight.js）
- 暗色/亮色主题自适应

**进阶（Phase 2）：**
- 主题感知配色（暗色 `#213A2B` 绿 / `#4A221D` 红；亮色 pastel）
- 跨 hunk 语法高亮保持
- 可折叠/展开 hunks

---

## 实施路线图

### Phase 1: Session 基础重构（当前）

#### 任务 1: Transcript 格式升级（向后兼容）
**修改文件：**
- `src/embedagent/session.py` — 添加 `MessageType`, `SessionItem`
- `src/embedagent/transcript_store.py` — 支持 schema_version=2，自动检测类型
- `src/embedagent/query_engine.py` — 写入时使用新类型

**验收：**
- 新 session 的 transcript 使用 schema_version=2
- 旧 transcript（schema_version=1）仍可正常读取
- `parent_message_id` 形成完整链

#### 任务 2: Session 恢复容错
**修改文件：**
- `src/embedagent/session_restore.py` — 添加 `best_effort` 模式

**验收：**
- 损坏单条记录不中断恢复
- 恢复完成报告成功/跳过数
- 现有测试全部通过

#### 任务 3: History Assembler 扁平化
**修改文件：**
- `src/embedagent/session_history.py` — 添加 `build_flat_timeline()`

**验收：**
- 输出扁平 `items[]` 数组
- 每个 item 有完整 type/id/parent_id/status
- 保持旧 `build()` 方法可用

#### 任务 4: 集成验证
**新增文件：**
- `tests/test_transcript_v2.py` — transcript 写入/读取/恢复测试
- `tests/test_session_restore_fault_tolerance.py` — 容错恢复测试
- `tests/test_history_flat.py` — 扁平 history 测试

**验收：**
- 完整 session 写入→恢复→history assembly 端到端测试通过
- 损坏记录场景测试通过
- 1000+ 条消息性能测试通过

### Phase 2: 对话流 & GUI 重构

#### 任务 5: Timeline 扁平化渲染
**修改文件：**
- `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx` — 移除嵌套，直接渲染 items
- `src/embedagent/frontend/gui/webapp/src/store.js` — 添加 item type 处理

**验收：**
- 工具调用 inline 展示（6-state lifecycle）
- 移除 Step N 折叠面板
- Diff preview 内联展示

#### 任务 6: DiffView 升级
**修改文件：**
- `src/embedagent/frontend/gui/webapp/src/components/DiffView.jsx`

**验收：**
- 行号 + gutter 标记
- 暗色/亮色主题自适应
- 语法高亮集成

#### 任务 7: 实时流式更新
**修改文件：**
- `src/embedagent/frontend/gui/webapp/src/App.jsx` — 处理 `item.updated` 事件
- `src/embedagent/inprocess_adapter.py` — 发送增量更新事件

**验收：**
- 命令执行实时显示输出
- 文件读取显示进度
- 工具调用状态实时更新

### Phase 3: Mode & Harness 重构

#### 任务 8: Mode 权限契约化
**修改文件：**
- `src/embedagent/modes.py` — 移除预设 workflow 描述
- `src/embedagent/harness/registry.py` — track 可为空
- `src/embedagent/harness/runner.py` — 不无条件生成 task graph

**验收：**
- build 模式说"hi"不触发构建
- 明确构建指令才生成 task graph

#### 任务 9: 终止策略重构
**修改文件：**
- `src/embedagent/query_engine.py` — 移除 `max_turns=8` 硬限制
- `src/embedagent/guard.py` — 增强死循环检测

**验收：**
- 无固定 step 限制
- 模型输出 `attempt_completion` 信号
- Guard 检测连续重复 tool 调用

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 格式升级破坏现有 session | 高 | 保持 schema_version=1 读取能力；新 session 用 v2 |
| 前端/后端格式不一致 | 高 | 先改后端，提供兼容层；前端逐步切换 |
| 性能退化（大量 items） | 中 | 虚拟滚动、分页加载、增量更新 |
| 测试覆盖不足 | 高 | 每个任务配对应测试；集成测试覆盖端到端 |
| Win7 兼容性 | 高 | 不使用新 API；文件锁用 threading.RLock；路径用 pathlib |

---

## 决策记录

1. **扁平 Item[] vs 嵌套 Turn→Step** → 采用扁平，逐步迁移
2. **JSONL vs SQLite** → JSONL（离线友好、git 版本控制）
3. **6-state vs 2-state tool lifecycle** → 6-state（更好的 UX）
4. **固定 step limit vs 完成度自判** → 完成度自判 + Guard 兜底
5. **Inline diff vs 侧边栏 diff** → Inline（对话流为中心）

---

## 相关文档

- `.planning/research/questions.md` — RQ-001 调研问题
- `.planning/phases/01-ui-ux-harness-research/01-RESEARCH.md` — 参考工程深度分析
- `.planning/notes/gui-harness-refactor-direction.md` — 重构设计方向
- `.planning/todos/pending/refactor-mode-intervention.md` — Mode 重构任务
- `.planning/todos/pending/refactor-termination-strategy.md` — 终止策略重构任务
