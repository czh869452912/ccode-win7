# Pi/T3 residual debt audit and cleanup plan

Date: 2026-06-27
Status: proposed cleanup plan

## Scope

This audit covers the residual architecture debt left after the recent pre-release cleanup rounds. The goal is not compatibility with old internal state. The goal is to keep moving toward:

- Pi-like Agent Core: minimal kernel, append-only session truth, explicit runtime dependencies, hook/capability boundaries, and policy outside the low-level loop.
- T3 Code-like GUI: contract-first thread/session shell, focused runtime modules, scoped stores/controllers, and no parallel legacy timeline/state paths.
- Windows 7, Python 3.8, offline deployment, and the bundled C/C++ workflow as non-negotiable constraints.

Evidence reviewed:

- Product docs: `README.md`, `docs/overall-solution-architecture.md`, `docs/implementation-roadmap.md`, `docs/pre-release-architecture-debt-audit.md`, `docs/pi-inspired-agent-core-blueprint.md`, `docs/frontend-protocol.md`, `docs/permission-model.md`.
- Pi references: `reference/pi/packages/agent/src/agent-loop.ts`, `reference/pi/packages/agent/src/types.ts`, `reference/pi/packages/agent/docs/agent-harness.md`, `reference/pi/packages/agent/docs/durable-harness.md`.
- T3 references: `reference/t3code/apps/web/src`, `reference/t3code/packages/contracts/src`, `reference/t3code/packages/shared/src`.
- Local source hotspots: `src/embedagent/guard.py`, `src/embedagent/agent_loop.py`, `src/embedagent/agent_loop_continuation.py`, `src/embedagent/permissions.py`, `src/embedagent/tools/runtime.py`, `src/embedagent/query_engine.py`, `src/embedagent/inprocess_adapter.py`, `src/embedagent/session_history.py`, and GUI webapp runtime modules.

The generated GUI artifact `src/embedagent/frontend/gui/static/assets/app.js` was already dirty before this audit and was not touched.

## Findings

### P0. Loop guard treats ordinary tool failures as hard-stop conditions

Current state:

- `LoopGuard` defaults to `max_consecutive_failures=2`.
- `AgentLoop` records every failed Observation into the same guard path.
- A failed `bash` or `run_recipe` result includes `error_kind=command_failed` and `retryable=False`, then counts toward a hard `guard_stop`.
- Tests currently pin the behavior that two failing `bash` observations stop the loop.

Why this is debt:

- Pi's low-level loop does not stop after arbitrary tool failures. Tool failures become tool-result messages and the next model turn decides what to do.
- In C/C++ work, compile/test/shell failures are normal diagnostic input. Stopping after two failures breaks the default target workflow.
- Raising the threshold would be a patch. The missing piece is outcome classification, not a bigger number.

Target design:

- Replace the generic consecutive-failure stop with a Pi-style continuation policy over classified tool outcomes.
- Keep abort, pending interaction, explicit safety fuse, provider empty response, and explicit extension/tool termination as valid stops.
- Treat command/build/test failures as diagnostic outcomes that continue the agent loop unless an explicit stop hint is present.
- Treat repeated identical no-progress actions as model-visible blocked observations first; only hard-stop when policy classifies the loop as runaway.

Required protocol shape:

- Tool observations should expose safe loop classification metadata, for example:
  - `outcome_class`: `diagnostic_failure`, `policy_block`, `tool_contract_error`, `interrupted`, `discarded`, `success`
  - `counts_as_runaway`: boolean
  - `terminate_turn`: boolean, reserved for explicit extension/tool termination
- `retryable=False` must keep its current meaning: do not rerun the exact same command unchanged. It must not imply "stop the agent".

Acceptance checks:

- Two different failing `bash` commands do not produce `guard_stop`.
- Two failing C/C++ build or recipe commands do not produce `guard_stop`; the next provider turn receives the diagnostics.
- Empty assistant response with no tool calls may still stop as `guard_stop`.
- Repeated identical non-retryable blocked actions are blocked or summarized without ending a productive diagnostic loop.
- Parallel discarded/interrupted results remain excluded from runaway accounting.

### P0. Permission policy has dual truth and a fail-open unknown path

Current state:

- `ToolRuntime` has permission metadata in `_DEFAULT_TOOL_METADATA`.
- `PermissionPolicy` also owns hard-coded tool-name sets such as `READ_TOOLS`, `WORKSPACE_WRITE_TOOLS`, `SHELL_EXEC_TOOLS`, and `TOOLCHAIN_EXEC_TOOLS`.
- `OFFICIAL_PERMISSION_CATEGORY_ORDER` omits `other`, while docs and rule aliases mention `other`.
- If category lookup is absent or invalid and a tool is not in the hard-coded sets, `_category_for_action()` returns `other`; `evaluate()` then falls through to `allow`.

Why this is debt:

- Tool activation, capability metadata, and permission category are split across two sources of truth.
- New extension or hosted tools can drift into the wrong category if metadata projection is incomplete.
- Unknown capability should fail closed or ask, not allow.
- This is especially risky for future intranet, provider, telemetry, and self-extension work.

Target design:

- Make runtime/capability metadata the only source of tool permission category.
- Keep `PermissionPolicy` responsible for rule matching and decisions, not tool taxonomy.
- Treat missing or unknown permission metadata as `other` and ask/deny by default.
- Include `other` in the official category order only if it is a first-class ask-by-default category.
- Ensure permission prompts carry provenance: tool name, runtime source, permission category, arguments summary, rule source, and operation/session ids.

Acceptance checks:

- Unknown tools and tools with invalid/missing metadata do not auto-allow.
- Built-in tools resolve categories from tool metadata, not from hard-coded sets in `permissions.py`.
- `read` remains allow-by-default; `workspace_write`, `shell_exec`, `toolchain_exec`, `network`, `telemetry`, and `other` ask by default unless a rule or explicit auto-approve setting says otherwise.
- Dynamic in-process extension tools cannot register without a valid permission category.
- Permission context GUI receives the same official categories as the backend policy.

### P1. QueryEngine, AgentLoop, and InProcessAdapter remain too thick

Current state:

- `QueryEngine` is still over 2000 lines and owns mode switch parsing, transcript appends, operation event helpers, prompt assembly coordination, pending interaction helpers, compaction payloads, and session mutation.
- `AgentLoop` still owns provider step orchestration, lifecycle emissions, tool scheduling, loop guard policy, and continuation decisions.
- `InProcessAdapter` is still a large hosted facade mixing session lifecycle, bootstrap projections, capability snapshots, resource reload, review invocation, GUI APIs, and runtime ownership.

Why this is debt:

- The promoted boundaries exist, but orchestration semantics still collect in the old facade classes.
- Pi-like minimal core needs smaller kernel objects with explicit reducers/services, not large procedural owner objects.
- Future self-extension and workflow-package work will keep adding hooks unless the boundaries are enforced.

Target design:

- `QueryEngine`: session-scoped facade only. It should wire `AgentKernel`, `AgentLoop`, `AgentExtensionHost`, and reducer/journal services, not own their semantics.
- `AgentLoop`: low-level Pi-style loop. It should ask injected policy/services for continuation, tool outcome classification, and lifecycle recording.
- `InProcessAdapter`: hosted runtime facade only. Move session lifecycle, bootstrap/read models, capability projection, review commands, and resource operations behind narrow services.

Cleanup order:

1. Extract loop outcome and continuation policy first, because it changes behavior and tests.
2. Extract permission category resolution, because it controls future extension safety.
3. Slim QueryEngine helpers that directly support those changes.
4. Split InProcessAdapter only after the backend protocol shape is stable.

### P1. GUI is T3-inspired but still adapter-heavy rather than T3-native

Current state:

- `App.jsx` remains a large coordinator for session loading, transport recovery, API calls, interactions, command palette, terminal, workbench, and panels.
- `store.js` still owns broad root-level runtime state such as timeline, streaming assistant ids, permissions, tasks, artifacts, plan/review, file tree, tool catalog, and termination fields.
- Focused modules exist under `session-runtime/`, `app-runtime/`, `composer/`, `terminal/`, and `workbench/`, but many live updates still pass through root action cases.
- `socket-message-effects.js` translates backend event names into GUI actions and synthesizes `interaction.created` transport events for permission/user-input requests.
- GUI file-refresh logic hard-codes tool names including inactive source-control mutation names such as `git_commit` and `git_reset`.
- `store.js` keeps fallback labels for removed or inactive tool names such as `create_file`, `patch_file`, `delete_file`, `search_files`, `git_commit`, and `compile`.

Why this is debt:

- T3's useful pattern is contract-first thread/environment read models with scoped stores/controllers. Current GUI still adapts a backend-shaped event stream inside the frontend.
- Hard-coded tool names in frontend state preserve stale product vocabulary and bypass backend capability metadata.
- Synthetic frontend interaction events show that the backend stream is not yet the single session activity contract.

Target design:

- Define one backend-owned T3-shaped session stream contract for turn, step, tool, interaction, command, compaction, and transition events.
- GUI should consume that contract directly in `session-runtime/activity-state.js` and transport modules.
- Tool presentation and invalidation behavior should come from tool metadata, for example `result_renderer_key`, `progress_renderer_key`, and `invalidates: ["workspace_tree"]`, not frontend hard-coded tool-name sets.
- Continue moving API orchestration out of `App.jsx` into app/session controllers.
- Remove stale tool label fallbacks once the backend catalog provides all active labels.

Acceptance checks:

- Permission and user-input requests arrive as normal session activity stream items, not frontend-synthesized session events.
- Workspace tree refresh is driven by backend/tool metadata, not by a frontend list containing inactive mutation tools.
- Root store no longer owns session timeline mechanics directly; focused runtime modules own thread/activity/transport state.
- GUI tests assert absence of removed tool names in product source, not only in generated static assets.

### P1. Backend/frontend activation is still split across several read paths

Current state:

- Session activation uses `/api/sessions/{id}/bootstrap`, then GUI controllers load tasks, artifacts, permission context, terminal summaries, source-control data, and file children through separate paths.
- Some split paths are app-shell surfaces and can remain lazy, but session/workflow truth must not leak into parallel frontend-owned state.
- `SessionHistoryAssembler.build()` returns both `activities` and structured diagnostics; GUI normalization still contains broad snake/camel and legacy fallback handling.

Why this is debt:

- The cleanup removed old timeline truth, but the GUI still compensates for multiple payload shapes.
- T3 parity should make the session bootstrap shape the thread shell contract, then lazy app-shell surfaces should be explicit non-core surfaces.

Target design:

- Promote a `ThreadShellBootstrap` style backend contract:
  - session identity and summary
  - current mode/workflow projection
  - activity stream seed
  - active interaction
  - capability/tool presentation snapshot
  - safe runtime diagnostics
- Keep terminal, source control, file tree, preview, and review as explicit app-shell/lazy surfaces.
- Remove old fallback normalizers after backend contracts and tests are updated.

### P2. Compatibility tests still pin shapes that should be deleted pre-release

Current state:

- `manage_todos` appears mainly in tests that assert it is absent, which is acceptable as a deletion guard.
- `test_workflow_prompt_dedupe_ignores_legacy_harness_prompt_kind` still adds a `harness_prompt` message and verifies dedupe behavior.
- Guard tests pin two consecutive bash failures as a stop condition.

Why this is debt:

- Negative deletion guards are useful, but compatibility behavior for old prompt kinds contradicts the pre-release "do not preserve old internal state" rule.
- Tests should pin target architecture, not historic compatibility paths.

Target design:

- Keep absence tests for removed public vocabulary where useful.
- Delete or rewrite tests that require accepting legacy internal prompt kinds.
- Replace loop guard tests with outcome-policy tests matching Pi-style behavior.

### P2. Release evidence remains incomplete

Current state:

- Docs correctly mark real Windows 7/WebView2 bundle smoke evidence and real C/C++ project validation as remaining release-gate work.

Why this matters:

- This is not an architecture rewrite blocker, but it is a release blocker.
- Do not turn intended compatibility into a claim until bundle-local evidence exists.

Target design:

- Keep `scripts/offline-runtime-contract.json` as the single release-gate runtime contract.
- Add evidence records only from real Win7/WebView2 and bundle-local C/C++ smoke runs.

## Cleanup slices

### Slice 1: Permission policy convergence

Work:

- Add failing tests for unknown/`other` tools asking by default.
- Add tests proving built-in categories come from runtime metadata.
- Add tests for `network` and `telemetry` asking by default.
- Move permission category resolution behind a runtime/capability descriptor callback.
- Remove hard-coded built-in tool sets from policy decisions.
- Add `other` as an official ask-by-default category or remove rule aliases/docs that imply it is official.

Done when:

- `permissions.py` no longer owns built-in tool taxonomy.
- Unknown tools cannot fall through to allow.
- GUI permission context category list matches backend policy exactly.

### Slice 2: Pi-style loop continuation and tool outcome policy

Work:

- Introduce a small outcome classification boundary for tool observations.
- Extend continuation facts with latest tool batch/outcome summary instead of raw `guard_stop_reason`.
- Rework `LoopGuard` into a runaway/no-progress detector, or replace it with a narrower `ToolOutcomePolicy`.
- Ensure command/build/test failures are diagnostic outcomes that continue the loop.
- Keep explicit stops: abort, pending interaction, empty provider response, safety fuse, explicit terminate hint.
- Update guard/session history labels so `guard_stop` means real runaway/protocol guard, not ordinary tool failure.

Done when:

- Two failing shell/build commands do not hard-stop a turn.
- Repeated identical no-progress calls are blocked with a clear observation.
- Provider empty response still stops safely.
- Tests describe Pi-style loop semantics.

### Slice 3: Backend session stream contract for T3 GUI

Work:

- Define one typed session activity stream item shape for backend bootstrap and WebSocket events.
- Emit permission/user-input requests as first-class activity items from the backend.
- Add tool presentation and invalidation metadata to tool start/finish payloads.
- Update GUI `socket-message-effects.js` to become a thin dispatcher, then retire compatibility mapping branches.

Done when:

- GUI no longer synthesizes `interaction.created` events for backend permission/user-input messages.
- File-tree refresh uses backend invalidation metadata.
- Active session history and live stream use the same activity item vocabulary.

### Slice 4: GUI store/App split toward T3 structure

Work:

- Move remaining session timeline mechanics out of root `store.js` into `session-runtime/activity-state.js`.
- Move session action APIs from `App.jsx` into focused app/session controllers.
- Keep terminal, source control, workbench, and preview as explicit app-shell surfaces.
- Replace stale fallback tool labels with catalog-provided presentation metadata.

Done when:

- `App.jsx` composes controllers and views rather than owning session orchestration.
- Root reducer does not contain parallel session timeline or transport policy.
- Removed tool names do not appear in product UI label tables.

### Slice 5: Facade slimming after behavior and protocol settle

Work:

- Extract remaining QueryEngine transcript/journal/pending-interaction helpers into existing services.
- Move InProcessAdapter bootstrap/capability/session lifecycle operations behind hosted services.
- Keep the public adapter/query facade stable only where current tests and GUI routes require it.

Done when:

- `QueryEngine` owns session facade responsibilities, not loop, permission, extension, and journal policy.
- `InProcessAdapter` owns runtime wiring and route-facing delegation, not implementation details for each surface.

### Slice 6: Test and documentation sync

Work:

- Delete target-contradicting compatibility tests.
- Keep absence guards for removed public vocabulary.
- Update `docs/permission-model.md`, `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md`, and `docs/implementation-roadmap.md` when slices change source-of-truth behavior.
- Record real Win7/WebView2 and bundle-local C/C++ smoke evidence before release claims.

Done when:

- Tests assert the promoted Pi/T3 architecture.
- Source-of-truth docs and implementation are synchronized in the same change.

## Non-goals

- No compatibility with old timeline/session/prompt shapes.
- No restoration support for stale pre-release transcript variants.
- No Docker, WSL, VS Code, online service, runtime dependency installation, or non-Win7-compatible GUI/runtime dependency.
- No hidden network, telemetry, source-control mutation, or extension execution path inside Agent Core.

## Recommended next implementation order

1. Permission policy convergence.
2. Loop outcome and continuation policy.
3. Backend session stream contract.
4. GUI store/App split.
5. QueryEngine/InProcessAdapter slimming.
6. Release-gate evidence and source-of-truth doc sync.

This order removes the highest-risk safety and workflow bugs first, then stabilizes the backend contract before reshaping GUI state around it.
