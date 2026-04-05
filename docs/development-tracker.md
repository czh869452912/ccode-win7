# EmbedAgent 开发进度跟踪

> 更新日期：2026-04-05（Transcript-truth tool-result cutover + single-writer commit + SQLite projection cutover）
> 用途：持续跟踪当前阶段、下一步任务、里程碑进度、风险与阻塞

---

## 1. 使用规则

本文件用于回答四个问题：

1. 当前做到哪一步了？
2. 下一步最应该做什么？
3. 哪些任务已经完成，哪些仍在阻塞？
4. 当前有哪些风险需要被持续关注？

更新规则：

- 每完成一个里程碑或子里程碑，更新本文件
- 每次重要设计变更，同时检查是否需要同步本文件
- 当前只保留“近期最重要”的 5-10 项任务，不把它写成无限 backlog

---

## 2. 当前阶段

### 总阶段

- 当前阶段：`Phase 4 真实工程验证 + Phase 6 GUI / Win7 收口`
- 总体状态：`进行中`
- 当前重点：`Phase 4 默认 recipe/真实工程/Win7 验证，Phase 6 GUI / Win7 收口，以及 transcript-truth cutover 后的 regression/文档收口；Phase 7 继续推进 package.ps1 控制面后的 site-packages 精简与 Win7 bundle 验收`

### 当前判断

项目已经完成：

- 范围和目标收敛
- 参考项目分析
- 总体方案设计
- 实施路线与文档治理基线
- 项目级 `AGENTS.md`
- Python 3.8 / `uv` / `conda` 版本策略落盘
- 工具设计规范 `docs/tool-design-spec.md`（DC-004）
- 实施分期重组（DC-005）：关键路径前移，Phase 1 = 最小可工作 Loop
- Phase 1 最小原型代码骨架（`src/embedagent/`）
- 本地闭环自测：工具调用、Observation 回注、CLI 启动、语法编译
- Python 3.8.10 `uv` 环境验证通过（`.venv`）
- Moonshot `kimi-k2.5` 真实联调已跑通最小工具闭环（需使用 `/v1`，并保留 `reasoning_content`）
- `docs/llm-adapter.md` 已建立，记录已验证 provider 兼容点
- Phase 2 工具核心实现已落地：`run_command`、`git_status`、`git_diff`、`git_log`
- `docs/tool-contracts.md` 已建立，记录当前工具接口契约
- Phase 2 Loop 烟雾验证通过：`run_command` 与 `git_status` 已通过主循环消费验证
- Phase 3 模式系统 v2 已落地：5 模式配置驱动（`explore`/`spec`/`code`/`debug`/`verify`）、`initialize_modes`、工具过滤、`/mode`；`switch_mode` LLM 工具已移除
- `docs/mode-schema.md` 与 `docs/harness-state-machine.md` 已建立
- Phase 3 验证通过：模式切换、违规工具拦截、写入范围拦截均已完成本地验证
- Phase 4 工具第一版已落地：`compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
- `docs/clang-integration-plan.md` 已建立
- Phase 4 解析验证通过：编译诊断、测试汇总、覆盖率提取、质量门评估均已完成本地验证
- 项目内闭环 Clang 工具链已落地到 `toolchains/llvm/current`
- 已完成真实本地 smoke test：编译、analyze、clang-tidy、profdata、llvm-cov report
- Phase 5 最小权限模型已落地：CLI 可对写入和命令执行做确认
- Doom Loop Guard 已落地：连续失败和重复失败动作会触发防护
- `docs/permission-model.md` 已建立
- `docs/context-management-design.md` 已建立
- Phase 5 第一版上下文管理已落地：旧 turn 摘要化、Observation 遮蔽化、最近 turn 保真化
- Phase 5A 上下文预算器已接入：按 mode 分配预算并为输出/推理预留空间
- Phase 5A ReducerRegistry 已落地：不同工具按类型裁剪 Observation，并返回 ContextStats / BudgetEstimate
- transcript-truth tool-result cutover 已落地：`ArtifactStore` 与共享 `artifacts/index.json` 已从运行时热路径移除，长文本结果现在由 `ToolCommitCoordinator` 串行落到 `.embedagent/memory/sessions/<session_id>/tool-results/<tool_call_id>/...`，Observation 使用 `*_stored_path`
- Phase 5C Session Summary Store 已落地：会话关键状态会持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
- Phase 5D Project Memory Store 已落地：项目级 profile / recipe / known issue 已可落盘并注入上下文
- Phase 5E Resume Entry 已落地：CLI 已支持 `--list-sessions` 与 `--resume <session_id|latest|summary.json>`
- Phase 5F / Query cutover memory maintenance 已收口：tool-result cleanup 已改为基于 session-local stored paths，artifact browse/session summary/project memory 的可查询投影已切到 SQLite
- Phase 5 长任务稳定性验证已完成：`scripts/validate-phase5.py` 已在修复根目录文件写入边界后重新跑通
- Phase 5 权限细化已完成：已支持规则文件、allow / ask / deny、路径与命令模式匹配
- Query / Context 重构切片已启动：`session.py` 已补齐 transcript/event 数据模型，`query_engine.py` 已成为新主循环骨架，`loop.py` 已退化为兼容入口
- `ContextManager.build_messages(...)` 已开始接入 workspace intelligence、tool result replacement、duplicate suppression、activity folding 与 compact boundary 复用
- `workspace_intelligence.py`、`tool_execution.py` 与 `tests/test_query_engine_refactor.py` 已落地；新测试已覆盖 pending interaction resume、tool batch partition、intelligence/boundary 注入
- `DiagnosticsProvider` 已升级为工作集优先的文件级热点聚合：同一文件上的 compile/tidy/analyzer 诊断会折叠为单条热点证据，最近编辑/读取文件优先于被动报错文件
- `DiagnosticsProvider` 已继续推进第二段：`verify` 模式下会把 `report_quality`、`run_tests`、`collect_coverage` 等无路径失败聚成一条 quality gate summary，避免质量门信息只剩零散 observation
- `RecipeProvider` 已继续推进第二段：当前会按 mode 区分 `project / history / detected` recipe 来源优先级，并把 `stage` 作为细粒度 tie-break；`code` 模式更偏 project/detected build，`verify` 模式更偏 project/history test
- `QueryEngine` 已具备第一版 reactive compact retry：当模型明确报出 prompt/context 过长时，会记录 `compact_retry` transition、复用 compact boundary，并以内部 compact policy 自动重试一次
- `compact_retry` 现在已对前端可观测：snapshot 暴露最近 transition reasons / compact retry 次数，timeline 也会记录 `compact_retry` event
- `build_structured_timeline()` 现在也保留 turn/step 级 transitions，`compact_retry` 不再只存在于 raw timeline event
- `build_structured_timeline()` 也开始保留 `user_input_required / permission_required` 等等待态 transition，并把 turn 状态同步为 waiting 态
- `turn_end` 的非完成终止态也开始进入 structured timeline transitions，当前已覆盖 `max_turns`
- 终止态 transition 现在会携带停止原因文本，structured timeline 不再只暴露终止类型
- `SessionSnapshot` 也开始保留 `last_transition_message`，并在会话结束后重持久化最终状态，避免末尾 transition 丢失
- `SessionSnapshot` 现在还会暴露结构化 `recent_transitions`，前端可直接查看最近几条状态迁移及其 `reason / message / display_reason`
- `SessionSnapshot` 还补了 `last_transition_display_reason`，前端可直接消费用户语义层的状态名称；历史 summary 缺失 `display_reason` 时也会在读取 snapshot 时即时补齐
- structured timeline 的 transition 也开始带 `display_reason`，等待态与终止态都能直接映射到 GUI 友好的状态语义
- GUI inspector 现在已开始直接消费 `last_transition_display_reason / last_transition_message / recent_transitions`，Runtime 面板不再只依赖内部 termination reason
- GUI webapp 本地验证链已补齐第一段：`build.mjs` 依赖的 `esbuild` 现在已声明为显式 `devDependency`，并新增根目录 `run-local-tests.mjs` 作为本地 test runner；当前已验证 `node .\\run-local-tests.mjs` 与 `npm run build`
- resume consistency 已切到 transcript-truth 语义：新增 `transcript_store.py`、`session_restore.py`，`resume_session()` 已从 transcript replay 恢复 `Session`，`summary.json` 不再作为恢复真相源
- single-writer commit 已落地：工具线程只返回 raw observation，`ToolCommitCoordinator` 统一负责 tool-result 落盘、`tool_result` / `content_replacement` transcript append 与 SQLite projection 更新，并确保 projection 失败不会反向把 tool success 改成失败
- transcript hardening 已推进一段：`TranscriptStore.append_event()` 现已按 transcript 文件串行化写入，避免并发 append 时 `seq` 竞争与 JSONL 尾部截断放大
- transcript 损坏恢复已推进一段：`TranscriptStore.load_events()` 现在会在 `seq` 跳号/乱序时停止读取；`append_event()` 追加前会截断损坏尾部，避免“坏尾后新事件永久不可见”
- transcript 消息因果链已推进一段：`TranscriptMessage` 与 transcript `message/tool_result` 事件现在会显式写入 `parent_message_id`，`SessionRestorer` 在提供父引用时也会验证其存在，resume 不再只依赖“当前顺序碰巧正确”
- restore 因果校验已推进一段：`SessionRestorer` 现在在 `tool_result` 缺少前置 `tool_call`、或 `pending_resolution` 缺少前置 `pending_interaction` 时停止回放，避免 malformed transcript 被静默脑补成合法状态
- restore 顺序校验已继续推进：`SessionRestorer` 现在在 `step_started` 缺少 user turn、`tool_call` 缺少 active step，或 replay 事件引用了错误的 `turn_id / step_id` 时停止回放，避免恢复链凭空补造空 turn / 空 step，或把事件静默挂到错误的活动节点上
- compact boundary replay 已继续推进：`SessionRestorer` 现在会校验 `preserved_head_message_id / preserved_tail_message_id` 是否存在且顺序正确；同时 `QueryEngine` 会在 transcript 缺失时先 bootstrap 现有内存 session 的 message / compact boundary 历史，避免新 boundary 引用了 transcript 里不存在的旧消息
- compact boundary 写入策略已继续收口：同一 step 在 `compact_retry` 前后现在只会落一条有效 `compact_boundary`，避免把“摘要套摘要”再次写回 transcript，导致 restore 后边界漂移
- message replay 边界已继续推进：`SessionRestorer` 现在会拒绝错误 `turn_id` 的 `assistant/tool` message，并在已有 active step 时校验其 `step_id`；同时保留对旧 transcript 的兼容入口，允许“未显式落 `step_started` 的 assistant/tool message”作为建步前缀继续恢复
- transcript 引用 ID 校验已继续推进：`SessionRestorer` 现在会在出现重复 `message_id` 或重复 `tool_call.call_id` 时停止回放，避免 compact boundary、content replacement 和 tool topology 的引用目标变得不唯一
- pending resolution replay 已继续推进：`SessionRestorer` 现在会校验 `pending_resolution` 的 `turn_id / step_id` 是否仍然指向当前活动节点，避免错误 resolution 把真正的 pending 状态提前清掉
- pending resolution 引用一致性已继续推进：`SessionRestorer` 现在还会校验 `pending_resolution` 的 `interaction_id / tool_name / kind` 是否匹配当前 pending interaction，避免“指向别的等待态”的 resolution 被错误消费
- tool result replay 已继续推进：`SessionRestorer` 现在会校验 `tool_result` 的 `tool_name`，以及显式提供时的 `arguments`，是否与前置 `tool_call` 记录一致，避免仅凭 `call_id` 就把错误结果挂到现有 tool call 上
- content replacement replay 已继续推进：`SessionRestorer` 现在会校验 `content_replacement` 必须指向一个已恢复的 `tool` message，且其 `tool_call_id / tool_name` 不得与目标消息冲突，避免错误 replacement 文案污染后续上下文组装
- restore 诊断性已推进一段：`SessionRestoreResult` 现在会暴露 `consumed_event_count` 与 `stop_reason`，上层可以区分“完整恢复”与“在某个校验点停在自洽前缀”
- restore 诊断透传已推进一段：`resume_session()` / session snapshot 现在会把 `restore_stop_reason / restore_consumed_event_count / restore_transcript_event_count` 透出给 adapter 上层，恢复截断不再只能靠日志推断
- step / pending identity 唯一性已继续推进：`SessionRestorer` 现在会在出现重复 `step_id` 或重复 `pending_interaction.interaction_id` 时停止回放，避免后续事件挂接到不唯一的活动节点
- turn identity 唯一性已继续推进：`SessionRestorer` 现在会在 replay 新 `user` message 时校验 `turn_id` 唯一性，避免 turn 级投影和后续 transition/pending 挂接重新出现歧义
- compact boundary identity 唯一性已继续推进：`SessionRestorer` 现在会在出现重复 `compact_boundary.boundary_id` 时停止回放，避免前端或恢复链把两个不同摘要边界当成同一个历史切点
- tool result message identity 已继续推进：`SessionRestorer` 现在会把 `tool_result.message_id` 也纳入唯一性校验，避免 tool result 与既有 message 共享同一引用目标
- compact / resume replay 已推进一段：`compact_boundary` 现在会显式写入 transcript，并补齐 `preserved_head_message_id / preserved_tail_message_id`，`SessionRestorer` 已可回放 compact 边界而不丢失 preserved segment 元数据
- pending interaction replay 已推进一段：`resume_pending()` 现在会把 `pending_resolution` 与恢复阶段生成的 `tool_result` 一并落入 transcript，恢复后的 tool call 状态不再卡在 `pending`
- tool interrupt / retry 已推进第一段：`tool_started` 之后若会话被取消，`QueryEngine` 现在会写入 synthetic interrupted tool_result，并在 transcript / timeline / adapter `tool_finished` 事件中统一表现为 aborted
- tool interrupt / retry 已继续推进第二段：parallel batch 中的 `discarded` synthetic result 仍会进 transcript，但不再误计入 `LoopGuard` 导致整轮提前 `guard_stop`
- tool interrupt / retry 已继续推进第三段：`StreamingToolExecutor` 并行批次已改成流式 start/result，`max_parallel_tools=1` 场景下现在能稳定落下“首个 action interrupted、后续未开始 action discarded”的 transcript 语义
- tool interrupt / retry 已继续推进第四段：`tool_call` transcript 现在在 assistant action 阶段统一落盘，因此 discarded action 也能保持完整 `tool_call -> tool_result` 链路
- tool interrupt / retry 已继续推进第五段：Windows 下 `run_command` 现在以新进程组启动，并在取消时优先发送 `CTRL_BREAK_EVENT`；长命令用户中断不再依赖 `taskkill` 成功才会及时返回
- tool interrupt / retry 已继续推进第六段：`StreamingToolExecutor` 现在会直接观察 cancel event，因此 `max_parallel_tools>1` 时排队 action 在取消后会保持 `discarded`，不再偷偷升级成已启动的 `interrupted`
- tool interrupt / retry 已继续推进第七段：当前 batch 一旦已经出现 `discarded`，同一条 assistant plan 中后续 batch 会统一落 `discarded` result，而不会继续真实执行后续写动作
- tool interrupt / retry 已继续推进第八段：`StreamingToolExecutor` 现在对并行 batch 引入 idle timeout / cancel 收口；started 但迟迟不返回的只读 action 会落 `timeout` 或 `interrupted`，尚未开始的兄弟 action 会落 `discarded`，session 不再因单个卡死线程无限等待
- timeline 持久化已推进一段：`SessionTimelineStore` 现在与 transcript 一样按文件串行化写入并记录单调 `seq`；GUI raw timeline 顺序不再只依赖 `created_at`
- GUI turn 锚点已收口：webapp reducer 现在会给本地用户消息分配 provisional turn anchor，并在 `turn_started` 到来时整体回填，`/mode ... <message>` 这类“先命令结果、后真实 turn”链路不再把 command card 绑到伪 turn id 上
- GUI active-session runtime 已推进到 event-log + projector 第一版：GUI backend 已新增统一 `session_event` envelope、`GET /api/sessions/{session_id}/events?after_seq=N` replay 入口，以及统一的 interaction response route；前端当前会以 `sessionEventLog + projectSessionRuntime(...)` 作为 active session 读模型骨架
- Inspector / Timeline 交互边界已收口：Inspector 现在使用统一 `InteractionPanel` 处理当前 pending interaction，Timeline 只显示交互历史摘要，不再保留第二套 inline approve / answer 控件
- transport / restore 退化语义已补齐第一版：`ThreadsafeAsyncDispatcher` 现在会返回带 `reason` 的调度结果；`SessionRestorer` 遇到缺失可信 `interaction_id` 的 pending interaction 时会显式停在 `interaction_expired`；webapp `sessionEventLog` 已升级到 typed `replayState`
- GUI runtime hardening 第二段已完成：timeline replay 现在显式区分 `replay / reload_required / degraded`，HTTP / WebSocket 错误边界已 typed 化；webapp projector 现在接管 replay state、command-result fallback、detached turn item 排序与 session-scoped runtime reset
- GUI runtime hardening slice 已关闭：相关设计与实施文档已归档到 `docs/archive/gui-runtime-hardening/`
- GUI backend broadcast 已硬化：`WebSocketFrontend` 现在会在广播前冻结连接快照，并在独立锁下做 connect/disconnect/cleanup，连接集变化不再触发 `Set changed size during iteration`
- QueryEngine session 互斥已补齐：`InProcessAdapter` 现在把 `state.lock` 传给 `QueryEngine`，后者会在上下文构建、消息追加、transition/tool_result 落盘、compact boundary 写入和 summary refresh 等关键路径上持锁，避免运行中的 session 与外部模式/快照操作共享可变 `Session` 时发生竞态
- Phase 7 设计基线已建立：`docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md`
- Phase 7 初始脚本骨架已落地：`scripts/prepare-offline.ps1` 已可生成 `build/offline-staging/EmbedAgent/`、launcher、模板配置和 manifest/checksum 草案，并已通过 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证
- Phase 7 build 脚本骨架已落地：`scripts/build-offline-bundle.ps1` 已可把 staging bundle 复制到 `build/offline-dist/`、重写 manifest、重算 checksum，并生成 zip
- Phase 7 validate 脚本骨架已落地：`scripts/validate-offline-bundle.ps1` 已在 skeleton bundle 上验证通过，且 `-RequireComplete` 会按预期对缺失资产返回失败
- Phase 7 真实资产接入已打通第一段：`scripts/offline-assets.json` 已固定 `python_embedded_x64` 与 `mingit_x64`，`prepare/build/validate` 已完成真实 zip、SHA256、sources seed、license notice 与 launcher 校验
- Phase 7 真实资产接入已继续扩展到 `ripgrep_x64` 与 `universal_ctags_x64`，当前 `prepare/build/validate -RequireComplete` 已在四类核心资产上通过
- GUI 状态语义已收口：session status 现在以 `session_snapshot` 为权威，补齐了 `session_status`、`reasoning_delta`、`thinking_state`、稳定 `tool_call_id` 与 GUI 专用懒加载文件树接口
- GUI / Core 已完成第一段高拟态 clean-room 升级：时间线 API 现在以 `turns[].steps[]` 为主，单个用户问题下的多轮 Agent 自推进会拆成独立 step；GUI 也已开始按 step 渲染 thinking / tool / assistant
- 托管运行环境摘要已接入 ToolRuntime / SessionSnapshot / GUI Runtime inspector：当前会显示 `runtime_source`、`bundled_tools_ready`、`fallback_warnings` 与 `resolved_tool_roots`
- workbench 第一段已落地：Tool Runtime 可自动检测 `CMakeLists.txt` / `Makefile` 与历史成功命令 recipe；`compile_project` / `run_tests` / `run_clang_tidy` / `run_clang_analyzer` / `collect_coverage` 支持 `recipe_id`；slash command 新增 `/recipes` 与 `/run <recipe_id>`；GUI Inspector 已补 `Run` / `Problems` 并可直接执行 recipe
- todo 已切换为 session-scoped：真实会话默认使用 `.embedagent/memory/sessions/<session_id>/todos.json`，新建会话不再继承旧会话 todo
- 新 GUI webapp 已建立：`src/embedagent/frontend/gui/webapp/` 使用 React + Vite 构建，产物已写回 `src/embedagent/frontend/gui/static/`
- `scripts/validate-gui-smoke.py` 已升级：当前源码路径 smoke 可覆盖 tool / permission / ask_user / session todo 隔离、`/review` workflow 与 renderer 报告
- unified input / slash command / workflow 第一版已落地：`submit_user_message` 已统一分发普通消息与 `/help` `/mode` `/sessions` `/resume` `/workspace` `/clear` `/plan` `/review` `/diff` `/permissions` `/todos` `/artifacts`
- 协议层已扩展 `CommandResult`、`PlanSnapshot`、`TurnRecord`、`TimelineItem` 与增强版 `SessionSnapshot`；GUI 已接入 command result、plan pane、command cards 与 slash command hint
- `/review` 已升级为结构化 findings 输出；GUI 工具卡片开始使用 Core 下发的 `tool_label` / `progress_renderer_key` / `result_renderer_key` 做分支渲染
- GUI 已新增独立 review inspector；后端已暴露 tool catalog API，前端开始用 Core 的工具目录为旧 timeline / fallback 展示补足 label 与 renderer
- 已补 workflow/filtering 回归测试：`test_tools_package.py` 现在覆盖 `schemas_for(mode, workflow)` 过滤与 tool metadata 注入，GUI webapp `run-tests.mjs` 现在覆盖 review command / permission context 状态回归
- 已完成 dist/source GUI 布局重新对齐：重建后的离线 bundle 已携带 `static/assets`、Fixed Version WebView2 109、无 `__editable__.embedagent-*.pth` 泄漏，且 bundle 级 `validate-offline-bundle.ps1`、`validate-gui-smoke.py`、`check-bundle-dependencies.py` 全部通过
- Phase 7 打包链路已开始切换到声明式控制面：`scripts/package.config.json`、`scripts/package-lib.ps1` 与 `scripts/package.ps1` 已落地；当前 `doctor/deps/assemble/verify/release` 已可通过 mocked orchestration contract 运行，并统一写入 `build/offline-reports/`

项目下一步：继续推进 Phase 4 真实工程验证，在 Win7 bundle 中验证 Fixed Version WebView2 109 路径，并把 Phase 7 的 site-packages 精简、真实 release pipeline 验收和 Win7 bundle 验收接上。

---

## 3. 下一步优先级

### P0：立刻要做（当前关键路径）

1. 推进 Phase 4 的真实 C 工程与 Win7 验证
2. 在 Win7 bundle 中完成 GUI Chromium 基线实机验证并记录结果
3. 为当前 `package.ps1 release` 路径评估并收敛 `site-packages` 的精简导出方案

实现备注：

- Phase 1 已按当前可用条件验收完成；`GLM5 int4` / `Qwen3.5` 因环境不具备暂不纳入阻塞项。
- 当前原型已收敛到 `src/embedagent/` 包结构，打包入口与导入路径已同步更新。
- Phase 2 里程碑已满足：文件读写、命令执行、Git 状态/差异/日志均已具备并完成 3.8 本地验证。
- Phase 3 v2 里程碑已满足：5 模式（explore/spec/code/debug/verify）、配置驱动、工具过滤、用户主导切换均已完成 3.8 本地验证。
- Phase 4 已具备项目内闭环工具链，但默认 recipe、真实 C 工程和 Win7 验证仍需补齐。
- Phase 5 脚本验证已重新跑通，当前已从“实现完成”推进到“脚本复验通过”。
- Phase 6 自动化验证已通过，当前缺口已收敛到 Win7 Chromium 路径与真实交互体验。
- Phase 7 现已完成设计基线、ADR、`prepare/build/validate` 三段脚本骨架，以及 Python / MinGit / rg / ctags 的真实资产接入；公共控制面 `package.ps1` 已接上，下一步应转向 site-packages 精简与完整 bundle 验收。

### P1：紧随其后

1. 收敛 Clang bundle 的版本组合与默认命令 recipe
2. 决定是否将 memory browse / inspect 作为 Phase 6 收口项
3. 评估终端前端稳定后是否推进 stdio JSON-RPC adapter
4. 决定是否从 `.venv\Lib\site-packages` 继续直拷，还是切到更精简的运行时导出策略
5. 在 Win7 虚拟机上对当前四类核心资产 bundle 做一次真实验收

---

## 4. 近期任务板

| 编号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| T-001 | 建立最小 `pyproject.toml` + 代码骨架 | `completed` | 已收敛为 `src/embedagent/` 包结构 |
| T-002 | 实现 `OpenAI-compatible LLM Adapter` | `completed` | 同步+流式，Python 标准库，无厂商 SDK |
| T-003 | 实现第一批工具（read/list/search/edit） | `completed` | 已按 `docs/tool-design-spec.md` 规范落地 |
| T-004 | 实现最小主循环 + CLI 入口 | `completed` | 本地假模型闭环已跑通 |
| T-005 | Phase 1 里程碑验证（GLM5 + Qwen3.5） | `completed` | 目标模型环境不具备，按 Moonshot + Python 3.8 验证口径验收 |
| T-006 | 实现 Phase 2 工具（run_command / git） | `completed` | 已补齐工具契约与 Loop 烟雾验证 |
| T-007 | 实现模式系统 v1（dict + 工具过滤） | `completed` | 已补齐文档与本地验证 |
| T-008 | 实现 Phase 4 Clang 工具链第一版封装 | `in_progress` | 已有本地闭环工具链与 recipe-aware build/test 入口，待真实工程验证与版本收敛 |
| T-009 | 实现 Phase 5 最小权限与防循环保护 | `completed` | 权限模型、Doom Loop Guard、ContextManager、mode-aware budget、Artifact Store、SessionSummaryStore、ProjectMemoryStore、Resume Entry、MemoryMaintenance 已落地；`scripts/validate-phase5.py` 已在 2026-03-29 复验通过 |
| T-010 | 完成 Phase 6 前端协议与 TUI IA 设计 | `completed` | `frontend-protocol.md` 与 `tui-information-architecture.md` 已建立 |
| T-011 | 实现 Phase 6A InProcessAdapter | `completed` | CLI 已改为通过 adapter 驱动 Core，并完成最小行为验证 |
| T-012 | 落地模块化终端前端 | `completed` | 已完成 `src/embedagent/frontend/tui/` 模块化拆包，`src/embedagent/frontend/tui/` 已按新架构迁移，接入 timeline / workspace / artifact / todo 浏览接口，保留 `embedagent.tui` 兼容入口；下一步是继续做真实控制台 / Win7 手工验证与交互细化 |
| T-013 | 建立 Phase 6 验证入口 | `completed` | `scripts/validate-phase6.py` 与 `docs/phase6-validation.md` 已建立，Phase 6 已进入脚本可跟踪状态 |
| T-014 | 建立 Phase 7 离线打包设计基线 | `completed` | 已新增 `docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md` |
| T-015 | 实现 Phase 7A prepare-offline 骨架 | `completed` | 已新增 `scripts/prepare-offline.ps1`，可生成 `build/offline-staging/EmbedAgent/`、launcher、模板配置、manifest 与 checksum 草案，并支持 `-SkipBuild` |
| T-016 | 实现 Phase 7B build-offline-bundle 骨架 | `completed` | 已新增 `scripts/build-offline-bundle.ps1`，可消费 staging bundle，生成 `build/offline-dist/<artifact>/` 与 zip，并重写 dist manifest/checksum |
| T-017 | 实现 Phase 7C validate-offline-bundle 骨架 | `completed` | 已新增 `scripts/validate-offline-bundle.ps1`，可校验 skeleton bundle，并支持 `-RequireComplete` 切换到严格门禁 |
| T-018 | 接入 Python embeddable 与 MinGit 真实资产 | `completed` | 已新增 `scripts/offline-assets.json`，并完成真实 zip 下载、SHA256 固定、staging 解压、sources seed、license notice 与 `-RequireComplete` 验收 |
| T-019 | 接入 ripgrep 与 Universal Ctags 真实资产 | `completed` | 已扩展 `scripts/offline-assets.json` 与 `prepare/build/validate`，完成真实 zip 下载、SHA256 固定、sources seed、license notice 与 `-RequireComplete` 验收 |
| T-020 | 实现新架构协议层（protocol/core/frontend） | `completed` | 已新增 `protocol/` 层定义 CoreInterface/FrontendCallbacks，`core/` 层实现 AgentCoreAdapter，`frontend/gui/` 实现 PyWebView 前端，架构测试 17 项全通过 |
| T-021 | GUI 前端与后端功能联动 | `in_progress` | 已完成 session-scoped todo、权威 session snapshot 状态事件、稳定 tool_call_id、reasoning/thinking 事件、GUI 懒加载文件树、新 React/Vite webapp 构建、slash command / plan pane / command cards、structured review command、review inspector、tool catalog fallback、step-based timeline、Runtime inspector、Run / Problems 面板、runtime hardening（typed replay / restore / projector ownership）与 `/review` smoke；剩余缺口是更完整的 workflow 深化与 Win7 实机验证 |
| T-026 | unified input / slash command / workflow 第一版 | `completed` | 已打通 `submit_user_message -> slash command dispatcher -> command_result / plan_updated -> GUI/TUI` 闭环，并补齐协议类型、计划存储、权限上下文与 focused tests |
| T-022 | 零依赖打包：Python 依赖完整导出 | `completed` | 已新增 `scripts/export-dependencies.py`，确保所有 Python 依赖（含传递依赖）完整导出到 site-packages |
| T-023 | 零依赖打包：依赖完整性验证 | `completed` | 已新增 `scripts/check-bundle-dependencies.py`，验证 bundle 包含所有必需依赖 |
| T-024 | 零依赖打包：内网部署文档 | `completed` | 已新增 `docs/intranet-deployment.md` 和 `docs/offline-packaging-guide.md`，提供完整内网部署指南 |
| T-025 | 零依赖打包：内网配置模板 | `completed` | 已新增 `config/config.json.template`，预配置内网大模型服务示例 |
| T-027 | Phase 7 打包控制面收口 | `in_progress` | `scripts/package.ps1`、`scripts/package.config.json`、`scripts/package-lib.ps1` 与 `tests/test_packaging_control_plane.py` 已打通 `doctor/deps/assemble/verify/release` mocked orchestration；下一步是完成文档迁移并在真实 bundle 路径上验收 |
| T-028 | Query / Context 内核重构切片 | `completed` | 已落地 `QueryEngine`、transcript/event 模型、workspace intelligence broker、tool capability metadata、batch tool orchestration、pending interaction resume、`transcript_store.py`、`session_restore.py`、transcript-truth resume、`parent_message_id` 因果链、timeline `seq` 顺序、parallel tool timeout/cancel 收口、single-writer tool commit、session-local tool-result store、SQLite projection cutover，以及 websocket/session-lock 竞态硬化；当前这一轮 context loop 迭代已关闭，handoff/analysis/review 文档已归档到 `docs/archive/context-loop/` |

---

## 5. 里程碑进度

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| Phase 0 | 仓库基线与工作约束 | `completed` | 已完成文档、版本策略、治理基线、工具规范 |
| Phase 1 | 最小可工作 Loop | `completed` | 已完成 Python 3.8 与真实 OpenAI-compatible 工具闭环验证 |
| Phase 2 | 工具集 v1 | `completed` | 已实现 run_command / git 工具，并完成 3.8 本地验证 |
| Phase 3 | 模式系统 v2 | `completed` | 5 模式配置驱动（explore/spec/code/debug/verify）、initialize_modes、工具过滤、/mode 已完成；switch_mode LLM 工具已移除 |
| Phase 4 | Clang 工具链 | `in_progress` | 已有项目内闭环工具链，待真实工程与 Win7 验证 |
| Phase 5 | 质量保障层 | `completed` | 权限、上下文、记忆、恢复与 cleanup 已落地；修复根目录文件写入边界后，专项验证脚本已复验通过 |
| Phase 6 | CLI / TUI / GUI | `in_progress` | InProcessAdapter 已扩展 workspace / timeline / artifact / todo 前端接口；终端前端已拆为 `frontend/tui` 子模块；GUI 已切换到 React/Vite webapp + PyWebView 宿主，当前环境 smoke 已覆盖 tool / permission / ask_user / todo 隔离；待 Win7 Chromium 实机验证与 diff/编辑闭环细化 |
| Phase 7 | 打包与离线交付 | `in_progress` | 设计基线、ADR、`prepare/build/validate` 三段脚本骨架已完成；Python/MinGit/rg/ctags 真实资产接入已完成；`package.ps1` 控制面已接上 mocked orchestration；GUI 依赖与 bundle-local smoke 已进入交付物，`validate-offline-bundle -RequireComplete`、`check-bundle-dependencies.py` 与 bundle 级 windowed GUI smoke 已通过；待真实 release pipeline 与 Win7 bundle 实机验收 |

---

## 6. 当前风险与关注点

| 编号 | 风险 | 当前判断 | 应对方式 |
|------|------|----------|----------|
| R-001 | Python 版本上滑 | 高 | 强制保持 `>=3.8,<3.9`，文档与配置双锁定 |
| R-002 | 过早做 UI 导致核心失焦 | 高 | Phase 6 才做 TUI，Phase 1 只做最简 CLI |
| R-003 | 内网模型 function calling 格式不标准 | 高 | Phase 1 里程碑强制在真实模型上验证，发现问题立即在 LLM Adapter 层补充兼容处理 |
| R-004 | 工具集设计退化（工具增多、描述变复杂） | 中 | `docs/tool-design-spec.md` 有审查清单，每次新增工具前必须过清单 |
| R-005 | 文档和实现脱节 | 高 | 每轮关键变更必须同步更新 tracker / change log / roadmap |
| R-006 | Clang bundle 包大小过大 | 低 | 静态链接验证已通过，打包细节推到 Phase 7 处理 |
| R-007 | provider 兼容差异未系统沉淀 | 中 | 已确认 Moonshot `kimi-k2.5` 需要 `/v1` 和 `reasoning_content`，后续整理到适配文档 |
| R-008 | 当前仓库缺少真实 C 构建入口 | 中 | 已完成本地 smoke test，后续仍需接默认命令和真实工程 |
| R-009 | 当前闭环工具链存在跨版本组合 | 中 | 现状已通过本地 smoke test，后续需要继续收敛到同版本或自建包 |
| R-010 | 当前上下文压缩仍较弱 | 中 | 已有 mode-aware budget、reducer registry、Artifact Store、SessionSummaryStore、ProjectMemoryStore 与 Resume Entry，后续继续补生命周期清理与可选 LLM condenser |
| R-011 | Python embeddable distribution 的 CRT / UCRT 本地部署复杂 | 中 | 用 Phase 7 preflight 清单和本地 DLL bundling 策略收口 |
| R-012 | 第三方二进制来源、License 和 checksum 追溯不足 | 中 | 用 bundle manifest 记录 version/source/license/checksum，并纳入构建产物 |
| R-013 | prepare 阶段与最终 build/validate 阶段契约不清晰，后续脚本容易返工 | 中 | 先把 `prepare/build/validate` 的输入输出边界写清，再继续实现 |
| R-014 | 当前 build 已验证四类核心资产可启动，但 `site-packages` 仍是直拷 `.venv`，离最终 bundle 仍有优化空间 | 中 | 下一步收敛更精简的运行时包导出方案 |
| R-015 | validate 默认允许 skeleton bundle 以告警通过，若无人切到 `-RequireComplete` 可能误判“已可交付” | 中 | 在正式验收和 CI 入口中强制使用 `-RequireComplete` |
| R-016 | 直接拷贝 `.venv\Lib\site-packages` 可能带来过大的 bundle 体积 | 中 | 评估更精简的运行时导出方案，再决定是否替换当前实现 |
| R-017 | 离线 bundle 容易因未重建或直接拷贝开发 `.venv` 而把旧 GUI 布局或项目内 editable `.pth` 带进发布物 | 中 | 保持 `prepare/build/validate` 串联执行，并在 bundle 验证中强制检查 `static/assets`、Fixed Version WebView2 和无 `__editable__*.pth` |
| R-018 | transcript-truth cutover 已完成，但后续增强若绕过单写提交边界，仍可能重新引入 projection/summary 漂移 | 低 | 继续保留 focused regression tests 覆盖 mode、timeline、pending interaction、context assembly 与 stored-path replacement；新增增强时优先复用 `ToolCommitCoordinator + ProjectionDb` 主线 |

---

## 7. 最近更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-04-04 | Query / Context / Context Loop 这轮重构已收口：P0 问题全部关闭，handoff/analysis/review 文档已归档到 `docs/archive/context-loop/`，活动状态以后续真实工程集成回归和 Win7 验证为准 |
| 2026-04-04 | GUI runtime hardening 已推进完成：timeline replay / restore / typed HTTP-WS error boundary / active-session projector ownership 已收口，webapp 现已按 replay 状态和 grouped projector 读模型驱动 active session |
| 2026-04-04 | GUI runtime hardening 相关 spec/plan 已从活动 `docs/superpowers/` 入口移入 `docs/archive/gui-runtime-hardening/`，当前该 slice 视为关闭 |
| 2026-03-27 | 建立进度跟踪文件，明确当前阶段与下一步优先级 |
| 2026-03-27 | DC-004/DC-005：工具设计规范建立，实施分期重组，Phase 1 改为最小可工作 Loop |
| 2026-03-27 | 已落地 Phase 1 最小原型代码，并完成本地语法检查、工具自测与假模型闭环验证 |
| 2026-03-27 | Moonshot `kimi-k2.5` 真实联调通过，补齐了温度参数与 `reasoning_content` 兼容处理 |
| 2026-03-27 | 代码骨架迁移到 `src/embedagent/`，并通过 `uv` 创建的 Python 3.8.10 环境验证 |
| 2026-03-27 | 按当前可用条件完成 Phase 1 验收，并切换到 Phase 2 工具集实现 |
| 2026-03-27 | Phase 2 核心工具已实现，并通过 Python 3.8 本地自测 |
| 2026-03-28 | Phase 2 工具契约与 Loop 烟雾验证完成，阶段状态切换到 Phase 3 准备中 |
| 2026-03-28 | Phase 3 模式系统 v1 已完成，并补齐模式结构与状态机文档 |
| 2026-03-28 | Phase 4 第一版工具封装与解析验证完成，并建立 Clang 集成计划文档 |
| 2026-03-28 | 已下载、组装并验证项目内闭环 Clang 工具链，完成编译/分析/tidy/coverage smoke test |
| 2026-03-28 | Phase 5 最小权限模型与 Doom Loop Guard 已落地，并清理了工具链临时产物 |
| 2026-03-28 | Phase 5 第一版 ContextManager 已落地，并完成本地压缩/回归验证 |
| 2026-03-28 | Phase 5A mode-aware budget、ReducerRegistry 与 ContextStats 已落地，并完成本地行为验证 |
| 2026-03-28 | Phase 5B Artifact Store 已落地，并完成大输出脱敏/落盘/回灌验证 |
| 2026-03-28 | Phase 5C Session Summary Store 已落地，并完成状态落盘/回归验证 |
| 2026-03-28 | Phase 5D Project Memory Store 已落地，并完成 recipe / known issue / context 注入验证 |
| 2026-03-28 | Phase 5E Resume Entry 已落地，并完成 list / load / resume 验证 |
| 2026-03-28 | Phase 5F Memory Maintenance 已落地，并完成 cleanup / index 验证 |
| 2026-03-28 | Phase 6B 交互深化已完成：TUI 新增会话列表浏览、权限确认/错误/上下文状态展示，并修复 --tui 空启动路径 |
| 2026-03-28 | Phase 6B 依赖与运行验证已推进：`prompt_toolkit` / `rich` 已接入，非控制台宿主会优雅报错，并完成 headless 真实事件循环验证 |
| 2026-03-28 | Phase 6 验证入口已建立：新增 scripts/validate-phase6.py 和 docs/phase6-validation.md，阶段状态已可脚本跟踪 |
| 2026-03-29 | Phase 6 终端前端已模块化：新增 src/embedagent/frontend/tui/ 包、timeline store 和 adapter 浏览接口，保留 embedagent.tui 兼容入口，并通过 headless 与单元测试 |
| 2026-03-29 | 修复 `**/*.md` 等模式对根目录文件不匹配的问题，补充 `test_modes.py` 回归，并重新跑通 `scripts/validate-phase5.py` |
| 2026-03-29 | README、路线图、进度跟踪与变更日志已按当前能力和阶段状态完成一轮对齐 |
| 2026-03-29 | 建立 Phase 7 离线打包设计基线：新增 `docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md` |
| 2026-03-29 | 建立 `scripts/prepare-offline.ps1`：已可生成 staging bundle 骨架、launcher、模板配置、`bundle-manifest.json` 与 `checksums.txt`，并通过 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证 |
| 2026-03-29 | 建立 `scripts/build-offline-bundle.ps1`：已可把 staging bundle 复制到 `build/offline-dist/`、生成 zip、重写 dist manifest 并重算 checksum |
| 2026-03-29 | 建立 `scripts/validate-offline-bundle.ps1`：默认模式可校验 skeleton bundle 并告警通过，`-RequireComplete` 下会对缺失资产返回失败 |
| 2026-03-29 | 建立 `scripts/offline-assets.json`，正式接入 `python_embedded_x64` 与 `mingit_x64`，并完成真实 prepare/build/validate 验收 |
| 2026-03-30 | 零依赖打包方案落地：新增 `scripts/export-dependencies.py` 导出完整 Python 依赖（含传递依赖），新增 `scripts/check-bundle-dependencies.py` 验证 bundle 完整性，新增 `docs/intranet-deployment.md` 内网部署指南，新增 `docs/offline-packaging-guide.md` 完整打包指南，配置模板已预置内网大模型服务示例 |
| 2026-03-30 | 当前环境 GUI 验证已补齐：已安装 `pywebview` / `fastapi` / `uvicorn` / `websockets`，新增 `scripts/validate-gui-smoke.py`，源码路径与 bundle 路径的 headless GUI smoke 均已通过 |
| 2026-03-30 | 离线 bundle GUI 集成已补齐：`prepare/build/validate` 与 `check-bundle-dependencies.py` 已纳入 GUI launcher / static files / 文档 / site-packages 检查，当前环境完整 bundle 验证通过 |
| 2026-03-30 | Win7 GUI 实机验证入口已准备：GUI launcher 新增 renderer report 与 auto-close 参数，bundle 已内置 `validate-gui-smoke.cmd` 和 `docs/win7-gui-validation.md`，当前 Windows 10 环境 windowed smoke 返回 `renderer=edgechromium` |
| 2026-03-30 | GUI 新壳层已落地：新增 `frontend/gui/webapp/` React + Vite 工程，产物写回 `frontend/gui/static/`；同时完成 session-scoped todo、权威 `session_status`/`thinking_state`/`reasoning_delta`、稳定 `tool_call_id`、GUI 懒加载文件树与增强版 smoke 校验 |
| 2026-03-31 | 已补 workflow/filtering 回归测试，并把 `scripts/validate-gui-smoke.py` 扩展到 `/review` workflow；源码路径 smoke 已通过，但当前 `build/offline-dist/` bundle 仍呈现旧 GUI 布局并在 bundle smoke / validate 中暴露出与最新 validator 的结构漂移 |
| 2026-03-31 | 已定位并修复 dist/source GUI 漂移：原因是旧 dist 未在 GUI 静态产物迁移后重建、WebView2 资产未纳入 prepare/build、以及 `.venv` 里的 `__editable__.embedagent-0.1.0.pth` 被直接带入 bundle；当前已重建 bundle，并通过 `validate-offline-bundle.ps1`、bundle 级 `validate-gui-smoke.py` 与 `check-bundle-dependencies.py` |
| 2026-04-02 | 已启动 Query / Context 激进重构切片：新增 `QueryEngine`、transcript/event 模型、workspace intelligence broker、tool capability metadata、batch tool orchestration、pending interaction resume 与 focused regression tests；`tests.test_context_config` / `tests.test_guard` / `tests.test_modes` / `tests.test_session_timeline` / `tests.test_query_engine_refactor` 已复验通过 |





