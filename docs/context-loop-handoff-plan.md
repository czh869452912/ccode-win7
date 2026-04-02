# Context/Loop 重构交接计划

> 最后更新：2026-04-02
> 用途：这是面向“上下文管理 + agent loop + tool orchestration + workspace intelligence”重构线的自包含计划文档。
> 交接约定：在另一台电脑上，只要仓库代码与本文件、[`docs/context-loop-handoff-status.md`](./context-loop-handoff-status.md) 同步，就可以继续开发这一工作流，不依赖额外口头背景。

---

## 1. 工作流目标

将 EmbedAgent 的内核从“单次 message 拼接 + 简单工具调用循环”升级为更接近 Claude Code 风格的长任务内核，但保持当前产品约束：

- Windows 7 兼容
- 离线交付
- Python 3.8
- 单 agent 主线
- 面向 C / 嵌入式业务工程
- bundle 内置 clang / ctags / git / rg 等工具

本工作流只关注以下四个核心面：

1. 上下文管理
2. Agent Loop / 状态机
3. 工具编排与恢复
4. 工作区情报层

---

## 2. 不变约束

继续开发时必须保持以下边界不被突破：

- 不引入 Docker、Node、VS Code、WSL、在线服务运行时依赖
- 不突破 Python 3.8 语法与依赖边界
- `llsp` 只能作为 provider contract / 可选接入点，不能成为当前运行硬依赖
- 单 agent 仍是当前产品主线，不实现真正多 agent orchestration
- 外部协议尽量兼容，内部允许激进重构
- GUI / TUI 只是投影层，Agent Core 才是产品核心

---

## 3. 目标架构

### 3.1 Query Engine

目标是由 `QueryEngine.submit_turn(...)` 作为真实主循环入口，显式推进：

1. input normalize
2. context pipeline
3. model stream
4. tool orchestration
5. follow-up / finish / wait / retry

核心状态迁移以 `LoopTransition` 表达，至少覆盖：

- `completed`
- `permission_wait`
- `user_input_wait`
- `compact_retry`
- `guard_stop`
- `aborted`
- `max_turns`

### 3.2 Transcript / Session

会话真相应落在 transcript/event 模型，而不是旧的前端 snapshot 结构。核心类型：

- `TranscriptMessage`
- `ToolCallRecord`
- `AgentStepState`
- `PendingInteraction`
- `LoopTransition`
- `CompactBoundary`
- `ContextAssemblyResult`

### 3.3 Context Pipeline

上下文组装固定走以下流水线：

1. working set 提取
2. workspace intelligence 选证
3. tool result budget replacement
4. duplicate read/search suppression
5. activity folding
6. summary / compact
7. final prompt render

### 3.4 Workspace Intelligence

工作区情报统一由 broker/provider 体系负责，不靠临时工具调用凑上下文。首批 provider：

- `WorkingSetProvider`
- `ProjectMemoryProvider`
- `RecipeProvider`
- `CtagsProvider`
- `DiagnosticsProvider`
- `GitStateProvider`
- `LlspProvider`（contract + optional backend）

### 3.5 Tool Execution

工具执行目标行为：

- `read_only && concurrency_safe` 工具可批处理并发
- 其他工具严格串行
- 工具结果写回 transcript 时保持原始调用顺序
- 支持 progress/result 分离
- 支持 pending permission / pending user input / retry / interrupt

### 3.6 Frontend Projection

旧前端协议继续保留，但只能作为投影层：

- `SessionSnapshot`
- raw timeline
- structured timeline

这些投影要从新 transcript / transition 真相里派生，不再自己定义状态。

---

## 4. 分阶段计划

### Phase A：新 transcript 与主状态机

目标：

- `QueryEngine` 成为主循环
- 新 session/transcript 类型落地
- pending interaction 能挂起 / 恢复

完成标准：

- adapter 不再依赖旧 loop 直接驱动长任务
- `ask_user` / permission 不再伪造失败 observation

### Phase B：context pipeline 与 compact

目标：

- 用 pipeline 替代单次 `build_messages()`
- 引入 artifact replacement
- 引入 compact boundary
- 支持 reactive compact retry

完成标准：

- 长上下文失败后可 compact retry
- snapshot / summary 能反映 compact 信息

### Phase C：tool capability 与 orchestration

目标：

- 工具能力元数据齐全
- batch partition / ordered writeback 落地
- pending interaction resume 打通

完成标准：

- 工具批处理逻辑有单元测试
- permission / ask_user 能在原位置恢复

### Phase D：workspace intelligence broker

目标：

- `ctags / recipe / diagnostics / git / llsp contract` 统一接入 broker
- mode-aware 选证稳定

完成标准：

- `code/debug/verify` 模式能看到差异化情报
- snapshot 能投影 intelligence

### Phase E：恢复一致性与前端收口

目标：

- resume consistency 做硬
- interrupt / retry / synthetic result 语义补齐
- adapter 的 legacy 路径继续收缩

完成标准：

- 长任务 resume 不破坏 artifact replacement / transition 语义
- 前端主要状态都直接消费新 transcript 投影

---

## 5. 当前剩余工作

### P0：恢复一致性

优先完成：

- artifact replacement 的严格重放一致性
- resume 后 recent context / replacements / compact boundary 的稳定回放
- 更强的 resume 集成回归

### P1：tool interrupt / retry 收口

优先完成：

- user interrupt 后 synthetic tool_result
- discard-on-retry 的 transcript 语义
- streaming tool execution 的 retry / abort 边界

### P1：workspace intelligence 深化

优先完成：

- `LlspProvider` 接真实 backend

### P1：frontend / protocol 继续规范化

优先完成：

- 明确 step/turn 状态语义是否继续保留 raw/internal 双层
- 让 GUI inspector 直接消费 `display_reason`
- 继续收缩 adapter 内的 legacy 分支

### P2：更强集成回归

优先完成：

- 大型 C 工程上的 `read -> compile -> diagnose -> edit -> verify`
- prompt-too-long / interrupt / resume / permission wait 全链路回归

---

## 6. 继续开发时先看的文件

如果要继续这个工作流，优先看这些代码文件：

- `src/embedagent/query_engine.py`
- `src/embedagent/session.py`
- `src/embedagent/context.py`
- `src/embedagent/tool_execution.py`
- `src/embedagent/workspace_intelligence.py`
- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/session_store.py`
- `src/embedagent/protocol/__init__.py`

优先看这些测试：

- `tests/test_query_engine_refactor.py`
- `tests/test_inprocess_adapter_frontend_api.py`

已有设计背景补充：

- `docs/query-context-redesign.md`

---

## 7. 继续开发的验证命令

最低验证：

```powershell
$env:PYTHONPATH='D:/Project/coding_agent/src;D:/Project/coding_agent/.venv/Lib/site-packages'; python -m unittest tests.test_inprocess_adapter_frontend_api tests.test_query_engine_refactor -v
```

本工作流常用语法检查：

```powershell
$env:PYTHONPATH='D:/Project/coding_agent/src;D:/Project/coding_agent/.venv/Lib/site-packages'; python -m py_compile src\embedagent\inprocess_adapter.py src\embedagent\session_store.py src\embedagent\protocol\__init__.py tests\test_inprocess_adapter_frontend_api.py
```

如果修改了 `context/query/tool_execution/workspace_intelligence`，也应补跑：

```powershell
$env:PYTHONPATH='D:/Project/coding_agent/src;D:/Project/coding_agent/.venv/Lib/site-packages'; python -m py_compile src\embedagent\context.py src\embedagent\query_engine.py src\embedagent\tool_execution.py src\embedagent\workspace_intelligence.py
```

---

## 8. 交接结论

继续这条工作流时，不要重新做“总体设计”。当前正确做法是：

1. 先读本文件
2. 再读 `docs/context-loop-handoff-status.md`
3. 跑验证
4. 从 `P0 恢复一致性` 或 `P1 tool interrupt/retry` 开始下一轮

这两份文件的目标就是让另一台电脑上的开发者无需重新梳理对话历史，也能直接接着干。
