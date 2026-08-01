# Documentation Workflows

> 状态：`active`
> 类型：`navigation`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`

These workflows implement one ownership model: update the document that owns the durable fact, change the global map only when routing changes, replace current state rather than appending history, and archive completed process material.

| Need | Workflow |
|---|---|
| Keep code and its owning documentation aligned | `docs/workflows/code-doc-sync.md` |
| Change a cross-layer architecture boundary | `docs/workflows/architecture-change-process.md` |
| Verify release-facing documentation and evidence claims | `docs/workflows/release-doc-checklist.md` |

`docs/documentation-governance.md` defines the five layers, authority rules, and context budgets. `docs/documentation-style-guide.md` defines writing and review rules. `docs/README.md` remains the only global map.

Closure means durable truth is synchronized once, the active-slice index is exact, and completed specs/plans are placed in an indexed archive package. It does not mean appending completion notes across entry, architecture, roadmap, and status documents.
