# Independent Agent Core First Milestone Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an independently installable Agent Core and deterministically assemble the existing C/C++ product from external Host, workflow, and composition packages.

**Architecture:** Execute four sequential vertical plans. Each plan ends with a runnable product and a stricter dependency gate. Do not start the next plan until the preceding plan is merged and its verification commands pass from a clean worktree.

**Tech Stack:** Python 3.8, setuptools, uv workspaces, pytest, existing React/Vite GUI tests, PowerShell offline packaging, JSON manifests and lock records.

---

## Source Design

Read the approved design before executing any plan:

- `docs/superpowers/specs/2026-07-11-independent-agent-core-and-adaptive-gui-design.md`

The earlier boundary design remains useful historical context, but this
milestone follows the 2026-07-11 design when the documents differ.

## Plan Order

1. `2026-07-11-core-public-api-and-neutral-runtime.md`
   - establish the public SDK and low-level runner;
   - promote restore and session-log contracts into Core;
   - remove implicit `chat`, mode, and auto-approval defaults;
   - route hosted user turns and interaction replies through `AgentSession`.

2. `2026-07-11-python-distribution-split.md`
   - create the uv workspace and separate wheels;
   - move Core, Protocol, and Host sources into their owning distributions;
   - move Host-owned concrete runtime services out of the product namespace;
   - prove isolated Python 3.8 installation and imports.

3. `2026-07-11-cpp-workflow-distribution.md`
   - move all C/C++ specialization into `embedagent-workflow-cpp`;
   - replace central profile-kind and builder-path construction with trusted
     package registration;
   - preserve the complete default C/C++ workflow.

4. `2026-07-11-deterministic-agent-composition.md`
   - implement the frozen component catalog and compiler;
   - generate `agent.json`, `agent.lock.json`, and export reports;
   - export a base wheel set and C/C++ portable bundle deterministically.

## Cross-Plan Invariants

- Python syntax remains compatible with 3.8.
- No new runtime dependency is added to Core.
- `uv sync` and the documented root test commands remain valid after every
  plan.
- Core never imports Host, product, GUI, protocol, or workflow packages.
- Host never imports C/C++ workflow code after Plan 3.
- Missing workflow and mode remain empty; no layer invents `chat` or `explore`
  for a base agent.
- Permission requirements never grant permission. Standalone defaults are ask
  or deny.
- Exactly one extension manager and one runtime tool catalog serve an agent.
- Manifest data never executes code or contains credentials.
- Runtime installation never downloads components or dependencies.
- Old internal paths are deleted when their replacement is promoted.

## Milestone Verification

Run after Plan 4 from the repository root:

```bash
uv sync
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
uv build --all-packages
uv run python scripts/check-python-distributions.py --dist-dir dist
```

Run from `src/embedagent/frontend/gui/webapp` until the GUI package moves:

```bash
npm test
npm run build
```

Run the two product export smokes:

```bash
uv run python -m embedagent_composition export products/base-agent.json --output build/exports/base
uv run python -m embedagent_composition export products/cpp-agent.json --output build/exports/cpp
uv run python scripts/smoke-exported-agent.py build/exports/base --expect-agent embedagent.base
uv run python scripts/smoke-exported-agent.py build/exports/cpp --expect-agent embedagent.default_c_cpp
```

Expected:

- all commands exit zero;
- the base export contains no C/C++ workflow wheel or LLVM assets;
- the C/C++ export contains the declared workflow wheel and all assets required
  by `scripts/offline-runtime-contract.json`;
- `git status --short` is empty after generated build outputs are removed by
  their normal cleanup command or remain under ignored build directories.

## First Milestone Exit Criteria

- `embedagent-core` installs by itself on Python 3.8.
- `from embedagent_core import Agent` runs a fake-model base session without
  Host, GUI, or C/C++ installed.
- the hosted CLI/TUI/GUI product still runs through the public Core facade.
- `embedagent-workflow-cpp` is a separate wheel selected only by product
  composition.
- base and C/C++ exports have deterministic lock records and asset closures.
- no compatibility import aliases or duplicate managers remain.
