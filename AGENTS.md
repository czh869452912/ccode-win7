# AGENTS.md

## Purpose

This file is the always-loaded project constitution. It keeps non-negotiable implementation, delivery, and documentation rules reachable without duplicating the architecture manuals. Detailed behavior belongs to the authority selected through `docs/README.md`.

The baseline is mandatory: Windows 7 compatibility, offline deployment, Python 3.8, a minimal workflow-neutral Agent Core, and a first-class Clang-centered C/C++ workflow.

## Quick Commands

Use these commands from the repository root unless a command says otherwise.

```bash
# Install dev environment
uv sync

# Run one test node or file during the TDD red/green loop
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py

# Re-run failures from the fast local partition
uv run python scripts/test-suite.py failed

# Run the local pre-push partition
uv run python scripts/test-suite.py pre-push

# Run the complete regular Python partition
uv run python scripts/test-suite.py full

# Run delivery and performance partitions explicitly
uv run python scripts/test-suite.py release
uv run python scripts/test-suite.py performance

# Audit partition collection and forbidden nested pytest execution
uv run python scripts/test-suite.py audit

# Run harness component tests only
uv run pytest tests/ -m harness -v

# Check or fix lint
uv run --locked python scripts/lint.py
uv run --locked python scripts/lint.py --fix

# Full local CI equivalent
make ci

# Build, inspect, and isolate-smoke all six Python distributions
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release
```

The distribution builder is mandatory. Never replace it with raw `uv build --all-packages`; it protects external wheelhouses and cleans only known build artifacts. The checker must pass before installation or archival.

## Hard Constraints

- Runtime Python is strictly `>=3.8,<3.9`. Do not use the walrus operator, `match`, `dict | dict`, or other Python 3.9+ syntax/API assumptions.
- Windows 7 SP1 x64 and offline operation are product requirements, not optional compatibility targets.
- The base product and default C/C++ workflow must start and run with no network and no preinstalled tools.
- The offline bundle must carry Python 3.8 embeddable, vendored Python packages, MinGit portable, Bash from MinGit, ripgrep, Universal Ctags, required LLVM/Clang executables, WebView2 runtime assets, and every other binary invoked at runtime.
- Do not introduce runtime dependencies on Docker, WSL, VS Code, Node.js, or external online services. Node.js is a frontend build-time tool only.
- Use only dependencies declared in the owning `pyproject.toml`; prefer stdlib and a small dependency surface. Never edit `uv.lock` manually.
- Never commit `config/config.json` because it can contain `api_key`. Do not emit prompts, source files, raw tool outputs, credentials, tokens, approval secrets, or permission payloads through telemetry or diagnostics.
- Tests belong under `tests/`, never under `src/`.
- Keep `scripts/offline-runtime-contract.json` aligned with every runtime binary and release gate; do not create a second hard-coded bundle-tool list.
- The project is pre-release. Do not add compatibility scaffolding for retired internal state, reducer, timeline, hook, registry, sanitizer, adapter, or workflow-package shapes. Preserve external constraints, not obsolete internals.

## Read Routing

Before non-trivial work, read `README.md` and `docs/README.md`, then open only the authority for the task:

| Intent | Authority |
|---|---|
| System topology and distribution boundaries | `docs/overall-solution-architecture.md` |
| Agent Core and durable session runtime | `docs/platform/agent-core.md`, `docs/platform/session-runtime.md` |
| C/C++ workflow, tools, permissions, and context | `docs/applications/cpp-workflow.md`, `docs/platform/tools-and-extensions.md`, `docs/platform/permissions-and-context.md` |
| Host/UI protocol and registrable shells | `docs/platform/protocol.md`, `docs/platform/frontend-protocol.md`, `docs/platform/frontend-gui.md`, `docs/platform/frontend-tui.md` |
| Product composition and default registration | `docs/product/composition.md` |
| Packaging, offline delivery, and Win7 acceptance | `docs/product/packaging-and-deployment.md`, `docs/guides/win7-release-runbook.md` |
| Current blockers and open sequencing | `docs/current-status.md`, then `docs/implementation-roadmap.md` |

Use `docs/archive/` and `analysis/` only for historical investigation. Implementation must never require archive reading to discover current behavior.

## Distribution Ownership

| Distribution | Package | Owns | Allowed project dependencies |
|---|---|---|---|
| `embedagent-core` | `embedagent_core` | Public SDK, workflow-neutral turn/session policy and contracts | none |
| `embedagent-protocol` | `embedagent_protocol` | Stdlib-only JSON-safe wire DTOs | none |
| `embedagent-host` | `embedagent_host` | Generic providers, tools, stores, context, and session hosting | exact-matched Core and Protocol |
| `embedagent-composition` | `embedagent_composition` | Dependency-free build-time definition/compiler/export contracts | none |
| `embedagent-workflow-cpp` | `embedagent_workflow_cpp` | Default C/C++ workflow behavior and package metadata | exact-matched Core |
| `embedagent` | `embedagent` | Product bootstrap, composition, CLI, TUI, and GUI | all five lower distributions |

Dependency direction is lower distributions toward the product only. Core never imports Protocol, Host, product, GUI, or workflow packages. Host never imports `embedagent`; product bootstrap injects registries, policies, discovery, and the selected extension manager into Host. GUI/TUI contracts and shell behavior are generic; product configuration, default registration, launcher selection, and delivery assets stay in the product. C/C++ behavior stays in the workflow package.

Offline export must build and validate exactly these six wheels, install project distributions wheel-only with network resolution disabled, stage the product under `app/embedagent`, and keep other distributions under `runtime/site-packages`. Editable links or a duplicate product package in `runtime/site-packages` are release defects.

## Architecture Invariants

- `Agent` / `AgentSession` are the public standalone Core SDK; `run_agent` is the low-level primitive. `AgentSession` is the durable transaction handle.
- Internal `SessionTransaction` owns leased restore-dispatch-project. `SessionJournal` preflights and appends through `SessionLogPort` before `SessionReducer` changes live state; restore folds the same event families through the same reducer.
- `AgentKernel` plans only context, provider, and tool effects. `AgentLoop` is the commit-execute-resume driver. `AgentToolActionService` owns active-tool checks, hooks, permission, path guards, runtime dispatch, interaction suspension, and workflow patches. `ProgressGuard` uses evidence fingerprints rather than generic repeated-tool counting.
- `HostedSessionController` is the supported Core/Host boundary. Host receives frozen projections and never owns mutable Core `Session`, private `AgentSession` members, or restore policy.
- `AgentPorts` uses focused `ContextAssemblerPort`, `SessionProjectionPort`, `SessionRestorePolicyPort`, `ToolRuntimePort`, and permission collaborators. Do not reintroduce a general service or callback bag.
- `ExtensionManager` and `AgentExtensionHost` are the shared capability and dispatch boundaries. Extensions participate only through declared `ExtensionCapability` records; hook dispatch uses source-aware `AgentEventBus`. Runtime owners must not scatter direct manager calls.
- `SessionEventEnvelope` is the canonical live event DTO. Host creates it once and every UI path forwards the same envelope through the single `session_event` branch.
- `transcript.jsonl` is the only durable hosted session-history ledger; `Session` / `session.turns` are live truth; `SessionHistoryAssembler` serializes history; `/api/sessions/{id}/bootstrap` activates a session. App bootstrap is shell metadata, never session truth.
- Permission decisions and writable-path decisions are separate. Standalone callers provide `AgentPorts.permissions`; default `PermissionPolicy()` allows read and asks for write, execution, network, telemetry, and other. `DenyWritePathPolicy` remains independently authoritative.
- `Session.workflow_state` is the generic workflow carrier. Frontends consume `Session.workflow_state["workflow"]`; C/C++ `TaskGraph` ownership stays behind `CHarnessWorkflowExtension`.
- Turn snapshots, capability/runtime-config/compaction/recovery/experience reducers, workflow package manifests, and frontend capability projections are read models only. They do not execute tools, grant permissions, restore state, or become parallel truth sources. Their detailed contracts live in the routed domain authorities.

## Official Vocabulary

- Modes: `explore`, `spec`, `build`, `debug`, `verify`. `code` is retired.
- Default C/C++ semantics: `mode`, `discipline_profile`, `execution_phase`, `TaskGraph`, `task_status`, and session task snapshots.
- Workflow-neutral tools: `read_file`, `list_dir`, `glob_files`, `grep_text`, `write_file`, `edit_file`, `author_local_capability`, `bash`, and `ask_user`.
- C/C++ workflow tools: `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, and `task_status`; the workflow extension, not Core mode schema, activates them.
- Tool schemas come only from `ToolRuntime.schemas_for(...)` with explicit active names from the shared extension boundary. Runtime catalog metadata owns permission category, preview arguments, changed paths, and read-model invalidations.
- C/C++ pack truth lives only in `embedagent_workflow_cpp.packs`.
- Retired without aliases: `QueryEngine`, `SessionRestorer`, mutable Host `Session`, `ExecutionTracer`, `CircuitBreaker`, `HarnessStateSynchronizer`, per-event callbacks, frontend event translation layers, `embedagent.tooling`, and `embedagent.workflow_packages`.
- Singleton-like access uses `get_mode_registry()`, `get_command_sanitizer()`, and `get_inprocess_adapter()`. Never recreate removed proxy aliases or forwarding facades.
- Local self-extension is workspace-bound file resources plus enabled, manifest-gated project Python extensions. No remote registry, runtime dependency installation, online install, marketplace, built-in tool replacement, or general multi-agent orchestration.
- Optional intranet Git, custom providers, and telemetry remain trusted, explicit, disableable adapters outside Core and pass normal `network` or `telemetry` permission checks.

## Delivery And Verification Gates

For GUI, Agent Core, permission, extension, workflow-package, or frontend-protocol changes, run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
```

From `src/embedagent/frontend/gui/webapp`, run `npm test` and `npm run build`. Commit generated static assets under `src/embedagent/frontend/gui/static/` whenever webapp source changes.

For distribution or delivery changes, run the six-wheel build/check/smoke commands and `scripts/package.ps1 release`. Release internally runs dependency preparation, assembly, and verification; `doctor` is the standalone preflight.

No local or hosted CI result proves Windows 7 delivery. A release claim requires real clean-machine Win7/WebView2 bundle evidence validated by the release evidence scripts.

## Documentation Rules

- Update the one owning platform, application, product, contract, workflow, or ADR document; entry files route and do not duplicate detail.
- Replace current status in place. Do not append completion diaries, progress ledgers, or verification chronicles to active authorities.
- A temporary slice stays in `docs/superpowers/` only while an acceptance condition is open. On closure, synchronize durable truth, then move the slice into an indexed `docs/archive/<topic>/` package.
- New durable architecture rationale belongs in an ADR. Historical narrative belongs only in archive.
- Keep paths, commands, public names, distribution boundaries, and constraints mechanically checkable. Update `docs/references/code-doc-matrix.md` when ownership changes.
