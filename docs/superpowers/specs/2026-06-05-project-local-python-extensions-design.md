# Project-Local Python Extensions Design

## Purpose

Slice 4 makes project-local Python extensions a controlled, offline-only capability.

The goal is not to create a plugin marketplace or a general Python execution platform. The goal is to let a workspace opt in to small in-process extension objects that use the already established `ExtensionManager` hooks, dynamic tool registration, local resource reload, diagnostics, and permission policy.

## Current Baseline

The previous slices established:

- `ExtensionManager` as the shared in-process capability boundary.
- Dynamic extension tool registration into the shared `ToolRuntime`.
- File-only local resource discovery for `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes`.
- Transcript-backed reload diagnostics and session snapshot extension state.

Current source-of-truth docs still state that project-local Python loading is deferred. This slice changes that from "not enabled" to "available only behind an explicit manifest and disabled-by-default policy."

## Scope

Included:

- Discover `.embedagent/extensions/<name>/extension.json`.
- Validate a strict manifest schema.
- Load `.embedagent/extensions/<name>/extension.py` only when manifest `enabled` is `true`.
- Build a narrow API object and pass it to `create_extension(api)` when present.
- Accept either a returned extension object or a module-level `EXTENSION` object.
- Register successfully loaded objects into the hosted runtime's shared `ExtensionManager`.
- Record load state and diagnostics without blocking bundled C/C++ harness behavior.
- Expose project extension load state through adapter diagnostics and session snapshot extension state.

Excluded:

- Installing dependencies.
- Remote downloads, registries, marketplaces, or online extension catalogs.
- Loading arbitrary files outside the workspace.
- Replacing built-in tools.
- Granting permission automatically to dynamically registered privileged tools.
- Exposing `QueryEngine`, `InProcessAdapter`, `Session`, or raw internal stores to project extension code.
- Hot-reloading project Python modules while a turn is running.

## Manifest

Each extension lives in:

```text
.embedagent/extensions/<name>/
  extension.json
  extension.py
```

The manifest is JSON object:

```json
{
  "id": "sample_extension",
  "enabled": true,
  "entrypoint": "extension.py",
  "description": "Optional human-readable summary.",
  "permissions": ["read"],
  "modes": ["explore", "spec", "build", "debug", "verify"]
}
```

Rules:

- `id` is required and must match `^[A-Za-z_][A-Za-z0-9_.-]*$`.
- `enabled` defaults to `false` if omitted.
- `entrypoint` defaults to `extension.py`.
- `entrypoint` must resolve inside that extension directory.
- `permissions` is required when `enabled` is `true`.
- allowed permission declarations are `read`, `workspace_write`, `shell_exec`, `toolchain_exec`, and `git_write`.
- `modes` is optional metadata for diagnostics. Active-tool gating remains owned by the extension hooks and existing mode policy.

Disabled manifests are considered discovered but not loaded. They produce a non-error state item with status `disabled`.

## Loader Behavior

The loader is deterministic and local:

1. Scan immediate child directories under `.embedagent/extensions`.
2. Read `extension.json` if present.
3. Validate manifest and workspace-bound paths.
4. If disabled, report status `disabled`.
5. If enabled, load `extension.py` with `importlib.util.spec_from_file_location`.
6. Create a narrow API object.
7. Prefer `create_extension(api)` when callable.
8. Otherwise use module-level `EXTENSION`.
9. Set missing metadata on the loaded object:
   - `extension_id`
   - `builtin_extension = False`
   - `project_extension = True`
10. Register the object into `ExtensionManager`.

Errors are captured as diagnostics and do not abort default extension assembly.

## Extension API

The first API is intentionally tiny:

```python
api.workspace
api.extension_id
api.manifest
api.ToolDefinition
api.Observation
api.ToolRegistrationResult
api.ResourcesDiscoverResult
api.PromptPatch
api.ContextPatch
api.ToolCallDecision
api.ToolResultPatch
api.WorkflowPatch
api.safe_join(*parts)
api.read_text(relative_path, max_chars=40000)
```

The API does not expose mutable core services. File helpers are workspace-bound and should raise `ValueError` on path escape.

This is not a sandbox. It is a guard-railed in-process extension API. The risk control comes from explicit manifest opt-in, clear diagnostics, permission classification, and existing tool permission enforcement.

## Runtime Integration

Project extension loading belongs outside `QueryEngine`.

`InProcessAdapter` owns the hosted runtime's shared `ExtensionManager`, so it should assemble project extensions after `build_default_extension_set(self.tools)` and before sessions use the manager for tool catalog, resource discovery, or query execution.

Direct `QueryEngine` users remain unchanged: they receive only the manager passed by their host.

The default C/C++ harness remains bundled and enabled by default. Project extension failures must not prevent sessions from starting.

## Diagnostics And State

The loader returns a payload shaped like:

```json
{
  "workspace": "D:/workspace",
  "counts": {
    "discovered": 2,
    "loaded": 1,
    "disabled": 1,
    "failed": 0
  },
  "extensions": [
    {
      "id": "sample_extension",
      "status": "loaded",
      "manifest_path": ".embedagent/extensions/sample/extension.json",
      "entrypoint": ".embedagent/extensions/sample/extension.py",
      "permissions": ["read"]
    }
  ],
  "diagnostics": []
}
```

Diagnostics should also be mirrored into `ExtensionManager` diagnostics with source `project` where practical, so existing frontend and snapshot paths can show failures without a separate diagnostics system.

Session snapshots should keep current `extension_diagnostics` behavior and may include:

```json
{
  "extensions": {
    "project_extensions": {
      "state": {
        "counts": {},
        "extensions": []
      }
    }
  }
}
```

## Security And Permission Policy

The loader does not make project code safe. It makes project code explicit.

Risk boundaries:

- Disabled by default.
- Manifest-gated.
- Workspace-bound entrypoint.
- No dependency installation.
- No raw core object access.
- Dynamic tools from project extensions still require source-aware catalog metadata.
- Privileged dynamic tools still trigger the same `PermissionPolicy` ask/rule path.
- Built-in tool replacement remains disallowed by `ToolRuntime.register_tool`.

If a workspace wants a project extension that registers a shell tool, the tool metadata must declare `shell_exec`; permission policy then decides whether the call is allowed, denied, or requires user approval.

## Testing Strategy

Focused tests should cover:

- Disabled manifest is discovered but not imported.
- Enabled manifest with `create_extension(api)` loads and registers into `ExtensionManager`.
- Enabled manifest can register a dynamic read-only tool through existing `register_tools`.
- Bad JSON, invalid id, path escape, missing permissions, import failure, and factory failure are diagnostics, not crashes.
- Loaded project extension diagnostics appear in adapter/session projection.
- Direct `QueryEngine` remains free of project loader imports.

Regression tests should include:

- `tests/test_local_resources.py`
- `tests/test_dynamic_tool_registration.py`
- `tests/test_capability_extensions.py`
- `tests/test_workflow_extensions.py`
- `tests/test_inprocess_adapter_frontend_api.py`

## Documentation Updates

When implementation lands, update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The durable docs must say project-local Python extensions are available only through explicit local manifests and are not a remote plugin system.
