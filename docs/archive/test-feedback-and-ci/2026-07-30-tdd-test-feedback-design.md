# TDD Test Feedback Design

**Status:** Approved

**Date:** 2026-07-30

## 1. Goal

Improve local test-driven development feedback without weakening regression,
architecture, packaging, offline, Windows, or release assurance.

The design separates local feedback speed from complete verification. A
developer should receive a useful red/green result in seconds, while fixed CI
partitions continue to execute the complete project test inventory. No test is
discarded merely because it is slow.

## 2. Measured Baseline

The repository baseline was measured on Windows with Python 3.8.10:

- `1682` Python tests collected
- `1681` selected by `-m "not slow and not gui"`
- the selected suite completed in `484.27` seconds
- the frontend helper suite completed in approximately `1.5` seconds

The slowest Python cases exposed scheduling defects rather than an inherently
slow unit suite:

- `test_hygn_03_warning_cleanup.py` launched almost the entire pytest suite
  recursively and consumed `241.69` seconds.
- three distribution build/install/smoke cases consumed approximately `86`
  seconds but were not classified as release tests.
- two session performance cases consumed approximately `13.4` seconds but
  were not separated from the daily suite.

The configured `unit`, `session`, and `slow` markers are effectively unused.
The current fast-subset command therefore selects almost the entire suite.
The Makefile also enables coverage for its normal test target, adding work to
a command developers are likely to use during local iteration.

## 3. Constraints

The test program must preserve these project constraints:

1. Python remains `>=3.8,<3.9` and test tooling must support Python 3.8.
2. Runtime behavior remains offline and Windows 7 compatible.
3. Release verification continues to cover all six Python distributions,
   offline packaging, bundled tools, and target-style GUI evidence.
4. Tests remain under `tests/`; frontend tests remain under the webapp test
   tree.
5. CI completeness must not depend on changed-file selection, pytest cache,
   or a developer choosing the correct local command.
6. Slow tests are scheduled separately, not silently skipped or deleted.
7. The initial implementation should not add parallel-test dependencies.
8. Existing unrelated worktree changes must remain untouched.

## 4. Considered Approaches

### 4.1 Add Slow Markers Only

Marking the known expensive tests is a low-risk immediate improvement. It does
not solve the lack of architecture-specific test entry points, unclassified
test drift, or very large integration modules. It is selected as the first
migration step, not as the final design.

### 4.2 Parallelize Or Use Dependency-Based Selection

`pytest-xdist` can reduce full-suite wall time, and dependency-based selectors
can reduce local work. Neither corrects recursive pytest execution or release
tests mixed into the daily suite. Test-level parallelism also introduces risk
for Windows subprocesses, global state, shared directories, and packaging
tests. These tools may be evaluated after isolation improves, but they are not
the first intervention.

### 4.3 Layered Feedback With Fixed Completeness Gates

This design separates exact TDD tests, architecture slices, pre-push tests,
complete regular CI, and release/performance gates. Local selection is an
ergonomic optimization. CI runs fixed partitions whose audited union is the
complete suite.

This is the selected approach.

## 5. Feedback Layers

The repository will expose six feedback layers:

| Layer | Purpose | Target wall time | Contents |
| --- | --- | ---: | --- |
| TDD | Every red/green cycle | under 10 seconds | Exact node, file, or smallest component |
| Slice | Complete a small change | under 30-60 seconds | Tests owned by the changed architecture area plus direct boundaries |
| Pre-push | Local commit readiness | under 120 seconds | Unit, component, and architecture tests |
| PR CI | Complete regular regression | under 5 minutes | All regular Python and frontend tests in fixed parallel jobs |
| Release | Platform and delivery assurance | measured, not in the TDD budget | Wheels, packaging, offline bundle, and target smoke |
| Performance | Explicit performance regression checks | measured, not in the TDD budget | Large data sets and performance thresholds |

The complete test inventory is the union of the regular, frontend, release,
and performance partitions. Completeness is not redefined as running every
test during each TDD cycle.

## 6. Test Ownership And Classification

Architecture ownership is the primary classification axis. Execution level is
the secondary axis.

The target layout is:

```text
tests/
  core/
    unit/
    component/
  protocol/
    unit/
    contract/
  host/
    unit/
    component/
  workflow_cpp/
    unit/
    component/
  product/
    unit/
    component/
  frontend/
    backend/
    contract/
  integration/
    runtime/
    session/
    gui_bridge/
  architecture/
  release/
  performance/
  support/
```

Each test has one primary owner and one execution level:

- `unit`: pure logic and fake ports; no filesystem, thread, subprocess, or
  sleep; normal target below 100 milliseconds per case
- `component`: one distribution or focused component; temporary files and
  in-memory adapters are allowed; normal target below one second per case
- `integration`: multiple distributions, hosted runtime, threads, or light
  subprocess interaction; normal target below five seconds per case
- `architecture`: AST, source, import-boundary, metadata, and dependency-DAG
  assertions
- `release`: wheel build, installation, PowerShell, offline bundle, toolchain,
  launcher, and target-style smoke behavior
- `performance`: explicit performance thresholds and large data volumes

Markers describe orthogonal execution requirements only:

- `windows`
- `subprocess`
- `serial`
- `gui`
- `slow`

Directory ownership determines when a test runs. Markers determine which
environment it needs and whether it may run concurrently. This replaces the
current mixture of domain, layer, and runtime concepts in marker names.

Cross-distribution behavior belongs to `integration`. A test that checks one
distribution's public contract stays with that distribution. A test that
checks the repository dependency direction belongs to `architecture`.

## 7. Initial Asset Routing

The first migration routes representative existing modules as follows:

- agent effect kernel and loop driver tests to `core/unit`
- session journal and reducer tests to `core/component`
- agent runtime integration tests to `integration/runtime`
- in-process adapter/frontend API tests to `integration/gui_bridge`
- pre-release and current architecture guards to `architecture`
- Python distribution metadata/import contracts to architecture or
  distribution contract tests
- Python distribution smoke, packaging control plane, and Phase 7 delivery
  tests to `release`
- session performance tests to `performance`

The deprecation-warning configuration assertions remain lightweight. The test
that launches another complete pytest process is deleted because CI already
runs pytest with the configured warning policy directly.

## 8. Unified Test Command

A Python 3.8-compatible `scripts/test-suite.py` becomes the single test-suite
entry point used by documentation, Makefile targets, and CI. It wraps pytest
without hiding direct pytest access.

The interface is:

```powershell
uv run python scripts/test-suite.py tdd <node-or-file>
uv run python scripts/test-suite.py failed
uv run python scripts/test-suite.py slice core
uv run python scripts/test-suite.py slice host
uv run python scripts/test-suite.py slice workflow-cpp
uv run python scripts/test-suite.py pre-push
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py release
uv run python scripts/test-suite.py performance
uv run python scripts/test-suite.py audit
```

Command behavior is fixed:

- `tdd` runs exact node ids or files with `-q -x --tb=short` and no coverage.
- `failed` uses pytest's last-failed cache for repair loops only.
- `slice` runs unit/component tests for one architecture area plus its direct
  boundary tests.
- `pre-push` runs all unit, component, and architecture tests.
- `full` runs all regular Python tests without changed-file selection.
- `release` runs packaging, wheel, offline, and platform-specific tests.
- `performance` runs performance thresholds separately.
- `audit` verifies suite membership and collection completeness.

Direct pytest remains supported for diagnosis. The wrapper does not become a
new test framework.

## 9. Source-To-Slice Mapping

The default local mapping is:

| Source area | Primary tests | Slice additions |
| --- | --- | --- |
| `embedagent-core` | `tests/core` | runtime integration and architecture |
| `embedagent-protocol` | `tests/protocol` | GUI bridge and architecture |
| `embedagent-host` | `tests/host` | runtime and GUI bridge integration |
| `embedagent-workflow-cpp` | `tests/workflow_cpp` | C/C++ runtime integration |
| product `src/embedagent` | `tests/product` | frontend backend and GUI bridge |
| webapp | corresponding frontend test module | full `npm test`; build before merge |
| packaging/offline scripts | corresponding contract test | release suite |

Optional changed-file selection may use this mapping locally. It must never
replace fixed complete CI partitions.

## 10. CI Completeness

CI uses fixed jobs:

```text
python-unit-component
python-integration
python-architecture
frontend-test-build
windows-release
performance
```

The required set relationships are:

```text
full regular suite
= unit/component
+ integration
+ architecture

all project tests
= full regular suite
+ frontend
+ release
+ performance
```

The audit command fails when:

- a test file has no partition
- a test node belongs to multiple fixed partitions
- the fixed-partition union differs from complete collection
- a new root-level `tests/test_*.py` file bypasses the target layout after the
  directory migration completes
- a test launches a nested full-suite pytest process

CI records partition duration and slowest-test reports. Initial timing budgets
are observational so shared-runner variance does not create false failures.
Budgets may become enforced after stable baselines exist.

Coverage runs only in complete CI, not in local TDD commands. The CI invocation
must use the configured multi-package coverage sources rather than overriding
them with only `--cov=src/embedagent`. The workflow package is added to the
coverage source set where meaningful. A new multi-distribution baseline is
established before enforcing non-regression.

## 11. Large Test Module Decomposition

The first modules to split are:

- `test_agent_runtime_integration.py`
- `test_inprocess_adapter_frontend_api.py`
- `test_pre_release_architecture_guards.py`
- `test_session_reducer_restore.py`
- `test_packaging_control_plane.py`

Splits follow behavior boundaries, not arbitrary line counts. Runtime tests,
for example, separate action execution, interactions, compaction, restore, and
tool lifecycle. Shared fixtures and builders move to `tests/support` only when
they remove meaningful duplication.

Every resulting file must run independently. Shared setup must not recreate a
large inheritance hierarchy or couple unrelated behaviors to one fixture.

## 12. Migration Sequence

### Phase 0: Preserve The Baseline

- record collection, duration, skip, and slowest-test reports
- preserve intentional behavior and account for every deliberate deletion

### Phase 1: Remove Pathological Scheduling

- delete the recursive pytest test while retaining its configuration checks
- route distribution smoke and packaging execution to release
- route explicit performance thresholds to performance
- remove coverage from the local fast path
- remeasure the suite

The measured durations indicate that this phase alone should reduce the
current default path from about eight minutes to roughly two to two and a half
minutes. The actual post-change measurement is authoritative.

### Phase 2: Add Unified Routing And Audit

- implement the command entry point
- classify every existing module
- update repository commands and CI to use the shared entry point
- require complete, non-overlapping partition collection

The directory migration need not complete before developers receive the new
TDD commands.

### Phase 3: Split Large Modules

- split the five initial large modules along behavior boundaries
- consolidate only focused test helpers
- confirm each new file is independently runnable

### Phase 4: Move Tests By Architecture Area

- first make repository-root resolution independent of each test file's depth
- move one area at a time in this order: Core, Protocol, C/C++ workflow, Host,
  product, integration, architecture, release, performance
- after each move, run the area slice, architecture gate, full regular suite,
  and collection audit
- remove transitional classification data after directory ownership becomes
  the sole source of truth

### Phase 5: Parallelize Stable Partitions

- run fixed architecture partitions concurrently in CI
- keep release, performance, shared-directory, and Windows subprocess tests
  serial where required
- evaluate test-level parallelism only for isolated unit/component partitions
  if fixed job parallelism is insufficient

## 13. Failure And Flake Policy

The design does not use automatic retries, silent skips, or a flaky-test
quarantine to meet timing targets. A failing partition remains a failing gate.

Tests that start threads or subprocesses require explicit timeouts and unique
temporary paths. Tests should use synchronization signals instead of fixed
sleeps. Release tests that mutate shared build locations remain serial.

Local `failed` and exact-node commands are convenience loops. A successful
result from either is never presented as complete verification.

## 14. Acceptance Criteria

The migration is complete when:

1. typical exact-node or focused-file TDD feedback has a P95 below 10 seconds
2. Core, Protocol, and C/C++ workflow slices complete within 30 seconds
3. Host and product slices complete within 60 seconds
4. the pre-push suite completes within 120 seconds on the baseline developer
   machine
5. complete PR regression has a wall time below five minutes through fixed CI
   partitioning
6. release and performance duration is tracked outside the TDD budget
7. no test starts another complete pytest suite
8. no test is unclassified or assigned to multiple fixed partitions
9. the audited CI partition union equals complete test collection
10. migration does not add silent skips, automatic retries, or flaky
    quarantine
11. CI coverage reports all relevant project distributions and establishes a
    non-regression baseline
12. frontend tests and the required frontend build remain part of the merge
    gate when webapp source changes

## 15. Non-Goals

This program does not include:

- deleting valuable tests solely to reduce duration
- making release validation part of every local red/green cycle
- replacing pytest or the frontend test runner during the initial migration
- relying on Git-diff selection for CI completeness
- adding general distributed test infrastructure
- weakening the pre-merge architecture gates
- claiming Windows 7/WebView2 bundle acceptance from local development tests
