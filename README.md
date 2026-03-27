# EmbedAgent — 轻量化嵌入式 C 语言 Agentic 编程平台

> **目标**：在 Windows 7 物理隔离内网环境下，提供一个极简、自包含、可实用的 AI 辅助嵌入式 C 语言开发平台。

---

## 项目定位

本项目是一个针对**嵌入式 C 语言开发**场景深度裁剪的 Agentic Coding 平台，不是通用智能体框架的又一次复制。

**适用场景**：
- 物理隔离内网，无互联网访问
- 目标 OS：Windows 7（及以上）
- 开发语言：C 语言（嵌入式方向）
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
- 文档读取与分析（PDF、Markdown、纯文本）
- 需求文档与设计文档的辅助编写
- 代码注释与 API 文档生成

### 版本管理
- 基于 Git 的提交、分支、回退操作
- Agent 自主生成提交信息
- 会话级变更快照（防止 Agent 操作失误）

### Agent 自治
- 任务规划与 TODO 自维护
- 多步工具调用循环（Agent Loop）
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
- 预留子 Agent 接口（规划、探索、压缩等专用 Agent）

---

## 技术选型（规划中）

| 层次 | 选型 | 理由 |
|------|------|------|
| 实现语言 | Python 3.x（嵌入式分发） | 单文件可分发，生态丰富，适合快速迭代 |
| TUI 框架 | `textual` 或 `urwid` | 纯终端，无 GUI 依赖，Windows 7 兼容 |
| LLM 接入 | Anthropic Claude API（HTTP） | 标准 REST，可替换为任意兼容接口 |
| 持久化 | SQLite | 内置，零依赖，会话历史 / 权限规则均可存储 |
| 编译工具链 | LLVM/Clang Windows 预编译包 | 统一体系，覆盖编译 / 静态分析 / 覆盖率 |
| 版本管理 | Git（命令行调用） | 标准工具，Agent 直接调用 |

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

- [x] 需求确认与范围界定
- [x] 参考项目架构分析（OpenCode / OpenHands / Roo-Code）
- [ ] 整体架构设计文档
- [ ] Clang 工具链集成方案
- [ ] Agent Loop 核心实现
- [ ] TUI 界面原型
- [ ] 工具集实现（文件 / Shell / Git / Clang）
- [ ] 权限系统实现
- [ ] 上下文压缩策略
- [ ] 打包与分发

---

## 目录结构

```
coding_agent/
├── analysis/           # 参考项目架构分析文档
├── reference/          # 参考项目源码（opencode / OpenHands / Roo-Code）
├── docs/               # 设计文档（待补充）
└── README.md
```

---

## License

待定。参考项目均为开源项目，本项目实现将避免直接复制其代码。
