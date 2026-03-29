# EmbedAgent Context Management Design（Phase 5）

> 更新日期：2026-03-28
> 适用阶段：Phase 5 上下文管理第一版

---

## 1. 文档目标

记录当前上下文管理的设计原则、压缩顺序、保留规则和实现边界。

本版本聚焦低成本、可预测、无额外 LLM 调用的第一版方案。

---

## 2. 设计原则

### 2.1 先做确定性压缩，再考虑 LLM 摘要

当前实现遵循：

1. 保留当前模式的最新 system prompt
2. 保留最近若干 turn 的原始消息链
3. 将更早的 turn 压缩为结构化摘要
4. 对工具 Observation 做遮蔽与截断
5. 仅在仍超预算时做硬裁剪

这样做的原因：

- 无额外模型调用
- 行为稳定、可调试
- 更适合当前离线/内网场景

### 2.2 模式提示始终是最高优先级

由于系统已引入 `MODE_REGISTRY`，上下文管理必须确保：

- 最新模式的 system prompt 永不丢失
- 旧模式切换历史可以被摘要化
- 当前工作边界始终明确

### 2.3 工具观测优先遮蔽而不是整段保留

Observation 往往是上下文膨胀的主要来源，尤其是：

- `read_file.content`
- `stdout` / `stderr`
- `diff`
- `diagnostics`

因此当前实现优先压缩工具结果，而不是先丢用户/助手语义。

---

## 3. 当前实现位置

- `src/embedagent/context.py`
- `src/embedagent/session.py`
- `src/embedagent/loop.py`
- `src/embedagent/tools/`
- `src/embedagent/artifacts.py`
- `src/embedagent/session_store.py`
- `src/embedagent/project_memory.py`
- `src/embedagent/memory_maintenance.py`

---

## 4. 当前数据结构

### 4.1 `Turn` 扩展字段

`Turn` 新增：

- `message_start_index`
- `message_end_index`

作用：

- 精确定位某个 turn 在 `session.messages` 中的切片范围
- 让最近 turn 的“原始消息链”可以被完整保留
- 避免靠 role 猜测消息边界

### 4.2 `ContextConfig`

当前参数包括：

- `max_context_chars`
- `max_recent_turns`
- `min_recent_turns`
- `max_summary_turns`
- `max_summary_chars`
- `recent_message_chars`
- `recent_tool_chars`
- `summary_text_chars`
- `summary_tool_chars`
- `hard_message_chars`
- `hard_tool_chars`

当前使用字符预算而不是 token 预算，原因是：

- Python 3.8 标准库内可直接实现
- 无需额外 tokenizer 依赖
- 对 Phase 5 MVP 已足够稳定

---

## 5. 构建流程

每次调用模型前：

1. 从 `Session` 读取完整历史
2. 提取最新 system prompt
3. 取最近 `N` 个 turn 保留原始消息链
4. 将更早 turn 压缩为一条“历史摘要” system message
5. Tool Runtime 先对大 Observation 做源头瘦身，并把长输出落为 artifact
6. 对最近消息中的 tool message 做 Observation reducer 压缩
7. Agent Loop 会把会话摘要持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
8. ContextManager 会按 mode 装载 Project Memory system message
9. CLI / Loop 可通过 `summary.json` 恢复会话并继续运行
10. MemoryMaintenance 会定期清理 session / artifact / project memory
11. 若仍超预算，减少保留的 recent turn 数量
12. 若仍超预算，执行硬裁剪

---

## 6. 压缩策略

### 6.1 旧 turn 摘要化

更早的 turn 不再保留原始 assistant/tool message，而被压缩为摘要，包含：

- 用户问题摘要
- 工具动作名称
- 关键 Observation 摘要
- 最终 assistant 结果摘要

摘要规则：

- 最多保留最近若干个旧 turn 的摘要
- 更早的 turn 只保留数量信息（“还有 X 个 turn 已折叠”）

### 6.2 最近 turn 保真化

最近 turn 尽量保留原始顺序：

- user
- assistant
- tool
- assistant
- ...

但对 `tool.content` 进行压缩。

### 6.3 Observation 遮蔽

当前会优先保留以下结构化字段：

- `path`
- `query`
- `command`
- `cwd`
- `exit_code`
- `duration_ms`
- `timed_out`
- `error_count`
- `warning_count`
- `diagnostic_count`
- `test_summary`
- `coverage_summary`
- `passed`
- `line_coverage`

并按类型截断：

- `content`
- `stdout`
- `stderr`
- `diff`
- `diagnostics`
- `files`
- `matches`
- `entries`

### 6.4 Artifact Store（Phase 5B）

从 Phase 5B 起，大输出不再先完整进入会话历史，再由 `ContextManager` 被动裁剪。

当前规则是：

- `content` / `stdout` / `stderr` / `diff` 过大时，只在 Observation 中保留预览
- 原始字段会生成 `<field>_artifact_ref`，指向 `.embedagent/memory/artifacts/...`
- `diagnostics` / `files` / `matches` / `entries` 过大时，只保留前若干项，并写入 JSON artifact
- artifact 与预览都会先做基础脱敏

这样做的收益是：

- 会话源头体积更小
- 模型仍可通过 `read_file` 按需回看 artifact
- 上下文管理从“事后裁剪”升级为“源头控体积 + 事后再压缩”

### 6.5 Session Summary 持久化（Phase 5C）

从 Phase 5C 起，会话不再只依赖内存中的 `Session` 对象。

当前 `AgentLoop` 会在关键节点刷新 `summary.json`：

- 初始化会话后
- 每轮构建上下文后
- assistant 回复后
- 每次 Observation 回注后

当前摘要文件会保留：

- `user_goal` / `latest_user_message` / `assistant_last_reply`
- `current_mode` / `mode_history`
- `working_set` / `modified_files`
- `last_success` / `last_blocker`
- `recent_actions` / `recent_artifacts`
- 最近一次 `context_policy` / `context_budget` / `context_stats`

这样做的收益是：

- 进程外可直接查看当前会话状态
- 为后续恢复入口与 Project Memory 提供稳定落点
- 在不恢复全量 message log 的前提下，也能保住关键工作状态

### 6.6 Project Memory（Phase 5D）

从 Phase 5D 起，模型上下文不再只依赖会话内状态和最近 Observation。

当前 `ProjectMemoryStore` 会维护三类文件：

- `project-profile.json`：项目级约束、Python 版本、环境策略、最近会话引用
- `command-recipes.json`：最近成功的构建 / 测试 / 命令配方
- `known-issues.json`：最近失败的已知问题摘要与状态

当前上下文装载规则是：

- `verify` / `test` 优先装载构建、测试、覆盖率相关 recipe
- `code` / `debug` 优先装载编译、命令和最近 open issue
- `ask` / `spec` / `compact` 只保留更轻的项目概况与少量关键问题

这使模型在新轮次中不必完全依赖当前会话，也能拿到：

- 项目硬约束
- 常用命令
- 最近踩过的坑

### 6.7 恢复入口与会话索引（Phase 5E）

从 Phase 5E 起，`summary.json` 不再只是落盘状态，而是可直接作为恢复入口使用。

当前已具备：

- `SessionSummaryStore.index.json`：最近会话索引
- `--list-sessions`：列出最近可恢复会话
- `--resume <session_id|latest|summary.json>`：从摘要恢复
- 恢复时会注入一条“恢复摘要” system message，再叠加当前模式 prompt 和 Project Memory

当前恢复策略不是全量历史回放，而是：

- 保留原会话 `session_id`
- 用摘要重建关键状态
- 在新用户消息上继续推进

这让 Phase 5 的记忆层首次具备了“落盘 -> 读取 -> 续跑”的完整闭环。

### 6.8 生命周期清理与索引收口（Phase 5F）

从 Phase 5F 起，记忆层不再只负责写入，还会负责“保留什么、删除什么”。

当前已具备：

- `ArtifactStore.index.json`：artifact 元数据索引
- `SessionSummaryStore.index.json`：最近会话索引
- `ProjectMemoryStore.memory-index.json`：已处理事件索引
- `MemoryMaintenance`：协调整理 session / artifact / project memory

当前清理规则是：

- Session：只保留最近若干会话目录
- Artifact：优先保留活跃引用、最近条目和较新文件
- Project Memory：保留 open issue，只保留少量最近 resolved issue

这使文件型记忆层从“只增不减”进入“可持续收敛”的状态。

### 6.9 硬裁剪

若在减少 recent turn 后仍超预算：

- 对非 system message 的 `content` 做更强截断
- 对 tool message 做更小上限截断
- 必要时丢弃最旧的非 system message

---

## 7. 当前收益

这版上下文管理已经带来：

- 当前模式提示稳定保活
- 长工具输出不再无上限累积
- 旧历史转为摘要，避免会话无限膨胀
- 工具链 / Git / 编译输出以结构化字段优先保留
- 会话关键状态已可落盘，为恢复与续跑打下基础
- 不需要额外模型调用即可工作

---

## 8. 当前局限

### 8.0 Artifact Store 已有索引和基础清理，但仍是文件级 MVP

当前 artifact 已经有索引和清理能力，但还没有：

- 用户可见的 artifact 浏览入口
- 更精细的引用计数与代际回收
- 专门的 `read_artifact` / `list_artifacts` 工具

### 8.1 仍使用字符预算

当前不是精确 token 预算，只是近似字符预算。

### 8.2 摘要是规则化而非语义化

当前旧 turn 摘要基于字段拼接，不是 LLM 语义总结。

### 8.3 恢复入口已具备，但仍是摘要驱动 MVP

当前恢复已经可用，但仍然存在这些局限：

- 不是全量 message / tool history 回放
- 恢复质量依赖 `summary.json` 的信息完整度
- 多会话索引仍是轻量文件清单，不是结构化检索系统

### 8.4 Project Memory 仍是规则驱动 MVP

当前 `ProjectMemoryStore` 已经接入，但仍然存在这些局限：

- recipe 选择主要依赖 mode 和最近成功记录
- known issue 的归并和 resolved 判定仍较粗
- 还没有 Project Memory 的显式编辑入口

### 8.5 生命周期清理仍较粗粒度

当前 cleanup 已可工作，但仍然存在这些局限：

- 保留策略主要按最近性与少量阈值
- 没有跨层统一的引用计数
- 没有后台或定时清理任务

### 8.6 尚未接入真正的 Archive Memory

当前只处理会话摘要和项目级记忆，还没有把：

- 多会话历史摘要
- 可复用解决记录
- 架构决策索引

纳入统一 Context Manager。

---

## 9. 后续演进建议

### 9.1 Phase 5 后续

- 引入更细粒度的消息裁剪指标
- 对近期 tool result 做按工具类型定制摘要模板
- 将上下文预算暴露为可配置项

### 9.2 Phase 6+

- 接入真正的 token 计数器
- 引入可选 LLM 摘要压缩
- 为 `compact` 模式提供专用上下文压缩路径
- 将 Project Memory / Archive Memory 纳入统一上下文构建器

---

## 10. 当前结论

当前上下文管理方案的定位是：

**确定性、低成本、对 Phase 5 足够稳定的第一版 Context Manager。**

它不是最终形态，但已经把“上下文无限直塞模型”的问题收住了，并为后续更强的摘要压缩和记忆系统预留了清晰演进路径。

---

## 11. Phase 5A-5F 新增能力

### 11.1 Mode-Aware Budget

当前 `ContextManager` 不再只使用单一字符上限，而是引入 `ContextPolicy`：

- 不同 mode 具有不同的 `max_context_tokens`
- 为输出与推理保留预算（`reserve_output_tokens` / `reserve_reasoning_tokens`）
- 不同 mode 可覆盖 `max_recent_turns` 与消息裁剪阈值

当前 token 仍是近似估算，不是 tokenizer 精算，但已经把“预算”从纯字符截断升级成了可替换策略层。

### 11.2 Reducer Registry

当前工具 Observation 的压缩不再完全依赖通用字段表，而是引入 `ReducerRegistry`：

- `read_file` 保留文件元信息与内容预览
- `search_text` 保留匹配数与命中片段
- `run_command` / `compile_project` / `run_tests` 等命令类工具保留退出码、耗时、结构化诊断与输出预览
- `git_status` / `git_diff` / `git_log` 使用更贴近 Git 语义的裁剪方式
- `report_quality` / `switch_mode` 使用专门 reducer

这使上下文压缩开始具备“按工具类型保真”的能力，而不是统一截断所有 Observation。

### 11.3 Context Stats

每次 `build_messages()` 现在都会返回额外统计信息：

- 原始 / 发送后字符数
- 近似 token 数
- recent turn 数量
- 被摘要化的 turn 数量
- 被 reducer 处理的 tool message 数量
- 是否触发 hard trim
- 当前 mode 对应的预算信息

这些统计用于后续做：

- 上下文压缩效果评估
- `compact` 模式专用路径
- LLM condenser 触发阈值判断
- 调试“为什么某条上下文被裁掉”

### 11.4 Session Summary Store

`SessionSummaryStore` 当前已经把会话关键状态落盘到 `.embedagent/memory/sessions/<session_id>/summary.json`。

它不是全量历史回放，而是一个面向恢复与续跑的轻量状态快照，重点保留：

- 目标
- 当前模式
- 工作集
- 最近阻塞
- 最近成功
- 近期动作
- 最近 artifact 引用
- 最近一次上下文预算统计

### 11.5 Project Memory Store

`ProjectMemoryStore` 当前会把项目级稳定知识收敛到 `.embedagent/memory/project/`。

它的定位是：

- 用文件型结构保存可解释、可审计的项目记忆
- 把常用命令和最近问题从会话中抽离出来
- 为后续恢复入口和 Archive Memory 提供基础层

当前已经会自动沉淀：

- 项目概况和硬约束
- 最近成功命令 recipe
- 最近 open / resolved issue

### 11.6 Resume Entry

当前 CLI 已支持基于 `summary.json` 的恢复入口和最近会话索引。

它的定位是：

- 不追求全量历史回放
- 以摘要恢复关键工作状态
- 让用户可以从最近会话快速续跑

### 11.7 Memory Maintenance

`MemoryMaintenance` 当前负责协调整个文件型记忆层的收敛。

它会联动：

- `ArtifactStore.cleanup()`
- `SessionSummaryStore.cleanup()`
- `ProjectMemoryStore.cleanup()`

让 Phase 5 的记忆层首次具备“写入 -> 索引 -> 恢复 -> 清理”的完整闭环。

---

## 12. 下一步实施建议

Phase 5F 完成后，推荐继续按下面顺序推进：

1. 继续细化权限规则与默认批准策略
2. 在更长任务场景下做稳定性验证
3. 评估是否需要统一的 memory browse / inspect 入口
4. 仅在预算仍严重不足时引入可选 LLM condenser





