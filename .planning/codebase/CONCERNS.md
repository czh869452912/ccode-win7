# Codebase Concerns

**Analysis Date:** 2026-05-02

## Tech Debt

### Massive Adapter Class

- **Issue:** `InProcessAdapter` in `src/embedagent/inprocess_adapter.py` is 2,446 lines. It mixes session lifecycle management, event emission, persistence, permission handling, tool execution orchestration, workspace file operations, and harness state refresh in a single class.
- **Files:** `src/embedagent/inprocess_adapter.py`
- **Impact:** Changes to one concern (e.g., event serialization) risk regressing unrelated concerns (e.g., session restore). Code reviews are difficult; the class has 30+ `with state.lock:` blocks and several 100+ line methods.
- **Fix approach:** Extract `SessionLifecycleManager`, `EventEmitter`, `WorkspaceFileService`, and `HarnessStateSynchronizer` into separate modules. Keep `InProcessAdapter` as a thin facade.

### Over-Sized Query Engine

- **Issue:** `QueryEngine` in `src/embedagent/query_engine.py` is 1,530 lines. It handles LLM retries, context compaction, tool partitioning, session persistence, memory maintenance, and reasoning delta streaming.
- **Files:** `src/embedagent/query_engine.py`
- **Impact:** The retry loop at line 1,430 uses `# type: ignore[misc]` to suppress a mypy error about `last_exc` possibly being unbound, masking control-flow complexity.
- **Fix approach:** Split into `LLMClientRetryWrapper`, `ContextCompactionEngine`, and `TurnOrchestrator`.

### Global Mutable State

- **Issue:** Several modules use module-level singletons that are mutated at runtime.
- **Files:**
  - `src/embedagent/modes.py` — `MODE_REGISTRY` (line 125) mutated by `initialize_modes()` via `global MODE_REGISTRY` (line 183)
  - `src/embedagent/command_sanitizer.py` — `_DEFAULT_SANITIZER` (line 158) lazy-initialized via `global _DEFAULT_SANITIZER` (line 162)
  - `src/embedagent/core/adapter.py` — `_inprocess_adapter` (line 32) lazy-initialized via `global _inprocess_adapter` (line 48)
- **Impact:** Unit tests can leak state between runs. Race conditions are possible when multiple tests or threads trigger initialization concurrently.
- **Fix approach:** Replace lazy module globals with explicit factory functions or dependency injection.

### Deprecated `datetime.utcnow()`

- **Issue:** `datetime.utcnow()` is deprecated in Python 3.12 and will be removed in a future version. The codebase uses it in at least five files.
- **Files:**
  - `src/embedagent/project_memory.py` (line 21)
  - `src/embedagent/inprocess_adapter.py` (line 77)
  - `src/embedagent/session_timeline.py` (line 17)
  - `src/embedagent/plan_store.py` (line 12)
  - `src/embedagent/session_restore.py` (line 432)
- **Impact:** Running on Python 3.12+ produces 4,000+ `DeprecationWarning` lines during test execution (observed: 4,062 warnings in 27.86s). This noise hides real issues and will eventually become a hard error.
- **Fix approach:** Replace `datetime.utcnow()` with `datetime.now(timezone.utc).replace(tzinfo=None)` or use `timezone.utc` aware objects consistently.

### Bare `except Exception:` Swallowing

- **Issue:** 44 occurrences of bare `except Exception:` (or equivalent) silently swallow errors, often returning empty collections or `None`.
- **Files:**
  - `src/embedagent/inprocess_adapter.py` (lines 321, 2205, 2244, 2249, 2358)
  - `src/embedagent/query_engine.py` (lines 476, 1449, 1453, 1457, 1505)
  - `src/embedagent/project_memory.py` (lines 497, 511, 547)
  - `src/embedagent/permissions.py` (line 184)
  - `src/embedagent/frontend/gui/backend/server.py` (lines 216, 637, 679)
  - `src/embedagent/frontend/tui/controller.py` (lines 255, 353, 362, 370)
  - `src/embedagent/tool_commit.py` (lines 65, 155, 183)
  - `src/embedagent/session_store.py` (line 297)
  - `src/embedagent/tool_execution.py` (line 105)
  - Many others across TUI services, tools, and harness modules
- **Impact:** Failures in persistence, permission loading, project memory refresh, and shell execution are silently ignored. Debugging production issues is extremely difficult.
- **Fix approach:** Log the exception with `logging.exception()` or `logging.warning()` at minimum. Distinguish between expected failures (file not found) and unexpected failures (corrupt data).

### Protocol Stub Files

- **Issue:** `src/embedagent/protocol/__init__.py` contains 25+ method bodies that are just `pass` (lines 325–451). These are ABC protocol definitions, but the density of stubs without docstrings or type hints on some parameters makes the protocol hard to implement correctly.
- **Files:** `src/embedagent/protocol/__init__.py`
- **Impact:** Frontend implementers must reverse-engineer the expected shape of callbacks from `CallbackBridge` in `src/embedagent/core/adapter.py`.
- **Fix approach:** Add parameter and return-type docstrings to all protocol methods.

## Known Bugs

### GUI Test Collection Errors

- **Symptoms:** `pytest` collection fails for GUI tests with `ModuleNotFoundError: No module named 'fastapi'`.
- **Files:** `tests/test_gui_backend_api.py`, `tests/test_gui_runtime.py`, `tests/test_gui_sync.py`
- **Trigger:** Run `uv run pytest tests/` without `fastapi` installed in the active venv.
- **Workaround:** Skip GUI tests with `-m "not gui"`.
- **Fix approach:** Either add `fastapi` and `uvicorn` as test dependencies in `pyproject.toml`, or wrap GUI test imports in `pytest.importorskip("fastapi")`.

### `ast.literal_eval` on Untrusted LLM Output

- **Symptoms:** When the LLM returns tool arguments that are not valid JSON, the code falls back to `ast.literal_eval(text)`.
- **Files:** `src/embedagent/llm.py` (lines 333–341)
- **Trigger:** Any tool call where the model outputs Python dict/list syntax instead of JSON.
- **Impact:** `ast.literal_eval` is safer than `eval()` but still parses arbitrary Python literals (including nested structures). A compromised or adversarial model could exploit this to cause unexpected behavior or denial of service with deeply nested structures.
- **Fix approach:** Remove the `ast.literal_eval` fallback. If JSON parsing fails, treat the tool call as malformed and surface the error to the user.

## Security Considerations

### `shell=True` in Subprocess Execution

- **Risk:** All shell tool commands execute via `subprocess.Popen(..., shell=True)` in `src/embedagent/tools/_base.py` (line 491–615). Even though `command_sanitizer.py` blocks some dangerous patterns, `shell=True` on Windows opens a `cmd.exe` process that parses the full command string, making injection possible if the sanitizer regexes have gaps.
- **Files:** `src/embedagent/tools/_base.py`
- **Current mitigation:** `CommandSanitizer` blocks `rm -rf`, `format`, `regedit`, etc. Permission system requires confirmation for write tools.
- **Recommendations:** Prefer `shell=False` with argument lists where possible. For user-provided command strings, use `shlex.split()` (or `shlex.split(..., posix=False)` on Windows) and execute without `shell=True`. If `shell=True` must remain, add a strict allow-list for command tokens rather than a deny-list.

### GUI Backend Lacks Authentication and CORS

- **Risk:** The FastAPI backend in `src/embedagent/frontend/gui/backend/server.py` binds to `127.0.0.1` with no CORS middleware, no API token check, and no request signing. Any process on the local machine can connect to `/api/files/{path:path}` or `/ws`.
- **Files:** `src/embedagent/frontend/gui/backend/server.py`
- **Current mitigation:** Binds to localhost only.
- **Recommendations:** Add a secret token generated at launcher startup and require it in an `X-EmbedAgent-Token` header for all HTTP and WebSocket requests. Add CORS middleware restricted to the PyWebView origin.

### API Key Storage in Plaintext JSON

- **Risk:** The `api_key` field from `AppConfig` is stored in `~/.embedagent/config.json` and `<workspace>/.embedagent/config.json` as plain text.
- **Files:** `src/embedagent/config.py`
- **Current mitigation:** `persistence_sanitize.py` redacts API keys when serializing to logs or tool results.
- **Recommendations:** Use the Windows Credential Manager (via `keyring` or `win32cred`) or at minimum document that users should set `api_key` via environment variable only.

### File Path Traversal in Workspace Tools

- **Risk:** Most file operations use `os.path.realpath(candidate)` to resolve paths, but some checks happen after resolution. The `tool_result_store.py` explicitly blocks `".."` as a path component (line 43), yet the check is component-level and may not catch all traversal variants.
- **Files:** `src/embedagent/tools/_base.py`, `src/embedagent/tool_result_store.py`, `src/embedagent/frontend/tui/services/workspace.py`
- **Recommendations:** Centralize path validation in `ToolContext.resolve_path()` and assert the resolved path is under `self.workspace` before any read/write operation.

## Performance Bottlenecks

### Repeated JSON Serialization in Context Assembly

- **Problem:** `ContextManager._estimate_tokens()` and `_build_candidate()` repeatedly call `json.dumps()` on individual messages and full payloads to estimate token counts.
- **Files:** `src/embedagent/context.py` (lines 158, 187, 815, 835, 853, 936, 1051, 1053)
- **Cause:** Token estimation uses character count (`len(json.dumps(message)) / chars_per_token`), which requires serializing the same message multiple times per turn.
- **Improvement path:** Cache the JSON string or pre-computed character count on `Message`/`Turn` objects. Use `orjson` or a faster JSON encoder if caching is insufficient.

### Busy-Wait Polling for Command Resolution

- **Problem:** `_wait_for_command_resolution()` polls session state in a tight loop with `time.sleep(0.05)`.
- **Files:** `src/embedagent/inprocess_adapter.py` (lines 1827–1840)
- **Cause:** The method waits for an interaction to resolve but uses polling instead of an event/condition variable.
- **Improvement path:** Replace polling with `threading.Condition` or `threading.Event` on `ManagedSession`.

### Lock Contention in `InProcessAdapter`

- **Problem:** `inprocess_adapter.py` acquires `state.lock` 30+ times across read/write operations, sometimes in nested patterns.
- **Files:** `src/embedagent/inprocess_adapter.py` (lines 404, 719, 779, 802, 809, 814, 845, 876, 1309, 1333, 1388, 1397, 1448, 1470, 1475, 1504, 1835, 1869, 1884, 1907, 1950, 1981, 1996, 2048, 2143, 2161, 2207, 2221, 2225, 2251, 2274, 2302, 2309, 2318)
- **Cause:** The monolithic adapter holds the lock for long-running operations (e.g., emitting events, serializing snapshots).
- **Improvement path:** Reduce lock granularity by copying immutable snapshot data outside the lock and emitting events without holding the lock.

## Fragile Areas

### Session Restore Logic

- **Files:** `src/embedagent/session_restore.py`
- **Why fragile:** The restoration algorithm must validate a long chain of invariants (message parent chains, tool call/result pairing, step/turn alignment, compact boundary integrity). There are 40+ distinct stop conditions in `test_session_restore.py` alone. A single off-by-one error in sequence validation can corrupt a restored session.
- **Safe modification:** Any change to `SessionRestorer.restore()` must be paired with a new test case in `test_session_restore.py`. Run the full restore test suite before committing.
- **Test coverage:** Good direct coverage via `test_session_restore.py`, but the integration with `inprocess_adapter.py` resume path is only indirectly tested.

### `QueryEngine` Retry and Compaction Loop

- **Files:** `src/embedagent/query_engine.py` (lines 1430–1458)
- **Why fragile:** The retry loop has three nested `except Exception` blocks for summary persist, project memory refresh, and session trim. If any one fails, the others are still attempted, but failures are silently logged. The `# type: ignore[misc]` at line 1442 masks a real control-flow issue where `last_exc` could theoretically be unbound.
- **Safe modification:** Add explicit `else` branches to the retry loop and remove the `# type: ignore`. Add unit tests that simulate each failure mode.

### `ToolContext.run_subprocess` Signal Handling

- **Files:** `src/embedagent/tools/_base.py` (lines 460–480)
- **Why fragile:** On Windows, the code sends `CTRL_BREAK_EVENT`, then falls back to `taskkill /F /T /PID`, then `process.kill()`. Each fallback is wrapped in `except (OSError, ValueError, subprocess.TimeoutExpired): pass`, so a zombie process is possible if all three attempts fail.
- **Safe modification:** Log each fallback failure. Add a hard timeout after which the process handle is abandoned and logged as an error.

## Scaling Limits

### Session Timeline Append Serialization

- **Current capacity:** `SessionTimelineStore` serializes concurrent writers per-file via an `RLock` dictionary (`_append_locks`).
- **Limit:** If the number of concurrent sessions writing to the same workspace grows, the lock dictionary itself becomes a bottleneck.
- **Scaling path:** Shard timeline files by session ID prefix to reduce lock contention.

### In-Memory Session Store

- **Current capacity:** `InProcessAdapter._sessions` is an in-memory dictionary with no eviction policy.
- **Limit:** Long-running server processes (GUI backend) will accumulate sessions indefinitely.
- **Scaling path:** Add an LRU eviction or a `max_sessions` limit with explicit unload to disk.

## Dependencies at Risk

### `ast.literal_eval` Security Surface

- **Risk:** See "Known Bugs" above. The fallback to `ast.literal_eval` in `llm.py` is a latent security issue.
- **Impact:** A malformed or adversarial model response could crash the process or consume excessive memory.
- **Migration plan:** Remove the fallback entirely; fail the tool call and request corrected JSON from the model.

### GUI Optional Dependencies

- **Risk:** `fastapi` and `pywebview` are optional runtime dependencies, but GUI tests fail hard when they are missing.
- **Impact:** CI cannot run the full test suite without installing heavy GUI dependencies.
- **Migration plan:** Use `pytest.importorskip("fastapi")` in GUI test modules so collection succeeds even when the dependency is absent.

## Missing Critical Features

### Request Size Limits on GUI Backend

- **Problem:** FastAPI endpoints such as `/api/files/{path:path}` (POST) and `/api/diff` accept arbitrary JSON bodies with no `Body(..., max_length=...)` or middleware size limit.
- **Files:** `src/embedagent/frontend/gui/backend/server.py`
- **Blocks:** Protection against accidental or malicious out-of-memory from huge file uploads.

### Workspace Path Validation in `InProcessAdapter`

- **Problem:** `read_workspace_file` and `write_workspace_file` in `inprocess_adapter.py` resolve paths but do not consistently verify the resolved path is inside the workspace boundary.
- **Files:** `src/embedagent/inprocess_adapter.py` (lines 2394–2395)
- **Blocks:** Defense-in-depth against path traversal if a tool bypasses `ToolContext` checks.

## Test Coverage Gaps

### No Dedicated Unit Tests for Core Modules

- **What's not tested:** Many core modules have no corresponding `test_*.py` file. Examples include:
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/context.py`
  - `src/embedagent/llm.py`
  - `src/embedagent/session.py`
  - `src/embedagent/workspace_intelligence.py`
  - `src/embedagent/permissions.py` (has tests but coverage is shallow)
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/tui/controller.py`
  - `src/embedagent/tools/_base.py`
  - `src/embedagent/tools/runtime.py`
  - All TUI view modules (`dialogs`, `editor`, `explorer`, `header`, `inspector`, `layout`, `timeline`)
- **Files:** See full list in analysis above.
- **Risk:** Refactoring the adapter, query engine, or context manager is dangerous without regression tests.
- **Priority:** High for `inprocess_adapter.py`, `query_engine.py`, and `context.py`; Medium for TUI views.

### No Tests for Shell Command Sanitizer

- **What's not tested:** `CommandSanitizer.is_blocked()` and `caution_note()` are not directly tested.
- **Files:** `src/embedagent/command_sanitizer.py`
- **Risk:** Changes to deny patterns or caution patterns could accidentally block legitimate commands or allow dangerous ones.
- **Priority:** High

### No Tests for `ast.literal_eval` Fallback Path

- **What's not tested:** The `llm.py` `_parse_arguments` method's `ast.literal_eval` branch is not covered.
- **Files:** `src/embedagent/llm.py`
- **Risk:** If this path is hit in production, it may fail on edge-case input or introduce security issues.
- **Priority:** High (especially because the fix is to remove the path entirely).

---

*Concerns audit: 2026-05-02*
