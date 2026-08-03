# Frontend Protocol

## Metadata

> 状态：`active`
> 类型：`platform contract`
> 负责人：`Agent platform maintainers`
> 最后同步日期：`2026-08-03`
> 对应代码范围：`packages/embedagent-protocol/src/embedagent_protocol/`, `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`, `src/embedagent/core/adapter.py`, `src/embedagent/frontend/`

## 1. Truth Layers

前端协议有三个明确层次：

| Layer | Purpose | Truth rule |
|---|---|---|
| app bootstrap | 产品名、workspace registry、commands、surfaces、shell diagnostics | 只是 shell metadata，不是 session truth |
| session bootstrap | 激活 session id，返回 thread、snapshot、history、capabilities、workflow、integrity | 来自 transcript-backed hosted projection |
| session event stream | 运行中增量事件 | 只能通过 canonical `SessionEventEnvelope` |

前端 local state 只拥有布局、选中、折叠、draft、scroll 和输入中交互等展示状态。它不拥有 session history、workflow、permission、tool activation、capability availability 或 restore policy。

## 2. Canonical Event Envelope

`SessionEventEnvelope` 字段：

- `schema_version`；
- `event_id`；
- `session_id`；
- positive `sequence`；
- `event_kind`；
- `timestamp`；
- JSON-safe `payload`。

Host `SessionEventEncoder` 为一次 live change 创建一个 envelope，Core adapter、WebSocket bridge 和 shell 逐层原样转发；renderer transport 只有一个 `session_event` 分支。前端不设置 per-event callbacks，不将后端 event kinds 翻译为第二套协议。

主要 event families：

- turn/step lifecycle；
- assistant/reasoning/thinking stream；
- tool started/finished/progress；
- approval/user-input requested/resolved/response-failed；
- session status/finished/error；
- context compaction、command result、plan update 及其他 declared hosted events。

schema version 是实际 wire compatibility 标识，不是文档或架构命名。

## 3. Session Bootstrap

`/api/sessions/{id}/bootstrap` 是前端激活 session 的正式路径。响应至少包含：

- thread shell metadata；
- frozen session snapshot；
- `history.activities` 和 integrity summary；
- session capability snapshot；
- generic `workflow` projection。

`SessionHistoryAssembler` 拥有 history DTO 序列化，`SessionSnapshotProjector` 拥有 snapshot。GUI/TUI 不从 replay tail、app bootstrap 或自己保存的 timeline 重建 session。

当前 bootstrap 尚未携带 event cursor，因此 GUI 在 sequence gap 后无法原子确定 snapshot 对应的 live high-water mark。收敛切片将把 `event_cursor` 加入当前 schema，并在同一变更中切换全部消费者、删除旧 schema；切换完成前不得宣称 gap recovery 已闭合。

## 4. Capabilities And Registries

`CapabilitySnapshot` 可投影：

- modes；
- commands；
- tool presentation metadata；
- workflow package descriptors；
- active/available agent application descriptors；
- local resources；
- model profiles；
- empty-state metadata。

app bootstrap 可声明 surfaces、commands 和 workspace state。shell 必须从 descriptor/capability registry 计算可见性、标签、排序、dispatch 和 renderer key；不以产品名、应用 id、工具名或 command id 分支重建 backend policy。

renderer-local registry 只声明当前 shell 支持哪些通用 component/handler/renderer kinds。它是展示实现表，不是 capability source。未支持的 descriptor 必须显式隐藏并产生受控 diagnostics，不得以 generic fallback 补入未注册的应用能力。

## 5. Generic Workflow Projection

`workflow` 是通用、命名空间可扩展的读模型。shell 可显示 summary、items、activity 和 metadata，但不解释上层应用内部类或在前端推进状态。新应用通过 backend projection 和 descriptors 参与，不要求协议硬编码其专有词汇。

## 6. Interactions

permission 和 user-input request payload 共享 stable `request_id` / `interaction_id`, `turn_id` 及请求细节。shell 调用 `respond_to_interaction(...)` 后，Host 原子 claim 该交互并返回 acknowledgement。只有 resolved event 和后续 session snapshot 能清除 pending interaction。

前端必须防止同一 request 重复提交，但该本地防护不代替 Host claim。response-failed 事件应恢复可操作状态或显示后端错误，不假设 action 已执行。

## 7. Tool Presentation And Refresh

tool catalog 提供 label、permission category、renderer keys、preview/changed-path metadata 和 provenance。timeline 只按这些字段展示，不按 tool name 猜测。`read_model_invalidations` 可请求 shell 刷新 workspace files、capabilities 等读模型，但不能改变工具、权限或 workflow。

tool/activity identity 使用 engine-issued `turn_id`, `step_id`, `step_index`, `call_id`。前端不 mint 替代 identity。

## 8. Failure And Diagnostics

tool failure 可携带 `FailureRecord(code, message, retryable, source)`。runtime config、compaction、recovery、turn experience、extension diagnostics 和 integrity 都是读模型，仅用于恢复/调试可见性。它们不是 active-tool、permission、context selection、extension loading 或 history authority。

协议不发送 full prompt、skill/prompt body、source contents、raw tool output、API key、approval secret 或 permission token。

## 9. Verification

- `tests/test_session_event_protocol.py`
- `tests/test_inprocess_adapter_frontend_api.py`
- `tests/test_gui_sync.py`
- `tests/test_gui_backend_api.py`
- `tests/test_terminal_frontend.py`
- `src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs`
- `src/embedagent/frontend/gui/webapp/test/protocol-adapter.test.mjs`

## 10. Related Documents

- `docs/platform/protocol.md`
- `docs/platform/session-runtime.md`
- `docs/platform/tool-contracts.md`
- `docs/platform/frontend-gui.md`
- `docs/platform/frontend-tui.md`
