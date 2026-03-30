# EmbedAgent 设计与变更跟踪

> 更新日期：2026-03-30
> 用途：记录关键设计变更、影响范围、关联文档和后续动作

---

## 1. 使用规则

本文件不是完整 changelog，也不是 ADR 替代品。

它的定位是：

- 记录“已经发生的关键设计变化”
- 标明“哪些文档受影响”
- 指向相关 ADR、方案文档、实现任务

适合记录的变更类型：

- 架构分层变化
- 模式系统变化
- Python / 打包 / 运行时主线变化
- 工具链或质量门设计变化
- 文档治理机制变化

若某个变更足够重大且具有长期影响，应同时新增 ADR。

---

## 2. 变更记录格式

建议每次新增一条记录，包含：

- `ID`
- `日期`
- `变更主题`
- `变更摘要`
- `影响范围`
- `关联文档`
- `是否需要 ADR`
- `后续动作`

---

## 3. 当前变更记录

### DC-001

- 日期：2026-03-27
- 变更主题：确立 Windows 7 离线 Agent Core 总体架构
- 变更摘要：
  - 确立 `Frontend -> Agent Core API -> Orchestration -> Runtime/LLM/State` 分层
  - 确立 Agent Core 为产品本体，前端可替换
  - 确立 Python 3.8、离线打包、Clang 生态为主线
- 影响范围：
  - 总体架构
  - 技术选型
  - 运行时约束
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
- 是否需要 ADR：`暂缓`
- 后续动作：
  - 进入 Core 骨架细化

### DC-002

- 日期：2026-03-27
- 变更主题：确立可配置模式与 Agent Harness
- 变更摘要：
  - 确立模式是 Core 契约而不是 UI 标签
  - 确立 `ask / orchestra / spec / code / test / verify / debug / compact` 模式集
  - 确立 `Spec-Driven + TDD + Coverage/MC/DC Gate` 默认工程方法学
- 影响范围：
  - Core 设计
  - Harness 设计
  - 多智能体演进路径
- 关联文档：
  - `docs/overall-solution-architecture.md`
  - `AGENTS.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`建议后续补`
- 后续动作：
  - 编写 `docs/mode-schema.md`
  - 编写 `docs/harness-state-machine.md`

### DC-003

- 日期：2026-03-27
- 变更主题：建立文档治理与版本策略
- 变更摘要：
  - 建立 `AGENTS.md`
  - 建立 `implementation-roadmap.md`
  - 建立 `docs/adrs/`
  - 锁定 Python `>=3.8,<3.9`
  - 明确 `uv` 优先、`conda` 兜底
- 影响范围：
  - 开发环境
  - 文档治理
  - 后续实现纪律
- 关联文档：
  - `AGENTS.md`
  - `docs/implementation-roadmap.md`
  - `.python-version`
  - `pyproject.toml`
- 是否需要 ADR：`可不单独写`
- 后续动作：
  - 建立进度跟踪文件
  - 在每轮关键设计调整时持续维护本文件

### DC-004

- 日期：2026-03-27
- 变更主题：工具集设计提升为一等公民
- 变更摘要：
  - 内网模型（GLM5 int4、Qwen3.5）验证表明工具集设计质量是系统稳定性的关键变量
  - 确立每个模式工具上限 5 个（目标 3-4 个）
  - 确立工具描述模板：中文描述 + 英文命名，三段结构，参数含示例
  - 确立 7 类工具设计反模式（禁止使用）
  - 确立结构化 Observation 规范
  - Clang on Win7 风险项解除：已验证完全静态链接的最新版 Clang 可正常运行
- 影响范围：
  - 所有工具的实现与 schema 编写
  - 工具数量与模式分配
  - 工具返回值结构
- 关联文档：
  - `docs/tool-design-spec.md`（新建）
  - `docs/overall-solution-architecture.md`（补充 §8.3a）
  - `AGENTS.md`（补充工具规范约束）
- 是否需要 ADR：`暂缓，先在 Phase 1 验证后再决定是否需要`
- 后续动作：
  - 每次新增工具前必须过 `docs/tool-design-spec.md` 审查清单
  - Phase 1 完成后根据实际测试结果补充兼容处理细节

### DC-005

- 日期：2026-03-27
- 变更主题：实施分期重组，关键路径前移
- 变更摘要：
  - 原 Phase 1（Core 骨架）+ 原 Phase 3（LLM Adapter）合并为新 Phase 1（最小可工作 Loop）
  - Phase 2 改为工具集 v1（run_command + git），Phase 3 改为模式系统 v1
  - 每个 Phase 结束时必须有可实际运行的端到端验证点
  - `orchestra` 模式推迟到 Phase 3 之后实现
  - Harness 改为分阶段叠加：Phase 1 无 Harness，Phase 3 引入 dict 实现，Phase 5 可选 TOML
- 影响范围：
  - 实施顺序与里程碑定义
  - 开发节奏（从文档驱动转为端到端验证驱动）
- 关联文档：
  - `docs/implementation-roadmap.md`（Phase 1-5 重写）
  - `docs/development-tracker.md`（里程碑、任务板、风险更新）
  - `docs/overall-solution-architecture.md`（补充 Harness 演进路径）
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 直接进入 Phase 1 编码

### DC-006

- 日期：2026-03-27
- 变更主题：Phase 1 骨架收敛到 `src/embedagent`，模型验证策略允许受限替代
- 变更摘要：
  - 将 Phase 1 原型代码从仓库根目录平铺模块收敛到 `src/embedagent/` 包结构
  - `pyproject.toml` 同步切换为 `src` 布局与 console script 入口
  - 当 `GLM5 int4` / `Qwen3.5` 联调环境暂不可用时，允许用可访问的 OpenAI-compatible 服务完成真实 function calling 闭环验证
  - 基于 Moonshot `kimi-k2.5` 补齐了 `temperature` 与 `reasoning_content` 兼容处理
- 影响范围：
  - 代码组织结构
  - Phase 1 验证口径
  - LLM 适配层兼容策略
- 关联文档：
  - `pyproject.toml`
  - `README.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/llm-adapter.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 2 工具集实现

### DC-007

- 日期：2026-03-28
- 变更主题：Phase 2 工具集 v1 落地并验收
- 变更摘要：
  - 在 `src/embedagent/tools/` 包中实现 `run_command`、`git_status`、`git_diff`、`git_log`
  - 命令执行支持超时终止，并在 Windows 上使用 `taskkill /F /T /PID` 处理进程树
  - 建立 `docs/tool-contracts.md` 记录当前工具 Observation 契约
  - 在 Python 3.8.10 环境下完成工具直调与 Loop 烟雾验证
- 影响范围：
  - Tool Runtime
  - Phase 2 验证口径
  - 后续模式系统的工具过滤基线
- 关联文档：
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tools/shell_ops.py`
  - `src/embedagent/tools/git_ops.py`
  - `docs/tool-contracts.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 3 模式系统 v1

### DC-008

- 日期：2026-03-28
- 变更主题：Phase 3 模式系统 v1 落地并验收
- 变更摘要：
  - 新增 `src/embedagent/modes.py`，以 Python dict 形式定义 `MODE_REGISTRY`
  - Loop 按当前模式过滤工具，并对违规工具调用返回失败 Observation
  - 实现 `switch_mode(target)` 工具与用户显式 `/mode <name>` 入口
  - `edit_file` 增加基于 `writable_globs` 的写入边界检查
  - 新增 `docs/mode-schema.md` 与 `docs/harness-state-machine.md`
- 影响范围：
  - Agent Loop
  - CLI 入口
  - Tool Runtime 调用边界
  - 后续 Harness 演进基线
- 关联文档：
  - `src/embedagent/modes.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `docs/mode-schema.md`
  - `docs/harness-state-machine.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 4 Clang 工具链实现

### DC-009

- 日期：2026-03-28
- 变更主题：Phase 4 工具链第一版封装落地
- 变更摘要：
  - 在 `src/embedagent/tools/build_ops.py` 中新增 `compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
  - 引入 Clang/MSVC 风格诊断解析、测试结果统计和覆盖率摘要提取
  - 调整 `code` / `test` / `verify` 模式工具集，使其更贴近阶段职责
  - 建立 `docs/clang-integration-plan.md`，明确当前采用显式 command 封装、后续再接真实工具链
- 影响范围：
  - Tool Runtime
  - Mode Registry
  - Phase 4 验证口径
- 关联文档：
  - `src/embedagent/tools/build_ops.py`
  - `src/embedagent/modes.py`
  - `docs/tool-contracts.md`
  - `docs/clang-integration-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 接入真实项目构建命令与 Clang 二进制路径

### DC-010

- 日期：2026-03-28
- 变更主题：项目内闭环 Clang 工具链组装与验证
- 变更摘要：
  - 下载并测试多个静态 Windows LLVM/Clang 发行包
  - 基于 `clang-20.1.8 libcmt`、静态 `clang-tidy` 和 `win-llvm 21.1.8` 组装出 `toolchains/llvm/current`
  - 在 `ToolRuntime` 中为子进程自动注入 `toolchains/llvm/current/bin` 与 `libexec`
  - 补本地 `clang-analyzer` 包装入口
  - 完成编译、静态分析、clang-tidy、profdata、llvm-cov 的真实 smoke test
- 影响范围：
  - 本地工具链目录布局
  - Tool Runtime 的子进程环境
  - Phase 4 验证口径
- 关联文档：
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tools/build_ops.py`
  - `docs/clang-integration-plan.md`
  - `toolchains/README.md`
  - `toolchains/manifest.json`
  - `scripts/activate-bundled-llvm.ps1`
  - `scripts/test-bundled-llvm.ps1`
- 是否需要 ADR：`暂不写，先等待真实工程和 Win7 验证结果`
- 后续动作：
  - 收敛版本组合
  - 在真实 C 工程和 Win7 上补验

### DC-011

- 日期：2026-03-28
- 变更主题：Phase 5 最小权限与防循环保护落地
- 变更摘要：
  - 新增 `src/embedagent/permissions.py`，定义最小权限分类和 CLI 确认策略
  - 新增 `src/embedagent/guard.py`，实现连续失败与相同失败动作的防护
  - `AgentLoop` 接入权限确认和 Doom Loop Guard
  - CLI 增加 `--approve-all`、`--approve-writes`、`--approve-commands`
  - 工具链 smoke test 脚本增加清理逻辑，减少临时产物污染
- 影响范围：
  - Agent Loop
  - CLI 入口
  - Phase 5 验证口径
- 关联文档：
  - `src/embedagent/permissions.py`
  - `src/embedagent/guard.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `docs/permission-model.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 继续补上下文压缩和更细粒度权限规则

### DC-012

- 日期：2026-03-28
- 变更主题：Phase 5 第一版上下文管理落地
- 变更摘要：
  - 新增 `src/embedagent/context.py`，以确定性规则实现会话上下文构建
  - `Turn` 新增消息范围索引，允许精确保留最近 turn 的原始消息链
  - 旧 turn 被压缩为摘要，工具 Observation 被结构化遮蔽与截断
  - `AgentLoop` 在每轮模型调用前不再直接发送全量 `session.messages`，而是交由 `ContextManager` 构建上下文
  - 新增 `docs/context-management-design.md` 记录当前策略与后续演进方向
- 影响范围：
  - Session 结构
  - Agent Loop 的上下文构建流程
  - Phase 5 上下文预算与压缩口径
- 关联文档：
  - `src/embedagent/context.py`
  - `src/embedagent/session.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 引入更精确的 token 预算
  - 视需要增加 LLM 摘要压缩路径

### DC-013

- 日期：2026-03-28
- 变更主题：Phase 5A 上下文预算器与 Observation Reducer Registry 落地
- 变更摘要：
  - `ContextManager` 引入 mode-aware budget，为不同模式分配不同输入预算并预留输出/推理空间
  - 新增 `ContextPolicy`、`BudgetEstimate`、`ContextStats`，让上下文压缩过程可观测
  - 引入 `ReducerRegistry`，按工具类型裁剪 Observation，而不是只依赖统一截断逻辑
  - `AgentLoop` 在构建上下文时显式传入当前 mode，使预算策略不再只靠 system prompt 反推
- 影响范围：
  - Context Manager
  - Agent Loop 的模型输入构建逻辑
  - Phase 5 上下文压缩评估与后续 condenser 触发策略
- 关联文档：
  - `src/embedagent/context.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在 Tool Runtime 源头引入 Artifact Store
  - 持久化 session summary
  - 评估可选 LLM condenser 的接入点

### DC-014

- 日期：2026-03-28
- 变更主题：Phase 5B Artifact Store 与 Observation 源头瘦身落地
- 变更摘要：
  - 新增 `src/embedagent/artifacts.py`，提供本地 artifact 落盘与基础脱敏能力
  - `ToolRuntime` 在 Observation 返回前，会把长 `content/stdout/stderr/diff` 和大列表写入 `.embedagent/memory/artifacts/...`
  - Observation 改为保留预览 + `artifact_ref` + 元数据，不再把大输出完整塞入会话
  - `ContextManager` 的 reducer 现在会保留关键 `artifact_ref`，允许模型按需回看工件
- 影响范围：
  - Tool Runtime
  - 上下文管理链路
  - Tool Observation 契约
- 关联文档：
  - `src/embedagent/artifacts.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/context.py`
  - `docs/tool-contracts.md`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 持久化 session summary
  - 增加 artifact 生命周期清理与索引
  - 评估是否需要单独的 artifact 读取工具

---

### DC-015

- 日期：2026-03-28
- 变更主题：Phase 5C Session Summary Store 与会话状态持久化落地
- 变更摘要：
  - 新增 `src/embedagent/session_store.py`，负责将会话关键状态持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
  - `AgentLoop` 在初始化、构建上下文、assistant 回复和 Observation 回注后都会刷新摘要文件
  - 摘要当前保留 `user_goal`、`current_mode`、`working_set`、`modified_files`、`last_success`、`last_blocker`、`recent_actions`、`recent_artifacts` 以及最近一次上下文预算统计
  - 该摘要文件作为后续恢复入口和 Project Memory 的基础落点，而不是全量历史回放
- 影响范围：
  - Agent Loop
  - 会话状态持久化
  - Phase 5 后续恢复与记忆演进路径
- 关联文档：
  - `src/embedagent/session_store.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 建立 Project Memory 加载层
  - 增加基于 `summary.json` 的恢复入口
  - 为 session / artifact 增加生命周期清理与索引

---

### DC-016

- 日期：2026-03-28
- 变更主题：Phase 5D Project Memory Store 与项目级记忆装载落地
- 变更摘要：
  - 新增 `src/embedagent/project_memory.py`，维护 `project-profile.json`、`command-recipes.json`、`known-issues.json` 与处理索引
  - `AgentLoop` 在持久化 session summary 后，会继续刷新 Project Memory
  - `ContextManager` 现在会按当前 mode 装载 Project Memory system message
  - 模型在新轮次中可直接看到项目硬约束、最近成功命令 recipe 和最近 open issue
- 影响范围：
  - Agent Loop
  - Context Manager
  - Phase 5 后续恢复与长期记忆演进路径
- 关联文档：
  - `src/embedagent/project_memory.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/context.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 增加基于 `summary.json` 的恢复入口
  - 为 memory 文件增加生命周期清理与索引
  - 评估是否需要 Project Memory 的显式编辑入口

### DC-017

- 日期：2026-03-28
- 变更主题：Phase 5E Resume Entry 与会话索引落地
- 变更摘要：
  - `SessionSummaryStore` 新增 `index.json`、最近会话列表、`latest` 解析和摘要加载能力
  - CLI 新增 `--list-sessions` 与 `--resume <session_id|latest|summary.json>`
  - 恢复会话时，会基于 `summary.json` 注入恢复摘要，再叠加当前模式 prompt 与 Project Memory
  - 这使 Phase 5 的记忆层首次形成“落盘 -> 列出 -> 加载 -> 续跑”的闭环
- 影响范围：
  - CLI 入口
  - Session Summary Store
  - Context Manager 的 system message 装载逻辑
- 关联文档：
  - `src/embedagent/cli.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/context.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 为 memory 文件增加生命周期清理与索引收口
  - 继续细化权限规则
  - 在长任务上验证恢复与记忆层稳定性

### DC-018

- 日期：2026-03-28
- 变更主题：Phase 5F Memory Maintenance 与记忆生命周期清理落地
- 变更摘要：
  - 新增 `src/embedagent/memory_maintenance.py`，统一协调 artifact / session / project memory 的清理
  - `ArtifactStore` 新增 `index.json` 与基础 cleanup 能力
  - `SessionSummaryStore` 新增会话目录 cleanup 与活跃 artifact 引用收集
  - `ProjectMemoryStore` 新增 artifact 引用收集与 resolved issue 收敛
  - `AgentLoop` 现在会周期性触发 memory maintenance，避免文件型记忆无限增长
- 影响范围：
  - Artifact / Session / Project Memory 全链路
  - Agent Loop 的后台维护逻辑
  - Phase 5 的长期稳定性与离线可持续运行能力
- 关联文档：
  - `src/embedagent/memory_maintenance.py`
  - `src/embedagent/artifacts.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/project_memory.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在长任务上验证 cleanup 策略是否足够稳健
  - 继续细化权限规则
  - 评估 memory browse / inspect 入口

### DC-019

- 日期：2026-03-28
- 变更主题：Phase 5 长任务稳定性验证完成并升级规则驱动权限模型
- 变更摘要：
  - 新增 `scripts/validate-phase5.py`，提供 Phase 5 的长任务稳定性与权限专项回归入口
  - 完成 20+ turn 长任务、多次上下文压缩、恢复续跑和 Project Memory 注入的本地验证
  - `PermissionPolicy` 升级为规则驱动模型，支持 `allow / ask / deny`、路径 glob 和命令正则匹配
  - CLI 新增 `--permission-rules`，支持加载 `.embedagent/permission-rules.json`
- 影响范围：
  - 权限模型
  - Phase 5 验证基线
  - CLI 配置入口
- 关联文档：
  - `src/embedagent/permissions.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `scripts/validate-phase5.py`
  - `docs/permission-model.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在真实模型与更长时间跨度上补稳定性验证
  - 继续推进 Phase 4 真正工程验证
  - 评估 memory browse / inspect 入口

### DC-020

- 日期：2026-03-28
- 变更主题：Phase 6 前端协议与 TUI 信息架构设计落地
- 变更摘要：
  - 新增 `docs/frontend-protocol.md`，定义 Frontend 与 Core 的 Command / Event 边界、In-Process adapter 和 stdio JSON-RPC 演进路径
  - 新增 `docs/tui-information-architecture.md`，定义首版 TUI 的页面结构、关键交互流和首版范围边界
  - 明确 Phase 6 首先实现 `InProcessAdapter`，再在其上构建最小 TUI，最后才考虑 stdio adapter
- 影响范围：
  - Phase 6 实现顺序
  - CLI / TUI 的边界定义
  - Frontend 与 Core 的协议收敛方式
- 关联文档：
  - `docs/frontend-protocol.md`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 实现 `InProcessAdapter`
  - 让现有 CLI 改为通过 adapter 调用 Core
  - 在 adapter 上实现最小 TUI

### DC-021

- 日期：2026-03-28
- 变更主题：Phase 6A InProcessAdapter 落地并接管 CLI 驱动路径
- 变更摘要：
  - 新增 `src/embedagent/inprocess_adapter.py`，统一封装会话创建、恢复、消息提交、事件回调和会话快照
  - `AgentLoop` 新增 `on_context_result` 钩子，允许前端层接收 `context_compacted` 事件
  - 现有 CLI 已改为通过 `InProcessAdapter` 驱动 Core，而不再直接组装 loop
  - 当前适配层已具备 Phase 6 最小可用边界，为最小 TUI 直接复用铺平路径
- 影响范围：
  - CLI 入口
  - Frontend / Core 协议落地方式
  - Phase 6 的实现顺序
- 关联文档：
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/cli.py`
  - `src/embedagent/loop.py`
  - `docs/frontend-protocol.md`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在 adapter 之上实现最小 TUI
  - 评估是否需要 stdio adapter 提前落地
  - 继续推进 Phase 4 真实工程验证

### DC-022

- 日期：2026-03-28
- 变更主题：Phase 6B 最小 TUI 原型接入 CLI
- 变更摘要：
  - 新增 `src/embedagent/tui.py`，在 `InProcessAdapter` 之上实现最小单会话 TUI 骨架
  - TUI 已具备 Header、Transcript、Side Panel、Composer 和基本快捷键
  - 现有 CLI 新增 `--tui` 入口，并在依赖缺失时返回明确错误提示
  - 当前已验证普通 CLI 不退化，以及 `--tui` 在缺少 `prompt_toolkit` / `rich` 时会 graceful fallback
- 影响范围：
  - CLI 入口
  - Phase 6 最小可运行交互壳
  - 后续 TUI 实现节奏
- 关联文档：
  - `src/embedagent/tui.py`
  - `src/embedagent/cli.py`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 补齐 `prompt_toolkit` / `rich` 依赖并完成真实运行验证
  - 完善权限确认、会话列表和侧栏刷新交互
  - 评估是否推进 stdio adapter

### DC-023

- 日期：2026-03-28
- 变更主题：Phase 6B 最小 TUI 交互深化与 `--tui` 空启动修复
- 变更摘要：
  - `src/embedagent/tui.py` 新增会话列表浏览、选中恢复、帮助/快照侧栏，以及权限、错误、上下文压缩状态展示
  - `src/embedagent/cli.py` 修复 `--tui` 仍要求启动消息的问题，并支持将可选初始消息交给 TUI 在首轮自动提交
  - 已补做本地回归：普通 CLI 不退化，TUI 逻辑可用假依赖验证，缺失 `prompt_toolkit` / `rich` 时继续保持 graceful fallback
- 影响范围：
  - Phase 6 最小 TUI 交互能力
  - CLI 的 `--tui` 启动路径
  - 后续真实 TUI 运行验证的准备状态
- 关联文档：
  - `src/embedagent/tui.py`
  - `src/embedagent/cli.py`
  - `README.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 补齐 `prompt_toolkit` / `rich` 依赖并完成真实运行验证
  - 评估是否接入 artifact 浏览或 inspect 入口
  - 继续推进 Phase 4 真实工程验证

### DC-024

- 日期：2026-03-28
- 变更主题：Phase 6B TUI 依赖接入与宿主兼容性收口
- 变更摘要：
  - `pyproject.toml` 已声明 `prompt-toolkit==3.0.52` 与 `rich==14.3.3`，开发环境可通过 `uv sync --python 3.8.10` 直接拉起 TUI 依赖
  - `src/embedagent/tui.py` 新增非控制台宿主拦截，遇到 `NoConsoleScreenBufferError` 时会转换为清晰的 `TUIUnavailableError`
  - 新增 `EMBEDAGENT_TUI_HEADLESS=1` 的内部验证路径，用于在当前宿主下跑通真实 prompt_toolkit 事件循环
- 影响范围：
  - TUI 依赖声明
  - 非控制台宿主的错误体验
  - Phase 6 的自动化验证能力
- 关联文档：
  - `pyproject.toml`
  - `src/embedagent/tui.py`
  - `README.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实控制台里补一轮手工验证
  - 评估是否为 headless 验证补独立脚本
  - 继续推进 Phase 4 真实工程验证

### DC-025

- 日期：2026-03-28
- 变更主题：Phase 6 进入脚本可追踪状态
- 变更摘要：
  - 新增 `scripts/validate-phase6.py`，固化 Phase 6 的自动化验证入口
  - 新增 `docs/phase6-validation.md`，记录自动化命令与真实控制台手工验证清单
  - 修正 `docs/frontend-protocol.md` 中 Phase 6B/6C 的阶段编号，使其与实际实现顺序一致
- 影响范围：
  - Phase 6 验证口径
  - 前端协议文档与路线图一致性
  - 阶段收口状态的可追踪性
- 关联文档：
  - `scripts/validate-phase6.py`
  - `docs/phase6-validation.md`
  - `docs/frontend-protocol.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实控制台里执行手工验证并记录结果
  - 继续推进 Phase 4 真实工程验证

## 4. 维护约定

- 若改动影响总体架构，更新本文件
- 若改动影响项目纪律或版本边界，同时更新 `AGENTS.md`
- 若改动影响实施顺序，同时更新 `docs/implementation-roadmap.md`
- 若改动具有长期不可逆影响，补充一个 ADR


### DC-026

- 日期：2026-03-29
- 变更主题：Phase 6 终端前端模块化与浏览接口扩展
- 变更摘要：
  - `src/embedagent/tui.py` 已收敛为兼容 shim，真实终端前端迁移到 `src/embedagent/frontends/terminal/`
  - 终端前端按 `state / reducer / controller / layout / services / views` 拆分，避免继续把交互逻辑堆在单文件中
  - `InProcessAdapter` 新增 workspace / timeline / artifact / todo 读取接口，并接入 `SessionTimelineStore`
  - 新增单元测试覆盖 timeline store、adapter 前端接口与终端补全模块；`scripts/validate-phase6.py` 回归通过
- 影响范围：
  - Phase 6 前端包结构
  - Frontend/Core 浏览型接口边界
  - 后续 Win7 控制台与 ConEmu 收口路径
- 关联文档：
  - `src/embedagent/frontends/terminal/`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/session_timeline.py`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实 Win7 控制台与 ConEmu 下补手工验证
  - 继续细化 explorer / editor / plan 交互
  - 评估是否将同一协议推广到 stdio adapter

### DC-027

- 日期：2026-03-29
- 变更主题：修复根目录文件写入边界匹配并对齐当前文档状态
- 变更摘要：
  - `modes.py` 现在把前导 `**/` 视为“可为空的目录前缀”，使 `README.md`、`AGENTS.md`、`pyproject.toml` 等根目录文件能按模式写入规则正确匹配
  - `tests/test_modes.py` 新增根目录 `README.md` / `pyproject.toml` / `manage.py` 的可写边界回归
  - `scripts/validate-phase5.py` 已在该修复后重新跑通，Phase 5 状态从“实现完成”校正为“脚本复验通过”
  - README、路线图、进度跟踪与变更日志已同步对齐当前能力、阶段状态与验证口径
- 影响范围：
  - 模式写入边界
  - Phase 5 验证基线
  - 文档治理一致性
- 关联文档：
  - `src/embedagent/modes.py`
  - `tests/test_modes.py`
  - `README.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
  - `docs/design-change-log.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 继续推进 Phase 4 真实 C 工程与 Win7 验证
  - 在真实控制台与 Win7 / ConEmu 下完成 Phase 6 手工验证
  - 启动 Phase 7 打包文档与前置自检设计

### DC-028

- 日期：2026-03-29
- 变更主题：建立 Phase 7 离线打包与 Win7 preflight 设计基线
- 变更摘要：
  - 新增 `docs/offline-packaging.md`，固定 one-folder portable bundle、目录布局、组件清单、构建流水线与 bundle 级验证口径
  - 新增 `docs/win7-preflight-checklist.md`，固定 Windows 7 目标机部署与首次运行检查项
  - 新增 ADR `0001-offline-portable-bundle-baseline.md`，把 Phase 7 首个交付形态收敛为 x64 one-folder portable bundle
  - README、tracker 与 roadmap 已同步登记 Phase 7 设计基线已建立
- 影响范围：
  - Phase 7 交付路线
  - 文档治理与验收口径
  - 后续打包脚本命名与职责拆分
- 关联文档：
  - `README.md`
  - `docs/offline-packaging.md`
  - `docs/win7-preflight-checklist.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/adrs/0001-offline-portable-bundle-baseline.md`
- 是否需要 ADR：`已补 ADR-0001`
- 后续动作：
  - 落 bundle manifest / checksum / license 生成方案
  - 规划 `prepare-offline` / `build-offline-bundle` / `validate-offline-bundle` 脚本骨架
  - 在 Win7 虚拟机上按 preflight 口径完成首轮 bundle 验收

### DC-029

- 日期：2026-03-29
- 变更主题：落地 Phase 7A `prepare-offline` 脚本骨架
- 变更摘要：
  - 新增 `scripts/prepare-offline.ps1`，可生成 `build/offline-staging/EmbedAgent/` 目录布局
  - 该脚本会写出 `embedagent.cmd`、`embedagent-tui.cmd`、默认配置模板、`bundle-manifest.json` 和 `checksums.txt`
  - 脚本支持 `-SkipBuild`，允许在第三方资产尚未收齐时先生成稳定的 staging 布局和组件状态清单
  - 已用 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证脚本可运行
- 影响范围：
  - Phase 7 打包脚本分层
  - bundle 目录布局的可执行基线
  - manifest / checksum 生成口径
- 关联文档：
  - `scripts/prepare-offline.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 补 `build-offline-bundle.ps1`
  - 补 `validate-offline-bundle.ps1`
  - 固化 MinGit / ripgrep / Universal Ctags / embeddable Python 的来源与校验和

### DC-030

- 日期：2026-03-29
- 变更主题：落地 Phase 7B `build-offline-bundle` 脚本骨架
- 变更摘要：
  - 新增 `scripts/build-offline-bundle.ps1`，可直接消费 `build/offline-staging/EmbedAgent/`
  - 脚本会把 staging bundle 复制到 `build/offline-dist/<artifact>/`，重写 dist 上下文 `bundle-manifest.json`，重算 `checksums.txt`，并生成 zip
  - 脚本已在 skeleton bundle 上通过 `powershell.exe -NoProfile -File scripts/build-offline-bundle.ps1` 验证
  - `prepare-offline.ps1` 同步增加对 `__pycache__` / `.pyc` / `.pyo` 的清理，避免把瞬态 Python 产物带进发布包
- 影响范围：
  - Phase 7 build 阶段脚本分层
  - dist 目录与 zip 产物约定
  - bundle manifest / checksum 在 dist 上下文的生成口径
- 关联文档：
  - `scripts/build-offline-bundle.ps1`
  - `scripts/prepare-offline.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 补 `validate-offline-bundle.ps1`
  - 将 launcher、manifest 与关键文件存在性检查纳入自动验证
  - 在真实资产收齐后补全 end-to-end bundle 验证

### DC-031

- 日期：2026-03-29
- 变更主题：落地 Phase 7C `validate-offline-bundle` 脚本骨架
- 变更摘要：
  - 新增 `scripts/validate-offline-bundle.ps1`，可校验 bundle 根目录、manifest、checksums、关键 launcher 和目录布局
  - 默认模式下，缺失 embeddable Python / MinGit / rg / ctags / LLVM 等资产会以告警呈现，便于在 skeleton bundle 阶段继续推进
  - `-RequireComplete` 下，相同缺失项会被提升为失败，作为后续正式离线交付验收门
  - 已在当前 skeleton bundle 上完成两轮验证：默认模式返回告警但通过；`-RequireComplete` 按预期返回失败
- 影响范围：
  - Phase 7 validate 阶段脚本分层
  - skeleton bundle 与正式验收之间的门禁切换策略
  - bundle manifest/checksum 的自动校验口径
- 关联文档：
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在正式验收入口中强制使用 `-RequireComplete`
  - 接入 embeddable Python 与第三方工具后补动态启动验证
  - 将 validate 结果沉淀到 bundle manifest 或独立报告文件

### DC-032

- 日期：2026-03-29
- 变更主题：接入 Python embeddable 与 MinGit 的真实资产链路
- 变更摘要：
  - 新增 `scripts/offline-assets.json`，固定 `python_embedded_x64` 与 `mingit_x64` 的官方 URL、SHA256、stage/cache 路径与 License 元数据
  - `scripts/prepare-offline.ps1` 现在支持 `-AssetManifestPath`、`-AssetIds` 和 `-AllowDownload`，并会对 Python/MinGit 执行缓存校验、按需下载、解压和 license notice 生成
  - Python embeddable 会在 prepare 阶段修补 `python38._pth`，写入 `..\..\app`、`..\site-packages` 和 `import site`
  - `scripts/build-offline-bundle.ps1` 现在会生成 `embedagent-win7-x64-sources/`，包含 `assets-manifest.json`、原始 zip 归档和 `checksums.txt`
  - `scripts/validate-offline-bundle.ps1` 已在真实 Python/MinGit 资产接入后通过默认模式和 `-RequireComplete` 模式验收
- 影响范围：
  - Phase 7 真实资产接入路径
  - bundle manifest / sources seed 结构
  - Python embeddable 启动方式
- 关联文档：
  - `scripts/offline-assets.json`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 接入 `ripgrep` 与 `Universal Ctags`
  - 评估是否用更精简的方式导出运行时 `site-packages`
  - 在 Win7 虚拟机上补 bundle 级真实验收

### DC-033

- 日期：2026-03-29
- 变更主题：接入 ripgrep 与 Universal Ctags 的真实资产链路
- 变更摘要：
  - `scripts/offline-assets.json` 已新增 `ripgrep_x64` 与 `universal_ctags_x64`，固定官方 URL、SHA256、stage/cache 路径与 License 元数据
  - `scripts/prepare-offline.ps1` 现在会对这两类 zip 执行缓存校验、按需下载、解压与 license notice 生成
  - prepare 新增“单层顶级目录自动拍平”逻辑，使 ripgrep zip 能稳定落到 `bin/rg/rg.exe`
  - `scripts/validate-offline-bundle.ps1` 已把 `rg.exe`、`ctags.exe`、对应 license notice、sources archive 和 `--version` 动态检查纳入正式门禁
  - 当前 `prepare/build/validate -RequireComplete` 已在 Python / MinGit / ripgrep / Universal Ctags 四类核心资产上全量通过
- 影响范围：
  - Phase 7 第三方资产接入范围
  - bundle 与 sources seed 的完整性门禁
  - validate 的动态工具检查覆盖面
- 关联文档：
  - `scripts/offline-assets.json`
  - `scripts/prepare-offline.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 评估 `.venv\Lib\site-packages` 的精简导出方案
  - 在 Win7 虚拟机上补 bundle 级真实验收
  - 视需要继续收敛第三方工具 license 文件的随包归档方式

### DC-034

- 日期：2026-03-29
- 变更主题：模式/权限解耦与空目录启动收口
- 变更摘要：
  - 新增 `write_file`，允许 agent 在工作区内创建新文件并自动创建父目录，解决空目录下 `spec` 无法起草文档的问题
  - 新增 `ask_user` 与 `waiting_user_input` 交互流，将用户问答与权限审批彻底分开
  - `switch_mode` 不再全模式可用，只保留给 `orchestra`；其他模式只能通过 `ask_user` 或文本建议请求用户决定
  - `MODE_REGISTRY` 的默认可写范围改为按文件类型放行，不再把 `docs/` / `src/` / `tests/` 固定成唯一目录结构
  - 配置新增 `mode_extra_writable_globs`，用于在保留默认值的前提下增量追加可写规则
  - 引入工作区画像 system message，并把非重试型阻塞纳入 LoopGuard 的提前停机逻辑
- 影响范围：
  - Mode Registry
  - Agent Loop / Guard
  - InProcessAdapter / CLI / TUI
  - 配置与文档治理
- 关联文档：
  - `src/embedagent/modes.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/tools/file_ops.py`
  - `src/embedagent/workspace_profile.py`
  - `docs/mode-schema.md`
  - `docs/tool-design-spec.md`
  - `docs/permission-model.md`
  - `docs/configuration-guide.md`
  - `docs/harness-state-machine.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 在真实 TUI / Win7 手工验证中复查 `waiting_user_input` 与 `waiting_permission` 的宿主体验
  - 继续评估 `ask_user` 是否需要被扩展到 `code` / `debug` 等执行模式

### DC-035

- 日期：2026-03-29
- 变更主题：模式系统 v2 重构——5 模式配置驱动，移除 switch_mode LLM 工具
- 变更摘要：
  - 模式集从 8 个缩减为 5 个：`explore`（默认，重命名自 ask）/`spec`/`code`/`debug`/`verify`；删除 `orchestra`、`test`、`compact`
  - `switch_mode` LLM 工具彻底移除；LLM 不能主动切换模式，只能通过 `ask_user` 建议，由用户确认
  - 模式定义迁移到 `_BUILTIN_MODES` + `initialize_modes(workspace)` 配置加载层；项目可通过 `.embedagent/modes.json` 覆盖或新增模式
  - `build_system_prompt()` 改为 `str.format()` + 可替换框架模板（`prompt_frame.txt`）
  - `manage_todos` / `ask_user` 在所有模式中统一可用
  - 会话启动时自动注入待办提示（通过 `workspace_profile.py`）
  - 旧 session 中已删除模式名（如 `orchestra`）自动回落到 `explore`，不崩溃
- 影响范围：
  - `src/embedagent/modes.py`（主要改动）
  - `src/embedagent/loop.py`（删除 switch_mode 逻辑）
  - `src/embedagent/workspace_profile.py`（加入待办提示）
  - `src/embedagent/cli.py` / `inprocess_adapter.py`（调用 initialize_modes）
  - 所有引用旧模式集的文档
- 关联文档：
  - `docs/mode-schema.md`（完全重写）
  - `docs/harness-state-machine.md`（更新切换机制）
  - `docs/tool-design-spec.md`（更新工具分配表）
  - `AGENTS.md`（更新模式政策与 Harness 演进策略）
  - `README.md`（更新模式列表）
  - `docs/implementation-roadmap.md` / `docs/development-tracker.md` / `docs/configuration-guide.md`（同步更新）
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 在真实 TUI / Win7 环境验证新默认模式 `explore` 的入口体验
  - 评估是否需要为常见 C 维护工程提供预置的 `modes.json` 样板文件

### DC-036

- 日期：2026-03-30
- 变更主题：新架构落地——protocol/core/frontend 分层与 GUI PyWebView 前端
- 变更摘要：
  - 新增 `src/embedagent/protocol/`，定义 `CoreInterface`、`FrontendCallbacks` 及数据类型，实现前后端协议层
  - 新增 `src/embedagent/core/adapter.py`，实现 `AgentCoreAdapter` 包装 `InProcessAdapter` 并统一事件分发
  - 新增 `src/embedagent/frontend/gui/`，实现 PyWebView + FastAPI + WebSocket 的 GUI 前端，包含 diff/权限确认弹窗
  - 迁移 `src/embedagent/frontend/tui/`，按新架构实现 `TUIFrontend` 适配器，延迟导入处理缺失依赖
  - 旧 `src/embedagent/frontends/terminal/` 保留向后兼容，未来逐步迁移
  - 新增 `tests/test_architecture.py`，17 项架构测试覆盖协议、Core、前后端导入
  - 新增 `docs/architecture-new.md` 记录新架构设计
- 影响范围：
  - 整体架构分层（新增 protocol/core/frontend）
  - TUI/GUI 前端实现方式
  - Agent Core 与前端解耦程度
  - 文档治理（README、development-tracker、architecture-new）
- 关联文档：
  - `docs/architecture-new.md`（新建）
  - `docs/frontend-protocol.md`（需要后续更新以反映 protocol 层）
  - `docs/development-tracker.md`（新增 T-020、T-021）
  - `README.md`（目录结构、技术选型、项目现状更新）
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/tui/`
  - `src/embedagent/frontend/gui/`
  - `tests/test_architecture.py`
- 是否需要 ADR：`建议后续补 ADR 记录架构分层决策`
- 后续动作：
  - 将旧 `frontends/terminal/` 完全迁移到 `frontend/tui/`
  - 实现 GUI 的 diff/权限确认弹窗与后端实际联动
  - 更新 `docs/frontend-protocol.md` 以反映新 protocol 层设计
  - 在 Win7 环境下验证 GUI 前端兼容性（IE11 回退）
