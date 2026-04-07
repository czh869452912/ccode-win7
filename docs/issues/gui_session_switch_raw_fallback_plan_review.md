# Session History Single-Source Cutover Plan 审查报告

> 审查对象：`docs/superpowers/plans/2026-04-07-session-history-single-source-cutover.md`
> 审查日期：2026-04-07

---

## 1. 总体结论

这是一个高质量、架构正确的根治方案。它精准定位了问题本质——`timeline.jsonl` 被错误地同时用作"传输日志"和"历史数据库"，导致截断窗口、永久删除、职责错位三重失效。

方案提出的分层架构与业界主流实现（包括 Claude Code）一致：
- `transcript.jsonl` 为唯一持久真相源
- `Session.turns` 为活结构化对象
- 专用 `SessionHistoryAssembler` 为读取模型
- `timeline.jsonl` 降级为纯传输/回放日志

具备可扩展性，建议按方案推进。

---

## 2. 分项评估

### 2.1 思路合理性：A+

从"补丁参数调优"（如把 200 改大）转向了数据所有权重构，是唯一正确的路径。

- 核心决策正确：对 CQRS 原则的正确应用。
- 参考实现对齐：Claude Code 的历史视图通过远程 API 返回已结构化的 `SDKMessage[]`，本地 transport 只做实时通信和断线续传。本方案虽未使用远程后端，但职责划分与其完全一致。
- Bootstrap 端点设计极佳：将 `App.jsx` 中 4 个分散 fetch 合并为 `/api/sessions/{id}/bootstrap`，消除了 split-brain 激活，大幅简化了前端状态机。

### 2.2 设计准确性：A

关键设计点基本准确，但有细节需进一步推敲：

| 设计点 | 评价 |
|---|---|
| `session_history.py` 专用 Assembler | 非常正确，避免 adapter 臃肿，便于未来支持分页、缓存。 |
| UI Metadata 在 serialization time 推导 | 方向正确，但引入了**时变性风险**。若 tool 在会话创建后被移除或重命名，恢复后的历史可能找不到 label/category。Assembler 需提供安全降级。 |
| Projection Source 词汇替换 | 清理了技术债务，语义清晰。 |
| Auto-Hydrate | 理念正确，但方案对**具体触发点**描述较模糊——是在 `CoreInterface` 新增 `ensure_session_active`，还是侵入现有方法内部？实现前需明确钩子位置。 |

### 2.3 问题覆盖与封堵：A+

方案完整封堵了 issue 中分析的全部失效模式及同类连锁问题：

- `limit=200` 窗口截断：彻底免疫
- `max_events=2000` 永久截断：彻底免疫
- 长 Session 不可逆 raw fallback：彻底免疫
- 切换 Session 后的 split-brain：通过 bootstrap endpoint 解决
- resumed vs active 历史不一致：两者走同一 assembler

额外封堵了未来问题：transport log 与历史渲染解耦，允许更激进的 trim/rotation；明确 restore 失败显式报错而非静默降级。

---

## 3. 潜在风险（可控，但需提前防范）

### 风险 A：`SessionRestorer` 的容错能力成为单点故障

改造后，GUI 激活**完全依赖** `transcript.jsonl -> SessionRestorer -> Session` 链路。当前 `SessionRestorer.restore()` 非常严格，任何 mismatch 都会 break 并返回 `stop_reason`。若生产环境存在格式略有偏差的旧 transcript，改造后这些 session 会直接显示"历史不可用"，而非之前的 raw fallback。

**建议**：在方案中增加 "Transcript Corruption Handling" 策略。若 restore 因尾部损坏失败，允许返回 **partial history**（已恢复部分 + `integrity` 字段说明 stop reason），而非 strict stop。

### 风险 B：工具元数据的时变性

`_tool_event_metadata` 依赖当前 `tool_catalog_entry` 和 `runtime_environment_snapshot`。若某个 MCP tool 在会话创建后被移除，恢复时 assembler 可能找不到 catalog entry，导致前端渲染异常。

**建议**：在 `session_history.py` 中增加防御：若找不到 entry，默认 `tool_label = tool_name`，`permission_category = ""`，`supports_diff_preview = False`。DTO 中始终保留原始 `tool_name` 和 `call_id`。

### 风险 C：大 Session 的性能

`SessionRestorer.restore()` 和 assembler 均为 Python 顺序遍历。对包含数千条消息的极长 session，可能达到数百毫秒甚至秒级，阻塞 GUI bootstrap。

**建议**：Phase 1 就应加入性能基准测试（如 500 turns、2000 events 的 session 从 restore 到 DTO 输出的耗时）。若超过 200ms，应引入惰性分页或 memory-mapped 缓存。

### 风险 D：前端实时事件与 Bootstrap 历史的合并

`projector.js` 负责 overlay 实时事件。若 bootstrap 中 step 状态为 `completed`，而 websocket `step_end` 因延迟在 bootstrap 后到达，projector 需能**幂等合并**（基于 `step_id` / `call_id` 去重），而非盲目追加。

**建议**：审核 `projector.js` 的合并逻辑，确保使用稳定 ID 进行 upsert。

---

## 4. 与 Claude Code 参考实现的对比

| 维度 | Claude Code | 本方案 |
|---|---|---|
| 历史来源 | 远程 API `/v1/sessions/{id}/events`，返回结构化 `SDKMessage[]` | 本地 `transcript.jsonl -> SessionRestorer -> Session -> Assembler -> bootstrap` |
| 分页 | 原生支持（`HISTORY_PAGE_SIZE=100`，`before_id` 游标） | 暂不分页，一次性返回全部 |
| 本地 event log | 仅做 transport replay / 断线续传 | `timeline.jsonl` 职责完全一致 |
| 分离度 | 历史 = 远程数据库；实时 = SSE/WebSocket | 历史 = transcript 文件；实时 = timeline 文件 + WebSocket |

结论：本方案在本地嵌入式场景下，实现了与 Claude Code 同等级别的职责分离。唯一的结构性差异是 Claude Code 有远程后端天然支持分页，本方案当前可暂不分页（未来如需可通过 assembler 扩展）。

---

## 5. 推进建议（供方案微调）

1. **明确 Auto-Hydrate 的 API 层钩子**
   建议在第 9.2 节中明确：在 `inprocess_adapter.py`（或 `CoreInterface` 实现层）新增 `def _ensure_session_active(self, session_id: str) -> ManagedSession:`，内部逻辑为：若不在内存则调用 `resume_session`，然后返回。所有 read 方法统一调用它。

2. **为 History Assembler 增加防御性元数据策略**
   在 `session_history.py` 的 tool serialization 中规定：若 tool catalog 中不存在该 `tool_name`，默认 `tool_label = tool_name`，`permission_category = ""`，`supports_diff_preview = False`。

3. **为 `SessionRestorer` 增加 Partial Restore 模式**
   评估当 `stop_reason != ""` 时的行为：建议允许返回 partial turns + integrity 信息，用户通常更想看到"损坏之前的对话"，而非完全空白。

4. **增加性能验收标准**
   在第 11 节的 verification 中加入：1000-turn session 的 bootstrap API 响应时间 < 500ms（在目标硬件上）。

5. **Bootstrap endpoint 保留 replay metadata**
   方案 4.4 提到返回 `replay transport metadata`，建议明确字段如 `first_seq`、`last_seq`、`status`，使前端 `recoverSessionReplay` 知道从哪个 seq 开始续传。

---

## 6. 最终建议

该方案**思路清晰、架构正确、覆盖全部已发现的失效路径**，能够对齐参考实现的最佳实践。主要需警惕 `SessionRestorer` 的容错能力和大 session 的性能。只要在这两点上做好防御性设计和基准测试，本次 cutover 将彻底根治 raw fallback 问题，并为将来的分页、远程同步打下基础。建议按方案推进，无需推翻。
