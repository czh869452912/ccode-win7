# Interaction Response Async

> 状态：`archived`
> 类型：`implementation closeout`
> 完成日期：`2026-07-20`
> 实现提交：`6ce5e033`

## Scope

This package records the approved design and implementation plan for the GUI
`ask_user`/permission response latency fix. The implementation keeps
`HostedInteractionService` as the Host boundary, returns a generic accepted
acknowledgement, and resumes Core/command work through backend coordination.

## Contents

- `2026-07-20-interaction-response-async-design.md` — approved design and
  implementation closeout.
- `2026-07-20-interaction-response-async-plan.md` — execution plan and closeout
  notes.

## Durable Conclusions

- `accepted` responses carry no session snapshot; resolved events and subsequent
  session snapshots remain authoritative.
- Pending interaction claim, permission policy, command execution, and Core
  resume lifecycle remain backend-owned.
- The frontend clears resolving state from generic resolved events and does not
  register or branch on tool/workflow names.
- Diagnostics are credential-free and exclude prompts, answers, source text,
  raw tool output, and permission secrets.

Current source-of-truth documents are [frontend-protocol.md](../../frontend-protocol.md),
[frontend-gui.md](../../modules/frontend-gui.md),
[protocol-and-core.md](../../modules/protocol-and-core.md), and
[development-tracker.md](../../development-tracker.md). This archive is
historical reference only.
