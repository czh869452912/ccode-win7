# EmbedAgent 开发进度跟踪

> 更新日期：2026-03-27
> 用途：持续跟踪当前阶段、下一步任务、里程碑进度、风险与阻塞

---

## 1. 使用规则

本文件用于回答四个问题：

1. 当前做到哪一步了？
2. 下一步最应该做什么？
3. 哪些任务已经完成，哪些仍在阻塞？
4. 当前有哪些风险需要被持续关注？

更新规则：

- 每完成一个里程碑或子里程碑，更新本文件
- 每次重要设计变更，同时检查是否需要同步本文件
- 当前只保留“近期最重要”的 5-10 项任务，不把它写成无限 backlog

---

## 2. 当前阶段

### 总阶段

- 当前阶段：`Phase 1 前置收敛`
- 总体状态：`进行中`
- 当前重点：`把实现入口从“方案文档”推进到“可编码的 Core 设计”`

### 当前判断

项目已经完成：

- 范围和目标收敛
- 参考项目分析
- 总体方案设计
- 实施路线与文档治理基线
- 项目级 `AGENTS.md`
- Python 3.8 / `uv` / `conda` 版本策略落盘

项目下一步不应立刻进入 UI 或打包，而应先把 Core 设计再向下细化一层。

---

## 3. 下一步优先级

### P0：立刻要做

1. 定义 `Mode Registry` 配置 schema
2. 定义 `Agent Harness` 状态机与模式切换规则
3. 定义 Core 领域模型与事件模型

### P1：紧接着做

1. 建立最小 `src/` 目录布局
2. 实现 OpenAI-compatible LLM adapter 骨架
3. 实现最小工具运行时骨架

### P2：随后推进

1. 设计 clang / test / coverage 工具契约
2. 设计权限模型
3. 设计上下文管理骨架

---

## 4. 近期任务板

| 编号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| T-001 | 编写 `docs/mode-schema.md` | `pending` | 明确 mode 配置字段、校验规则、覆盖层次 |
| T-002 | 编写 `docs/harness-state-machine.md` | `pending` | 明确 `ask/orchestra/spec/code/test/verify/debug/compact` 切换规则 |
| T-003 | 编写 `docs/core-domain-model.md` | `pending` | 固化 `Session/Turn/Action/Observation/Task/Artifact` |
| T-004 | 建立最小 `src/` 代码目录与包结构 | `pending` | 在文档先行后开始 |
| T-005 | 建立 LLM adapter 骨架 | `pending` | 只做 OpenAI-compatible 路径 |
| T-006 | 建立 tool runtime 骨架 | `pending` | 文件/命令/Git 先行 |

---

## 5. 里程碑进度

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| Phase 0 | 仓库基线与工作约束 | `completed` | 已完成文档、版本策略、治理基线 |
| Phase 1 | Core 骨架 | `not_started` | 下一步主战场 |
| Phase 2 | Mode Registry 与 Agent Harness | `not_started` | 与 Phase 1 可交错推进 |
| Phase 3 | LLM Adapter | `not_started` | Core 设计稳定后开始 |
| Phase 4 | Runtime 与工具链 | `not_started` | 先文件/命令/Git，再 clang |
| Phase 5 | 上下文、记忆、权限 | `not_started` | 在主链路打通后推进 |
| Phase 6 | CLI / TUI | `not_started` | 不抢在 Core 之前 |
| Phase 7 | 打包与离线交付 | `not_started` | 最后阶段 |

---

## 6. 当前风险与关注点

| 编号 | 风险 | 当前判断 | 应对方式 |
|------|------|----------|----------|
| R-001 | Python 版本上滑 | 高 | 强制保持 `>=3.8,<3.9`，文档与配置双锁定 |
| R-002 | 过早做 UI 导致核心失焦 | 高 | 先做 Core、Harness、Runtime 契约 |
| R-003 | 模式系统做得太重 | 中 | 先做最小可配置字段和有限模式切换 |
| R-004 | Clang 生态集成复杂度低估 | 中 | 先写工具契约与验证样例，不急于全接入 |
| R-005 | 文档和实现脱节 | 高 | 每轮关键变更必须同步更新 tracker / change log / roadmap |

---

## 7. 最近更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-03-27 | 建立进度跟踪文件，明确当前阶段与下一步优先级 |

