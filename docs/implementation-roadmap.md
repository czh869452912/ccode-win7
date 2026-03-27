# EmbedAgent 实施路线与文档维护方案

> 更新日期：2026-03-27
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
- 工具链围绕 Clang 生态统一组织
- 最终运行时必须可在 Windows 7 离线环境中一体化交付

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

### Phase 1：Core 骨架

目标：

- 定义领域模型与事件模型
- 建立最小会话状态机
- 建立命令/事件协议骨架

实现重点：

- `Session`
- `Turn`
- `Action`
- `Observation`
- `Task`
- `PermissionRequest`
- `Artifact`

建议文档同步：

- 若对象模型调整，更新 `docs/overall-solution-architecture.md`
- 若目录布局改变，更新 `README.md`

### Phase 2：Mode Registry 与 Agent Harness

目标：

- 把模式系统做成 Core 一等能力
- 让 `ask / orchestra / spec / code / test / verify / debug / compact` 可配置

实现重点：

- Mode schema
- Mode loader
- Mode switch policy
- Harness state machine
- Artifact handoff model

建议产物：

- `docs/mode-schema.md`
- `docs/harness-state-machine.md`
- 第一批 ADR

### Phase 3：LLM Adapter

目标：

- 先打通内网大模型服务
- 支持 OpenAI-compatible HTTP 接口

实现重点：

- 请求/响应归一化
- 流式输出
- 工具调用结构化解析
- 错误归一化与重试

建议产物：

- `docs/llm-adapter.md`
- `docs/model-profiles.md`

### Phase 4：Runtime 与工具链

目标：

- 建立文件、命令、Git、Clang、测试、覆盖率工具

实现重点：

- `read_file` / `edit_file`
- `run_command`
- `git_status` / `git_diff`
- `compile_project`
- `run_tests`
- `run_clang_tidy`
- `run_clang_analyzer`
- `collect_coverage`
- `check_quality_gate`

建议产物：

- `docs/tool-contracts.md`
- `docs/clang-integration-plan.md`

### Phase 5：上下文、记忆、权限

目标：

- 控制上下文膨胀
- 建立可审计权限系统

实现重点：

- History builder
- Observation masking
- Summary compaction
- Permission rules
- Session snapshots

建议产物：

- `docs/context-management-design.md`
- `docs/permission-model.md`

### Phase 6：交互层

目标：

- 先做 CLI，再做 TUI

实现重点：

- In-process adapter
- stdio JSON-RPC adapter
- prompt_toolkit + Rich TUI

建议产物：

- `docs/frontend-protocol.md`
- `docs/tui-information-architecture.md`

### Phase 7：打包与离线交付

目标：

- 形成可在 Windows 7 离线导入的完整交付物

实现重点：

- 运行时目录布局
- 外部工具 bundling
- 前置检查
- one-folder portable bundle

建议产物：

- `docs/offline-packaging.md`
- `docs/win7-preflight-checklist.md`

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

1. 建立 `Mode Registry` 配置 schema
2. 设计 `Harness` 状态机与模式切换规则
3. 设计 Core 领域模型与事件模型
4. 建立最小 `pyproject.toml` 与开发命令
5. 编写 `OpenAI-compatible adapter`
6. 编写文件工具与命令工具
7. 编写 clang / test / coverage 工具契约

---

## 7. 近期文档清单

建议下一批优先补齐这些文档：

1. `docs/mode-schema.md`
2. `docs/harness-state-machine.md`
3. `docs/clang-integration-plan.md`
4. `docs/tool-contracts.md`
5. `docs/permission-model.md`
6. `docs/offline-packaging.md`

---

## 8. 当前建议结论

当前最合适的做法是：

- 用 `uv` 管理开发环境
- 把开发和运行时都约束在 Python 3.8 线上
- 若 `uv` 无法提供合适 Python 3.8，再用 `conda` 兜底
- 立即建立 `AGENTS.md`
- 用“总体架构文档 + 实施路线文档 + 进度跟踪 + 设计变更记录 + 按需 ADR”的组合维护知识

这样后续实现时，代码、架构、开发环境和文档会更容易保持一致。
