# GUI 切换 Session 后显示 RAW FALLBACK 的根因分析

## 1. 问题摘要

在 EmbedAgent GUI 上进行一个 Session 的对话，新建另一个 Session，然后立即点击回到之前的 Session，Timeline 区域会整体降级显示：

```
raw fallback: showing raw timeline events
```

并且所有 Step 都带有 `RAW FALLBACK`（或 `raw_event`）标签。这不是前端缓存或状态管理的 bug，而是**后端 timeline 重建机制存在架构级缺陷**。

---

## 2. 触发路径

用户切回旧 Session 时，前端 `App.jsx:176` 会请求 `/api/sessions/{id}/timeline`。后端 `inprocess_adapter.py:676` 的 `build_structured_timeline` 尝试从 raw events 重建结构化 turns。如果读取的事件窗口中**找不到任何 `turn_start` 事件**，后端返回 `projection_source: "raw_events"` 和空 `turns` 数组。前端检测到 `turns` 为空，回退到 `timelineFromEvents()`，为每个 item 硬编码 `projectionSource: "raw_events"`，从而触发全屏的 raw fallback UI。

---

## 3. 根因分析（三层相互强化的失效模式）

### 3.1 失效模式 A：`limit=200` 的窗口截断

`build_structured_timeline` 默认只读取 timeline store 的**最后 200 条事件**：

```python
# src/embedagent/inprocess_adapter.py:694
raw_events = self.timeline_store.load_events(state.session.session_id, limit=limit)
has_turn_start = any(r.get("event") == "turn_start" for r in raw_events)
```

```python
# src/embedagent/session_timeline.py:65-72
def load_events(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    ...
    return items[-limit:]
```

一个包含多个 tool call、reasoning delta、assistant delta 的较长回合，其事件数量可以轻易超过 200 条。此时当前回合的 `turn_start` 事件落在返回窗口之外，`has_turn_start` 为 `False`，整个 Session 被判定为"legacy"并降级为 raw fallback。

### 3.2 失效模式 B：Timeline 文件的永久截断（2000 条上限）

即使某轮事件不到 200 条，timeline JSONL 文件本身也会被 aggressive trim：

```python
# src/embedagent/session_timeline.py:140-148
def _trim_if_needed(self, path: str) -> None:
    ...
    if len(lines) <= self.max_events:
        return
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(lines[-self.max_events :])   # max_events = 2000
```

当 Session 总事件超过 2000 条后，**早期的 `turn_start` 事件会从磁盘上永久消失**。从此以后，无论 `limit` 设多大（只要不读取全量文件），该 Session 的 `build_structured_timeline` 都会因为检测不到 `turn_start` 而返回 raw fallback。这意味着：**长 Session 会不可逆地陷入 raw fallback 状态**。

### 3.3 失效模式 C：架构级职责错位——用有损传输日志重建权威历史视图

最深层的缺陷是设计层面的：**`build_structured_timeline` 完全忽略了内存中已经存在的结构化权威数据**。

`Session` 对象本身就维护着一个完整的 `turns` 列表（`src/embedagent/session.py:225`），其中每轮包含 `user_message`、`assistant_message`、`steps`、`tool_calls`、`transitions` 等。Runtime 的所有操作都直接基于这个 `turns` 结构。

但 `build_structured_timeline` 不使用它，而是选择从一个**被截断、被窗口限制、仅用于事件回放**的 append-only log 中重新解析出 turns。这相当于用日志文件来反推数据库的当前状态。

| 已有的权威数据源 | `build_structured_timeline` 的做法 |
|---|---|
| `session.turns` — 结构化、完整、在内存中 | 完全忽略 |
| `timeline.jsonl` — 有损、截断、仅用于回放 | 作为唯一真相源 |

---

## 4. 与业界实现对标的差距

在参考实现（`reference/claude-code`）中，会话历史的管理方式与 EmbedAgent 当前实现存在本质差异：

- **`sessionHistory.ts`** — 历史视图通过远程 API `/v1/sessions/{id}/events` 获取，返回的是**已结构化的消息列表**（`SDKMessage[]`），而非从本地有损日志重新 parse。
- **`replBridgeTransport.ts`** — 本地的 event stream（SSE/WebSocket）仅用于**实时通信**和**断线重连时的序列号续传**。它不承担"生成结构化历史视图"的职责。

**核心差异总结：**

| Claude Code | EmbedAgent（当前） |
|---|---|
| 历史视图 = 独立持久化的结构化消息 | 历史视图 = 从被截断的本地 append-only log 重新 parse |
| 本地 event log 只做实时传输与断线恢复 | 同一个 `timeline.jsonl` 既做传输回放，又做结构化重建 |

EmbedAgent 的问题本质是**架构职责错位**：用传输日志兼任历史数据库。

---

## 5. 为什么 `session.turns` 目前还不能直接替代 event log

进一步检查 `session.py` 的数据模型发现，`ToolCallRecord`（`session.py:94`）仅包含以下字段：

```python
@dataclass
class ToolCallRecord:
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "pending"
    observation: Optional[Observation] = None
    started_at: str = ""
    finished_at: str = ""
    progress: List[Dict[str, Any]] = field(default_factory=list)
```

但 `build_structured_timeline` 返回给前端的数据格式还需要以下 UI 元数据：

- `tool_label`
- `permission_category`
- `supports_diff_preview`
- `runtime_source`
- `resolved_tool_roots`

这些字段目前只在 event emit 时通过 `_tool_event_metadata(tool_name)` 动态生成并写入 `timeline.jsonl`（`inprocess_adapter.py:1720`、`2300` 附近），却**从未被持久化到 `Session.turns` 的数据结构中**。

这意味着：如果直接把 `build_structured_timeline` 改为读取 `session.turns`，会在前端丢失权限分类、diff 预览支持等信息。这也解释了为什么系统被迫依赖 event log 来弥补——**数据模型本身不完整**。

---

## 6. 为什么前端"之前看起来正常"

当 Session 处于活跃状态且没有被切换走时，前端并不依赖 `/timeline` API。它通过 WebSocket 实时事件（`turn_start`、`step_start`、`tool_start`、`tool_finish`、`step_end`、`turn_end`）在 reducer 中**增量构建** timeline（`store.js:166-376`）。这些增量 item 的 `projectionSource` 是 `"step_events"`，因此显示正常。

一旦用户切走再切回，前端状态被 `session_activated` 完全重置（`store.js:73-109`），timeline 必须从后端 `build_structured_timeline` 重新获取。此时后端因前述的截断/缺失问题失败，问题才暴露。

---

## 7. 关键代码位置速查

| 文件 | 行号 | 作用 |
|---|---|---|
| `src/embedagent/inprocess_adapter.py` | 676-702 | `build_structured_timeline` 入口，决定 structured / raw fallback |
| `src/embedagent/inprocess_adapter.py` | 694-696 | `has_turn_start` 判断，触发 fallback 的关键条件 |
| `src/embedagent/session_timeline.py` | 65-72 | `load_events(limit=200)`，只返回最后 200 条事件 |
| `src/embedagent/session_timeline.py` | 140-148 | `_trim_if_needed`，永久删除超过 2000 条的旧事件 |
| `src/embedagent/frontend/gui/webapp/src/App.jsx` | 176-205 | `loadSession`，调用 timeline API 并决定使用 `timelineFromTurns` 还是 `timelineFromEvents` |
| `src/embedagent/frontend/gui/webapp/src/state-helpers.js` | 60-89, 118-128 | `describeProjectionBadge` 和 `describeTimelineProjectionNotice`，生成 fallback UI 文本 |
| `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx` | 233-236, 356, 370-379 | 实际渲染 "raw fallback" 提示和 step badge |
| `src/embedagent/session.py` | 94-105 | `ToolCallRecord`，缺少 UI 元数据字段 |
| `src/embedagent/session.py` | 225 | `Session.turns`，已有的结构化权威数据 |

---

## 8. 修复方案（三层综合改造，非补丁）

单点调参（如把 `limit=200` 改成 `limit=2000`）**不可接受**：它无法解决 `_trim_if_needed` 的 2000 条永久截断，且 CPU/IO 成本会随着 Session 长度线性劣化。

正确的修复必须是**数据模型层 + API 层 + 职责重构**的组合改造：

### 层 1：补齐 `session.turns` 的数据模型

在 `ToolCallRecord` 中增加 UI 展示所需的元数据字段：`tool_label`、`permission_category`、`supports_diff_preview`、`runtime_source`、`resolved_tool_roots`。

涉及修改：
- `session.py`：`ToolCallRecord` dataclass 定义
- `inprocess_adapter.py`：在 `on_tool_start`、`_execute_tool_from_command`、以及 command/recipe 执行路径中，将 `_tool_event_metadata` 的结果同步写入 `session.turns`

### 层 2：让 `build_structured_timeline` 以 `session.turns` 为唯一真相源

重构 `build_structured_timeline`，**停止扫描 event log**，改为直接从 `state.session.turns` 序列化为现有的 API response 格式（`turns` 数组 + `projection_source: "step_events"`）。

这样做的好处：
- 彻底免疫 `limit=200` 和 `max_events=2000` 的截断
- 性能与 Session 长度无关
- 与 runtime 状态完全一致

### 层 3：明确 `timeline.jsonl` 的职责边界

将 `timeline.jsonl` 降级为**纯回放/恢复日志**。保留其现有的截断策略（甚至可进一步收紧），因为它的合法消费者应仅限：
- WebSocket 实时推送
- 进程重启后的 event replay（`recoverSessionReplay`）
- 调试/审计用途

**历史视图不再从中读取。**

---

## 9. 结论

**该问题不是前端 bug，而是后端深层设计缺陷。**

`build_structured_timeline` 试图从一个被 `limit=200` 窗口限制、且被 `max_events=2000` 永久截断的 append-only event log 中重建结构化 turns，而忽略了内存中本来就有完整权威的 `session.turns` 数据。与此同时，`session.turns` 的数据模型缺少 UI 元数据，导致系统不得不依赖 event log 来补全，最终形成了今天的脆弱局面。

修复应优先采用**三层综合改造**：先补齐 `ToolCallRecord` 的数据模型，再让 `build_structured_timeline` 直接从 `session.turns` 生成结构化 timeline，从而将 `timeline.jsonl` 放回它应该待的位置——纯传输/回放日志。
