# EmbedAgent 开发进度跟踪

> 更新日期：2026-03-28（DC-017 修订）
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

- 当前阶段：`Phase 5 质量保障层实施中`
- 总体状态：`进行中`
- 当前重点：`在现有闭环基础上补权限控制、防循环保护和上下文管理`

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
- Phase 1 最小原型代码骨架（`src/embedagent/`）
- 本地闭环自测：工具调用、Observation 回注、CLI 启动、语法编译
- Python 3.8.10 `uv` 环境验证通过（`.venv`）
- Moonshot `kimi-k2.5` 真实联调已跑通最小工具闭环（需使用 `/v1`，并保留 `reasoning_content`）
- `docs/llm-adapter.md` 已建立，记录已验证 provider 兼容点
- Phase 2 工具核心实现已落地：`run_command`、`git_status`、`git_diff`、`git_log`
- `docs/tool-contracts.md` 已建立，记录当前工具接口契约
- Phase 2 Loop 烟雾验证通过：`run_command` 与 `git_status` 已通过主循环消费验证
- Phase 3 模式系统 v1 已落地：`MODE_REGISTRY`、工具过滤、`switch_mode`、`/mode`
- `docs/mode-schema.md` 与 `docs/harness-state-machine.md` 已建立
- Phase 3 验证通过：模式切换、违规工具拦截、写入范围拦截均已完成本地验证
- Phase 4 工具第一版已落地：`compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
- `docs/clang-integration-plan.md` 已建立
- Phase 4 解析验证通过：编译诊断、测试汇总、覆盖率提取、质量门评估均已完成本地验证
- 项目内闭环 Clang 工具链已落地到 `toolchains/llvm/current`
- 已完成真实本地 smoke test：编译、analyze、clang-tidy、profdata、llvm-cov report
- Phase 5 最小权限模型已落地：CLI 可对写入和命令执行做确认
- Doom Loop Guard 已落地：连续失败和重复失败动作会触发防护
- `docs/permission-model.md` 已建立
- `docs/context-management-design.md` 已建立
- Phase 5 第一版上下文管理已落地：旧 turn 摘要化、Observation 遮蔽化、最近 turn 保真化
- Phase 5A 上下文预算器已接入：按 mode 分配预算并为输出/推理预留空间
- Phase 5A ReducerRegistry 已落地：不同工具按类型裁剪 Observation，并返回 ContextStats / BudgetEstimate
- Phase 5B Artifact Store 已落地：长输出与大列表会落盘为 `.embedagent/memory/artifacts/...` 并回写 `artifact_ref`
- Phase 5C Session Summary Store 已落地：会话关键状态会持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
- Phase 5D Project Memory Store 已落地：项目级 profile / recipe / known issue 已可落盘并注入上下文
- Phase 5E Resume Entry 已落地：CLI 已支持 `--list-sessions` 与 `--resume <session_id|latest|summary.json>`

项目下一步：继续推进 Phase 5 的记忆生命周期清理、长任务验证与更细粒度权限规则。

---

## 3. 下一步优先级

### P0：立刻要做（Phase 5 关键路径）

1. 为 artifact / session / project memory 增加生命周期清理与索引收口
2. 继续细化权限规则与默认批准策略
3. 在更长任务场景下验证 Doom Loop Guard、ContextManager、Artifact Store、Session Summary Store、Project Memory 与恢复入口

实现备注：

- Phase 1 已按当前可用条件验收完成；`GLM5 int4` / `Qwen3.5` 因环境不具备暂不纳入阻塞项。
- 当前原型已收敛到 `src/embedagent/` 包结构，打包入口与导入路径已同步更新。
- Phase 2 里程碑已满足：文件读写、命令执行、Git 状态/差异/日志均已具备并完成 3.8 本地验证。
- Phase 3 里程碑已满足：模式切换、工具过滤和 `switch_mode` 已具备并完成 3.8 本地验证。
- Phase 4 已具备项目内闭环工具链，但版本混搭仍需后续继续收敛。

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
| T-001 | 建立最小 `pyproject.toml` + 代码骨架 | `completed` | 已收敛为 `src/embedagent/` 包结构 |
| T-002 | 实现 `OpenAI-compatible LLM Adapter` | `completed` | 同步+流式，Python 标准库，无厂商 SDK |
| T-003 | 实现第一批工具（read/list/search/edit） | `completed` | 已按 `docs/tool-design-spec.md` 规范落地 |
| T-004 | 实现最小主循环 + CLI 入口 | `completed` | 本地假模型闭环已跑通 |
| T-005 | Phase 1 里程碑验证（GLM5 + Qwen3.5） | `completed` | 目标模型环境不具备，按 Moonshot + Python 3.8 验证口径验收 |
| T-006 | 实现 Phase 2 工具（run_command / git） | `completed` | 已补齐工具契约与 Loop 烟雾验证 |
| T-007 | 实现模式系统 v1（dict + 工具过滤） | `completed` | 已补齐文档与本地验证 |
| T-008 | 实现 Phase 4 Clang 工具链第一版封装 | `in_progress` | 已有本地闭环工具链，待真实工程验证与版本收敛 |
| T-009 | 实现 Phase 5 最小权限与防循环保护 | `in_progress` | 权限模型、Doom Loop Guard、ContextManager、mode-aware budget、Artifact Store、SessionSummaryStore、ProjectMemoryStore、Resume Entry 已落地 |

---

## 5. 里程碑进度

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| Phase 0 | 仓库基线与工作约束 | `completed` | 已完成文档、版本策略、治理基线、工具规范 |
| Phase 1 | 最小可工作 Loop | `completed` | 已完成 Python 3.8 与真实 OpenAI-compatible 工具闭环验证 |
| Phase 2 | 工具集 v1 | `completed` | 已实现 run_command / git 工具，并完成 3.8 本地验证 |
| Phase 3 | 模式系统 v1 | `completed` | MODE_REGISTRY、工具过滤、switch_mode、/mode 已完成 |
| Phase 4 | Clang 工具链 | `in_progress` | 已有项目内闭环工具链，待真实工程与 Win7 验证 |
| Phase 5 | 质量保障层 | `in_progress` | 最小权限模型、Doom Loop Guard、ContextManager、Artifact Store、SessionSummaryStore、ProjectMemoryStore、Resume Entry 已落地 |
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
| R-007 | provider 兼容差异未系统沉淀 | 中 | 已确认 Moonshot `kimi-k2.5` 需要 `/v1` 和 `reasoning_content`，后续整理到适配文档 |
| R-008 | 当前仓库缺少真实 C 构建入口 | 中 | 已完成本地 smoke test，后续仍需接默认命令和真实工程 |
| R-009 | 当前闭环工具链存在跨版本组合 | 中 | 现状已通过本地 smoke test，后续需要继续收敛到同版本或自建包 |
| R-010 | 当前上下文压缩仍较弱 | 中 | 已有 mode-aware budget、reducer registry、Artifact Store、SessionSummaryStore、ProjectMemoryStore 与 Resume Entry，后续继续补生命周期清理与可选 LLM condenser |

---

## 7. 最近更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-03-27 | 建立进度跟踪文件，明确当前阶段与下一步优先级 |
| 2026-03-27 | DC-004/DC-005：工具设计规范建立，实施分期重组，Phase 1 改为最小可工作 Loop |
| 2026-03-27 | 已落地 Phase 1 最小原型代码，并完成本地语法检查、工具自测与假模型闭环验证 |
| 2026-03-27 | Moonshot `kimi-k2.5` 真实联调通过，补齐了温度参数与 `reasoning_content` 兼容处理 |
| 2026-03-27 | 代码骨架迁移到 `src/embedagent/`，并通过 `uv` 创建的 Python 3.8.10 环境验证 |
| 2026-03-27 | 按当前可用条件完成 Phase 1 验收，并切换到 Phase 2 工具集实现 |
| 2026-03-27 | Phase 2 核心工具已实现，并通过 Python 3.8 本地自测 |
| 2026-03-28 | Phase 2 工具契约与 Loop 烟雾验证完成，阶段状态切换到 Phase 3 准备中 |
| 2026-03-28 | Phase 3 模式系统 v1 已完成，并补齐模式结构与状态机文档 |
| 2026-03-28 | Phase 4 第一版工具封装与解析验证完成，并建立 Clang 集成计划文档 |
| 2026-03-28 | 已下载、组装并验证项目内闭环 Clang 工具链，完成编译/分析/tidy/coverage smoke test |
| 2026-03-28 | Phase 5 最小权限模型与 Doom Loop Guard 已落地，并清理了工具链临时产物 |
| 2026-03-28 | Phase 5 第一版 ContextManager 已落地，并完成本地压缩/回归验证 |
| 2026-03-28 | Phase 5A mode-aware budget、ReducerRegistry 与 ContextStats 已落地，并完成本地行为验证 |
| 2026-03-28 | Phase 5B Artifact Store 已落地，并完成大输出脱敏/落盘/回灌验证 |
| 2026-03-28 | Phase 5C Session Summary Store 已落地，并完成状态落盘/回归验证 |
| 2026-03-28 | Phase 5D Project Memory Store 已落地，并完成 recipe / known issue / context 注入验证 |




