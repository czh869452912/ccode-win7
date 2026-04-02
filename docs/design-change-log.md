# EmbedAgent 设计与变更跟踪

> 更新日期：2026-04-02
> 用途：记录关键设计变更、影响范围、关联文档和后续动作

---

## 1. 使用规则

本文件不是完整 changelog，也不是 ADR 替代品。

它的定位是：

- 记录“已经发生的关键设计变化”
- 标明“哪些文档受影响”
- 指向相关 ADR、方案文档、实现任务

适合记录的变更类型：

- 架构分层变化
- 模式系统变化
- Python / 打包 / 运行时主线变化
- 工具链或质量门设计变化
- 文档治理机制变化

若某个变更足够重大且具有长期影响，应同时新增 ADR。

---

## 2. 变更记录格式

建议每次新增一条记录，包含：

- `ID`
- `日期`
- `变更主题`
- `变更摘要`
- `影响范围`
- `关联文档`
- `是否需要 ADR`
- `后续动作`

---

## 3. 当前变更记录

### DC-055

- 日期：2026-04-02
- 变更主题：discard-on-retry 已扩展到后续 batch
- 变更摘要：
  - `QueryEngine` 现在会把“当前 batch 已出现 discarded”视为当前 assistant plan 已不完整的明确边界
  - 在这种情况下，同一条 assistant reply 中后续 batch 的 action 不再继续真实执行，而是统一落 `discarded` tool_result
  - 新增回归覆盖“前一个并行读 batch 已 discarded，后续 edit batch 必须 discarded 且不得改文件”的 transcript 语义
- 影响范围：
  - discard-on-retry transcript contract
  - 多 batch assistant plan 的安全边界
  - 写动作在部分失败后的继续执行策略
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 在真实 C 工程回归里验证 compile/test/diagnose 链路上的 discard-on-retry 体验
  - 评估是否要把 discarded 的 reason contract 再细分为 cancel / retry 两类

### DC-054

- 日期：2026-04-02
- 变更主题：并行执行器现在直接观察 cancel event
- 变更摘要：
  - `StreamingToolExecutor` 现在在 worker 获得并发槽位后，会直接检查 cancel event，而不再只等主线程处理 update 后再转述 `discard()`
  - 这让 `max_parallel_tools>1` 时尚未启动的 queued action 在取消后保持 `discarded`，不会因为主线程观察延迟而偷偷变成已启动的 `interrupted`
  - 新增高并发回归，覆盖“两条慢读已启动、第三条排队、取消后第三条仍应 discarded”的 transcript 语义
- 影响范围：
  - 并行 tool batch 的取消边界
  - discard vs interrupted 的 transcript 语义
  - 高并发 focused regression
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续覆盖更复杂的 multi-batch retry 组合边界
  - 评估是否要把 cancel/discard contract 明确写成独立文档

### DC-053

- 日期：2026-04-02
- 变更主题：Windows 长命令中断已切到进程组 + CTRL_BREAK_EVENT
- 变更摘要：
  - `run_command` 现在在 Windows 下以新进程组启动子进程，取消时优先发送 `CTRL_BREAK_EVENT`
  - 这让长命令用户中断不再依赖 `taskkill` 成功，避免当前运行环境里 `taskkill` 返回 `Access denied` 时仍然要等命令自然结束
  - Query loop 现在可以更稳定地得到非 synthetic 的 interrupted observation，并及时以 `aborted` transition 收束
- 影响范围：
  - Tool runtime 的 Windows 中断语义
  - 长命令取消时的端到端响应延迟
  - interrupt/retry focused regression
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续覆盖更高并发下的 abort/retry 组合边界
  - 评估 compile/test/toolchain 类工具是否也需要复用更细的 runtime interrupt contract

### DC-049

- 日期：2026-04-02
- 变更主题：中断后的 synthetic interrupted tool_result 已接入 transcript 主线
- 变更摘要：
  - 当会话在 `tool_started` 之后被取消时，`QueryEngine` 现在会生成 synthetic interrupted observation，而不是让工具调用只留下 `tool_call` 没有结果
  - 该 synthetic result 会同步写入 transcript、session observation、timeline 和 adapter 的 `tool_finished` 事件
  - 会话最终仍以 `aborted` transition 收束，但前端和恢复链现在都能看到更完整的“中断发生在工具执行阶段”语义
- 影响范围：
  - Query loop 中断语义
  - Transcript 完整性
  - Adapter / timeline 的取消态投影
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 discard-on-retry transcript 语义
  - 收紧多 tool batch 下的 abort 边界
  - 评估长命令 / tool runtime 的真实 interrupt 行为

### DC-050

- 日期：2026-04-02
- 变更主题：discarded synthetic result 不再误触发 guard stop
- 变更摘要：
  - parallel batch 中被丢弃的 synthetic `discarded` tool_result 仍会写入 transcript 和 session observation
  - `LoopGuard` 现在不会把 `discarded` / `interrupted` synthetic result 当成真实工具失败累计
  - 这避免了“第一个只读工具失败，后续被丢弃的工具结果反而把整轮提前打成 `guard_stop`”的错误语义
- 影响范围：
  - parallel tool batch 的失败路径
  - QueryEngine 的 retry/abort 行为
  - transcript 中 synthetic result 的语义一致性
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补多 tool batch 下的 abort 边界
  - 明确 discard-on-retry 的更细 transcript contract

### DC-051

- 日期：2026-04-02
- 变更主题：并行 tool batch 已切到流式 start/result writeback
- 变更摘要：
  - `StreamingToolExecutor` 的并行批次不再一次性收集完结果后整体返回，而是改为流式发出 `start` / 有序 `result`
  - 这让 `QueryEngine` 能在看到 `tool_started` 后及时 `discard()` 尚未开始的后续 action
  - 在 `max_parallel_tools=1` 等受控场景下，当前已验证“首个 action interrupted、后续未开始 action discarded”的 transcript 语义
- 影响范围：
  - Tool batch 执行时序
  - QueryEngine 的 cancel/discard 协同
  - interrupt/retry transcript 一致性
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补更高并发下的 abort/retry 组合边界
  - 评估是否需要显式 progress event / result buffering contract 文档

### DC-052

- 日期：2026-04-02
- 变更主题：tool_call transcript 改为在 assistant action 阶段统一落盘
- 变更摘要：
  - `tool_call` transcript event 不再依赖实际 start 时机，而是在 assistant 产出 action 后就按原始顺序统一写入
  - 这保证了后续 action 即使因取消而变成 `discarded`，仍然有完整的 `tool_call -> tool_result` transcript 链路
  - `SessionRestorer` 也已避免为同一 `call_id` 重复创建 `ToolCallRecord`
- 影响范围：
  - Transcript 完整性
  - Resume replay 的 tool-call 重建
  - 并行 batch 取消场景的可审计性
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续验证更高并发下 `tool_call` / `tool_result` 顺序与 retry 组合语义

### DC-048

- 日期：2026-04-02
- 变更主题：Resume truth source switched to transcript replay
- 变更摘要：
  - 新增 append-only session transcript 持久化，路径为 `.embedagent/memory/sessions/<session_id>/transcript.jsonl`
  - 新增 `SessionRestorer`，可按 transcript event replay 重建 `Session`
  - `resume_session()` 已从 summary-driven reconstruction 切到 transcript-driven replay
  - `summary.json` / snapshot 数据已降级为 derived projection，不再作为恢复真相源
- 影响范围：
  - Session persistence
  - Resume 语义
  - Context replacement / compact snapshot 持久化
  - Frontend snapshot/timeline projection 的恢复来源
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/superpowers/specs/2026-04-02-full-transcript-persistence-design.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 补 interrupt / synthetic tool_result / discard-on-retry 的 transcript 语义
  - 补更贴近真实工程的 transcript restore 集成回归
  - 继续收缩 summary-only 兼容路径

### DC-046

- 日期：2026-04-02
- 变更主题：QueryEngine 增加 reactive compact retry
- 变更摘要：
  - `QueryEngine` 现在会识别 `prompt/context too long` 一类 LLM 错误，并在同一步内触发一次内部 `compact_retry`
  - retry 前会尽量落下 `CompactBoundary`，随后以更紧的 compact budget 重组上下文，再自动重试一次模型调用
  - compact retry 仍保持原始 mode 作为工具过滤和 workspace intelligence 选证依据，不把 `compact` 暴露成用户可切换 mode
- 影响范围：
  - Query loop 状态迁移
  - Context pipeline 的内部 compact 策略
  - 长任务上下文超限后的恢复体验
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 把 retry 触发条件从字符串匹配升级为更稳的 provider/error contract
  - 继续补 LLM compact 与多次 retry 的边界策略
  - 补 adapter/session snapshot 对 compact retry 的显式可观测性

### DC-047

- 日期：2026-04-02
- 变更主题：compact retry 已投影到 snapshot 与 timeline
- 变更摘要：
  - `SessionSummaryStore` / `SessionSnapshot` 现在会暴露 `last_transition_reason`、`recent_transition_reasons` 与 `compact_retry_count`
  - `InProcessAdapter` 在检测到 `reactive_compact_retry` 上下文装配时，会额外发出 `compact_retry` event，前端和调试工具可直接从 timeline 观察到自动压缩重试
  - 这让 compact retry 不再只是 loop 内部细节，而是成为可调试、可回归验证的显式状态
- 影响范围：
  - Session summary / snapshot 协议
  - Timeline event 可观测性
  - 前端调试和 QA 回归
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 决定 GUI inspector 是否要给 compact retry 单独展示卡片/徽标
  - 继续把更多 transition 信息投影为结构化 timeline 语义

### DC-048

- 日期：2026-04-02
- 变更主题：structured timeline 保留 compact retry transitions
- 变更摘要：
  - `build_structured_timeline()` 现在会在 turn/step 级别保留 `transitions`
  - `compact_retry`、`context_compacted`、`mode_changed` 这类事件不再只存在于 raw events，而能进入结构化 timeline 供 GUI 直接消费
  - 这让 step-based timeline 和 snapshot 对同一条状态机变化的观察口径开始收敛
- 影响范围：
  - 结构化时间线协议
  - GUI step timeline / inspector 展示能力
  - 前端回归测试口径
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 决定 transitions 在 GUI 中的展示形式
  - 继续把更多 loop transition 结构化到 step/turn 记录中

### DC-049

- 日期：2026-04-02
- 变更主题：structured timeline 保留 waiting-state transitions
- 变更摘要：
  - `build_structured_timeline()` 现在会把 `user_input_required` / `permission_required` 作为 turn/step 级 transition 保留下来
  - 当会话进入等待态时，structured timeline 的 turn 状态也会同步更新为 `waiting_user_input` 或 `waiting_permission`
  - 这让 pending interaction 不再只靠 snapshot 判断，structured timeline 也能完整表达“为什么停住了”
- 影响范围：
  - 结构化时间线协议
  - pending interaction 的前端展示能力
  - 调试与回归测试口径
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续把 `guard_stop / max_turns / aborted` 等终止态也统一投影到 structured timeline transitions

### DC-050

- 日期：2026-04-02
- 变更主题：structured timeline 开始保留终止态 transitions
- 变更摘要：
  - `turn_end` 的 `termination_reason` 现在会在非 `completed` 情况下同步投影到 structured timeline transitions
  - 目前已覆盖 `max_turns`，同一条规则也为后续 `guard_stop / cancelled` 留好了入口
  - 这样 structured timeline 不再只靠 turn status 文本表达终止原因，而是能把它当成显式状态机事件
- 影响范围：
  - 结构化时间线协议
  - loop 终止态的前端可观测性
  - 调试与回归测试口径
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 补 `guard_stop / cancelled` 的回归测试
  - 决定 GUI 是否对终止态 transitions 做统一展示

### DC-051

- 日期：2026-04-02
- 变更主题：structured timeline 终止态补齐停止原因文本
- 变更摘要：
  - `turn_end` / `session_finished` 现在会携带 `error` 字段，把 loop 终止时的原因文本显式传给前端
  - structured timeline 中由终止态生成的 transition 会直接消费这段文本，而不再只暴露一个无说明的 `kind`
  - 这让 `max_turns` 以及后续 `guard / cancelled` 的展示和排障信息更完整
- 影响范围：
  - turn_end / session_finished 事件契约
  - structured timeline transition 语义
  - 前端调试与展示质量
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 `guard_stop / cancelled` 的专项测试

### DC-052

- 日期：2026-04-02
- 变更主题：snapshot 补齐最后 transition 的原因文本
- 变更摘要：
  - `SessionSummaryStore` / `SessionSnapshot` 现在会暴露 `last_transition_message`
  - adapter 在会话结束后会重新持久化一次最终 session，使 `max_turns` 等最后才落下的 transition 进入 summary / snapshot
  - 这让前端无需强依赖 timeline，也能直接解释当前 session 的最后状态
- 影响范围：
  - Session summary / snapshot 协议
  - 会话结束时的持久化链路
  - 前端状态说明质量
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 `guard_stop / cancelled` 的 snapshot/timeline 一致性测试

### DC-053

- 日期：2026-04-02
- 变更主题：snapshot 补齐结构化 recent transitions
- 变更摘要：
  - `SessionSummaryStore` 现在会持久化 `recent_transitions`，每项包含 `reason`、`message` 与 `display_reason`
  - `SessionSnapshot` 已投影这一结构化列表，前端可直接消费最近几条状态迁移，而不必先解析 raw timeline
  - 对历史 summary，如果 `recent_transitions` 尚未带 `display_reason`，adapter 也会在读取 snapshot 时即时补齐
  - 这让 snapshot 和 structured timeline 之间的可观测性口径进一步靠近
- 影响范围：
  - Session summary / snapshot 协议
  - 前端状态面板与调试能力
  - transition 相关回归测试
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 `guard_stop / cancelled` 的专项回归
  - 视 GUI 需求决定 recent transitions 的展示排序与截断策略

### DC-054

- 日期：2026-04-02
- 变更主题：snapshot 补齐 display 级 transition reason
- 变更摘要：
  - `SessionSnapshot` 现在会额外暴露 `last_transition_display_reason`
  - 该字段把内部 loop reason 映射到更适合前端消费的语义，例如 `aborted -> cancelled`、`guard_stop -> guard`
  - `build_structured_timeline()` 里的 transition 项现在也会带上同一套 `display_reason`
  - 这让前端可以同时保留底层 raw reason 和用户可读 reason，而无需在 UI 层硬编码映射表
- 影响范围：
  - Session snapshot 协议
  - 前端状态文案与展示逻辑
  - transition 相关回归测试
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 视 GUI 需求决定是否把 `display_reason` 进一步统一成完整的展示文案层模型

### DC-045

- 日期：2026-04-02
- 变更主题：Workspace intelligence 的诊断热点改为按工作集优先聚合
- 变更摘要：
  - `DiagnosticsProvider` 不再只返回最近两条原始诊断摘录，而是先按文件聚合 compile / test / tidy / analyzer 等诊断热点
  - 最近编辑/读取过的工作集文件会优先于“仅出现在报错输出里的文件”，避免被动报错文件抢占焦点
  - 同一文件上的多条诊断会折叠为一条热点证据，并带出诊断数量、来源工具集合与最新一条摘要，便于 `code/debug/verify` 模式把首屏上下文留给更有操作价值的问题
- 影响范围：
  - Workspace intelligence 证据选择
  - Context pipeline 首屏上下文质量
  - Diagnostics / Problems 聚合的一致性预期
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 pathless 的 failing tests / quality gate / coverage 热点聚合
  - 后续把 LLSP/clangd 的引用链与调用关系证据并入同一热点选择器
  - 观察 GUI Problems / timeline inspector 是否也应复用同一聚合逻辑

### DC-056

- 日期：2026-04-02
- 变更主题：DiagnosticsProvider 已补 quality gate / pathless summary 聚合
- 变更摘要：
  - `verify` 模式下，`DiagnosticsProvider` 现在会把 `report_quality`、`run_tests`、`collect_coverage` 等无明确文件路径的失败或告警聚成一条 `Quality Gate Summary`
  - 这让质量门信息不再散落成多条 pathless observation，而能以单条高优先级证据进入 workspace intelligence
  - 若没有 `report_quality` 但存在多条无路径诊断，provider 也会退化输出 `Pathless Diagnostics` 摘要
- 影响范围：
  - verify mode 的工程情报首屏质量
  - quality gate / test / coverage 的上下文聚合
  - DiagnosticsProvider 的 pathless failure contract
- 关联文档：
  - `docs/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续深化 `RecipeProvider` 的 mode-aware 选证
  - 评估 GUI Problems / inspector 是否也应直接复用这条 quality gate summary

### DC-044

- 日期：2026-04-02
- 变更主题：上下文与 Query Loop 激进重构切片落地
- 变更摘要：
  - `session.py` 已升级为 transcript/event 基础模型，新增 `TranscriptMessage`、`ToolCallRecord`、`AgentStepState`、`PendingInteraction`、`LoopTransition`、`CompactBoundary` 与 `ContextAssemblyResult`
  - 新增 `query_engine.py` 作为真实主循环；`loop.py` 已退化为兼容 shim
  - `ContextManager.build_messages(...)` 已扩展为上下文流水线入口，开始接入 workspace intelligence、tool result replacement、duplicate suppression、activity folding 与 compact boundary 复用
  - 新增 `workspace_intelligence.py`，统一挂接 `WorkingSet / ProjectMemory / Recipe / Ctags / Diagnostics / Git / Llsp(empty)` provider
  - `ToolDefinition` 与 `ToolRuntime` 已补齐 `read_only / concurrency_safe / interrupt_behavior / result_budget_policy / activity_kind / context_priority`
  - 新增 `tool_execution.py`，提供批处理分组与流式工具执行器骨架
  - `InProcessAdapter` 已开始采用 pending interaction + resume 主链路，不再只依赖线程阻塞等待 `ask_user` / permission
- 影响范围：
  - Agent Core 主循环
  - 会话与 transcript 模型
  - 上下文管理
  - Tool Runtime 能力模型
  - 前端兼容投影
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`建议后续补一条 Query / Context 内核 ADR`
- 后续动作：
  - 继续把 reactive compact、resume consistency 与 workspace intelligence provider 深化到真实工程场景
  - 逐步把旧的 event-blocking 交互路径完全切换到 pending interaction / resume
  - 扩充对旧测试集的兼容回归覆盖

### DC-043

- 日期：2026-04-02
- 变更主题：离线打包切换到 `package.ps1` 控制面
- 变更摘要：
  - 新增 `scripts/package.config.json`、`scripts/package-lib.ps1` 与 `scripts/package.ps1`，把离线打包的公共入口收敛为 `doctor` / `deps` / `assemble` / `verify` / `release`
  - 现有 `export-dependencies.py`、`prepare-offline.ps1`、`build-offline-bundle.ps1`、`validate-offline-bundle.ps1` 与 `check-bundle-dependencies.py` 继续保留，但转为控制面内部 stage 或兼容入口
  - `tests/test_packaging_control_plane.py` 已覆盖 foundation、stage JSON 报告、doctor 契约以及 mocked orchestration；`tests/fixtures/package/` 提供最小 mock stage 夹具
  - `build/offline-reports/` 现在成为控制面统一的阶段报告与最终报告目录，`release -Json` 可直接输出机器可读状态
  - 对外文档开始全面改口：用户和维护者默认不再串联旧多脚本流程，而是从 `pwsh -File scripts/package.ps1 release` 开始
- 影响范围：
  - Phase 7 打包控制面
  - 脚本职责分层
  - operator-facing 文档与部署流程
  - 后续真实 bundle 验收口径
- 关联文档：
  - `docs/offline-packaging-guide.md`
  - `docs/offline-packaging.md`
  - `docs/intranet-deployment.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
  - `docs/adrs/0004-packaging-control-plane-redesign.md`
- 是否需要 ADR：`是`
- 后续动作：
  - 在真实 bundle 路径上验证 `package.ps1 release`
  - 继续收紧 `site-packages` 导出策略
  - 在 Win7 实机上补控制面主路径验收

### DC-042

- 日期：2026-04-01
- 变更主题：recipe-aware build/test 入口与 GUI Run / Problems 面板
- 变更摘要：
  - 新增 `workspace_recipes.py`，统一收集项目自定义 recipe、自动检测的 `CMakeLists.txt` / `Makefile` recipe，以及历史成功命令 recipe
  - `compile_project` / `run_tests` / `run_clang_tidy` / `run_clang_analyzer` / `collect_coverage` 已支持 `recipe_id`，并把 `recipe_id`、`recipe_source`、`recipe_label` 回写到 Observation
  - `InProcessAdapter` 与 GUI backend 已暴露 workspace recipe API；slash command 新增 `/recipes` 与 `/run <recipe_id>`
  - GUI Inspector 已新增 `Run` / `Problems` 面板：Run 用于查看并直接执行 recipe，Problems 用于聚合最近 diagnostics / failing tests / quality reasons
  - workspace profile 会把探测到的 recipe 样本注入给 Agent，减少后续 build/test 仍走自由拼命令的概率
- 影响范围：
  - Tool Runtime recipe 解析
  - slash command / workspace API
  - GUI Inspector 工作台
  - Agent workspace profile 注入
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续把 recipe / preset 扩展到更强的 `target / profile / coverage` 工作流
  - 在 Win7 bundle 中验证 Run / Problems 与 step timeline 的联动

### DC-041

- 日期：2026-04-01
- 变更主题：Agent step 时间线与托管运行环境摘要接入 GUI 壳层
- 变更摘要：
  - `AgentLoop` / `InProcessAdapter` 现在会在单个用户 turn 内生成多个 agent step，并写出 `step_start` / `step_end`
  - `build_structured_timeline()` 已从旧的扁平事件推断切换为以 `turns[].steps[]` 为主，同时保留 raw events 作为调试/回放补充
  - `ToolRuntime` / `ToolContext` 新增托管运行环境摘要，统一产出 `runtime_source`、`bundled_tools_ready`、`fallback_warnings` 与 `resolved_tool_roots`
  - GUI timeline 已改为按 turn 下的多个 step 呈现 thinking / tool / assistant；Inspector 新增 Runtime 面板
  - `styles.css` 已与 `Timeline.jsx` / `Sidebar.jsx` / `Inspector.jsx` / `Composer.jsx` 的类名重新对齐，修复缺失卡片与样式漂移
- 影响范围：
  - AgentLoop 与 InProcessAdapter 事件模型
  - 协议层 `TurnRecord` / `SessionSnapshot`
  - Tool Runtime 与 GUI Runtime inspector
  - GUI 时间线与样式系统
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/adrs/0003-agent-step-timeline-and-managed-runtime-shell.md`
- 是否需要 ADR：`是`
- 后续动作：
  - 在 Phase 2 中把 build/test/tidy/coverage 收敛到默认 recipe / preset
  - 继续推进 Runtime inspector 与 Problems / Diagnostics / Diff 工作台联动
  - 在 Win7 bundle 中验证 step-based GUI 与托管环境路径

### DC-040

- 日期：2026-03-31
- 变更主题：离线 bundle GUI 布局重新对齐与 editable path 泄漏修复
- 变更摘要：
  - 确认 `build/offline-dist/` 先前之所以仍是旧的 `static/js` / `static/css` 布局，不是 `prepare-offline.ps1` 回退了静态资源，而是旧 dist 根本没有在 GUI webapp 迁移到 `static/assets` 之后重新构建
  - `prepare-offline.ps1` 现在会在复制 `site-packages` 后清理指向开发工作区的 `__editable__*.pth`，避免 bundle 运行时串回本机源码树
  - `build-offline-bundle.ps1` 现在正确透传 `WebView2RuntimeRoot`，并在重建时显式接入 `webview2_fixed_runtime_x64`
  - `prepare-offline.ps1` 的压缩包解包逻辑改成基于 `System.IO.Compression.ZipFile`，从而真正支持 `.nupkg` 形式的 WebView2 runtime 资产
  - bundle 生成的 `embedagent-gui.cmd` 改为直接执行 bundle 内 `launcher.py`，并设置 `PYTHONNOUSERSITE=1`，减少 `runpy` warning 与宿主环境污染
  - `validate-offline-bundle.ps1` 与 `check-bundle-dependencies.py` 新增对 `__editable__*.pth` 的门禁检查；重建后的 dist 已通过 `validate-offline-bundle.ps1`、bundle 级 `validate-gui-smoke.py` 与 `check-bundle-dependencies.py`
- 影响范围：
  - Phase 7 prepare/build/validate 脚本
  - bundle GUI launcher 稳定性
  - 离线包对宿主开发环境的隔离性
- 关联文档：
  - `docs/development-tracker.md`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `scripts/check-bundle-dependencies.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 在 Win7 目标机上执行 `validate-gui-smoke.cmd --windowed`
  - 继续推进 `site-packages` 精简导出，减少 bundle 体积
  - 视需要把“禁止 bundle 残留 editable path”纳入更多自动化入口

### DC-039

- 日期：2026-03-31
- 变更主题：补强 workflow/filtering 回归测试与 GUI smoke 的 `/review` 覆盖
- 变更摘要：
  - `tests/test_tools_package.py` 新增 `schemas_for(mode, workflow_state)` 过滤回归，确认 `spec` 在 `review` workflow 下不会暴露写工具，`verify` 仍保留质量门工具
  - `ToolRuntime.execute()` 的 metadata 回灌新增回归断言，确保 `tool_label`、`permission_category`、renderer key 与 `supports_diff_preview` 在观察结果里稳定存在
  - GUI webapp `test/run-tests.mjs` 新增 reducer 级状态断言，覆盖 review command result 和 permission context inspector 所依赖的状态流
  - `scripts/validate-gui-smoke.py` 现在会显式执行 `/review`，让源码路径 smoke 覆盖 command/workflow 链路，而不仅是普通对话与工具调用
  - 当前验证也暴露出 `build/offline-dist/` 里的既有 bundle 仍是旧 GUI 布局（`static/js` / `static/css`），尚未与最新 validator 所要求的 `static/assets` / Fixed Version WebView2 路径完全同步
- 影响范围：
  - Core workflow/tool filtering 回归测试
  - GUI 状态层 smoke 与 reducer 回归
  - Phase 7 bundle/source 布局一致性检查
- 关联文档：
  - `docs/development-tracker.md`
  - `tests/test_tools_package.py`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `scripts/validate-gui-smoke.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 重新生成离线 bundle，并在新 bundle 上重跑 `validate-offline-bundle.ps1`
  - 用 bundle 级 `validate-gui-smoke.py` 复核 `/review` workflow 与 renderer runtime 路径
  - 继续收敛 GUI 打包产物布局，避免 source 与 dist 结构漂移

### DC-034

- 日期：2026-03-31
- 变更主题：统一输入总线与 slash command / workflow 第一版
- 变更摘要：
  - `submit_user_message` 升级为统一输入入口，先分发普通消息与 slash command，再决定是否进入 `AgentLoop`
  - 新增 `/help`、`/mode`、`/sessions`、`/resume`、`/workspace`、`/clear`、`/plan`、`/review`、`/diff`、`/permissions`、`/todos`、`/artifacts`
  - 新增 `CommandResult`、`PlanSnapshot`、`TurnRecord`、`TimelineItem`、`PermissionContextView`，并扩展 `SessionSnapshot`
  - GUI 已接入 command result、plan pane、timeline command cards、slash command hint；TUI 已可透传核心 workflow 命令
- 影响范围：
  - Core 输入分发
  - 协议层
  - GUI/TUI 交互层
  - 会话计划与权限上下文
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/adrs/0002-gui-workflow-shell-clean-room.md`
- 是否需要 ADR：`是`
- 后续动作：
  - 继续把 `/review`、`/permissions`、`/diff` 的 GUI inspector 表现收口
  - 在 Win7 bundle 中完成 GUI workflow / plan pane / renderer 路径验收

### DC-035

- 日期：2026-03-31
- 变更主题：`/review` 结构化 findings 与 renderer metadata 前端消费
- 变更摘要：
  - `/review` 不再只返回普通文本，而是输出带 `priority` / `severity` / `title` / `body` / `evidence` 的 findings 列表
  - GUI timeline 新增 review result 卡片，能够直接渲染 findings 与 residual risks
  - 工具事件开始把 `progress_renderer_key` / `result_renderer_key` 从 Core 传到前端，GUI 工具卡片已按 renderer key 展示不同摘要
  - `permissions` inspector 已独立于 `plan` inspector，减少工作流视图混杂
- 影响范围：
  - command/workflow 结果模型
  - GUI timeline 与 inspector 渲染
  - tool metadata 消费链路
- 关联文档：
  - `docs/development-tracker.md`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续把 quality / diagnostics / coverage 的 review evidence 展示细化到 inspector
  - 继续减少前端 `toolName -> UI` 的硬编码映射

### DC-036

- 日期：2026-03-31
- 变更主题：review inspector 独立化与 tool catalog API 前端 fallback
- 变更摘要：
  - GUI inspector 新增独立 `review` 面板，`/review` 的结构化结果不再只存在于 timeline bubble
  - 后端新增 tool catalog API，前端会在事件未携带完整 label / renderer 时使用 Core 工具目录做 fallback
  - 这让前端进一步从“猜测工具展示”转向“消费 Core 工具定义”
- 影响范围：
  - GUI inspector 信息架构
  - 前后端工具元数据链路
  - 旧 timeline / fallback 展示逻辑
- 关联文档：
  - `docs/development-tracker.md`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- 是否需要 ADR：`否`
- 后续动作：
  - 把 permissions inspector 从 JSON 视图升级为结构化规则列表
  - 继续把 review evidence 细化为可展开的 diagnostics / tests / coverage 分组

### DC-001

- 日期：2026-03-27
- 变更主题：确立 Windows 7 离线 Agent Core 总体架构
- 变更摘要：
  - 确立 `Frontend -> Agent Core API -> Orchestration -> Runtime/LLM/State` 分层
  - 确立 Agent Core 为产品本体，前端可替换
  - 确立 Python 3.8、离线打包、Clang 生态为主线
- 影响范围：
  - 总体架构
  - 技术选型
  - 运行时约束
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
- 是否需要 ADR：`暂缓`
- 后续动作：
  - 进入 Core 骨架细化

### DC-002

- 日期：2026-03-27
- 变更主题：确立可配置模式与 Agent Harness
- 变更摘要：
  - 确立模式是 Core 契约而不是 UI 标签
  - 确立 `ask / orchestra / spec / code / test / verify / debug / compact` 模式集
  - 确立 `Spec-Driven + TDD + Coverage/MC/DC Gate` 默认工程方法学
- 影响范围：
  - Core 设计
  - Harness 设计
  - 多智能体演进路径
- 关联文档：
  - `docs/overall-solution-architecture.md`
  - `AGENTS.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`建议后续补`
- 后续动作：
  - 编写 `docs/mode-schema.md`
  - 编写 `docs/harness-state-machine.md`

### DC-003

- 日期：2026-03-27
- 变更主题：建立文档治理与版本策略
- 变更摘要：
  - 建立 `AGENTS.md`
  - 建立 `implementation-roadmap.md`
  - 建立 `docs/adrs/`
  - 锁定 Python `>=3.8,<3.9`
  - 明确 `uv` 优先、`conda` 兜底
- 影响范围：
  - 开发环境
  - 文档治理
  - 后续实现纪律
- 关联文档：
  - `AGENTS.md`
  - `docs/implementation-roadmap.md`
  - `.python-version`
  - `pyproject.toml`
- 是否需要 ADR：`可不单独写`
- 后续动作：
  - 建立进度跟踪文件
  - 在每轮关键设计调整时持续维护本文件

### DC-004

- 日期：2026-03-27
- 变更主题：工具集设计提升为一等公民
- 变更摘要：
  - 内网模型（GLM5 int4、Qwen3.5）验证表明工具集设计质量是系统稳定性的关键变量
  - 确立每个模式工具上限 5 个（目标 3-4 个）
  - 确立工具描述模板：中文描述 + 英文命名，三段结构，参数含示例
  - 确立 7 类工具设计反模式（禁止使用）
  - 确立结构化 Observation 规范
  - Clang on Win7 风险项解除：已验证完全静态链接的最新版 Clang 可正常运行
- 影响范围：
  - 所有工具的实现与 schema 编写
  - 工具数量与模式分配
  - 工具返回值结构
- 关联文档：
  - `docs/tool-design-spec.md`（新建）
  - `docs/overall-solution-architecture.md`（补充 §8.3a）
  - `AGENTS.md`（补充工具规范约束）
- 是否需要 ADR：`暂缓，先在 Phase 1 验证后再决定是否需要`
- 后续动作：
  - 每次新增工具前必须过 `docs/tool-design-spec.md` 审查清单
  - Phase 1 完成后根据实际测试结果补充兼容处理细节

### DC-005

- 日期：2026-03-27
- 变更主题：实施分期重组，关键路径前移
- 变更摘要：
  - 原 Phase 1（Core 骨架）+ 原 Phase 3（LLM Adapter）合并为新 Phase 1（最小可工作 Loop）
  - Phase 2 改为工具集 v1（run_command + git），Phase 3 改为模式系统 v1
  - 每个 Phase 结束时必须有可实际运行的端到端验证点
  - `orchestra` 模式推迟到 Phase 3 之后实现
  - Harness 改为分阶段叠加：Phase 1 无 Harness，Phase 3 引入 dict 实现，Phase 5 可选 TOML
- 影响范围：
  - 实施顺序与里程碑定义
  - 开发节奏（从文档驱动转为端到端验证驱动）
- 关联文档：
  - `docs/implementation-roadmap.md`（Phase 1-5 重写）
  - `docs/development-tracker.md`（里程碑、任务板、风险更新）
  - `docs/overall-solution-architecture.md`（补充 Harness 演进路径）
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 直接进入 Phase 1 编码

### DC-006

- 日期：2026-03-27
- 变更主题：Phase 1 骨架收敛到 `src/embedagent`，模型验证策略允许受限替代
- 变更摘要：
  - 将 Phase 1 原型代码从仓库根目录平铺模块收敛到 `src/embedagent/` 包结构
  - `pyproject.toml` 同步切换为 `src` 布局与 console script 入口
  - 当 `GLM5 int4` / `Qwen3.5` 联调环境暂不可用时，允许用可访问的 OpenAI-compatible 服务完成真实 function calling 闭环验证
  - 基于 Moonshot `kimi-k2.5` 补齐了 `temperature` 与 `reasoning_content` 兼容处理
- 影响范围：
  - 代码组织结构
  - Phase 1 验证口径
  - LLM 适配层兼容策略
- 关联文档：
  - `pyproject.toml`
  - `README.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/llm-adapter.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 2 工具集实现

### DC-007

- 日期：2026-03-28
- 变更主题：Phase 2 工具集 v1 落地并验收
- 变更摘要：
  - 在 `src/embedagent/tools/` 包中实现 `run_command`、`git_status`、`git_diff`、`git_log`
  - 命令执行支持超时终止，并在 Windows 上使用 `taskkill /F /T /PID` 处理进程树
  - 建立 `docs/tool-contracts.md` 记录当前工具 Observation 契约
  - 在 Python 3.8.10 环境下完成工具直调与 Loop 烟雾验证
- 影响范围：
  - Tool Runtime
  - Phase 2 验证口径
  - 后续模式系统的工具过滤基线
- 关联文档：
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tools/shell_ops.py`
  - `src/embedagent/tools/git_ops.py`
  - `docs/tool-contracts.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 3 模式系统 v1

### DC-008

- 日期：2026-03-28
- 变更主题：Phase 3 模式系统 v1 落地并验收
- 变更摘要：
  - 新增 `src/embedagent/modes.py`，以 Python dict 形式定义 `MODE_REGISTRY`
  - Loop 按当前模式过滤工具，并对违规工具调用返回失败 Observation
  - 实现 `switch_mode(target)` 工具与用户显式 `/mode <name>` 入口
  - `edit_file` 增加基于 `writable_globs` 的写入边界检查
  - 新增 `docs/mode-schema.md` 与 `docs/harness-state-machine.md`
- 影响范围：
  - Agent Loop
  - CLI 入口
  - Tool Runtime 调用边界
  - 后续 Harness 演进基线
- 关联文档：
  - `src/embedagent/modes.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `docs/mode-schema.md`
  - `docs/harness-state-machine.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 4 Clang 工具链实现

### DC-009

- 日期：2026-03-28
- 变更主题：Phase 4 工具链第一版封装落地
- 变更摘要：
  - 在 `src/embedagent/tools/build_ops.py` 中新增 `compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
  - 引入 Clang/MSVC 风格诊断解析、测试结果统计和覆盖率摘要提取
  - 调整 `code` / `test` / `verify` 模式工具集，使其更贴近阶段职责
  - 建立 `docs/clang-integration-plan.md`，明确当前采用显式 command 封装、后续再接真实工具链
- 影响范围：
  - Tool Runtime
  - Mode Registry
  - Phase 4 验证口径
- 关联文档：
  - `src/embedagent/tools/build_ops.py`
  - `src/embedagent/modes.py`
  - `docs/tool-contracts.md`
  - `docs/clang-integration-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 接入真实项目构建命令与 Clang 二进制路径

### DC-010

- 日期：2026-03-28
- 变更主题：项目内闭环 Clang 工具链组装与验证
- 变更摘要：
  - 下载并测试多个静态 Windows LLVM/Clang 发行包
  - 基于 `clang-20.1.8 libcmt`、静态 `clang-tidy` 和 `win-llvm 21.1.8` 组装出 `toolchains/llvm/current`
  - 在 `ToolRuntime` 中为子进程自动注入 `toolchains/llvm/current/bin` 与 `libexec`
  - 补本地 `clang-analyzer` 包装入口
  - 完成编译、静态分析、clang-tidy、profdata、llvm-cov 的真实 smoke test
- 影响范围：
  - 本地工具链目录布局
  - Tool Runtime 的子进程环境
  - Phase 4 验证口径
- 关联文档：
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tools/build_ops.py`
  - `docs/clang-integration-plan.md`
  - `toolchains/README.md`
  - `toolchains/manifest.json`
  - `scripts/activate-bundled-llvm.ps1`
  - `scripts/test-bundled-llvm.ps1`
- 是否需要 ADR：`暂不写，先等待真实工程和 Win7 验证结果`
- 后续动作：
  - 收敛版本组合
  - 在真实 C 工程和 Win7 上补验

### DC-011

- 日期：2026-03-28
- 变更主题：Phase 5 最小权限与防循环保护落地
- 变更摘要：
  - 新增 `src/embedagent/permissions.py`，定义最小权限分类和 CLI 确认策略
  - 新增 `src/embedagent/guard.py`，实现连续失败与相同失败动作的防护
  - `AgentLoop` 接入权限确认和 Doom Loop Guard
  - CLI 增加 `--approve-all`、`--approve-writes`、`--approve-commands`
  - 工具链 smoke test 脚本增加清理逻辑，减少临时产物污染
- 影响范围：
  - Agent Loop
  - CLI 入口
  - Phase 5 验证口径
- 关联文档：
  - `src/embedagent/permissions.py`
  - `src/embedagent/guard.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `docs/permission-model.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 继续补上下文压缩和更细粒度权限规则

### DC-012

- 日期：2026-03-28
- 变更主题：Phase 5 第一版上下文管理落地
- 变更摘要：
  - 新增 `src/embedagent/context.py`，以确定性规则实现会话上下文构建
  - `Turn` 新增消息范围索引，允许精确保留最近 turn 的原始消息链
  - 旧 turn 被压缩为摘要，工具 Observation 被结构化遮蔽与截断
  - `AgentLoop` 在每轮模型调用前不再直接发送全量 `session.messages`，而是交由 `ContextManager` 构建上下文
  - 新增 `docs/context-management-design.md` 记录当前策略与后续演进方向
- 影响范围：
  - Session 结构
  - Agent Loop 的上下文构建流程
  - Phase 5 上下文预算与压缩口径
- 关联文档：
  - `src/embedagent/context.py`
  - `src/embedagent/session.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 引入更精确的 token 预算
  - 视需要增加 LLM 摘要压缩路径

### DC-013

- 日期：2026-03-28
- 变更主题：Phase 5A 上下文预算器与 Observation Reducer Registry 落地
- 变更摘要：
  - `ContextManager` 引入 mode-aware budget，为不同模式分配不同输入预算并预留输出/推理空间
  - 新增 `ContextPolicy`、`BudgetEstimate`、`ContextStats`，让上下文压缩过程可观测
  - 引入 `ReducerRegistry`，按工具类型裁剪 Observation，而不是只依赖统一截断逻辑
  - `AgentLoop` 在构建上下文时显式传入当前 mode，使预算策略不再只靠 system prompt 反推
- 影响范围：
  - Context Manager
  - Agent Loop 的模型输入构建逻辑
  - Phase 5 上下文压缩评估与后续 condenser 触发策略
- 关联文档：
  - `src/embedagent/context.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在 Tool Runtime 源头引入 Artifact Store
  - 持久化 session summary
  - 评估可选 LLM condenser 的接入点

### DC-014

- 日期：2026-03-28
- 变更主题：Phase 5B Artifact Store 与 Observation 源头瘦身落地
- 变更摘要：
  - 新增 `src/embedagent/artifacts.py`，提供本地 artifact 落盘与基础脱敏能力
  - `ToolRuntime` 在 Observation 返回前，会把长 `content/stdout/stderr/diff` 和大列表写入 `.embedagent/memory/artifacts/...`
  - Observation 改为保留预览 + `artifact_ref` + 元数据，不再把大输出完整塞入会话
  - `ContextManager` 的 reducer 现在会保留关键 `artifact_ref`，允许模型按需回看工件
- 影响范围：
  - Tool Runtime
  - 上下文管理链路
  - Tool Observation 契约
- 关联文档：
  - `src/embedagent/artifacts.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/context.py`
  - `docs/tool-contracts.md`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 持久化 session summary
  - 增加 artifact 生命周期清理与索引
  - 评估是否需要单独的 artifact 读取工具

---

### DC-015

- 日期：2026-03-28
- 变更主题：Phase 5C Session Summary Store 与会话状态持久化落地
- 变更摘要：
  - 新增 `src/embedagent/session_store.py`，负责将会话关键状态持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
  - `AgentLoop` 在初始化、构建上下文、assistant 回复和 Observation 回注后都会刷新摘要文件
  - 摘要当前保留 `user_goal`、`current_mode`、`working_set`、`modified_files`、`last_success`、`last_blocker`、`recent_actions`、`recent_artifacts` 以及最近一次上下文预算统计
  - 该摘要文件作为后续恢复入口和 Project Memory 的基础落点，而不是全量历史回放
- 影响范围：
  - Agent Loop
  - 会话状态持久化
  - Phase 5 后续恢复与记忆演进路径
- 关联文档：
  - `src/embedagent/session_store.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 建立 Project Memory 加载层
  - 增加基于 `summary.json` 的恢复入口
  - 为 session / artifact 增加生命周期清理与索引

---

### DC-016

- 日期：2026-03-28
- 变更主题：Phase 5D Project Memory Store 与项目级记忆装载落地
- 变更摘要：
  - 新增 `src/embedagent/project_memory.py`，维护 `project-profile.json`、`command-recipes.json`、`known-issues.json` 与处理索引
  - `AgentLoop` 在持久化 session summary 后，会继续刷新 Project Memory
  - `ContextManager` 现在会按当前 mode 装载 Project Memory system message
  - 模型在新轮次中可直接看到项目硬约束、最近成功命令 recipe 和最近 open issue
- 影响范围：
  - Agent Loop
  - Context Manager
  - Phase 5 后续恢复与长期记忆演进路径
- 关联文档：
  - `src/embedagent/project_memory.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/context.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 增加基于 `summary.json` 的恢复入口
  - 为 memory 文件增加生命周期清理与索引
  - 评估是否需要 Project Memory 的显式编辑入口

### DC-017

- 日期：2026-03-28
- 变更主题：Phase 5E Resume Entry 与会话索引落地
- 变更摘要：
  - `SessionSummaryStore` 新增 `index.json`、最近会话列表、`latest` 解析和摘要加载能力
  - CLI 新增 `--list-sessions` 与 `--resume <session_id|latest|summary.json>`
  - 恢复会话时，会基于 `summary.json` 注入恢复摘要，再叠加当前模式 prompt 与 Project Memory
  - 这使 Phase 5 的记忆层首次形成“落盘 -> 列出 -> 加载 -> 续跑”的闭环
- 影响范围：
  - CLI 入口
  - Session Summary Store
  - Context Manager 的 system message 装载逻辑
- 关联文档：
  - `src/embedagent/cli.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/context.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 为 memory 文件增加生命周期清理与索引收口
  - 继续细化权限规则
  - 在长任务上验证恢复与记忆层稳定性

### DC-018

- 日期：2026-03-28
- 变更主题：Phase 5F Memory Maintenance 与记忆生命周期清理落地
- 变更摘要：
  - 新增 `src/embedagent/memory_maintenance.py`，统一协调 artifact / session / project memory 的清理
  - `ArtifactStore` 新增 `index.json` 与基础 cleanup 能力
  - `SessionSummaryStore` 新增会话目录 cleanup 与活跃 artifact 引用收集
  - `ProjectMemoryStore` 新增 artifact 引用收集与 resolved issue 收敛
  - `AgentLoop` 现在会周期性触发 memory maintenance，避免文件型记忆无限增长
- 影响范围：
  - Artifact / Session / Project Memory 全链路
  - Agent Loop 的后台维护逻辑
  - Phase 5 的长期稳定性与离线可持续运行能力
- 关联文档：
  - `src/embedagent/memory_maintenance.py`
  - `src/embedagent/artifacts.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/project_memory.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在长任务上验证 cleanup 策略是否足够稳健
  - 继续细化权限规则
  - 评估 memory browse / inspect 入口

### DC-019

- 日期：2026-03-28
- 变更主题：Phase 5 长任务稳定性验证完成并升级规则驱动权限模型
- 变更摘要：
  - 新增 `scripts/validate-phase5.py`，提供 Phase 5 的长任务稳定性与权限专项回归入口
  - 完成 20+ turn 长任务、多次上下文压缩、恢复续跑和 Project Memory 注入的本地验证
  - `PermissionPolicy` 升级为规则驱动模型，支持 `allow / ask / deny`、路径 glob 和命令正则匹配
  - CLI 新增 `--permission-rules`，支持加载 `.embedagent/permission-rules.json`
- 影响范围：
  - 权限模型
  - Phase 5 验证基线
  - CLI 配置入口
- 关联文档：
  - `src/embedagent/permissions.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `scripts/validate-phase5.py`
  - `docs/permission-model.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在真实模型与更长时间跨度上补稳定性验证
  - 继续推进 Phase 4 真正工程验证
  - 评估 memory browse / inspect 入口

### DC-020

- 日期：2026-03-28
- 变更主题：Phase 6 前端协议与 TUI 信息架构设计落地
- 变更摘要：
  - 新增 `docs/frontend-protocol.md`，定义 Frontend 与 Core 的 Command / Event 边界、In-Process adapter 和 stdio JSON-RPC 演进路径
  - 新增 `docs/tui-information-architecture.md`，定义首版 TUI 的页面结构、关键交互流和首版范围边界
  - 明确 Phase 6 首先实现 `InProcessAdapter`，再在其上构建最小 TUI，最后才考虑 stdio adapter
- 影响范围：
  - Phase 6 实现顺序
  - CLI / TUI 的边界定义
  - Frontend 与 Core 的协议收敛方式
- 关联文档：
  - `docs/frontend-protocol.md`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 实现 `InProcessAdapter`
  - 让现有 CLI 改为通过 adapter 调用 Core
  - 在 adapter 上实现最小 TUI

### DC-021

- 日期：2026-03-28
- 变更主题：Phase 6A InProcessAdapter 落地并接管 CLI 驱动路径
- 变更摘要：
  - 新增 `src/embedagent/inprocess_adapter.py`，统一封装会话创建、恢复、消息提交、事件回调和会话快照
  - `AgentLoop` 新增 `on_context_result` 钩子，允许前端层接收 `context_compacted` 事件
  - 现有 CLI 已改为通过 `InProcessAdapter` 驱动 Core，而不再直接组装 loop
  - 当前适配层已具备 Phase 6 最小可用边界，为最小 TUI 直接复用铺平路径
- 影响范围：
  - CLI 入口
  - Frontend / Core 协议落地方式
  - Phase 6 的实现顺序
- 关联文档：
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/cli.py`
  - `src/embedagent/loop.py`
  - `docs/frontend-protocol.md`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在 adapter 之上实现最小 TUI
  - 评估是否需要 stdio adapter 提前落地
  - 继续推进 Phase 4 真实工程验证

### DC-022

- 日期：2026-03-28
- 变更主题：Phase 6B 最小 TUI 原型接入 CLI
- 变更摘要：
  - 新增 `src/embedagent/tui.py`，在 `InProcessAdapter` 之上实现最小单会话 TUI 骨架
  - TUI 已具备 Header、Transcript、Side Panel、Composer 和基本快捷键
  - 现有 CLI 新增 `--tui` 入口，并在依赖缺失时返回明确错误提示
  - 当前已验证普通 CLI 不退化，以及 `--tui` 在缺少 `prompt_toolkit` / `rich` 时会 graceful fallback
- 影响范围：
  - CLI 入口
  - Phase 6 最小可运行交互壳
  - 后续 TUI 实现节奏
- 关联文档：
  - `src/embedagent/tui.py`
  - `src/embedagent/cli.py`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 补齐 `prompt_toolkit` / `rich` 依赖并完成真实运行验证
  - 完善权限确认、会话列表和侧栏刷新交互
  - 评估是否推进 stdio adapter

### DC-023

- 日期：2026-03-28
- 变更主题：Phase 6B 最小 TUI 交互深化与 `--tui` 空启动修复
- 变更摘要：
  - `src/embedagent/tui.py` 新增会话列表浏览、选中恢复、帮助/快照侧栏，以及权限、错误、上下文压缩状态展示
  - `src/embedagent/cli.py` 修复 `--tui` 仍要求启动消息的问题，并支持将可选初始消息交给 TUI 在首轮自动提交
  - 已补做本地回归：普通 CLI 不退化，TUI 逻辑可用假依赖验证，缺失 `prompt_toolkit` / `rich` 时继续保持 graceful fallback
- 影响范围：
  - Phase 6 最小 TUI 交互能力
  - CLI 的 `--tui` 启动路径
  - 后续真实 TUI 运行验证的准备状态
- 关联文档：
  - `src/embedagent/tui.py`
  - `src/embedagent/cli.py`
  - `README.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 补齐 `prompt_toolkit` / `rich` 依赖并完成真实运行验证
  - 评估是否接入 artifact 浏览或 inspect 入口
  - 继续推进 Phase 4 真实工程验证

### DC-024

- 日期：2026-03-28
- 变更主题：Phase 6B TUI 依赖接入与宿主兼容性收口
- 变更摘要：
  - `pyproject.toml` 已声明 `prompt-toolkit==3.0.52` 与 `rich==14.3.3`，开发环境可通过 `uv sync --python 3.8.10` 直接拉起 TUI 依赖
  - `src/embedagent/tui.py` 新增非控制台宿主拦截，遇到 `NoConsoleScreenBufferError` 时会转换为清晰的 `TUIUnavailableError`
  - 新增 `EMBEDAGENT_TUI_HEADLESS=1` 的内部验证路径，用于在当前宿主下跑通真实 prompt_toolkit 事件循环
- 影响范围：
  - TUI 依赖声明
  - 非控制台宿主的错误体验
  - Phase 6 的自动化验证能力
- 关联文档：
  - `pyproject.toml`
  - `src/embedagent/tui.py`
  - `README.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实控制台里补一轮手工验证
  - 评估是否为 headless 验证补独立脚本
  - 继续推进 Phase 4 真实工程验证

### DC-025

- 日期：2026-03-28
- 变更主题：Phase 6 进入脚本可追踪状态
- 变更摘要：
  - 新增 `scripts/validate-phase6.py`，固化 Phase 6 的自动化验证入口
  - 新增 `docs/phase6-validation.md`，记录自动化命令与真实控制台手工验证清单
  - 修正 `docs/frontend-protocol.md` 中 Phase 6B/6C 的阶段编号，使其与实际实现顺序一致
- 影响范围：
  - Phase 6 验证口径
  - 前端协议文档与路线图一致性
  - 阶段收口状态的可追踪性
- 关联文档：
  - `scripts/validate-phase6.py`
  - `docs/phase6-validation.md`
  - `docs/frontend-protocol.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实控制台里执行手工验证并记录结果
  - 继续推进 Phase 4 真实工程验证

## 4. 维护约定

- 若改动影响总体架构，更新本文件
- 若改动影响项目纪律或版本边界，同时更新 `AGENTS.md`
- 若改动影响实施顺序，同时更新 `docs/implementation-roadmap.md`
- 若改动具有长期不可逆影响，补充一个 ADR


### DC-026

- 日期：2026-03-29
- 变更主题：Phase 6 终端前端模块化与浏览接口扩展
- 变更摘要：
  - `src/embedagent/tui.py` 已收敛为兼容 shim，真实终端前端迁移到 `src/embedagent/frontend/tui/`
  - 终端前端按 `state / reducer / controller / layout / services / views` 拆分，避免继续把交互逻辑堆在单文件中
  - `InProcessAdapter` 新增 workspace / timeline / artifact / todo 读取接口，并接入 `SessionTimelineStore`
  - 新增单元测试覆盖 timeline store、adapter 前端接口与终端补全模块；`scripts/validate-phase6.py` 回归通过
- 影响范围：
  - Phase 6 前端包结构
  - Frontend/Core 浏览型接口边界
  - 后续 Win7 控制台与 ConEmu 收口路径
- 关联文档：
  - `src/embedagent/frontend/tui/`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/session_timeline.py`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实 Win7 控制台与 ConEmu 下补手工验证
  - 继续细化 explorer / editor / plan 交互
  - 评估是否将同一协议推广到 stdio adapter

### DC-027

- 日期：2026-03-29
- 变更主题：修复根目录文件写入边界匹配并对齐当前文档状态
- 变更摘要：
  - `modes.py` 现在把前导 `**/` 视为“可为空的目录前缀”，使 `README.md`、`AGENTS.md`、`pyproject.toml` 等根目录文件能按模式写入规则正确匹配
  - `tests/test_modes.py` 新增根目录 `README.md` / `pyproject.toml` / `manage.py` 的可写边界回归
  - `scripts/validate-phase5.py` 已在该修复后重新跑通，Phase 5 状态从“实现完成”校正为“脚本复验通过”
  - README、路线图、进度跟踪与变更日志已同步对齐当前能力、阶段状态与验证口径
- 影响范围：
  - 模式写入边界
  - Phase 5 验证基线
  - 文档治理一致性
- 关联文档：
  - `src/embedagent/modes.py`
  - `tests/test_modes.py`
  - `README.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
  - `docs/design-change-log.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 继续推进 Phase 4 真实 C 工程与 Win7 验证
  - 在真实控制台与 Win7 / ConEmu 下完成 Phase 6 手工验证
  - 启动 Phase 7 打包文档与前置自检设计

### DC-028

- 日期：2026-03-29
- 变更主题：建立 Phase 7 离线打包与 Win7 preflight 设计基线
- 变更摘要：
  - 新增 `docs/offline-packaging.md`，固定 one-folder portable bundle、目录布局、组件清单、构建流水线与 bundle 级验证口径
  - 新增 `docs/win7-preflight-checklist.md`，固定 Windows 7 目标机部署与首次运行检查项
  - 新增 ADR `0001-offline-portable-bundle-baseline.md`，把 Phase 7 首个交付形态收敛为 x64 one-folder portable bundle
  - README、tracker 与 roadmap 已同步登记 Phase 7 设计基线已建立
- 影响范围：
  - Phase 7 交付路线
  - 文档治理与验收口径
  - 后续打包脚本命名与职责拆分
- 关联文档：
  - `README.md`
  - `docs/offline-packaging.md`
  - `docs/win7-preflight-checklist.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/adrs/0001-offline-portable-bundle-baseline.md`
- 是否需要 ADR：`已补 ADR-0001`
- 后续动作：
  - 落 bundle manifest / checksum / license 生成方案
  - 规划 `prepare-offline` / `build-offline-bundle` / `validate-offline-bundle` 脚本骨架
  - 在 Win7 虚拟机上按 preflight 口径完成首轮 bundle 验收

### DC-029

- 日期：2026-03-29
- 变更主题：落地 Phase 7A `prepare-offline` 脚本骨架
- 变更摘要：
  - 新增 `scripts/prepare-offline.ps1`，可生成 `build/offline-staging/EmbedAgent/` 目录布局
  - 该脚本会写出 `embedagent.cmd`、`embedagent-tui.cmd`、默认配置模板、`bundle-manifest.json` 和 `checksums.txt`
  - 脚本支持 `-SkipBuild`，允许在第三方资产尚未收齐时先生成稳定的 staging 布局和组件状态清单
  - 已用 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证脚本可运行
- 影响范围：
  - Phase 7 打包脚本分层
  - bundle 目录布局的可执行基线
  - manifest / checksum 生成口径
- 关联文档：
  - `scripts/prepare-offline.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 补 `build-offline-bundle.ps1`
  - 补 `validate-offline-bundle.ps1`
  - 固化 MinGit / ripgrep / Universal Ctags / embeddable Python 的来源与校验和

### DC-030

- 日期：2026-03-29
- 变更主题：落地 Phase 7B `build-offline-bundle` 脚本骨架
- 变更摘要：
  - 新增 `scripts/build-offline-bundle.ps1`，可直接消费 `build/offline-staging/EmbedAgent/`
  - 脚本会把 staging bundle 复制到 `build/offline-dist/<artifact>/`，重写 dist 上下文 `bundle-manifest.json`，重算 `checksums.txt`，并生成 zip
  - 脚本已在 skeleton bundle 上通过 `powershell.exe -NoProfile -File scripts/build-offline-bundle.ps1` 验证
  - `prepare-offline.ps1` 同步增加对 `__pycache__` / `.pyc` / `.pyo` 的清理，避免把瞬态 Python 产物带进发布包
- 影响范围：
  - Phase 7 build 阶段脚本分层
  - dist 目录与 zip 产物约定
  - bundle manifest / checksum 在 dist 上下文的生成口径
- 关联文档：
  - `scripts/build-offline-bundle.ps1`
  - `scripts/prepare-offline.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 补 `validate-offline-bundle.ps1`
  - 将 launcher、manifest 与关键文件存在性检查纳入自动验证
  - 在真实资产收齐后补全 end-to-end bundle 验证

### DC-031

- 日期：2026-03-29
- 变更主题：落地 Phase 7C `validate-offline-bundle` 脚本骨架
- 变更摘要：
  - 新增 `scripts/validate-offline-bundle.ps1`，可校验 bundle 根目录、manifest、checksums、关键 launcher 和目录布局
  - 默认模式下，缺失 embeddable Python / MinGit / rg / ctags / LLVM 等资产会以告警呈现，便于在 skeleton bundle 阶段继续推进
  - `-RequireComplete` 下，相同缺失项会被提升为失败，作为后续正式离线交付验收门
  - 已在当前 skeleton bundle 上完成两轮验证：默认模式返回告警但通过；`-RequireComplete` 按预期返回失败
- 影响范围：
  - Phase 7 validate 阶段脚本分层
  - skeleton bundle 与正式验收之间的门禁切换策略
  - bundle manifest/checksum 的自动校验口径
- 关联文档：
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在正式验收入口中强制使用 `-RequireComplete`
  - 接入 embeddable Python 与第三方工具后补动态启动验证
  - 将 validate 结果沉淀到 bundle manifest 或独立报告文件

### DC-032

- 日期：2026-03-29
- 变更主题：接入 Python embeddable 与 MinGit 的真实资产链路
- 变更摘要：
  - 新增 `scripts/offline-assets.json`，固定 `python_embedded_x64` 与 `mingit_x64` 的官方 URL、SHA256、stage/cache 路径与 License 元数据
  - `scripts/prepare-offline.ps1` 现在支持 `-AssetManifestPath`、`-AssetIds` 和 `-AllowDownload`，并会对 Python/MinGit 执行缓存校验、按需下载、解压和 license notice 生成
  - Python embeddable 会在 prepare 阶段修补 `python38._pth`，写入 `..\..\app`、`..\site-packages` 和 `import site`
  - `scripts/build-offline-bundle.ps1` 现在会生成 `embedagent-win7-x64-sources/`，包含 `assets-manifest.json`、原始 zip 归档和 `checksums.txt`
  - `scripts/validate-offline-bundle.ps1` 已在真实 Python/MinGit 资产接入后通过默认模式和 `-RequireComplete` 模式验收
- 影响范围：
  - Phase 7 真实资产接入路径
  - bundle manifest / sources seed 结构
  - Python embeddable 启动方式
- 关联文档：
  - `scripts/offline-assets.json`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 接入 `ripgrep` 与 `Universal Ctags`
  - 评估是否用更精简的方式导出运行时 `site-packages`
  - 在 Win7 虚拟机上补 bundle 级真实验收

### DC-033

- 日期：2026-03-29
- 变更主题：接入 ripgrep 与 Universal Ctags 的真实资产链路
- 变更摘要：
  - `scripts/offline-assets.json` 已新增 `ripgrep_x64` 与 `universal_ctags_x64`，固定官方 URL、SHA256、stage/cache 路径与 License 元数据
  - `scripts/prepare-offline.ps1` 现在会对这两类 zip 执行缓存校验、按需下载、解压与 license notice 生成
  - prepare 新增“单层顶级目录自动拍平”逻辑，使 ripgrep zip 能稳定落到 `bin/rg/rg.exe`
  - `scripts/validate-offline-bundle.ps1` 已把 `rg.exe`、`ctags.exe`、对应 license notice、sources archive 和 `--version` 动态检查纳入正式门禁
  - 当前 `prepare/build/validate -RequireComplete` 已在 Python / MinGit / ripgrep / Universal Ctags 四类核心资产上全量通过
- 影响范围：
  - Phase 7 第三方资产接入范围
  - bundle 与 sources seed 的完整性门禁
  - validate 的动态工具检查覆盖面
- 关联文档：
  - `scripts/offline-assets.json`
  - `scripts/prepare-offline.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 评估 `.venv\Lib\site-packages` 的精简导出方案
  - 在 Win7 虚拟机上补 bundle 级真实验收
  - 视需要继续收敛第三方工具 license 文件的随包归档方式

### DC-034

- 日期：2026-03-29
- 变更主题：模式/权限解耦与空目录启动收口
- 变更摘要：
  - 新增 `write_file`，允许 agent 在工作区内创建新文件并自动创建父目录，解决空目录下 `spec` 无法起草文档的问题
  - 新增 `ask_user` 与 `waiting_user_input` 交互流，将用户问答与权限审批彻底分开
  - `switch_mode` 不再全模式可用，只保留给 `orchestra`；其他模式只能通过 `ask_user` 或文本建议请求用户决定
  - `MODE_REGISTRY` 的默认可写范围改为按文件类型放行，不再把 `docs/` / `src/` / `tests/` 固定成唯一目录结构
  - 配置新增 `mode_extra_writable_globs`，用于在保留默认值的前提下增量追加可写规则
  - 引入工作区画像 system message，并把非重试型阻塞纳入 LoopGuard 的提前停机逻辑
- 影响范围：
  - Mode Registry
  - Agent Loop / Guard
  - InProcessAdapter / CLI / TUI
  - 配置与文档治理
- 关联文档：
  - `src/embedagent/modes.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/tools/file_ops.py`
  - `src/embedagent/workspace_profile.py`
  - `docs/mode-schema.md`
  - `docs/tool-design-spec.md`
  - `docs/permission-model.md`
  - `docs/configuration-guide.md`
  - `docs/harness-state-machine.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 在真实 TUI / Win7 手工验证中复查 `waiting_user_input` 与 `waiting_permission` 的宿主体验
  - 继续评估 `ask_user` 是否需要被扩展到 `code` / `debug` 等执行模式

### DC-035

- 日期：2026-03-29
- 变更主题：模式系统 v2 重构——5 模式配置驱动，移除 switch_mode LLM 工具
- 变更摘要：
  - 模式集从 8 个缩减为 5 个：`explore`（默认，重命名自 ask）/`spec`/`code`/`debug`/`verify`；删除 `orchestra`、`test`、`compact`
  - `switch_mode` LLM 工具彻底移除；LLM 不能主动切换模式，只能通过 `ask_user` 建议，由用户确认
  - 模式定义迁移到 `_BUILTIN_MODES` + `initialize_modes(workspace)` 配置加载层；项目可通过 `.embedagent/modes.json` 覆盖或新增模式
  - `build_system_prompt()` 改为 `str.format()` + 可替换框架模板（`prompt_frame.txt`）
  - `manage_todos` / `ask_user` 在所有模式中统一可用
  - 会话启动时自动注入待办提示（通过 `workspace_profile.py`）
  - 旧 session 中已删除模式名（如 `orchestra`）自动回落到 `explore`，不崩溃
- 影响范围：
  - `src/embedagent/modes.py`（主要改动）
  - `src/embedagent/loop.py`（删除 switch_mode 逻辑）
  - `src/embedagent/workspace_profile.py`（加入待办提示）
  - `src/embedagent/cli.py` / `inprocess_adapter.py`（调用 initialize_modes）
  - 所有引用旧模式集的文档
- 关联文档：
  - `docs/mode-schema.md`（完全重写）
  - `docs/harness-state-machine.md`（更新切换机制）
  - `docs/tool-design-spec.md`（更新工具分配表）
  - `AGENTS.md`（更新模式政策与 Harness 演进策略）
  - `README.md`（更新模式列表）
  - `docs/implementation-roadmap.md` / `docs/development-tracker.md` / `docs/configuration-guide.md`（同步更新）
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 在真实 TUI / Win7 环境验证新默认模式 `explore` 的入口体验
  - 评估是否需要为常见 C 维护工程提供预置的 `modes.json` 样板文件

### DC-036

- 日期：2026-03-30
- 变更主题：新架构落地——protocol/core/frontend 分层与 GUI PyWebView 前端
- 变更摘要：
  - 新增 `src/embedagent/protocol/`，定义 `CoreInterface`、`FrontendCallbacks` 及数据类型，实现前后端协议层
  - 新增 `src/embedagent/core/adapter.py`，实现 `AgentCoreAdapter` 包装 `InProcessAdapter` 并统一事件分发
  - 新增 `src/embedagent/frontend/gui/`，实现 PyWebView + FastAPI + WebSocket 的 GUI 前端，包含 diff/权限确认弹窗
  - 迁移 `src/embedagent/frontend/tui/`，按新架构实现 `TUIFrontend` 适配器，延迟导入处理缺失依赖
  - 旧 `src/embedagent/frontend/tui/` 保留向后兼容，未来逐步迁移
  - 新增 `tests/test_architecture.py`，17 项架构测试覆盖协议、Core、前后端导入
  - 新增 `docs/architecture-new.md` 记录新架构设计
- 影响范围：
  - 整体架构分层（新增 protocol/core/frontend）
  - TUI/GUI 前端实现方式
  - Agent Core 与前端解耦程度
  - 文档治理（README、development-tracker、architecture-new）
- 关联文档：
  - `docs/architecture-new.md`（新建）
  - `docs/frontend-protocol.md`（需要后续更新以反映 protocol 层）
  - `docs/development-tracker.md`（新增 T-020、T-021）
  - `README.md`（目录结构、技术选型、项目现状更新）
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/tui/`
  - `src/embedagent/frontend/gui/`
  - `tests/test_architecture.py`
- 是否需要 ADR：`建议后续补 ADR 记录架构分层决策`
- 后续动作：
  - 将旧 `frontend/tui/` 完全迁移到 `frontend/tui/`
  - 实现 GUI 的 diff 确认弹窗与后端实际联动
  - 更新 `docs/frontend-protocol.md` 以反映新 protocol 层设计
  - 在 Win7 环境下验证 GUI 前端兼容性（IE11 回退）

### DC-037

- 日期：2026-03-30
- 变更主题：补齐 GUI smoke 与离线 bundle GUI 验证链路
- 变更摘要：
  - 在当前开发环境安装并同步 GUI 运行依赖，新增 `scripts/validate-gui-smoke.py`，可对源码路径和 bundle 路径执行 headless GUI smoke
  - `src/embedagent/frontend/gui/launcher.py` 新增 renderer report 与 auto-close 参数，便于在真实 Windows 宿主执行 windowed smoke
  - 修正 `scripts/prepare-offline.ps1` 生成的 `embedagent-gui.cmd`，使其直接进入 GUI launcher，支持 GUI 专属参数
  - 离线 bundle 新增 `validate-gui-smoke.cmd` 与 `docs/win7-gui-validation.md`，作为 Win7 实机验收入口
  - 修正 `scripts/build-offline-bundle.ps1` 的 `AssetIds` 参数处理
  - 扩展 `scripts/validate-offline-bundle.ps1` 与 `scripts/check-bundle-dependencies.py`，把 GUI launcher、静态资源、内网部署文档和 GUI 依赖纳入正式校验
- 影响范围：
  - GUI 当前环境验收口径
  - 离线 bundle 的 GUI 交付完整性
  - Phase 6 / Phase 7 的验证结论
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/gui-packaging.md`
  - `scripts/validate-gui-smoke.py`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `scripts/check-bundle-dependencies.py`
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 实现 GUI 的 diff 确认弹窗与后端实际联动
  - 在真实 Win7 环境完成 WebView2 / MSHTML 回退实机验证

### DC-038

- 日期：2026-03-30
- 变更主题：GUI 状态语义收口、session-scoped todo 与 React/Vite 新壳层
- 变更摘要：
  - `manage_todos` 与前端 `list_todos` 默认切换为 session 作用域，真实会话数据落到 `.embedagent/memory/sessions/<session_id>/todos.json`；新建会话不再继承旧会话 todo
  - `InProcessAdapter` / `protocol` / `core.adapter` 补齐权威 `session_snapshot` 状态流，新增 `session_status`、`reasoning_delta`、`thinking_state`，并修复 `tool_started` / `tool_finished` 的稳定 `call_id`
  - 新增 GUI 专用懒加载文件树接口 `list_workspace_children`
  - 新增 `src/embedagent/frontend/gui/webapp/` React + Vite 工程，构建产物写回 `src/embedagent/frontend/gui/static/`
  - GUI launcher 现在优先要求 bundle 内 Fixed Version WebView2 runtime；bundle 模式下若缺失 Chromium 运行时会显式失败，不再静默回退到 IE11
  - `scripts/validate-gui-smoke.py` 已升级，可覆盖 tool / permission / ask_user / session todo 隔离与 renderer runtime source
- 影响范围：
  - GUI / Core 协议边界
  - todo 持久化语义
  - Win7 GUI 运行时基线
  - GUI 前端构建与静态资源来源
- 关联文档：
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/tools/todo_ops.py`
  - `src/embedagent/frontend/gui/webapp/`
  - `src/embedagent/frontend/gui/launcher.py`
  - `scripts/validate-gui-smoke.py`
  - `docs/frontend-protocol.md`
  - `docs/gui-packaging.md`
  - `docs/win7-gui-validation.md`
  - `docs/configuration-guide.md`
- 是否需要 ADR：`建议后续补一条 GUI Chromium 基线 ADR`
- 后续动作：
  - 在 Win7 bundle 中完成 Fixed Version WebView2 109 实机验证
  - 继续细化文件预览 / diff / 编辑闭环
  - 评估是否继续保留 `mshtml` 仅作报错级兜底
