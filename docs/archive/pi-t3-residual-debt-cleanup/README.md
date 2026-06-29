# Pi/T3 Residual Debt Cleanup Archive

> Status: completed slice archive
> Date: 2026-06-27

This package preserves completed Pi/T3 residual architecture-debt cleanup plans,
follow-up plans, and audit notes.

Durable conclusions were synchronized into active source-of-truth docs before archiving:

- default hosted configuration uses `default_mode: explore` and `max_turns: null`
- `ToolRuntime.execute_for_mode` and adapter turn-runner compatibility wrappers are removed
- local skill/prompt slash command specs are projected from the slash-command boundary
- hosted `/review` evidence shaping lives in `ReviewCommandService`
- GUI run-output display state and transport connection/reload projection live under `webapp/src/session-runtime/`
- session activation and WebSocket lifecycle control live under focused `webapp/src/app-runtime/` controllers
- root GUI connection state was removed in favor of focused session transport state
- permission policy now reads permission categories from runtime/catalog metadata and unknown categories ask by default
- ordinary command/build/test failures remain diagnostic tool results instead of hard loop stops
- GUI interaction activity and workspace refresh invalidation now come from backend/tool metadata contracts
- runtime configuration read-model invalidation is reducer-backed and tested from transcript events
- GUI backend route registration is delegated to route-family modules instead of
  concentrated in `server.py`
- hosted command and interaction glue now lives in `HostedCommandService` and
  `HostedInteractionService`
- provider snapshot, workflow prompt, and compaction payload assembly now lives
  in `TurnSnapshotService`, `PromptAssemblyService`, and `CompactionJournal`
- `grep_text` accepts file roots and reports diagnostic search/path failures
  without tripping no-progress guard-stop behavior
- default workspace search skips `.embedagent/memory`
- GUI composer slash commands are projected from backend command capabilities
  instead of static frontend hints
- context usage accounting prefers provider usage metadata and ignores stale
  usage before the latest compact boundary
- legacy wrapper-level `ContextCompactionEngine` compaction was removed from
  `LLMClientRetryWrapper`

Archived materials:

- [2026-06-26-pi-t3-debt-cleanup.md](2026-06-26-pi-t3-debt-cleanup.md)
- [2026-06-26-pi-t3-followup-cleanup.md](2026-06-26-pi-t3-followup-cleanup.md)
- [2026-06-27-t3-gui-architecture-guards.md](2026-06-27-t3-gui-architecture-guards.md)
- [2026-06-27-pi-t3-residual-debt-audit.md](2026-06-27-pi-t3-residual-debt-audit.md)
- [2026-06-27-pi-t3-residual-debt-design.md](2026-06-27-pi-t3-residual-debt-design.md)
- [2026-06-27-pi-t3-residual-debt-cleanup.md](2026-06-27-pi-t3-residual-debt-cleanup.md)
- [2026-06-28-pi-t3-debt-cleanup.md](2026-06-28-pi-t3-debt-cleanup.md)
- [2026-06-29-pi-t3-debt-cleanup-design.md](2026-06-29-pi-t3-debt-cleanup-design.md)
- [2026-06-29-pi-t3-debt-cleanup.md](2026-06-29-pi-t3-debt-cleanup.md)

Use active docs for current product truth.
