# Frontend Event Publication Convergence Archive

> 状态：`archive`
> 关闭日期：`2026-08-16`

本目录保存已完成的 frontend event publication 收敛切片，仅用于历史追溯，不承载当前架构真相。

## Contents

- `2026-08-16-frontend-event-publication-convergence-design.md`：已批准的根因设计。
- `2026-08-16-frontend-event-publication-convergence.md`：已执行的 TDD 实施与验证计划。

## Durable Authorities

- `docs/platform/frontend-protocol.md`
- `docs/platform/protocol.md`
- `docs/platform/frontend-tui.md`
- `docs/current-status.md`
- `docs/implementation-roadmap.md`

当前实现以单一 synchronization phase、单一 ordered event queue、delivered-before-committed runtime action publication、Host sink failure propagation 及共享跨语言契约为准。归档内的诊断过程和临时计划不得覆盖这些活跃权威。
