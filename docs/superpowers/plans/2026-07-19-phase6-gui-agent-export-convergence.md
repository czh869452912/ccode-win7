# Phase 6 GUI And Agent Export Convergence Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete the next architecture slice by making the GUI a versioned, T3-shaped client runtime and adding deterministic build-time export of generic and workflow-specialized Agents without weakening the existing Core, offline, Python 3.8, or Windows 7 boundaries.

**Architecture:** Phase 6 keeps the current React 18/Vite 5/PyWebView/WebView2 109 shell and moves remaining GUI state behind four JSON-safe protocol contracts. The renderer consumes only normalized capabilities, snapshots, ordered events, and service results. A real embedagent-composition compiler is added as a dependency-free build-time layer: trusted catalogs compile base or workflow-specialized Agent definitions into manifest, lock, and export-report artifacts; runtime activation remains owned by Host and Core.

**Tech Stack:** Python 3.8, stdlib-only embedagent-composition, embedagent-protocol, React 18, Vite 5, Node test harness, existing GUI controller/runtime modules, pytest, Ruff, Black, architecture guards, and the pinned reference/t3code checkout at 2318e00270203780b72efbbcffce92e907312027.

---

## Scope And Boundaries

Phase 6 includes:

- four versioned GUI contracts: Agent Session, Capability, IDE Service, and App Shell;
- T3-shaped client runtime convergence in the existing React/Vite shell;
- unchanged-GUI Agent matrix coverage for empty, generic, C/C++, Python/HTML, and injected project-local specialized Agents;
- deterministic build-time Agent composition and export for fixed wheel sets and declared offline assets;
- production removal of visual-debug fixture imports and remaining renderer-specific Agent literals;
- current T3 re-baselining, responsive/visual regression, and phase closeout evidence;
- source-of-truth documentation alignment for the new Phase 6 scope.

Phase 6 does not include:

- clean Windows 7 target-machine smoke or final WebView2 evidence;
- representative real C/C++ project validation and long-run workflow evidence;
- online registries, marketplaces, runtime dependency installation, arbitrary JavaScript plugins, or remote extension discovery;
- React 19, Node 24, Electron, Relay, cloud authentication, mobile surfaces, or remote workspaces;
- moving policy, workflow execution, permissions, transcript truth, or tool implementation into the renderer.

## File Map

Existing files to modify:

- src/embedagent/frontend/gui/backend/protocol_payloads.py — JSON-safe backend projections and protocol version metadata.
- src/embedagent/frontend/gui/backend/app_shell.py — app-shell descriptor version and capability envelope.
- src/embedagent/frontend/gui/backend/routes_app.py and src/embedagent/frontend/gui/backend/routes_sessions.py — route responses through the single protocol serializer boundary.
- src/embedagent/frontend/gui/webapp/src/App.jsx — composition root only; no route calls, workflow branches, or domain reducers.
- src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-controller.js — optional injected debug hook with no production fixture import.
- src/embedagent/frontend/gui/webapp/src/app-shell/, src/embedagent/frontend/gui/webapp/src/session-runtime/, and src/embedagent/frontend/gui/webapp/src/workbench/ — normalized protocol state and domain controllers.
- src/embedagent/frontend/gui/webapp/test/ — contract, reducer, and capability matrix tests.
- scripts/gui-visual-debug.mjs — development-only fixture injection.
- packages/embedagent-composition/src/embedagent_composition/__init__.py — public composition exports.
- docs/implementation-roadmap.md, docs/development-tracker.md, and docs/modules/packaging-and-deployment.md — canonical phase and six-wheel wording.

Files to create:

- packages/embedagent-composition/src/embedagent_composition/model.py — frozen component and product-definition DTOs.
- packages/embedagent-composition/src/embedagent_composition/catalog.py — trusted component registration and freeze validation.
- packages/embedagent-composition/src/embedagent_composition/compiler.py — deterministic definition compilation and lock construction.
- packages/embedagent-composition/src/embedagent_composition/export.py — manifest, lock, export report, and declared asset closure writer.
- packages/embedagent-composition/src/embedagent_composition/errors.py — stable validation error types and error codes.
- src/embedagent/frontend/gui/backend/protocol_versions.py — four protocol version constants and envelope validation helpers.
- src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-envelope.js — frontend envelope normalization and unknown-value handling.
- tests/test_agent_composition.py — compiler/catalog/export contract tests.
- tests/test_gui_agent_matrix.py — backend capability matrix tests.
- src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs — frontend protocol envelope tests.
- src/embedagent/frontend/gui/webapp/test/agent-capability-matrix.test.mjs — unchanged-renderer capability fixture tests.
- docs/superpowers/plans/2026-07-19-phase6-closeout.md — execution closeout and verification record after all tasks pass.

---

## Task 1: Freeze The Phase 6 Contracts And Baseline

Files:
- Create: src/embedagent/frontend/gui/backend/protocol_versions.py
- Create: src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-envelope.js
- Modify: src/embedagent/frontend/gui/backend/protocol_payloads.py
- Modify: src/embedagent/frontend/gui/backend/app_shell.py
- Test: tests/test_gui_protocol_projection.py
- Test: src/embedagent/frontend/gui/webapp/test/protocol-envelope.test.mjs
- Modify: docs/guides/t3-gui-parity-ledger.md

- [ ] Step 1: Add failing Python contract tests.

Add tests for four named protocol versions, required envelope fields (protocol, version, sequence, revision, payload), empty/missing descriptors, and rejection of malformed sequence/revision values. Assert that protocol DTOs contain no credentials, prompt bodies, source contents, raw tool output, or permission secrets.

- [ ] Step 2: Run the focused Python tests and confirm failure.

    uv run pytest tests/test_gui_protocol_projection.py -k "protocol or envelope or version" -v

Expected: FAIL because the version constants and envelope validator do not yet exist.

- [ ] Step 3: Implement the version constants and envelope validation.

Define Python 3.8-compatible constants:

    AGENT_SESSION_PROTOCOL = "agent_session_v1"
    CAPABILITY_PROTOCOL = "capability_v1"
    IDE_SERVICE_PROTOCOL = "ide_service_v1"
    APP_SHELL_PROTOCOL = "app_shell_v1"

Add one validator that accepts only JSON-safe mappings, preserves unknown payload fields under payload, requires non-negative integer sequence and non-empty string revision, and returns structured diagnostics instead of importing runtime policy classes.

- [ ] Step 4: Add the matching JavaScript normalizer and tests.

Normalize missing protocol metadata to an invalid envelope result, preserve unknown activity/tool/surface kinds as generic records, and never synthesize product, mode, or workflow names. Keep the normalizer independent of HTTP route names.

    cd src/embedagent/frontend/gui/webapp
    npm test -- protocol-envelope
    cd ../../../..

Expected: the new envelope tests pass.

- [ ] Step 5: Rebaseline the T3 ledger.

Record the pinned T3 commit and classify each changed path as UX, client runtime, protocol, or intentionally excluded infrastructure. Do not import T3 dependencies or copy cloud/desktop/mobile/remote behavior.

- [ ] Step 6: Commit the contract slice.

    git add src/embedagent/frontend/gui/backend src/embedagent/frontend/gui/webapp/src/session-runtime src/embedagent/frontend/gui/webapp/test tests/test_gui_protocol_projection.py docs/guides/t3-gui-parity-ledger.md
    git commit -m "feat: freeze versioned GUI protocol envelopes"

---

## Task 2: Close The Single GUI Adapter Boundary

Files:
- Modify: src/embedagent/frontend/gui/backend/protocol_payloads.py
- Modify: src/embedagent/frontend/gui/backend/routes_app.py
- Modify: src/embedagent/frontend/gui/backend/routes_sessions.py
- Modify: src/embedagent/frontend/gui/webapp/src/app-runtime/transport.js
- Modify: src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-controller.js
- Modify: src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js
- Test: tests/test_gui_protocol_projection.py
- Test: src/embedagent/frontend/gui/webapp/test/transport-contract.test.mjs

- [ ] Step 1: Add failing route/transport contract tests.

Assert that bootstrap, WebSocket events, commands, pending interactions, and command results all pass through one normalized envelope. Assert that command results expose structured switch_session_id, log_label, and log_detail fields and that the frontend does not infer them from slash command names.

- [ ] Step 2: Run the focused tests and confirm failure.

    uv run pytest tests/test_gui_protocol_projection.py -k "transport or command or bootstrap" -v
    cd src/embedagent/frontend/gui/webapp
    npm test -- transport-contract
    cd ../../../..

- [ ] Step 3: Route backend responses through the serializer.

Make route handlers construct protocol DTOs and envelopes only; keep Core/Host objects out of JSON serialization. Preserve missing mode/workflow/product values as empty strings. Keep session history sourced from the Phase 5 projection service.

- [ ] Step 4: Route frontend traffic through the adapter.

Make controllers consume normalized envelopes and callbacks. Remove direct route-name checks, slash-command session switching inference, and local event-history reconstruction. Unknown event kinds become generic activity records with safe diagnostics.

- [ ] Step 5: Run tests and commit.

    uv run pytest tests/test_gui_protocol_projection.py tests/test_gui_app_shell.py -v
    cd src/embedagent/frontend/gui/webapp
    npm test
    cd ../../../..
    git add src/embedagent/frontend/gui/backend src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test tests/test_gui_protocol_projection.py
    git commit -m "refactor: route GUI traffic through protocol adapter"

Expected: focused Python and frontend tests pass with no renderer access to backend route names.

---

## Task 3: Finish T3-Shaped Client Runtime Decomposition

Files:
- Modify: src/embedagent/frontend/gui/webapp/src/App.jsx
- Modify/create in existing domains: src/embedagent/frontend/gui/webapp/src/app-shell/, src/embedagent/frontend/gui/webapp/src/session-runtime/, src/embedagent/frontend/gui/webapp/src/workbench/, src/embedagent/frontend/gui/webapp/src/composer/, src/embedagent/frontend/gui/webapp/src/terminal/, src/embedagent/frontend/gui/webapp/src/source-control/
- Test: src/embedagent/frontend/gui/webapp/test/app-composition.test.mjs
- Test: src/embedagent/frontend/gui/webapp/test/client-runtime-reducers.test.mjs

- [ ] Step 1: Add source-shape tests before moving logic.

Assert that App.jsx does not contain fetch(, WebSocket(, route path literals, built-in workflow tool names, C/C++/Clang labels, or domain reducer implementations. Assert that controller modules expose pure state transitions and effect callbacks.

- [ ] Step 2: Run source-shape tests and record the current failures.

    cd src/embedagent/frontend/gui/webapp
    npm test -- app-composition client-runtime-reducers
    cd ../../../..

- [ ] Step 3: Move remaining transitions into domain modules.

Keep App.jsx responsible only for composing controllers/views, activating the current thread, wiring transport, and passing capability-derived props. Move thread activation, command effects, composer submission, terminal actions, right-panel state, source-control state, and activity projection into their existing domain modules.

- [ ] Step 4: Preserve generic behavior while removing policy.

All visible copy, tool labels, surface titles, command labels, and workflow summaries come from normalized capabilities or snapshots. Missing values remain empty; unknown values render generic rows or disappear according to descriptor visibility.

- [ ] Step 5: Run frontend tests and commit.

    cd src/embedagent/frontend/gui/webapp
    npm test
    cd ../../../..
    git add src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test
    git commit -m "refactor: converge T3 client runtime boundaries"

---

## Task 4: Implement Deterministic Agent Composition And Export

Files:
- Create: packages/embedagent-composition/src/embedagent_composition/model.py
- Create: packages/embedagent-composition/src/embedagent_composition/catalog.py
- Create: packages/embedagent-composition/src/embedagent_composition/compiler.py
- Create: packages/embedagent-composition/src/embedagent_composition/export.py
- Create: packages/embedagent-composition/src/embedagent_composition/errors.py
- Modify: packages/embedagent-composition/src/embedagent_composition/__init__.py
- Create: tests/test_agent_composition.py
- Modify: tests/test_python_distribution_contract.py
- Modify: tests/test_packaging_control_plane.py

- [ ] Step 1: Add failing model and compiler tests.

Cover:

- ComponentManifest, ComponentRef, AgentProductDefinition, and CompiledAgentSpec are frozen and JSON-safe;
- duplicate ids, conflicting components, unsupported API versions, undeclared permissions, duplicate tool namespaces, and asset path escapes fail with stable error codes;
- component ordering is deterministic regardless of registration order;
- manifest records never contain executable builder paths or secrets.

- [ ] Step 2: Add failing export tests for base and specialized Agents.

Create temporary wheel/asset fixtures and assert:

- base export includes Core, Host, Protocol, Composition, and declared generic assets but no C/C++ package;
- C/C++ export includes the exact workflow wheel and workflow-owned assets;
- agent.json, agent.lock.json, and export-report.json are reproducible byte-for-byte;
- hashes, versions, source ids, dependency order, and runtime assets are recorded;
- partial export directories are removed on failure without touching paths outside the requested output root.

- [ ] Step 3: Run the new tests and confirm failure.

    uv run pytest tests/test_agent_composition.py -v

- [ ] Step 4: Implement the frozen component catalog.

Use stdlib dataclasses and tuples. Registration is allowed only before freeze(). Freeze validates ids, API versions, dependency/conflict graphs, permission categories, safe relative asset paths, and unique tool/workflow namespaces. Compiled manifests remain non-executing.

- [ ] Step 5: Implement compilation and lock generation.

Compile a fixed AgentProductDefinition into a normalized component order, exact distribution versions, file hashes, declared runtime assets, permission categories, and deterministic ordering. Do not implement a dependency solver or runtime entry-point discovery.

- [ ] Step 6: Implement export reports and public exports.

Write UTF-8 JSON with stable key ordering and newline termination. Export only inside the caller-selected output directory. Expose compile_agent, export_agent, model DTOs, and error types from embedagent_composition.

- [ ] Step 7: Add product definitions without GUI coupling.

Provide trusted definitions for embedagent.generic, embedagent.python, embedagent.html, and embedagent.default_c_cpp. The C/C++ definition references the independently packaged workflow component; the base definitions remain valid without that wheel.

- [ ] Step 8: Run packaging tests and commit.

    uv run pytest tests/test_agent_composition.py tests/test_python_distribution_contract.py tests/test_packaging_control_plane.py -v
    git add packages/embedagent-composition tests
    git commit -m "feat: add deterministic Agent composition exports"

---

## Task 5: Verify The Unchanged GUI Agent Matrix And Remove Production Fixture Imports

Files:
- Create: tests/test_gui_agent_matrix.py
- Create: src/embedagent/frontend/gui/webapp/test/agent-capability-matrix.test.mjs
- Modify: src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-controller.js
- Modify: src/embedagent/frontend/gui/webapp/src/App.jsx
- Modify: scripts/gui-visual-debug.mjs
- Move or rename: src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js to a development-only fixture entry used by the visual harness
- Modify: tests/test_pre_release_architecture_guards.py

- [ ] Step 1: Add failing matrix tests.

Define fixtures for:

- empty Agent with no mode/workflow;
- embedagent.generic;
- embedagent.default_c_cpp;
- embedagent.python;
- embedagent.html;
- injected project-local specialized Agent with a distinct tool, command, surface, and workflow payload.

Assert that all fixtures use the same renderer source and that visible values come only from capability/snapshot payloads.

- [ ] Step 2: Run the matrix tests and record fixture/import failures.

    uv run pytest tests/test_gui_agent_matrix.py tests/test_pre_release_architecture_guards.py -v
    cd src/embedagent/frontend/gui/webapp
    npm test -- agent-capability-matrix
    cd ../../../..

- [ ] Step 3: Remove the production fixture dependency.

Make visual-debug-controller.js accept an injected fixture installer and return a no-op when none is supplied. Remove its static import of visual-debug-fixtures.js from the production renderer path. Update scripts/gui-visual-debug.mjs to provide the fixture installer only for visual-debug sessions.

- [ ] Step 4: Add forbidden-literal guards.

Scan production renderer source, excluding the explicit development-only fixture entry, for C/C++, Clang, built-in workflow tool names, and product fallback branding. Keep generic surface ids, T3 layout constants, and fixture identifiers allowed only in the documented development entry.

- [ ] Step 5: Run matrix, frontend, and visual harness checks.

    uv run pytest tests/test_gui_agent_matrix.py tests/test_gui_protocol_projection.py tests/test_gui_app_shell.py -v
    cd src/embedagent/frontend/gui/webapp
    npm test
    cd ../../../..
    node scripts/gui-visual-debug.mjs --scenario load,chat,diff,timeline,interaction

Expected: the same GUI source renders all matrix fixtures; visual-debug scenarios load only through the explicit development hook.

- [ ] Step 6: Commit the matrix and hardcode-removal slice.

    git add src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/webapp/test scripts/gui-visual-debug.mjs tests
    git commit -m "test: prove unchanged GUI Agent capability matrix"

---

## Task 6: Rebaseline T3 UX And Run The Phase 6 GUI Gate

Files:
- Modify: docs/guides/t3-gui-parity-ledger.md
- Modify: src/embedagent/frontend/gui/webapp/src/components/
- Modify: the existing GUI CSS entry only when a T3 parity difference is recorded
- Test: src/embedagent/frontend/gui/webapp/test/

- [ ] Step 1: Diff the current T3 reference paths.

    git -C reference/t3code log -1 --date=iso --format="%H%n%ad%n%s"
    rg --files reference/t3code/apps/web/src reference/t3code/packages/client-runtime/src reference/t3code/packages/contracts/src

Record only applicable changes in Sidebar, ChatView, Composer, timeline, right panel, terminal, source control, responsive behavior, client runtime, and contracts. Mark cloud, Relay, Electron, mobile, remote, and marketplace changes as excluded infrastructure.

- [ ] Step 2: Add focused behavior tests before each parity change.

Cover narrow viewport stacking, timeline row expansion, composer pending interaction states, right-panel surface activation, terminal drawer state, source-control read-only behavior, and generic unknown activity/tool rendering.

- [ ] Step 3: Port only classified UX/runtime changes.

Keep layout and keyboard constants in the GUI. Keep Agent policy and workflow semantics in backend capability projections. Do not introduce a second shell or T3 dependency graph.

- [ ] Step 4: Run the complete GUI gate.

    cd src/embedagent/frontend/gui/webapp
    npm test
    npm run build
    cd ../../../..
    uv run pytest tests/test_gui_protocol_projection.py tests/test_gui_app_shell.py tests/test_gui_agent_matrix.py -v
    uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
    uv run pytest tests/ -m "not slow and not gui" -v
    uv run --locked python scripts/lint.py

Expected: all focused GUI/backend tests, architecture guards, non-GUI tests, lint, and the production build pass. Generated static assets must be reviewed and committed with source changes.

- [ ] Step 5: Commit the T3 parity slice.

    git add docs/guides/t3-gui-parity-ledger.md src/embedagent/frontend/gui/webapp/src src/embedagent/frontend/gui/static src/embedagent/frontend/gui/webapp/test
    git commit -m "feat: close Phase 6 T3 GUI parity gate"

---

## Task 7: Documentation Alignment And Phase Closeout

Files:
- Modify: docs/implementation-roadmap.md
- Modify: docs/development-tracker.md
- Modify: docs/modules/packaging-and-deployment.md
- Create: docs/superpowers/plans/2026-07-19-phase6-closeout.md

- [ ] Step 1: Normalize the phase vocabulary.

Use the post-Phase 4 route as the canonical active plan: Phase 5 durable session projection is complete; Phase 6 GUI/export convergence is the current phase; Phase 7 is target delivery; Phase 8 is real C/C++; Phase 9 is optional enterprise work. Mark the older Phase 4/5/6/7 table as historical or update it to the same vocabulary rather than leaving two active meanings.

- [ ] Step 2: Correct distribution documentation.

Replace references to five project wheels with six: Core, Protocol, Host, Composition, C/C++ workflow, and product. Document that Composition is now a build-time compiler/export layer and remains absent from the Core runtime dependency graph.

- [ ] Step 3: Write the closeout record.

Record:

- commit ids for every Phase 6 slice;
- T3 reference commit and classified exclusions;
- protocol versions and compatibility behavior;
- Agent matrix results;
- composition export hashes and manifest/lock examples without secrets;
- GUI test/build and architecture gate outputs;
- explicit remaining Phase 7/8 evidence gaps.

- [ ] Step 4: Run the final status check and commit docs.

    git status --short --branch
    git log --oneline -12
    git add docs/implementation-roadmap.md docs/development-tracker.md docs/modules/packaging-and-deployment.md docs/superpowers/plans/2026-07-19-phase6-closeout.md
    git commit -m "docs: close out Phase 6 GUI and Agent export convergence"

---

## Phase 6 Definition Of Done

Phase 6 is complete only when all of the following are true:

- four GUI protocol versions are validated at the Python/JavaScript boundary;
- the renderer has one transport adapter and App.jsx is a composition root;
- missing and unknown capability values degrade safely without invented branding or workflow state;
- one unchanged GUI build passes empty, generic, C/C++, Python/HTML, and injected specialized Agent fixtures;
- embedagent-composition can deterministically export a base Agent and a C/C++ specialized Agent with manifest, lock, report, hashes, and declared assets;
- production renderer source contains no C/C++/Clang/built-in tool branches outside the explicit development fixture entry;
- T3 parity differences are classified against the pinned current reference;
- npm test, npm run build, GUI/backend tests, Agent matrix tests, architecture guards, non-GUI tests, and lint pass;
- active roadmap and packaging docs describe the same phase vocabulary and six-distribution model;
- Phase 7 clean Win7/WebView2 evidence and Phase 8 real C/C++ evidence remain explicitly open and are not claimed by this phase.

## Execution Order And Checkpoints

Tasks must be executed in this order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7.

Each task produces one focused commit. After Tasks 2, 4, and 6, run the architecture gate before starting the next task. Do not begin Phase 7 bundle work until Task 7 has been merged and the six-wheel export path is reproducible locally.

