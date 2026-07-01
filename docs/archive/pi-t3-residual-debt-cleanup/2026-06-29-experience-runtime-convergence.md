# Experience Runtime Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CLI-visible agent runs use an honest runtime outcome contract, preserve real shell semantics, and remove stale write-boundary friction without keeping compatibility shims for old behavior.

**Architecture:** Agent Core returns a structured turn outcome derived from loop transitions. Hosted shells render and exit from that outcome instead of inferring success from the absence of exceptions. Shell execution becomes a true shell capability with managed tools exposed through PATH, while direct managed executable resolution remains available for dedicated toolchain calls.

**Tech Stack:** Python 3.8, pytest, existing hosted runtime/session/agent loop/tool runtime boundaries.

---

### Task 1: Define Honest Turn Outcome Contract

**Files:**
- Modify: `src/embedagent/session.py`
- Test: `tests/test_turn_outcome.py`

- [x] **Step 1: Write failing tests for transition-to-outcome mapping**

Create `tests/test_turn_outcome.py` with tests asserting that `completed` is successful, `guard_stop` is blocked, `aborted` is aborted, `max_turns` is partial, and `permission_wait` is waiting.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_turn_outcome.py -v`
Expected: FAIL because `TurnOutcome` and `QueryTurnResult.outcome` do not exist.

- [x] **Step 3: Add minimal outcome dataclass and mapper**

Add `TurnOutcome` to `session.py` with fields `kind`, `reason`, `message`, `exit_code`, and `is_success`. Add `TurnOutcome.from_transition()` and `QueryTurnResult.outcome`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_turn_outcome.py -v`
Expected: PASS.

### Task 2: Make CLI Exit and Render From Outcome

**Files:**
- Modify: `src/embedagent/cli.py`
- Modify if needed: `src/embedagent/hosted/session_host.py`
- Test: `tests/test_cli_hosted_entrypoint.py`

- [x] **Step 1: Write failing CLI tests**

Add tests proving that a `session_finished` payload with `outcome.kind == "blocked"` prints a blocked diagnostic and returns exit code `2`, while `outcome.kind == "completed"` returns `0`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_hosted_entrypoint.py -v`
Expected: FAIL because CLI ignores outcome payloads.

- [x] **Step 3: Emit and consume outcome**

Ensure hosted completion events include the `QueryTurnResult.outcome.to_dict()` payload. Update CLI to store it, print a concise diagnostic for `blocked`, `partial`, or `aborted`, and return the outcome exit code unless `session_error` already returned `1`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_hosted_entrypoint.py -v`
Expected: PASS.

### Task 3: Preserve Real Shell Semantics

**Files:**
- Modify: `src/embedagent/tools/_base.py`
- Test: `tests/test_tools_v2_runtime.py` or new focused test file if no suitable shell-runtime test exists.

- [x] **Step 1: Write failing shell test**

Add a test proving that `run_shell_tool('clang --version || echo fallback')` does not raise `ToolError` when managed clang is absent and system fallback is disabled; it must pass the original command to the shell with managed PATH entries.

- [x] **Step 2: Run test to verify it fails**

Run the focused shell test.
Expected: FAIL because `rewrite_command_for_managed_tools()` raises before shell execution.

- [x] **Step 3: Remove shell preflight rewrite**

Change `run_shell_tool()` to execute `command_text` directly with `build_process_env()`. Keep `resolve_managed_command_executable()` for non-shell managed executable paths.

- [x] **Step 4: Run test to verify it passes**

Run the focused shell test.
Expected: PASS.

### Task 4: Replace Narrow Build/Debug Write Boundary With Development Boundary

**Files:**
- Modify: `src/embedagent/modes.py`
- Modify tests that assert old narrow globs only if they preserve obsolete constraints.
- Test: `tests/test_modes.py` or existing architecture tests.

- [x] **Step 1: Write failing mode test**

Add or update a test proving build/debug can write common project docs such as `README.md` and `docs/design.md`, while verify remains read-only.

- [x] **Step 2: Run test to verify it fails**

Run the focused mode test.
Expected: FAIL because build/debug reject markdown docs today.

- [x] **Step 3: Update mode write boundary**

Add markdown/text docs to build/debug writable globs. Do not add compatibility aliases or old mode names.

- [x] **Step 4: Run test to verify it passes**

Run the focused mode test.
Expected: PASS.

### Task 5: Remove Stale Vocabulary and Verify Gates

**Files:**
- Modify: prompt/profile files containing stale `code` mode references.
- Test: architecture guards and focused test suite.

- [x] **Step 1: Write or update guard test for stale `code/debug` prompt vocabulary**

Assert active prompt/profile text does not present `code` as a first-class mode.

- [x] **Step 2: Run test to verify it fails if stale text remains**

Run the focused guard.

- [x] **Step 3: Delete stale text**

Replace stale `code/debug` guidance with official modes only.

- [x] **Step 4: Run final verification**

Run:
`uv run pytest tests/test_turn_outcome.py tests/test_cli_hosted_entrypoint.py tests/test_tools_v2_runtime.py tests/test_current_architecture_boundaries.py tests/test_pre_release_architecture_guards.py -v`
and `uv run --locked python scripts/lint.py`.
