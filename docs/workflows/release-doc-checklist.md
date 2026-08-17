# Release Documentation Checklist

> 状态：`active`
> 类型：`workflow`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-09`

## Navigation And State

- [ ] `docs/README.md` routes packaging and target acceptance to the current product authority/runbook.
- [ ] `docs/current-status.md` states the actual release state, blockers, and evidence boundary.
- [ ] `docs/implementation-roadmap.md` contains only open release sequencing and exit conditions.
- [ ] `README.md` release summary agrees with current status without duplicating evidence history.

## Contract And Guide

- [ ] `docs/product/packaging-and-deployment.md` matches plan-selected distribution closures, official flavor plans, and conditional bundle layouts.
- [ ] `docs/guides/win7-release-runbook.md` matches current commands, report schema, plan hashes, and exact per-flavor gate requirements.
- [ ] `scripts/offline-runtime-contract.json` covers every runtime binary and release gate.
- [ ] configuration examples contain no secrets and do not require network for base startup.

## Evidence Boundary

- [ ] Local tests and hosted CI are not presented as clean Windows 7 acceptance.
- [ ] Release claims require hash-bound clean-target evidence for the exact plan-selected gates; minimal requires CLI smoke, while desktop additionally requires windowed GUI/WebView2 109 and bundle-local C smoke.
- [ ] `publishable` and acceptance state match validated evidence rather than plan completion.

## Verification

- [ ] Every plan-selected distribution closure builds, inspects, and isolate-smokes successfully.
- [ ] `scripts/package.ps1 doctor` and `release` use the documented control plane for both `minimal-cli` and `cpp-desktop`.
- [ ] Architecture guards, full Python partition, lint, and frontend test/build gates pass as applicable.
- [ ] Paths, commands, links, metadata, and documentation context budgets are checked.

## Archive Closure

- [ ] Completed release specs/plans and evidence summaries are moved to an indexed archive package.
- [ ] `docs/superpowers/README.md` lists only release work with open acceptance conditions.
- [ ] Durable conclusions are present in the owning domain authority, runbook, status, roadmap, or ADR before archival.
