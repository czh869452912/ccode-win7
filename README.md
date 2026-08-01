# EmbedAgent

EmbedAgent is a native, offline-first Agent IDE assembled from a reusable workflow-neutral Agent Platform, replaceable upper-layer applications, and product-specific delivery. The packaged default is a Clang-centered C/C++ development workflow. The product must run from a self-contained bundle on Windows 7 with Python 3.8 and without network access or preinstalled developer tools.

## Architecture At A Glance

The repository is a six-distribution uv workspace:

| Distribution | Import package | Ownership |
|---|---|---|
| `embedagent-core` | `embedagent_core` | Dependency-free Agent SDK, session transaction, event/reducer, kernel, loop, permissions, and public contracts |
| `embedagent-protocol` | `embedagent_protocol` | Stdlib-only JSON-safe Host/UI DTOs |
| `embedagent-host` | `embedagent_host` | Generic providers, local services, tools, stores, context, and hosted sessions |
| `embedagent-composition` | `embedagent_composition` | Dependency-free build-time definition/compiler/export contracts |
| `embedagent-workflow-cpp` | `embedagent_workflow_cpp` | Independently exported default C/C++ workflow package |
| `embedagent` | `embedagent` | Product bootstrap plus CLI, TUI, and GUI shells |

```text
embedagent-core --------> embedagent-host --------\
        |                       ^                  \
        +--> embedagent-workflow-cpp                > embedagent
embedagent-protocol ----> embedagent-host --------/
embedagent-composition --------------------------/
```

Core, Protocol, Composition, and the C/C++ workflow never import the product. Host depends only on exact-matched Core and Protocol distributions. Product composition injects workflow packages and product registries into Host.

## Quick Commands

```bash
# Install the development environment
uv sync

# TDD, failed-test replay, and local partitions
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py
uv run python scripts/test-suite.py failed
uv run python scripts/test-suite.py pre-push
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py release
uv run python scripts/test-suite.py performance
uv run python scripts/test-suite.py audit

# Lint and full local CI
uv run --locked python scripts/lint.py
uv run --locked python scripts/lint.py --fix
make ci

# Build, inspect, and isolate-smoke all six distributions
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

```powershell
# Offline packaging preflight and release
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release
```

The distribution builder is the required release entry point; do not replace it with raw `uv build --all-packages`. The checker must pass before wheels are installed or archived.

## Documentation Map

- Start with [`docs/README.md`](docs/README.md) and route by intent.
- Read [`docs/current-status.md`](docs/current-status.md) for replace-in-place state and blockers.
- Read [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md) for open programs and ordering.
- Read [`docs/overall-solution-architecture.md`](docs/overall-solution-architecture.md) for durable system topology.
- Read [`docs/platform/README.md`](docs/platform/README.md) for the reusable Agent foundation and registrable shells.
- Read [`docs/applications/README.md`](docs/applications/README.md) for upper-layer workflows.
- Read [`docs/product/README.md`](docs/product/README.md) for EmbedAgent composition and delivery.
- Read [`docs/guides/configuration-guide.md`](docs/guides/configuration-guide.md) for configuration.
- Read [`docs/guides/win7-release-runbook.md`](docs/guides/win7-release-runbook.md) for target-machine acceptance.
- Use [`docs/archive/README.md`](docs/archive/README.md) only for historical investigation.

`AGENTS.md` is the compact contributor constitution. Platform, application, product, and contract authorities own implementation detail; entry documents only route to them.

## Release Evidence

Repository-side release state is `TARGET_READY` with `acceptance_status=PENDING_WIN7` and `publishable=false`. A release claim requires hash-bound evidence from a clean Windows 7 SP1 x64 machine running the packaged GUI with bundled Fixed Version WebView2 109, plus bundle-local C smoke. Local tests, hosted Windows CI, and development-machine bundle smoke do not replace that evidence.

## Scope

EmbedAgent is not a cloud coding service, public plugin marketplace, remote extension registry, or general multi-agent orchestrator. Docker, WSL, VS Code, external online services, and runtime Node.js are not product dependencies. Optional intranet providers, Git sources, or telemetry sinks must remain explicit, disableable, permission-checked, failure-tolerant adapters outside Agent Core; the default C/C++ workflow remains fully offline.
