# Domain Pitfalls

**Domain:** Agentic coding framework with compile environment integration
**Researched:** 2026-05-02
**Confidence:** HIGH (based on direct codebase analysis + official Python docs)

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, security vulnerabilities, or major regressions.

---

### CE-1: Shell-Injection via Build Flags and Recipe Parameters

**What goes wrong:**  
The `run_recipe` tool and `run_command` tool both pass user-influenced strings through `shell=True` to `subprocess.Popen`. The `rewrite_command_for_managed_tools` uses a naive regex (`^(	*)(?:"([^"]+)"|([^\s|&;<>]+))`) to identify the first token. This regex is bypassable, and recipe parameters like `target` and `profile` are string-interpolated directly into commands without shell escaping.

**Why it happens:**  
- `shell=True` is used to support shell pipelines and redirections in recipes
- Recipe resolution in `workspace_recipes.py` does `command += " --target %s" % normalized_target` with no `shlex.quote()` equivalent
- The sanitizer (`get_default_sanitizer()`) only blocks known-dangerous patterns, it does not escape
- Windows 7 `cmd.exe` parsing rules differ from POSIX shell rules, making cross-platform escaping hard

**Consequences:**  
- A malicious workspace recipe or LLM-generated target name can inject arbitrary commands
- Build flags passed through `run_recipe` can execute unwanted code with the user's privileges
- On Windows, `&`, `|`, `&&`, `||` in target names become command separators

**Warning signs:**
- `shell=True` appears anywhere near user-influenced strings
- String formatting (`%`, `.format()`, f-strings) used to build command strings
- Sanitizer only blockslist patterns instead of escaping or using argument lists
- No audit log of executed commands

**Prevention:**
1. **Eliminate `shell=True` for recipe execution** — parse recipe commands into argument lists and use `subprocess.run(args, shell=False)`
2. **If shell must be used**, apply `shlex.quote()` on POSIX and a Windows-aware equivalent on Windows
3. **Validate recipe parameters** with strict allowlists (e.g., `^[A-Za-z0-9_.-]+$` for target names)
4. **Log every executed command** to transcript for forensic analysis
5. **Run recipe commands through the sanitizer** after parameter interpolation, not before

**Phase to address:** Phase 1 (Compile Environment Foundation) — security must be designed in, not retrofitted.

---

### CE-2: Compiler Path Detection Fragility (Bundled vs System vs Custom)

**What goes wrong:**  
`ToolContext.resolve_managed_command_executable()` and `classify_managed_command()` detect LLVM tools by executable name matching (`clang.exe`, `clang++.exe`, etc.). On Windows 7, the bundled toolchain may be shadowed by a system-installed LLVM, or vice versa. The `build_process_env()` prepends managed paths to PATH, but does not verify the resolved executable is the intended one.

**Why it happens:**  
- Detection is name-based, not path-signature-based
- No version validation (bundled Clang may differ from system Clang)
- `EMBEDAGENT_LLVM_ROOT` is set but not consumed by downstream logic
- `discover_bundle_root()` caches once; if the bundle is moved, the cache is stale

**Consequences:**  
- Build reproducibility breaks between machines (system Clang vs bundled Clang)
- Different warning/error formats break diagnostic parsing (`CLANG_DIAGNOSTIC_RE` vs `MSVC_DIAGNOSTIC_RE`)
- ABI-incompatible object files when mixing compiler versions
- Windows 7 path resolution quirks (short filenames, case insensitivity) cause missed detections

**Warning signs:**
- Build succeeds on one machine but fails on another with identical source
- Diagnostic regex fails to match compiler output
- `EMBEDAGENT_LLVM_ROOT` is set but ignored in build logs
- Stale `_bundle_root_cache` in `ToolContext`

**Prevention:**
1. **Fingerprint the resolved executable** — check `clang --version` output against expected bundled version
2. **Explicitly reference bundled tools** by absolute path instead of relying on PATH precedence
3. **Invalidate caches** when `discover_bundle_root()` returns a different path
4. **Fail fast** if the bundled toolchain is missing and no compatible system toolchain is found
5. **Store toolchain metadata** (version, path, source) in the build observation for debugging

**Phase to address:** Phase 1 (Compile Environment Foundation) — path resolution is foundational.

---

### CE-3: Build Directory Pollution and Cleanup Failures

**What goes wrong:**  
CMake recipes in `workspace_recipes.py` default to `build/` for all profiles. On Windows 7 with NTFS, long paths inside `build/` can exceed `MAX_PATH` (260 chars). There is no cleanup logic for stale build directories, and concurrent recipe runs may collide on the same `build/` directory.

**Why it happens:**  
- `resolve_workspace_recipe()` creates `build_dir = "build/%s" % normalized_profile.replace("\\", "/")` without path length checks
- No locking around build directory access
- No distinction between in-source and out-of-source builds
- `shutil.rmtree` in `session_store.py` silently catches `OSError`, masking cleanup failures

**Consequences:**  
- Stale object files from previous builds cause mysterious link errors
- Concurrent builds corrupt each other's state
- Path-length errors on Windows 7 cause silent cmake failures
- Disk space leaks from accumulated build artifacts

**Warning signs:**
- `build/` directory grows unbounded over sessions
- CMake "re-configure" errors about cached variables
- `OSError` silently swallowed in `cleanup()` methods
- Race conditions when two recipes run simultaneously

**Prevention:**
1. **Use profile-scoped build dirs** with unique identifiers (`build/<profile>_<hash>`)
2. **Implement build dir locking** via file locks or atomic directory creation
3. **Validate path lengths** before passing to cmake on Windows
4. **Add explicit cleanup recipes** and expose them through `list_recipes`
5. **Log build directory state** (size, file count) in recipe observations

**Phase to address:** Phase 2 (Build System Integration) — requires recipe system maturity.

---

### CE-4: Error Parsing Fragility Across Compilers and Locales

**What goes wrong:**  
The codebase hardcodes two diagnostic regexes: `CLANG_DIAGNOSTIC_RE` and `MSVC_DIAGNOSTIC_RE`. These assume English output and specific formatting. On systems with non-English locales, compiler messages may be localized, breaking parsing entirely. GCC is not handled at all.

**Why it happens:**  
- Only Clang and MSVC patterns exist; no GCC pattern
- No `LC_ALL=C` or equivalent forcing in `build_process_env()`
- Regexes assume single-byte character widths for column positions
- Error parsing is not separated from error collection

**Consequences:**  
- Quality reports miss errors/warnings on localized systems
- The LLM receives unparsed raw output instead of structured diagnostics
- False negatives in `report_quality_v2` cause broken builds to pass verification

**Warning signs:**
- `parse_test_summary()` or diagnostic parsing returns empty on non-English systems
- Regex match failures logged but ignored
- `report_quality_v2` reports 0 errors when compiler output shows failures

**Prevention:**
1. **Force `LC_ALL=C` / `LANGUAGE=en`** in build process environment for deterministic parsing
2. **Add GCC diagnostic regex** (`file:line:column: severity: message`)
3. **Use a pluggable diagnostic parser** registry instead of hardcoded regexes
4. **Fall back to raw output** with a "parse failed" flag so the LLM knows parsing was attempted
5. **Unit-test parsing** against real output from multiple compiler versions and locales

**Phase to address:** Phase 2 (Build System Integration) — requires compiler abstraction layer.

---

### CE-5: Environment Variable Inheritance and Override Leaks

**What goes wrong:**  
`ToolContext.build_process_env()` copies the entire `os.environ` and prepends managed paths. This inherits all parent environment variables, including `CC`, `CXX`, `CFLAGS`, `LDFLAGS`, which can override the intended bundled toolchain behavior. There is no allowlist or blocklist.

**Why it happens:**  
- `env = os.environ.copy()` is too permissive
- No filtering of toolchain-override variables
- Parent process may have Visual Studio environment variables set, conflicting with bundled LLVM

**Consequences:**  
- `CC=gcc` in parent environment silently switches compiler
- `LDFLAGS` from parent causes link errors with bundled libraries
- Non-reproducible builds depending on user's shell environment

**Warning signs:**
- Build behavior changes when launched from different shells (cmd vs PowerShell vs VS Code terminal)
- `EMBEDAGENT_RUNTIME_SOURCE` is set but `CC`/`CXX` are also present
- Build logs show unexpected compiler paths

**Prevention:**
1. **Use an explicit environment allowlist** for variables passed to child processes
2. **Unset or override `CC`, `CXX`, `CFLAGS`, `LDFLAGS`** when using bundled toolchain
3. **Log the effective environment** (sanitized) in diagnostic observations
4. **Provide an escape hatch** (`EMBEDAGENT_PRESERVE_ENV`) for power users

**Phase to address:** Phase 1 (Compile Environment Foundation) — environment hygiene is foundational.

---

### REF-1: Breaking Behavior During Large-Class Extraction

**What goes wrong:**  
`InProcessAdapter` (2,446 lines, 101 methods) and `QueryEngine` (1,530 lines, 36 methods) mix multiple responsibilities. Extracting classes without preserving exact transaction boundaries and state synchronization semantics causes regressions. The `_session_guard()` RLock is acquired at multiple nesting levels; splitting classes can change lock ordering or omit locks.

**Why it happens:**  
- `InProcessAdapter` manages sessions, builds engines, refreshes harness state, persists state, handles events, processes slash commands, resolves permissions, resolves user input, creates snapshots, manages timeline, restores sessions, and runs recipes
- `QueryEngine` owns turn execution, step management, context building, LLM calls with retry, compaction, transcript integration, tool observation recording, summary persistence, and memory maintenance
- Both use ad-hoc `with self._session_guard():` blocks scattered throughout methods
- Transcript events and session mutations are not atomic

**Consequences:**  
- Refactored code drops transcript events or double-records them
- Session state becomes inconsistent with transcript
- Race conditions in multi-threaded scenarios (GUI + background tasks)
- Test failures that are hard to diagnose because they depend on lock timing

**Warning signs:**
- Methods longer than 50 lines with multiple `with` blocks
- Same lock acquired and released multiple times in one method
- Direct field access to `session.turns`, `session.messages` outside guard blocks
- Tests that pass individually but flake in suite (lock ordering issues)

**Prevention:**
1. **Characterize before extracting** — write comprehensive characterization tests that assert exact behavior (including side effects) before touching code
2. **Extract by responsibility, not by size** — identify cohesive units (e.g., `TranscriptRecorder`, `HarnessStateManager`) with clear boundaries
3. **Preserve lock scope** — ensure extracted methods either run entirely inside or outside the guard, never split across extraction boundaries
4. **Use command pattern** for operations that mutate session + transcript together
5. **Run tests under thread sanitizer** or with `threading` stress tests

**Phase to address:** Phase 1 (Architecture Cleanup) — must precede feature work on these classes.

---

### REF-2: Test State Leakage from Global Singletons

**What goes wrong:**  
`MODE_REGISTRY` (in `modes.py`) and `_DEFAULT_SANITIZER` (in `command_sanitizer.py`) are global mutable singletons. Tests that call `initialize_modes()` mutate global state, causing order-dependent test failures. The comment on `MODE_REGISTRY` explicitly says "tests that import directly get the built-in defaults without calling initialize_modes()", which is a smell.

**Why it happens:**  
- `MODE_REGISTRY = dict(_BUILTIN_MODES)` at module level
- `initialize_modes()` mutates the global with `global MODE_REGISTRY; MODE_REGISTRY = new_registry`
- `_DEFAULT_SANITIZER` is lazily initialized and shared
- No `reset()` or context-manager for test isolation

**Consequences:**  
- Tests pass in isolation, fail in suite
- Heisenbugs where test order matters
- Impossible to parallelize tests
- Refactoring that changes initialization order breaks unrelated tests

**Warning signs:**
- Comments in source code apologizing for test behavior
- `global` keyword in module-level functions
- Lazy initialization with `if _DEFAULT_SANITIZER is None`
- Test files with explicit ordering or `pytest-order` markers

**Prevention:**
1. **Replace global singletons with instance registries** passed through constructors
2. **If globals must exist**, provide `reset_to_defaults()` and use `pytest` fixtures that call it
3. **Use dependency injection** — `InProcessAdapter` and `QueryEngine` should receive registries, not import them
4. **Add `pytest` fixtures** that snapshot and restore global state around every test

**Phase to address:** Phase 1 (Architecture Cleanup) — blocks safe refactoring of everything else.

---

### REF-3: Over-Engineering with Too Many Small Classes

**What goes wrong:**  
The opposite of REF-1: after identifying that `InProcessAdapter` is too large, there's a temptation to create dozens of tiny single-method classes (`SessionCreator`, `EngineBuilder`, `HarnessRefresher`, `StatePersister`, `EventEmitter`, `SlashCommandProcessor`, `PermissionResolver`, `UserInputResolver`, `SnapshotProjector`, `TimelineAppender`, `SessionRestorer`, `RecipeRunner`). This creates a "class explosion" where behavior is fragmented and hard to follow.

**Why it happens:**  
- Misapplication of SOLID principles without considering cohesion
- Each extracted class needs its own tests, mocks, and wiring
- The cognitive load shifts from "one big file" to "twenty tiny files with hidden coupling"

**Consequences:**  
- Harder to understand than the original large class
- Excessive mockery in tests masks real integration bugs
- Refactoring fatigue — developers avoid changing anything because it's spread across too many files
- Performance overhead from object churn

**Warning signs:**
- Classes with only one public method
- Test files that are mostly mock setup
- Developers needing to open 5+ files to understand one user action
- Names like `XxxService`, `XxxManager`, `XxxHandler` that don't describe behavior

**Prevention:**
1. **Group by workflow phase** — `SessionLifecycle` (create/restore/close), `TurnOrchestrator` (run loop/resume), `TranscriptRecorder` (all transcript I/O)
2. **Aim for 3-7 extracted classes**, not 20
3. **Keep related behavior together** — if two methods always call each other, they belong in the same class
4. **Measure cohesion** — if a class has methods that never call each other or share state, split further; if they always do, merge

**Phase to address:** Phase 1 (Architecture Cleanup) — during extraction, not after.

---

### REF-4: Losing Transaction Boundaries When Splitting Classes

**What goes wrong:**  
`QueryEngine._record_tool_observation()` performs multiple operations that must be atomic: `tool_commit.commit()`, `session.add_observation()`, `_persist_summary()`, `on_tool_finish()`. If these are split across classes without a transaction wrapper, partial failures leave session state inconsistent.

**Why it happens:**  
- The current code uses `with self._session_guard()` to protect some but not all operations
- `_persist_summary()` calls `self.summary_store.persist()` which does file I/O and SQLite writes outside the session lock
- `on_tool_finish` is a user callback that could throw
- `tool_commit.commit()` has its own `except Exception` fallback

**Consequences:**  
- Session says observation recorded but summary store disagrees
- Transcript has tool_call event but no matching observation
- Callback throws and aborts persistence, but session state is already mutated
- Recovery from checkpoint loads inconsistent state

**Warning signs:**
- Multiple side effects in one method with different failure handling
- Some operations inside `with` block, some outside
- Callbacks invoked between state mutations
- No rollback mechanism visible

**Prevention:**
1. **Define transaction boundaries explicitly** — document which operations must be atomic
2. **Use a two-phase commit pattern** — prepare all mutations, then apply them together
3. **Move persistence outside the hot path** — queue summaries for async persistence
4. **Make callbacks read-only observers** — they must not throw, or catch and log all exceptions
5. **Add consistency checks** — on load, verify transcript events match session state

**Phase to address:** Phase 1 (Architecture Cleanup) — must be designed into extraction.

---

### AL-1: Race Conditions in Suspend/Resume

**What goes wrong:**  
`QueryEngine.resume_interaction()` and `submit_command_turn()` both access `session.pending_interaction` without ensuring the session is in the expected state. The `stop_event` is checked in `_run_loop()` but not consistently in `_execute_action()`. Thread-local `stop_event` in `ToolContext` may not propagate to subprocesses.

**Why it happens:**  
- `resume_interaction()` calls `session.pending_interaction` outside `_session_guard()` initially, then enters the guard
- `stop_event` is passed as optional parameter through 5+ method layers
- `ToolContext.set_interrupt_event()` uses `threading.local()` — if tool execution spawns a thread pool, the event is invisible
- `terminate_process_tree()` on Windows uses `taskkill /F /T` which is asynchronous

**Consequences:**  
- Resumed interaction operates on stale `pending_interaction`
- Stop signal ignored during long-running recipe execution
- Zombie subprocesses after interrupt
- Session state corrupted by concurrent resume + stop

**Warning signs:**
- `pending_interaction` accessed both with and without lock
- `stop_event` passed through long parameter chains
- Subprocess timeout logic uses polling loops with hardcoded 0.2s intervals
- `taskkill /F` followed immediately by `process.wait(timeout=0.5)`

**Prevention:**
1. **Centralize session state machine** — define explicit states (idle, running, suspended, stopping) with valid transitions
2. **Use condition variables** instead of polling for stop/resume coordination
3. **Propagate stop_event to subprocess** via process group on POSIX, or job object on Windows
4. **Make resume idempotent** — if already resumed, return existing result instead of restarting
5. **Add thread-safety tests** that deliberately interleave operations

**Phase to address:** Phase 3 (Agent Loop Hardening) — requires careful concurrency design.

---

### AL-2: Context Loss During Compaction

**What goes wrong:**  
The compaction retry loop in `_run_loop()` catches `ModelClientError`, checks `_should_retry_with_compact()` against a hardcoded list of string markers (`"context length"`, `"maximum context"`, `"prompt is too long"`, `"max tokens"`, `"too many tokens"`, `"上下文"`, `"超出上下文"`), forces compaction, and retries once. If compaction removes critical context (e.g., the failing recipe's error output, marked as high priority), the retry fails for a different reason and the original error is lost.

**Why it happens:**  
- `_COMPACT_RETRY_ERROR_MARKERS` is a heuristic string match, not structured error codes
- `_maybe_record_compact_boundary()` checks `assembly.compacted` but not whether high-priority tool results were preserved
- The `ContextManager` hard-trims messages to fit budget, potentially discarding the very diagnostic output needed to fix the build
- There is no validation that the compacted context still contains enough information for the LLM to succeed

**Consequences:**  
- LLM retries with less context and produces worse or broken output
- Original error (context length) masked by new error (missing information)
- Transcript records "compact_retry" transition but not what was lost
- User sees a confusing failure that doesn't match the real problem

**Warning signs:**
- Retry succeeds on context length but fails with "I don't have enough information"
- `_HIGH_PRIORITY_TOOLS` is defined but not enforced during hard-trim
- `compact_retry_used = True` prevents more than one compaction per step
- No metrics on compaction success rate

**Prevention:**
1. **Use structured error codes** from the model client (HTTP 413, specific error types) instead of string matching
2. **Preserve high-priority context** by marking critical messages as non-compactable
3. **Validate post-compaction context** — ensure the LLM still has the information it needs
4. **Limit compaction depth** — don't compact more than N turns, fail gracefully instead
5. **Track compaction outcomes** — log whether compaction+retry succeeded or failed

**Phase to address:** Phase 3 (Agent Loop Hardening) — core loop behavior.

---

### AL-3: Infinite Loops from Retry Logic

**What goes wrong:**  
`_call_llm_with_retry()` retries up to `_LLM_MAX_RETRIES = 3` with exponential backoff. However, `_run_loop()` has its own retry via `compact_retry_used`, and `submit_command_turn()` / `resume_interaction()` call `_run_loop()` which can loop up to `max_turns = 8`. These retry layers can compound: a transient error could consume 3 LLM retries × 8 turns = 24 API calls before failing.

**Why it happens:**  
- Retry logic is layered without coordination
- `_call_llm_with_retry()` sleeps in the main thread, blocking the UI
- No circuit breaker for repeated failures
- `ModelClientError` is caught at multiple levels with different handling

**Consequences:**  
- API quota exhaustion or rate limiting
- UI appears frozen during retry sleeps
- Users cannot cancel during the sleep period
- Transcript flooded with failed attempts

**Warning signs:**
- Multiple nested retry loops with different counters
- `time.sleep()` in main execution thread
- No `stop_event` check between retry attempts
- Same error type retried at multiple layers

**Prevention:**
1. **Use a single retry policy** at the outermost layer (`_run_loop()`), not in `_call_llm_with_retry()`
2. **Make LLM calls non-blocking** or use async/await (if Python 3.8 compatible)
3. **Check `stop_event` during retry delays** — allow immediate cancellation
4. **Implement circuit breaker** — after N failures in a session, fail fast with "service unavailable"
5. **Cap total retry budget** — e.g., max 3 retries per turn, max 6 per session

**Phase to address:** Phase 3 (Agent Loop Hardening) — requires retry architecture redesign.

---

### AL-4: Tool Execution Timeouts and Deadlocks

**What goes wrong:**  
`ToolContext.run_subprocess()` uses a polling loop with `process.communicate(timeout=0.2)` and checks `stop_event` only on `TimeoutExpired`. If the subprocess generates massive output, the pipe buffer fills and the subprocess blocks before `communicate()` returns. The `terminate_process_tree()` on Windows tries `CTRL_BREAK_EVENT`, then `taskkill /F /T`, then `process.kill()`, but each has a 0.5s grace period that may not be enough for deeply nested processes.

**Why it happens:**  
- `stdout=PIPE, stderr=PIPE` with polling is deadlock-prone per Python subprocess docs
- `communicate()` is the recommended approach, but the code uses it inside a loop with tiny timeouts
- Windows process tree termination is inherently racy
- No handling of subprocesses that spawn their own children (e.g., `make` spawning `cl.exe`)

**Consequences:**  
- UI freezes waiting for deadlocked subprocess
- Zombie processes accumulate on Windows
- Interrupted builds leave lock files that prevent future builds
- `stop_event` is ignored if subprocess is blocked on I/O

**Warning signs:**
- `process.communicate(timeout=0.2)` in a while-True loop
- `terminate_process_tree()` with short grace periods
- No handling of `OSError` during termination
- Build tools that spawn children (cmake, make) not tracked

**Prevention:**
1. **Use `subprocess.run()` with `timeout`** instead of manual polling for simple cases
2. **For streaming/interruptibility**, use threads to drain pipes asynchronously
3. **Track child PIDs** on Windows using `job objects` to ensure entire tree is killed
4. **Increase grace period** or make it configurable per tool type
5. **Add watchdog thread** that monitors subprocess health and force-kills if unresponsive

**Phase to address:** Phase 2 (Build System Integration) — tool execution is shared infrastructure.

---

### ST-1: Data Corruption During Transcript Append

**What goes wrong:**  
`TranscriptStore.append_event()` writes JSON lines to `.jsonl` files with `handle.flush(); os.fsync(handle.fileno())`. The `_repair_tail()` method truncates partial lines by scanning from the start. On Windows 7, power loss or process crash between `write()` and `fsync()` can leave a partially written line. The `_scan_cache` is in-memory and not shared across processes.

**Why it happens:**  
- `_repair_tail()` uses `_scan_events()` which reads the entire file to find valid length
- No checksum or length prefix on lines
- `_scan_cache` is process-local; multi-process access (e.g., GUI backend + CLI) sees stale cache
- `os.fsync()` on Windows flushes to OS buffer, not necessarily to disk on all filesystems

**Consequences:**  
- Transcript loses events, breaking session history replay
- `_next_seq()` returns duplicate sequence numbers after repair
- Session restore loads truncated or inconsistent transcript
- Cache inconsistency causes `seq` gaps or duplicates

**Warning signs:**
- `_repair_tail()` truncates files regularly
- `_scan_cache` keyed by `os.path.realpath()` but not invalidated on external changes
- No file locking between processes
- Sequence numbers in transcript are non-monotonic

**Prevention:**
1. **Use length-prefixed records** (4-byte length + JSON) instead of newline-delimited
2. **Add per-line CRC32** to detect corruption without scanning
3. **Use file locking** (`msvcrt.locking` on Windows, `fcntl` on POSIX) for multi-process safety
4. **Invalidate cache on mtime change** — check `os.stat().st_mtime` before using cached scan
5. **Write to WAL-style append-only log** instead of modifying existing files

**Phase to address:** Phase 4 (Storage Reliability) — durability improvements.

---

### ST-2: Migration Failures on Schema Changes

**What goes wrong:**  
`ProjectionDb._ensure_columns()` adds missing columns with `ALTER TABLE ... ADD COLUMN`, but it cannot handle type changes, column renames, or dropped columns. The `_ensure_columns()` is called during `initialize()`, but there's no schema version tracking. If a column type changes (e.g., `turn_count` from `INTEGER` to `TEXT`), old databases crash on insert.

**Why it happens:**  
- `schema_meta` table exists but is unused for versioning
- `_ensure_columns()` only adds, never modifies or removes
- SQLite's `ALTER TABLE` is limited — no `DROP COLUMN` in older versions
- No migration scripts or versioning policy

**Consequences:**  
- Existing user databases become incompatible after upgrade
- `sqlite3.OperationalError` on startup, blocking entire application
- Manual database deletion required, losing all session history

**Warning signs:**
- `schema_meta` table created but never populated
- `_ensure_columns()` is the only migration mechanism
- Column types hardcoded in SQL without version history
- No tests for opening old database files

**Prevention:**
1. **Implement schema versioning** — store version in `schema_meta`, run migrations sequentially
2. **Use migration scripts** (`m001_create_tables.sql`, `m002_add_started_at.sql`, etc.)
3. **Test migrations** by creating databases at each version and upgrading to current
4. **Provide `projection_db.migrate_or_recreate()`** that recreates from summary files if migration fails
5. **Never change column types** — add new columns, deprecate old ones, remove in major versions only

**Phase to address:** Phase 4 (Storage Reliability) — schema stability is long-term maintenance.

---

### ST-3: Encryption Key Management (Future Risk)

**What goes wrong:**  
The codebase currently stores transcripts and summaries as plaintext JSON. If encryption is added later (e.g., for API keys in config or sensitive source code in transcripts), key management is often an afterthought. Hardcoded keys, keys stored next to data, or keys derived from predictable passwords are common failures.

**Why it happens:**  
- Encryption is often added reactively ("compliance requirement") without architectural planning
- Python 3.8 has `cryptography` library but it's a heavy dependency
- Offline deployment means no key server or HSM

**Consequences:**  
- Encryption provides false security (key is extractable from bundle)
- Users lose all data if they forget password (no recovery)
- Key rotation is impossible without re-encrypting everything

**Warning signs:**
- ` Fernet ` or `AES` usage without key derivation
- Keys stored in source code or config files
- No separation between data encryption and transport encryption

**Prevention:**
1. **If encryption is needed**, derive keys from user password using PBKDF2/HKDF with per-user salt
2. **Store salt separately** from encrypted data
3. **Use Python's `secrets` module** for key generation, never `random`
4. **Document the threat model** — encryption protects against what threat? (Theft of laptop? Malware?)
5. **Consider not encrypting** if the threat model doesn't justify the complexity and key-recovery risk

**Phase to address:** Phase 5 (Security Hardening) — defer until threat model is defined.

---

## Moderate Pitfalls

### MP-1: `datetime.utcnow()` Deprecation Cascade

**What goes wrong:**  
`datetime.utcnow()` is used in 10+ source files (`inprocess_adapter.py`, `session.py`, `transcript_store.py`, `session_store.py`, etc.). In Python 3.12+ this is deprecated and warns. While the project targets Python 3.8, forward compatibility is valuable, and the deprecation warnings (4,000+ in tests) mask other issues.

**Prevention:**  
Replace all `datetime.utcnow()` with `datetime.now(timezone.utc).replace(tzinfo=None)` or use a shared `_utc_now()` utility. Do this in a single mechanical PR.

**Phase:** Phase 0 (Hygiene) — can be done immediately.

---

### MP-2: Bare `except Exception:` Blocks

**What goes wrong:**  
25 bare `except Exception:` blocks across `src/`. These catch `KeyboardInterrupt`, `SystemExit`, `MemoryError`, and `GeneratorExit`, often unintentionally. They also swallow stack traces, making debugging impossible.

**Prevention:**  
1. Replace with `except (SpecificError, AnotherError):` where possible
2. Where generic catch is needed, use `except Exception as exc:` and log the full traceback with `_LOG.exception()`
3. Never catch `Exception` without re-raising or logging
4. Add ruff rule `E722` and `B001` to CI to prevent new occurrences

**Phase:** Phase 0 (Hygiene) — can be done incrementally.

---

### MP-3: JSONL Corruption from Multi-Process Access

**What goes wrong:**  
`TranscriptStore` uses per-path `threading.RLock` instances. If the GUI backend and CLI run concurrently (same workspace), they are separate processes and the thread lock provides no protection. Two processes appending to the same `transcript.jsonl` can interleave writes.

**Prevention:**  
Use file-based locking (`portalocker` or `msvcrt.locking` / `fcntl`) for cross-process safety. Alternatively, assign one process as the transcript writer and use IPC for others.

**Phase:** Phase 4 (Storage Reliability) — multi-process safety.

---

## Minor Pitfalls

### MiP-1: SQLite Connection Per Operation

**What goes wrong:**  
`ProjectionDb` opens and closes a SQLite connection for every operation. This is safe but slow for batch operations. `check_same_thread=True` is the default, which is correct but limits connection reuse.

**Prevention:**  
Connection pooling is unnecessary for the current workload, but document the decision. If batch operations are added later, use a persistent connection with explicit transaction boundaries.

**Phase:** Not urgent — monitor performance.

---

### MiP-2: `uuid.uuid4().hex[:12]` Collision Risk

**What goes wrong:**  
IDs are truncated to 12 hex chars (48 bits). The birthday bound means ~16 million IDs before 50% collision probability. For a long-running system, this is eventually a problem.

**Prevention:**  
Use full UUIDs or add a counter suffix. 48 bits is acceptable for the current scale but should be documented as a limit.

**Phase:** Not urgent — architectural debt note.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Compile Env (Phase 1) | Shell injection via recipe params | Eliminate `shell=True` or add strict escaping |
| Compile Env (Phase 1) | Wrong compiler detected | Fingerprint resolved executable, validate version |
| Compile Env (Phase 1) | Env var leaks break builds | Use explicit env allowlist |
| Build System (Phase 2) | Build dir collisions | Profile-scoped dirs + file locking |
| Build System (Phase 2) | Diagnostic parsing fails | Force `LC_ALL=C`, add GCC regex |
| Build System (Phase 2) | Subprocess deadlocks | Async pipe draining, job objects on Windows |
| Agent Loop (Phase 3) | Resume races with stop | Centralized state machine, condition variables |
| Agent Loop (Phase 3) | Context lost in compaction | Preserve high-priority messages, validate post-compact |
| Agent Loop (Phase 3) | Retry cascade exhaustion | Single retry policy, circuit breaker |
| Storage (Phase 4) | Transcript corruption | Length-prefixed records, file locking |
| Storage (Phase 4) | Schema migration crashes | Versioned migrations, test upgrade paths |
| Architecture (Phase 1) | Extraction breaks behavior | Characterization tests, preserve lock scope |
| Architecture (Phase 1) | Global singleton test leaks | Instance registries, DI, reset fixtures |

---

## Sources

- Python 3.14 subprocess documentation: https://docs.python.org/3/library/subprocess.html (HIGH confidence)
- Python 3.14 sqlite3 documentation: https://docs.python.org/3/library/sqlite3.html (HIGH confidence)
- Direct codebase analysis of `src/embedagent/` (HIGH confidence):
  - `inprocess_adapter.py` — 2,446 lines, 101 methods
  - `query_engine.py` — 1,530 lines, 36 methods
  - `tools/_base.py` — subprocess execution, managed tool resolution
  - `workspace_recipes.py` — recipe resolution and command building
  - `transcript_store.py` — jsonl persistence and repair
  - `projection_db.py` — SQLite schema and migration
  - `modes.py` — `MODE_REGISTRY` global mutable state
  - `command_sanitizer.py` — `_DEFAULT_SANITIZER` global singleton
- Martin Fowler, "Workflows of Refactoring" — refactoring taxonomy (MEDIUM confidence)
- C2 Wiki, "God Class" — large class anti-pattern (MEDIUM confidence)
