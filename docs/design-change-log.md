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

---

## 4. 维护约定

- 若改动影响总体架构，更新本文件
- 若改动影响项目纪律或版本边界，同时更新 `AGENTS.md`
- 若改动影响实施顺序，同时更新 `docs/implementation-roadmap.md`
- 若改动具有长期不可逆影响，补充一个 ADR
