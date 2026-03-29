# EmbedAgent — 轻量化嵌入式 C 语言 Agentic 编程平台

> **目标**：在 Windows 7 物理隔离内网环境下，提供一个极简、自包含、可实用的 AI 辅助嵌入式 C 语言开发平台。

---

## 项目定位

本项目是一个针对**嵌入式 C 语言开发**场景深度裁剪的 Agentic Coding 平台，不是通用智能体框架的又一次复制。

**适用场景**：
- 物理隔离内网，无互联网访问
- 目标 OS：Windows 7（及以上）
- 开发语言：C 语言（偏应用软件，聚焦业务逻辑与算法实现）
- 工具链：全套 Clang 体系，离线可用

**不做的事**：
- 网页搜索 / 网页访问
- 代码库索引 / 语义检索
- 多语言支持（Python、JS 等）
- 云端执行 / Docker 沙箱
- 插件市场 / 远程协作

---

## 核心能力

### C 语言开发
| 能力 | 工具 |
|------|------|
| 代码编写与修改 | Agent 工具调用（read/edit/write） |
| 桌面编译 | clang / clang-cl |
| 静态检查 | clang-tidy、clang-analyzer |
| 单元测试 | 基于 clang 构建的测试 runner |
| MC/DC 覆盖率 | clang 插桩 + 覆盖率报告 |
| 运行时分析 | AddressSanitizer、UBSan（clang 内置） |
| 仿真运行 | QEMU 或裸机仿真（待定） |

### 文档管理
- 文档读取与分析（Markdown、纯文本）
- 需求文档与设计文档的辅助编写
- 代码注释与 API 文档生成

### 版本管理
- 基于 Git 的提交、分支、回退操作
- Agent 自主生成提交信息
- 会话级变更快照（防止 Agent 操作失误）

### Agent 自治
- 任务规划与 TODO 自维护
- 多步工具调用循环（Agent Loop）
- 可配置模式与 Agent Harness（Ask / Orchestra / Spec / Code / Test / Verify / Debug）
- 上下文压缩（防止长任务超出 context window）
- 权限管控（操作前确认 / 自动放行规则）

---

## 设计原则

**极简但不简陋**

- Agent Loop 质量对标 OpenCode / OpenHands 的成熟设计，不因极简而退化
- 工具集精准裁剪，不做无用抽象
- 事件驱动架构，动作生成与执行分离，便于调试、回放、扩展

**自包含，零外部依赖**

- 整体打包可在目标机器直接运行，不依赖系统 Python / Node / MSVC 环境
- Clang 工具链内嵌，离线完整可用

**可扩展，但不过度设计**

- 工具接口、权限规则、Agent 配置均配置驱动
- 核心 Loop 与具体工具实现解耦
- 模式聚焦而非全能提示，每个模式职责单一、工具受限、便于弱模型稳定执行
- 预留子 Agent 接口（规划、探索、压缩等专用 Agent）

---

## 技术选型（当前实现 / 规划）

| 层次 | 选型 | 理由 |
|------|------|------|
| 实现语言 | Python 3.8 Embedded Distribution | Windows 7 兼容边界清晰，适合离线整体打包 |
| TUI 框架 | `prompt_toolkit` + `rich` | 纯终端、轻依赖、对 Windows/旧终端更友好 |
| LLM 接入 | OpenAI-compatible HTTP Adapter | 适配内网模型服务，不绑定单一厂商 SDK |
| 持久化 | 文件系统 JSON + SQLite（分阶段） | 当前以文件型记忆与摘要为主，后续补 SQLite 索引、权限与结构化状态 |
| 编译工具链 | LLVM/Clang Windows 预编译包 | 统一体系，覆盖编译 / 静态分析 / 覆盖率 |
| 版本管理 | MinGit / Portable Git | 可随包分发，满足无环境依赖要求 |
| 代码搜索 | `ripgrep` + `Universal Ctags` | 轻量、离线、适合 C 代码库结构化检索 |

---

## 参考架构分析

在正式编码前，对三个成熟开源项目进行了系统分析，分析结果存于 [analysis/](analysis/)：

| 项目 | 分析文件 | 主要借鉴点 |
|------|----------|-----------|
| [OpenCode](https://github.com/sst/opencode) | [opencode-analysis.md](analysis/opencode-analysis.md) · [deep-dive](analysis/opencode-deep-dive.md) · [permission](analysis/opencode-permission-sandbox.md) | 配置驱动 Agent、三值权限规则、Doom Loop 检测、上下文压缩 Agent |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | [openhands-analysis.md](analysis/openhands-analysis.md) · [deep-dive](analysis/openhands-deep-dive.md) · [sandbox](analysis/openhands-sandbox-security.md) | 事件驱动架构、Action/Observation 分离、AgentController 主控循环 |
| [Roo-Code](https://github.com/RooVetGit/Roo-Code) | [roo-code-architecture.md](analysis/roo-code-architecture.md) · [deep-dive](analysis/roo-code-deep-dive.md) · [permission](analysis/roo-code-permission-sandbox.md) | 流式响应处理、连续错误检测、基于栈的重试机制、工具重复检测 |

---

## 项目现状

- 2026-03-28：Phase 1-4 已完成最小可工作闭环，Phase 5 已完成到 5F（权限、Doom Loop、ContextManager、Artifact Store、Session Summary、Project Memory、恢复入口、memory cleanup/index）。
- 当前可运行能力已经覆盖：OpenAI-compatible LLM Adapter、文件 / Shell / Git / Clang 工具、模式系统、项目内闭环 LLVM/Clang 工具链、上下文压缩与基础记忆层。
- 当前主线工作已进入：Phase 4 真实工程验证，以及 Phase 6 终端前端模块化后的真实控制台 / Win7 运行验证收口。

- [x] 需求确认与范围界定
- [x] 参考项目架构分析（OpenCode / OpenHands / Roo-Code）
- [x] 整体架构设计文档（[docs/overall-solution-architecture.md](docs/overall-solution-architecture.md)）
- [x] 实施路线与文档维护方案（[docs/implementation-roadmap.md](docs/implementation-roadmap.md)）
- [x] 项目宪章（[AGENTS.md](AGENTS.md)）
- [x] 开发进度跟踪（[docs/development-tracker.md](docs/development-tracker.md)）
- [x] 设计与变更跟踪（[docs/design-change-log.md](docs/design-change-log.md)）
- [x] Phase 1 最小可工作 Loop
- [x] Phase 2 工具集 v1（文件 / Shell / Git）
- [x] Phase 3 模式系统 v1
- [x] Phase 4 第一版 Clang 工具封装与本地闭环工具链
- [x] Phase 5A-5F 质量保障层基础（权限、上下文、Artifact、Session Summary、Project Memory、恢复入口、cleanup/index）
- [x] 长任务稳定性验证与权限细化
- [ ] TUI / CLI adapters 收口（InProcessAdapter 已扩展 workspace / timeline / artifact / todo 浏览接口，终端前端已拆为 `src/embedagent/frontends/terminal/` 包并保留 `embedagent.tui` 兼容入口，已完成 headless/单元测试，待真实控制台 / Win7 手工验证）
- [ ] 打包与离线交付

### Phase 6 验证

自动化验证：

```powershell
.venv\Scripts\python.exe scripts\validate-phase6.py
```

手工验证说明见 [docs/phase6-validation.md](docs/phase6-validation.md)。

---

## 目录结构

```
ccode-win7/
├── AGENTS.md           # 项目级实现约束与 agent 宪章
├── analysis/           # 参考项目架构分析文档
├── docs/               # 设计文档
│   ├── adrs/
│   ├── development-tracker.md
│   └── design-change-log.md
├── reference/          # 参考项目源码（opencode / OpenHands / Roo-Code）
├── scripts/            # 本地辅助脚本（LLVM 激活 / smoke test 等）
├── src/
│   └── embedagent/
│       ├── artifacts.py
│       ├── cli.py
│       ├── context.py
│       ├── frontends/
│       │   └── terminal/  # 模块化终端前端（state / reducer / controller / views / services）
│       ├── guard.py
│       ├── inprocess_adapter.py
│       ├── llm.py
│       ├── loop.py
│       ├── memory_maintenance.py
│       ├── modes.py
│       ├── permissions.py
│       ├── project_memory.py
│       ├── session.py
│       ├── session_store.py
│       ├── session_timeline.py
│       ├── tools/
│       └── tui.py      # 兼容 shim，导出模块化终端前端入口
├── tests/              # 单元测试与前端回归测试
├── toolchains/         # 项目内闭环 LLVM/Clang 工具链与清单
├── pyproject.toml      # uv / Python 版本与项目元数据
└── README.md
```

---
## License

待定。参考项目均为开源项目，本项目实现将避免直接复制其代码。


