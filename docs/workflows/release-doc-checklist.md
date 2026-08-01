# Release Documentation Checklist

> 状态：`active`
> 类型：`workflow`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`

## Navigation And State

- [ ] `docs/README.md` routes packaging and target acceptance to the current product authority/runbook.
- [ ] `docs/current-status.md` states the actual release state, blockers, and evidence boundary.
- [ ] `docs/implementation-roadmap.md` contains only open release sequencing and exit conditions.
- [ ] `README.md` release summary agrees with current status without duplicating evidence history.

## Contract And Guide

- [ ] `docs/product/packaging-and-deployment.md` matches the distribution and bundle layout.
- [ ] `docs/guides/win7-release-runbook.md` matches current commands, report schema, hashes, WebView2 and C smoke requirements.
- [ ] `scripts/offline-runtime-contract.json` covers every runtime binary and release gate.
- [ ] configuration examples contain no secrets and do not require network for base startup.

## Evidence Boundary

- [ ] Local tests and hosted CI are not presented as clean Windows 7 acceptance.
- [ ] Release claims require target-style windowed GUI, Fixed Version WebView2 109, bundle-local C smoke, and hash-bound structured evidence.
- [ ] `publishable` and acceptance state match validated evidence rather than plan completion.

## Verification

- [ ] Six distributions build, inspect, and isolate-smoke successfully.
- [ ] `scripts/package.ps1 doctor` and `release` use the documented control plane.
- [ ] Architecture guards, full Python partition, lint, and frontend test/build gates pass as applicable.
- [ ] Paths, commands, links, metadata, and documentation context budgets are checked.

## Archive Closure

- [ ] Completed release specs/plans and evidence summaries are moved to an indexed archive package.
- [ ] `docs/superpowers/README.md` lists only release work with open acceptance conditions.
- [ ] Durable conclusions are present in the owning domain authority, runbook, status, roadmap, or ADR before archival.
