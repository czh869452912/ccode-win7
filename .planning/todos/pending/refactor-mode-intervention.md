---
title: "重构 Mode 介入机制 — 从无条件固定 Track 到用户意图驱动"
date: "2026-05-03"
priority: high
resolves_phase: 7
---

# 重构 Mode 介入机制

## 目标

消除 mode 的无条件 workflow 注入行为。Mode 应只控制**权限和可用工具范围**，不预设任何固定的 phase track 或 workflow。

## 当前问题

- `harness/registry.py` 为 build/debug/verify 定义了固定的 `lite_track` / `full_track`
- `harness/runner.py` 的 `describe_mode()` 无条件调用 `TaskGraph.for_mode()` 生成完整 phase track
- `modes.py` 的 system prompt 明确描述"当前阶段先以 lite_spec_tdd 方式推进"
- 结果: 用户进入 build 模式说"hi"，模型收到"UNDERSTAND 阶段"的任务列表，开始尝试构建

## 期望行为

1. **进入 mode 后保持待命**: 没有预设 task，模型知道"我有 build 权限，但没有当前任务"
2. **用户意图触发 workflow**: 用户说"帮我实现 X"或"修复这个 bug"时，模型才生成 task graph
3. **动态 task 生成**: Task graph 根据具体请求动态创建，不绑定固定 phase

## 具体任务

### Phase 1: 削弱固定 Track（低风险）
- [ ] 修改 `harness/registry.py`: 保留 ModeDefinition 结构，但 track 可为空
- [ ] 修改 `harness/runner.py`: `describe_mode()` 仅在 session 已有 task graph 时才更新，不新建
- [ ] 修改 `harness/task_graph.py`: `for_mode()` 支持空 track（生成空 graph 或单节点 graph）
- [ ] 修改 `modes.py`: build/debug system prompt 移除"lite_spec_tdd 方式推进"描述

### Phase 2: 动态 Task 生成（中风险）
- [ ] 设计"task creation signal": 模型在需要时调用 `task_status` 的 create 语义
- [ ] 修改 `task_status` tool: 支持"查看/创建/更新" task graph
- [ ] 修改 `query_engine.py`: 在 context assembly 时，只有存在 task 时才注入 task graph
- [ ] 测试: 进入 build 模式说"hi" → 不应触发任何 tool 调用

### Phase 3: 用户意图识别（高风险）
- [ ] 评估是否需要显式的"intent classification"步骤
- [ ] 或完全依赖模型自判（在 system prompt 中明确"只有收到明确构建指令时才创建 task"）
- [ ] 添加测试覆盖各种边界情况（闲聊、文档阅读、明确构建请求）

## 验收标准

- [ ] build 模式下输入 "hi" → 模型正常回复，不调用任何 tool
- [ ] build 模式下输入 "帮我实现一个排序函数" → 生成 task graph 并开始实现
- [ ] debug 模式下输入 "这个错误什么意思" → 正常解释，不开始 debug 流程
- [ ] debug 模式下输入 "帮我定位这个崩溃" → 生成 debug task graph
- [ ] verify 模式下输入 "运行测试" → 生成 verify task graph 并执行
- [ ] verify 模式下输入 "今天天气怎么样" → 回复无相关权限（或优雅拒绝）

## 依赖

- `.planning/notes/gui-harness-refactor-direction.md`
- `.planning/research/questions.md` (RQ-001)
