# Independent Agent And Adaptive GUI Program Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute plans sequentially. Within a plan, use superpowers:subagent-driven-development only for independent tasks and preserve each plan's review checkpoints.

**Goal:** Complete the approved six-phase program from the current mixed product to an independently exportable Agent Core, deterministic specialized agents, and one agent-neutral T3-style GUI shell.

**Source Design:** `docs/superpowers/specs/2026-07-11-independent-agent-core-and-adaptive-gui-design.md`

---

## Execution Order

1. `2026-07-11-core-public-api-and-neutral-runtime.md`
   - public `Agent` / `AgentSession` SDK;
   - functional runner and lease-aware session log;
   - neutral mode/workflow and fail-closed permission defaults;
   - Host adoption of the facade.

2. `2026-07-11-python-distribution-split.md`
   - independent Core, Protocol, Host, and Composition wheels;
   - package import/dependency guards;
   - isolated Python 3.8 wheel smokes.

3. `2026-07-11-cpp-workflow-distribution.md`
   - independent C/C++ workflow wheel;
   - all C/C++ profiles, tools, tasks, recipes, reducers, and detectors moved;
   - no Host/Core/GUI C/C++ import.

4. `2026-07-11-deterministic-agent-composition.md`
   - explicit frozen trusted catalog;
   - graph compilation, lock records, asset closure;
   - deterministic base wheel-set and C/C++ portable exports.

5. `2026-07-11-adaptive-gui-protocol-and-shell.md`
   - independent GUI wheel;
   - separate app-shell, IDE, agent-capability, and session protocols;
   - safe declarative read-only panels;
   - one GUI build proven against base, C/C++, and Python agents.

6. `2026-07-11-legacy-removal-and-release-validation.md`
   - deletion of mixed CoreInterface, application builder, v1 protocol, and
     fallback paths;
   - hardcoding and final dependency gates;
   - isolated exports and real Win7/WebView2 evidence.

Plans are sequential. Do not begin a later plan until the prior plan is merged,
its closeout command set passes, and active architecture documentation reflects
the promoted boundary.

## Milestones

### Milestone 1: Independent Agent Products

Plans 1 through 4. The detailed checkpoint is
`2026-07-11-agent-core-first-milestone-roadmap.md`.

Exit means:

- Core installs and runs without Host, GUI, or C/C++;
- C/C++ is an external workflow wheel;
- base and C/C++ products compile and export deterministically;
- the existing GUI continues to work through Host while protocol separation is
  still pending.

### Milestone 2: Adaptive GUI

Plan 5.

Exit means:

- GUI is an independent wheel with no Core/workflow imports;
- four versioned documents own disjoint truth;
- capabilities change atomically per session;
- base, C/C++, and non-C agents use the same static GUI build;
- agent declarations cannot execute UI code.

### Milestone 3: Release Candidate

Plan 6.

Exit means:

- retired mixed paths and compatibility APIs are absent;
- architecture and hardcoding checkers are clean;
- all wheels and products pass isolated offline smokes;
- the final bundle hash has clean Windows 7 SP1 and WebView2 109 evidence.

## Dependency Direction

```text
embedagent-core <- embedagent-host
embedagent-core <- embedagent-workflow-cpp
embedagent-protocol <- embedagent-host
embedagent-protocol <- embedagent-gui

embedagent-composition
  -> build-time manifest/factory contracts only

root embedagent product
  -> explicit catalog registration
  -> compiled product selection
  -> host/gui launch
```

Core imports none of Host, Protocol, GUI, Composition, product, or workflow.
The C/C++ workflow depends only on Core. GUI depends only on Protocol plus its
declared local GUI/server libraries, never on Core, Host, or workflow packages.
The root product is the only trusted composition root allowed to know and bind
all selected distributions.

## Non-Negotiable Invariants

- Python runtime remains `>=3.8,<3.9` with no newer syntax.
- Default operation and default C/C++ workflow remain fully offline.
- Every runtime binary is bundle-local and declared in the offline contract.
- One agent owns one extension manager and one tool catalog.
- Permission requirements are metadata, never permission grants.
- Manifests and GUI declarations never execute code.
- Missing mode, workflow, product name, labels, and notices stay empty.
- Session history comes only from transcript-backed session bootstrap history.
- Unknown GUI values degrade generically or stay hidden.
- Pre-release internal compatibility is deleted, not emulated.
- Local test success never substitutes for Win7/WebView2 release evidence.

## Program Verification

The final plan owns the complete command list. At minimum, the release
candidate must pass:

```bash
uv sync
uv run python scripts/generate-gui-protocol.py --check
uv run python scripts/check-final-architecture.py --root .
uv run python scripts/check-product-hardcoding.py --root .
uv run pytest tests/ -v
uv run --locked python scripts/lint.py
uv build --all-packages --out-dir build/release-dist
uv run python scripts/check-python-distributions.py --dist-dir build/release-dist
```

From `packages/embedagent-gui/src/embedagent_gui/webapp`:

```bash
npm test
npm run build
```

Then run deterministic base/C/C++ exports, exported-agent smokes, bundle
validation, and evidence verification exactly as specified in Plan 6.

## Stop Conditions

Stop and revise the active plan before implementation continues if any change:

- requires Core to import a higher layer;
- introduces runtime component discovery or online installation;
- creates a second session-history, permission, extension, or tool truth;
- requires GUI source changes for a new trusted workflow package;
- grants agent metadata an executable renderer or service handler;
- weakens Windows 7, Python 3.8, offline, or bundle-local tool requirements;
- preserves an old internal API solely to avoid updating in-repository callers.
