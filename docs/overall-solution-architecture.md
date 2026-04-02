# EmbedAgent 总体方案设计（V1 草案）

> 更新日期：2026-03-27
> 适用阶段：总体方案设计 / 架构收敛
> 设计基线：Windows 7 可用、离线可部署、Agent Core 与前端解耦、轻量但可扩展

---

## 1. 文档目标

基于当前对 OpenCode、OpenHands、Roo-Code 以及上下文工程的分析，本文件将项目从“研究结论”推进到“可落地的总体方案”。

本方案重点回答五个问题：

1. 在 **Windows 7** 上，系统如何可靠运行？
2. 在 **无网络、无额外环境依赖** 的前提下，系统如何一体化打包并导入离线内网？
3. 如何把 **Agent Core** 做成真正的核心，并与前端完全解耦？
4. 如何在保持 **轻量化** 的同时，预留未来更开放场景和多智能体协同的演进空间？
5. 哪些部分应该 **充分复用开源实现**，哪些部分必须自己掌控？

---

## 2. 设计约束与目标

### 2.1 刚性约束

- 目标操作系统必须覆盖 Windows 7。
- 目标环境可能完全离线，仅能访问内网大模型服务。
- 交付物必须可整体打包，不能依赖目标机预装 Python、Node、Docker、VS Code 等环境。
- 系统首期聚焦 **C 语言偏应用软件** 场景，即业务逻辑、协议处理、算法实现、数据处理与配套测试，而非通用多语言开发平台。
- 系统要能在嵌入式 C 开发场景下稳定工作，优先支持本地代码读写、构建、诊断、Git 操作、文档读取。
- Agent 能力必须独立于前端存在，前端只负责交互与呈现。

### 2.2 核心目标

- **核心优先**：先做强 Agent Core，再接不同前端。
- **离线优先**：所有关键能力可在无外网下运行。
- **轻量优先**：优先使用标准库、轻依赖、预编译可执行文件。
- **可审计**：关键状态、任务、权限、会话、产物要可追踪、可回放、可恢复。
- **可演进**：未来可扩展到多模型、多前端、多智能体、多工具源。

### 2.3 非目标

- 首期不做浏览器自动化、联网搜索、云端执行、Docker 沙箱。
- 首期不做重量级 RAG 平台、向量数据库集群、插件市场。
- 首期不追求“通用 Agent 平台”，而是针对离线嵌入式开发场景做深做稳。

---

## 3. 总体设计原则

### 3.1 Agent Core 是产品本体

前端不是系统本体，真正的产品是一个可嵌入、可调用、可扩展的 Agent Core。  
TUI、CLI、未来 GUI/Web 只是不同的交互壳。

### 3.2 架构上解耦，部署上可一体

逻辑上：

- Core 不依赖任何具体 UI 框架
- 前端通过稳定的命令/事件协议与 Core 通信
- 工具执行、LLM 访问、状态存储都在 Core 边界内统一管理

部署上：

- 可以单进程运行（最轻量）
- 也可以前后端分进程运行（更强隔离与扩展性）
- 二者共享同一套领域模型与协议

### 3.3 单 Agent 先做强，多 Agent 后加速

第一阶段不追求复杂编排，而是先把：

- 单 Agent loop
- 上下文管理
- 权限控制
- 工具调用
- 错误恢复

做扎实。

多智能体能力通过“任务队列 + 上下文隔离 + 摘要回传”的方式预留接口，而不是一开始引入复杂编排框架。

### 3.4 文件系统优先，SQLite 作为后续增强基础设施

在离线 Windows 7 环境下，最稳妥的基础设施是：

- 文件系统：规则、记忆、快照、日志、索引产物，也是当前 Phase 5 MVP 的主要落地介质
- SQLite：后续用于会话、事件、权限、任务和结构化状态索引

避免引入额外服务进程作为系统运行前提。

### 3.5 模式聚焦优先于全能 Agent

借鉴 Roo-Code 的模式设计，但进一步收敛到我们的场景：

- 模式不是 UI 标签，而是 Core 中的执行契约
- 每个模式只负责一类工作，尽量减少跨阶段决策
- 每个模式拥有独立的工具集、文件写入范围、质量门和退出条件
- 通过模式切换把复杂任务拆解成多个低复杂度子问题

这本质上是 **Agent Harness** 思路：

- 不把“规划、写代码、写测试、验证覆盖率、诊断问题”混成一个巨提示
- 而是让系统用受约束的模式，把模型放进合适的轨道中工作

对于能力有偏差、工具调用稳定性较弱或上下文理解能力一般的模型，这种设计尤其重要。

### 3.6 工作流表层化，模式内核化

在当前实现阶段，模式继续保留为 Core 执行契约，但不再作为产品主导航。

- 用户主入口改为 slash command / workflow，例如 `/plan`、`/review`、`/permissions`
- 模式继续负责工具过滤、写入边界、权限前置约束和会话语义
- 工作流默认不新增核心 mode，而是复用 `spec` / `verify` 等模式能力
- 只有 `/mode <name>` 或用户确认的 mode proposal 才会改变 `current_mode`

---

## 4. 总体架构

```text
┌──────────────────────────────────────────────────────────────┐
│                        Frontend Layer                        │
│  CLI / TUI / Future GUI / Future Web Console                │
└──────────────────────────────┬───────────────────────────────┘
                               │ Command/Event Protocol
┌──────────────────────────────▼───────────────────────────────┐
│                        Agent Core API                        │
│  Session API | Task API | Event Stream | Permission API      │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                     Orchestration Layer                      │
│  AgentController | Planner Loop | Context Manager            │
│  Action Parser    | Retry Guard  | Doom Loop Guard           │
└───────────────┬───────────────┬───────────────┬──────────────┘
                │               │               │
┌───────────────▼──────┐ ┌──────▼──────────┐ ┌──▼──────────────┐
│ Tool Runtime         │ │ LLM Adapter      │ │ State & Memory  │
│ File / Shell / Git   │ │ OpenAI-compatible│ │ SQLite + Files  │
│ Clang / Search / Doc │ │ Stream / Retry   │ │ Rules / Notes   │
└───────────────┬──────┘ └──────┬──────────┘ └──┬──────────────┘
                │               │               │
┌───────────────▼────────────────▼───────────────▼─────────────┐
│                  Bundled Offline Dependencies                 │
│  Python 3.8 Embedded | MinGit | ripgrep | ctags | LLVM/Clang │
└──────────────────────────────────────────────────────────────┘
```

### 4.1 分层说明

#### Frontend Layer

- 只负责输入、展示、交互状态。
- 不包含 Agent 决策逻辑。
- 可以存在多个前端实现，共用同一 Core。

#### Agent Core API

- 对外暴露统一的会话与任务接口。
- 以命令和事件为边界，而不是直接暴露内部对象。
- 允许前端以嵌入方式或独立进程方式接入。

#### Orchestration Layer

- 负责 Agent 主循环。
- 将“LLM 生成动作”与“运行时执行动作”严格分离。
- 集中处理上下文构建、重试、压缩、迭代限制、异常保护。
- 当前 clean-room 升级方向是把旧的 `AgentLoop` 收口为兼容入口，并把真实执行迁移到 `QueryEngine`。
- `QueryEngine` 以显式状态机驱动 `submit_turn -> transition`，并把 `PendingInteraction`、`CompactBoundary`、`ToolCallRecord` 与 `AgentStepState` 作为一等领域对象。
- `ask_user` 与权限审批不再被建模成“失败 Observation + 阻塞线程”，而是可挂起、可恢复的交互状态。

#### Tool Runtime

- 统一封装文件、命令、Git、编译、静态分析、符号检索等工具。
- 所有工具返回结构化 Observation，而不是让 Agent 解析原始终端垃圾输出。
- Tool Runtime 负责统一解析托管运行环境，优先使用 bundle / workspace 内置的 `git`、`rg`、`ctags`、`llvm` 与 Python 运行时，并把 `runtime_source`、`bundled_tools_ready`、`fallback_warnings`、`resolved_tool_roots` 回写到 Observation / Session Snapshot。
- Tool Runtime 同时负责暴露工作区 recipe：自动检测 `CMakeLists.txt` / `Makefile`，加载项目自定义 recipe，并把历史成功命令整理成可复用 recipe 列表。
- 产品表层允许用户通过 `/recipes` 浏览 recipe，并通过 `/run <recipe_id>` 直接执行；GUI Run 面板复用同一入口，而不是单独维护第二套执行逻辑。

#### LLM Adapter

- 面向内网模型服务，首要兼容 OpenAI 风格 HTTP API。
- 内部保持 provider adapter 抽象，避免绑死单一厂商 SDK。

#### State & Memory

- 当前已落地文件型 JSON / Markdown 记忆与摘要。
- SQLite 仍保留为后续结构化状态、索引与恢复增强的主线。
- 支持审计、差异比对、恢复和人工干预。

---

## 5. Agent Core 设计

### 5.1 核心领域对象

- `Session`：一次会话的总容器
- `Turn`：一轮用户输入到系统输出的处理周期
- `Action`：Agent 发起的动作
- `Observation`：工具执行或系统返回的结果
- `Task`：结构化任务与 TODO
- `PermissionRequest`：需要用户确认的动作
- `Artifact`：会话产物，如 diff、日志、构建结果、摘要

### 5.2 主循环

建议采用 `Controller -> Agent -> Runtime -> Observation -> Controller` 的同步循环：

1. 从 `Session State` 构建上下文
2. 为当前用户 turn 创建一个新的 agent step
3. 调用 LLM，得到结构化 Action
4. 校验 Action 是否符合权限与状态机规则
5. 调用 Runtime 执行工具
6. 产出 Observation 并写入事件流
7. 结束当前 agent step，并决定是否继续下一步
8. 更新任务状态、上下文状态、压缩状态
9. 继续下一轮，直到 `finish`

这里的 `Turn` 与 `Agent Step` 区分如下：

- `Turn`：一次用户输入触发的完整会话处理周期
- `Agent Step`：该 turn 内的一次模型迭代，负责承载 `thinking -> tools -> partial answer`

这样 GUI / TUI / 回放层都不需要再通过“最后一个 user bubble 之后的所有事件”去猜测分组。

### 5.3 必须具备的安全阀

- 最大迭代数
- 连续错误计数
- 重复工具调用检测
- 重复编辑检测
- 上下文超限检测
- 长命令超时与强制终止
- 用户中断与会话暂停

这些设计分别来自：

- OpenHands 的状态机与 Action/Observation 分离
- OpenCode 的配置驱动 Agent 与权限规则
- Roo-Code 的上下文超限保护、重复调用检测和重试防御

### 5.4 配置驱动的 Agent Modes

Agent Core 应当内建“模式注册表（Mode Registry）”，模式由配置定义，而不是硬编码在 UI 或 prompt 里。

一个模式至少应包含以下字段：

- `slug`：模式唯一标识
- `role`：模式角色描述
- `when_to_use`：何时进入该模式
- `instructions`：模式专属行为约束
- `allowed_tools`：允许使用的工具集合
- `writable_globs`：允许写入的文件范围
- `default_model_profile`：推荐模型与采样参数
- `entry_artifacts`：进入模式前必须具备的输入工件
- `exit_checks`：退出模式前必须满足的条件
- `handoff_to`：推荐切换到的下游模式

可采用 TOML 配置，例如：

```toml
[mode.spec]
role = "负责把需求转成可实现、可验证的规格与测试目标"
when_to_use = "收到新需求、需求变更、实现前澄清范围时"
allowed_tools = ["read_file", "read_range", "search_text", "list_files", "update_todo"]
writable_globs = ["**/*.md", "**/*.rst", "**/*.txt"]
entry_artifacts = ["user_request"]
exit_checks = ["spec_complete", "acceptance_criteria_defined", "test_points_defined"]
handoff_to = ["test", "code"]

[mode.code]
role = "负责最小化实现生产代码以满足规格和测试"
when_to_use = "已有明确规格或失败测试，需要修改 src/include 下的生产代码时"
allowed_tools = ["read_file", "read_range", "edit_file", "search_text", "compile_project", "update_todo"]
writable_globs = ["**/*.c", "**/*.h", "**/*.hpp", "**/*.toml", "CMakeLists.txt"]
entry_artifacts = ["spec_ref", "failing_tests_or_tasks"]
exit_checks = ["build_pass_or_expected_failures_known"]
handoff_to = ["test", "verify", "debug"]

[mode.ask]
role = "负责在信息不足、需求冲突或关键决策未定时，向用户提出最小必要问题"
when_to_use = "存在阻塞实现的歧义、需要用户确认方向、权限或验收标准时"
allowed_tools = ["read_file", "read_range", "search_text", "list_files", "update_todo", "ask_user"]
writable_globs = []
entry_artifacts = ["ambiguity_or_decision_point"]
exit_checks = ["question_answered_or_decision_recorded"]
handoff_to = ["orchestra", "spec", "code", "test"]
``` 

核心原则是：

- 模式 = 权限集合 + Prompt 契约 + 工件契约 + 质量门
- 切换模式 = 切换工作边界，而不是切换一套新的程序架构

### 5.5 内置模式建议

首期建议内建以下模式，并允许项目级配置覆盖：

| 模式 | 主要职责 | 典型可写范围 | 核心工具 | 退出条件 |
|------|----------|--------------|----------|----------|
| `ask` | 在信息不足时向用户提最小必要问题，收敛歧义、确认约束与分支决策 | `docs/tasks/**` | 读取、搜索、TODO、ask_user | 关键问题已回答，阻塞解除 |
| `orchestra` | 作为协调模式拆解任务、分配子目标、选择/切换下游模式，后续可升级为多智能体调度入口 | `docs/tasks/**`, `artifacts/plans/**` | TODO、模式切换、工件汇总、后续可接 worker 调度 | 路线清晰，已把任务交给合适模式或 worker |
| `spec` | 将需求转成规格、验收标准、测试点、任务拆解 | `docs/specs/**`, `docs/tasks/**` | 读取、搜索、TODO | 规格清晰，验收标准可执行 |
| `code` | 编写或重构生产代码，聚焦 `.c/.h` 业务逻辑与算法实现 | `src/**`, `include/**` | 读写、搜索、编译 | 代码可编译，变更边界清晰 |
| `test` | 编写/维护单元测试、夹具、测试入口，推动 TDD 闭环 | `tests/**`, `testdata/**` | 读写、运行测试、收集失败 | 测试能重现需求或缺陷 |
| `verify` | 运行 clang 质量检查、覆盖率、报告汇总与质量门判定 | `artifacts/reports/**` | 编译、测试、clang-tidy、analyzer、coverage | 质量门结果明确 |
| `debug` | 复现问题、定位根因、输出最小修复路径 | `src/**`, `include/**`, `tests/**` | 搜索、运行、诊断、最小改动 | 根因明确且有验证证据 |
| `compact` | 内部上下文整理、摘要压缩 | 内部模式，不对用户暴露 | 摘要/压缩 | 上下文恢复到安全预算 |

这里最关键的不是“模式数量多”，而是“每个模式工作面足够窄”：

- `ask` 只负责消除不确定性，不顺手实现功能
- `orchestra` 只负责编排与切换，不直接承担大段生产代码编写
- `spec` 不承担实现
- `test` 不承担大规模架构设计
- `verify` 不承担开放式编码
- `debug` 以复现和根因为中心，而不是重新实现整块功能

其中：

- `ask` 是人机协同入口，负责把“缺信息时硬猜”改成“最小必要确认”
- `orchestra` 是控制面入口，负责把复杂任务转成受控模式流

二者共同作用后，弱模型也不必同时承担“理解问题、决定流程、写代码、验证质量”这四类负担。

### 5.6 Agent Harness 设计

Agent Harness 是 Agent Core 上方的一层”约束与编排器”，负责把复杂任务压缩成模式化工作流。

**Harness 分阶段演进（不一步到位）**：

| 实施阶段 | Harness 实现形式 | 说明 |
|----------|-----------------|------|
| Phase 1 | 无 Harness | Loop 硬编码单一 system prompt，无模式概念 |
| Phase 3 | Python dict + 工具过滤（~100行） | 与最终版数据结构兼容，可直接叠加字段 |
| Phase 5 | 可选 TOML 加载 | 保持 dict 结构不变，只替换加载来源 |

每阶段向已有 dict 添加字段，核心 Loop 代码改动量极小（每次约 10-20 行）。

Harness 的职责应包括：

- 选择当前模式，或建议切换模式
- 按模式过滤工具、文件写入范围和可见指令
- 为当前模式注入专属检查表与输出格式
- 管理模式间交接工件，如 `spec.md`、失败测试、覆盖率报告、诊断摘要
- 在信息不足时切入 `ask` 模式，等待人类补充关键信息后再恢复工作流
- 在任务复杂度过高时切入 `orchestra` 模式，拆解任务并决定后续模式路由
- 执行质量门，例如“测试必须先失败再实现”“覆盖率未达标时进入 verify/debug”
- 对能力较弱模型缩小决策面，减少“该做什么”的自由度

可以把它理解为：

```text
User Task
   ↓
Agent Harness
   ├─ ask mode       → 澄清歧义 / 请求决策 / 记录答案
   ├─ orchestra mode → 拆解任务 / 路由模式 / 汇总工件
   ├─ spec mode      → 产出规格/验收标准/测试点
   ├─ test mode      → 产出失败测试或测试基线
   ├─ code mode      → 最小实现
   ├─ verify mode    → 质量门判定
   └─ debug mode     → 失败回路闭环
```

这套机制不是为了让系统“更复杂”，恰恰是为了把复杂度从模型脑内搬到系统设计里。

**模式切换触发机制（简化版，Phase 3 实现）**：

1. 用户显式：消息以 `/mode <name>` 开头，立即切换
2. LLM 工具调用：仅 `orchestra` 模式具备 `switch_mode(target, reason)` 工具；其他模式需要通过 `ask_user` 或文本建议等待用户决定

`orchestra` 模式推迟到 Phase 3 之后实现，Phase 1/2 阶段用简单任务拆解 prompt 替代。

### 5.7 `ask` 与 `orchestra` 的分工

这两个模式容易看起来相近，但职责不同：

- `ask` 面向人
  - 目标是拿到缺失信息或用户决策
  - 输出是一组精炼问题、备选项或确认结果
  - 一旦答案到位，就退出并交回 `orchestra` 或具体执行模式

- `orchestra` 面向系统
  - 目标是组织工作流，而不是直接求答案
  - 输出是任务拆解、模式切换、工件交接与阶段状态
  - 在单 Agent 阶段，`orchestra` 协调模式切换
  - 在多智能体阶段，`orchestra` 可升级为 worker 调度入口

换句话说：

- `ask` 解决“还缺什么信息”
- `orchestra` 解决“接下来由谁、按什么顺序做”

### 5.8 默认开发方法学

Agent Core 应将以下方法学固化为默认工作流模板，而不是作为可选提示：

1. **Spec-Driven Development**
   - 先明确规格、边界条件、验收标准
   - 再进入实现和验证

2. **TDD（测试驱动开发）**
   - 先由 `test` 模式产出失败测试
   - 再由 `code` 模式做最小实现
   - 再由 `verify` 模式确认测试通过与质量达标

3. **Coverage / MC/DC Gate**
   - 对关键模块引入覆盖率门禁
   - 对有需求的安全关键逻辑预留 MC/DC 检查位
   - 由 `verify` 模式统一给出质量门结论

在这套设计下，Core 中不再只有“一个会写代码的 Agent”，而是一个带有明确工程方法学的受控 Harness。

---

## 6. 前后端解耦方案

### 6.1 解耦目标

前端可以替换，但 Core 不重写。

这意味着：

- TUI 不应直接操作 Runtime
- TUI 不应自行拼 prompt
- TUI 不应掌握会话状态真相

真正状态真相只在 Core 内。

### 6.2 交互协议

Core 对前端只暴露两类接口：

#### Command

- `create_session`
- `submit_user_message`
- `approve_permission`
- `reject_permission`
- `pause_session`
- `resume_session`
- `cancel_session`
- `list_artifacts`
- `get_session_snapshot`

#### Event

- `session_created`
- `turn_started`
- `assistant_delta`
- `tool_started`
- `tool_finished`
- `permission_required`
- `task_list_updated`
- `context_compacted`
- `session_finished`
- `session_error`

### 6.3 传输层建议

首期保留三种实现位：

1. **In-Process Adapter**
   - 最轻量
   - 适合同进程 TUI/CLI

2. **stdio JSON-RPC Adapter**
   - 适合被其他宿主程序拉起
   - 最易嵌入桌面应用或脚本系统

3. **Local HTTP + SSE Adapter**
   - 适合未来 GUI/Web 前端
   - 只绑定 `127.0.0.1`

建议首期实现 `In-Process` 和 `stdio`，`HTTP + SSE` 作为后续扩展。

这样既满足当前轻量化，也保证后续前端演进时不需要改 Agent Core。

---

## 7. 上下文与记忆设计

### 7.1 分层策略

采用四层记忆设计：

1. **Working Memory**
   - 当前 TODO
   - 当前步骤计划
   - 当前工具结果摘要

2. **Session Memory**
   - 本次会话历史
   - 关键 Observation
   - 最近编辑和命令结果

3. **Project Memory**
   - 项目规则
   - 构建命令
   - 代码约定
   - 常见坑和经验

4. **Archive Memory**
   - 历史会话摘要
   - 关键架构决策
   - 可复用问题解决记录

### 7.2 存储介质

- 当前落地：Working / Session / Project 以文件系统 JSON + 少量内存缓存为主
- 后续演进：SQLite 用于事件、权限、任务与多会话索引；Project / Archive 继续保留 Markdown / JSON 的可审计形态

### 7.3 上下文构建策略

默认采用“轻量优先”的三层方式：

1. 当前任务相关文件片段
2. 最近若干轮动作-观测
3. 项目规则和任务摘要

超限时按以下顺序处理：

1. 先压缩 Observation
2. 再裁剪低价值历史
3. 最后再触发 LLM 摘要

在 2026-04-02 的 Query / Context 重构切片中，这一策略已经开始收敛为显式流水线：

1. `working set`
2. `workspace intelligence`
3. `tool result replacement`
4. `duplicate read/search suppression`
5. `activity folding`
6. `summary / compact boundary`
7. `prompt render`

这与调研结论一致：对于本地或内网模型，**先做观测遮蔽，再做摘要压缩**，成本和稳定性都更好。

### 7.4 代码库上下文策略

首期不做重量级向量检索，采用“三层渐进式代码上下文”：

1. **文件树 + ignore 规则**
2. **符号级索引**
3. **按需读取实现片段**

实现建议：

- 文件发现：`ripgrep`
- 符号索引：`Universal Ctags`
- 精确读取：自研 `read_range` / `search_symbol`

这是比 Tree-sitter + 向量库更稳妥的首期方案，尤其适合离线、轻量、C 项目。

当前已新增 `WorkspaceIntelligenceBroker` 作为统一情报层入口，首批 provider 包括：

- `WorkingSetProvider`
- `ProjectMemoryProvider`
- `RecipeProvider`
- `CtagsProvider`
- `DiagnosticsProvider`
- `GitStateProvider`
- `LlspProvider`（空实现，占位未来 provider 契约）

---

## 8. 工具与运行时设计

### 8.1 工具分类

#### 基础工具

- `read_file`
- `read_range`
- `write_file`
- `edit_file`
- `list_files`
- `search_text`

#### 研发工具

- `run_command`
- `git_status`
- `git_diff`
- `git_log`
- `compile_project`
- `run_tests`
- `run_sanitizers`
- `collect_coverage`
- `check_quality_gate`
- `run_clang_tidy`
- `run_clang_analyzer`

#### 嵌入式增强工具

- `search_symbol`
- `read_map_file`
- `read_doc`
- `collect_build_errors`
- `summarize_diagnostics`

### 8.2 Clang 生态优先

系统在研发工具链上应明确“依附 Clang 生态”，避免测试、静态分析、覆盖率各走各路。

建议统一围绕以下能力组织：

- 编译：`clang` / `clang-cl`
- 静态检查：`clang-tidy`
- 静态分析：`clang --analyze` 或等价能力
- 运行时检查：`AddressSanitizer` / `UBSan`（在目标环境允许时开启）
- 覆盖率：`llvm-profdata` + `llvm-cov`
- 质量门：函数/语句/分支覆盖率，以及面向关键模块的 MC/DC 预留能力

这样做有三个好处：

- 诊断格式相对统一，便于结构化解析
- 构建、测试、覆盖率可以复用同一套编译配置
- `verify` 模式可以更稳定地输出工程质量结论

### 8.3 面向 C 应用开发的默认工作流

系统首期要服务的是 C 语言偏应用软件开发，即业务逻辑、协议处理、算法与数据处理代码。

因此默认工作流应是：

1. 先由 `orchestra` 模式接收任务并判断是否需要 `ask`
2. `ask` 模式在必要时整理最小问题集，补齐关键决策
3. `spec` 模式整理需求、接口假设、边界条件、验收标准
4. `test` 模式先写单元测试或构造失败样例
5. `code` 模式以最小变更实现业务逻辑或算法
6. `verify` 模式执行编译、测试、静态检查、覆盖率与质量门
7. 若失败，进入 `debug` 模式做根因定位，再回到 `code` / `test`

这条链路要写入 Harness，而不是依赖模型临场发挥。

### 8.3a 工具集设计是一等公民

内网模型（GLM5 int4 量化版、Qwen3.5 全量版）的工具调用成功率对工具集设计极为敏感。工具集设计质量直接决定系统稳定性，必须和架构设计同等对待。

核心约束：

- 每个模式严格控制在 **5 个工具以内**（目标 3-4 个）
- 工具描述使用**中文描述 + 英文命名**，按统一模板编写
- 参数数量不超过 5 个，不使用嵌套对象参数
- 所有工具返回结构化 Observation，不返回原始终端文本

详细规范见 `docs/tool-design-spec.md`。

### 8.4 Observation 必须结构化

例如编译结果不应只返回原始终端文本，而应该拆为：

- 退出码
- 命令
- 标准输出
- 标准错误
- 错误数量
- 诊断列表（文件、行、列、级别、消息）
- 持续时间

这样 Agent 才能更稳定地做决策，前端也更容易展示。

### 8.5 Windows 7 运行时注意点

- 不依赖 Docker、WSL、Node 运行时
- 子进程执行统一使用 `subprocess`
- 超时终止统一走 `taskkill /F /T /PID`
- 路径标准化必须兼容盘符、反斜杠、大小写不敏感
- 进程环境要可控，避免污染系统 PATH
- **Clang 工具链**：使用完全静态链接的 Clang 二进制（已验证最新版可在 Win7 正常运行），直接 bundle 入交付物，无需目标机预装 LLVM

---

## 9. 权限与安全模型

### 9.1 基本判断

在 Windows 7 离线环境里，不现实也没有必要引入真正容器沙箱。  
因此安全策略应采用“软隔离 + 审批 + 可恢复”的模型。

### 9.2 三层控制

1. **静态规则**
   - allow / ask / deny
   - 按工具、路径、命令模式匹配

2. **运行期审批**
   - 高风险命令需要用户确认
   - 例如删除、覆盖、危险 Git 操作

3. **事后可恢复**
   - 会话级快照
   - patch 记录
   - Git 变更摘要

### 9.3 首期权限建议

- 文件读取：默认允许
- 工作区内写入：默认询问或按规则放行
- 非工作区写入：默认拒绝
- 命令执行：默认询问
- Git 只读命令：默认允许
- Git 写命令：默认询问

---

## 10. LLM 适配设计

### 10.1 适配目标

系统默认面向“内网大模型服务”，不绑定任何特定云厂商。

首要支持：

- OpenAI 风格 Chat Completions / Responses 类接口
- 流式输出
- 工具调用或结构化输出
- 超时、重试、错误归一化

### 10.2 适配层抽象

建议定义统一接口：

```text
ModelClient
  - generate(messages, tools, options)
  - stream(messages, tools, options)
  - count_tokens(...)
  - normalize_error(...)
```

具体实现：

- `OpenAICompatibleClient`
- `CustomHTTPClient`
- 后续可扩展 `AnthropicCompatibleClient`

### 10.3 为什么不直接引入重量级 Agent 框架

不建议首期引入 LangChain、AutoGen、CrewAI 作为核心编排层，原因：

- 依赖链重
- Python 版本漂移快
- 为 Win7 锁版本成本高
- 对我们真正需要的单 Agent 控制环帮助有限

建议做法是：

- 自研控制环和领域模型
- 在工具、UI、索引、Git、编译等外围尽量复用成熟开源组件

---

## 11. 打包与离线交付方案

### 11.0 零外部依赖刚性约束

**交付物必须完全自包含，目标机只需 Windows 7，无需任何预装软件。**

捆绑清单（缺一不可）：

| 组件 | 说明 |
|------|------|
| Python 3.8 embeddable distribution | 主运行时 |
| 所有 Python 第三方包 | vendoring 方式，不依赖 pip 联网安装 |
| MinGit portable | Git 操作工具 |
| ripgrep | 代码搜索 |
| Universal Ctags | 符号索引 |
| clang（静态链接） | 编译器 |
| clang-tidy（静态链接） | 静态检查 |
| clang-analyzer（静态链接） | 静态分析 |
| llvm-profdata（静态链接） | 覆盖率数据处理 |
| llvm-cov（静态链接） | 覆盖率报告生成 |

> **判定标准**：若某工具在运行时被调用但未包含在 bundle 中，视为交付缺陷。系统的任何功能路径不得依赖目标机上的任何预装工具。

### 11.1 交付形态

建议提供两类产物：

1. **Portable Bundle**
   - 解压即用
   - 适合已满足前置条件的内网机器

2. **Offline Installer Bundle**
   - 含运行前置检查与补丁包
   - 适合首次导入隔离环境

### 11.2 核心打包思路

以 **Python 3.8 Embedded Distribution** 为运行时底座，所有第三方依赖采用 vendoring 方式随包分发。

建议目录：

```text
EmbedAgent/
├── runtime/
│   ├── python/
│   ├── dlls/
│   └── site-packages/
├── bin/
│   ├── embedagent.exe or .bat
│   ├── rg.exe
│   ├── ctags.exe
│   ├── git.exe
│   └── clang/
├── app/
│   ├── core/
│   ├── adapters/
│   ├── tools/
│   ├── ui/
│   └── resources/
├── data/
│   ├── sessions/
│   ├── memory/
│   └── logs/
└── config/
    ├── settings.toml
    ├── permissions.toml
    └── models.toml
```

### 11.3 Win7 前置风险必须显式处理

根据 Python 3.8 Windows 官方文档：

- 嵌入式 Python 发行包适合嵌入到应用中
- 第三方包应由应用一起分发
- 在 Windows 7 上运行时需要 `KB2533623`
- 嵌入式分发不自带 Microsoft C Runtime

因此打包方案必须包含：

- 启动前置检查器
- `ucrtbase.dll` 检测
- Win7 补丁与运行库说明
- x64 / x86 双架构打包策略

### 11.4 一体化打包建议

首选 **one-folder portable bundle**，不建议首期追求 one-file 单 exe。

原因：

- 更容易排查缺失依赖
- 更适合携带 clang、git、ctags、rg 等外部工具
- 启动更稳定
- 对离线更新和问题定位更友好

若后续需要“单 exe 启动体验”，可增加一个薄启动器，但不改变底层目录式部署。

---

## 12. 多智能体扩展路径

### 12.1 首期结论

首期只交付单 Agent，但核心抽象必须为多智能体留口，尤其要让 `orchestra` 模式未来可以自然升级为协调入口：

- `Task`
- `Mailbox`
- `Worker`
- `SharedArtifact`
- `SummaryBack`

### 12.2 未来扩展方式

多智能体不共享整段上下文，而共享：

- 任务定义
- 工件引用
- 结构化摘要
- 状态机状态

每个子智能体保持独立上下文窗口，只向主控返回摘要。

建议约束：

- `orchestra` 负责创建和回收 worker
- `code/test/debug/verify` 可作为 worker 的执行模式
- `ask` 仍然作为人机澄清入口，不下放给后台 worker

### 12.3 推荐演进顺序

1. 主 Agent + `orchestra` 模式
2. 专用压缩 Agent
3. 只读探索 Agent
4. 构建/测试 Agent
5. 多 Worker 协同（由 `orchestra` 调度）

这样不会过早引入任务协调复杂度。

---

## 13. 选型分析

### 13.1 运行时语言

| 方案 | 结论 | 原因 |
|------|------|------|
| Python 3.8 Embedded | **首选** | Win7 兼容边界清晰、生态成熟、开发效率高、可整体打包 |
| Go | 暂不首选 | 单文件分发优秀，但 Win7 支持与依赖生态控制成本更高 |
| Rust | 暂不首选 | 可执行文件质量高，但首期开发速度与工具集成成本偏高 |

### 13.2 前端技术

| 方案 | 结论 | 原因 |
|------|------|------|
| `prompt_toolkit` + `Rich` | **首选** | 纯 Python、支持全屏终端交互、Windows 可用、对 Python 3.8 友好 |
| `Textual` | 暂不采用 | 官方文档要求 Python 3.9+，且更偏现代终端体验，不适合 Win7 基线 |
| `urwid` | 备选 | 轻量，但原生 Windows 体验与后续扩展性不如 `prompt_toolkit` 方案 |

### 13.3 状态与记忆

| 方案 | 结论 | 原因 |
|------|------|------|
| SQLite + Markdown | **首选** | 零服务依赖、易审计、易迁移、适合离线环境 |
| 向量数据库 | 后续可选 | 首期价值不足，维护成本高 |
| 图数据库 | 后续可选 | 仅当多跳推理需求明确时再引入 |

### 13.4 代码搜索与索引

| 方案 | 结论 | 原因 |
|------|------|------|
| `ripgrep` + `Universal Ctags` | **首选** | 成熟、轻量、Windows 可分发、对 C/C++ 友好 |
| Tree-sitter | 后续增强 | 结构更强，但首期集成复杂度更高 |
| 向量化代码检索 | 暂不采用 | 离线索引链路复杂，对 MVP 不是刚需 |

### 13.5 版本控制

| 方案 | 结论 | 原因 |
|------|------|------|
| MinGit / Portable Git | **首选** | 可随包分发，适合第三方应用嵌入 |
| 系统预装 Git | 不依赖 | 不满足“无环境依赖”目标 |

### 13.6 构建与诊断工具

| 方案 | 结论 | 原因 |
|------|------|------|
| LLVM/Clang 工具链 | **首选** | 编译、静态分析、格式化、覆盖率能力完整 |
| GCC 混搭 | 谨慎引入 | 会带来工具链和诊断格式分裂 |

### 13.7 Agent 编排框架

| 方案 | 结论 | 原因 |
|------|------|------|
| 自研轻量控制环 | **首选** | 最符合 Win7、离线、强可控要求 |
| OpenHands/OpenCode/Roo 直接集成 | 不采用整包 | 可借鉴设计，不适合整体搬入 |
| LangChain/AutoGen/CrewAI | 暂不采用 | 依赖重、版本快、可控性不足 |

---

## 14. 开源复用策略

### 14.1 直接复用“设计思想”

- OpenHands：事件驱动、Action/Observation 分离、Controller 状态机
- OpenCode：配置驱动 Agent、权限三值规则、上下文治理
- Roo-Code：双轨历史、重试/重复检测、防止上下文失控

### 14.2 直接复用“现成组件”

- Python 3.8 Embedded Distribution
- Rich
- prompt_toolkit
- SQLite
- ripgrep
- Universal Ctags
- LLVM/Clang
- MinGit 或 Portable Git

### 14.3 必须掌握在自己手里的部分

- Agent Controller 主循环
- 上下文构建与压缩策略
- 权限模型
- Tool Runtime 抽象
- 会话状态与事件模型
- 前后端协议

这几部分决定系统气质和长期可维护性，不能外包给重量级框架。

---

## 15. 建议的实施阶段

### P0：架构基线

- 固化领域模型
- 固化模式注册表与 Agent Harness 契约
- 固化命令/事件协议
- 固化目录布局与配置文件格式

### P1：最小可运行内核

- Session / Event / Controller
- Mode Registry / Harness / Mode Switch
- OpenAI-compatible LLM adapter
- read / edit / command / git / todo 工具
- 基础 CLI

### P2：可用版

- prompt_toolkit + Rich TUI
- clang / test / diagnostics / coverage 工具
- 上下文压缩与任务跟踪
- SQLite 持久化

### P3：离线交付版

- 打包脚本
- Win7 前置检查
- Portable bundle
- Offline installer bundle

### P4：扩展版

- 专用压缩 Agent
- 探索 Agent
- 本地 HTTP/SSE 前端适配
- 更强的代码索引

---

## 16. 当前建议结论

本项目的最佳方向不是“再造一个大而全的 Agent 平台”，而是：

**做一个以 Agent Core 为中心、在 Windows 7 离线环境中可稳定运行、可整体打包、可向多前端和多智能体演进的轻量化工程 Agent。**

用一句更工程化的话概括：

**内核自研，外围大量复用；单 Agent 做深，协议先行解耦；离线打包优先，扩展能力预埋。**

---

## 17. 参考依据

### 仓库内分析

- `analysis/opencode-analysis.md`
- `analysis/openhands-analysis.md`
- `analysis/roo-code-architecture.md`
- `docs/context-management-research.md`

### 官方资料

- Python 3.8 Embedded Distribution:
  https://docs.python.org/3.8/using/windows.html#the-embeddable-package
- PyInstaller operating mode:
  https://pyinstaller.org/en/latest/operating-mode.html
- prompt_toolkit documentation:
  https://python-prompt-toolkit.readthedocs.io/
- Rich documentation:
  https://rich.readthedocs.io/
- Textual requirements:
  https://textual.textualize.io/getting_started/
- Universal Ctags:
  https://docs.ctags.io/
- ripgrep:
  https://github.com/BurntSushi/ripgrep
- Git for Windows build-extra:
  https://github.com/git-for-windows/build-extra
- SQLite download / amalgamation:
  https://www.sqlite.org/download.html
  https://www.sqlite.org/amalgamation.html
