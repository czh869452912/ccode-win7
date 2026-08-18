# ADR-0009: Pi-shaped Core 与 Cordis-lite 组合运行时

- 状态：`accepted`
- 日期：2026-08-18
- 相关文档：
  - `docs/platform/agent-core.md`
  - `docs/platform/tools-and-extensions.md`
  - `docs/platform/agent-platform-blueprint.md`
  - `docs/overall-solution-architecture.md`

## 背景

EmbedAgent 需要同时满足两个容易互相冲突的目标：Agent Core 必须足够小、可离线运行、可恢复和可测试；Host/Application 又需要支持能力注册、工作流插件、工具策略、动态 workspace 扩展和资源生命周期。

Pi 的 Agent Core 通过显式状态、显式 loop、事件流和 append-only session 保持内核可理解。Cordis 则通过作用域、依赖注入、可逆 effect、fiber 生命周期和 quiescent teardown 解决运行时组合问题。两者解决的是不同层级的问题。

直接把 Cordis Context/Fiber 搬进 Core 会扩大内核语义面，并引入 ambient service lookup、动态配置和不可证明的逆操作；只采用 Pi 的注册回调又无法结构性保证扩展卸载、资源所有权和依赖撤销。

## 决策

采用 **Pi-shaped Core + Cordis-lite Composition Runtime**：

1. Core 继续只拥有 Agent/AgentSession、SessionJournal/Reducer、AgentKernel、AgentLoop、权限和 focused ports。Core 不引入通用 Service Registry、ambient Context 或在线插件加载器。
2. Host/Application 使用一个小型 `RegistrationScope` 表达 owner、子作用域、注册 effect、quiescence 和逆序 disposer。该原语不承载工作流语义，也不负责加载任意外部代码。
3. 能力使用显式 `source_id`、`scope_id`、`requires`、`provides` 和 permission metadata。动态注册必须返回可幂等调用的 disposer；禁止只有 append、没有撤销的全局注册。
4. 事件只允许有限的 typed dispatch mode：观察型 `emit`、有序 `serial`、可短路 `waterfall` 和白名单 `parallel`。事件传播受 scope admission 限制。
5. durable session ledger 仍是唯一事实源。`model-visible means logged`、append-before-apply、同一 reducer restore/live 和 workflow projection-only 规则不因插件化改变。
6. Effect 按可逆内部资源、可补偿外部资源和不可逆外部操作分层。只有第一类自动 disposer；第二、三类必须通过 journal、permission 和 operation marker 管理，不能伪称 rollback。
7. 形式化保证以可执行契约、状态机、属性测试和架构门禁为第一阶段目标；只对 scope lifecycle、工具取消和并发 admission 等有限模型引入 TLA+/PlusCal，不追求证明全部业务代码。

## 生命周期契约

`RegistrationScope` 的状态为 `ACTIVE -> QUIESCING -> DISPOSED`。其不变量是：

- scope 进入 `QUIESCING` 后不再接受新的 registration 或 operation admission；
- child scope 先于 parent scope dispose；
- disposer 逆注册顺序执行，且每个 disposer 至多产生一次实际清理；
- dispose 等待已 admission 的 operation 退出；
- 安装失败必须撤销本次安装已经产生的 registration；
- 同一个 scope 和 manifest 的激活结果可重复得到同一 capability projection。

## 影响

收益：Core 的稳定面不因插件数量增长；Host 可以获得可审计的资源所有权和 teardown 语义；扩展注册泄漏和重复投影可以通过句柄及属性测试发现。

代价：Host/Application 需要显式传递 scope 和 disposer；部分现有 manager、reducer registry 和 project extension loader 需要迁移；不可逆 effect 仍需要补偿和权限设计，Cordis-style disposer 不能替代它们。

安全边界：不采用 Node/Cordis runtime、npm/remote marketplace、在线 HMR、MCP remote 或 Pi 的“扩展拥有进程全部权限”模型。project extension 继续 workspace-bound、manifest-gated、offline-only，并经过现有 permission boundary。

## 备选方案

### 纯 Pi

内核简单、会话和 replay 清晰，但生命周期、依赖关系和资源回收主要靠约定，不能解决当前 ExtensionManager/AgentEventBus 没有 disposer 的技术债。

### 全量 Cordis

动态组合和 lifecycle 语义更强，但会把 Context/Fiber/effect/coeffect 复杂度带入 Core，扩大 Python 3.8/Win7 离线运行时风险，并让 durable session truth 与运行时上下文产生竞争。

### 通用全局 Service Registry

实现成本低，但会重新引入隐式依赖、跨 scope 泄漏和 teardown 无主的问题，违反 focused ports 和 Core/Host 边界。

## 后续动作

1. 添加独立的 `RegistrationScope` 及契约测试。
2. 让 `AgentEventBus` 注册返回 disposer，并让扩展注册使用可追踪 owner。
3. 将 `ApplicationRegistrar` 的现有 disposer 栈迁移到该原语。
4. 为 `HostedRuntime`、`InProcessAdapter` 和 session lifecycle 增加 quiescent close。
5. 将 C/C++ TaskGraph 收敛到 workflow-owned durable event source，清除并行状态真相。
6. 增加 requires/provides/runtime closure 的 manifest 校验，再继续处理 mode/profile 去平台化。
