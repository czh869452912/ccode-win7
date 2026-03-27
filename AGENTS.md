# AGENTS.md

## Purpose

This file is the project constitution for future agent and contributor work.

It exists to keep implementation decisions aligned with the core constraints of this repository:

- Windows 7 compatibility is mandatory.
- Offline deployment is mandatory.
- Agent Core is the product core, UI is replaceable.
- The initial target is C application software development with a Clang-centered toolchain.

## Read This First

Before making non-trivial changes, read these files in order:

1. `README.md`
2. `docs/overall-solution-architecture.md`
3. `docs/implementation-roadmap.md`

Use `analysis/` as reference material, not as the source of truth for the current design.

## Hard Constraints

- Do not introduce a runtime dependency on Docker, Node.js, VS Code, WSL, or external online services.
- Do not introduce Python syntax or dependencies that require Python 3.9+.
- Target runtime remains Python 3.8 because Windows 7 support is a hard requirement.
- Prefer standard library plus a very small dependency surface.
- Keep the system portable and bundle-friendly for offline deployment.

## Python And Environment Policy

- Primary development environment manager: `uv`
- Required compatibility target: `CPython 3.8`
- Default pinned development interpreter: `3.8.10`
- Runtime packaging target: Python 3.8 embeddable distribution
- If `uv` cannot provide a suitable Python 3.8 interpreter on a given machine, `conda` is the approved fallback

Practical rules:

- Keep `requires-python` within `>=3.8,<3.9`
- Do not use structural pattern matching, `tomllib`, `typing.Self`, or other 3.9+ / 3.10+ features
- New tooling should be checked for Python 3.8 compatibility before adoption

## Implementation Priorities

Build in this order:

1. Core domain model and event model
2. Mode Registry and Agent Harness
3. OpenAI-compatible LLM adapter
4. Tool runtime for file, shell, git, clang, test, coverage
5. Context, memory, permission system
6. TUI / CLI adapters
7. Offline packaging

## Mode System Policy

The supported first-class modes are:

- `ask`
- `orchestra`
- `spec`
- `code`
- `test`
- `verify`
- `debug`
- `compact`

Rules:

- Modes are Core contracts, not UI decorations
- Each mode should have a narrow responsibility
- `ask` is for resolving ambiguity with the user
- `orchestra` is for workflow decomposition and routing
- `code` should not replace `spec` or `test`
- `verify` should own quality gates

## Documentation Maintenance

When changing the project, update the matching document:

- `README.md`
  - Public overview, scope, current status
- `AGENTS.md`
  - Project constitution, development constraints, workflow rules
- `docs/overall-solution-architecture.md`
  - Stable architecture and major design decisions
- `docs/implementation-roadmap.md`
  - Milestones, implementation sequencing, document maintenance plan
- `docs/adrs/*.md`
  - One-off architectural decisions that need historical traceability

If a change alters architecture, workflow, version policy, or operating assumptions, document it in the same change.

## Non-Goals For Early Phases

- No browser automation
- No web search features
- No heavyweight RAG platform
- No plugin marketplace
- No premature multi-agent orchestration framework

Multi-agent support is allowed only through the planned `orchestra`-led evolution path.

