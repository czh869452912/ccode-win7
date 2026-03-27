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
- **The final deliverable must be fully self-contained with zero external dependencies.** This means the bundle must include, without exception:
  - Python 3.8 embeddable distribution
  - All Python third-party packages (vendored)
  - MinGit portable binary
  - ripgrep binary
  - Universal Ctags binary
  - Clang toolchain (statically linked binaries: clang, clang-tidy, clang-analyzer, llvm-profdata, llvm-cov)
  - Any other tool invoked at runtime
- A target machine that has only Windows 7 with no pre-installed software must be able to run the system after unpacking the bundle. If a tool is used at runtime but not included in the bundle, it is a defect.

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

1. Minimum working loop: LLM Adapter + first tool set + CLI (Phase 1)
2. Tool set v1: shell command + git tools (Phase 2)
3. Mode system v1: MODE_REGISTRY dict + tool filtering + switch_mode (Phase 3)
4. Clang toolchain: compile, test, clang-tidy, coverage with static binary bundle (Phase 4)
5. Quality guard layer: context compression, permission system, doom loop guard (Phase 5)
6. TUI / CLI adapters (Phase 6)
7. Offline packaging (Phase 7)

Each phase must end with an end-to-end runnable milestone. Do not proceed to the next phase before the milestone is validated.

## Tool Design Policy

Tool set design is a first-class design concern. Refer to `docs/tool-design-spec.md` for the complete specification.

Key rules:

- Each mode must have at most 5 tools (target: 3-4)
- Tool descriptions must follow the template: Chinese description + English name, three-sentence structure, parameter includes example
- All parameters must be flattened top-level fields — no nested objects
- Enum values must be in the `enum` field, not embedded in `description`
- All tool results must return structured Observations, not raw terminal text
- Before adding any new tool, go through the checklist in `docs/tool-design-spec.md`

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
- `orchestra` is for workflow decomposition and routing (implement after Phase 3)
- `code` should not replace `spec` or `test`
- `verify` should own quality gates

## Harness Evolution Policy

The Agent Harness must be built incrementally — do not implement TOML configuration or a full state machine before the minimum loop is validated.

Evolution stages:

- Phase 1: No harness — loop has a single hardcoded system prompt
- Phase 3: Python dict (MODE_REGISTRY) + tool filtering function (~100 lines)
- Phase 5: Optional TOML loading as an additive layer on top of the dict structure

Mode switch triggers (Phase 3+):

1. User explicit: message starts with `/mode <name>`
2. LLM tool call: `switch_mode(target)` tool — update current mode, rebuild context with new mode prompt, do not advance the loop

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
- `docs/development-tracker.md`
  - Near-term execution status, current priorities, blockers and risks
- `docs/design-change-log.md`
  - Key design changes, impact scope, related follow-up work
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
