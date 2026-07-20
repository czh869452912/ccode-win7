# CI Platform Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Restore CI by aligning each check with the platform and interpreter contract it actually exercises, while preserving the six-distribution workspace architecture.

**Architecture:** Ubuntu remains responsible for source-resolved lint, portable tests, and package import smoke. Windows owns PowerShell, reparse-point, and pinned Python 3.8.10 packaging tests. The workflow will not install published workspace distributions from an index; smoke uses the locked uv workspace so dynamic source composition remains intact.

**Tech Stack:** GitHub Actions, uv, Python 3.8, pytest, Black, PowerShell.

---

### Task 1: Normalize the current implementation test and workspace smoke install

**Files:**
- Modify: `tests/test_inprocess_adapter_frontend_api.py` (Black formatting only)
- Modify: `.github/workflows/ci.yml` (smoke installation and locked test setup)

- [ ] Run Black check against the failing test file and capture the expected reformat diff.
- [ ] Apply Black formatting to the file and rerun the check.
- [ ] Change smoke setup from `pip install -e ".[cli]"` to `uv sync --locked --python "$(which python)"`, then invoke import checks through `uv run --locked --python "$(which python)"`.
- [ ] Keep the smoke job source-resolved and offline-compatible; do not add an index dependency or duplicate distribution installation.

### Task 2: Make portable pytest selection explicit

**Files:**
- Modify: `tests/test_transcript_store.py` (three root-directory redirect tests)
- Modify: `tests/test_phase7_doctor.py` (PowerShell-dependent tests)
- Modify: `tests/test_release_reproducibility.py` (PowerShell-dependent tests)
- Modify: `tests/test_python_distribution_smoke.py` (pinned release-toolchain subprocess tests)
- Modify: `tests/test_packaging_control_plane.py` (PowerShell-dependent wheel publication tests)

- [ ] Add `skipUnless(os.name == "nt", ...)` to the three transcript root-alias tests that exercise Windows directory redirect behavior.
- [ ] Add platform skips only to tests that invoke PowerShell or the pinned 3.8.10 release builder; leave pure contract/read-model tests running on Ubuntu.
- [ ] Run the affected portable tests and confirm the Windows-only cases are reported as skips rather than failures.

### Task 3: Add a Windows packaging/release CI lane

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] Add a Windows job using `windows-latest` and `actions/setup-python` with Python `3.8.10`.
- [ ] Install uv, run `uv sync --locked --python "${{ ... }}"` using the setup interpreter, and execute the skipped packaging, doctor, reproducibility, and distribution-smoke modules.
- [ ] Keep the job bounded to existing tests; do not change runtime package ownership or release scripts.

### Task 4: Verify and record the fix

**Files:**
- No additional source files unless verification exposes a concrete regression.

- [ ] Run Black, lint, portable pytest, and the selected Windows-lane command locally where the host supports it.
- [ ] Parse the workflow YAML and inspect the diff for architecture-boundary regressions.
- [ ] Commit the CI alignment and test platform guard changes with a focused message.
