---
title: "GUI & Harness 体验重构设计方向"
date: "2026-05-03"
context: "GUI & Harness design evaluation + reference engineering research"
---

# GUI & Harness 体验重构设计方向

## 当前痛点（已确认）

### 1. Mode 过度积极
- build/debug/verify 模式**无条件注入固定 phase track**（如 UNDERSTAND→CONTRACT→IMPLEMENT→CHECK→HANDOFF）
- 即使用户只是打招呼（"hi"），模型也会收到"当前在 UNDERSTAND 阶段"的 task graph，开始尝试构建
- **根因**: `harness/runner.py` 的 `TaskGraph.for_mode()` 无条件创建完整 track；system prompt 预设了 workflow

### 2. 8-Step 硬限制不合理
- `query_engine.py:899` 硬编码 `for turn_index in range(self.max_turns)`，默认 `max_turns=8`
- 复杂任务（重构大模块）明显不够；简单问答又显得多余
- **根因**: 全局固定限制，不区分任务类型和完成度

### 3. Inspector 信息分散
- tasks/artifacts/plan/review/recipes 等分布在多个 tabs
- 用户需要频繁切换才能了解全貌
- **根因**: 信息架构采用"IDE 仪表盘"模式，而非"对话流"模式

### 4. Timeline 嵌套混乱
- Step N 折叠面板多重嵌套（turn → step → activityItems）
- 信息被隐藏，难以快速浏览
- diff 组件（`DiffView.jsx`）存在但未被充分利用

### 5. Session 持久化/重建不可靠
- timeline 重建逻辑复杂，restore 状态经常 partial/unavailable
- transcript 格式与前端展示存在语义断层

## Reference Engineering 发现（关键模式）

### 必须采纳的模式
1. **线性对话流**: 所有标杆产品使用简单线性消息流，tool 调用 inline 展示
2. **Tool 生命周期状态**: queued → progress → result|error|rejected，防止用户困惑
3. **文件级状态存储**: JSONL transcript + `.planning/` Markdown，离线友好、git 版本控制
4. **Mode 是行为契约**: system-prompt + tool-permission，不是 UI 皮肤或 workflow 模板
5. **Auto-approval + guardrails**: 按工具类型设置 + 连续错误限制（如 3 次）
6. **破坏性操作前 checkpoint**: git-based checkpoint，支持安全恢复

### 必须避免的模式
1. **OpenHands 式多 agent 事件系统**: 增加服务器复杂度，违反 Win7/离线约束
2. **数据库级状态存储**: SQLite 等不适合离线部署
3. **预设固定 workflow track**: 与 Roo Code / Claude Code 的"intent-driven"模式冲突

## 重构原则

### Principle 1: 对话流为中心
- 所有信息（工具调用、文件改动、任务状态）都应该是**对话消息的一部分**
- 取消 Inspector 的多 tab 分散设计，改为：
  - **Sidebar**: 文件树 + 简要状态概览（workspace snapshot）
  - **Main**: 对话流（核心交互区）
  - 可展开的 inline 详情（而非侧边栏 tabs）

### Principle 2: 用户意图驱动 Workflow
- Mode **只控制权限/工具范围**，不预设任何 workflow phase
- Task graph **按需生成** —— 模型根据用户输入判断是否需要构建流程
- 如果用户说"hi"，模型收到的是"你有 build 权限，但没有当前任务"，不会自动开始构建

### Principle 3: 任务完成度自判
- 移除固定 `max_turns` 限制
- 模型在 context 中收到"如何判断任务完成"的指引
- Guard（死循环检测）作为兜底，而非 step 限制
- 设计清晰的"完成信号":
  - 模型主动输出 `<done>` 或类似标记
  - 或在最后一步总结"已完成"，由系统识别

### Principle 4: 渐进式披露
- 复杂信息默认折叠（如 tool 输出、diff）
- 用户主动展开查看详情
- 关键信息（如错误、权限请求）醒目展示但不阻断流程

### Principle 5: 工具调用 Inline 展示
- 文件读取: inline code block，带文件路径标签
- 文件编辑: inline diff preview（使用 `DiffView`），用户确认后应用
- 命令执行: collapsible output，实时流式显示
- 状态: 工具生命周期标签（running... → done/error）

### Principle 6: Session 简洁持久化
- 唯一 truth: `transcript.jsonl`（JSON Lines，每行一个 event）
- 恢复: 从 JSONL 重建 `Session` 对象 → 前端 timeline
- 避免 split snapshot/timeline bootstrap，使用 single bootstrap payload

## 关键代码改动点

### Harness 层
- `harness/registry.py`: 移除或弱化固定 `lite_track` / `full_track`
- `harness/runner.py`: `describe_mode()` 不再无条件生成 task graph；改为按需生成
- `harness/task_graph.py`: 支持动态 task 创建，不绑定固定 phase
- `modes.py`: system prompt 不再包含预设 workflow 描述

### Query Engine 层
- `query_engine.py:899`: 移除 `range(self.max_turns)` 硬循环
- 添加"任务完成度检测"逻辑（guard + 完成信号）
- `context.py`: 动态 task graph 注入逻辑

### Frontend 层
- `App.jsx`: 从三栏布局调整为"Sidebar + Chat"两栏，Inspector 内容内联到对话
- `Timeline.jsx`: 简化嵌套，工具调用 inline 展示，diff preview 内联
- `Composer.jsx`: 保持简洁，mode badge 可隐藏或简化
- `DiffView.jsx`: 在对话流中内联使用

## 成功标准

- [ ] 进入 build 模式说"hi"不会触发任何构建动作
- [ ] 用户明确说"帮我实现 X"才生成 task graph
- [ ] 复杂任务可以持续 20+ 轮不被打断
- [ ] 对话流清晰可读，工具调用 inline 展示
- [ ] 文件编辑 diff 在对话中直接预览
- [ ] Session 恢复成功率 > 95%
- [ ] Win7 离线环境正常运行

## 参考材料

- `.planning/phases/01-ui-ux-harness-research/01-RESEARCH.md` — Reference engineering deep-dive
- `reference/claude-code/` — TUI conversation patterns
- `reference/codex/` — App-based chat patterns
- `reference/opencode/` — CLI interaction patterns
- `reference/Roo-Code/` — VS Code extension UX
- `reference/superpowers/` — Workflow orchestration
- `reference/get-shit-done/` — Task execution patterns
