# Pi/T3 Architecture Debt Cleanup Design

Date: 2026-06-29

## Purpose

This design defines the next cleanup slice after the recent Agent Core and GUI architecture refactors.
The goal is to remove remaining patch-style divergence while preserving the current product constraints:
Windows 7 compatibility, offline operation, Python 3.8, and the default C/C++ workflow.

The slice intentionally does not preserve compatibility with obsolete internal log or GUI shapes. The
project is pre-release, so old compatibility scaffolding should be deleted rather than carried forward.

## Reference Baseline

Agent behavior should continue moving toward Pi's architecture:

- ordinary tool failures are returned to the model as tool results;
- loop termination is reserved for explicit completion, cancellation, provider failure, tool-requested
  termination, or no-progress guard conditions;
- context usage prefers real model usage data and uses estimates only as a fallback;
- compaction state is durable, explicit, and not a second execution policy.

GUI behavior should continue moving toward T3 Code's architecture:

- the composer is a presentation and interaction layer;
- slash command suggestions are derived from backend/provider capability state plus a small local UI
  command set;
- frontend modules consume focused read models instead of maintaining parallel product truth.

## Findings

### Search and Guard Hard Stop

In the RODOS session `4b71823348414d96be4681260e59b276`, the last assistant step issued two
`grep_text` calls against `rodos-core/api/hal/hal_uart.h`. Both failed with `路径不是目录` because
`grep_text` resolves its `path` as a directory before searching. `ToolRuntime` then converted both
failures to generic `tool_error` observations with `retryable=True`, so `LoopGuard` counted them as
ordinary consecutive failures and stopped the loop after two failures.

This is a contract mismatch, not a reason to weaken the guard threshold. `grep_text` should support
file roots, search misses and path-shape mistakes should be diagnostic tool results, and the guard
should continue to protect only genuine runaway behavior.

### Workspace Search Pollution

Workspace-wide search currently traverses `.embedagent/memory`, including session transcripts and
tool-result artifacts. That caused the agent to search its own session history, inflate context, and
increase compaction pressure. Agent-owned memory is not project source and should be skipped by default.

### Static GUI Slash Menu

The GUI composer uses static command hints and workbench commands. The backend already has a command
capability read model, including dynamic resource commands from local skills and prompts. The frontend
is therefore maintaining a parallel command truth and misses commands such as `/resources`,
`/skill:<name>`, and `/prompt:<name-or-path>`.

### Mechanical Token Accounting

`ContextManager` estimates context usage from JSON character counts divided by a fixed ratio. Pi uses
valid assistant response usage when available, then estimates only trailing messages. It also refuses to
trust usage from before the latest compaction boundary. The current approach can trigger or avoid
compaction at the wrong time and gives poor diagnostics after compaction.

### Legacy Compaction Strategy Residue

`ContextCompactionEngine` and wrapper-level compaction in `LLMClientRetryWrapper` remain exported and
tested even though the active architecture moved compaction into `ContextManager`, `AgentLoop`, and
durable compaction journal/reducer state. Keeping the old strategy available makes it easier to
accidentally reintroduce a second compaction policy.

## Design

### 1. Search Tool and Guard Classification

Introduce structured tool-failure metadata instead of relying on free-form `ToolError` strings.
`ToolError` should be extended in a Python 3.8-compatible way with optional fields:

- `error_kind`
- `retryable`
- `outcome_class`
- `suggested_next_step`

`ToolRuntime.execute_with_interrupt()` will convert these fields into observation data for all
`ToolError` failures, then apply the same catalog metadata enrichment used for successful observations.
Generic unexpected tool exceptions remain `tool_error` and retryable by default.

`grep_text` will resolve its search root with `resolve_path()` rather than `resolve_directory()`.
If the root is a file, it searches only that file. If the root is a directory, it searches the directory.
If the root is missing, outside the workspace, binary-only, or otherwise invalid for search, the result
is a diagnostic failure observation rather than a hard loop failure.

The first implementation should keep the public tool name `grep_text`, but align semantics closer to
Pi's grep:

- accept file and directory roots;
- support regex patterns by default;
- add an optional `literal` boolean for fixed-string search;
- keep pagination through `limit` and `offset`;
- cap line previews as today;
- report invalid regex as a diagnostic failure with a clear next step;
- prefer bundled ripgrep when the managed runtime exposes it, with a Python fallback only for local
  development or tests where ripgrep is unavailable.

Agent-owned memory paths are skipped by default during project search. The skip rule should be shared
with other workspace traversal services by adding `.embedagent/memory` to the internal traversal filter
without hiding `.embedagent/skills`, `.embedagent/prompts`, or `.embedagent/recipes`.

`LoopGuard` keeps its existing diagnostic-failure exemption. The change is to classify search/path
diagnostics correctly so ordinary model recovery can happen on the next turn.

### 2. Backend-Owned Slash Command Capability

Add a safe command capability projection to session bootstrap. The source of truth is still
`RuntimeCapabilityService.snapshot()`, which already includes `command_capability_descriptors()` and
`resource_command_specs(local_resources)`.

`SessionBootstrapService` should accept a capability loader and return:

```json
{
  "capabilities": {
    "commands": [
      {
        "name": "resources",
        "usage": "/resources reload",
        "summary": "Reload workspace skills, prompts, and recipes.",
        "source_type": "builtin",
        "source_id": "slash_commands",
        "active": true
      }
    ]
  }
}
```

The GUI route serializer should pass this through with secret-safe filtering. The frontend should
normalize the command descriptors into composer command items. Workbench commands remain a UI command
palette concept and should not be used as slash command truth.

The composer menu will mirror T3's split responsibility:

- backend/session capability descriptors provide product slash commands;
- frontend composer handles trigger detection, search, grouping, and insertion;
- app/workbench commands without backend slash support stay in the command palette only.

This removes the static `SLASH_COMMAND_HINTS` list from the composer path. A tiny empty-state fallback is
acceptable for first-load UI, but it must not masquerade as the source of product commands.

### 3. Usage-Aware Token and Compaction Accounting

Introduce a focused context-usage service that can inspect session messages and compaction boundaries.
It should expose a safe read model:

- `tokens`: integer when known, otherwise `None`;
- `source`: `provider_usage`, `provider_usage_plus_estimate`, `estimate`, or `unknown_after_compaction`;
- `usage_tokens`;
- `trailing_estimate_tokens`;
- `last_usage_message_id`;
- `context_window`;
- `threshold_tokens`;
- `percent`, when both token count and context window are known.

Assistant responses with valid provider usage are the preferred source. Usage is invalid when the
assistant response was aborted, errored, all-zero, or older than the latest compaction boundary. When
there are messages after the latest valid usage, estimate only those trailing messages. If the latest
compaction boundary has no later valid assistant usage, report context usage as unknown rather than
using stale pre-compaction usage.

`ContextManager` should keep deterministic fallback estimates for offline operation and tests. The
change is not to add an online tokenizer dependency; it is to trust observed provider usage when the
provider supplies it and keep fallback estimates explicit in diagnostics.

Auto-compaction should use this usage-aware state when available. If usage is unknown immediately after
compaction, do not trigger a second threshold compaction from stale pre-compaction data. Reactive
compaction on provider context-length errors remains owned by `AgentLoop` and the compaction journal.

### 4. Legacy Strategy Deletion

Audit `ContextCompactionEngine` and `LLMClientRetryWrapper` usage. If wrapper-level compaction is not in
the active product path, delete `ContextCompactionEngine` and the compaction-engine branch from
`LLMClientRetryWrapper`. Keep retry and circuit-breaker behavior only where it is still active and
aligned with `AgentLoop`.

Update architecture guard tests so they prevent reintroducing a second compaction policy. Existing tests
that only preserve the old strategy shape should be replaced with tests for the active compaction
boundary, usage accounting, and loop retry behavior.

## Data Flow

Search flow:

1. Model calls `grep_text`.
2. `ToolRuntime` dispatches to the search tool.
3. The search tool resolves a workspace-bound file or directory root.
4. Search results or diagnostic failures are returned as `Observation`.
5. `LoopGuard` ignores diagnostic failures for consecutive-failure hard-stop accounting.
6. The next model turn receives the diagnostic result and can adjust the search.

Command menu flow:

1. Hosted adapter builds runtime capability snapshot.
2. Session bootstrap includes safe command capability descriptors.
3. GUI normalizes command descriptors into composer items.
4. Composer search ranks and groups items locally.
5. Selecting a command inserts the backend-provided usage string.

Context usage flow:

1. Provider response usage is recorded on assistant replies where available.
2. Context usage service finds the latest valid post-compaction usage.
3. It estimates only messages after that usage.
4. `ContextManager` and diagnostics consume the same usage read model.
5. Compaction decisions never use stale pre-compaction usage.

## Error Handling

Search and path-shape failures should be visible, actionable diagnostics:

- missing path: `error_kind=path_not_found`, `outcome_class=diagnostic_failure`;
- file passed to a directory-only tool: keep current failure, but classify it as diagnostic when it is a
  user/model-correctable path issue;
- invalid grep regex: `error_kind=invalid_pattern`, `outcome_class=diagnostic_failure`;
- ripgrep missing from a bundled runtime: `error_kind=runtime_missing`, not retryable, and included in
  offline-runtime validation.

Unexpected Python exceptions, broken tool handlers, catalog metadata failures, and permission-policy
violations remain non-diagnostic unless the owning component explicitly classifies them.

## Testing

Add or update tests before implementation:

- `grep_text` accepts a single file path and returns matches.
- `grep_text` supports regex alternation and a fixed-string `literal` option.
- workspace-wide `grep_text` does not traverse `.embedagent/memory`.
- structured `ToolError` metadata appears in failed observations and still receives catalog metadata.
- two diagnostic `grep_text` failures do not produce a guard-stop transition.
- session bootstrap includes static and dynamic resource command descriptors.
- GUI composer command normalization builds slash items from backend command capabilities.
- command palette UI commands are not treated as backend slash command truth.
- usage-aware context accounting prefers valid provider usage and estimates only trailing messages.
- usage from before the latest compaction boundary is ignored.
- no second threshold compaction is triggered immediately after compaction when usage is unknown.
- architecture guards reject legacy wrapper-level compaction policy reintroduction.

Run gates after implementation:

```bash
uv run pytest tests/test_tools_package.py tests/test_harness_guard_safety.py tests/test_context_config.py tests/test_capability_registry.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

If webapp source changes, also run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test
npm run build
```

## Implementation Slices

1. Tool error taxonomy and grep behavior.
2. Search traversal filtering for agent-owned memory.
3. Session bootstrap command capability projection.
4. GUI composer command source migration.
5. Usage-aware context accounting and compact threshold policy.
6. Legacy compaction strategy deletion and architecture guard updates.

Each slice should land with tests and no compatibility shim for obsolete internal state.

## Non-Goals

- No remote registry, online extension install, or runtime dependency installation.
- No new tokenizer dependency unless it is already bundled and compatible with Python 3.8 and Windows 7.
- No durable history migration for old session logs.
- No frontend-owned command registry for product slash commands.
- No replacement of the current default C/C++ workflow package boundary.

## Acceptance Criteria

- The RODOS-style repeated `grep_text` file-path failure no longer hard-stops the loop after two
  diagnostic failures.
- `grep_text` works on both files and directories and no longer searches `.embedagent/memory` by default.
- GUI slash menu reflects backend command capabilities, including resource commands.
- Context usage diagnostics identify whether counts are provider-derived, estimated, or unknown after
  compaction.
- Auto-compaction does not use stale pre-compaction usage.
- Legacy wrapper-level compaction cannot be reached or reintroduced without failing architecture tests.
