# Technology Stack

**Analysis Date:** 2026-05-02

## Languages

**Primary:**
- Python 3.8.x — strict compatibility, no 3.9+ syntax (walrus `:=`, `match`, `dict | dict` forbidden)
  - Backend, agent core, harness, tooling, CLI, TUI, and GUI backend logic
- JavaScript (JSX/ES modules) — React frontend webapp
  - GUI client-side code only

**Secondary:**
- HTML/CSS — GUI shell and static assets
- Shell/Makefile — build automation

## Runtime

**Environment:**
- CPython >=3.8,<3.9 (strictly enforced)
- Node.js (build-time only, for frontend bundling)

**Package Manager:**
- `uv` (Python) — lockfile: `uv.lock`
- `npm` (frontend) — lockfiles: `package-lock.json` (webapp + `.opencode/`)

## Frameworks

**Core:**
- `fastapi` >=0.100 — GUI backend REST API
- `uvicorn[standard]` >=0.23 — ASGI server for FastAPI
- `websockets` >=11.0 — WebSocket support (GUI real-time events)
- `pywebview` >=4.0 — Desktop GUI shell (Windows 7, Chromium via WebView2)
- `prompt-toolkit` ==3.0.52 — TUI input and layout
- `rich` ==14.3.3 — TUI rendering, colors, tables, progress

**Frontend:**
- `react` ^18.3.1 / `react-dom` ^18.3.1 — GUI webapp UI framework
- `react-markdown` ^9.0.1 — Markdown rendering in chat
- `react-arborist` ^3.4.3 — File tree component
- `diff2html` ^3.4.52 — Diff visualization
- `highlight.js` ^11.10.0 — Syntax highlighting
- `remark-gfm` / `remark-math` / `rehype-katex` — Markdown plugins

**Build/Dev:**
- `vite` ^5.4.10 — Frontend dev server (config: `vite.config.js`)
- `esbuild` ^0.21.5 — Production frontend bundler (`build.mjs`)
- `@vitejs/plugin-react` ^4.3.4 — Vite React plugin
- `setuptools` >=65 — Python package build backend

**Testing:**
- `pytest` — Test runner (config in `pyproject.toml`)
- `coverage.py` — Code coverage (config in `pyproject.toml`)
- Custom Node.js test runner for webapp (`test/run-tests.mjs`)

**Linting/Formatting:**
- `ruff` >=0.15.12 — Python linter (target py38, line-length 100)
- `black` — Python formatter (target py38, line-length 100)

## Key Dependencies

**Critical:**
- `fastapi` + `uvicorn` — GUI backend server and API layer (`src/embedagent/frontend/gui/backend/server.py`)
- `pywebview` — Desktop window shell requiring WebView2 runtime on Windows (`src/embedagent/frontend/gui/launcher.py`)
- `prompt-toolkit` + `rich` — Terminal UI framework (`src/embedagent/frontend/tui/`)
- Standard library `urllib.request` — LLM API client (no external HTTP library; `src/embedagent/llm.py`)
- Standard library `sqlite3` — Local projection database (`src/embedagent/projection_db.py`)

**Infrastructure:**
- `websockets` — WebSocket endpoint for real-time frontend updates
- `react` + `react-dom` — GUI webapp component model
- `esbuild` — Production build tool for offline-static GUI bundle

## Configuration

**Environment:**
- Two-level JSON config: `~/.embedagent/config.json` (user) and `<workspace>/.embedagent/config.json` (project)
- Config loader: `src/embedagent/config.py`
- Key settings: `base_url`, `api_key`, `model`, `timeout`, `max_context_tokens`, `reserve_output_tokens`, `chars_per_token`, `max_turns`, `default_mode`, `mode_writable_globs`

**Environment Variables:**
- `EMBEDAGENT_BASE_URL` — LLM API endpoint
- `EMBEDAGENT_API_KEY` — LLM API key
- `EMBEDAGENT_MODEL` — Model name
- `EMBEDAGENT_TIMEOUT` — Request timeout
- `EMBEDAGENT_BUNDLE_ROOT` — Offline bundle root path
- `EMBEDAGENT_LLVM_ROOT` — Clang/LLVM toolchain root
- `EMBEDAGENT_WEBVIEW2_RUNTIME` — WebView2 fixed runtime path
- `EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK` — Allow system PATH fallback for tools
- `EMBEDAGENT_TUI_HEADLESS` — TUI headless mode flag

**Build:**
- `pyproject.toml` — Python project metadata, dependencies, tool configs (ruff, black, pytest, coverage)
- `vite.config.js` — Vite dev/build config (target: chrome109)
- `build.mjs` — Custom esbuild production pipeline
- `Makefile` — Convenience targets: `install`, `test`, `harness`, `lint`, `lint-fix`, `smoke`, `ci`

**Entry Points:**
- `embedagent` console script → `embedagent.cli:main`
- `embedagent-gui` console script → `embedagent.frontend.gui.launcher:main`

## Platform Requirements

**Development:**
- Python 3.8.x
- `uv` (Python package manager)
- Node.js + npm (for frontend build only)
- Windows 7 compatible (mandatory)

**Production/Offline Bundle:**
- Windows 7 target
- Must include bundled runtime assets:
  - Python 3.8 embeddable distribution
  - Vendored Python third-party packages
  - MinGit portable
  - ripgrep
  - Universal Ctags
  - Clang toolchain binaries
  - WebView2 fixed runtime (for GUI)
- No runtime dependency on Docker, WSL, VS Code, or online services
- Clean Windows 7 machine must run the bundle without preinstalled tools

---

*Stack analysis: 2026-05-02*
