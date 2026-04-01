# ADR-0003：Agent Step 时间线与托管运行环境摘要作为 GUI 壳层新基线

- 状态：accepted
- 日期：2026-04-01

## 背景

现有 GUI 与 Core 已具备：

- unified input / slash command / workflow 第一版
- `session_snapshot`、`reasoning_delta`、`thinking_state`、稳定 `tool_call_id`
- React/Vite webapp + PyWebView 宿主

但仍存在两个关键缺口：

1. 同一条用户问题如果触发多轮 Agent 自推进，timeline 只能按“单 user bubble + 一坨 think/tool/assistant”显示，无法复刻 Claude Code 式的多 step 体验。
2. 工具链虽然已开始通过 bundle 注入 PATH，但 Core / GUI 仍无法明确展示当前到底使用的是 bundle、workspace 还是 system 工具，也不能稳定暴露缺失和回退告警。

## 决策

采用以下新基线：

1. `Turn` 与 `Agent Step` 分离：一个用户 turn 下允许多个 agent step，每个 step 单独承载 `thinking -> tools -> assistant`
2. 时间线 API 以 `build_structured_timeline()` 返回的 `turns[].steps[]` 为主；raw events 继续保留，但只作为调试 / 回放补充
3. Tool Runtime 统一生成托管运行环境摘要：
   - `runtime_source`
   - `bundled_tools_ready`
   - `fallback_warnings`
   - `resolved_tool_roots`
4. `SessionSnapshot` 与工具结果都带上运行环境摘要，GUI 通过 Runtime inspector 直接展示
5. GUI timeline 改为“一个用户 turn，下分多个 agent step”的壳层结构，而不是继续依赖扁平事件猜分组

## 结果

正面影响：

- GUI 能正确复刻多轮 think/tool/assistant 的交互节奏
- 历史回放与实时 WebSocket 增量使用同一套 turn/step 模型
- 托管运行环境从隐式 PATH 注入提升为可观测的一等能力
- 后续可继续在 step 维度叠加 diagnostics、plan、review evidence，而不必重写时间线结构

代价与限制：

- 协议层、InProcessAdapter、GUI reducer 和 timeline 组件需要同步升级
- 旧 session 的 timeline 仍需保留 raw-event fallback
- 当前只解决 step 粒度的单 agent 迭代，不引入多 agent / coordinator

## 备选方案

### 方案 A：继续使用扁平 timeline，只在前端 heuristics 分组

未采用。

原因：

- 仍然依赖“从最后一个 user bubble 猜本轮范围”的脆弱规则
- 历史回放与实时增量很难保持一致

### 方案 B：只做 Runtime inspector，不改事件模型

未采用。

原因：

- 不能解决最明显的交互退化问题
- 仍会让同一问题下的多轮 agent 自推进挤在一个 think / assistant 框里

### 方案 C：直接照搬 Claude Code 的 task/query/tool 前端实现

未采用。

原因：

- 不符合 clean-room 约束
- 技术栈与 Win7 / Python 3.8 / PyWebView bundle 基线不兼容
