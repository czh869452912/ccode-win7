---
title: "重构终止策略 — 从固定 Step 限制到任务完成度自判"
date: "2026-05-03"
priority: high
resolves_phase: 7
---

# 重构终止策略

## 目标

移除硬编码的 `max_turns=8` 全局限制，改为基于**任务完成度**的动态终止策略。

## 当前问题

- `query_engine.py:899`: `for turn_index in range(self.max_turns)`，默认 8 步
- `inprocess_adapter.py:170`: `max_turns: int = 8`
- `config.py:19`: `"max_turns": 8`
- 第 1232 行: `reason="max_turns", message="超过最大迭代次数"`
- 结果: 复杂任务（重构大模块）在 8 步后被迫中断，用户体验极差

## 期望行为

1. **无全局 step 限制**: 对话可以持续直到任务完成
2. **模型自判完成**: 模型在认为任务完成时主动输出完成信号
3. **Guard 兜底**: 死循环检测（重复调用相同 tool 相同参数）作为安全网
4. **用户可控**: 用户可以随时手动取消（保留现有 cancel 机制）

## 具体任务

### Phase 1: 提升 max_turns（临时缓解）
- [ ] 将默认 `max_turns` 从 8 提升到 32 或 64（作为过渡措施）
- [ ] 或彻底移除硬限制，改为 token/time budget
- [ ] 修改 `query_engine.py`: 移除/放宽 `range(self.max_turns)`
- [ ] 修改 `config.py`: 更新默认值

### Phase 2: 完成信号机制
- [ ] 设计"完成信号"格式:
  - 选项 A: 模型在最终回复中包含特定标记（如 `<task_complete>`）
  - 选项 B: 模型在最终回复中自然语言总结"已完成"，由系统识别关键词
  - 选项 C: 模型调用专用 tool（如 `task_complete`）来声明完成
- [ ] 在 system prompt / prompt frame 中添加"如何判断任务完成"的指引
- [ ] 修改 `query_engine.py`: 在检测到完成信号时优雅终止
- [ ] 在 `session.py` 中添加 `completion_signal` 状态字段

### Phase 3: Guard 增强（安全网）
- [ ] 审查现有 `LoopGuard` 的实现（`guard.py`）
- [ ] 增强死循环检测:
  - 连续 N 次（如 3 次）调用相同 tool + 相同参数 → stop
  - 连续 N 次 tool 调用都失败 → stop 并提示用户
  - 长时间无进展（如 10 步内无任何文件改动或测试执行）→ ask_user
- [ ] 添加"progress check"机制: 每 N 步让模型总结当前进度

### Phase 4: 预算控制（可选）
- [ ] 评估是否需要 token budget 或 time budget
- [ ] 如果实现，budget 应该是软限制（模型收到警告但可继续）而非硬限制
- [ ] 或保留 `max_turns` 作为超大数值（如 100）的最后防线

## 验收标准

- [ ] 简单问答（"解释一下这个函数"）在 1-3 步内自然完成
- [ ] 复杂重构任务可以持续 20+ 步不被系统打断
- [ ] 模型在任务完成时明确输出完成信号
- [ ] 死循环在 3-5 次重复后被检测并停止
- [ ] 用户随时可按 Escape 取消
- [ ] Timeline 不再显示 "max_turns reached" 卡片

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 模型永远不输出完成信号 | Guard 兜底 + 用户可手动取消 |
| 模型过早判断完成 | 在 prompt 中强调"确认所有验收标准满足后才标记完成" |
| 无限循环消耗 token | Guard 检测 + 可选 soft budget |
| 与现有测试冲突 | 全面更新测试用例，移除对 max_turns=8 的假设 |

## 依赖

- `.planning/notes/gui-harness-refactor-direction.md`
- `src/embedagent/guard.py` — LoopGuard 实现
- `src/embedagent/query_engine.py` — 核心循环逻辑
