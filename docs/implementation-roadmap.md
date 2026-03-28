# EmbedAgent 实施路线与文档维护方案

> 更新日期：2026-03-27（DC-004/DC-005 调整后修订）
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
- 工作流采用 `orchestra -> ask(按需) -> spec -> test -> code -> verify -> debug`
- 工具链围绕 Clang 生态统一组织（已验证完全静态链接的最新版 Clang 可在 Win7 运行）
- 最终运行时必须可在 Windows 7 离线环境中一体化交付
- **工具集设计是一等公民**：每个模式工具上限 5 个，描述格式统一，参见 `docs/tool-design-spec.md`
- **Harness 分阶段叠加**：Phase 1 无 Harness，Phase 3 引入最小 dict 实现，Phase 5 可选 TOML 加载
- **每个 Phase 必须有端到端可验证的里程碑**，不做无法验证的纯抽象层构建

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
- `src/embedagent/tools.py`：第一批工具——`read_file`、`list_files`、`search_text`、`edit_file`（按 `docs/tool-design-spec.md` 规范编写）
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

实现重点：

- `MODE_REGISTRY`（Python dict，包含 `system_prompt`、`allowed_tools`、`writable_globs`）
- 工具过滤机制（按当前模式过滤可调用工具）
- `switch_mode(target: str)` 工具（所有模式均可调用）
- 用户显式切换：`/mode <name>` 命令

模式切换规则：

1. 用户消息以 `/mode <name>` 开头 → 立即切换
2. LLM 调用 `switch_mode` 工具 → 更新当前模式，用新模式 prompt 重建上下文后继续（不推进循环）

> `orchestra` 模式在本阶段暂不实现，用简单任务拆解 prompt 替代，后续再完整实现。

**Phase 3 完成里程碑**：

- [ ] 模式切换生效，工具集随模式变化
- [ ] 违规工具调用（当前模式不允许的工具）被拦截并提示
- [ ] `ask` / `spec` / `code` / `test` / `verify` / `debug` 模式均可进入

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

- 先做 CLI，再做 TUI

实现重点：

- In-process adapter（同进程调用）
- stdio JSON-RPC adapter（被宿主程序拉起）
- prompt_toolkit + Rich TUI

建议产物：

- `docs/frontend-protocol.md`
- `docs/tui-information-architecture.md`

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

---

## 5. 文档维护策略

### 5.1 文档分工

| 文档 | 角色 | 更新时机 |
|------|------|----------|
| `README.md` | 对外总览、项目范围、当前状态 | 范围、定位、阶段状态发生变化时 |
| `AGENTS.md` | 项目宪章、开发约束、模式与版本纪律 | 工作规则、版本策略、执行纪律变化时 |
| `docs/overall-solution-architecture.md` | 稳定架构设计 | 分层、模式体系、核心决策变化时 |
| `docs/implementation-roadmap.md` | 实施路径、阶段计划、文档治理 | 里程碑、实施顺序、维护策略变化时 |
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

1. ~~建立工具设计规范~~ `docs/tool-design-spec.md`（**已完成**）
2. 建立最小 `pyproject.toml` 与 `src/` 目录骨架
3. 编写 `OpenAI-compatible LLM Adapter`（同步 + 流式）
4. 编写第一批工具（`read_file`、`list_files`、`search_text`、`edit_file`）
5. 编写最小主循环（50-80 行）
6. 在 GLM5 int4 / Qwen3.5 上完成 Phase 1 里程碑验证
7. 根据验证结果补充 function calling 兼容处理

---

## 7. 近期文档清单

下一批优先补齐：

1. `docs/llm-adapter.md`（function calling 兼容细节，Phase 1 完成后）
2. `docs/tool-contracts.md`（工具接口契约，Phase 2 完成后）
3. `docs/mode-schema.md`（Phase 3）
4. `docs/harness-state-machine.md`（Phase 3）
5. `docs/clang-integration-plan.md`（Phase 4）
6. `docs/permission-model.md`（Phase 5）
7. `docs/offline-packaging.md`（Phase 7）

---

## 8. 当前建议结论

当前最合适的做法是：

- 用 `uv` 管理开发环境
- 把开发和运行时都约束在 Python 3.8 线上
- 若 `uv` 无法提供合适 Python 3.8，再用 `conda` 兜底
- 立即建立 `AGENTS.md`
- 用“总体架构文档 + 实施路线文档 + 进度跟踪 + 设计变更记录 + 按需 ADR”的组合维护知识

这样后续实现时，代码、架构、开发环境和文档会更容易保持一致。
