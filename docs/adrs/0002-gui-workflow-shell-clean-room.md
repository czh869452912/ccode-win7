# ADR-0002：GUI 工作流壳层与 clean-room Claude Code 风格升级

- 状态：accepted
- 日期：2026-03-31

## 背景

项目已经具备：

- Win7 / Python 3.8 / 离线部署基线
- Agent Core 与前端协议分层
- 5 模式内核
- GUI 宿主与 React/Vite webapp 壳层

但现有产品入口仍偏“模式驱动”，而不是“命令 / workflow 驱动”。
这会让用户必须先思考 mode，再思考任务，不利于对标 Claude Code 类产品的使用节奏。

同时，本项目仍需保持：

- 不复制 `reference/claude-code` 实现代码
- 不引入 Node.js / Docker / 在线服务作为运行时依赖
- 不膨胀为通用插件平台或多 Agent 编排系统

## 决策

采用 **clean-room 对标** 路线，升级为：

- GUI-first 的单主 Agent IDE
- slash command / workflow 作为产品表层
- 5 模式继续保留，但退到 Core 执行边界

具体决定：

1. 保留 `explore`、`spec`、`code`、`debug`、`verify` 五个核心模式
2. `/plan`、`/review`、`/permissions`、`/diff`、`/sessions` 等作为 workflow / command，不新增核心 mode
3. `submit_user_message` 升级为统一输入总线，普通消息与 slash command 共用 session / timeline / permission / snapshot
4. 协议层新增 `CommandResult`、`PlanSnapshot`、`TurnRecord`、`TimelineItem`、`PermissionContextView`
5. GUI 继续使用 `PyWebView + 本地后端 + 预构建静态资源`，不改变 Win7 bundle 路径

## 结果

正面影响：

- 用户主入口从“先选 mode”转成“直接发命令或消息”
- Core 继续保留模式约束、工具过滤和写入边界
- GUI/TUI/CLI 可以共享同一输入分发和命令语义
- 计划、审查、权限上下文成为 session 内的一等工件

代价与限制：

- `/review` 第一版仍以本地证据汇总为主，尚未形成更复杂的审查工作流
- TUI 只保留核心命令透传与兜底能力，不追求 Claude Code 级终端交互
- 仍需在 Win7 bundle 上做 GUI workflow / WebView2 路径实机验收

## 备选方案

### 方案 A：删除模式，仅保留命令与工作流

未采用。

原因：

- 会削弱弱模型下的工具池收敛与写入边界
- 不利于离线环境中的可审计性和安全前置过滤

### 方案 B：继续以 mode 作为产品主导航

未采用。

原因：

- 交互成本偏高
- 与目标产品体验不一致

### 方案 C：直接照抄 `reference/claude-code`

未采用。

原因：

- 不符合 clean-room 约束
- 技术栈与 Win7 / Python 3.8 / 离线 bundle 基线不兼容
