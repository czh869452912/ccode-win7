# EmbedAgent Configuration Guide

EmbedAgent uses layered configuration for model connection settings, context budgets,
and mode write policies.

This guide follows the current product baseline:

- official modes are `explore`, `spec`, `build`, `debug`, and `verify`
- `build` is the implementation mode
- task state is projected from the default C/C++ harness through `task_status`
- the retired implementation-mode and todo-management names are historical terms,
  not current configuration targets

## Configuration Precedence

Configuration is resolved from low to high priority:

```text
built-in defaults
< user config      (~/.embedagent/config.json)
< project config   (<workspace>/.embedagent/config.json)
< environment      (EMBEDAGENT_*)
< explicit shell arguments
```

Later layers override earlier layers. CLI, TUI, and GUI all call the same product
`resolve_launch_config(...)` entry; launchers only construct explicit overrides and never load
the JSON files themselves. An explicit boolean `false` is a value, while an omitted override
allows the lower layer to win.

## Configuration Files

| Level | Path | Scope |
|------|------|-------|
| User | `~/.embedagent/config.json` | All workspaces for one user |
| Project | `<workspace>/.embedagent/config.json` | Current workspace only |

The product loads these files before it constructs a Host runtime for a shell process. Editing
a config file takes effect for the next CLI command or TUI/GUI runtime construction.

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
  "default_mode": "explore",
  "agent_application_id": "<application-id>",
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

## Mode Defaults

| Field | Type | Default | Meaning |
|------|------|---------|---------|
| `default_mode` | string | `explore` | Initial mode for new sessions |
| `agent_application_id` | string | omitted | Hosted scenario application to load |

Valid `default_mode` values are:

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

Unknown mode names fail fast. `code` is not a valid first-class mode.

`agent_application_id` selects the hosted application package before the
session engine is built. Omit it to let the hosted application registry choose
the packaged default application. Set it explicitly to pin a base or
specialized agent with a different profile, workflow packages, and GUI
capability metadata while keeping the same Agent Core and GUI shell.
Built-in application ids are:

- `embedagent.default_c_cpp`
- `embedagent.generic`
- `embedagent.python`
- `embedagent.html`

The equivalent environment variable is `EMBEDAGENT_AGENT_APPLICATION_ID`, and
CLI/TUI/GUI launchers accept `--agent-application <id>`.

## Packaged Flavor Restrictions

开发树中的完整 registry 和离线 bundle 的可选范围不同。bundle 启动时会校验 `manifests/bundle-plan.json` 与 `bundle-manifest.json` 的 hash binding，然后只允许计划声明的 application 和 shell：

| Flavor | Allowed application IDs | Available shells |
|---|---|---|
| `minimal-cli` | `embedagent.generic` | CLI |
| `cpp-desktop` | `embedagent.default_c_cpp` | CLI, TUI, GUI |

在 bundle 中省略 `agent_application_id` 会选择计划允许的首个 application。显式配置其他 built-in ID 会 fail closed，即使包含该代码的六个 project wheel 已安装。类似地，`minimal-cli` 不能通过 launcher 参数激活 TUI/GUI。

打包选择由 packaging CLI 控制，不写入 workspace config：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Flavor minimal-cli
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Flavor cpp-desktop
```

省略 `-Flavor` 时使用 `cpp-desktop`。`-Profile` 只控制 dev/release assurance，`-Flavor` 只控制产品内容。官方模板位于 `config/bundle-flavors/`，模板不包含 `api_key`；真实 credential 只能进入未提交的用户/项目配置或环境变量。

## Writable Globs

`mode_writable_globs` completely replaces the built-in write scope for a mode.

```json
{
  "mode_writable_globs": {
    "build": ["src/**/*.py", "pyproject.toml"],
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
    "build": ["scripts/**/*.ps1", "tools/**/*.json"],
    "debug": ["repro/**/*.py"]
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
    "build": ["src/mymodule/**/*.py"],
    "debug": ["src/mymodule/**/*.py", "tests/**/*.py"]
  }
}
```

### Add Project Build Metadata Paths

```json
{
  "mode_extra_writable_globs": {
    "build": ["scripts/**/*.ps1", "tools/**/*.json", "pyproject.toml"]
  }
}
```

## CLI Commands And Overrides

The CLI requires an explicit command. A naked message is not a supported invocation:

```text
embedagent chat [OPTIONS]
embedagent run [OPTIONS] TASK
embedagent sessions list [OPTIONS]
embedagent sessions show [OPTIONS] REFERENCE
embedagent sessions rename [OPTIONS] REFERENCE TITLE
embedagent sessions archive [OPTIONS] REFERENCE
embedagent sessions fork [OPTIONS] REFERENCE [--title TITLE]
```

Use `chat` for an interactive session with descriptor commands and permission/user-input
responses. Use `run` for one turn suitable for scripts; a required interaction returns exit
code `2` and a blocked result instead of prompting. `sessions` operates on durable session
records and does not create parallel history.

These CLI arguments override matching config fields. `--max-turns` is an
explicit runtime safety fuse for diagnostics and tests; persistent JSON config
does not set the product's loop ceiling.

```text
--max-context-tokens INT
--reserve-output-tokens INT
--chars-per-token FLOAT
--max-turns INT
--mode STR
--agent-application STR
--base-url URL
--api-key KEY
--model NAME
--timeout SECONDS
--approve-all
--approve-writes
--approve-commands
--permission-rules PATH
```

`run` and session query commands also accept `--output text|json`; `run` and `chat` accept
`--resume`, while session creation accepts `--mode`. Equivalent TUI/GUI startup options feed
the same explicit-override layer and do not alter file/environment precedence.

## Task State

Do not configure or invoke the retired todo-management tool for current
workflows. The default C/C++ harness owns task truth through `TaskGraph`, projects it into
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
- `docs/platform/mode-contract.md`
- `docs/platform/tool-contracts.md`
- `docs/platform/permission-model.md`
- `src/embedagent/modes.py`
