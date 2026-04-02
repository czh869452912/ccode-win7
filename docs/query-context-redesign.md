# EmbedAgent Query / Context Redesign

> 更新日期：2026-04-02
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
- `SessionSnapshot` / timeline 已开始投影 compact retry 可观测性，当前至少能看到 `compact_retry_count`、最近 transition reasons，以及 `compact_retry` timeline event
- `build_structured_timeline()` 也开始保留 turn/step 级别的 `transitions`，这样 `compact_retry` 不会在结构化时间线里丢失

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
  - `LlspProvider`（空实现）
- 本轮只定义统一 broker/provider 契约；`llsp` 不作为运行前置条件

2026-04-02 的后续切片继续把这一层做深：

- `CtagsProvider` 不再只探测 `tags` 文件存在，而会解析符号项并优先呈现最近工作集 / 诊断热点文件中的符号定义
- `DiagnosticsProvider` 已升级为“工作集优先 + 按文件聚合”的热点选择器：最近编辑/读取过的文件会优先于被动报错文件，同一文件上的多条 compile/tidy/analyzer 诊断会合并成单条热点证据
- `RecipeProvider` 按 mode 重新排序 recipe，`verify` 优先测试/静态检查，`code` 优先编译与测试
- `LlspProvider` 已扩展为可注入 backend 的契约；默认仍为空实现，但后续可直接接入真实 `llsp/clangd` provider

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
- 更深的 ctags / llsp 实体级代码情报
- 全量旧测试迁移到无 ACL 噪音的测试沙箱
