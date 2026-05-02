# External Integrations

**Analysis Date:** 2026-05-02

## APIs & External Services

**LLM Inference API:**
- Purpose: Core agent reasoning and code generation
- Protocol: OpenAI-compatible chat completions API
- Client: Custom `OpenAICompatibleClient` in `src/embedagent/llm.py`
- Transport: Python standard library `urllib.request` (no external HTTP SDK)
- Streaming: Server-Sent Events (SSE) over HTTP POST
- Default endpoint: `http://127.0.0.1:8000/v1/chat/completions`
- Auth: Bearer token via `Authorization` header
- Config sources (priority order):
  1. CLI args (`--base-url`, `--api-key`, `--model`)
  2. Environment vars (`EMBEDAGENT_BASE_URL`, `EMBEDAGENT_API_KEY`, `EMBEDAGENT_MODEL`)
  3. Project config: `<workspace>/.embedagent/config.json`
  4. User config: `~/.embedagent/config.json`
- Response formats supported: standard OpenAI chat completions + OpenAI Responses API (`output` field)
- Tool calling: function/tool_calls schema with streaming accumulation

**No other external HTTP APIs detected.**

## Data Storage

**Databases:**
- SQLite (`sqlite3` standard library)
  - File: `<workspace>/.embedagent/memory/projections.sqlite3`
  - Purpose: Session projection index and tool result projection cache
  - Schema managed in: `src/embedagent/projection_db.py`
  - Tables: `schema_meta`, `session_projection`, `tool_result_projection`
  - No ORM; raw SQL with `sqlite3.Row` factory

**File Storage:**
- Local filesystem only
- Session data: JSON files in `<workspace>/.embedagent/memory/sessions/{session_id}/`
  - `summary.json` — session summary snapshot
  - `transcript.jsonl` — durable session transcript ledger
- Tool results: stored in `<workspace>/.embedagent/memory/tool_results/`
  - Content-addressed via SHA-256 hashes (`src/embedagent/tool_result_store.py`)
- Project memory: JSON files in `<workspace>/.embedagent/memory/project/`
- Static GUI assets: `src/embedagent/frontend/gui/static/` (built from webapp)

**Caching:**
- No dedicated caching service
- In-memory caches in runtime (tool result store, projection DB rows)
- File-based content-addressable storage for tool outputs

## Authentication & Identity

**Auth Provider:**
- None — no user identity system
- LLM API authentication only via configurable API key (local config/env)
- No OAuth, SSO, or session cookies for users

**Permission Engine:**
- Local permission system: `src/embedagent/permissions.py`
- Rule-based approval for risky tool operations (file writes, shell commands)
- Configurable auto-approve categories via CLI flags or rules JSON file

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Rollbar, or similar service
- Errors logged to Python `logging` and surfaced in UI/CLI

**Logs:**
- Python standard `logging` module
- GUI backend logs via `logging.getLogger(__name__)`
- CLI/TUI output to stderr/stdout
- No structured log aggregation or external log shipping

## CI/CD & Deployment

**Hosting:**
- Not applicable — this is a desktop/offline application, not a hosted service
- Distribution via offline bundle containing all runtime dependencies

**CI Pipeline:**
- GitHub Actions: `.github/workflows/ci.yml`
- Jobs:
  - `lint` — ruff + black checks on Python 3.8
  - `test` — pytest with coverage (excludes slow/gui tests), uploads coverage artifact
  - `smoke` — pip install CLI extras, import check, entry point verification
- Triggers: all branches on push and pull_request

## Environment Configuration

**Required env vars:**
- `EMBEDAGENT_BASE_URL` — LLM service URL (or use config file)
- `EMBEDAGENT_API_KEY` — LLM service API key (or use config file)
- `EMBEDAGENT_MODEL` — Model name (or use config file)

**Optional env vars:**
- `EMBEDAGENT_TIMEOUT` — LLM request timeout in seconds
- `EMBEDAGENT_BUNDLE_ROOT` — Override offline bundle discovery path
- `EMBEDAGENT_LLVM_ROOT` — Override Clang/LLVM toolchain path
- `EMBEDAGENT_WEBVIEW2_RUNTIME` — Override WebView2 fixed runtime path
- `EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK` — Enable/disable system PATH fallback (`1`/`0`/`true`/`false`)
- `EMBEDAGENT_TUI_HEADLESS` — Run TUI in headless mode

**Secrets location:**
- API keys stored in local JSON config files (`config.json`) or environment variables
- `.env` files not used by the application
- `config/config.json` is gitignored (contains `api_key`)

## Webhooks & Callbacks

**Incoming:**
- None — no external webhooks received

**Outgoing:**
- None — no outgoing webhooks to external systems
- Internal callbacks only: `FrontendCallbacks` interface for UI updates (`src/embedagent/protocol/__init__.py`)

## Bundled External Binaries

The application discovers and optionally bundles these external tools for offline use:

**Managed Runtime Tools (`src/embedagent/tools/_base.py`):**
- `git` / `git.exe` — MinGit portable
- `rg` / `rg.exe` — ripgrep
- `ctags` / `ctags.exe` — Universal Ctags
- `python` / `python.exe` — Python 3.8 embeddable
- LLVM/Clang toolchain (`clang`, `clang++`, `clang-tidy`, `llvm-cov`, `llvm-profdata`, etc.)

**Discovery order:**
1. `EMBEDAGENT_BUNDLE_ROOT` environment override
2. Auto-discovered bundle root (via marker paths: `app/embedagent`, `runtime/python`, `bin`)
3. Workspace-local paths (`toolchains/llvm/current`, `bin/git`, etc.)
4. System PATH (only if `EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK` is enabled)

**GUI Runtime:**
- WebView2 fixed runtime (Chrome 109 compatible) for Windows 7 GUI mode
- Configured in `src/embedagent/frontend/gui/launcher.py`
- Required when running from bundle; no IE11 fallback

## Network Architecture

**GUI Mode:**
- FastAPI server binds to `127.0.0.1` on auto-selected port
- PyWebView loads `http://127.0.0.1:{port}` in local desktop window
- WebSocket at `/ws` for real-time bidirectional events
- REST API at `/api/*` for session management, file operations, tool catalog
- Static files served from built webapp at `/static/`
- No external network exposure; strictly localhost

**CLI/TUI Mode:**
- No local server; direct in-process execution
- Only outbound network: HTTP POST to configured LLM `base_url`

---

*Integration audit: 2026-05-02*
