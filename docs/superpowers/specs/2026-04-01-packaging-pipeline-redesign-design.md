# Offline Packaging Pipeline Redesign

> Status: approved design baseline
> Date: 2026-04-01
> Scope: Phase 7 packaging control-plane redesign

---

## 1. Goal

Replace the current multi-script offline packaging workflow with a single declarative packaging control plane that is easier to operate, easier to document, and unambiguous about whether a bundle is developer-only or truly release-ready.

This redesign does not change the project-level constraints:

- Windows 7 remains the deployment target.
- Offline deployment remains mandatory.
- The final bundle remains fully self-contained.
- The LLVM/Clang-centered C development scope remains unchanged.

The change is specifically about the packaging chain operator experience, packaging state model, and packaging governance.

---

## 2. Current Problems

The current chain works, but it is not pleasant or reliable to operate as the public packaging interface.

### 2.1 Too many user-facing entry points

The operator currently has to understand the difference between:

- `scripts/export-dependencies.py`
- `scripts/prepare-offline.ps1`
- `scripts/build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`
- `scripts/check-bundle-dependencies.py`

This creates unnecessary cognitive load. The operator is forced to understand internal build stages instead of using a product-level packaging command.

### 2.2 Repeated and confusing parameters

The current flow repeats high-friction parameters across multiple stages:

- asset selection
- site-packages source
- LLVM path
- WebView2 path
- download policy

That is acceptable for internal building blocks, but it is poor as the public interface.

### 2.3 Success criteria are split across multiple tools

The current workflow can leave the operator with an unclear answer to the core question:

`Is this bundle actually releasable?`

Today that answer may depend on:

- `warn` versus `fail`
- whether `-RequireComplete` was passed
- whether `check-bundle-dependencies.py` was also run
- whether GUI smoke was separately checked

This is too fragmented.

### 2.4 The guide and the scripts have drifted apart

The public guide already teaches a staged linear flow, but the underlying scripts still expose internal mechanics directly. This makes the documented user experience and the real tooling experience diverge.

---

## 3. Design Principles

The new packaging chain should follow these principles.

### 3.1 One public control plane

The user-facing packaging interface must converge to one command surface:

- `scripts/package.ps1`

All human-facing documentation should treat this as the only recommended entry point.

### 3.2 Declarative configuration first

Frequent packaging choices should live in a shared config file, not in repeated command-line flags.

The command line remains for:

- selecting the subcommand
- selecting the profile
- overriding a small number of one-off values

### 3.3 Clear operator mental model

The operator should think in terms of:

- what they want to produce
- how strict the packaging mode is
- whether the result is developer-only or release-ready

The operator should not need to understand internal staging mechanics to do routine work.

### 3.4 Single packaging truth

There must be one authoritative packaging result and one authoritative release verdict.

The chain must not require humans to mentally merge multiple partially overlapping validation outputs.

### 3.5 Preserve proven internals while redesigning the surface

Existing scripts can continue to exist as internal stages during migration, but they should stop being the public interface.

---

## 4. Proposed Control Plane

Introduce a new packaging control entry point:

- `scripts/package.ps1`

This becomes the only public command documented for offline packaging operations.

### 4.1 Public subcommands

The public command surface is:

- `doctor`
- `deps`
- `assemble`
- `verify`
- `release`

Example usage:

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 deps
pwsh -File scripts/package.ps1 assemble -Profile dev
pwsh -File scripts/package.ps1 verify -BundleRoot build/offline-dist/embedagent-win7-x64
pwsh -File scripts/package.ps1 release
```

### 4.2 Subcommand roles

`doctor`

- Checks whether the current machine can perform packaging work.
- Reports missing prerequisites, default config resolution, and likely failure points.
- Produces no bundle artifact.

`deps`

- Resolves or exports vendored Python dependencies.
- Resolves required third-party asset availability.
- Produces reusable cache state, not a final bundle.

`assemble`

- Builds staging and distribution outputs.
- Supports developer-oriented packaging runs.
- May optionally skip zip generation for faster local iteration.

`verify`

- Verifies an existing bundle without rebuilding it.
- Produces the authoritative packaging verdict for the inspected bundle.
- Must be usable independently by humans and future CI.

`release`

- The primary operator path.
- Runs the required packaging stages in order.
- Produces a strict release verdict and the final report.

---

## 5. Packaging Profiles

The chain should use explicit profiles so that the operator can choose intent without learning internal switches.

### 5.1 `dev` profile

Purpose:

- local iteration
- smoke packaging
- local bundle validation before final release

Characteristics:

- allows some non-release warnings
- may skip zip generation
- may tolerate development-oriented validation gaps
- must never claim release readiness

### 5.2 `release` profile

Purpose:

- formal distributable bundle generation
- Win7-targeted release preparation

Characteristics:

- requires complete required assets
- requires full validation gate success
- requires zip generation
- may not downgrade release blockers into warnings

### 5.3 Default profile behavior

Recommended defaults:

- `assemble` defaults to `dev`
- `release` defaults to `release`
- `verify` defaults to the profile recorded in the bundle report if available; otherwise it requires explicit selection or falls back to strict verification semantics

---

## 6. Declarative Configuration

Introduce a shared packaging configuration file:

- `scripts/package.config.json`

This file is the packaging policy source of truth for routine packaging behavior.

### 6.1 Configuration responsibilities

The config should define:

- default artifact naming
- default profile
- required assets by profile
- optional assets by profile
- download policy by profile
- site-packages source strategy
- LLVM source strategy
- WebView2 requirements
- zip policy
- validation gates
- report locations

### 6.2 What should move out of routine CLI usage

The following should normally come from config rather than repeated flags:

- asset lists
- site-packages source path or strategy
- LLVM root or strategy
- WebView2 runtime requirement
- whether downloads are allowed by default
- whether GUI assets are required

### 6.3 CLI overrides

Command-line overrides should exist, but remain limited to exceptional cases.

Examples:

- alternate config path
- bundle root override for verify
- output root override
- artifact name override
- explicit one-off `AllowDownload`

---

## 7. Internal Stage Model

The new control plane may continue to reuse existing script logic during migration, but those stages become internal implementation details rather than user-facing products.

The internal stages are conceptually:

1. dependency export / dependency resolution
2. third-party asset resolution
3. staging assembly
4. distribution assembly
5. validation
6. reporting

These stages should be orchestrated by `package.ps1`.

The operator should not need to reason about:

- whether they are in `prepare` versus `build`
- whether `validate` must be followed by another checker
- whether a missing component is acceptable in the current mode

That interpretation belongs to the control plane.

---

## 8. Final Status Model

The new packaging chain should collapse packaging outcomes into a small, explicit status vocabulary.

### 8.1 Allowed final states

- `READY`
- `DEV_ONLY`
- `NOT_READY`

### 8.2 Meaning of each state

`READY`

- The bundle satisfies the release gate for the selected release-oriented workflow.
- It is acceptable to hand off for Win7 release validation or shipment, depending on remaining process policy.

`DEV_ONLY`

- The bundle assembled successfully enough for developer use or local validation.
- It is not allowed to be described as release-ready.

`NOT_READY`

- The bundle failed a required build or validation gate.
- It must not be presented as usable release output.

### 8.3 Rules

- `release` may only finish as `READY` or `NOT_READY`
- `assemble -Profile dev` may finish as `DEV_ONLY` or `NOT_READY`
- `verify` must emit an explicit final state rather than only warnings and raw findings

This design removes ambiguity from the operator experience.

---

## 9. Exit Codes

The packaging chain should use a stable exit-code model.

- `0` = success for the requested operation
- `1` = packaging or validation failure
- `2` = invalid user input or invalid config
- `3` = missing or failed external asset acquisition

This makes the control plane usable by both humans and future automation.

---

## 10. Unified Reporting

Every meaningful packaging run should produce a single structured report.

Recommended location:

- `build/offline-reports/latest.json`
- `build/offline-reports/<timestamp>-<command>.json`

### 10.1 Required report fields

The report should contain at least:

- command
- profile
- artifact name
- bundle root
- zip path
- resolved configuration summary
- assets summary
- validation summary
- final status
- blocking issues
- warnings
- generated-at timestamp

### 10.2 Why this matters

This report becomes the single operator-facing answer to:

- what was built
- which policy was used
- what failed
- whether the result is releasable

This replaces the current situation where humans must correlate multiple outputs manually.

---

## 11. Migration Strategy

Migration should happen in controlled phases.

### 11.1 Phase A: introduce the new control plane

Create:

- `scripts/package.ps1`
- `scripts/package.config.json`

The new entry point may initially call existing internals, but the external command surface must already be the new one.

### 11.2 Phase B: unify status and reports

All packaging stages should return normalized results that the control plane can translate into:

- a final state
- a final exit code
- a final JSON report

This is the point where public documentation should stop teaching the old scripts as first-class entry points.

### 11.3 Phase C: internalize old scripts

The following tools remain temporarily for compatibility or stage reuse:

- `scripts/export-dependencies.py`
- `scripts/prepare-offline.ps1`
- `scripts/build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`
- `scripts/check-bundle-dependencies.py`

But they should be treated as internal implementation stages or compatibility shims.

### 11.4 Validation convergence

The long-term target is a single authoritative verification system.

The project should avoid indefinitely maintaining two parallel human-facing validation paths:

- the PowerShell bundle validator
- the Python dependency checker

If both remain temporarily, the control plane must still combine them into one authoritative final verdict.

---

## 12. Documentation Changes

This redesign requires documentation reclassification.

### 12.1 `docs/offline-packaging-guide.md`

Role after redesign:

- operator manual
- public packaging workflow reference

It should teach only the new `package.ps1` interface.

### 12.2 `docs/offline-packaging.md`

Role after redesign:

- architecture and packaging model reference

It should describe:

- bundle layout
- profile semantics
- validation philosophy
- component requirements

It should not be the main place for operational command recipes.

### 12.3 Other required updates

Also update:

- `docs/development-tracker.md`
- `docs/design-change-log.md`
- optionally a new ADR for the packaging control-plane redesign

---

## 13. Out of Scope

This redesign does not itself solve:

- final LLVM/Clang version convergence
- Win7 real-machine validation results
- real C project default recipe selection
- final site-packages minimization policy

Those remain important, but they are downstream of the packaging control-plane redesign.

---

## 14. Testing And Acceptance

The redesign should be accepted only when all of the following are true.

### 14.1 Operator experience acceptance

An operator can complete the routine packaging workflow using:

- one documented command family
- one documented guide
- one clear release verdict model

### 14.2 Technical acceptance

`package.ps1 release` must be able to:

- resolve dependencies
- assemble the bundle
- run verification
- emit a final report
- exit with a stable success/failure code

### 14.3 Documentation acceptance

The public guide must no longer require operators to memorize the old multi-script sequence as the primary workflow.

---

## 15. Recommended Implementation Order

1. Add `scripts/package.ps1`
2. Add `scripts/package.config.json`
3. Implement `release` and `doctor`
4. Implement `deps`, `assemble`, and `verify`
5. Add normalized JSON report output
6. Reclassify old scripts as internal stages
7. Rewrite packaging documentation around the new control plane

---

## 16. Final Design Statement

The offline packaging chain should move from a public multi-script workflow to a single declarative packaging control plane centered on:

- one public entry point
- profile-based packaging behavior
- one authoritative validation verdict
- one authoritative packaging report

This redesign is intended to reduce operator friction, reduce command memorization, eliminate ambiguity around release readiness, and make the offline bundle pipeline behave like a product feature rather than a collection of internal scripts.
