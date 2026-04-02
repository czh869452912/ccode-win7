# Context/Loop 重构当前进展

> 最后更新：2026-04-02
> 用途：这是面向另一台电脑继续开发的“当前状态快照”。
> 使用方式：先读 [`docs/context-loop-handoff-plan.md`](./context-loop-handoff-plan.md)，再读本文件，然后直接从“下一步建议”开始。

---

## 1. 总体判断

相对最初的重构计划，这条工作流当前总体进展约为 `80%`。

这是人工评估，不是自动统计；它反映的是：

- 核心骨架已经成形
- 关键主链路已可用
- 但恢复一致性、interrupt/retry、真实 llsp 接入、部分前端收口还没有完成

---

## 2. 已合入主线的提交范围

这一轮工作流的核心提交从 `9bfc9c3` 到 `2b02fa5`，主题如下：

- `9bfc9c3` `feat: add query and context refactor core`
- `0e12058` `feat: harden query refactor compatibility`
- `c1f4363` `feat: enrich ctags workspace intelligence`
- `0046d30` `feat: refine workspace intelligence selection`
- `26510b0` `feat: project workspace intelligence into session snapshots`
- `6e65a65` `feat: aggregate diagnostics hotspots by working set`
- `75cc10f` `feat: add reactive compact retry`
- `4d1723c` `feat: surface compact retry observability`
- `952914d` `feat: preserve transitions in structured timeline`
- `43cb19f` `feat: retain waiting states in structured timeline`
- `29f8b7e` `feat: project terminal transitions into timeline`
- `1387a4d` `feat: persist final transition details`
- `e2d39d0` `feat: enrich snapshot transition details`
- `359455f` `test: cover guard stop timeline projection`
- `2b02fa5` `feat: enrich transition display semantics`

---

## 3. 当前阶段完成度

| 阶段 | 进展 | 说明 |
|------|------|------|
| Phase A | `基本完成` | `QueryEngine`、transcript/event、pending interaction 主链路已落地 |
| Phase B | `大体完成` | context pipeline、artifact replacement、compact boundary、reactive compact retry 已落地 |
| Phase C | `大部分完成` | tool capability metadata、batch orchestration、permission / ask_user 恢复已打通 |
| Phase D | `基本完成` | workspace intelligence broker 和首批 provider 已接入 |
| Phase E | `大体完成` | resume consistency 与 interrupt/retry 主线已基本补齐，legacy projection 瘦身和前端最终消费仍待继续 |

---

## 4. 已落地能力

### 4.1 Query / Session 内核

已落地：

- `QueryEngine.submit_turn(...)` 作为真实主循环入口
- 新 transcript/event 模型
- `PendingInteraction`
- `LoopTransition`
- `CompactBoundary`
- `ContextAssemblyResult`

关键文件：

- `src/embedagent/query_engine.py`
- `src/embedagent/session.py`

### 4.2 Context Pipeline

已落地：

- working set 提取
- workspace intelligence 注入
- tool result replacement
- duplicate suppression
- activity folding
- deterministic compact
- reactive compact retry

关键文件：

- `src/embedagent/context.py`

### 4.3 Workspace Intelligence

已落地：

- broker/provider 框架
- `CtagsProvider` 真实解析 `tags`
- `DiagnosticsProvider` 工作集优先热点聚合
- `RecipeProvider` mode-aware source/stage 选证
- `GitStateProvider`
- `LlspProvider` contract + backend hook

关键文件：

- `src/embedagent/workspace_intelligence.py`

### 4.4 Tool Execution

已落地：

- 工具能力元数据
- batch partition
- ordered result writeback
- pending permission / pending user input 恢复链路

关键文件：

- `src/embedagent/tool_execution.py`
- `src/embedagent/tools/_base.py`
- `src/embedagent/tools/runtime.py`

### 4.5 Frontend Projection

已落地：

- snapshot 投影新 context / intelligence / transition 信息
- raw timeline 保留 compact retry 与等待态
- structured timeline 保留 turn/step 级 transitions
- `display_reason` 语义映射
- legacy summary 缺失 `display_reason` 时的 snapshot 读取兼容回填

关键文件：

- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/session_store.py`
- `src/embedagent/protocol/__init__.py`

---

## 5. 当前测试面

核心测试文件：

- `tests/test_query_engine_refactor.py`
- `tests/test_inprocess_adapter_frontend_api.py`

当前已覆盖的重点包括：

- pending permission / pending user input 挂起与恢复
- tool batch partition
- transcript-truth restore
- ctags 解析与优先级
- diagnostics hotspot 聚合
- quality gate / pathless diagnostics 聚合
- recipe mode-aware source/stage ranking
- reactive compact retry
- tool interrupt / discard / long-running command cancel
- discard-on-retry transcript boundary
- compact retry 的 snapshot / timeline / structured timeline 投影
- `guard_stop / aborted / max_turns / user_input_wait / permission_wait` 的前端投影
- `display_reason` 以及旧 summary 兼容回填

最近一次新鲜验证结果：

- `python -m unittest tests.test_transcript_store tests.test_session_restore tests.test_query_engine_refactor tests.test_inprocess_adapter_frontend_api -v`
  - `68/68` 通过
- `python -m py_compile src\embedagent\workspace_intelligence.py src\embedagent\tools\_base.py src\embedagent\tools\runtime.py src\embedagent\query_engine.py tests\test_query_engine_refactor.py tests\test_inprocess_adapter_frontend_api.py`
  - 通过

---

## 6. 当前最重要的未完成项

### P0：resume consistency

已切到 transcript-truth 主线：

- `transcript.jsonl` 现在是会话真相源
- `SessionRestorer` 可重建 `Session/Turn/Step/ToolCall/CompactBoundary/PendingInteraction`
- `summary.json` 已降级为 projection/index 层

剩余需要继续硬化的点：

- interrupt / synthetic tool_result transcript 语义已起步；当前已覆盖“tool_started 后取消 -> synthetic interrupted tool_result + aborted transition”
- retry/discard transcript 语义
- 更贴近真实大工程的恢复一致性回归

### P1：interrupt / retry / synthetic result

当前进展：

- 用户中断后 synthetic tool_result 已落地第一段：`tool_started` 之后若会话被取消，`QueryEngine` 会写入 synthetic interrupted observation，并在 transcript / timeline / adapter event 中对齐为 aborted
- parallel batch 中的 `discarded` result 现在仍会写入 transcript，但不再误触发 `LoopGuard` 把整轮提前打成 `guard_stop`
- `StreamingToolExecutor` 的并行批次现在已改成流式 start/result；在 `max_parallel_tools=1` 一类受控场景下，已覆盖“首个 action interrupted、后续未开始 action discarded”的 batch abort 边界
- 更高并发下的 queued action cancel 边界也已补上：`StreamingToolExecutor` 现在会直接观察 cancel event，因此 `max_parallel_tools>1` 时排队 action 不会在取消后偷偷启动
- transcript completeness 也已补硬：`tool_call` event 现在在 assistant action 阶段按原始顺序落盘，因此即使后续 action 被 discarded，也不会出现“有 tool_result 没有 tool_call”的残缺链路
- 更贴近真实 runtime 的取消路径也已补上：Windows 下 `run_command` 现在使用新进程组 + `CTRL_BREAK_EVENT` 优先中断，长命令在用户取消后不再等完整命令自然结束才返回
- discard-on-retry 的 transcript 语义也已补上：一旦前一个 batch 已经出现 `discarded`，同一条 assistant plan 中后续 batch 会统一落 `discarded` result，而不再继续真实执行

当前判断：

- 这条 `interrupt / retry` 主线已经从“待收口”进入“基本完成”；剩余更像真实工程级集成回归，而不是核心 contract 缺失

### P1：workspace intelligence 深化

还没做硬的点：

- `LlspProvider` 真实 backend 接入

### P1：frontend/protocol 收口

还没做硬的点：

- step/turn 状态语义是否继续保持 raw/internal 双层
- adapter 中 legacy 路径继续收缩

---

## 7. 建议的下一轮切入点

如果在另一台电脑继续开发，我建议按这个顺序推进：

1. `workspace intelligence`
   - 接入真实 `LlspProvider`
2. `frontend/protocol`
   - 继续收 `step/turn` raw/internal 双层语义和 legacy adapter 分支
3. `更强集成回归`
   - 在真实 C 工程上把 interrupt / resume / compact / permission wait 再串一遍

不建议下一轮优先做的事：

- 重新设计整体架构
- 扩张新工具面
- 提前做多 agent

---

## 8. 继续开发的最小步骤

在另一台电脑上继续时，按下面做：

1. 拉取最新 `main`
2. 打开本文件和 `docs/context-loop-handoff-plan.md`
3. 运行：

```powershell
$env:PYTHONPATH='D:/Project/coding_agent/src;D:/Project/coding_agent/.venv/Lib/site-packages'; python -m unittest tests.test_inprocess_adapter_frontend_api tests.test_query_engine_refactor -v
```

4. 从 `src/embedagent/inprocess_adapter.py`、`src/embedagent/session_store.py`、`src/embedagent/query_engine.py`、`src/embedagent/context.py` 开始阅读
5. 按“第 7 节 下一轮切入点”继续

---

## 9. 一句话结论

这条重构线已经从“概念计划”进入“骨架已成、剩余是硬化和收口”的阶段；接下来最值钱的工作，不是再扩功能，而是把恢复一致性、interrupt/retry 和前端最终消费链做实。
