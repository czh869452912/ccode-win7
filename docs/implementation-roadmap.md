# EmbedAgent 实施路线与文档维护方案

> 更新日期：2026-04-02（Packaging control plane slice）
> 适用阶段：架构收敛后进入实现前

---

## 1. 文档目标

本文件用于回答三个问题：

1. 接下来按什么顺序实现？
2. 文档应该如何维护，避免方案和实现脱节？
3. 在开发机使用 `uv` 的前提下，如何确保 Python 版本不突破 Windows 7 约束？

---

## 2. 当前共识

- 系统核心是 `Agent Core + Mode Registry + Agent Harness`
- 首期聚焦 C 语言偏应用软件开发，而非通用多语言平台
- 工作流：用户以 `explore` 模式入场（探索/讨论），按需切换到 `spec / code / debug / verify` 等具体模式；产品表层逐步转向 slash command / workflow，模式退到 Core 执行边界
- 工具链围绕 Clang 生态统一组织（已验证完全静态链接的最新版 Clang 可在 Win7 运行）
- 最终运行时必须可在 Windows 7 离线环境中一体化交付
- **工具集设计是一等公民**：每个模式工具上限 5 个，描述格式统一，参见 `docs/tool-design-spec.md`
- **Harness 分阶段叠加**：Phase 1 无 Harness，Phase 3 引入最小 dict 实现，Phase 5 可选 TOML 加载
- **每个 Phase 必须有端到端可验证的里程碑**，不做无法验证的纯抽象层构建

### 2.1 当前执行状态（2026-03-31）

路线图的阶段顺序保持不变，但当前仓库已经不再处于 Phase 1 起步期。

截至 2026-03-31：

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 0 | `completed` | 文档治理、版本策略、约束基线已完成 |
| Phase 1 | `completed` | 最小可工作 Loop 已完成真实 OpenAI-compatible 闭环验证 |
| Phase 2 | `completed` | 文件 / Shell / Git 工具已落地 |
| Phase 3 | `completed` | 模式系统 v1 已落地 |
| Phase 4 | `in_progress` | 本地闭环 LLVM/Clang 工具链已具备，recipe-aware build/test 入口已起步，待真实 C 工程与 Win7 验证 |
| Phase 5 | `completed` | 权限、上下文、记忆、恢复和 cleanup 已落地，`validate-phase5.py` 已复验通过 |
| Phase 6 | `in_progress` | 自动化验证已通过；unified input / slash command / workflow 第一版、step-based timeline 与 Runtime inspector 已落地，待真实控制台 / Win7 / ConEmu 手工验证 |
| Phase 7 | `in_progress` | 离线打包设计文档、ADR、`prepare/build/validate` 三段脚本，以及 Python/MinGit/rg/ctags 真实资产接入已完成；`package.ps1` 控制面已接上 `doctor/deps/assemble/verify/release` mocked orchestration，待继续收口真实 bundle / Win7 验收 |

---

## 3. Python 与环境策略

### 3.1 目标机运行时

- 运行时主线固定为 `Python 3.8`
- 打包目标优先采用 `Python 3.8 embeddable distribution`
- 代码必须保持 `Python 3.8` 语法和标准库兼容

### 3.2 开发机环境

开发机当前已确认：

- `uv 0.7.8` 可用
- `uv` 可见 `CPython 3.8.10` 与 `CPython 3.8.20`

因此建议：

- 默认使用 `uv` 管理开发环境
- 默认锁定 `CPython 3.8.10`
- 若个别开发机上 `uv` 不能提供合适的 `Python 3.8`，则允许使用 `conda` 作为兜底方案

### 3.3 版本控制策略

建议立即固化以下规则：

- `.python-version` 固定为 `3.8.10`
- `pyproject.toml` 中 `requires-python = ">=3.8,<3.9"`
- 所有运行时代码默认按 Python 3.8 约束审查

### 3.4 推荐命令

#### uv 主路径

```powershell
uv python pin 3.8.10
uv sync --python 3.8.10
```

#### conda 兜底路径

```powershell
conda create -n embedagent-py38 python=3.8.10
conda activate embedagent-py38
```

注意：

- `conda` 只作为开发机兜底，不改变目标机运行时方案
- 目标机仍以离线打包的 Python 3.8 运行时为准

---

## 4. 实施分期

### Phase 0：仓库基线与工作约束

目标：

- 固化 Python 版本策略
- 建立项目宪章和实施路线文档
- 统一“谁是事实来源”的文档边界

交付物：

- `AGENTS.md`
- `docs/implementation-roadmap.md`
- `.python-version`
- `pyproject.toml`

### Phase 1：最小可工作 Loop【关键路径，目标 2-3 周】

目标：

- 打通 LLM Adapter + 最小工具集 + 命令行 Loop 的端到端链路
- 在内网 GLM5 int4 和 Qwen3.5 上完成首次 function calling 实际验证

实现重点（5 个核心文件，不超过此范围）：

- `src/embedagent/llm.py`：OpenAI-compatible HTTP 调用（同步 + 流式，无厂商 SDK 依赖）
- `src/embedagent/tools/`：第一批工具包——`read_file`、`list_files`、`search_text`、`edit_file`（按 `docs/tool-design-spec.md` 规范编写）
- `src/embedagent/loop.py`：主循环（50-80 行，无模式系统，硬编码单一系统 prompt）
- `src/embedagent/session.py`：Session / Turn / Action / Observation 的最小 dataclass 定义
- `src/embedagent/cli.py`：命令行入口（argparse，无 TUI）

**Phase 1 完成里程碑（缺一不可）**：

- [ ] 命令行可启动会话
- [ ] LLM 流式输出可正常打印
- [ ] LLM 能成功调用 `read_file` 工具
- [ ] 工具执行结果作为 Observation 回到 LLM
- [ ] 会话能正常结束
- [ ] Python 3.8 无报错运行
- [ ] GLM5 int4 和 Qwen3.5 各跑通一次

> 如果 function calling 响应格式不标准（非标准 JSON），必须在 Phase 1 的 LLM Adapter 层补充解析兼容，**不能跳过验证直接进入 Phase 2**。
>
> 若目标环境暂时不具备 `GLM5 int4` / `Qwen3.5` 联调条件，可使用任一可访问的 OpenAI-compatible 模型服务完成真实 function calling 闭环验证，并在 `docs/development-tracker.md` 与 `docs/llm-adapter.md` 中明确记录未覆盖模型与已确认兼容点。

建议文档同步：

- 若领域对象定义调整，更新 `docs/overall-solution-architecture.md`
- 建立 `docs/llm-adapter.md` 记录 function calling 兼容处理细节

### Phase 2：工具集 v1

目标：

- 建立文件、Shell 命令、Git 基础工具，支持自然语言驱动代码查看与编辑

实现重点：

- `run_command`（带超时，Win7 使用 `taskkill /F /T /PID` 强制终止）
- `git_status` / `git_diff` / `git_log`

**Phase 2 完成里程碑**：

- [ ] 能用自然语言指令让 Agent 查看代码文件
- [ ] 能让 Agent 编辑代码并保存
- [ ] 能让 Agent 执行 shell 命令并返回结构化结果
- [ ] 能让 Agent 查看 Git 状态和差异

建议产物：

- `docs/tool-contracts.md`（记录工具接口契约和 Observation 结构）

### Phase 3：模式系统 v1

目标：

- 把模式系统做成 Core 一等能力
- 先用 Python dict 实现，不用 TOML 配置文件

实现重点（v2 已落地）：

- `_BUILTIN_MODES`（Python dict，含 `system_prompt`、`allowed_tools`、`writable_globs`）
- `initialize_modes(workspace)` 配置加载（`modes.json` 两级覆盖）
- 工具过滤机制（按当前模式过滤可调用工具）
- `ask_user(...)` 用户交互工具（所有模式均可用）
- `manage_todos` 任务跟踪工具（所有模式均可用）
- 用户显式切换：`/mode <name>` 命令；`ask_user` 选项也可触发切换

模式切换规则：

1. 用户消息以 `/mode <name>` 开头 → 立即切换（未知模式回落到 `explore`）
2. 用户在 `ask_user` 弹出选项中选择含 `option_N_mode` 的项 → 自动追加新模式 prompt，更新 `current_mode`

> **`switch_mode` LLM 工具已移除**：LLM 不能主动切换模式，只能通过 `ask_user` 建议，由用户确认。

**Phase 3 v2 完成状态**：

- [x] 模式切换生效，工具集随模式变化
- [x] 违规工具调用（当前模式不允许的工具）被拦截并提示
- [x] `ask_user` 与权限审批分开显示，不再共用等待状态
- [x] 5 个模式（`explore`/`spec`/`code`/`debug`/`verify`）均可进入
- [x] 模式定义可通过 `modes.json` 覆盖，无需改代码

建议产物：

- `docs/mode-schema.md`（记录 Mode dict 结构与字段含义）
- `docs/harness-state-machine.md`（记录模式切换规则和触发路径）

### Phase 4：Clang 工具链

目标：

- 建立编译、测试、静态检查工具，支持完整 C 开发质量闭环
- 集成完全静态链接的 Clang 二进制（已验证可在 Win7 运行）

实现重点：

- `compile_project`
- `run_tests`
- `run_clang_tidy`
- `run_clang_analyzer`
- `collect_coverage`（llvm-profdata + llvm-cov）
- `report_quality`（汇总编译/测试/覆盖率结果）

**Phase 4 完成里程碑**：

- [ ] 能完成"编写代码 → 编译 → 运行测试"完整循环
- [ ] 编译错误以结构化 Observation 返回（含 file/line/message 诊断列表）
- [ ] `verify` 模式可输出质量门结论

建议产物：

- `docs/clang-integration-plan.md`

### Phase 5：质量保障层

目标：

- 控制上下文膨胀，支持长任务稳定运行
- 建立权限系统和 Doom Loop 防护

实现重点：

- 上下文压缩策略（Observation 截断 → 裁剪低价值历史 → LLM 摘要）
- PermissionRequest 机制（写入确认、命令执行确认）
- Doom Loop Guard（连续错误计数、重复工具调用检测、迭代上限）
- Session Summary 持久化与恢复入口
- Project Memory / Archive Memory 演进
- 模式系统 TOML 可选加载（叠加在 Phase 3 dict 结构上，不重写）

**Phase 5 完成里程碑**：

- [ ] 20+ turn 的长任务可稳定运行（不因上下文超限崩溃）
- [ ] 高风险操作（文件写入、命令执行）触发 PermissionRequest
- [ ] 连续 3 次相同工具调用失败后触发防护

建议产物：

- `docs/context-management-design.md`
- `docs/permission-model.md`

### Phase 6：交互层

目标：

- 先做 CLI，再做模块化终端前端

实现重点：

- In-process adapter（同进程调用）
- `SessionTimelineStore` 与 workspace / artifact / todo 浏览接口
- `src/embedagent/frontend/tui/` 模块化终端前端包（state / reducer / controller / layout / services / views）
- prompt_toolkit + Rich TUI
- Phase 6 回归脚本与手工验证清单
- stdio JSON-RPC adapter（被宿主程序拉起，放在终端前端稳定后）

建议产物：

- `docs/frontend-protocol.md`
- `docs/tui-information-architecture.md`
- `scripts/validate-phase6.py`
- `docs/phase6-validation.md`
### Phase 7：打包与离线交付

目标：

- 形成可在 Windows 7 离线导入的完整交付物
- **交付物必须完全自包含，目标机只需 Windows 7，无需任何预装软件**

实现重点：

- 运行时目录布局
- 全量工具 bundling（见下表，缺一不可）：
  - Python 3.8 embeddable distribution
  - 所有 Python 第三方包（vendoring）
  - MinGit portable
  - ripgrep
  - Universal Ctags
  - clang / clang-tidy / clang-analyzer / llvm-profdata / llvm-cov（全部静态链接）
- 前置自检脚本（验证 bundle 完整性，不依赖目标机环境）
- one-folder portable bundle（解压即用）

验收标准：

- 在全新 Windows 7 虚拟机（无预装开发工具）上解压后可直接运行
- 所有功能路径均可正常工作，无"找不到工具"类报错

建议产物：

- `docs/offline-packaging.md`（包含 bundle 清单与构建流程）
- `docs/win7-preflight-checklist.md`（目标机部署检查清单）

当前状态补充：

- `docs/offline-packaging.md` 已建立
- `docs/win7-preflight-checklist.md` 已建立
- `docs/adrs/0001-offline-portable-bundle-baseline.md` 已建立
- `scripts/prepare-offline.ps1` 已建立，可生成 staging bundle 骨架与 manifest/checksum 草案
- `scripts/build-offline-bundle.ps1` 已建立，可把 staging bundle 复制到 `offline-dist` 并生成 zip
- `scripts/validate-offline-bundle.ps1` 已建立，可校验 skeleton bundle，并支持 `-RequireComplete` 严格门禁
- `scripts/offline-assets.json` 已建立，并完成 Python embeddable / MinGit / ripgrep / Universal Ctags 真实资产接入
- `scripts/package.ps1` / `scripts/package-lib.ps1` / `scripts/package.config.json` 已建立，并已通过 mocked orchestration 测试打通控制面

---

## 5. 文档维护策略

### 5.1 文档分工

| 文档 | 角色 | 更新时机 |
|------|------|----------|
| `README.md` | 对外总览、项目范围、当前状态 | 范围、定位、阶段状态发生变化时 |
| `AGENTS.md` | 项目宪章、开发约束、模式与版本纪律 | 工作规则、版本策略、执行纪律变化时 |
| `docs/overall-solution-architecture.md` | 稳定架构设计 | 分层、模式体系、核心决策变化时 |
| `docs/implementation-roadmap.md` | 实施路径、阶段计划、文档治理 | 里程碑、实施顺序、维护策略变化时 |
| `docs/development-tracker.md` | 当前执行状态、阻塞、风险、下一步 | 每次里程碑完成、验证结论改变、优先级调整时 |
| `docs/design-change-log.md` | 关键设计变更与关联影响范围 | 每次关键实现或文档口径变化时 |
| `docs/adrs/*.md` | 单项关键决策记录 | 做出重要不可逆决策时 |
| `analysis/*.md` | 外部参考研究 | 新增竞品或新一轮研究时 |

### 5.2 是否需要建立 `AGENTS.md`

结论：**需要，现在就建立。**

原因：

- 该项目本身就是 Agent Core 设计项目，后续大量工作会由 agent 协助推进
- `AGENTS.md` 适合作为项目级机器可读宪章
- 它比 README 更适合承载“实现纪律、版本边界、文档维护规则”
- 它能降低未来每次会话重复解释约束的成本

### 5.3 是否需要建立 ADR 机制

结论：**建议建立，但按需写，不要泛滥。**

建议只有以下类型的决策写 ADR：

- Python / 运行时主线变更
- 前端技术路线变更
- LLM 接口协议变更
- 工具链或打包路线变更
- 模式系统和 Harness 机制的重大变更

### 5.4 是否需要单独的进度与变更跟踪文档

结论：**需要。**

建议固定使用两份文档：

- `docs/development-tracker.md`
  - 跟踪当前阶段、下一步任务、风险、阻塞和里程碑状态
- `docs/design-change-log.md`
  - 跟踪关键设计变更、影响范围、关联文档和后续动作

这样可以把“未来要做什么”和“刚刚改变了什么”分开维护。

---

## 6. 推荐近期任务

建议接下来按这个顺序推进：

1. 完成 `package.ps1 release` 在真实 bundle 路径上的验收，而不只是 mocked orchestration
2. 为 Phase 4 选定真实 C 工程样例，并固化默认 `compile / test / tidy / coverage` recipe
3. 在 Win7 与真实控制台宿主中完成 Phase 4 / Phase 6 手工验证
4. 收敛 LLVM/Clang bundle 的版本组合与调用路径
5. 评估 `.venv\Lib\site-packages` 直拷是否需要替换成更精简的运行时导出方案
6. 在 Win7 虚拟机上对当前 bundle 做一次真实验收

---

## 7. 近期文档清单

下一批优先补齐：

1. `docs/clang-integration-plan.md`（补真实工程 recipe 与 Win7 验证记录）
2. `docs/phase6-validation.md`（回填真实控制台 / Win7 / ConEmu 手工验证结果）
3. `docs/offline-packaging.md`（已建立，后续补 bundle manifest 与脚本落地记录）
4. `docs/win7-preflight-checklist.md`（已建立，后续补实机验收记录）
5. `docs/adrs/0001-offline-portable-bundle-baseline.md`（已建立）

---

## 8. 当前建议结论

当前最合适的做法是：

- 用 `uv` 管理开发环境
- 把开发和运行时都约束在 Python 3.8 线上
- 若 `uv` 无法提供合适 Python 3.8，再用 `conda` 兜底
- 立即建立 `AGENTS.md`
- 用“总体架构文档 + 实施路线文档 + 进度跟踪 + 设计变更记录 + 按需 ADR”的组合维护知识

这样后续实现时，代码、架构、开发环境和文档会更容易保持一致。



