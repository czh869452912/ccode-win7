# Architecture Change Process

> 状态：`active`
> 类型：`workflow`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`

## When To Use

Use this workflow for distribution ownership, Core/Host/workflow/frontend boundaries, public contracts, durable state, permission policy, offline runtime, or release evidence changes.

## Inputs

- current authority selected through `docs/README.md`;
- affected code and tests;
- constraints from `AGENTS.md`;
- meaningful alternatives and compatibility/deletion implications;
- an active spec/plan only when the change needs temporary execution context.

## Design

State the problem, current boundary, proposed owner, data/control flow, alternatives, non-goals, risks, and measurable acceptance conditions. New Core responsibilities require explicit proof that a focused port, Host service, workflow package, or extension cannot own them safely.

## Sync Rules

1. Update the affected architecture, module, or contract authority.
2. Update `docs/README.md` or the code-doc matrix only if routing/ownership changed.
3. Add or update an ADR when durable rationale and alternatives must persist.
4. Replace `docs/current-status.md` when priorities, blockers, or evidence state changed.
5. Keep `docs/implementation-roadmap.md` limited to still-open sequencing and exit conditions.

## Review Gates

- dependency direction and distribution ownership remain valid;
- event/session truth has one writer and one durable source;
- activation, execution, permissions, and write-path decisions remain separate;
- Windows 7, Python 3.8, offline, C/C++, and release evidence constraints remain explicit;
- obsolete pre-release shapes are deleted rather than wrapped;
- focused tests, architecture guards, full partition, lint, and affected frontend/delivery gates pass.

## Closeout

1. Confirm the owning authority describes the landed behavior.
2. Confirm any required ADR records the durable decision.
3. Replace current status if the active focus changed.
4. Remove the slice from `docs/superpowers/README.md`.
5. Move completed spec/plan and useful evidence into an indexed archive package.

Do not close by appending the same completion statement to multiple global documents.
