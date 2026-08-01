# Cross-Platform Frontend CI Design

**Status:** Approved

**Date:** 2026-08-01

## 1. Goal

Make Windows a first-class frontend CI platform while retaining Linux as a
portability gate for the npm dependency manifest and lock file.

The frontend must install, test, build, and reproduce committed static assets
on both operating systems. This change must fix the current Linux `npm ci`
failure without weakening strict installs, hiding platform failures, or
claiming that a hosted Windows runner proves Windows 7 compatibility.

## 2. Failure Evidence

GitHub Actions run `30560598850` failed only in the frontend job during
`npm ci` on `ubuntu-latest`:

```text
npm error code EBADPLATFORM
Unsupported platform for @rollup/rollup-win32-x64-msvc@4.60.1
wanted: {"os":"win32","cpu":"x64"}
current: {"os":"linux","cpu":"x64"}
```

The webapp currently declares the Windows-only Rollup native package as a
normal development dependency. The lock file therefore requires that package
on Linux even though its package metadata permits only Windows x64. The
existing frontend CI job runs only on Ubuntu. The repository has a separate
Windows packaging job, but that job runs Python release tests and does not
exercise npm or the frontend build.

## 3. Constraints

1. Windows remains the primary product and development platform.
2. Linux remains a supported CI environment for dependency portability.
3. Windows 7 and offline delivery requirements remain mandatory.
4. The frontend install remains a strict `npm ci`; force and compatibility
   flags are not acceptable fixes.
5. Node, Vite, Rollup, and other package upgrades are outside this change.
6. The implementation must not introduce Docker, WSL, or an online runtime
   dependency.
7. Generated GUI assets must remain reproducible and committed when frontend
   source changes.

## 4. Considered Approaches

### 4.1 Windows-Only Frontend CI

Moving the frontend job to Windows would align the job with the primary
platform and avoid the immediate Linux install error. It would also hide a
non-portable lock file and remove an inexpensive cross-platform dependency
check. This approach is rejected.

### 4.2 Linux-Only Frontend CI With An Optional Native Package

Making the package optional would fix the current job at the lowest CI cost.
It would leave the primary Windows frontend installation and build outside the
repository's automated gates. This approach is rejected.

### 4.3 Linux And Windows Frontend Matrix

Declare the Windows native package as optional and run the complete frontend
gate on both Ubuntu and Windows. The two jobs run in parallel and provide
platform-specific diagnostics. This is the selected approach.

## 5. Dependency Design

Move `@rollup/rollup-win32-x64-msvc` from `devDependencies` to
`optionalDependencies` in the webapp `package.json`, preserving its current
version range.

The explicit declaration is retained because Windows is the primary platform
and the package supports Vite/Rollup development on Windows. Making it
optional lets npm skip it when its `os` and `cpu` constraints do not match the
host. The package must appear in only one dependency section.

Regenerate `package-lock.json` through npm using the CI-aligned Node/npm
toolchain. Do not edit the lock file by hand. The resulting lock must record:

- the package under the root package's `optionalDependencies`;
- no root `devDependencies` entry for the package;
- `optional: true` on the native package node;
- `os: ["win32"]` and `cpu: ["x64"]` on that node.

This follows npm's documented optional dependency behavior. In particular,
`npm ci` does not treat a non-matching optional dependency as an install
failure. No command may use `--force`, `--legacy-peer-deps`,
`--omit=optional`, or platform environment overrides.

## 6. CI Design

Keep the existing `frontend` job boundary and convert it to an operating
system matrix:

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, windows-latest]
runs-on: ${{ matrix.os }}
```

Both matrix legs execute the same steps:

1. Check out the repository.
2. Configure Node 20 and the npm cache from the webapp lock file.
3. Run `npm ci`.
4. Run `npm test`.
5. Run `npm run build`.
6. Run `git diff --exit-code -- src/embedagent/frontend/gui/static` from the
   repository root.

`fail-fast: false` preserves diagnostic evidence from both platforms. It does
not make either leg optional. A failure on either platform fails the matrix.
The existing Windows packaging job remains separate because it owns Python
release validation, not frontend validation.

The implementation must also check whether repository branch protection names
the old frontend check explicitly. Matrix jobs can change displayed check
names. Repository protection settings are external state and must not be
changed without separate authorization.

## 7. Regression Test Design

Extend `tests/test_packaging_control_plane.py`, which already owns CI and
packaging control-plane contracts. The test is in the explicit `release`
partition, so it does not add latency to the normal TDD or pre-push partition.
It remains directly runnable during the focused red/green loop.

The new contract test must parse `package.json` and `package-lock.json` with
the Python standard library and assert the dependency invariants in section 5.
It must also scope its workflow assertions to the frontend job and verify:

- both `ubuntu-latest` and `windows-latest` are matrix values;
- the job uses `runs-on: ${{ matrix.os }}`;
- `fail-fast` is false;
- `npm ci`, `npm test`, `npm run build`, and the committed-asset check remain
  present.

No YAML parser dependency is added. The workflow contract may use focused text
assertions consistent with the existing control-plane tests, while JSON files
must use structured parsing.

Implementation follows a red/green sequence: add the failing contract first,
then update the dependency metadata and workflow until the focused test passes.

## 8. Verification

### 8.1 Focused Red/Green Loop

Run the exact packaging control-plane test file through the repository's TDD
entry point.

### 8.2 Local Windows Frontend Gate

From the webapp directory, run a clean `npm ci`, `npm test`, and
`npm run build`. Then verify that the committed static asset tree has no
unexpected differences.

### 8.3 Repository Gates

Run:

- the two pre-merge architecture guard files;
- `scripts/test-suite.py full`;
- `scripts/test-suite.py release`;
- the locked lint command;
- the frontend test and build commands required by `AGENTS.md`.

The performance partition is not required because the change has no runtime
performance behavior.

### 8.4 GitHub Verification

After push, both frontend matrix legs and all existing CI jobs must pass. The
Linux leg is the authoritative proof that the lock file no longer requires a
Windows-only package. The Windows leg is the authoritative hosted-runner proof
for the primary frontend development platform.

## 9. Failure Handling

- Do not add conditional install commands by operating system.
- Do not add `continue-on-error` to either matrix leg.
- Do not remove the generated-asset comparison from either platform.
- If asset output differs between operating systems, treat it as a build
  determinism defect and fix the build rather than suppressing one comparison.
- If the Windows native package is absent on Windows, inspect the generated
  lock metadata and npm platform resolution; do not restore it as a mandatory
  dependency that breaks Linux.
- Keep the two platform results visible even when one fails.

## 10. Scope

Implementation changes are limited to:

- `src/embedagent/frontend/gui/webapp/package.json`;
- `src/embedagent/frontend/gui/webapp/package-lock.json`;
- `.github/workflows/ci.yml`;
- `tests/test_packaging_control_plane.py`.

No frontend source or generated static asset change is expected. Any generated
asset difference must be reviewed rather than committed automatically.

## 11. Acceptance Criteria

1. The focused control-plane regression test passes.
2. A clean Windows `npm ci` succeeds and installs the applicable native Rollup
   package without force flags.
3. Windows frontend tests and build pass with no generated-asset diff.
4. GitHub's Ubuntu frontend leg completes `npm ci`, tests, build, and asset
   verification successfully.
5. GitHub's Windows frontend leg completes the same gate successfully.
6. All pre-existing CI jobs remain successful.
7. The working tree contains no unrelated or unexpected generated changes.

## 12. Windows 7 Evidence Boundary

`windows-latest` is a modern hosted runner. Passing it proves that the current
frontend development toolchain works on GitHub's Windows environment; it does
not prove that the shipped application works on Windows 7.

Windows 7 compatibility and offline delivery claims still require the existing
target-style bundle validation and real Win7/WebView2 smoke evidence described
by the project constitution. This CI repair does not replace or weaken that
release gate.

## 13. References

- npm `package.json` optional dependencies:
  https://docs.npmjs.com/cli/configuring-npm/package-json/#optionaldependencies
- npm `ci` platform handling:
  https://docs.npmjs.com/cli/v11/commands/npm-ci/
- GitHub Actions matrix jobs:
  https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
