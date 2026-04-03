# EmbedAgent Query / Context Redesign

> 更新日期：2026-04-03
> 适用阶段：上下文管理与 agent loop 激进重构切片

---

## 1. 目标

本设计切片把现有 `AgentLoop + ContextManager + InProcessAdapter` 的松耦合增强为统一的 query 内核，重点解决：

- 长任务中的上下文失控
- 工具结果重复注入
- `ask_user` / 权限等待只能阻塞线程、不能挂起恢复
- recipe / diagnostics / ctags / git 等工程情报没有统一入口

---

## 2. 新核心对象

- `TranscriptMessage`：统一 transcript 真相，补齐 `message_id / turn_id / step_id / kind / replaced_by_refs`
- `ToolCallRecord`：记录工具调用、结果和完成状态
- `AgentStepState`：记录单 turn 下的单次 agent step
- `PendingInteraction`：记录等待中的权限或用户输入
- `LoopTransition`：记录 `completed / permission_wait / user_input_wait / guard_stop / aborted / max_turns`
- `CompactBoundary`：记录已压缩的历史边界与摘要
- `ContextAssemblyResult`：记录上下文流水线产物、分析统计和 replacement 结果

---

## 3. Query Engine

- 新增 `QueryEngine.submit_turn(...)` 作为真实主循环，`loop.py` 退化为兼容 shim
- 主循环固定走：
  - `input normalize`
  - `context assembly`
  - `LLM sampling`
  - `tool batch execution`
  - `transition commit`
- `ask_user` 和权限审批在 resolver 缺失时不再伪造失败 Observation，而是返回 `PendingInteraction + LoopTransition`
- `resume_pending(...)` 会先把等待中的交互写回 transcript，再继续后续 step
- 当 LLM 明确返回 `prompt/context too long` 一类错误时，主循环现在会记录一次内部 `compact_retry` transition，并用更紧的内部 compact policy 重组上下文后自动重试一次
- 当会话在 `tool_started` 之后被取消时，主循环现在会补 synthetic interrupted tool_result，避免 transcript 里只留下孤立的 `tool_call`
- Windows 下的 `run_command` 现在会以新进程组启动，并在取消时优先发送 `CTRL_BREAK_EVENT`，因此长命令中断不再需要等命令自然结束
- `SessionSnapshot` / timeline 已开始投影 compact retry 可观测性，当前至少能看到 `compact_retry_count`、最近 transition reasons，以及 `compact_retry` timeline event
- `SessionSnapshot` 现在也开始保留 `last_transition_message`，便于前端直接展示“为什么停住了”
- `SessionSnapshot` 也开始暴露 `recent_transitions`，让前端不依赖 raw timeline 也能拿到最近几条状态迁移的 `reason + message + display_reason`
- `SessionSnapshot` 现在还会给最后一条 transition 提供 display 级 reason，前端不必自己把 `aborted / guard_stop / user_input_wait` 这类内部名称再映射成用户语义
- GUI inspector 现在也已直接消费这些 snapshot 字段，Runtime 面板会展示最后状态与最近状态迁移，而不是只靠内部 termination reason
- 读取旧 `summary.json` 时，即使历史 `recent_transitions` 里还没有 `display_reason`，snapshot 也会按当前映射规则即时补齐，避免 resume 老会话时出现新旧字段混杂
- `build_structured_timeline()` 也开始保留 turn/step 级别的 `transitions`，这样 `compact_retry` 不会在结构化时间线里丢失
- 结构化时间线现在也会保留 `user_input_required / permission_required` 这类等待态 transition，并把 turn 状态更新为对应的 waiting 状态
- `turn_end` 的非完成终止态（如 `max_turns`）也开始进入 structured timeline transitions，不再只表现为 turn status 文本
- 结构化时间线里的 transition 现在也会同步携带 `display_reason` 与错误/停止原因文本，前端不必再从其他 summary 或日志里反查原因
- `build_structured_timeline()` 现在还会显式暴露 `projection_source`，并用 `projection_kind / synthetic` 标记 recorded step、synthetic single step 与 raw-event fallback 的区别
- 当 `turn_end` 带来 `max_turns` 等终止态时，structured timeline 也会同步收口当前 step 的 `status`，不再出现 turn 已终止但 step 仍停在 `tool_calls` 的分裂语义
- 会话结束后会重新持久化一次最终状态，确保 `max_turns` 这类最后才出现的 transition 不会丢失在 summary/snapshot 之外
- Session truth 现在开始落到 `.embedagent/memory/sessions/<session_id>/transcript.jsonl`
- `summary.json` / snapshot payload 已下沉为 derived projection，而不再作为恢复真相源
- `resume_session()` 已切到 transcript replay 主线：恢复时先重建 `Session`，再回填 snapshot / summary / timeline
- `content_replacement` 与 `context_snapshot` transcript events 已开始持久化 replacement / compact 相关语义，避免 resume 后 replacement 字符串漂移

---

## 4. Context Pipeline

- `ContextManager.build_messages(...)` 现在支持：
  - `workspace intelligence`
  - `tool result replacement`
  - `duplicate read/search suppression`
  - `activity folding`
  - `compact boundary reuse`
- 新增 `TokenEstimator` 抽象，统一输出 token 近似值和 context analysis
- `ContextBuildResult` 现在会额外输出：
  - `summary_message`
  - `intelligence_sections`
  - `analysis`
  - `replacements`
  - `pipeline_steps`

---

## 5. Workspace Intelligence

- 新增 `WorkspaceIntelligenceBroker`
- 首批 provider：
  - `WorkingSetProvider`
  - `ProjectMemoryProvider`
  - `RecipeProvider`
  - `CtagsProvider`
  - `DiagnosticsProvider`
  - `GitStateProvider`
  - `LlspProvider`（默认文件型 backend + injectable backend）
- `LlspProvider` 当前默认会读取工作区 `.embedagent/llsp/evidence.json`；文件缺失时静默退化，不把 `llsp` 变成运行前置条件
- provider 侧会按当前 session 的 focus path / working set 对 LLSP 证据做最小排序，优先把当前正在看的文件抬到前面

2026-04-02 的后续切片继续把这一层做深：

- `CtagsProvider` 不再只探测 `tags` 文件存在，而会解析符号项并优先呈现最近工作集 / 诊断热点文件中的符号定义
- `DiagnosticsProvider` 已升级为“工作集优先 + 按文件聚合”的热点选择器：最近编辑/读取过的文件会优先于被动报错文件，同一文件上的多条 compile/tidy/analyzer 诊断会合并成单条热点证据
- `DiagnosticsProvider` 现在还会在 `verify` 模式下聚合 `report_quality` / `run_tests` / `collect_coverage` 一类无路径失败，生成单条 quality gate summary
- `RecipeProvider` 现在会按 mode 区分 `project / history / detected` 来源优先级，并使用 `stage` 细化 `build / test / configure` 的相对顺序
- `LlspProvider` 已扩展为“默认文件型 backend + 可注入 custom backend”的契约；当前默认路径是 `.embedagent/llsp/evidence.json`，后续仍可直接接入真实 `llsp/clangd` provider

---

## 6. 工具编排

- `ToolDefinition` 已补齐能力元数据：
  - `read_only`
  - `concurrency_safe`
  - `interrupt_behavior`
  - `result_budget_policy`
  - `activity_kind`
  - `context_priority`
- 新增 `tool_execution.py`
  - `partition_tool_actions(...)`
  - `StreamingToolExecutor`
- 默认规则：
  - `read_only && concurrency_safe` 批量并发
  - 其余工具串行
  - 结果按原始 tool call 顺序回写
- `run_command` 的 Windows runtime interrupt 现已从 `taskkill` 单一路径收口为“进程组 + `CTRL_BREAK_EVENT` 优先、必要时再 fallback”的终止策略
- `StreamingToolExecutor` 现在也会直接观察 cancel event，避免 `max_parallel_tools>1` 时排队 action 在取消后继续偷偷启动
- `QueryEngine` 现在还会把“前一个 batch 已出现 discarded”当作 retry boundary，因此同一条 assistant plan 里的后续 batch 会统一落 `discarded` result，而不是继续真实执行

---

## 7. 当前实现边界

当前切片已经落地：

- transcript / step / pending interaction / compact boundary 基础数据模型
- QueryEngine 主循环与 loop 兼容层
- adapter 侧的 pending interaction 恢复主链路
- context pipeline 的第一版 intelligence / replacement / suppression / analysis
- tool capability metadata 与批处理执行器
- reactive compact 的第一版重试闭环：识别上下文超限错误、记录 compact retry、复用 compact boundary，并以内部 compact policy 自动重试一次

当前仍未完全收口：

- 更强的 reactive compact / LLM compact
- 更完整的 permission wait / background resume 用户体验
- 更深的 llsp/clangd 实时语义后端（若后续确有需要）
- 全量旧测试迁移到无 ACL 噪音的测试沙箱
