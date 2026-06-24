# Pi-Aligned Tool Architecture Redesign

> Archive status: Completed and archived on 2026-06-25. Durable conclusions were synchronized into active source-of-truth docs before this design was moved to archive.

## Purpose

Redesign the Agent Core tool architecture around Pi's minimal, composable
agent design rather than incrementally patching the current C/C++-heavy tool
surface.

This project has not shipped, so this redesign intentionally does not preserve
legacy tool compatibility. Stale compatibility paths, confusing aliases, and
tools that encourage poor model behavior should be removed instead of wrapped.

## Product Direction

Agent Core should expose a small set of first-class primitive tools. Workflow
packages should provide domain-specific capabilities without thickening Core or
turning high-level workflow actions into general-purpose shell substitutes.

The target architecture keeps the existing product constraints:

- Windows 7 compatibility remains mandatory.
- Offline deployment remains mandatory.
- Runtime compatibility remains Python `>=3.8,<3.9`.
- C/C++ development remains the default first-class workflow.
- Optional extensions and workflow packages must remain outside Core.

The design follows Pi's core principle: keep the model-facing default tool set
small, reliable, and easy to choose from. Higher-level capabilities should be
discoverable and explicit, not always-on substitutes for primitives.

## Current Problems

The current tool surface mixes three different abstraction levels:

1. Primitive file/search/shell operations.
2. C/C++ workflow helpers such as recipe execution and quality reporting.
3. Build-like wrappers that are actually generic shell execution.

This creates poor tool-selection incentives. In projects without configured
recipes, the agent can see workflow tools such as `run_recipe` or `run_build`
before it has a reliable project workflow. Because `run_build` accepts arbitrary
commands, it becomes a pseudo shell tool while still presenting itself as a
build tool. The agent then retries `run_build` or `run_recipe` as if they were
general command execution primitives.

Recipe auto-detection also overstates readiness. A detected CMake or Make
command is not the same as a configured, runnable project workflow. If a build
directory, generator, target, or prerequisite is missing, `run_recipe` must be
able to refuse execution with a precise non-retryable result.

Command output handling is also too text-first. Subprocess output is decoded
with fixed UTF-8 replacement behavior, which is not reliable on Windows 7,
Chinese Windows systems, legacy tools, `cmd.exe`, or tools that emit OEM/ANSI
encoded output.

## Target Tool Layers

### Core Primitive Tools

Agent Core should expose only small, stable, model-obvious primitives:

- `read_file`
- `write_file`
- `edit_file`
- `bash`
- `grep_text`
- `glob_files`
- `list_dir`
- `ask_user`

`bash` is a first-class primitive, not a workflow helper. It is the only general
command execution tool visible to the model by default.

### Workflow Package Tools

The default C/C++ workflow package may expose domain-specific tools, but these
tools are not Core primitives:

- `list_recipes`
- `run_recipe`
- `task_status`
- `report_quality_v2`
- `record_failing_evidence`

These tools must be activated by the workflow package through the extension
boundary. They must not be used as shortcuts for Core tool policy.

### Removed Public Tools

The following tool shape should be removed from the public model-visible
contract:

- `run_build`

`run_build` currently behaves like generic shell execution with extra build
diagnostics. That makes it an attractive but misleading substitute for a real
shell tool. Build commands should run through `bash`; C/C++ diagnostic parsing
should be attached to command results or workflow-specific post-processing.

No public compatibility alias should be retained for `run_build`.

### Reframed Tools

`configure_build_env` should not remain a frequent model-selected action tool.
Toolchain and environment discovery should be exposed as context, diagnostics,
or a narrowly scoped workflow capability only when it clearly helps the current
workflow state.

## Bash Tool Contract

The new `bash` tool is the model-facing general command primitive.

Required behavior:

- Execute a shell command in the workspace or a workspace-bound subdirectory.
- Prefer bundled Git Bash or MinGit-provided Bash for offline Windows runtime.
- Never require Docker, WSL, VS Code, runtime Node, or online services.
- Enforce the existing permission and command-sanitization policy.
- Return exit code, duration, timeout state, stdout tail, stderr tail, and
  truncation metadata.
- Save complete output when stdout or stderr is truncated.
- Include structured failure fields:
  - `error_kind`
  - `retryable`
  - `suggested_next_step`
- Avoid encouraging unchanged retries after command failure.

The offline runtime contract must include any Bash executable or support binary
that the product invokes at runtime.

## Recipe Tool Contract

Recipes are explicit workflow entries, not guessed commands with a friendly
name.

`list_recipes` must return readiness metadata for every recipe:

- `id`
- `label`
- `source`
- `command`
- `cwd`
- `ready`
- `confidence`
- `requires`
- `reason`
- `last_success`
- `failure_count`
- `last_failure_summary`
- `suggested_next_step`

Recipe sources must be distinguished:

- `project`
- `resource`
- `history`
- `detected`

Detected recipes are lower trust than project-declared recipes. They may be
listed, but they must not pretend to be configured project truth.

`run_recipe` must refuse execution before spawning a command when prerequisites
are obviously missing. Examples:

- CMake build recipe requires a configured build directory.
- CMake test recipe requires a configured build directory.
- Make test recipe should not claim high confidence when the target is unknown.
- Unknown recipe IDs must return available alternatives.

Failure results must be structured and specific. Missing recipe or missing
prerequisite failures are non-retryable until the workspace changes.

## Command Output And Encoding

Command output handling must become bytes-first.

Subprocess stdout and stderr should be captured as bytes and decoded by a
shared command-output decoder. The decoder should:

- Prefer UTF-8 and UTF-8 with BOM.
- Fall back to the Windows OEM code page.
- Fall back to the Windows ANSI code page or `cp936` where appropriate.
- Use replacement only as the final fallback.
- Track which encoding was used.
- Track decode replacement counts or undecodable byte evidence.
- Normalize line endings.
- Strip unsafe control characters while preserving tabs and newlines.
- Preserve ANSI color/control handling consistently for tool results and GUI
  terminal display.

Streaming output must use incremental decoders so multibyte characters split
across chunks are not corrupted.

The command result envelope should expose:

- `encoding`
- `decode_errors_count`
- `output_maybe_mojibake`
- `stdout_tail`
- `stderr_tail`
- `stdout_truncated`
- `stderr_truncated`
- `full_output_ref`

## Prompt And Tool Selection Policy

Tool descriptions and workflow prompt units should teach a simple order:

1. Inspect files and project structure.
2. Use `list_recipes` only to discover declared or detected workflows.
3. Use `run_recipe` only for ready recipes.
4. Use `bash` for general command exploration and build commands.
5. Do not repeat the same failing command or recipe unchanged.
6. After failure, inspect diagnostics, change the hypothesis, or ask the user.

The prompt should not describe workflow tools as general-purpose command
execution mechanisms.

## Documentation Updates

The implementation must update durable source-of-truth docs, not only slice-local
notes:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`

Completed slice-local docs should eventually move to `docs/archive/` after their
durable conclusions are synchronized.

## Testing Strategy

The implementation must be test-driven.

Required coverage:

- Core schema projection exposes `bash` and no longer exposes `run_build`.
- C/C++ workflow packs no longer include `run_build`.
- `bash` executes workspace-bound commands and returns structured success and
  failure observations.
- `bash` rejects commands blocked by the sanitizer.
- Long command output is tail-truncated and full output is retained.
- Non-UTF-8 command output decodes without mojibake when the active code page is
  known.
- `list_recipes` reports no configured recipes with an explicit suggested next
  step.
- Detected CMake build recipes are not ready when the build directory is absent.
- `run_recipe` returns non-retryable prerequisite failures before spawning.
- Unknown recipe IDs return available alternatives.
- Permission and path guards still apply to shell execution.

## Acceptance Criteria

The redesign is complete when:

- The model-visible default command primitive is `bash`.
- `run_build` is gone from public tool schemas, workflow packs, docs, and tests.
- Recipe tools expose readiness and reject invalid execution attempts with
  specific non-retryable observations.
- Command output decoding no longer relies on fixed UTF-8 text mode.
- Documentation consistently describes a small Agent Core and workflow-package
  owned C/C++ capabilities.
- Fast tests pass with:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```
