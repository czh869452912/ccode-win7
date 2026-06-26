# EmbedAgent Configuration Guide

EmbedAgent uses layered configuration for model connection settings, context budgets,
loop limits, and mode write policies.

This guide follows the current product baseline:

- official modes are `explore`, `spec`, `build`, `debug`, and `verify`
- `build` is the implementation mode
- task state is projected from the default C/C++ harness through `task_status`
- `code` and `manage_todos` are historical terms, not current configuration targets

## Configuration Precedence

Configuration is resolved from low to high priority:

```text
built-in defaults
  ^
user config      (~/.embedagent/config.json)
  ^
project config   (<workspace>/.embedagent/config.json)
  ^
environment      (EMBEDAGENT_*)
  ^
CLI arguments    (--max-context-tokens, --mode, ...)
```

Later layers override earlier layers. CLI arguments always have the highest priority.

## Configuration Files

| Level | Path | Scope |
|------|------|-------|
| User | `~/.embedagent/config.json` | All workspaces for one user |
| Project | `<workspace>/.embedagent/config.json` | Current workspace only |

The runtime reloads these files when it starts a session or command. Editing a config
file does not require changing source code.

## JSON Shape

```json
{
  "base_url": "string",
  "api_key": "string",
  "model": "string",
  "timeout": 120,
  "max_context_tokens": 18000,
  "reserve_output_tokens": 2000,
  "chars_per_token": 3.0,
  "max_recent_turns": 4,
  "max_turns": null,
  "default_mode": "explore",
  "mode_writable_globs": {
    "<mode_name>": ["glob_pattern", "..."]
  },
  "mode_extra_writable_globs": {
    "<mode_name>": ["glob_pattern", "..."]
  }
}
```

All fields are optional. Missing values use built-in defaults.

## LLM Connection

| Field | Type | Default | Meaning |
|------|------|---------|---------|
| `base_url` | string | `http://127.0.0.1:8000/v1` | OpenAI-compatible API base URL |
| `api_key` | string | `""` | API key |
| `model` | string | `""` | Model name |
| `timeout` | number | `120` | Request timeout in seconds |

Equivalent environment variables:

- `EMBEDAGENT_BASE_URL`
- `EMBEDAGENT_API_KEY`
- `EMBEDAGENT_MODEL`
- `EMBEDAGENT_TIMEOUT`

Do not commit `config/config.json` when it contains a real API key.

## Context Budget

| Field | Type | Default | Meaning |
|------|------|---------|---------|
| `max_context_tokens` | integer | `18000` | Total input context budget |
| `reserve_output_tokens` | integer | `2000` | Reserved output budget |
| `chars_per_token` | number | `3.0` | Approximate character-to-token ratio |
| `max_recent_turns` | integer | `4` | Recent turns kept in full before summarization |

For larger local models, increasing `max_context_tokens` can reduce compaction
frequency. Keep `reserve_output_tokens` large enough for tool plans and final answers.

## Loop And Mode Defaults

| Field | Type | Default | Meaning |
|------|------|---------|---------|
| `max_turns` | integer or null | `null` | Optional model/tool loop safety limit; omit or set null for Pi-style open continuation |
| `default_mode` | string | `explore` | Initial mode for new sessions |

Valid `default_mode` values are:

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

Unknown mode names fail fast. `code` is not a valid first-class mode.

## Writable Globs

`mode_writable_globs` completely replaces the built-in write scope for a mode.

```json
{
  "mode_writable_globs": {
    "build": ["src/**/*.c", "src/**/*.h", "CMakeLists.txt"],
    "spec": ["docs/**/*.md"]
  }
}
```

Rules:

- glob matching uses Python `fnmatch` semantics
- unspecified modes keep built-in defaults
- an empty list makes the mode read-only
- `explore` and `verify` should remain read-only

`mode_extra_writable_globs` appends extra write scopes without replacing the built-in
defaults.

```json
{
  "mode_extra_writable_globs": {
    "build": ["cmake/**/*.cmake", "cmake/**/*.txt"],
    "debug": ["repro/**/*.c"]
  }
}
```

Use replacement when you want a strict project-specific write boundary. Use append when
the default implementation/debug scopes are acceptable but the project has extra build
metadata paths.

## Built-In Write Policy

| Mode | Built-in write policy |
|------|-----------------------|
| `explore` | read-only |
| `spec` | documentation and text artifacts |
| `build` | implementation files and build metadata |
| `debug` | implementation files and build metadata |
| `verify` | read-only |

Permission rules still apply after mode write filtering. A path matching the mode glob
can still require confirmation or be denied by `PermissionPolicy`.

## Examples

### Local OpenAI-Compatible Model

```json
{
  "base_url": "http://127.0.0.1:8000/v1",
  "model": "qwen-coder-local",
  "timeout": 180
}
```

### Larger Context Model

```json
{
  "max_context_tokens": 32000,
  "reserve_output_tokens": 4000,
  "max_recent_turns": 8
}
```

### Restrict Build Writes To One Module

```json
{
  "default_mode": "explore",
  "mode_writable_globs": {
    "build": ["src/mymodule/**/*.c", "src/mymodule/**/*.h"],
    "debug": ["src/mymodule/**/*.c", "src/mymodule/**/*.h", "tests/**/*.c"]
  }
}
```

### Add Project Build Metadata Paths

```json
{
  "mode_extra_writable_globs": {
    "build": ["cmake/**/*.cmake", "toolchains/**/*.cmake", "CMakePresets.json"]
  }
}
```

## CLI Overrides

These CLI arguments override matching config fields:

```text
--max-context-tokens INT
--reserve-output-tokens INT
--chars-per-token FLOAT
--max-turns INT
--mode STR
```

## Task State

Do not configure or invoke `manage_todos` for current workflows. The default C/C++
harness owns task truth through `TaskGraph`, projects it into
`Session.workflow_state["workflow"]`, and exposes it through `task_status` plus
frontend task snapshots.

Frontend payloads use:

- `task_summary`
- `task_items`
- `current_phase`
- `discipline_profile`
- `current_activity`

## Source Of Truth

Keep this guide aligned with:

- `README.md`
- `AGENTS.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `src/embedagent/modes.py`
