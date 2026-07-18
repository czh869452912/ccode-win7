# Phase 5 Closeout: Durable Session Projection And Core Thinning

**Status:** Complete on `codex/phase5-core-projection` (2026-07-18)

Phase 5 is complete for the repository-side Agent Core and Host ownership
boundary. The public `Agent` / `AgentSession` contracts remain unchanged.

## Delivered

- Transcript-backed session history, snapshot, reducer refresh, and unavailable
  payload construction now live behind Host `SessionProjectionService`.
- `SessionRestoreResult` now carries runtime configuration and turn-experience
  read models in addition to operation, compaction, and recovery state.
- Partial restores reduce only the trusted transcript prefix. Restored
  unfinished operations are marked interrupted; active live operations remain
  active during an in-progress turn.
- The durable timeline store/API remains absent. GUI/TUI bootstrap and review
  paths use transcript-backed history projections.
- Hosted slash-command permission waits use the Core
  `AgentToolActionService` pending lifecycle exactly once. The hosted waiting
  state is published only after the Core pending result is created, avoiding a
  partial Host/Core state race.
- Removed unused `_host_record_pending_permission` and
  `host_record_pending_permission` Core forwarding wrappers.
- Hosted `/review` now consumes the same session history projection as GUI/TUI
  instead of traversing live `Session` internals directly.
- Extension diagnostics remain dynamic when the hosted extension manager is
  replaced or reloaded.

## Verification

- Architecture gate: `143 passed`.
- Full non-slow/non-GUI suite: `1570 passed, 4 deselected`.
- Focused Core/Host/action/review suites: `242 passed` and final adapter/review
  regression suite `100 passed`.
- Lint: Ruff and Black pass; `340` files checked.

The GUI `npm test` / `npm run build` gate was not required because Phase 5 did
not change webapp source or generated static assets.

## Remaining Release Evidence

Clean Windows 7/WebView2 109 bundle smoke remains Phase 7 work. Representative
real C/C++ project validation remains Phase 8 work. Neither is implied by the
repository-side Phase 5 test results.
