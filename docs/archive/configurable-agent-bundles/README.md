# Configurable Agent Bundles

> 状态：`archive`
> 类型：`completed slice package`
> 关闭日期：`2026-08-09`
> 实现基线：`262e79fd`

## Scope

本包保存 official offline bundle flavors 的已关闭设计与执行计划。实现将产品选择收敛为 official recipe、immutable bundle plan 和贯穿 dependency export、staging、validation、release identity、target evidence 与 runtime policy 的同一 hash binding。

首批官方 flavor 为 workflow-neutral CLI `minimal-cli` 与默认 C/C++ desktop `cpp-desktop`。两者保持精确六 wheel 交付边界，并让 profile assurance 与 flavor content 正交。

## Materials

### Specification

- `specs/2026-08-09-configurable-agent-bundle-flavors-design.md`

### Plan

- `plans/2026-08-09-configurable-agent-bundle-flavors.md`

## Current Authority

当前行为只查阅 `docs/product/composition.md`、`docs/product/packaging-and-deployment.md`、`docs/guides/configuration-guide.md`、`docs/guides/win7-release-runbook.md` 与 `docs/current-status.md`。本包不参与当前实现决策。

两个 flavor 的 clean-machine Windows 7 evidence 仍是独立的外部 release acceptance 条件；归档本实现切片不代表目标机验收已完成。
