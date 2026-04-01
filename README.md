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

## 核心能力（当前已落地）

### C 语言研发闭环
| 能力 | 当前实现 |
|------|----------|
| 代码查看与精确修改 | `read_file` / `list_files` / `search_text` / `edit_file` |
| 编译 | `compile_project` + 项目内闭环 LLVM/Clang 工具链 |
| 单元测试执行 | `run_tests` |
| 静态检查 | `run_clang_tidy` / `run_clang_analyzer` |
| 覆盖率统计与质量门 | `collect_coverage` / `report_quality` |
| 任务跟踪 | `manage_todos` + 模式化 Agent Loop |

### 文档与项目治理
- 文档读取与分析（Markdown、纯文本）
- 需求、设计、进度与变更文档的辅助维护
- `Session Summary` / `Project Memory` / `Artifact Store` 持久化

### 版本与工作区检查
- Git 状态、差异、历史查询
- 会话级 timeline / artifact / todo 浏览
- Git 写操作（提交、分支、回退）仍属于后续工作

### Agent 运行控制
- 多步工具调用循环（Agent Loop）
- 单个用户问题下支持多次 Agent 自推进 step（thinking / tools / partial answer 分步呈现）
- 配置驱动模式与 Agent Harness（Explore / Spec / Code / Debug / Verify），可通过 `modes.json` 覆盖或扩展
- 上下文压缩、记忆清理与恢复入口
- 权限管控（操作前确认 / `allow` / `ask` / `deny` 规则）
- 托管运行环境摘要（bundle/workspace/system 来源、内置工具就绪状态、回退告警）

当前尚未收口的能力主要是：

- Phase 4 真实 C 工程与 Win7 验证
- Phase 6 真实控制台 / Win7 / ConEmu 手工验证
- Phase 7 打包与离线交付

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
| GUI 框架 | `pywebview` + FastAPI + WebSocket | 现代 Web 界面、Windows 7 兼容（IE11 回退） |
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

- 2026-04-01：Phase 1 clean-room 高拟态升级切片已落地：时间线 API 现在以 `turns[].steps[]` 为主，GUI 可按单用户 turn 下的多个 agent step 显示 thinking/tool/assistant；托管运行环境会统一汇总 `runtime_source`、`bundled_tools_ready`、`fallback_warnings` 与 `resolved_tool_roots`，并在 GUI Runtime inspector 中显示。
- 2026-03-31：已落地 unified input / slash command / workflow 第一版：`submit_user_message` 现在统一分发普通消息与 `/help` `/mode` `/sessions` `/resume` `/workspace` `/clear` `/plan` `/review` `/diff` `/permissions` `/todos` `/artifacts`；协议层新增 `CommandResult`、`PlanSnapshot`、`TurnRecord`、`TimelineItem` 与扩展 `SessionSnapshot`；GUI 已接入 command result、plan pane、timeline command cards 与 slash command hint。
- 2026-03-30：新架构落地：`protocol/` 通信协议层、`core/` AgentCoreAdapter、`frontend/gui/` PyWebView 前端，TUI 迁移至 `frontend/tui/`，架构测试 17 项全通过，文档已同步更新。
- 2026-03-29：Phase 1-5 功能已落地；修复根目录文件写入边界后，`scripts/validate-phase5.py` 已重新跑通。
- 2026-03-29：Phase 6 自动化验证已通过；`scripts/validate-phase6.py` 与 `unittest discover -s tests -v` 已可复跑。
- 当前主线工作：Phase 4 真实 C 工程 / Win7 验证、Phase 6 真实控制台 / Win7 手工验证、Phase 7 打包与离线交付设计。
- 2026-03-29：Phase 7 设计基线已建立：`docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md`。
- 2026-03-29：Phase 7 首个脚本骨架已建立：`scripts/prepare-offline.ps1` 可生成 staging bundle 目录、launcher、模板配置、`bundle-manifest.json` 与 `checksums.txt`。
- 2026-03-29：Phase 7 `scripts/build-offline-bundle.ps1` 已落地，可把 staging bundle 复制到 `build/offline-dist/` 并生成 zip。
- 2026-03-29：Phase 7 `scripts/validate-offline-bundle.ps1` 已落地，默认模式可校验 skeleton bundle 并输出告警，`-RequireComplete` 可收紧为正式验收门。
- 2026-03-29：Phase 7 已正式接入真实 `Python 3.8 embeddable x64` 与 `MinGit x64` 资产，`scripts/offline-assets.json`、sources seed、license notice 和完整性校验链路已跑通。
- 2026-03-29：Phase 7 已继续接入真实 `ripgrep x64` 与 `Universal Ctags x64` 资产，当前 `prepare/build/validate -RequireComplete` 已在四类核心资产上全量通过。

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
- [x] 长任务稳定性验证与权限细化（`scripts/validate-phase5.py` 已复验通过）
- [x] Phase 6 自动化验证（`scripts/validate-phase6.py` + `unittest discover -s tests -v`）
- [ ] TUI / CLI adapters 收口（InProcessAdapter 已扩展 workspace / timeline / artifact / todo 浏览接口，终端前端已拆为 `src/embedagent/frontends/terminal/` 包并保留 `embedagent.tui` 兼容入口；真实控制台 / Win7 手工验证与交互细化待完成）
- [ ] 打包与离线交付

### 当前验证入口

自动化验证：

```powershell
.venv\Scripts\python.exe scripts\validate-phase5.py
.venv\Scripts\python.exe scripts\validate-phase6.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Phase 6 手工验证说明见 [docs/phase6-validation.md](docs/phase6-validation.md)。

Phase 7 设计基线见：

- [docs/offline-packaging.md](docs/offline-packaging.md)
- [docs/win7-preflight-checklist.md](docs/win7-preflight-checklist.md)
- [docs/adrs/0001-offline-portable-bundle-baseline.md](docs/adrs/0001-offline-portable-bundle-baseline.md)

---

## 目录结构

```
ccode-win7/
├── AGENTS.md           # 项目级实现约束与 agent 宪章
├── analysis/           # 参考项目架构分析文档
├── docs/               # 设计文档
│   ├── adrs/
│   ├── development-tracker.md
│   ├── design-change-log.md
│   ├── offline-packaging.md
│   ├── frontend-protocol.md      # 前端协议定义
│   ├── architecture-new.md       # 新架构文档
│   └── win7-preflight-checklist.md
├── reference/          # 参考项目源码（opencode / OpenHands / Roo-Code）
├── scripts/            # 本地辅助脚本（LLVM 激活 / smoke test 等）
├── src/
│   └── embedagent/
│       ├── artifacts.py
│       ├── cli.py
│       ├── context.py
│       ├── core/                 # Agent Core 适配层
│       │   ├── __init__.py
│       │   └── adapter.py        # AgentCoreAdapter
│       ├── frontends/
│       │   └── terminal/         # 模块化终端前端（向后兼容）
│       ├── frontend/             # 新前端架构
│       │   ├── tui/              # TUI 实现（prompt_toolkit）
│       │   │   ├── launcher.py
│       │   │   ├── frontend_adapter.py
│       │   │   └── ...
│       │   └── gui/              # GUI 实现（PyWebView）
│       │       ├── launcher.py
│       │       ├── backend/
│       │       └── static/
│       ├── guard.py
│       ├── inprocess_adapter.py
│       ├── llm.py
│       ├── loop.py
│       ├── memory_maintenance.py
│       ├── modes.py
│       ├── permissions.py
│       ├── project_memory.py
│       ├── protocol/             # 通信协议层
│       │   └── __init__.py       # CoreInterface, FrontendCallbacks
│       ├── session.py
│       ├── session_store.py
│       ├── session_timeline.py
│       ├── tools/
│       └── tui.py                # 兼容 shim
├── tests/              # 单元测试与前端回归测试
├── toolchains/         # 项目内闭环 LLVM/Clang 工具链与清单
├── pyproject.toml      # uv / Python 版本与项目元数据
└── README.md
```

---
## License

待定。参考项目均为开源项目，本项目实现将避免直接复制其代码。


