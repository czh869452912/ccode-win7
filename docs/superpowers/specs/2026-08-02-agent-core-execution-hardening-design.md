# Agent Core Execution Hardening Design

> 状态：`approved`
> 类型：`temporary implementation design`
> 负责人：`Agent platform maintainers`
> 日期：`2026-08-02`

## Purpose

本切片加固 Agent Core 的工具执行与会话恢复边界。它解决四个已确认问题：截断的 provider 工具参数仍可能被执行、工具副作用开始记录早于权限和路径预检、provider tool call id 被误作全局耐久身份，以及 hosted adapter 的隐式权限默认过宽。

本设计不改变六发行包拓扑，不引入第二套 Agent loop，不增加 lane、会话树分支、通用多智能体编排、异步 operation handle 或新的公开 SDK facade。后续 Core 边界迁移和 SDK 易用性工作使用独立切片。

## Constraints

- 保持 Python `>=3.8,<3.9`、Windows 7 和离线运行。
- `AgentKernel` 仍只规划 context、provider、tool 三类私有 effect family。
- `AgentLoop` 仍是 canonical commit-execute-resume driver。
- 所有 durable state 仍只通过 `SessionJournal` append-before-apply。
- `AgentToolActionService` 继续拥有 active-tool、extension hook、permission、write-path、dispatch、interaction 和 workflow patch 语义。
- `transcript.jsonl` 继续是 hosted session 唯一耐久账本。
- 不保留被替换的 pre-release tool effect 或 event shape 兼容层。

## Alternatives

### A. Let AgentToolActionService append execution-start events directly

服务可在 runtime dispatch 前直接调用 `SessionJournal`。实现改动较小，但会让 tool service 成为第二个 commit driver，使 Kernel/Loop 无法完整描述 effect 状态，也会把 live reduction context 泄漏进工具策略层。本方案拒绝。

### B. Split the existing tool effect family into prepare and execute phases

Provider 返回工具调用后，Kernel 先计划 `PrepareToolBatchEffect`。Loop 执行顺序预检并把 typed preparation result 交回 Kernel。Kernel 只为真正可执行的 invocation 生成 durable `operation_started`，提交后再计划 `ExecutePreparedToolBatchEffect`。本方案保留单一状态机和 journal 边界，同时把副作用意图放在实际 dispatch 前，是选定方案。

### C. Replace the loop with a per-tool durable workflow or lane operation log

每个工具调用独立成为可恢复工作流，并增加 lane、durable queues 和自动重放策略。该方向接近 Pi 的长期 Harness 设计，但超出当前产品需求和 Core 非目标，会显著扩大恢复协议。本方案后置，直到出现明确消费者和独立设计。

## Selected Architecture

### Tool effect family

现有单阶段 `ExecuteToolBatchEffect` 被两个私有 effect 取代：

- `PrepareToolBatchEffect`：携带 assistant message identity、source-ordered actions、mode/workflow carrier，以及 provider 输出是否截断。
- `ExecutePreparedToolBatchEffect`：只携带已完成预检且允许 dispatch 的 immutable prepared invocations，以及同批次的 immediate results。

对应 typed results：

- `ToolBatchPrepared`：包含每个 source position 的 `PreparedToolInvocation` 或 immediate `Observation`、journal-ready result events 和 commit tokens。需要交互时，prepare phase 改为返回 `InteractionSuspended`。
- `ToolBatchCompleted`：保持最终 observations、result events 和 commit tokens，observations 顺序必须与 assistant tool calls 相同。

`PreparedToolInvocation` 至少冻结：

- durable `invocation_id`；
- provider `tool_call_id`，仅作关联；
- source index；
- original action 和 hook 修改后的 effective action；
- permission category、read-only/concurrency-safe 和 presentation 快照；
- dispatch owner 所需的 source identity；
- replay safety snapshot，当前切片只记录，不自动重放。

### Durable invocation identity

耐久身份使用：

```text
tool:<assistant_message_id>:<source_index>
```

`assistant_message_id` 已由 turn、step 和 provider attempt 确定，source index 来自 assistant message 中的工具调用顺序。Provider `call_id` 不再作为 operation id，也不要求跨 session 全局唯一；它继续出现在 tool message 和 provider correlation 字段中。非 provider 的 command tool turn 必须先持久化 provider attempt 为 `0` 的 deterministic assistant action message，再使用同一 identity 规则。

### Prepare phase

Preparation 按 assistant source order 执行，且不调用 `ToolRuntime.execute_with_interrupt(...)`、result materialization 或 extension tool handler。它只允许使用 active-tool、catalog 和 path resolver 等无副作用查询。每个 action 依次经过：

1. 截断响应拦截；
2. active-tool 检查；
3. source-aware before-tool hook 和 effective arguments 固化；
4. permission policy；
5. writable-path policy；
6. interactive-tool 或 permission interaction 判断；
7. execution metadata snapshot。

Blocked、invalid、denied、truncated 和无需 runtime dispatch 的 interaction outcomes 形成 immediate observations。它们不得产生 `operation_started`，因为没有副作用开始。

如果 preparation 需要用户交互，`InteractionSuspended` 必须持久化当前 source index、完整 source-ordered batch、已形成的 immediate results、effective action 和 invocation id。恢复仅通过现有 interaction reply 路径构造 Kernel continuation，并复用同一个 AgentLoop commit-execute-resume driver 继续 preparation；不得直接调用 tool service，也不得执行尚未提交 execution-start intent 的 invocation。

### Commit before dispatch

Kernel 接受 `ToolBatchPrepared` 后生成一个 `KernelStep`：

- 提交 preparation 产生的 immediate result 和 interaction events；
- 为每个 ready invocation 提交 `operation_started(kind="tool_call")`；
- operation metadata 记录 invocation id、provider call id、effective tool name、安全参数摘要所需的结构化字段、presentation 和 replay-safe snapshot；
- 只有 commit 成功后才产生 `ExecutePreparedToolBatchEffect`。

如果 prepared batch 没有 ready invocation，Kernel 直接提交 source-ordered immediate results 并进入下一 context step，不创建空 execute effect。

工具参数不得进入 telemetry 或诊断；canonical transcript 继续按当前工具调用/结果契约保存执行所需数据。

### Execute phase

Execution 不再重复 active-tool、before-hook、permission 或 path checks。它只执行 frozen prepared invocation：

1. 尝试 source-aware extension tool dispatch；
2. 未由 extension 处理时调用 `ToolRuntime.execute_with_interrupt(...)`；
3. 应用 after-tool hook；
4. materialize observation；
5. 返回 journal-ready tool result、workflow patch 和 operation finish/interruption events。

只有 `read_only && concurrency_safe` 的连续 ready invocations 可并行。Preparation 始终串行。并行 completion 可按完成顺序通知 observer，但 canonical tool result 和 `ToolBatchCompleted.observations` 必须按 assistant source order。

### Truncated provider output

当 `AssistantReply.finish_reason` 归一化为 `length` 且包含 actions 时，所有 action 在 preparation 第一步生成 `truncated_tool_arguments` failure observation：

- 不运行 hook、permission、path guard、extension handler 或 ToolRuntime；
- 不写 tool `operation_started`；
- 为每个 call 写标准 tool result，使 provider 在下一 step 看到错误并重新发起完整调用；
- 不将整个 turn 直接终止为 guard failure。

### Restore behavior

Restore 继续把无 finish/interruption 的 tool `operation_started` 视为 outcome unknown，并以 `incomplete_side_effect` 拒绝自动继续。当前切片不自动重放工具。

仅有 `tool_call` planned event、但没有 `operation_started` 的 invocation 表示 runtime side effect 尚未开始。它不能触发 `incomplete_side_effect`。交互挂起由现有 pending interaction truth 恢复；其他被中断的 preparation 由明确的新输入或后续恢复切片处理，不猜测执行结果。

## Permission Default

`InProcessAdapter` 未显式提供 policy 时必须使用 `PermissionPolicy()`，不得使用 `auto_approve_all=True`。Hosted runtime 继续根据显式 `LaunchConfig` 构造 policy。Read 默认允许；write、execution、network、telemetry 和 other 默认请求确认，write-path policy 仍独立生效。

## Event And Observer Semantics

- Assistant 和 `tool_call` planned events 先提交。
- Immediate tool results 在 preparation result 被 Kernel 接受后提交。
- Ready invocation 的 `operation_started` 在 execute effect 前提交。
- `operation_finished` 或 `operation_interrupted` 与 tool result 一起由 execute result 提交。
- Observer 只能看到已提交事件；observer failure 不改变 durable truth。
- 本切片不改变 public `AgentObserver` shape 或 Host `SessionEventEnvelope`。

## Failure Handling

- Preparation exception 转为 `EffectFailed(error_kind="tool_prepare")`，且不产生 side-effect-start record。
- Execution exception 转为该 invocation 的 failure observation，并关闭对应 operation。
- Journal commit failure阻止后续 dispatch。
- Parallel batch cancellation 为已开始 invocation 生成 interrupted results，为未开始 invocation 生成 discarded results；所有 operation 都必须闭合。
- Materialization finalization 仍发生在 canonical commit 后；失败只降级非权威投影并记录安全日志。

## Package Impact

本切片只修改 `embedagent-core` 私有 effect/kernel/loop/tool service 和 `embedagent-host` 的权限默认，不改变发行包依赖。Public root exports、Protocol DTO、workflow package API 和 frontend event shape 不变。

## Verification

必须使用 TDD 覆盖：

- `finish_reason="length"` 的 actions 全部形成 error results 且 runtime 调用次数为零；
- ready invocation 的 operation id 基于 assistant message id 和 source index；
- blocked、denied、invalid 和 suspended action 不产生 tool `operation_started`；
- journal append 失败时 runtime dispatch 次数为零；
- serial 和 parallel execution 均先经过 permission/path preparation；
- parallel results 仍按 source order 提交；
- restore 只对已写 execution-start、未闭合的 invocation 报告 `incomplete_side_effect`；
- `InProcessAdapter` 默认 write/execute/network 请求确认而非自动批准。

完成代码后运行：

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py
uv run python scripts/test-suite.py tdd tests/test_agent_loop_driver.py
uv run python scripts/test-suite.py tdd tests/test_agent_runtime_integration.py
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

## Acceptance Criteria

本切片只有在以下条件全部满足时关闭：

- 没有任何 runtime tool dispatch 可发生在 durable execution-start intent 之前；
- 截断工具参数永不执行；
- provider call id 不再承担 durable invocation identity；
- serial/parallel 路径共享同一 permission 和 path preparation；
- hosted adapter 的隐式默认权限与 `PermissionPolicy()` 一致；
- Core/Host 架构权威已同步当前实现；
- 要求的架构守卫、完整 Python 分区、lint 和六 wheel build/check/smoke 全部通过；
- spec 和 implementation plan 已移动到带索引的 archive package。
