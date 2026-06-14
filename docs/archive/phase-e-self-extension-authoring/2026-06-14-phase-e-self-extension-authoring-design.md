# Phase E Self-Extension Authoring Loop Design

## Purpose

Phase E turns local self-extension from a low-level file/loading capability into a safe product workflow.

The system already supports local resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes`, plus manifest-gated project-local Python extensions under `.embedagent/extensions/<name>/`. What is missing is an authoring loop that lets the agent create these capabilities consistently, validate them, and report the next trust decision without blurring resource reload and executable extension loading.

This phase keeps the Pi-inspired direction: a small core, capability boundaries, explicit manifests, diagnostics, and local self-extension that is powerful but unsurprising.

## Constraints

- Python `>=3.8,<3.9`; no Python 3.9+ syntax.
- Offline and Windows 7 compatibility remain mandatory.
- No Docker, WSL, VS Code, online registry, dependency installation, plugin marketplace, or remote extension install.
- Generated executable extensions must be disabled by default.
- Resource reload must remain file discovery only and must not execute Python code.
- Project extension loading remains separate and manifest-gated.
- Built-in tool replacement remains disallowed.
- Dynamic tools remain subject to `PermissionPolicy`.

## Current Baseline

Implemented foundations:

- `ToolRuntime.reload_resources()` discovers local skills, prompts, and recipe JSON files.
- `InProcessAdapter.reload_resources(...)`, `/resources reload`, and `POST /api/sessions/{session_id}/resources/reload` expose file-resource reload.
- `project_extensions.load_project_extensions(...)` discovers `.embedagent/extensions/<name>/extension.json`.
- Enabled extension manifests require permissions and workspace-bound entrypoints.
- `InProcessAdapter` loads enabled project extensions into the shared `ExtensionManager`.
- Dynamic tools register through the shared `ToolRuntime` and are activated through `ExtensionManager.allowed_tool_names(...)`.

Phase E should reuse these foundations, not bypass them.

## Interface Designs Considered

### Design A: One Authoring Service Entry Point

Expose a focused service:

```python
class SelfExtensionAuthoringService(object):
    def plan_artifacts(self, request: AuthoringRequest) -> AuthoringPlan: ...
    def write_artifacts(self, plan: AuthoringPlan) -> AuthoringResult: ...
    def validate_artifacts(self, result: AuthoringResult) -> AuthoringValidation: ...
```

Callers provide an `AuthoringRequest` with a capability kind, name, summary, and options. The service returns deterministic artifact paths and writes only under `.embedagent`.

This keeps the public surface small and hides path normalization, template details, duplicate checks, and validation rules.

Trade-off: the service has to own enough structured request vocabulary to cover skills, prompts, recipes, and extension skeletons.

### Design B: Separate Authoring Modules Per Artifact

Expose one module per artifact type:

```python
write_skill(...)
write_prompt(...)
write_recipe(...)
write_extension(...)
validate_skill(...)
validate_prompt(...)
validate_recipe(...)
validate_extension(...)
```

This is explicit and simple for tests, and each artifact writer can evolve independently.

Trade-off: callers need to know too many details, and the product workflow becomes a coordination layer spread across functions.

### Design C: Recipe-Driven Generator

Represent authoring itself as local recipes:

```json
{
  "id": "author.skill",
  "template": "skill",
  "inputs": {}
}
```

The agent would run a generator recipe to create files and then reload resources.

Trade-off: this makes the authoring mechanism extensible, but it creates a bootstrap problem. The product needs a reliable built-in authoring loop before local recipes can safely extend that loop.

## Recommendation

Use Design A, backed by small artifact-specific template helpers.

The service should expose one stable workflow to hosts and tools, while implementation stays split internally by artifact kind. This gives Agent Core a deep module: a small caller-facing interface that hides filesystem safety, manifest defaults, generated content shape, validation, diagnostics, and reload guidance.

## Product Workflow

The authoring loop is:

1. User asks the agent to create a local skill, prompt, recipe, or project extension.
2. Agent uses an authoring action/tool to create workspace-bound files.
3. The authoring result lists written files, skipped files, diagnostics, and next actions.
4. File resources can be reloaded through the existing reload path.
5. Project Python extensions remain disabled by default after generation.
6. If the user chooses to trust/enable a project extension, enabling and loading happen through the existing manifest-gated project extension loading path, not resource reload.

## Artifact Rules

### Skills

Path:

```text
.embedagent/skills/<slug>.md
```

Generated content:

- title
- purpose
- when to use
- inputs expected
- output contract
- validation notes

### Prompts

Path:

```text
.embedagent/prompts/<slug>.md
```

Generated content:

- title
- intended mode or workflow
- prompt body
- expected model behavior
- safety notes

### Recipes

Path:

```text
.embedagent/recipes/<slug>.json
```

Generated JSON object:

- `id`
- `tool_name`
- `recipe_action`
- `label`
- `command`
- `cwd`
- `timeout_sec`

Recipes are file resources only. Running them still goes through `run_recipe` and normal tool permission policy.

### Project Extension Skeletons

Path:

```text
.embedagent/extensions/<slug>/
  extension.json
  extension.py
  README.md
  recipes/validate.json
```

Generated manifest defaults:

```json
{
  "id": "<slug>",
  "enabled": false,
  "entrypoint": "extension.py",
  "description": "<summary>",
  "permissions": ["read"]
}
```

Generated Python skeleton:

- defines `create_extension(api)`
- returns a project extension object
- includes extension id metadata
- includes commented examples for resource discovery or read-only dynamic tool registration
- does not import third-party dependencies
- does not enable itself

Generated validation recipe:

- local command only
- defaults to a Python syntax check using the bundled/current Python executable contract where available
- remains a recipe file until explicitly run

## Safety Model

The authoring service must:

- resolve all output paths inside the workspace
- write only under `.embedagent/skills`, `.embedagent/prompts`, `.embedagent/recipes`, or `.embedagent/extensions`
- reject empty or invalid names
- normalize names to stable slugs
- avoid overwriting existing files by default
- emit diagnostics instead of partial silent failure
- generate disabled project extensions by default
- never import or execute generated extension code
- return explicit next-step text that distinguishes resource reload from extension loading

## API Shape

Initial module:

```text
src/embedagent/self_extension_authoring.py
```

Core data classes:

```python
@dataclass
class AuthoringRequest:
    kind: str
    name: str
    summary: str = ""
    body: str = ""
    command: str = ""
    recipe_action: str = "custom"
    permissions: List[str] = field(default_factory=lambda: ["read"])
    overwrite: bool = False

@dataclass
class AuthoredFile:
    path: str
    kind: str
    status: str

@dataclass
class AuthoringResult:
    success: bool
    kind: str
    name: str
    slug: str
    files: List[AuthoredFile]
    diagnostics: List[Dict[str, Any]]
    next_actions: List[str]
```

Service:

```python
class SelfExtensionAuthoringService(object):
    def author(self, request: AuthoringRequest) -> AuthoringResult:
        ...
```

This intentionally starts with one entry point. If artifact-specific complexity grows, helpers can stay private until a second public method is justified.

## Tool Surface

Add a workflow-neutral built-in tool:

```text
author_local_capability
```

It creates local self-extension artifacts through `SelfExtensionAuthoringService`.

Permission category:

```text
workspace_write
```

Mode visibility:

- `build`
- `debug`

It should not be visible in `explore`, `spec`, or read-only `verify` mode by default.

The tool does not reload resources and does not load project extensions. Its result tells the caller which existing operation to use next.

## Hosted Adapter Surface

Add a narrow adapter method only if needed by frontend/API tests:

```python
InProcessAdapter.author_local_capability(...)
```

The adapter method should call the same service as the tool and should not bypass `PermissionPolicy` for model-driven tool calls.

Frontend API can be deferred unless a later subphase needs a GUI button. The first slice can be agent-tool-first.

## Testing Strategy

Add tests for:

- skill artifact generation
- prompt artifact generation
- recipe artifact generation and discoverability after `reload_resources`
- extension skeleton generation with disabled manifest
- extension skeleton is discovered as disabled and not imported
- invalid names are rejected
- path traversal is rejected
- existing files are not overwritten by default
- overwrite works only when explicitly requested
- `author_local_capability` is absent from verify schemas and present in build schemas
- authoring tool result includes next actions distinguishing reload from extension loading

Regression tests:

- `tests/test_local_resources.py`
- `tests/test_project_extensions.py`
- `tests/test_tools_package.py`
- `tests/test_permissions.py`
- `tests/test_inprocess_adapter_frontend_api.py` if adapter surface lands

## Documentation Updates

When Phase E implementation lands, update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md` only if an API endpoint lands

## Phase E Subphases

### E-A: Authoring Service

Create `SelfExtensionAuthoringService`, data classes, path safety, slug normalization, diagnostics, and artifact writers for skills/prompts/recipes/extensions.

### E-B: Runtime Tool

Add `author_local_capability` as a workflow-neutral built-in tool with `workspace_write` permissions and mode-aware schema visibility.

### E-C: Validation And Reload Boundaries

Ensure generated recipe resources are discoverable only after reload, generated extensions are discovered disabled, and no Python extension code is imported during resource reload.

### E-D: Hosted Projection

If useful, expose adapter-level authoring state/result projection without adding broad frontend coupling.

### E-E: Docs And Archive

Synchronize active docs, archive Phase E design/plan materials, and mark the roadmap/tracker state.
