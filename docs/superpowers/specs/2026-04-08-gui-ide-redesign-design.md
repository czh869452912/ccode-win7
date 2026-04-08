# EmbedAgent GUI 迭代设计文档：Agent 原生简易 IDE

**日期**: 2026-04-08  
**目标**: 将当前聊天式 GUI 重塑为一个 Agent 原生的简易 IDE，面向 C 语言全生命周期开发与管理。  
**约束**: Windows 7 兼容、离线部署、Python 3.8 运行时、自包含 bundle。

---

## 1. 设计目标与原则

### 目标
构建一个以 Agent 对话为主轴、同时具备代码编辑能力的简易 IDE，覆盖 C 语言开发的核心路径：代码阅读、编辑、编译、测试、诊断、调试。

### 核心原则

| 原则 | 说明 |
|------|------|
| **Agent 原生** | 界面不是「IDE + 聊天插件」，而是「对话为主轴，编辑和工具为对话中的可交互对象」。 |
| **渐进 IDE 化** | 不追求 VS Code 的完整度，但在 C 开发的关键路径上提供足够的物理空间和可操作性。 |
| **上下文不丢失** | 任何视图切换都不能让用户脱离当前的 Agent 对话上下文。 |
| **离线轻量** | 前端不引入 Monaco、不依赖 Node.js 运行时、不依赖在线 CDN。编辑器基线采用 CodeMirror 5 轻量版。 |

---

## 2. 布局与导航架构

采用 **三栏自适应布局**，中央主区域具备**对话/编辑 Split 能力**。

```
┌────────────────────────────────────────────────────────────┐
│  Header (Logo | Mode | Phase breadcrumb | Quick actions)   │
├──────────┬───────────────────────────────┬────────────────┤
│          │                               │                │
│ Sidebar  │    Main Workspace             │  Inspector     │
│ (Files/  │  ┌───────────┬─────────────┐  │  (Diagnostics/ │
│ Sessions/│  │ Timeline  │  Editor     │  │   Tasks /      │
│ Tasks)   │  │  (聊天流)  │  (代码编辑)  │  │   Build /      │
│          │  │           │             │  │   Tests ...)   │
│          │  │           │             │  │                │
│          │  └───────────┴─────────────┘  │                │
│          │         ↑ Composer (底部)      │                │
└──────────┴───────────────────────────────┴────────────────┘
```

### 布局规则

1. **默认状态**：当用户没有打开任何文件时，Main Workspace **100% 显示 Timeline**。
2. **Split 状态**：当用户从文件树或 Diff 卡片点击「Open in Editor」时，Main Workspace 自动变为 **Timeline | Editor 左右分栏**。默认各占 50%，中间有可拖拽的分隔条调整宽度。
3. **Composer 位置**：Split 模式下 Composer 始终位于 Timeline 底部，保证对话上下文和输入入口不被编辑器挤占。
4. **面板宽度**：Sidebar 和 Inspector 的宽度可拖拽调节，但最小宽度需保证基本可读性（Sidebar ≥ 160px，Inspector ≥ 200px）。

---

## 3. 核心组件定义

### 3.1 Header

- **左侧**：EmbedAgent Logo + 当前 Mode badge（explore / spec / build / debug / verify）。
- **中部**：Phase breadcrumb，可视化当前任务阶段（如 `explore → spec → build`）。
- **右侧**：
  - Quick Actions：Build / Test / Debug 三个快捷按钮。点击后向当前 Session 发送等效于自然语言的指令，由 Agent 自动执行对应 recipe。
  - 状态指示器：显示当前 session 状态（idle / running / waiting_permission / waiting_user_input）。

### 3.2 Sidebar（左侧，顶部 Tab 切换）

Sidebar 通过顶部 Tab 在三态之间切换：

- **Files**：
  - 树形工作区文件浏览器，支持展开/折叠目录。
  - 点击文件的行为：
    - 如果该文件已在某个 Editor Tab 中打开 → 聚焦该 Tab。
    - 否则 → 在 Editor 区域新建 Tab 并加载文件内容。
- **Sessions**：
  - 显示历史会话列表，包含会话标题、模式、最后活跃时间。
  - 支持点击切换会话或恢复已结束会话。
- **Tasks**：
  - 显示当前会话的 TaskGraph 概览。
  - 包括当前阶段、discipline_profile、任务摘要、子任务列表及完成状态。

### 3.3 Timeline（中间左侧，对话流）

- 垂直滚动的消息流，包含：
  - 用户消息气泡
  - Agent 消息气泡（支持 Markdown、代码块、表格）
  - 工具调用卡片（tool_start / tool_progress / tool_finish）
  - Diff 卡片（Agent 提议的代码变更）
  - 系统事件卡片（mode switch、error、context compaction 提示等）
- **Diff 卡片交互**：
  - 每个 Diff 卡片必须同时提供 **Apply** 和 **Open in Editor** 两个按钮。
  - **Apply**：直接将 Diff 应用到文件系统，成功后显示 Toast 提示。
  - **Open in Editor**：在 Editor 区域打开对应文件，以 Diff 覆盖层形式显示修改前后对比，用户可二次编辑后手动保存。
- **Composer**：
  - 位于 Timeline 底部。
  - 保持现有的 `mode-badge + textarea + send/stop` 结构。
  - textarea 支持多行输入，Enter 发送，Shift+Enter 换行。

### 3.4 Editor（中间右侧，条件渲染）

- **基线技术**：CodeMirror 5 轻量版（纯前端，~200KB，Win7 兼容）。
- **功能基线**：
  - C 语法高亮
  - 行号显示（可开关）
  - 括号匹配
  - 基础搜索替换（Ctrl+F / Ctrl+H）
  - 多 Tab（支持同时打开多个文件）
  - Diff 覆盖层：打开 Diff 时显示修改前后的行级高亮（红/绿）
- **Tab 行为**：
  - 每个打开的文件对应一个 Tab。
  - 未保存修改的 Tab 显示一个小圆点标记。
  - 支持关闭 Tab（关闭时若未保存需提示）。
- **后续扩展点（不纳入本期必须）**：
  - 通过已有的 ctags/clangd bundle 集成「跳转到定义」和「错误波浪线」。前端预留接口槽位。

### 3.5 Inspector（右侧，顶部 Tab 切换）

Inspector 是 C 开发信息和 Agent 工作流详情的集中展示区。Tab 按优先级排列：

- **Diagnostics**（高优先级）：
  - 展示静态分析结果：clang-tidy、clang-analyzer、MC/DC 覆盖率缺陷等。
  - 每条结果显示：文件路径、行号、严重程度、描述。
  - 点击条目可直接跳转到 Editor 对应行。
- **Tasks**（高优先级）：
  - TaskGraph 的详细视图。
  - 与 Sidebar 的 Tasks 是同一数据源的不同密度呈现：Sidebar 是概览，Inspector 是完整展开。
- **Build**（中优先级）：
  - 原始编译输出日志。
  - 如果空间紧张或用户偏好简洁，可默认折叠，或以 Rich Card 形式在 Timeline 中展示摘要。
- **Tests**（中优先级）：
  - 单元测试运行日志、失败用例详情、覆盖率摘要。
- **Git Diff / Coverage**（低优先级/扩展预留）：
  - 为后续版本预留的 Tab 位置。

### 3.6 Permission / User Input Modal

- 保持现有模态弹窗处理：
  - **Permission Request**：显示 tool_name、category、reason、details，提供 Approve / Deny 和 Remember 勾选框。
  - **User Input Request**：显示 question、options、details，提供文本输入或选项选择。
- 这两个是 Agent 工作流的关键阻断点，必须以模态形式强提醒，不允许弱化为中心通知。

---

## 4. C 语言全生命周期工作流映射

| 场景 | 用户行为 | GUI 呈现 |
|------|----------|----------|
| **阅读/浏览代码** | 点击 Sidebar Files 中的文件 | Main Workspace Split 出 Editor 显示代码，Timeline 保持当前对话不变 |
| **Agent 提议修改** | 观看 Timeline 中的 Diff 卡片 | 提供 Apply（一键落盘）和 Open in Editor（对比层确认） |
| **手工编辑代码** | 在 Editor 中直接输入 | 文件标记为 dirty，Tab 显示圆点；保存时通过 `write_file` API 落盘 |
| **编译项目** | 点击 Header Build 按钮，或对 Agent 说「编译」 | Agent 执行 build recipe；Timeline 插入 Build Summary Card；Inspector 可自动切到 Build Tab |
| **查看编译错误** | 在 Timeline 或 Inspector 中查看 | Diagnostics Tab 显示结构化错误列表；点击条目跳转 Editor 对应行 |
| **运行测试** | 点击 Header Test 按钮，或对话触发 | Agent 执行 test recipe；Timeline 插入测试摘要 Card；失败用例可展开 |
| **静态分析** | 通常由 Agent 自动触发 | Diagnostics Tab 接收 `report_quality_v2` 的结构化结果 |
| **调试** | 点击 Header Debug 按钮 | Agent 进入 debug 阶段；Timeline 显示调试会话摘要；预留 GDB 集成视图槽位 |

---

## 5. 数据流与状态管理

### 后端真相源

- `QueryEngine` + `Session` + `transcript.jsonl` 仍是唯一的持久真相源。
- 所有 workflow 语义（mode、phase、task、permission）由后端 Agent Core 主导，前端仅做投影和交互壳。

### 前端状态分层

1. **全局 UI 状态**（前端本地管理，不进入 Session）：
   - 当前布局（Split 比例、Sidebar/Inspector 宽度）
   - Sidebar 当前激活 Tab（Files/Sessions/Tasks）
   - Inspector 当前激活 Tab
   - Editor 打开的文件列表、当前活跃 Tab、dirty buffer 状态
2. **会话投影状态**（从后端同步）：
   - 消息流、任务状态、工具结果、权限请求
   - 同步通道：WebSocket `/ws` 用于实时事件；HTTP `/api/sessions/{id}/bootstrap` 用于初始加载和恢复。
3. **编辑器内容状态**（前端持有，按需写回）：
   - 打开文件的文本内容由前端通过 `/api/files/{path}` 读取。
   - 未保存修改存在于前端内存；保存时通过 `write_file` API 或 Agent tool 写回磁盘。

### 编辑器与 Session 的解耦

用户打开哪些文件进行编辑，是前端本地的 UI 状态，不作为 Session 事件写入 transcript。这避免了：
- 污染 Agent 的执行历史
- 增加 transcript 体积
- 在跨前端（TUI/GUI）切换时产生不一致预期

---

## 6. 技术约束与实现建议

### 前端技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 构建工具 | Vite（现有） | 当前 webapp 已使用，继续沿用。 |
| UI 框架 | React（现有） | 当前 app.js 已基于 React 构建，组件化改造成本最低。 |
| 编辑器 | CodeMirror 5 | 纯 JS、轻量、Win7/离线兼容、支持 C 语法高亮。 |
| 通信 | WebSocket + FastAPI | 现有 backend 已是 FastAPI + WebSocket，协议层无需大改。 |
| 静态资源 | 完全内嵌 | 继续将所有 CSS/JS/字体打包进 `static/` 目录，不引用外部 CDN。 |

### 后端影响范围

本版 GUI 迭代**不应**大规模改变后端 Agent Core 的 workflow 语义。但可能需要以下小幅度增强：

1. **编辑器 API**：确保 `/api/files/{path}` 的读写接口稳定且响应快速（CodeMirror 需要频繁读取文件）。
2. **Diff 预览 API**：现有 `/api/diff` 接口可能需要支持「基于 editor buffer 的临时 Diff」（当用户尚未保存时）。
3. **Diagnostics 结构化数据**：`report_quality_v2` 的结果需要有一个专门的前端消费格式，包含 `file`、`line`、`severity`、`message`、`rule_id` 等字段。
4. **Quick Actions 映射**：Header 的 Build/Test/Debug 按钮本质上可以复用现有的 `core.submit_message(session_id, text)`，发送等效文本（如 `"/build"` 或 `"执行 build recipe"`），无需新增专用 API。

### 边界情况与错误处理

| 边界情况 | 处理策略 |
|----------|----------|
| **Editor 打开时文件被 Agent 外部修改** | 保存前检查文件 mtime，若不一致提示用户「文件已被外部修改，是否覆盖/重载」。 |
| **Apply Diff 时文件已被外部修改** | 在 Apply 前通过 API 获取最新内容重新生成 Diff；若冲突则打开 Editor 的 Diff 覆盖层让用户手动解决。 |
| **Split 模式下窗口宽度太小** | 当窗口宽度低于某个阈值（如 960px）时，Editor 从并排模式切换为 Overlay/Tab 模式，避免两栏都过窄。 |
| **WebSocket 断开** | 显示非阻断式重连提示；恢复连接后根据 bootstrap payload 重新同步状态和消息流。 |
| **Win7 WebView2 兼容性** | CodeMirror 5 对旧版 Chromium 支持良好；避免使用 CSS Grid 的高级特性和较新的 JS API（如 `Array.prototype.toSorted`）。首屏加载资源总量应控制在 < 2MB。 |

---

## 7. 非目标（Out of Scope）

以下功能明确不在本期迭代范围内：

- 完整的 IDE 级调试器 UI（断点、调用栈、变量监视）——仅预留接口和 Debug 快捷按钮。
- 多工作区/多窗口支持。
- 插件/扩展系统。
- 实时协同编辑。
- Git 图形化操作面板（暂时的，预留位置但不实现）。
- Monaco Editor 或 VS Code 内核集成。

---

## 8. 验收标准

1. 用户可以从 Sidebar 文件树打开 C 文件，Editor 区域正确高亮并显示行号。
2. 打开文件后 Main Workspace 自动进入 Split 模式，Timeline 和 Editor 并排可见。
3. Agent 发出的 Diff 卡片同时包含 Apply 和 Open in Editor 按钮，且两者均可正常工作。
4. Header 的 Build / Test / Debug 快捷按钮点击后能正确触发 Agent 执行对应 recipe。
5. Inspector 的 Diagnostics 和 Tasks Tab 能正确接收并展示后端数据。
6. 在 Win7 离线 bundle 中，GUI 能正常启动且首屏资源加载不超过 3 秒。

