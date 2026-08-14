# Frontend Protocol

## Metadata

> 状态：`active`
> 类型：`platform contract`
> 负责人：`Agent platform maintainers`
> 最后同步日期：`2026-08-14`
> 对应代码范围：`packages/embedagent-protocol/src/embedagent_protocol/`, `packages/embedagent-host/src/embedagent_host/frontend_ports.py`, `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`, `src/embedagent/frontend/runtime/`, `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js`

## 1. Truth Layers

| Layer | Purpose | Truth rule |
|---|---|---|
| app bootstrap | 产品名、workspace registry、commands、surfaces、shell diagnostics | shell metadata，不是 session truth |
| session bootstrap | 激活 session，返回 thread、snapshot、history、capabilities、integrity 和 `event_cursor` | transcript-backed frozen projection；cursor 由 Host live stream 拥有 |
| session event stream | 运行中增量事件 | 只能通过 canonical `SessionEventEnvelope` |

前端 local state 只拥有布局、选中、draft、scroll、request-in-flight 和其他可丢失展示状态。它不拥有 session history、workflow、permission、tool activation、capability availability 或 restore policy。

## 2. Client Runtime Contract

所有 shell 遵守同一个 observable session state machine，但不共享 transport-specific executable code：

| Shell | Session synchronization owner | Transport / outer runtime |
|---|---|---|
| CLI | Python `SessionClientRuntime` | 进程内 `FrontendSessionPort`；CLI renderer 只消费 `RuntimeAction` |
| TUI | Python `SessionClientRuntime` | 进程内 `FrontendSessionPort`，另持有聚焦 `FrontendWorkspacePort` |
| GUI | JavaScript `SessionClientRuntime` | HTTP/WebSocket protocol adapter；browser-only controllers 由 `BrowserAppRuntime` 组合 |

两个 `SessionClientRuntime` 都拥有 active session id、generation、bootstrap buffer、Host cursor、duplicate/gap handling、一次 recovery、interaction lifecycle、terminal outcome 和 close。`BrowserAppRuntime` 额外拥有 workspace、terminal、preview、source-control、dialog 和 browser transport controllers；这些不是跨 shell runtime 合同。

Python 与 JavaScript 实现由 `tests/fixtures/session_client_runtime/contract.json` 的同一组 credential-free cases 验证。不得新增 direct endpoint helper、port/adapter 逃逸、三参数 callback、shell-local history loader 或第三套 session runtime。

## 3. Canonical Event Envelope

`SessionEventEnvelope` 包含 `schema_version`, `event_id`, `session_id`, positive `sequence`, `event_kind`, `timestamp` 和 JSON-safe `payload`。Host `SessionEventEncoder` 为一次 live change 创建一次 envelope；in-process sink 或 WebSocket bridge 原样转发，renderer transport 只有一个 `session_event` 分支。

主要 event families：

- turn/step lifecycle；
- assistant/reasoning/thinking stream；
- tool started/finished/progress；
- approval/user-input requested/resolved/response-failed；
- session status/finished/error；
- context compaction、command result、plan update 及其他 declared hosted events。

前端不设置 per-event callbacks，也不把 backend event kinds 翻译成第二套协议。schema version 是 wire compatibility 标识，不是迁移标签。

## 4. Activation, Ordering And Recovery

GUI 的 `/api/sessions/{id}/bootstrap` 与 Python runtime 的 `FrontendSessionPort.get_session_bootstrap(...)` 返回同一个 `SessionBootstrap` shape：thread、frozen snapshot、`history.activities`、integrity、capabilities、permission context 和 non-negative `event_cursor`。

runtime 在请求 bootstrap 前创建新 generation，并缓冲该 session 的 live envelopes。安装时以 `event_cursor` 为唯一基线，丢弃不高于 cursor 的 envelope，再按 sequence 应用连续事件。duplicate 被忽略；sequence gap 只启动当前 generation 的一次 bootstrap recovery。旧 generation、其他 session、close 后或 late async completion 都不能写回 state。

Host 在一个 per-session event publication 同步边界内捕获 projection 与 cursor，因此事件只能完整位于 bootstrap 之前或之后。serializer 和 shell 不维护第二个 sequence counter。renderer 不从 event tail 或 local timeline 重建 history。

## 5. Capabilities And Descriptor Dispatch

`CapabilitySnapshot` 投影 modes、commands、tool presentation、workflow packages、agent applications、resources、model profiles 和 empty state。app bootstrap 携带 product-compiled `ShellDescriptor`。

shell 从 descriptor/capabilities 计算 command 可用性、label、order、dispatch 和 renderer key；不得以 application id、workflow type 或 tool name 分支重建 policy。CLI 与 TUI 的通用 descriptor command dispatch 位于 Python runtime，GUI 的等价 dispatch 位于 JavaScript runtime。renderer registry 只声明本 shell 支持的展示实现，不是 capability source。

## 6. Generic Workflow Projection

`SessionSnapshot.workflow_state` 是通用、命名空间可扩展的读模型容器。shell 可以通过已注册 renderer 显示 `workflow_state["workflow"]`，但不解释应用内部类型或推进其状态。新应用通过 workflow projection 与 descriptors 参与，协议不硬编码专有词汇。

## 7. Interactions And Terminal Outcomes

permission 与 user-input request payload 共享 stable `interaction_id`、`turn_id` 和请求细节。shell 调用 `respond_to_interaction(...)` 后，Host 原子 claim 交互；resolved event 或后续 bootstrap/snapshot 清除 pending state。前端的 duplicate-submit 防护不能替代 Host claim。

Client runtime 把 interaction request 暴露为 `blocked` terminal outcome。交互式 shell 可以继续收集响应并 resume；one-shot client 必须返回结构化 `interaction_required`，不能隐式批准、猜测输入或长期持有 Agent 状态。

## 8. Failure And Diagnostics

Host/port failure 通过 `FailureRecord(code, message, retryable, source)` 传递。CLI 只按封闭 code 映射稳定 exit status；GUI/TUI 只渲染结构化失败。协议不发送 full prompt、source contents、raw tool output、API key、approval secret、permission payload 或 token 到 telemetry/diagnostics。

tool catalog 拥有 permission category、preview/changed-path metadata、read-model invalidations 和 provenance。前端只投影这些字段，不按 tool name 猜测。tool/activity identity 使用 engine-issued `turn_id`, `step_id`, `step_index`, `call_id`。

## 9. Verification

- `tests/test_session_client_runtime_contract.py`
- `tests/test_host_frontend_ports.py`
- `tests/test_session_event_protocol.py`
- `tests/test_cli_chat.py`
- `tests/test_terminal_frontend.py`
- `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/protocol-adapter.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs`

## 10. Related Documents

- `docs/platform/protocol.md`
- `docs/platform/session-runtime.md`
- `docs/platform/frontend-gui.md`
- `docs/platform/frontend-tui.md`
- `docs/product/composition.md`
