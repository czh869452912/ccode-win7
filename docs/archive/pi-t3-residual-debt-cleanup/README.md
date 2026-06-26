# Pi/T3 Residual Debt Cleanup Archive

> Status: completed slice archive
> Date: 2026-06-26

This package preserves the completed Pi/T3 residual architecture-debt cleanup plan.

Durable conclusions were synchronized into active source-of-truth docs before archiving:

- default hosted configuration uses `default_mode: explore` and `max_turns: null`
- `ToolRuntime.execute_for_mode` and adapter turn-runner compatibility wrappers are removed
- local skill/prompt slash command specs are projected from the slash-command boundary
- hosted `/review` evidence shaping lives in `ReviewCommandService`
- GUI run-output display state and transport connection/reload projection live under `webapp/src/session-runtime/`
- session activation and WebSocket lifecycle control live under focused `webapp/src/app-runtime/` controllers
- root GUI connection state was removed in favor of focused session transport state

Use active docs for current product truth.
