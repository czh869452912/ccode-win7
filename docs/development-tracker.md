# EmbedAgent 开发进度跟踪

> 更新日期：2026-03-27（DC-004/DC-005 调整后修订）
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
- 工具设计规范 `docs/tool-design-spec.md`（DC-004）
- 实施分期重组（DC-005）：关键路径前移，Phase 1 = 最小可工作 Loop

项目下一步：直接进入 Phase 1 编码，建立最小可工作 Loop 并在内网模型上完成验证。

---

## 3. 下一步优先级

### P0：立刻要做（Phase 1 关键路径）

1. 建立最小 `pyproject.toml` + `src/` 目录骨架
2. 实现 `OpenAI-compatible LLM Adapter`（同步 + 流式，Python 3.8，无厂商 SDK）
3. 实现第一批工具：`read_file`、`list_files`、`search_text`、`edit_file`（按 `docs/tool-design-spec.md` 规范）
4. 实现最小主循环（50-80 行）和命令行入口
5. 在 GLM5 int4 + Qwen3.5 上完成 Phase 1 里程碑验证

### P1：Phase 1 验证通过后

1. 根据验证结果补充 function calling 兼容处理
2. 建立 `docs/llm-adapter.md` 记录兼容细节
3. 实现 Phase 2 工具：`run_command`、`git_status`、`git_diff`

### P2：Phase 2 完成后

1. 设计并实现模式系统 v1（`MODE_REGISTRY` dict + 工具过滤 + `switch_mode`）
2. 编写 `docs/mode-schema.md` 和 `docs/harness-state-machine.md`

---

## 4. 近期任务板

| 编号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| T-001 | 建立最小 `pyproject.toml` + `src/` 目录骨架 | `pending` | Phase 1 起点 |
| T-002 | 实现 `OpenAI-compatible LLM Adapter` | `pending` | 同步+流式，Python 3.8，不引入厂商 SDK |
| T-003 | 实现第一批工具（read/list/search/edit） | `pending` | 严格按 `docs/tool-design-spec.md` 规范 |
| T-004 | 实现最小主循环 + CLI 入口 | `pending` | 50-80 行，无模式系统 |
| T-005 | Phase 1 里程碑验证（GLM5 + Qwen3.5） | `pending` | 两个模型各跑通一次 |
| T-006 | 实现 Phase 2 工具（run_command / git） | `pending` | T-005 通过后开始 |
| T-007 | 实现模式系统 v1（dict + 工具过滤） | `pending` | Phase 3，T-006 后 |

---

## 5. 里程碑进度

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| Phase 0 | 仓库基线与工作约束 | `completed` | 已完成文档、版本策略、治理基线、工具规范 |
| Phase 1 | 最小可工作 Loop | `not_started` | **当前主战场**：LLM Adapter + 4工具 + Loop + CLI，完成内网模型验证 |
| Phase 2 | 工具集 v1 | `not_started` | run_command + git 工具 |
| Phase 3 | 模式系统 v1 | `not_started` | MODE_REGISTRY dict + 工具过滤 + switch_mode |
| Phase 4 | Clang 工具链 | `not_started` | 编译/测试/静态检查，bundle 静态 Clang 二进制 |
| Phase 5 | 质量保障层 | `not_started` | 上下文压缩、权限系统、Doom Loop Guard |
| Phase 6 | CLI / TUI | `not_started` | prompt_toolkit + Rich |
| Phase 7 | 打包与离线交付 | `not_started` | Win7 离线 one-folder bundle |

---

## 6. 当前风险与关注点

| 编号 | 风险 | 当前判断 | 应对方式 |
|------|------|----------|----------|
| R-001 | Python 版本上滑 | 高 | 强制保持 `>=3.8,<3.9`，文档与配置双锁定 |
| R-002 | 过早做 UI 导致核心失焦 | 高 | Phase 6 才做 TUI，Phase 1 只做最简 CLI |
| R-003 | 内网模型 function calling 格式不标准 | 高 | Phase 1 里程碑强制在真实模型上验证，发现问题立即在 LLM Adapter 层补充兼容处理 |
| R-004 | 工具集设计退化（工具增多、描述变复杂） | 中 | `docs/tool-design-spec.md` 有审查清单，每次新增工具前必须过清单 |
| R-005 | 文档和实现脱节 | 高 | 每轮关键变更必须同步更新 tracker / change log / roadmap |
| R-006 | Clang bundle 包大小过大 | 低 | 静态链接验证已通过，打包细节推到 Phase 7 处理 |

---

## 7. 最近更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-03-27 | 建立进度跟踪文件，明确当前阶段与下一步优先级 |
| 2026-03-27 | DC-004/DC-005：工具设计规范建立，实施分期重组，Phase 1 改为最小可工作 Loop |

