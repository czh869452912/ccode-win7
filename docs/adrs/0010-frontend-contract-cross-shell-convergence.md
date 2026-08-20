# ADR-0010: Frontend Contract v2 Cross-Shell Convergence

- 状态：`accepted`
- 日期：2026-08-20
- 相关文档：
  - `docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md`
  - `docs/platform/frontend-protocol.md`
  - `docs/platform/frontend-gui.md`
  - `docs/platform/frontend-tui.md`
  - `docs/superpowers/plans/2026-08-20-frontend-contract-v2-design.md`

## 背景

Phase 4 收敛了 Core/Host 的应用选择、provider 注入和独立 wheel 边界，但 CLI、TUI、GUI
仍有几条没有同步迁移的前端路径。当前三端对失败记录、session owner、interaction
descriptor、WebSocket envelope 和 workspace notification 的处理不同；部分旧测试仍只验证
shell-local projection，因此绿色测试不能证明跨 shell 行为一致。

已确认的主要问题包括：CLI/TUI 绕过 Python `SessionClientRuntime`、TUI 使用硬编码的
permission/user-input 形状、GUI 仍解析 `last_error` 而 Host session snapshot 已发送
`last_failure`、GUI activation 静默吞 bootstrap 错误，以及 WebSocket sink 不传播发布失败。
这些问题不是某一个 shell 的 UI bug，而是公共前端协议和所有权没有完全落地。

## 决策

采用一次有意的 pre-release wire contract v2 迁移，不保留旧字段兼容别名或并行 facade：

1. `FailureRecord` 是 CLI、TUI、GUI 的唯一公开失败结构。app/session snapshot、HTTP error、
   WebSocket failure 和 CLI exit status 都从该结构派生；wire 层删除 `last_error`，统一为
   `last_failure: FailureRecord | null`。
2. Python 与 JavaScript `SessionClientRuntime` 是各自 transport 下唯一的 session
   synchronization owner。CLI session commands 不得直接访问 `session_port`；shell 不得以
   本地 projection 的 session id 代替 runtime active id。
3. permission 和 user-input 使用规范化的 `InteractionProjection` 与 descriptor-backed
   response。所有 shell 只依赖最小公共字段（interaction id、turn id、renderer、response
   lifecycle）；choices、questions、defaults 和 workflow-specific data 由命名空间化
   descriptor 描述，不能把某个 shell 或工作流的私有结构写进共享 runtime。
4. WebSocket 只接受经过 strict `SessionEventEnvelope` normalizer 的消息；event sink 发布
   失败必须传播给 Host/runtime，不能记录后当作成功。workspace 切换使用独立的 app-level
   `workspace_changed` notification，不伪装成 session event。
5. Host generic runtime 接收产品组合显式创建、且只满足 focused port/interface 的 model、
   tool、context 和 permission collaborators；Host 不依赖这些 collaborator 的具体实现，
   也不构造默认 provider。该迁移与 shell 协议迁移在同一个收敛计划中完成。
6. 必要耦合只存在于稳定 DTO、focused port、生命周期和 capability key；shell renderer、
   workflow implementation、provider SDK、Host concrete class 和 application registry
   不得进入公共 runtime。可替换实现通过 descriptor registry、capability contribution 和
   可撤销 `RegistrationScope` 接入，并以 fake port/provider contract tests 验证替换性。
7. 所有旧路径直接删除。不会添加 `last_error` alias、port forwarding facade、第三套
   runtime、shell-specific interaction fallback 或从异常文本恢复分类的兼容层。

## 形式化不变量

实现必须用 contract/property tests 证明以下不变量：

- **Failure uniqueness**：任意公开失败只能携带一个 `FailureRecord`；shell 不通过异常文本
  推导 `code`，也不向 wire/diagnostics 写入 raw exception text。
- **Runtime ownership**：一次 bootstrap-producing operation 只有一个 runtime generation；
  active session id、event cursor、pending interaction 和 terminal outcome 只能由 runtime
  提交。sink 回调中的新操作必须排队到当前 publication 提交之后。
- **Interaction lifecycle**：request 进入 `blocked`；成功 response 或 response failure
  都必须产生终态；同一 `interaction_id` 不得被重复提交。
- **Envelope integrity**：进入 runtime 的 session event 必须是 schema v2、严格 snake_case、
  canonical envelope；sequence gap 只能通过同一 recovery transaction 修复。
- **Workspace isolation**：workspace change 只更新 app-level shell state，不改变 session
  ledger 或伪造 session event。
- **Composition closure**：Host runtime 的 model/tool/context/permission collaborators
  必须由 selected product contribution 显式提供，缺失时产生 typed `configuration_error`。
- **Substitutability**：runtime contract tests 使用 fake transport、fake provider 和 fake
  renderer 即可通过；任何具体 Host、shell toolkit 或 provider SDK 都不能成为 runtime 的
  必需依赖。

## 影响

收益：三端的失败展示、退出码、interaction response、恢复和关闭行为可由同一组 fixtures
验证；shell 不再拥有 session truth；GUI/WebSocket 丢事件和 TUI stale-session race 可以在
runtime 层被拒绝；Host/Application 的组合边界与 Phase 4 的显式贡献模型一致；具体 shell、
provider 和 workflow 可以在不修改 runtime 的情况下替换。

代价：这是 breaking migration，需要同步更新 Python/JavaScript DTO、fixture、CLI/TUI/GUI
测试和 protocol schema；旧的 `last_error` fixture、direct port command 和硬编码 interaction
输入必须删除，而不是保留一段过渡期。

风险：WebSocket sink 传播失败后，Host 已分配的 event sequence 不能回滚，因此 recovery 必须
依赖 canonical cursor/bootstrap；workspace notification 增加 app-level DTO，需要单独的严格
normalizer 和连接关闭测试。过度收敛 descriptor 也可能把未来 capability 锁死，因此公共
字段保持最小化，扩展数据必须使用版本化命名空间，而不是继续扩张核心 DTO。

## 备选方案

### 保留 `last_error` 并新增 `last_failure`

拒绝。双字段会让不同 shell 继续选择不同真相，并把迁移债务永久化。

### 每个 shell 自己修复

拒绝。失败映射、interaction 和 session ownership 属于公共 runtime/protocol contract，
分 shell 修复会重新产生 drift。

### 新增一个跨 transport 的 HostedFrontendRuntime

拒绝。它会成为第四个近似 runtime facade，隐藏而不是消除 Python/JavaScript 的重复职责，
也会扩大 Host 的公共边界。

## 验收边界

实现完成前必须同时满足：

- 共享 Python/JavaScript contract fixtures 覆盖 failure、activation、interaction、
  response failure、sequence recovery、workspace change、reentrancy 和 close；
- architecture guards 拒绝 `last_error` wire key、CLI direct `session_port`、shell raw
  `str(exc)` diagnostics、静默 activation failure 和 Host 默认 provider construction；
- CLI、TUI、GUI focused tests、GUI webapp build/test、完整 Python partition、lint 和受影响
  的 distribution gates 全部通过；
- 当前平台 authority 在实现合入后同步为 v2 行为，临时设计切片随后归档。
