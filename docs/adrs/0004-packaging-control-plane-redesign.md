# ADR 0004: Packaging Control Plane Redesign

## Status

Accepted

## Context

The project already had working offline-packaging building blocks:

- `scripts/export-dependencies.py`
- `scripts/prepare-offline.ps1`
- `scripts/build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`
- `scripts/check-bundle-dependencies.py`

Those scripts were usable as internal stages, but they exposed too much operational complexity to human operators:

- too many entry points
- repeated path/asset parameters
- split release-readiness signals
- documentation that taught a multi-script sequence instead of a single public workflow

For a Windows 7 offline product, the packaging chain itself is part of the product experience. It needs one clear control surface and one clear verdict model.

## Decision

Adopt `scripts/package.ps1` as the single public packaging control plane.

The control plane is responsible for:

- command dispatch: `doctor`, `deps`, `assemble`, `verify`, `release`
- profile resolution (`dev`, `release`)
- orchestration of existing stage scripts
- final status calculation
- unified report output under `build/offline-reports/`

The existing stage scripts remain in the repository, but they are reclassified as:

- internal stages
- compatibility shims
- lower-level maintenance utilities

The default operator-facing guidance becomes:

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 release
```

## Consequences

Positive:

- human operators get one public entry point
- release readiness becomes easier to audit
- automation can consume one report model instead of correlating multiple outputs
- the old stage scripts can continue to exist without remaining the public UX

Trade-offs:

- there is now a second layer above the old scripts that must be maintained
- mocked orchestration tests are required to keep the control plane stable
- real bundle-path validation still must be completed after the control plane exists

Non-goals:

- this ADR does not settle LLVM version convergence
- it does not complete Win7 real-machine validation
- it does not by itself solve site-packages size optimization

## Follow-Up

Required next steps:

1. validate `package.ps1 release` against the real bundle path, not only mocked stages
2. update all operator-facing docs to prefer the control plane
3. keep stage-script compatibility only as long as needed for migration
