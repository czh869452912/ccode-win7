# Post-Phase 4 Agent Core, GUI, And Delivery Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:writing-plans` to refine each phase into an execution plan, then use `superpowers:executing-plans` or `superpowers:subagent-driven-development` for implementation. Each phase is independently testable and must be merged before the next dependent phase starts.

**Goal:** Move the merged Phase 4 baseline from adapted T3 parity toward a durable Pi-style Agent Core, a native T3-shaped GUI runtime, and evidence-backed Windows 7/offline delivery without weakening Python 3.8, offline, or C/C++ constraints.

**Architecture:** Phase 5 reduces remaining duplicate session/timeline truth and thins hosted orchestration while preserving the public `Agent` / `AgentSession` facade. Phase 6 makes the GUI consume versioned Agent App Protocol projections through T3-shaped runtime boundaries. Phase 7 proves the one-folder bundle on a clean Windows 7/WebView2 109 target; Phase 8 proves real C/C++ workflows; Phase 9 is optional enterprise integration outside Core and is gated by product demand.

**Tech Stack:** Python 3.8, uv six-distribution workspace, stdlib-first Core/Protocol, Host adapters, React 18, Vite 5, Node test harness, pywebview/WebView2 109, Playwright visual harness, bundled MinGit/ripgrep/Universal Ctags/LLVM.

---

## Baseline And Sequencing

Phase 4 is merged at `main` commit `e1a45384`. It established the T3 parity ledger, an isolated GUI Agent App Protocol adapter, a client-runtime reducer, capability-driven T3 workbench surfaces, dynamic base/specialized Agent fixtures, and the renderer hardcoding guard.

The pre-release debt audit still identifies four material gaps:

- `Session` and restore remain partly imperative instead of one durable-log projection graph.
- Timeline transport still has enough persistence/query behavior to become a second history truth.
- `QueryEngine` and `InProcessAdapter` still carry residual orchestration/projection knowledge.
- The GUI is T3-shaped but remains an adapted EmbedAgent app rather than a fully native T3 runtime structure.

The order below is intentional:

1. Phase 5 changes Core/session ownership without changing GUI layout.
2. Phase 6 consumes the stabilized protocol and removes remaining GUI runtime coupling.
3. Phase 7 proves the packaged runtime on the actual Win7/WebView2 envelope.
4. Phase 8 uses that bundle to validate real C/C++ projects and workflow quality.
5. Phase 9 is deferred and optional; it cannot become a prerequisite for offline operation.

Every phase uses a dedicated worktree, focused tests before implementation, one or more small commits, the full architecture gate, and a phase closeout record before merge.

## Phase 5: Durable Session Projection And Core Thinning

**Objective:** Make the durable session log the authoritative source for live session/read models and remove residual orchestration from `QueryEngine`/`InProcessAdapter` without changing public Core contracts.

**Primary areas:**

- `packages/embedagent-core/src/embedagent_core/session.py`
- `packages/embedagent-core/src/embedagent_core/session_restore.py`
- `packages/embedagent-core/src/embedagent_core/session_snapshot.py`
- `packages/embedagent-core/src/embedagent_core/agent_loop.py`
- `packages/embedagent-core/src/embedagent_core/agent_tool_action.py`
- `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- `src/embedagent/session_operation_log.py`
- `src/embedagent/timeline_store.py` and any remaining timeline consumers
- `tests/test_session_restore.py`, `tests/test_session_history.py`, `tests/test_agent_core_public_api.py`, `tests/test_gui_protocol_projection.py`

**Slices:**

1. Inventory every durable read/write of transcript, timeline, live `Session`, and restore state. Add architecture guards that distinguish transcript-backed projections from ephemeral event transport.
2. Extend the reducer graph for live session state, workflow state, pending interaction state, operation state, runtime configuration, compaction, recovery, and turn experience. Restore only a trusted durable prefix and mark unfinished operations interrupted.
3. Demote timeline to an ephemeral/replay transport. Build bootstrap, history, review evidence, and diagnostics from transcript-backed projections; delete timeline-only product queries and compatibility serializers.
4. Route pending permission, user-input, and mode-switch actions through `AgentToolActionService` and the normal lifecycle/action pipeline. Delete duplicate QueryEngine forwarding wrappers after callers migrate.
5. Split remaining hosted projection helpers from runtime ownership in `InProcessAdapter`; keep command, interaction, review, and GUI projection ownership in their existing hosted services.

**Exit criteria:**

- A Core session can restore from transcript/log entries without timeline availability.
- No product history or review path treats timeline storage as authoritative.
- Pending interactions, resumed actions, permissions, hooks, lifecycle events, and replay use one action pipeline.
- `QueryEngine` remains an internal facade and no new public integration path or compatibility wrapper is added.
- Core/Host architecture guards, restore fault-injection tests, focused GUI protocol tests, full non-GUI tests, and lint pass.

**Explicit non-goals:** no GUI redesign, no new provider, no network dependency, no public HookBus API, and no preservation of pre-release internal state formats.

## Phase 6: Native T3 GUI Runtime And Protocol Convergence

**Objective:** Turn the Phase 4 T3-shaped GUI into a protocol-driven client runtime whose components do not know Agent Core, Host, workflow package, or built-in tool names.

**Primary areas:**

- `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- `src/embedagent/frontend/gui/backend/` protocol route/serializer modules
- `src/embedagent/frontend/gui/webapp/src/App.jsx`
- `src/embedagent/frontend/gui/webapp/src/client-runtime/`
- `src/embedagent/frontend/gui/webapp/src/app-shell/`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/`
- `src/embedagent/frontend/gui/webapp/src/workbench/`
- `src/embedagent/frontend/gui/webapp/test/`
- `tests/test_gui_protocol_projection.py`, `tests/test_gui_app_shell.py`, and new Agent matrix tests

**Slices:**

1. Freeze four versioned GUI contracts: Agent Session Protocol, Capability Protocol, IDE Service Protocol, and App Shell Protocol. Validate envelopes, unknown values, missing descriptors, and sequence/revision metadata at the Python/JavaScript boundary.
2. Finish the T3 runtime decomposition: app-shell controller, thread/session controller, workbench store, composer store, terminal UI store, and right-panel store. `App.jsx` composes controllers and views rather than owning route calls or unrelated reducers.
3. Make one unchanged GUI connect to empty/base, bundled C/C++, Python/HTML, and an injected project-local specialized Agent. Capability-driven commands, surfaces, mode labels, empty-state copy, tool presentation, and workflow summary must all come from payloads.
4. Re-baseline against the current `reference/t3code` commit before each slice. Port only applicable UX/client-runtime changes; explicitly classify cloud, Relay, Electron, mobile, remote-environment, and marketplace changes as excluded.
5. Run desktop and narrow viewport visual regression through WebView2-compatible CSS/DOM behavior. Keep generated assets as explicit release artifacts and keep dev fixtures outside production reducers.

**Exit criteria:**

- No production renderer source contains C/C++/Clang or built-in workflow tool-name branches.
- Missing mode/workflow/product names remain empty; unknown tools/activities/surfaces degrade safely.
- The same committed GUI build works with base, specialized, and non-C Agent capability fixtures without React source changes.
- `npm test`, `npm run build`, protocol/app-shell/Agent matrix tests, architecture guards, and Playwright responsive/timeline/file/diff/terminal/source-control scenarios pass.

**Explicit non-goals:** no React 19, Node 24, Electron, cloud authentication, Relay, remote workspaces, online registry, or Agent-provided executable UI code.

## Phase 7: Offline Bundle And Windows 7/WebView2 Delivery Evidence

**Objective:** Prove that the one-folder offline bundle starts and runs the default workflow on a clean Windows 7 SP1 x64 target with the fixed WebView2 109 runtime.

**Primary areas:**

- `scripts/package.ps1`
- `scripts/prepare-offline.ps1`
- `scripts/build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`
- `scripts/check-bundle-dependencies.py`
- `scripts/offline-runtime-contract.json`
- `scripts/validate-cpp-smoke.py` and `scripts/validate-gui-smoke.*`
- `docs/guides/win7-preflight-checklist.md`
- `docs/evidence/win7/` (new immutable run records)

**Slices:**

1. Build all six project wheels, inspect the exact dependency DAG, install wheel-only with network resolution disabled, and verify product/runtime staging has no editable links or duplicate product package.
2. Assemble a release-profile one-folder bundle with manifest, checksums, licenses, bundled Python 3.8, MinGit, ripgrep, Universal Ctags, LLVM/Clang, WebView2 109 runtime, launcher scripts, and no system-tool fallback in release gates.
3. Run build-host checks: `package.ps1 doctor`, `package.ps1 release`, `validate-offline-bundle.ps1 -RequireComplete`, `check-bundle-dependencies.py`, isolated Python distribution smoke, bundle-local C smoke, and GUI smoke harness.
4. On a clean Windows 7 SP1 x64 machine/VM, unpack without administrator rights and run CLI, TUI, GUI, tool version checks, C smoke, first workspace/session creation, permission prompt, resume, and clean shutdown. Record OS/runtime/bundle hashes and results.
5. Classify every failure as bundle asset, Win7 runtime, WebView2, launcher, permission, model-service configuration, or workflow defect; fix only in the owning layer and rerun the full checklist.

**Exit criteria:**

- The bundle starts without preinstalled Python/Git/LLVM/Node/Docker/WSL.
- `runtime_source == "bundle"` for C smoke and release profile disallows system fallback.
- GUI starts with fixed WebView2 109 and passes the target-machine smoke flow.
- A dated, reproducible evidence record is committed for the tested bundle; no release claim relies only on developer-machine tests.

**Explicit non-goals:** no online installer, runtime dependency installation, target-machine auto-update, or network requirement.

## Phase 8: Real C/C++ Workflow And Long-Run Validation

**Objective:** Validate the independently exported default C/C++ workflow against representative real projects and long-running failure/recovery behavior.

**Primary areas:**

- `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/`
- `src/embedagent/workflow_packages/c_cpp/`
- `packages/embedagent-host/src/embedagent_host/runtime/`
- `data/workspace-template/`
- `tests/test_c_cpp_workflow_*.py`, `tests/test_query_engine_*.py`, `tests/test_session_restore.py`
- `docs/evidence/cpp/` (new validation records)

**Slices:**

1. Define a fixed local project matrix covering CMake, Make, and Ninja where available, clean/build/test/diagnostic/quality flows, missing-tool behavior, and workspace escape attempts.
2. Validate recipe discovery and normalization through workflow-owned metadata, then validate Clang compiler, clang-tidy, coverage, and diagnostic evidence through generic payload fields.
3. Run long turns with permission requests, tool failures, compaction, interruption, resume, recovery markers, and no-progress guard behavior; verify no duplicate tool execution or transcript corruption.
4. Run the same GUI and protocol matrix against the C/C++ package and a profile-only base Agent to prove specialization remains outside Core/GUI.
5. Record project/toolchain versions, commands, expected evidence, and results in durable validation documents; add regression fixtures only for deterministic, offline behavior.

**Exit criteria:**

- Representative local C/C++ projects complete the supported workflow or fail with actionable diagnostics.
- Recipe, quality, evidence, task, permission, compaction, and recovery behavior remains workflow-package-owned and protocol-generic.
- No system tool fallback appears in release-profile evidence.
- Repeated long-run tests show deterministic restore and no duplicate non-idempotent tool execution.

## Phase 9: Optional Trusted Enterprise Adapters

**Entry condition:** Only start this phase after Phase 7 delivery evidence and Phase 8 real-project validation pass, and only for a concrete product requirement.

**Objective:** Add optional intranet Git, custom service/provider gateway, organization-local catalog, or passive telemetry without thickening Core or making offline mode dependent on them.

**Rules and slices:**

1. Define a hosted adapter/provider manifest with source metadata, explicit enablement, timeout, retry/fallback, health/read-model fields, and `network`/`telemetry` permission categories.
2. Keep credentials and network clients in Host/product adapters; Core receives only safe typed requests/events and reducer-backed read models.
3. Add offline absence tests, permission-denial tests, timeout/failure degradation tests, redaction tests, and source/provenance diagnostics tests before any live integration.
4. Make GUI capability descriptors show availability and failure state without synthesizing controls or policy; default offline C/C++ behavior must be unchanged when the adapter is absent.

**Exit criteria:**

- Removing or disabling every enterprise adapter leaves the default offline bundle functional.
- No prompt, source file, raw tool output, credential, token, or approval secret enters telemetry/diagnostics.
- No remote registry, marketplace, runtime dependency install, built-in tool replacement, or multi-agent orchestration is introduced.

## Cross-Phase Gate And Merge Protocol

Each phase must produce a small closeout record containing:

- source-of-truth docs and reference commits used;
- changed ownership boundaries and explicit non-goals;
- focused tests and exact commands;
- full architecture/lint/regression results;
- generated asset or bundle evidence where applicable;
- known residual risks and the next phase entry condition.

Required repository gate before every merge:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -q
uv run --locked python scripts/lint.py
```

GUI phases additionally require:

```powershell
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../..
```

Phase 7 additionally requires clean-target Win7/WebView2 evidence. Phase 8 additionally requires the real-project C/C++ matrix. Phase 9 additionally requires an explicit product decision and offline absence proof.

## Immediate Recommendation

Start with **Phase 5A: durable session projection inventory and timeline demotion** as the next independently reviewable slice. Do not begin Phase 6 GUI decomposition until Phase 5 has a passing restore/history contract, because otherwise the GUI would stabilize against the wrong session truth. After Phase 5, execute Phase 6 in small T3-rebaselined slices, then schedule Phase 7 target-machine validation as the release gate rather than treating it as documentation work.
