# Pi/T3 Residual Architecture Debt Design

> 状态：`draft`
> 类型：`superpowers-spec`
> 负责人：`project maintainers`
> 最后同步日期：`2026-06-27`
> 对应代码范围：`src/embedagent/`, `src/embedagent/frontend/gui/`, `tests/`

## 1. Reader And Post-Read Action

本文面向下一轮执行清理的内部工程师。

读完后，工程师应能做一件事：按目标架构判断一个残余路径应该删除、迁移到新的 owner，还是保留为显示层 read model，并据此执行下一轮清理切片。

## 2. Scope

本轮只识别和规划，不修改运行时代码。

目标是找出最近多轮 Pi/T3 改造后仍可能导致后续发散的残余技术债：

- 旧契约仍被测试或文档保护。
- Agent Core facade 仍承担过多 hosted/runtime/projection 责任。
- GUI 已有 T3-style 模块，但主 App 和 store 仍像补丁总线。
- 前后端活动对接仍有前端合成事件和后端事件并存的风险。
- App-shell surface 边界正确但实现文件继续膨胀，容易吸收后续功能。

不在本轮范围：

- 兼容旧 session、旧 transcript、旧 GUI reducer shape。
- 修改 Pi/T3 reference 源码。
- 引入 Node runtime、Electron、Docker、WSL、在线服务或 Python 3.9+ 语法。
- 实现源代码清理。

## 3. Current Findings

### 3.1 Old Tool Vocabulary Still Has Test Gravity

产品源码中旧 task tool 已基本退出正式 catalog，但测试仍显式调用旧 task tool 并断言 runtime 返回失败 observation。

这不是严重运行时缺陷，但它保留了旧工具名作为测试 API。项目当前处于 pre-release，不需要保护旧工具调用行为；测试应该保护“旧工具不会出现在 catalog/schema/command/help 中”，而不是保护旧工具执行后的错误 shape。

Target owner:

- Runtime catalog and schema tests own official tool exposure.
- Architecture guard tests own forbidden legacy vocabulary.
- No test should require `ToolRuntime.execute()` to keep a named legacy tool branch stable.

### 3.2 Compatibility Tests Are Becoming A Compatibility Surface

`test_backward_compatibility` 仍以“public API unchanged”为组织口径。它目前也保护了一些正确边界，例如 removed aliases and single internal entrypoints，但文件名和用语会鼓励后续贡献者保留 pre-release API。

Target owner:

- Boundary guard tests should replace compatibility framing.
- Kept assertions should be reworded as current architecture invariants.
- Pre-release compatibility with removed internals should not appear as a product value.

### 3.3 QueryEngine Is Still The Largest Core Semantic Sink

The current core split is real: lifecycle, kernel, loop, tool action service, extension host, turn snapshot service, prompt assembly service, and reducers exist. However the session facade still owns many helper families:

- lifecycle event wrappers
- transcript append helpers
- provider operation metadata
- runtime/capability snapshot helpers
- workflow prompt appending
- command turn handling
- pending interaction payload helpers
- compact boundary and compacted-history payload assembly

This keeps the code working but keeps Core thicker than the Pi target. Future behavior can still land in QueryEngine because the facade has many nearby helpers.

Target owner:

- `AgentLifecycleJournal` owns lifecycle event emission.
- `TurnSnapshotService` owns provider snapshot metadata.
- `PromptAssemblyService` owns prompt append/dedup behavior.
- Compact-boundary payload assembly should move behind a focused compaction journal/helper.
- QueryEngine should remain a facade over turn submission, mode application, and session mutation coordination.

### 3.4 InProcessAdapter Is Still A Hosted Runtime Monolith

The adapter has useful extracted services, but it still combines:

- hosted extension/resource loading
- runtime configuration reducer refresh
- compaction/recovery reducer refresh
- session lifecycle
- workspace/file/artifact/task APIs
- slash command dispatch
- command result emission
- permission/user input response entrypoints
- tool execution from slash commands
- frontend event projection and snapshot emission

This is the strongest remaining Agent-side coupling risk. It is not enough to add another helper around it; responsibilities need deletion-oriented extraction into existing or new hosted services.

Target owner:

- `RuntimeCapabilityService` owns capability and tool-catalog projection.
- `SessionBootstrapService` owns bootstrap assembly.
- `SlashCommandService` owns slash command routing.
- A new hosted session command service should own command execution helpers that are not Agent Core.
- A hosted interaction facade should own permission/user-input response glue.
- The adapter should become a composition root and API facade, not a business-logic container.

### 3.5 Extension Boundary Has A Small Bypass Smell

Most extension hook calls now go through `AgentExtensionHost`. There are still direct `ExtensionManager` calls in the adapter for hosted operations such as context reducer registration, package manifests, resource discovery, task loading, and tool registration.

Some of these are legitimate composition-root operations, but the current shape does not clearly separate:

- session-engine extension dispatch
- hosted resource reload
- capability read-model projection
- default workflow maintenance

Target owner:

- Keep session turn behavior behind `AgentExtensionHost`.
- Keep composition-time operations in a named hosted extension services boundary.
- Add guards that prevent QueryEngine from regaining direct hook dispatch.
- Add docs/tests that distinguish allowed adapter composition calls from forbidden session-engine hook calls.

### 3.6 Frontend App.jsx Still Acts As The GUI Runtime Controller

The GUI has moved important state into focused modules, but `App.jsx` still owns:

- API fetch helpers
- workspace bootstrap orchestration
- session creation/loading
- thread lifecycle prompts
- mode/cancel/message submission
- command palette execution
- socket effect execution
- interaction response handling
- preview/source-control/file/diff opening
- terminal controller creation
- visual debug fixture installation
- rendering props for all major surfaces

T3 reference structure favors route components plus small state stores and controllers. The current App still resembles a central patchboard.

Target owner:

- App root should own providers, layout, and composition.
- Session orchestration belongs in an app-runtime controller.
- Thread lifecycle belongs in a thread controller/model.
- Surface opening belongs in right-panel/workbench stores and commands.
- Preview/source-control/terminal command execution belongs in feature-specific controllers.

### 3.7 Store.js Is A Mixed Global Reducer

The store dispatches to focused reducers for several domains, but it still directly mutates timeline items, streaming assistant/reasoning state, pending interactions, task/artifact/preview/file/diff state, inspector tab state, and command results.

This keeps old reducer-style patches alive beside T3-style focused modules.

Target owner:

- Session activity state owns activity/timeline item normalization and streaming deltas.
- Thread state owns active thread and history integrity.
- Workbench state owns inspector/right-panel surface selection.
- Feature states own tasks, artifacts, preview, file preview, diff, and source control.
- Store should become a root reducer delegating whole action families, not a place for product behavior.

### 3.8 Frontend Synthesizes An Interaction Resolution Event

When an interaction response succeeds, the GUI app appends a local `interaction.resolved` transport event. The target architecture says live interaction activity should come from backend-owned `session_event` messages, while raw request messages drive only the blocking UI.

This local event is display state today, but it can become a second activity truth. The fix should not be another dedupe patch; backend/Core should emit the resolved interaction event through the same session-event path.

Target owner:

- Core or backend session-event bridge owns `interaction.resolved`.
- Frontend consumes it through the existing session transport controller.
- Frontend interaction response handler clears local input state and refreshes snapshot, but does not invent history/activity events.

### 3.9 GUI Backend Server Is Functionally Correct But Structurally Too Broad

The backend app-shell surfaces appear to respect the architecture constraints: terminal, source control, and preview are local/app-shell surfaces and do not write Agent Core state. However the server module now combines serialization helpers, WebSocketFrontend, route registration, terminal routes, source-control routes, preview routes, interaction routing, and core session routes.

This makes future app-shell additions likely to land as one more block in the same module.

Target owner:

- Session route registration should live in a session routes module.
- App-shell/workspace routes should live in an app routes module.
- Terminal/source-control/preview route registration should live with their service families.
- WebSocketFrontend/session event bridge should be separate from HTTP route construction.

### 3.10 TUI Timeline Naming Is Display-Layer Acceptable But Needs Guarded Language

TUI still uses `timeline` as a view name and line buffer. This can be acceptable because it formats `history.activities` and live display lines. It must not be described as durable timeline truth or reload transport.

Target owner:

- TUI view naming may remain if guarded as display vocabulary.
- Protocol and docs must continue to say session history comes from transcript/bootstrap.
- Any new TUI reload behavior must consume bootstrap activities, not event replay.

### 3.11 Active Docs Still Contain Historical Terms

Some active documents mention old terms only as forbidden or historical vocabulary, which is fine. One ADR still describes an old `code` mode choice because it is historical. That should remain clearly historical or be archived from active reading paths if it confuses contributors.

Target owner:

- Source-of-truth docs should only use old terms in explicit historical/forbidden contexts.
- ADRs may preserve historical decisions, but entry docs should point readers to current docs first.

## 4. Target Re-Route Map

| Problem | Do Not Do | Target Route |
| --- | --- | --- |
| Old tool tests | Keep `execute("old_tool")` behavior stable | Guard official catalog/schema/help excludes old tools |
| QueryEngine helper growth | Add new private helper wrappers | Move payload/journal/snapshot logic to focused services |
| Adapter monolith | Add another method family to adapter | Extract hosted services; adapter composes and delegates |
| Extension calls | Scatter manager calls in session engine | Use AgentExtensionHost for turn behavior; named hosted extension service for composition |
| App.jsx controller sprawl | Add more callbacks and render props | Move orchestration into app-runtime/domain controllers |
| Store.js mixed reducer | Add more root action cases | Delegate action families to focused T3-style stores |
| Interaction resolved | Frontend-generated history-like event | Backend/Core session_event owns resolution |
| GUI backend server sprawl | Add route blocks to server.py | Register route groups from small modules |
| TUI timeline display | Rebuild history from event replay | Format bootstrap `history.activities` only |

## 5. Proposed Cleanup Order

### Slice A: Guard The Target Architecture

Before moving code, add or update guard tests so stale paths cannot come back:

- no product test asserts named legacy tool execution behavior
- no frontend-generated `interaction.resolved` transport event
- no new root reducer action case for session activity once delegated
- no direct QueryEngine extension manager hook dispatch
- no GUI server route growth outside route modules after split

### Slice B: Remove Old Contract Gravity

Rename or replace compatibility-framed tests that now protect current architecture invariants. Remove tests that keep old tool names alive as executable inputs.

### Slice C: Fix Interaction Resolution Ownership

Move interaction resolution activity to backend-owned `session_event`. Keep request messages for blocking UI only.

### Slice D: Split GUI Runtime Controllers

Move command execution, session loading/creation, thread lifecycle, and surface opening out of `App.jsx`. Keep App as composition root.

### Slice E: Split GUI Store Families

Move activity, interaction, file preview, diff, task/artifact, and inspector transitions behind focused reducers/read models. Root store delegates.

### Slice F: Split GUI Backend Routes

Keep route behavior unchanged but move route registration into route modules. This is a structural cleanup to prevent future backend coupling.

### Slice G: Slim QueryEngine And InProcessAdapter

After tests and GUI ownership are stable, extract focused Agent hosted services:

- compaction event payload/journal helper
- interaction response facade
- command execution service
- extension composition service

Each extraction deletes responsibility from the old owner in the same slice.

## 6. Acceptance Criteria

The cleanup is successful when:

- No active product source or tests require old internal session, timeline, GUI reducer, or legacy tool shapes.
- Interaction activity is backend-owned end to end.
- App.jsx is a composition root, not the owner of API orchestration for every surface.
- Root store delegates product behavior to focused modules.
- GUI backend route registration is grouped by boundary.
- QueryEngine and InProcessAdapter are smaller because responsibilities moved to named owners, not because wrappers were added.
- Fast Python tests and webapp runtime/helper tests pass.
- Active docs describe only the promoted owner boundaries.

## 7. Reader-Test Notes

A cold reader should be able to answer:

- Which remaining items are defects versus acceptable display vocabulary?
- Which owner should receive each responsibility?
- Which fixes must delete old paths rather than preserve compatibility?
- What order avoids adding new patch layers?

The answer is encoded in the findings, target re-route map, and cleanup order above.
