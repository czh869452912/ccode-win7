# Codebase Structure

**Analysis Date:** 2026-05-02

## Directory Layout

```
D:\Claude-project\ccode-win7/
├── src/embedagent/              # Main Python package (Agent Core + Frontends)
│   ├── core/                    # Protocol adapter wrapping InProcessAdapter
│   ├── frontend/                # UI shells (TUI + GUI)
│   │   ├── gui/                 # PyWebView + FastAPI + React webapp
│   │   └── tui/                 # prompt_toolkit terminal UI
│   ├── harness/                 # Mode registry, phase engine, task graph
│   ├── protocol/                # Stable frontend/core dataclass contracts
│   ├── tooling/                 # Tool pack definitions and budget policies
│   ├── tools/                   # Official tool runtime and implementations
│   └── *.py                     # Core modules (cli, query_engine, session, etc.)
├── tests/                       # pytest test suite
│   ├── fixtures/                # Test fixture packages and data
│   └── manual/                  # Manual/integration test scripts
├── docs/                        # Documentation
│   ├── adrs/                    # Architecture Decision Records
│   ├── archive/                 # Completed slice artifacts
│   ├── blueprints/              # Design blueprints
│   ├── guides/                  # User/developer guides
│   ├── modules/                 # Module-level documentation
│   ├── references/              # Glossary, API references
│   ├── superpowers/             # Active design/plan materials
│   ├── templates/               # Document templates
│   └── workflows/               # Workflow documentation
├── config/                      # Runtime configuration (gitignored)
├── build/                       # Build artifacts
├── scripts/                     # Utility scripts
├── toolchains/                  # Bundled toolchain configuration
├── reference/                   # Reference materials
├── analysis/                    # Comparative analysis documents
├── .agents/                     # Agent skill definitions
├── .claude/                     # Claude-specific configuration
├── .opencode/                   # Opencode workflow definitions
├── .superpowers/                # Superpower skill manifests
├── .planning/                   # Planning artifacts (this directory)
├── .worktrees/                  # Git worktrees
├── pyproject.toml               # Project metadata and tool config
├── uv.lock                      # Dependency lockfile
├── Makefile                     # Development tasks
└── README.md                    # Project overview
```

## Directory Purposes

**`src/embedagent/`:**
- Purpose: All production Python code
- Contains: CLI, core engine, frontends, harness, tools, session management
- Key files: `cli.py`, `query_engine.py`, `inprocess_adapter.py`, `session.py`, `context.py`, `permissions.py`, `modes.py`

**`src/embedagent/core/`:**
- Purpose: Stable protocol adapter between frontend and InProcessAdapter
- Contains: `AgentCoreAdapter` implementing `CoreInterface`
- Key files: `src/embedagent/core/adapter.py`

**`src/embedagent/frontend/`:**
- Purpose: UI shells that do not own workflow semantics
- Contains: TUI and GUI implementations
- Key files: `src/embedagent/frontend/tui/controller.py`, `src/embedagent/frontend/gui/launcher.py`

**`src/embedagent/frontend/gui/`:**
- Purpose: Desktop GUI application
- Contains: PyWebView launcher, FastAPI backend, static assets, React webapp
- Key files: `backend/server.py`, `backend/bridge.py`, `launcher.py`

**`src/embedagent/frontend/gui/webapp/src/`:**
- Purpose: React-based GUI frontend
- Contains: JSX components, state store, session runtime projector
- Key files: `App.jsx`, `store.js`, `components/Timeline.jsx`, `components/Inspector.jsx`, `session-runtime/projector.js`

**`src/embedagent/frontend/tui/`:**
- Purpose: Terminal-based UI
- Contains: Controller, views, services, state reducer
- Key files: `controller.py`, `views/timeline.py`, `views/inspector.py`, `reducer.py`

**`src/embedagent/harness/`:**
- Purpose: Workflow harness — mode registry, discipline profiles, phase advancement
- Contains: Contracts, phase engine, task graph, prompt stack, registry, runner
- Key files: `contracts.py`, `phase_engine.py`, `task_graph.py`, `runner.py`, `registry.py`

**`src/embedagent/protocol/`:**
- Purpose: Stable dataclass contracts between frontend and core
- Contains: Message types, session snapshots, tool calls, permission requests
- Key files: `src/embedagent/protocol/__init__.py`

**`src/embedagent/tooling/`:**
- Purpose: Tool pack definitions and result budget policies
- Contains: Pack constants, budget policies
- Key files: `packs.py`, `result_budget.py`, `contracts.py`

**`src/embedagent/tools/`:**
- Purpose: Official tool runtime and all tool implementations
- Contains: ToolRuntime facade, base classes, file ops, git ops, shell ops, recipe ops, session ops, discovery ops, harness runtime
- Key files: `runtime.py`, `_base.py`, `file_ops.py`, `git_ops.py`, `shell_ops.py`, `recipe_ops.py`, `harness_runtime.py`

**`tests/`:**
- Purpose: pytest test suite
- Contains: Unit tests, integration tests, harness tests, GUI tests
- Key files: `conftest.py`, `test_query_engine_*.py`, `test_harness_*.py`, `test_gui_*.py`

**`docs/`:**
- Purpose: Project documentation
- Contains: Architecture docs, ADRs, guides, workflow docs
- Key files: `overall-solution-architecture.md`, `implementation-roadmap.md`, `tool-contracts.md`, `permission-model.md`, `frontend-protocol.md`

**`docs/archive/`:**
- Purpose: Completed slice artifacts and historical references
- Contains: Subdirectories per completed architecture slice

**`docs/superpowers/`:**
- Purpose: Active design and plan materials for current slice
- Contains: `plans/`, `reviews/`, `specs/`
- Note: Working materials only; durable conclusions sync back to global docs

## Key File Locations

**Entry Points:**
- `src/embedagent/__main__.py`: Module entry point (delegates to cli.py)
- `src/embedagent/cli.py`: CLI argument parsing and main loop
- `src/embedagent/frontend/gui/launcher.py`: GUI launcher (`embedagent-gui` console script)
- `src/embedagent/frontend/tui/launcher.py`: TUI launcher

**Configuration:**
- `pyproject.toml`: Package metadata, dependencies, pytest config, ruff config, black config
- `src/embedagent/config.py`: Runtime config loader (user-level + project-level JSON)

**Core Logic:**
- `src/embedagent/query_engine.py`: Session-scoped execution engine (1530 lines)
- `src/embedagent/inprocess_adapter.py`: Host/bridge layer (2446 lines)
- `src/embedagent/context.py`: Context budget and compaction pipeline (1088 lines)
- `src/embedagent/session.py`: Session dataclass model (620 lines)

**Testing:**
- `tests/conftest.py`: Shared pytest fixtures
- `tests/test_query_engine_*.py`: Query engine tests (multiple files)
- `tests/test_harness_*.py`: Harness component tests
- `tests/test_gui_*.py`: GUI backend tests
- `tests/test_inprocess_adapter_frontend_api.py`: Frontend API contract tests (77954 lines)

## Naming Conventions

**Files:**
- Modules use `snake_case.py`
- Test files use `test_*.py`
- GUI webapp uses `PascalCase.jsx` for components, `camelCase.js` for utilities

**Directories:**
- Package directories use `snake_case`
- GUI webapp directories use `kebab-case` or `snake_case`

**Classes:**
- PascalCase for all classes (e.g., `QueryEngine`, `ToolRuntime`, `SessionSnapshotProjector`)

**Functions/Methods:**
- snake_case for all functions and methods

**Private members:**
- Leading underscore for internal methods and module-level constants (e.g., `_LOG`, `_session_lock`, `_build_payload`)

## Where to Add New Code

**New Feature (Agent Core):**
- Primary code: `src/embedagent/<feature_module>.py`
- Tests: `tests/test_<feature>.py`

**New Mode or Discipline:**
- Mode definitions: `src/embedagent/modes.py`
- Harness contracts: `src/embedagent/harness/contracts.py`
- Phase engine rules: `src/embedagent/harness/phase_engine.py`
- Tests: `tests/test_modes.py`, `tests/test_phase_engine.py`

**New Tool:**
- Tool implementation: `src/embedagent/tools/<category>_ops.py` (e.g., `file_ops.py`, `git_ops.py`)
- Tool metadata: `src/embedagent/tools/runtime.py` (`_DEFAULT_TOOL_METADATA`)
- Or harness-specific: `src/embedagent/tools/harness_runtime.py` (`OFFICIAL_HARNESS_TOOL_METADATA`)
- Base classes: `src/embedagent/tools/_base.py`
- Tests: `tests/test_tools_*.py`

**New Frontend Protocol Type:**
- Dataclass: `src/embedagent/protocol/__init__.py`
- Adapter mapping: `src/embedagent/core/adapter.py`
- Tests: `tests/test_inprocess_adapter_frontend_api.py`

**New GUI Component:**
- React component: `src/embedagent/frontend/gui/webapp/src/components/<Name>.jsx`
- Store updates: `src/embedagent/frontend/gui/webapp/src/store.js`

**New TUI View:**
- View: `src/embedagent/frontend/tui/views/<name>.py`
- Import in: `src/embedagent/frontend/tui/views/__init__.py`

**Utilities/Helpers:**
- Shared helpers: `src/embedagent/tools/_base.py` (for tool context helpers)
- Or new module at top level: `src/embedagent/<utility>.py`

## Special Directories

**`src/embedagent/frontend/gui/static/`:**
- Purpose: Compiled GUI static assets served by FastAPI
- Generated: Yes (built from webapp source)
- Committed: Yes

**`src/embedagent/frontend/gui/webapp/node_modules/`:**
- Purpose: Node.js dependencies for GUI build
- Generated: Yes
- Committed: No (in .gitignore)

**`tests/fixtures/`:**
- Purpose: Test fixture data and mock packages
- Generated: No
- Committed: Yes

**`tests/manual/`:**
- Purpose: Manual/integration test scripts (e.g., Playwright)
- Generated: No
- Committed: Yes
- Note: Excluded from ruff linting

**`config/`:**
- Purpose: Runtime configuration files
- Generated: No
- Committed: No (contains `api_key`)

**`docs/archive/`:**
- Purpose: Completed slice artifacts
- Generated: No
- Committed: Yes
- Note: Historical reference only; active truth lives in `docs/` root

**`.embedagent/` (workspace-local):**
- Purpose: Project-level config, permission rules, session data, transcripts
- Generated: Yes (at runtime)
- Committed: No (in .gitignore)
- Contents: `config.json`, `permission-rules.json`, `sessions/`, `transcripts/`, `memory/`

---

*Structure analysis: 2026-05-02*
