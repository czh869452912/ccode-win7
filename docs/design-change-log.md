# EmbedAgent 设计与变更跟踪

> 更新日期：2026-03-27
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
  - 在 `src/embedagent/tools.py` 中实现 `run_command`、`git_status`、`git_diff`、`git_log`
  - 命令执行支持超时终止，并在 Windows 上使用 `taskkill /F /T /PID` 处理进程树
  - 建立 `docs/tool-contracts.md` 记录当前工具 Observation 契约
  - 在 Python 3.8.10 环境下完成工具直调与 Loop 烟雾验证
- 影响范围：
  - Tool Runtime
  - Phase 2 验证口径
  - 后续模式系统的工具过滤基线
- 关联文档：
  - `src/embedagent/tools.py`
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
  - 在 `src/embedagent/tools.py` 中新增 `compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
  - 引入 Clang/MSVC 风格诊断解析、测试结果统计和覆盖率摘要提取
  - 调整 `code` / `test` / `verify` 模式工具集，使其更贴近阶段职责
  - 建立 `docs/clang-integration-plan.md`，明确当前采用显式 command 封装、后续再接真实工具链
- 影响范围：
  - Tool Runtime
  - Mode Registry
  - Phase 4 验证口径
- 关联文档：
  - `src/embedagent/tools.py`
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
  - `src/embedagent/tools.py`
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
  - `src/embedagent/tools.py`
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

## 4. 维护约定

- 若改动影响总体架构，更新本文件
- 若改动影响项目纪律或版本边界，同时更新 `AGENTS.md`
- 若改动影响实施顺序，同时更新 `docs/implementation-roadmap.md`
- 若改动具有长期不可逆影响，补充一个 ADR


