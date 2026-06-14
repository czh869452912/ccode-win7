# Phase M Plan: Core Alias Cleanup

Date: 2026-06-14
Status: Proposed

## Objective

Complete Phase M of the Pi-inspired Agent Core program by removing stale
core-level compatibility aliases and leaving only explicit factory/accessor
entry points.

## Constraints

- Preserve Windows 7, offline deployment, and Python 3.8 compatibility.
- Do not change mode behavior, shell command blocking behavior, permission
  categories, or adapter lifecycle behavior.
- Do not introduce runtime dependencies.
- Use tests to lock the new minimal boundary before removing code.

## Execution Steps

1. Baseline focused behavior.
   - Run the current compatibility/global-state tests that cover modes, command
     sanitizer, and adapter accessors.

2. Add red tests for the new boundary.
   - Assert `embedagent.modes` no longer exports `MODE_REGISTRY`.
   - Assert `embedagent.command_sanitizer` no longer exports
     `_DEFAULT_SANITIZER` or `get_default_sanitizer`.
   - Assert `embedagent.core.adapter` no longer contains the legacy adapter
     compatibility accessor/cache.
   - Assert official accessors remain usable.

3. Implement the cleanup.
   - Update mode helper functions to call `get_mode_registry()` directly.
   - Migrate shell tooling from `get_default_sanitizer()` to
     `get_command_sanitizer()`.
   - Delete the command sanitizer legacy proxy and wrapper.
   - Delete the adapter compatibility cache/accessor.

4. Synchronize documentation.
   - Update active source-of-truth docs with Phase M completion and the new
     no-legacy-alias rule.
   - Archive the Phase M design and plan once conclusions are reflected in
     active docs.

5. Verify.
   - Run focused compatibility/global-state/mode tests.
   - Run harness component tests.
   - Run the fast non-GUI suite.
   - Run ruff and black checks.

## Done When

- Legacy core aliases are absent from source and tests.
- Official accessors keep their existing behavior.
- Documentation records Phase M as completed.
- Verification commands pass.
- The Phase M branch is committed, fast-forward merged to `main`, and the
  temporary worktree is removed.

