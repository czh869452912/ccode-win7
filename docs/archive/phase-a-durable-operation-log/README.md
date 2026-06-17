# Phase A Durable Operation Log Archive

This directory preserves the completed Pi-inspired minimal Core Phase A implementation plan.

Durable conclusions now live in:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/frontend-protocol.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

Archived materials:

- `2026-06-13-durable-operation-log.md`

Current official operation truth is reducer-backed schema v2 `operation_started`, `operation_finished`, and `operation_interrupted` events. Legacy replay events remain session replay/history inputs, not operation-state inference inputs.

