# Configurable Agent Bundle Flavors Design

> Status: approved design, implementation pending
> Date: 2026-08-09
> Audience: product composition, packaging, and release maintainers
> Post-read action: implement official portable bundle flavors without weakening the six-distribution, offline-runtime, or release-evidence contracts

## 1. Outcome

EmbedAgent will support a small registry of official portable bundle flavors. The first two
flavors are `minimal-cli` and `cpp-desktop`. A flavor selects product behavior and delivery
surface; it does not select project wheels, raw asset paths, or release gates.

Packaging will compile each flavor into one immutable, JSON-safe `CompiledBundlePlan` before
dependency export or staging begins. Dependency export, staging, launcher generation,
validation, manifests, release identity, and evidence validation will consume that same plan.
They must not independently infer bundle contents.

The public packaging surface remains intentionally small:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 `
  release -Profile release -Flavor minimal-cli

powershell -ExecutionPolicy Bypass -File scripts/package.ps1 `
  release -Profile release -Flavor cpp-desktop -Reproducible
```

`cpp-desktop` remains the default when `-Flavor` is omitted, preserving the current product
release behavior.

## 2. Current Gap

The repository already has two useful but disconnected foundations:

- package profiles control operational behavior such as development versus release rigor,
  archive creation, frontend build, dynamic checks, and completeness requirements;
- build-time Agent composition can validate a component graph and export deterministic Agent
  manifest and lock data.

The production packaging pipeline does not consume the compiled Agent definition. It always
expects all six project wheels, the complete product application tree, GUI assets, native GUI
launchers, WebView2, LLVM, and the C/C++ validation workspace. Runtime application selection
changes which application is activated after launch but does not change bundle contents.

The build-time composition package also lacks the production component catalog and delivery
metadata needed to derive a runnable bundle. Its current export proves deterministic component
selection and asset locking; it is not a portable-product assembler.

## 3. Goals

- Make the common release command select one of a few audited product flavors.
- Keep build assurance (`dev` or `release`) independent from product contents.
- Preserve the exact six project distributions for every portable offline product export.
- Remove large unused runtime assets and shell dependencies from `minimal-cli`.
- Derive runtime assets and applicable release gates from declared capabilities.
- Keep the offline runtime contract as the only list of runtime-invoked external binaries and
  their validation requirements.
- Make every produced bundle explainable through a hash-bound plan, Agent lock, manifest, and
  release identity.
- Leave a controlled path to future custom `AgentProductDefinition` packaging without exposing
  it as a supported public command in the first release.

## 4. Non-Goals

- Reducing the number of project distributions in a portable product bundle.
- Adding a second wheel builder or bypassing the mandatory six-wheel checker.
- Treating `core-sdk` as another portable product flavor. The independently built Core wheel
  and its isolation smoke already own that use case.
- Letting callers enumerate assets, binary paths, project wheels, or gates.
- Accepting executable build logic, online installation, or arbitrary scripts from a product
  definition.
- Building a remote registry, marketplace, or general-purpose package solver.
- Preserving obsolete internal packaging shapes during the pre-release transition.

## 5. Vocabulary And Ownership

`Profile` means operational assurance. It controls development versus release strictness,
reproducibility, archive production, cache policy, reporting, and other orchestration concerns.
It does not define product capabilities.

`Flavor` means a stable official product recipe. It selects an Agent product definition,
shells, and a credential-free configuration template.

`Target` means the delivery environment and layout contract. The initial target remains
`win7-x64-portable`.

`CompiledBundlePlan` is the complete derived build input. It is immutable, JSON-safe,
credential-free, deterministic, and hashable.

The component catalog owns trusted component declarations and dependency/conflict closure.
The runtime contract owns external runtime capability providers, staged paths, and release-gate
applicability. The asset manifest owns download location, version, checksum, extraction, and
license metadata. The package profile owns operational assurance. None of these authorities may
duplicate another's data.

## 6. Public Interface

The first public interface is the existing packaging command with one new option:

```powershell
package.ps1 <doctor|deps|assemble|verify|release> `
  -Profile <dev|release> `
  -Flavor <minimal-cli|cpp-desktop>
```

Rules:

- `-Profile` and `-Flavor` are orthogonal.
- Omitted `-Flavor` resolves to `cpp-desktop`.
- Unknown flavors fail before dependency export or filesystem staging.
- `doctor`, `deps`, `assemble`, `verify`, and `release` all resolve the same flavor.
- A later `-ProductDefinition` option, if added, must be mutually exclusive with `-Flavor` and
  must compile through the same trusted catalog and bundle planner.
- No public option may disable a gate derived for a release plan.

The package configuration adds only the default flavor. The official registry remains
version-controlled product composition code. The configuration does not gain per-flavor copies
of asset or gate lists:

```json
{
  "default_flavor": "cpp-desktop"
}
```

## 7. Official Recipe Interface

The official registry optimizes the common maintainer operation: select a supported product
shape and run the normal package command.

```python
from dataclasses import dataclass
from typing import Callable, Tuple


@dataclass(frozen=True)
class OfficialBundleRecipe:
    recipe_id: str
    definition_factory: Callable[[], AgentProductDefinition]
    shell_ids: Tuple[str, ...]
    config_template_id: str


class FrozenBundleRecipeRegistry(object):
    def names(self) -> Tuple[str, ...]:
        ...

    def resolve(self, recipe_id: str) -> OfficialBundleRecipe:
        ...
```

Recipes contain references only. They cannot contain asset IDs, paths, wheel names, dependency
package names, validator scripts, or gate IDs. That information is derived from trusted
component and runtime contracts.

The registry is frozen before compilation. Duplicate IDs, unknown definition factories,
unsupported shells, and incomplete recipes fail closed.

## 8. Agent Composition Evolution

`AgentProductDefinition` replaces its single GUI reference with general shell references and
retains focused component groups:

```python
@dataclass(frozen=True)
class AgentProductDefinition:
    agent_id: str
    profile: ComponentRef
    providers: Tuple[ComponentRef, ...] = ()
    workflows: Tuple[ComponentRef, ...] = ()
    tools: Tuple[ComponentRef, ...] = ()
    resources: Tuple[ComponentRef, ...] = ()
    host: Optional[ComponentRef] = None
    shells: Tuple[ComponentRef, ...] = ()
```

`ComponentManifest` gains abstract runtime requirements:

```python
runtime_requirements: Tuple[str, ...] = ()
```

Examples are `runtime.python`, `shell.bash`, `search.rg`, `symbols.ctags`,
`toolchain.clang`, and `renderer.webview2`. Components do not declare binary locations or
asset archives.

The production catalog registers product profiles, the generic Host/provider/toolset,
workflow packages, and shell components. Compilation validates component kinds, versions,
dependencies, conflicts, namespaces, and runtime requirement identifiers before producing the
Agent lock.

## 9. Bundle Plan

The internal bundle compiler accepts a trusted recipe, target, and assurance level and returns
one plan:

```python
@dataclass(frozen=True)
class CompiledBundlePlan:
    schema_version: int
    flavor_id: str
    target_id: str
    assurance: str
    artifact_name: str
    agent_id: str
    config_template_id: str
    allowed_agent_application_ids: Tuple[str, ...]
    component_ids: Tuple[str, ...]
    shell_ids: Tuple[str, ...]
    plan_fact_ids: Tuple[str, ...]
    runtime_capability_ids: Tuple[str, ...]
    runtime_component_ids: Tuple[str, ...]
    asset_ids: Tuple[str, ...]
    python_feature_ids: Tuple[str, ...]
    launcher_ids: Tuple[str, ...]
    gate_ids: Tuple[str, ...]
    project_distribution_ids: Tuple[str, ...]
    agent_lock_sha256: str
    component_catalog_sha256: str
    runtime_contract_sha256: str
```

For every portable target, `project_distribution_ids` is the exact ordered six-distribution
set. It is a validated invariant, not a configurable recipe field.

`python_feature_ids` select dependency groups declared by the owning distribution metadata.
They do not contain copied package requirement strings. This permits a CLI flavor to omit GUI
third-party dependencies while keeping dependency truth in `pyproject.toml` and the lockfile.
Supporting this requires moving GUI-only third-party dependencies behind an owning product
extra or equivalent locked feature. Project distribution dependencies remain unchanged.

The plan is serialized before dependency export. Every later stage records and verifies its
hash. `config_template_id` is resolved from the trusted recipe during compilation so staging
never needs to reopen the recipe registry. A stage receiving a plan with an unsupported schema
version, mismatched hash, or missing field fails before mutating its output tree.

`allowed_agent_application_ids` and `shell_ids` are also runtime restrictions. A project wheel
being present does not make every packaged application or shell available. Product bootstrap
loads the bundle manifest and rejects an application or shell outside the compiled plan before
constructing Host services or launchers.

`plan_fact_ids` is a sorted derived set used only for bounded contract conditions. Facts are
namespaced, for example `component.workflow.cpp`, `runtime.toolchain.clang`, `shell.gui`,
`assurance.release`, and `target.win7-x64-portable`. Recipes cannot add arbitrary facts.

## 10. Runtime Contract Evolution

The runtime contract evolves from an unconditional full-product list into a target-aware
capability resolver while remaining the only runtime binary and release-gate authority.

```json
{
  "schema_version": 2,
  "targets": {
    "win7-x64-portable": {
      "always_requires": ["runtime.python"],
      "always_gates": ["runtime_contract"]
    }
  },
  "runtime_components": [
    {
      "id": "python",
      "provides": ["runtime.python"],
      "asset_id": "python_embedded_x64",
      "paths": ["runtime/python/python.exe"]
    },
    {
      "id": "webview2",
      "provides": ["renderer.webview2"],
      "asset_id": "webview2_fixed_runtime_x64",
      "paths": ["runtime/webview2-fixed-runtime"]
    }
  ],
  "release_gates": [
    {
      "id": "cpp_smoke_workspace",
      "applies_when": {
        "all_of": ["component.workflow.cpp", "runtime.toolchain.clang"]
      }
    }
  ]
}
```

Conditions are data, not code. They evaluate only against the compiler-produced, namespaced
plan facts. The only supported operators are bounded `all_of`, `any_of`, and `not`. Unknown
operators, facts, capability IDs, ambiguous providers, or dependency cycles fail closed.

The asset manifest remains unchanged in purpose. The planner follows each selected runtime
component's `asset_id` to obtain its pinned archive metadata. Missing assets or duplicate asset
ownership fail compilation or doctor preflight.

## 11. Initial Flavors

### `minimal-cli`

The recipe selects the generic Agent application, local Host, OpenAI-compatible provider,
workflow-neutral toolset, and CLI shell. The generated configuration template sets the generic
application ID and contains no credentials.

The capability closure includes only runtime components required by the selected Host, tools,
and CLI. It must exclude `renderer.webview2`, GUI launchers, C/C++ workflow activation,
`toolchain.clang`, the C/C++ workspace seed, and C/C++-specific gates. Bash, MinGit, ripgrep,
or other tools remain included when the selected workflow-neutral toolset or workspace
intelligence explicitly requires them.

The flavor still builds, checks, archives, and wheel-only installs all six project wheels. The
C/C++ workflow distribution is present but inactive. Most size reduction comes from omitted
LLVM, WebView2, GUI-only third-party dependencies, launchers, and validation assets rather than
from removing project wheels.

Release validation includes common static bundle validation, dependency isolation, CLI launch,
session creation, provider simulation, tool execution, permission/user-input interaction,
durable restore, and a clean-machine Windows 7 CLI smoke. It does not require GUI or C/C++
evidence.

### `cpp-desktop`

The recipe selects the default C/C++ application, local Host, OpenAI-compatible provider,
workflow-neutral and C/C++ toolsets, and CLI/TUI/GUI shells. It retains the existing
credential-free configuration template and C workspace seed.

Its capability closure includes Python, MinGit/Bash, ripgrep, Ctags, LLVM/Clang children,
WebView2, native GUI launchers, and the complete current release gate set. Its target acceptance
continues to require hash-bound clean Windows 7 GUI, bundled WebView2, and bundle-local C smoke
evidence.

## 12. End-To-End Data Flow

1. The package command resolves profile, flavor, and target without creating output.
2. The official recipe registry resolves the flavor.
3. Agent composition compiles the recipe's product definition and emits an Agent lock.
4. The bundle compiler closes runtime capabilities through the runtime contract.
5. Asset IDs are resolved through the asset manifest.
6. Applicable gates are derived from target, assurance, shells, and capability closure.
7. The compiler emits and hashes `CompiledBundlePlan`.
8. The mandatory distribution builder and checker produce exactly six wheels.
9. Dependency export installs the six project wheels with network resolution disabled and
   installs only the locked third-party features selected by the plan.
10. Staging materializes only the planned product tree, launchers, external assets,
    documentation, configuration template, and validation kit.
11. Validation recomputes the plan and checks actual files, dependencies, launchers, tools, and
    gates against it.
12. The bundle manifest and release identity bind source revision, flavor, Agent lock, plan,
    catalog, runtime contract, wheels, assets, product tree, and final artifact hashes.

Target evidence records the plan hash and the exact derived gate IDs. Evidence validation
rejects missing applicable gates and also rejects reports claiming a shell, workflow, or gate
that is outside the plan.

## 13. Configuration And Secrets

Each recipe refers to a credential-free configuration template. A template may set the default
application ID, empty model name, non-secret local base URL, default mode, context budgets, and
write-policy defaults. It must not contain an API key, credential, approval token, prompt body,
source content, or raw tool output.

Flavor selection is a build fact stored in the bundle manifest and release identity. Runtime
application overrides may be allowed only when the selected application is present and does not
require runtime capabilities absent from the compiled bundle. Unsupported overrides fail with
an explicit capability-missing error rather than silently using system tools or network
resolution.

The bundle manifest also carries `allowed_agent_application_ids` and `shell_ids`. The CLI must
reject `--agent-application` or shell-selection requests outside these sets. In particular, the
presence of the C/C++ project wheel in `minimal-cli` does not permit activating its workflow,
and the presence of GUI source files in the product wheel does not permit launching GUI without
the planned GUI dependencies, launcher, and browser runtime.

## 14. Failure And Safety Rules

- Resolve and validate the plan before cleaning or creating any output directory.
- Unknown flavor, target, component, shell, capability, runtime provider, asset, dependency
  feature, launcher, or gate is blocking.
- A release plan cannot omit a gate whose condition matches.
- A staged runtime binary not selected by the plan is a validation error, not harmless excess.
- A selected runtime binary missing from the bundle is blocking.
- System tool fallback remains forbidden for portable release validation.
- Build and validation recompute plan hashes from canonical JSON; operational timestamps and
  paths do not enter the identity.
- Custom definitions remain disabled until a trusted catalog, schema validation, plan export,
  and negative security tests exist.

## 15. Compatibility And Migration

This is a pre-release internal cutover. Do not retain a second legacy staging path or aliases for
old configuration shapes.

Migration proceeds through one pipeline:

1. Introduce the recipe, catalog, plan, and resolver contracts with `cpp-desktop` producing a
   plan equivalent to the current bundle.
2. Make doctor and reports expose the resolved plan without changing staging.
3. Move dependency export, staging, validation, identity, and evidence selection to plan input,
   one owner at a time.
4. Prove `cpp-desktop` output and gates remain equivalent.
5. Add `minimal-cli`, credential-free configuration, CLI launcher set, and CLI evidence gate.
6. Remove superseded profile fields and unconditional staging branches.
7. Keep arbitrary product-definition input private until official recipes and negative tests
   demonstrate that plan derivation is fail-closed.

The current `dev` and `release` profile names remain. Existing release commands without a
flavor continue to resolve to `cpp-desktop`.

## 16. Verification And Acceptance

Contract tests must prove:

- profiles and flavors are orthogonal;
- official recipes are deterministic and registry IDs are unique;
- `cpp-desktop` preserves the exact six project distributions and complete current capability
  closure;
- `minimal-cli` preserves the exact six project distributions while excluding GUI, WebView2,
  LLVM, C/C++ workspace, and their gates;
- every component runtime requirement resolves to exactly one runtime component;
- every runtime component asset resolves to one pinned asset manifest record;
- applicable gates cannot be disabled by config or command-line input;
- unknown or conflicting declarations fail before output mutation;
- dependency export installs only plan-selected locked feature groups;
- staging contains neither missing planned files nor unplanned runtime binaries;
- release identity changes when flavor, plan, Agent lock, catalog, contract, wheels, or staged
  artifact changes;
- runtime bootstrap rejects applications and shells outside the plan even when their project
  wheel or source files are physically present;
- target evidence matches the plan hash and exact applicable gate set;
- reproducible builds of the same flavor produce matching stable artifacts.

Smoke tests must prove:

- `minimal-cli` launches from the isolated portable tree on Python 3.8, creates a durable
  session, completes a model/tool interaction using a controlled provider, enforces permission
  and path policy, and restores the session;
- `cpp-desktop` retains the existing GUI, interaction, C compilation, and evidence flows;
- each release flavor passes its own clean Windows 7 target gates, and no flavor claims evidence
  for a shell or workflow it does not contain.

Repository gates continue to include architecture guards, the full Python partition, release
partition, lint, frontend tests/build when GUI sources change, mandatory six-wheel
build/check/smoke, and the relevant flavor release pipeline.

## 17. Alternatives Considered

### Extend package profiles with product fields

This would add profiles such as `minimal-cli-release` and `cpp-desktop-release`, each containing
asset lists and build switches. It was rejected because it multiplies assurance and product
dimensions, duplicates runtime truth, and lets configuration silently omit required gates.

### One deep `build_bundle(target, ...)` function

This gives callers one to three entry points and hides all orchestration. It is attractive for
an internal API but makes official flavor discovery and plan inspection less explicit. The
chosen design keeps the deep compiler internally while exposing stable recipes to maintainers.

### Public arbitrary product-definition compiler

This offers maximum flexibility through general bundle requests and a public compiler. It was
deferred because the trusted production catalog, shell/runtime contribution model, conditional
contract, and negative validation surface must be proven first. Official recipes exercise the
same eventual architecture without prematurely promising arbitrary combinations.

## 18. Documentation Ownership On Implementation

When behavior is implemented, durable current truth moves into the product composition and
packaging/deployment authorities. The overall architecture changes only if distribution
topology, dependency direction, or the execution spine changes. Configuration and release
guides document flavor selection and flavor-specific evidence. The active design and execution
plan remain under the current-work index until every acceptance condition closes, then move to
an indexed archive package.
