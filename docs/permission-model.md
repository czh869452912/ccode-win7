# Permission Model

## 1. Official Engine

The repository now has one official permission engine:

- `src/embedagent/permissions.py`

There is no parallel `permissions_v2` architecture anymore.

## 2. Decision Categories

Actions are classified into these categories:

- `read`
- `workspace_write`
- `shell_exec`
- `toolchain_exec`
- `git_write`
- `other`

These categories drive default allow/ask behavior and frontend explanation text.

Dynamic extension tools are classified through `ToolRuntime` catalog metadata. `PermissionPolicy` may receive a category lookup bound to the active runtime; if a registered extension tool declares `workspace_write`, `shell_exec`, `toolchain_exec`, or `git_write`, the same approval and rule paths apply as for built-in tools. Unknown tools without valid metadata remain `other` and should not be used as a shortcut for privileged behavior.

Local resource reload is a read/discovery operation and does not grant execution rights. Recipes discovered from `.embedagent/recipes/*.json` still execute through `run_recipe` and the same recipe/toolchain permission rules as bundled workspace recipes.

Reducer-backed runtime configuration is diagnostic/replay state and does not grant execution rights. `runtime_config.active_tool_names` records what was model-visible after backend activation, but permission checks for future actions still flow through `PermissionPolicy` with the current runtime category lookup.

Workflow package manifests are diagnostic/control-plane state and do not grant execution rights. A manifest can declare package tools and packs for inspection, but permission checks still flow through `PermissionPolicy` after a tool has been activated by the current mode and extension policy.

Reducer-backed compaction state is diagnostic/replay state and does not grant execution rights. `compaction_state` records compact boundary metadata for restore/debug visibility, but permission checks for future actions still flow through `PermissionPolicy` with the current runtime category lookup.

Reducer-backed recovery state is diagnostic/replay state and does not grant execution rights. `recovery_state` records hosted resume metadata for restore/debug visibility, but permission checks for future actions still flow through `PermissionPolicy` with the current runtime category lookup.

`author_local_capability` is a `workspace_write` action. It can create local skills, prompts, recipes, and disabled-by-default project extension skeletons under `.embedagent`, but it does not grant execution rights, reload resources, enable manifests, or load Python extension code.

Project-local Python extension manifests declare requested permissions, but those declarations do not bypass the runtime permission engine. Any dynamic tool registered by a project extension still needs explicit catalog metadata, active-tool visibility through `ExtensionManager.allowed_tool_names(...)`, and a normal `PermissionPolicy` decision for its permission category.

Project-local extension loading does not grant dependency installation rights. The loader must not invoke installers or package managers while importing enabled manifests; any command execution still has to enter through an official tool/recipe path, use bundled runtime commands, and pass the normal permission policy.

## 3. Rule Shape

Rules are structured objects loaded from the configured rules file.

Supported fields include:

- `decision`
  - `allow`
  - `ask`
  - `deny`
- `category`
- `tool_names` or `tool`
- `path_globs` or `path`
- `cwd_globs`
- `command_patterns` or `command_prefix`
- `recipes` or `recipe`
- `reason`

Rules are matched with last-match-wins semantics.

## 4. Explanation Format

Permission decisions expose stable explanation text for the frontend and the model.

The explanation contains:

- request
- risk
- reason
- rule source
- scope
- memory scope

This format is intentionally predictable so the UI and the model can reason about denied/ask states consistently.

## 5. Default Policy

Without a matching rule:

- `read` and interaction tools are allowed
- `workspace_write` asks unless auto-approve-writes is enabled
- `shell_exec` and `toolchain_exec` ask unless auto-approve-commands is enabled
- `git_write` asks unless auto-approve-writes is enabled

## 6. Session Memory

Frontends may remember permission categories for the current session.
That remembered state is part of the permission context view, not an implicit mode side effect.

Approving a pending permission does not create a second execution path.
The resumed action must re-enter the same validation/execution pipeline as the initial action, including mode/path policy checks.

## 7. Frontend Context View

The frontend-visible permission context includes:

- `rules_path`
- active categories
- normalized rules
- remembered categories
- auto-approve flags

This lets the frontend explain why an operation is blocked without reverse-engineering runtime behavior.

## 8. Design Rule

Do not push permission semantics back into prompt-only mode rules.

Modes may constrain intent and writable scope, but explicit permission decisions still belong to the permission engine.
