# Phase M Design: Core Alias Cleanup

Date: 2026-06-14
Status: Completed

## Context

The Pi-inspired architecture program has already moved the project toward a
smaller Agent Core: default C/C++ workflow behavior lives behind extensions,
workflow tools are activated through the shared extension manager, and previous
phases removed compatibility exports from harness/tooling package modules.

One class of legacy surface remains inside core modules: backward-compatible
global aliases that preserve old import styles after the earlier global-state
elimination work. These aliases make the architecture look larger than it is
and keep stale names available even though the product is not online and has no
external compatibility contract yet.

## Goals

- Remove stale core-level compatibility aliases that duplicate official factory
  or accessor APIs.
- Keep the supported runtime behavior intact for modes, command sanitization,
  and hosted adapter creation.
- Strengthen tests so the removed names do not quietly return.
- Update source-of-truth documentation so future slices preserve the minimal
  core boundary.

## Non-Goals

- Do not remove official accessors such as `get_mode_registry()`,
  `get_command_sanitizer()`, or `get_inprocess_adapter()`.
- Do not redesign the dependency injection container.
- Do not change mode semantics, permission policy, shell command blocking
  rules, or adapter lifecycle behavior.
- Do not introduce runtime dependencies or online extension behavior.

## Target Removals

| Legacy name | Module | Replacement |
|-------------|--------|-------------|
| `MODE_REGISTRY` | `embedagent.modes` | `get_mode_registry()` |
| `_DEFAULT_SANITIZER` | `embedagent.command_sanitizer` | `get_command_sanitizer()` |
| `get_default_sanitizer()` | `embedagent.command_sanitizer` | `get_command_sanitizer()` |
| `_inprocess_adapter` / `_get_adapter_class()` | `embedagent.core.adapter` | `get_inprocess_adapter()` |

The adapter file does not currently expose `InProcessAdapterClass`, but it still
contains the same compatibility pattern through `_inprocess_adapter` and
`_get_adapter_class()`. Phase M removes that pattern instead of preserving the
commented legacy boundary.

## Design

### Modes

`embedagent.modes` keeps `get_mode_registry(fresh=False)` as the sole registry
accessor. Convenience functions such as `mode_names()` and `require_mode()`
resolve the registry through that accessor at call time.

This keeps mode access explicit and avoids a global proxy object that looks like
authoritative mutable state.

### Command Sanitizer

`embedagent.command_sanitizer` keeps `get_command_sanitizer(fresh=False)` as the
sole default sanitizer accessor. Runtime shell tooling imports that function
directly.

This leaves tests able to request isolated sanitizer instances with
`fresh=True` while removing the old `_DEFAULT_SANITIZER` proxy and legacy
`get_default_sanitizer()` wrapper.

### Core Adapter

`embedagent.core.adapter` keeps `get_inprocess_adapter(fresh=False)` as the
single adapter class accessor. The unused compatibility cache/accessor pair is
deleted.

### Tests

Tests should check both sides of the new boundary:

- official accessors still return usable objects;
- removed legacy names are absent from their modules.

The existing backward-compatibility test file may remain as a historical test
suite, but Phase M changes the relevant assertions from "old alias works" to
"old alias is intentionally gone."

## Acceptance Criteria

- No source code imports `get_default_sanitizer()` or `MODE_REGISTRY`.
- `MODE_REGISTRY`, `_DEFAULT_SANITIZER`, and `get_default_sanitizer()` are absent
  from their modules.
- The adapter compatibility cache/accessor is absent from
  `embedagent.core.adapter`.
- Focused tests cover the removed aliases and official accessors.
- Fast non-GUI test suite and lint checks pass under the existing Python 3.8
  constraints.
