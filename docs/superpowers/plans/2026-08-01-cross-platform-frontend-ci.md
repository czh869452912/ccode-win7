# Cross-Platform Frontend CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the strict frontend install, test, build, and committed-asset check pass as required CI gates on both Linux and Windows.

**Architecture:** Keep one frontend GitHub Actions job and expand it into parallel Ubuntu and Windows matrix legs. Preserve the explicit Windows Rollup native package but classify it as optional in both npm manifests, then protect the dependency and workflow invariants with focused release-partition contract tests.

**Tech Stack:** Node.js 20, npm lockfile v3, Vite/Rollup, esbuild, Python 3.8 standard library, unittest/pytest, uv, GitHub Actions, and GitHub CLI.

---

## Scope Boundary

This plan implements the approved design in
`docs/superpowers/specs/2026-08-01-cross-platform-frontend-ci-design.md`.

Implementation changes are limited to:

- `src/embedagent/frontend/gui/webapp/package.json`;
- `src/embedagent/frontend/gui/webapp/package-lock.json`;
- `.github/workflows/ci.yml`;
- `tests/test_packaging_control_plane.py`.

Do not update Node, Vite, Rollup, esbuild, Playwright, or unrelated npm
packages. Do not edit `uv.lock`. No frontend source or generated static asset
change is expected.

## Execution Rules

Execute this plan in an isolated worktree created from the approved design
commit:

```powershell
git worktree add ..\ccode-win7-frontend-ci -b codex/frontend-ci-matrix main
Set-Location ..\ccode-win7-frontend-ci
git log -2 --oneline
```

Expected: `ce4f9ccb docs: design cross-platform frontend ci` is present or is
an ancestor of `HEAD`.

Use Python 3.8 syntax only. Use `apply_patch` for manual edits. Regenerate the
npm lock file with npm rather than editing it manually. Do not use `--force`,
`--legacy-peer-deps`, `--omit=optional`, platform environment overrides, or
`continue-on-error`.

After Tasks 1 and 2, run the listed focused test and commit only the files
owned by that task. Do not run the full repository gates inside either
red/green loop.

## Target File Map

- `tests/test_packaging_control_plane.py`: owns executable dependency-manifest
  and frontend-CI control-plane contracts.
- `src/embedagent/frontend/gui/webapp/package.json`: declares the Windows x64
  Rollup native package as an explicit optional development-time capability.
- `src/embedagent/frontend/gui/webapp/package-lock.json`: records the same
  optional root dependency and platform metadata reproducibly.
- `.github/workflows/ci.yml`: runs identical strict frontend gates on Ubuntu
  and Windows.

## Task 1: Make The Windows Rollup Native Package Optional

**Files:**

- Modify: `tests/test_packaging_control_plane.py`
- Modify: `src/embedagent/frontend/gui/webapp/package.json`
- Modify: `src/embedagent/frontend/gui/webapp/package-lock.json`

- [ ] **Step 1: Write the failing npm dependency contract**

Add this method to `TestPythonDistributionPackagingContract`, immediately
before the existing
`test_ci_workspace_jobs_provision_uv_and_share_offline_build_cache` method:

```python
    def test_frontend_native_rollup_dependency_is_optional(self):
        webapp = ROOT / "src" / "embedagent" / "frontend" / "gui" / "webapp"
        package = json.loads((webapp / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads(
            (webapp / "package-lock.json").read_text(encoding="utf-8")
        )
        dependency = "@rollup/rollup-win32-x64-msvc"

        self.assertNotIn(dependency, package.get("devDependencies", {}))
        self.assertEqual(
            package.get("optionalDependencies", {}).get(dependency), "^4.60.1"
        )

        lock_root = package_lock["packages"][""]
        self.assertNotIn(dependency, lock_root.get("devDependencies", {}))
        self.assertEqual(
            lock_root.get("optionalDependencies", {}).get(dependency), "^4.60.1"
        )

        native_package = package_lock["packages"]["node_modules/" + dependency]
        self.assertIs(native_package.get("optional"), True)
        self.assertEqual(native_package.get("os"), ["win32"])
        self.assertEqual(native_package.get("cpu"), ["x64"])
```

- [ ] **Step 2: Run the focused test and verify the current manifest fails**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_frontend_native_rollup_dependency_is_optional
```

Expected: FAIL at `assertNotIn` because
`@rollup/rollup-win32-x64-msvc` is still a normal `devDependency`.

- [ ] **Step 3: Move the package into `optionalDependencies`**

In `src/embedagent/frontend/gui/webapp/package.json`, remove the Rollup native
package from `devDependencies` and add the explicit optional section:

```json
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "esbuild": "^0.21.5",
    "playwright": "^1.61.0",
    "vite": "^5.4.10"
  },
  "optionalDependencies": {
    "@rollup/rollup-win32-x64-msvc": "^4.60.1"
  }
```

Do not change any other dependency range.

- [ ] **Step 4: Regenerate the lock file with npm**

```powershell
Set-Location src/embedagent/frontend/gui/webapp
npm install --package-lock-only --ignore-scripts
Set-Location ../../../../..
git diff -- src/embedagent/frontend/gui/webapp/package.json src/embedagent/frontend/gui/webapp/package-lock.json
```

Expected: the root package moves the dependency from `devDependencies` to
`optionalDependencies`, and the native package node gains `optional: true`.
There must be no unrelated version or integrity changes.

- [ ] **Step 5: Run the focused contract and verify it passes**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_frontend_native_rollup_dependency_is_optional
```

Expected: PASS.

- [ ] **Step 6: Verify a strict Windows install loads the native package**

```powershell
Set-Location src/embedagent/frontend/gui/webapp
npm ci
node -e "require('@rollup/rollup-win32-x64-msvc'); console.log('native Rollup OK')"
Set-Location ../../../../..
```

Expected: `npm ci` exits successfully without compatibility flags and Node
prints `native Rollup OK`.

- [ ] **Step 7: Commit the dependency fix and its contract**

```powershell
git add tests/test_packaging_control_plane.py src/embedagent/frontend/gui/webapp/package.json src/embedagent/frontend/gui/webapp/package-lock.json
git diff --cached --check
git commit -m "fix: make Windows Rollup dependency optional"
```

Expected: one commit containing only the three listed files.

## Task 2: Run The Frontend Gate On Linux And Windows

**Files:**

- Modify: `tests/test_packaging_control_plane.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the failing frontend matrix contract**

Add this method to `TestPythonDistributionPackagingContract`, immediately
after `test_frontend_native_rollup_dependency_is_optional`:

```python
    def test_frontend_ci_runs_required_linux_and_windows_matrix(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        frontend = workflow.split("  frontend:\n", 1)[1].split("  smoke:\n", 1)[0]

        self.assertIn(
            "strategy:\n"
            "      fail-fast: false\n"
            "      matrix:\n"
            "        os: [ubuntu-latest, windows-latest]",
            frontend,
        )
        self.assertIn("runs-on: ${{ matrix.os }}", frontend)
        for command in (
            "run: npm ci",
            "run: npm test",
            "run: npm run build",
            "run: git diff --exit-code -- src/embedagent/frontend/gui/static",
        ):
            self.assertIn(command, frontend)
        self.assertNotIn("continue-on-error:", frontend)
```

- [ ] **Step 2: Run the focused test and verify the Ubuntu-only job fails**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_frontend_ci_runs_required_linux_and_windows_matrix
```

Expected: FAIL because the frontend job has no `strategy` matrix and still
uses the literal `ubuntu-latest` runner.

- [ ] **Step 3: Convert the frontend job to a required OS matrix**

Replace the opening of the `frontend` job in `.github/workflows/ci.yml` with:

```yaml
  frontend:
    name: Frontend test and build
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        working-directory: src/embedagent/frontend/gui/webapp
```

Leave every existing frontend step unchanged. Do not add operating-system
conditionals or make either matrix leg optional.

- [ ] **Step 4: Run both focused control-plane contracts**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_frontend_native_rollup_dependency_is_optional tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_frontend_ci_runs_required_linux_and_windows_matrix
```

Expected: 2 passed.

- [ ] **Step 5: Inspect the workflow diff and syntax-sensitive whitespace**

```powershell
git diff --check
git diff -- .github/workflows/ci.yml tests/test_packaging_control_plane.py
```

Expected: only the matrix stanza and the new focused test are present; no
trailing-whitespace errors are reported.

- [ ] **Step 6: Commit the CI matrix and its contract**

```powershell
git add .github/workflows/ci.yml tests/test_packaging_control_plane.py
git diff --cached --check
git commit -m "ci: test frontend on Linux and Windows"
```

Expected: one commit containing only the two listed files.

## Task 3: Run Local Acceptance Gates

**Files:**

- Verify only; no planned file changes.

- [ ] **Step 1: Re-run both regression contracts from the repository root**

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_frontend_native_rollup_dependency_is_optional tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_frontend_ci_runs_required_linux_and_windows_matrix
```

Expected: 2 passed.

- [ ] **Step 2: Run the complete local Windows frontend gate**

```powershell
Set-Location src/embedagent/frontend/gui/webapp
npm ci
npm test
npm run build
Set-Location ../../../../..
git diff --exit-code -- src/embedagent/frontend/gui/static
```

Expected: strict install, frontend tests, and build all succeed; `git diff`
exits zero with no generated-asset changes.

- [ ] **Step 3: Run the pre-merge architecture guards**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 4: Run the complete regular Python partition**

```powershell
uv run python scripts/test-suite.py full
```

Expected: PASS with no release or performance tests selected.

- [ ] **Step 5: Run the release partition containing the control-plane test**

```powershell
uv run python scripts/test-suite.py release
```

Expected: PASS, including all packaging and distribution control-plane tests.

- [ ] **Step 6: Run locked lint**

```powershell
uv run --locked python scripts/lint.py
```

Expected: PASS with no modifications.

- [ ] **Step 7: Verify the implementation branch is clean**

```powershell
git diff --check
git status --short
git log -4 --oneline
```

Expected: `git status --short` is empty. The log contains the dependency-fix
commit followed by the frontend-matrix commit. Do not create an empty
verification commit.

## Task 4: Verify Required Checks And GitHub Matrix Results

**Files:**

- External verification only; no planned repository file changes.

- [ ] **Step 1: Inspect branch-protection required check names**

```powershell
gh api repos/czh869452912/ccode-win7/branches/main/protection/required_status_checks
```

Expected: either a JSON list of required checks or a 404 when no required
status-check protection is configured. If the JSON explicitly requires the
old singular frontend check name, stop before push and coordinate the external
branch-protection update; do not weaken repository protection from this plan.

- [ ] **Step 2: Push the implementation branch after authorization**

```powershell
git push -u origin codex/frontend-ci-matrix
```

Expected: the branch is published successfully and GitHub starts the CI
workflow.

- [ ] **Step 3: Wait for the branch workflow to finish**

```powershell
$frontendCiRun = gh run list --branch codex/frontend-ci-matrix --workflow CI --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $frontendCiRun --exit-status
```

Expected: the command exits zero after all CI jobs finish.

- [ ] **Step 4: Confirm both frontend platform results and existing jobs**

```powershell
gh run view $frontendCiRun --json jobs --jq '.jobs[] | [.name, .conclusion] | @tsv'
```

Expected: successful frontend results are present for both `ubuntu-latest` and
`windows-latest`; lint, regular tests with coverage, performance, smoke, and
Windows packaging also report `success`.

- [ ] **Step 5: Capture the Windows 7 evidence boundary in the handoff**

Report that `windows-latest` proves the hosted Windows development build only.
Do not describe this result as Win7 compatibility or offline-bundle evidence;
those claims continue to require the target-style bundle and real
Win7/WebView2 smoke gates defined by `AGENTS.md`.

## Completion Criteria

The plan is complete only when:

- both new control-plane contracts pass;
- strict local Windows npm installation, tests, and build pass;
- generated static assets remain unchanged;
- architecture, full regular, release, and lint gates pass;
- GitHub reports successful Ubuntu and Windows frontend matrix legs;
- every pre-existing CI job remains successful;
- no force flags, optional failures, platform-specific install branches,
  dependency upgrades, or unrelated files were introduced.
