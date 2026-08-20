# Frontend Contract v2 Design

> 状态：`proposed`
> 类型：设计切片（实现前审阅）
> 关联 ADR：`docs/adrs/0010-frontend-contract-cross-shell-convergence.md`

## 目标

让 CLI、TUI、GUI 对同一 hosted session 呈现同一套可观察行为：失败分类一致、runtime
拥有 session truth、interaction descriptor 可执行、事件顺序可恢复、workspace 切换不污染
session ledger。实现采用 breaking pre-release migration，不建立兼容双轨，同时把耦合限制在
协议和 focused ports，不把具体 shell、Host、provider 或 workflow 实现带入共享 runtime。

## 当前证据

- `src/embedagent/cli/app.py` 和 `src/embedagent/frontend/tui/launcher.py` 仍在 shell 层
  重新分类或输出异常。
- `src/embedagent/cli/sessions.py` 直接读取 `session_port`。
- `src/embedagent/frontend/tui/controller.py` 使用本地 session id、硬编码 y/n 和 answer
  payload，且没有 descriptor-backed interaction dispatch。
- `src/embedagent/frontend/runtime/session_client_runtime.py` 的 activation failure 会被
  转换为 `None`；同步 sink 回调还可能重入 publication。
- Host session snapshot 已发送 `last_failure`，GUI normalizer/state helper 仍使用
  `last_error`。
- GUI WebSocket bridge 不强制 strict envelope，也不把 sink/broadcast failure 传播给发布者。
- `packages/embedagent-host/src/embedagent_host/hosted/runtime.py` 仍在 generic Host 内部
  创建 model/tool/context/permission collaborators。

## 目标 DTO

### FailureRecord

所有公开失败只携带 `code`, `message`/`safe_message`, `retryable`, `source`, `phase`,
`kind`, `correlation_id` 和 allowlisted exception type。wire 和 diagnostics 禁止 raw
exception text、prompt、source、tool output、credential 和 approval secret。

### Session snapshot

用 `last_failure: FailureRecord | null` 替代 `last_error`。Python serializer、Python runtime、
JavaScript normalizer/reducer 和所有 fixtures 同步删除旧字段。

### InteractionProjection

Host normalization 后，顶层只包含稳定公共字段 `kind`, `interaction_id`, `turn_id`,
`renderer` 和 versioned `descriptor`。内置 permission/user-input descriptor 可以提供
choices/default/question(s)/answer key，但这些字段位于 descriptor 命名空间；未来 capability
可以注册不同 descriptor，而不修改 runtime 状态机。shell 只消费 descriptor contract，不
解释 Host 私有 payload。

### App shell notification

workspace 切换使用独立的 `workspace_changed` DTO。它不进入 session event sequence，不写入
session ledger，不改变 session runtime cursor。

## 运行时状态机调整

1. 所有 bootstrap-producing operation 先创建 generation，再请求 port/transport。
2. runtime 在 sink 回调期间收到的新操作进入 deferred queue，当前 event publication 提交
   cursor、pending interaction 和 terminal outcome 后才执行。
3. activation/bootstrap 错误通过 `FailureRecord` 返回或 dispatch `protocol_failed`，禁止
   `None` 表示失败。
4. interaction response 必须使用 runtime active session 和当前 generation；duplicate 或
   stale response 在 runtime 层拒绝。
5. close 进入不可复用终态，关闭后忽略晚到 event，所有 shell 直接委托 runtime close。

## Shell 迁移边界

### CLI

- session list/summary/rename/archive/fork 全部迁移到 Python runtime。
- `protocol_failed` 使用 `exit_code_for_failure(failure.code)`。
- `ApplicationConfigurationError` 保留 typed failure metadata。
- CLI command descriptor 增加 interaction response 的明确执行路径。

### TUI

- `TerminalState` 增加 capability/interaction projection，renderer 由 descriptor registry
  选择。
- pending interaction 使用规范化顶层 `kind`，支持 descriptor choices/default/question id
  和 response failure。
- submit/respond 不再读取本地 projected session id。
- availability/when 在 palette/keybinding projection 阶段计算。
- 所有错误转为 safe `FailureRecord`；直接 `run_tui()` 和 launcher 都保证 runtime close。

### GUI

- session normalizer/reducer 全面迁移到 `last_failure`。
- WebSocket 所有 inbound data 经过 strict envelope normalizer；dispatch/broadcast failure
  传播到 Host/runtime。
- `activateSession` 不再 blanket catch；BrowserAppRuntime 显式显示结构化失败。
- workspace activation 广播 `workspace_changed`，并由 browser app runtime 处理。
- HTTP errors 返回完整 FailureRecord JSON，而非只返回 status/detail。

### Product/Host

- `create_generic_hosted_runtime` 改为接收显式 model/tool/context/permission focused ports。
- 产品组合负责构造并绑定这些 ports；Host 只依赖 interface/Protocol，不依赖 collaborator
  concrete class。缺失或不匹配时返回 typed `configuration_error`。
- Host 不再创建默认 provider，不添加 forwarding facade。

## 耦合预算与可替换性

### 必要耦合

- Protocol DTO、schema version、FailureRecord、canonical session envelope；
- SessionClientRuntime 的 generation/cursor/interaction/close 状态机；
- focused ports 和 capability keys；
- descriptor registry 的 renderer/dispatch contract。

这些是跨实现必须一致的可执行契约，使用 shared fixtures 和 property tests 验证。

### 禁止耦合

- runtime import 具体 Host adapter、OpenAI/provider SDK、prompt_toolkit、React 或 pywebview；
- TUI/GUI 根据 workflow name、application id 或 tool name 重建 policy；
- interaction projection 暴露 Host 私有对象或 workflow 私有 DTO；
- 为了复用而增加 aggregate service、callback bag、forwarding facade 或第三套 runtime。

### 插件替换方式

具体 provider、renderer、command 和 workflow capability 通过 manifest-gated contribution、
descriptor registry 和 `RegistrationScope` 注册，注册返回可幂等 disposer。替换实现只需满足
focused port 与 descriptor contract；测试使用 fake implementation 验证 runtime 不依赖具体类。

## 删除项

- wire `last_error` 及其所有 JS/Python aliases、fixture 和 reducer 字段；
- CLI `context.session_port` command escape；
- TUI y/n、固定 `answer` key 和 raw exception presentation；
- runtime activation 的 silent `None` failure；
- GUI WebSocket permissive envelope bypass；
- Host generic provider construction fallback；
- 为保留旧行为而新增的 adapter、facade、双写字段或 message-text classifier。
- 将 concrete provider、shell renderer 或 workflow state 作为 shared runtime 的新依赖。

## 验收用例

共享 fixture 至少覆盖：

1. typed configuration/provider/cancelled/interaction failures 及 CLI exit mapping；
2. Python/JavaScript activation、generation rollback、cursor gap recovery 和 close；
3. nested interaction payload、descriptor choices/default/question id、response failure 和
   duplicate response；
4. sink failure propagation、strict WebSocket envelope 和 workspace notification；
5. runtime sink 回调重入、TUI late event 和 direct close；
6. explicit product provider composition 以及缺失 collaborator 的 configuration error。
7. fake transport/provider/renderer 替换 concrete implementation 后，runtime contract 仍全部通过。

## 审阅后下一步

设计获确认后，另行生成实现 plan，按 runtime/protocol、CLI/TUI、GUI、Host composition 和
architecture gates 分阶段执行。实现合入后同步三个 frontend authority，再归档本切片。
