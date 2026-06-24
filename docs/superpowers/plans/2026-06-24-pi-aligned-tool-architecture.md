# Pi-Aligned Tool Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current C/C++-heavy public tool surface with a Pi-aligned minimal primitive tool architecture centered on a first-class `bash` tool.

**Architecture:** Agent Core exposes small primitive tools, while the default C/C++ workflow package owns recipe, quality, task, and evidence tools through the extension boundary. `run_build` is removed from the public contract instead of being aliased or patched; build commands run through `bash`, and recipe execution becomes readiness-aware and refusal-capable.

**Tech Stack:** Python 3.8, stdlib subprocess/threading/codecs/locale/ctypes, existing `ToolRuntime`, `ToolContext`, C workflow extension, pytest/unittest.

---

## File Structure

- Modify `src/embedagent/tools/shell_ops.py`: rename the public model-facing command tool to `bash`; keep implementation small and delegate execution to `ToolContext.run_shell_tool`.
- Modify `src/embedagent/tools/runtime.py`: replace `run_command` metadata with `bash` metadata and keep catalog projection aligned with primitive Core.
- Modify `src/embedagent/modes.py`: include `bash` in build/debug/verify mode contracts as the general command primitive.
- Modify `src/embedagent/tools/_base.py`: add bytes-first subprocess decoding, managed Bash discovery, full-output materialization hooks, and richer command observations.
- Modify `src/embedagent/tools/compile_ops.py`: remove `run_build` and build-artifact behavior from model-visible workflow tools.
- Modify `src/embedagent/harness/packs.py`: remove `run_build`, `list_compilers`, and `configure_build_env` from model-visible workflow packs; add `bash` as the command primitive where command execution is expected.
- Modify `src/embedagent/harness/tool_metadata.py`: remove public metadata for `run_build`; keep only workflow-owned tools.
- Modify `src/embedagent/harness/context_reducers.py`: remove `run_build` reducer and high-priority registration; make diagnostic reduction reusable for `bash`/`run_recipe` where needed.
- Modify `src/embedagent/workspace_recipes.py`: add recipe readiness, confidence, prerequisites, reasons, and suggested next steps.
- Modify `src/embedagent/tools/recipe_ops.py`: return enriched `list_recipes` data and make `run_recipe` refuse missing prerequisites before spawning.
- Modify `scripts/offline-runtime-contract.json`: add bundled Bash as a required runtime capability under MinGit/Git Bash.
- Modify docs: `README.md`, `AGENTS.md`, `docs/overall-solution-architecture.md`, `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/design-change-log.md`, `docs/mode-schema.md`, `docs/tool-contracts.md`, `docs/permission-model.md`, `docs/frontend-protocol.md`, `docs/agent-harness-v2.md`.
- Modify tests: `tests/test_tools_package.py`, `tests/test_context_config.py`, `tests/test_harness_contracts.py`, `tests/test_workflow_package_manifest.py`, and focused tests as needed.

---

### Task 1: Lock Core Schema Around `bash`

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `src/embedagent/tools/shell_ops.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/modes.py`

- [ ] **Step 1: Write failing schema tests**

In `tests/test_tools_package.py`, update `TestToolRuntimeSchemas.test_official_tool_catalog_excludes_legacy_duplicate_tools` so the expected Core command tool is `bash`, not `run_command`:

```python
expected = [
    "read_file",
    "write_file",
    "edit_file",
    "bash",
    "git_status",
    "git_diff",
    "git_log",
]
for name in expected:
    self.assertIn(name, self.tool_names, "Missing tool: %s" % name)
for name in (
    "run_command",
    "list_compilers",
    "configure_build_env",
    "run_build",
    "list_files",
    "search_text",
    "compile_project",
    "run_tests",
    "run_clang_tidy",
    "run_clang_analyzer",
    "collect_coverage",
    "report_quality",
    "manage_todos",
):
    self.assertNotIn(name, self.tool_names, "Legacy tool leaked: %s" % name)
```

Update `test_total_tool_count` to the new count after replacing `run_command` with `bash`; if only the name changes, keep the count unchanged.

Add or update mode projection assertions:

```python
def test_schemas_for_build_exposes_bash_primitive(self):
    names = [
        item["function"]["name"]
        for item in self.rt.schemas_for("build", workflow_state="chat")
    ]
    self.assertIn("bash", names)
    self.assertNotIn("run_command", names)
    self.assertNotIn("run_build", names)

def test_schemas_for_verify_exposes_bash_without_write_tools(self):
    names = [
        item["function"]["name"]
        for item in self.rt.schemas_for("verify", workflow_state="chat")
    ]
    self.assertIn("bash", names)
    self.assertNotIn("write_file", names)
    self.assertNotIn("edit_file", names)
    self.assertNotIn("run_build", names)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas -v
```

Expected: failures show `bash` is missing and/or `run_command` still exists.

- [ ] **Step 3: Implement public `bash` tool**

In `src/embedagent/tools/shell_ops.py`, change the tool definition name and observation name to `bash`:

```python
def _bash(arguments: Dict[str, Any]) -> Observation:
    command_text = str(arguments["command"]).strip()
    cwd_argument = str(arguments.get("cwd") or ".")
    timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_COMMAND_TIMEOUT_SEC)
    sanitizer = get_command_sanitizer()
    blocked, reason = sanitizer.is_blocked(command_text)
    if blocked:
        raise ToolError(reason)
    return ctx.run_shell_tool("bash", command_text, cwd_argument, timeout_sec)
```

Return a single `ToolDefinition(name="bash", ...)` with concise English or UTF-8 Chinese description:

```python
description=(
    "Execute a Bash command in the workspace. Use this for build commands, "
    "tests, scripts, and command-line exploration. Do not repeat the same "
    "failing command unchanged."
)
```

Keep the parameters as `command`, optional `cwd`, optional `timeout_sec`.

- [ ] **Step 4: Update runtime metadata**

In `src/embedagent/tools/runtime.py`, replace the `_DEFAULT_TOOL_METADATA["run_command"]` entry with `_DEFAULT_TOOL_METADATA["bash"]`:

```python
"bash": {
    "permission_category": "shell_exec",
    "mode_visibility": ["build", "debug", "verify"],
    "workflow_visibility": ["chat", "plan", "review", "command"],
    "user_label": "Bash",
    "progress_renderer_key": "command",
    "result_renderer_key": "command",
    "supports_diff_preview": False,
    "context_reducer_key": "bash",
    "read_only": False,
    "concurrency_safe": False,
    "interrupt_behavior": "cancel",
    "result_budget_policy": "artifact-first",
    "activity_kind": "command",
    "context_priority": 88,
},
```

- [ ] **Step 5: Update built-in mode contracts**

In `src/embedagent/modes.py`, add `"bash"` to `build`, `debug`, and `verify` `allowed_tools`. Do not add it to `explore` or `spec` unless the product explicitly wants command execution in those modes.

- [ ] **Step 6: Run schema tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas -v
```

Expected: all `TestToolRuntimeSchemas` tests pass.

---

### Task 2: Replace Text-Mode Subprocess Output With Bytes-First Decoding

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `src/embedagent/tools/_base.py`

- [ ] **Step 1: Add focused decoding tests**

In `tests/test_tools_package.py`, add `TestCommandOutputDecoding`:

```python
class TestCommandOutputDecoding(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("command-decoding")
        self.ctx = ToolContext(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_decode_command_output_prefers_utf8(self):
        decoded = self.ctx.decode_command_output("stdout", "hello 中文".encode("utf-8"))
        self.assertEqual(decoded.text, "hello 中文")
        self.assertEqual(decoded.encoding, "utf-8")
        self.assertEqual(decoded.decode_errors_count, 0)

    def test_decode_command_output_falls_back_to_gbk(self):
        decoded = self.ctx.decode_command_output("stdout", "中文".encode("gbk"))
        self.assertEqual(decoded.text, "中文")
        self.assertIn(decoded.encoding, ("gbk", "cp936"))
        self.assertEqual(decoded.decode_errors_count, 0)

    def test_decode_command_output_reports_replacement_fallback(self):
        decoded = self.ctx.decode_command_output("stdout", b"\xff\xfe\x00\x81")
        self.assertTrue(decoded.decode_errors_count >= 0)
        self.assertIn("encoding", decoded.to_metadata())
```

- [ ] **Step 2: Add command observation shape test**

Add:

```python
@unittest.skipIf(sys.platform != "win32", "Windows-only: requires cmd.exe")
def test_bash_result_contains_decode_metadata(self):
    rt = ToolRuntime(self.workspace)
    obs = rt.execute("bash", {"command": "cmd /c echo hello"})
    self.assertTrue(obs.success)
    self.assertIn("stdout", obs.data)
    self.assertIn("stdout_encoding", obs.data)
    self.assertIn("stdout_decode_errors_count", obs.data)
    self.assertIn("stderr_encoding", obs.data)
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestCommandOutputDecoding -v
uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute::test_bash_result_contains_decode_metadata -v
```

Expected: tests fail because `decode_command_output` and `bash` metadata do not exist yet.

- [ ] **Step 4: Add decoder result type**

In `src/embedagent/tools/_base.py`, add:

```python
@dataclass
class DecodedCommandOutput:
    stream_name: str
    text: str
    encoding: str
    decode_errors_count: int
    output_maybe_mojibake: bool

    def to_metadata(self) -> Dict[str, Any]:
        prefix = self.stream_name
        return {
            "%s_encoding" % prefix: self.encoding,
            "%s_decode_errors_count" % prefix: self.decode_errors_count,
            "%s_output_maybe_mojibake" % prefix: self.output_maybe_mojibake,
        }
```

- [ ] **Step 5: Implement Windows code page helpers**

In `ToolContext`, add helpers that work on Python 3.8:

```python
def _windows_code_page_encoding(self, getter_name: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import ctypes

        getter = getattr(ctypes.windll.kernel32, getter_name)
        code_page = int(getter())
    except Exception:
        return ""
    return "cp%s" % code_page if code_page > 0 else ""

def command_output_encodings(self) -> List[str]:
    encodings = ["utf-8-sig", "utf-8"]
    for value in (
        self._windows_code_page_encoding("GetOEMCP"),
        self._windows_code_page_encoding("GetACP"),
        "gbk",
        "cp936",
    ):
        if value and value not in encodings:
            encodings.append(value)
    return encodings
```

- [ ] **Step 6: Implement `decode_command_output`**

Add:

```python
def decode_command_output(self, stream_name: str, raw_bytes: bytes) -> DecodedCommandOutput:
    data = raw_bytes or b""
    for encoding in self.command_output_encodings():
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        return DecodedCommandOutput(
            stream_name=stream_name,
            text=self.sanitize_command_output(text),
            encoding=encoding.replace("-sig", ""),
            decode_errors_count=0,
            output_maybe_mojibake=False,
        )
    text = data.decode("utf-8", errors="replace")
    return DecodedCommandOutput(
        stream_name=stream_name,
        text=self.sanitize_command_output(text),
        encoding="utf-8-replace",
        decode_errors_count=text.count("\ufffd"),
        output_maybe_mojibake=True,
    )
```

Add `sanitize_command_output` that removes unsafe controls but preserves `\n`, `\r`, and `\t`.

- [ ] **Step 7: Change `run_subprocess` to capture bytes**

In `run_subprocess`, remove `universal_newlines=True`, `encoding="utf-8"`, and `errors="replace"`. Use `communicate()` bytes, then decode with `decode_command_output`. Preserve timeout and interrupt behavior.

The returned dict should include:

```python
"stdout": stdout_text,
"stderr": stderr_text,
"stdout_encoding": stdout_decoded.encoding,
"stderr_encoding": stderr_decoded.encoding,
"stdout_decode_errors_count": stdout_decoded.decode_errors_count,
"stderr_decode_errors_count": stderr_decoded.decode_errors_count,
"stdout_output_maybe_mojibake": stdout_decoded.output_maybe_mojibake,
"stderr_output_maybe_mojibake": stderr_decoded.output_maybe_mojibake,
```

- [ ] **Step 8: Update `build_command_observation`**

Copy decode metadata from the subprocess result into observation data. Also set:

```python
if result["exit_code"] != 0:
    data["error_kind"] = "command_failed"
    data["retryable"] = False
    data["suggested_next_step"] = "Inspect stdout/stderr and change the command or project state before retrying."
elif result["timed_out"]:
    data["error_kind"] = "timeout"
    data["retryable"] = False
```

- [ ] **Step 9: Run decoding tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestCommandOutputDecoding -v
uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute -k bash -v
```

Expected: decoding and `bash` tests pass.

---

### Task 3: Add Tail Truncation And Full Output References

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `src/embedagent/tools/_base.py`
- Modify: `src/embedagent/tool_result_store.py` only if a reusable generic artifact writer is needed

- [ ] **Step 1: Write failing truncation test**

Add to `TestCommandOutputDecoding`:

```python
def test_truncate_output_keeps_tail(self):
    text = "a" * (MAX_COMMAND_OUTPUT_CHARS + 20)
    truncated, was_truncated = self.ctx.truncate_output(text)
    self.assertTrue(was_truncated)
    self.assertEqual(len(truncated), MAX_COMMAND_OUTPUT_CHARS)
    self.assertTrue(truncated.endswith("a" * 20))
```

Import `MAX_COMMAND_OUTPUT_CHARS` from `embedagent.tools._base`.

- [ ] **Step 2: Write failing full output reference test**

Add:

```python
def test_command_observation_records_full_output_ref_when_truncated(self):
    long_text = "x" * (MAX_COMMAND_OUTPUT_CHARS + 10)
    result = {
        "exit_code": 0,
        "stdout": long_text,
        "stderr": "",
        "stdout_truncated": True,
        "stderr_truncated": False,
        "duration_ms": 1,
        "timed_out": False,
        "interrupted": False,
        "stdout_encoding": "utf-8",
        "stderr_encoding": "utf-8",
        "stdout_decode_errors_count": 0,
        "stderr_decode_errors_count": 0,
        "stdout_output_maybe_mojibake": False,
        "stderr_output_maybe_mojibake": False,
    }
    obs = self.ctx.build_command_observation("bash", "echo long", self.workspace, result)
    self.assertTrue(obs.data["stdout_truncated"])
    self.assertIn("full_output_ref", obs.data)
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestCommandOutputDecoding -v
```

Expected: tail truncation or full output reference assertions fail.

- [ ] **Step 4: Make truncation keep tail**

Change `ToolContext.truncate_output`:

```python
def truncate_output(self, text: str) -> Tuple[str, bool]:
    if len(text) <= MAX_COMMAND_OUTPUT_CHARS:
        return text, False
    return text[-MAX_COMMAND_OUTPUT_CHARS:], True
```

- [ ] **Step 5: Add simple command output artifact writer**

Use `ToolResultStore` through `ToolRuntime` where session/call IDs are available, or for this slice write a workspace-local diagnostic artifact under `.embedagent/memory/command-output/` with sanitized filenames. Prefer reusing `ToolResultStore` if the call path can pass session/call IDs cleanly.

At minimum, `build_command_observation` must include `full_output_ref` when stdout or stderr is truncated:

```python
if result.get("stdout_truncated") or result.get("stderr_truncated"):
    data["full_output_ref"] = self.materialize_command_output(
        tool_name, command_text, result.get("stdout") or "", result.get("stderr") or ""
    )
```

Implement `materialize_command_output` inside `ToolContext` with workspace-bound `.embedagent/memory/command-output`.

- [ ] **Step 6: Run truncation tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestCommandOutputDecoding -v
```

Expected: tests pass.

---

### Task 4: Remove Public `run_build` And Reframe C Workflow Packs

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_context_config.py`
- Modify: `tests/test_harness_contracts.py`
- Modify: `tests/test_workflow_package_manifest.py`
- Modify: `src/embedagent/tools/compile_ops.py`
- Modify: `src/embedagent/harness/packs.py`
- Modify: `src/embedagent/harness/tool_metadata.py`
- Modify: `src/embedagent/harness/context_reducers.py`

- [ ] **Step 1: Write failing public-contract tests**

Update `tests/test_tools_package.py`:

```python
def test_default_c_workflow_package_does_not_register_run_build(self):
    register_default_c_workflow_tools(self.rt, self.workspace)
    names = [s["function"]["name"] for s in self.rt.schemas()]
    self.assertNotIn("run_build", names)
    self.assertNotIn("configure_build_env", names)
    self.assertNotIn("list_compilers", names)
    self.assertIn("list_recipes", names)
    self.assertIn("run_recipe", names)
```

Replace `test_bare_runtime_rejects_c_workflow_build_tools` with:

```python
def test_runtime_rejects_removed_build_wrapper_tools(self):
    register_default_c_workflow_tools(self.rt, self.workspace)
    for tool_name in ("run_build", "configure_build_env", "list_compilers"):
        obs = self.rt.execute(tool_name, {})
        self.assertFalse(obs.success, tool_name)
```

Remove or rewrite all `TestBuildArtifactReporting` tests. Artifact scanning tied to `run_build` is deleted from the public contract.

- [ ] **Step 2: Update context reducer tests**

In `tests/test_context_config.py`, change assertions so C workflow reducers do not include `run_build`, `list_compilers`, or `configure_build_env`, and high-priority tools include only `run_recipe` and `report_quality_v2`.

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas tests/test_context_config.py::TestReducerRegistryTasks -v
```

Expected: failures show old build tools are still registered.

- [ ] **Step 4: Remove `run_build` definition**

In `src/embedagent/tools/compile_ops.py`, remove `_run_build`, `ARTIFACT_EXTENSIONS`, `_scan_build_artifacts`, and the `ToolDefinition(name="run_build", ...)`.

Remove default registration for `list_compilers` and `configure_build_env` in this slice. If a future design reintroduces toolchain discovery, it must arrive as a separate readiness/context capability, not as part of this public tool rewrite.

- [ ] **Step 5: Stop registering compile ops by default**

In `src/embedagent/harness/tool_registry.py`, remove:

```python
definitions.extend(compile_ops.build_tools(ctx))
```

and remove the `compile_ops` import if unused.

- [ ] **Step 6: Update workflow packs**

In `src/embedagent/harness/packs.py`:

```python
C_WORKFLOW_CORE_PACK = [
    "read_file",
    "list_dir",
    "glob_files",
    "grep_text",
    "edit_file",
    "write_file",
    "bash",
    "ask_user",
]

C_WORKFLOW_BUILD_LITE_PACK = C_WORKFLOW_CORE_PACK + [
    "list_recipes",
    "run_recipe",
    "task_status",
]

C_WORKFLOW_DEBUG_LITE_PACK = C_WORKFLOW_CORE_PACK + [
    "list_recipes",
    "run_recipe",
    "task_status",
    "record_failing_evidence",
]

C_WORKFLOW_VERIFY_PACK = [
    "read_file",
    "list_dir",
    "glob_files",
    "grep_text",
    "bash",
    "list_recipes",
    "run_recipe",
    "report_quality_v2",
    "task_status",
    "ask_user",
]
```

- [ ] **Step 7: Remove old metadata and reducers**

In `src/embedagent/harness/tool_metadata.py`, remove `list_compilers`, `configure_build_env`, and `run_build` entries unless they remain internal and not registered by default.

In `src/embedagent/harness/context_reducers.py`, remove reducer registration for those tools and remove `register_high_priority_tool("run_build")`.

- [ ] **Step 8: Run contract tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas tests/test_tools_package.py::TestToolRuntimeExecute tests/test_context_config.py::TestReducerRegistryTasks -v
```

Expected: tests pass after old assertions are updated.

---

### Task 5: Make Recipes Readiness-Aware And Refusal-Capable

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `src/embedagent/workspace_recipes.py`
- Modify: `src/embedagent/tools/recipe_ops.py`

- [ ] **Step 1: Add failing recipe readiness tests**

In `TestWorkspaceRecipes`, add:

```python
def test_list_recipes_marks_cmake_build_not_ready_without_build_dir(self):
    with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
        handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
    from embedagent.workspace_recipes import list_workspace_recipes

    payload = list_workspace_recipes(self.workspace)
    build = [item for item in payload["items"] if item["id"] == "cmake.build.default"][0]
    self.assertFalse(build["ready"])
    self.assertEqual(build["confidence"], "medium")
    self.assertIn("cmake.configure.default", build["requires"])
    self.assertIn("suggested_next_step", build)

def test_project_recipe_is_ready_by_default(self):
    os.makedirs(os.path.join(self.workspace, ".embedagent"))
    with open(os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"), "w", encoding="utf-8") as handle:
        handle.write('[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","command":"echo ok","cwd":"."}]')
    from embedagent.workspace_recipes import list_workspace_recipes

    payload = list_workspace_recipes(self.workspace)
    recipe = [item for item in payload["items"] if item["id"] == "custom.build"][0]
    self.assertTrue(recipe["ready"])
    self.assertEqual(recipe["confidence"], "high")
```

- [ ] **Step 2: Add failing run_recipe refusal tests**

Add:

```python
def test_run_recipe_refuses_cmake_build_without_configure(self):
    with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
        handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
    runtime = ToolRuntime(self.workspace)
    register_default_c_workflow_tools(runtime, self.workspace)

    obs = runtime.execute("run_recipe", {"recipe_id": "cmake.build.default"})

    self.assertFalse(obs.success)
    self.assertEqual(obs.data["error_kind"], "recipe_prerequisite_missing")
    self.assertFalse(obs.data["retryable"])
    self.assertIn("cmake.configure.default", obs.data["requires"])
```

Add:

```python
def test_run_recipe_unknown_id_returns_available_alternatives(self):
    runtime = ToolRuntime(self.workspace)
    register_default_c_workflow_tools(runtime, self.workspace)
    obs = runtime.execute("run_recipe", {"recipe_id": "missing"})
    self.assertFalse(obs.success)
    self.assertEqual(obs.data["error_kind"], "recipe_not_found")
    self.assertFalse(obs.data["retryable"])
    self.assertIn("available_recipes", obs.data)
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestWorkspaceRecipes -v
```

Expected: readiness fields and refusal behavior are missing.

- [ ] **Step 4: Add recipe readiness normalization**

In `src/embedagent/workspace_recipes.py`, extend `_normalize_recipe_item` to set defaults:

```python
normalized["ready"] = bool(item.get("ready", True))
normalized["confidence"] = str(item.get("confidence") or "high")
normalized["requires"] = list(item.get("requires") or [])
normalized["reason"] = str(item.get("reason") or "")
normalized["suggested_next_step"] = str(item.get("suggested_next_step") or "")
normalized["last_success"] = str(item.get("last_success") or item.get("last_success_at") or "")
normalized["failure_count"] = int(item.get("failure_count") or 0)
normalized["last_failure_summary"] = str(item.get("last_failure_summary") or "")
```

For detected recipes, compute readiness before normalization:

- CMake configure: ready true, confidence medium, suggested next step `Run this configure recipe before build/test.`
- CMake build/test: ready only if `build` or selected profile build dir exists; requires `cmake.configure.default` when absent.
- Make build: ready true, confidence medium.
- Make test: ready false or low confidence unless the Makefile contains a `test:` target.
- Ninja build: ready true if `build.ninja` exists.
- Ninja test: ready false or low confidence unless the ninja file includes a test rule/target.

- [ ] **Step 5: Make resolve return structured failures**

Add a small exception type:

```python
class RecipeResolutionError(ValueError):
    def __init__(self, message: str, payload: Dict[str, Any]) -> None:
        super(RecipeResolutionError, self).__init__(message)
        self.payload = payload
```

Raise it for missing recipe, missing command, and not-ready recipe. Include `error_kind`, `retryable`, `available_recipes`, `requires`, `reason`, and `suggested_next_step`.

- [ ] **Step 6: Catch recipe resolution failures in `recipe_ops`**

In `_run_recipe`, catch `RecipeResolutionError` and return:

```python
return Observation(
    tool_name="run_recipe",
    success=False,
    error=str(exc),
    data=dict(exc.payload),
)
```

Do not spawn a subprocess for not-ready recipes.

- [ ] **Step 7: Run recipe tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestWorkspaceRecipes -v
```

Expected: recipe tests pass.

---

### Task 6: Align Runtime Contract And Manifest With Bash

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_workflow_package_manifest.py`
- Modify: `scripts/offline-runtime-contract.json`
- Modify: `src/embedagent/tools/_base.py`
- Modify: `src/embedagent/harness/package_manifest.py` if manifest derives old pack contents incorrectly

- [ ] **Step 1: Update runtime contract tests**

In `TestRuntimeContractAlignment`, update expectations so `MANAGED_RUNTIME_TOOL_KEYS` includes `bash` or a `git_bash` key, and command names classify as that key:

```python
self.assertEqual(classified["bash"], "bash")
self.assertEqual(classified["bash.exe"], "bash")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestRuntimeContractAlignment -v
```

Expected: Bash is missing from the contract and command classifier.

- [ ] **Step 3: Add Bash managed runtime discovery**

In `src/embedagent/tools/_base.py`:

```python
MANAGED_RUNTIME_TOOL_KEYS = ("python", "git", "bash", "rg", "ctags", "llvm")
```

Add direct command mappings:

```python
"bash": "bash",
"bash.exe": "bash",
"sh": "bash",
"sh.exe": "bash",
```

Add `_managed_tool_candidates("bash")` candidates:

```python
bin/git/bin/bash.exe
bin/git/usr/bin/bash.exe
bin/git/bin/sh.exe
bin/git/usr/bin/sh.exe
```

Also check workspace equivalents under `bin/git/...`.

Include Bash in `runtime_environment_snapshot` as `bash_exe` and in `bundled_tools_ready`.

- [ ] **Step 4: Update offline contract**

In `scripts/offline-runtime-contract.json`, add a required tool:

```json
{
  "id": "bash",
  "component": "mingit_portable",
  "category": "shell",
  "alternatives": [
    { "paths": ["bin/git/bin/bash.exe"] },
    { "paths": ["bin/git/usr/bin/bash.exe"] },
    { "paths": ["bin/git/bin/sh.exe"] },
    { "paths": ["bin/git/usr/bin/sh.exe"] }
  ],
  "command_names": ["bash", "bash.exe", "sh", "sh.exe"],
  "dynamic_check": ["--version"],
  "notes": "Used by the model-facing bash primitive for offline command execution."
}
```

- [ ] **Step 5: Update workflow manifest expectations**

Run:

```bash
uv run pytest tests/test_workflow_package_manifest.py -v
```

If it fails because pack declarations still contain old build helpers, update manifest derivation to reflect the new packs: include `bash`; exclude `run_build`, `list_compilers`, and `configure_build_env`.

- [ ] **Step 6: Run runtime/manifest tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestRuntimeContractAlignment tests/test_workflow_package_manifest.py -v
```

Expected: tests pass.

---

### Task 7: Update Context, Frontend Labels, And Permission Vocabulary

**Files:**
- Modify: `src/embedagent/context.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Modify: related frontend tests if they assert labels

- [ ] **Step 1: Write or update context tests**

In `tests/test_context_config.py`, assert bare reducer has `bash` and not `run_command`:

```python
self.assertIn("bash", self.registry._reducers)
self.assertNotIn("run_command", self.registry._reducers)
```

Add a reducer smoke assertion:

```python
def test_reduce_bash_command_result(self):
    policy = self._make_policy()
    data = {"command": "echo ok", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
    result = self.registry.reduce_tool_data("bash", data, detailed=True, policy=policy)
    self.assertEqual(result["exit_code"], 0)
    self.assertIn("stdout_preview", result)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_context_config.py::TestReducerRegistryTasks -v
```

Expected: reducer still uses `run_command`.

- [ ] **Step 3: Update reducer registry**

In `src/embedagent/context.py`, replace:

```python
"run_command": self._reduce_command,
```

with:

```python
"bash": self._reduce_command,
```

Extend `_reduce_command` to copy decode metadata and `full_output_ref`.

- [ ] **Step 4: Update frontend labels**

In `src/embedagent/frontend/gui/webapp/src/store.js`, replace `run_command` label with `bash`:

```javascript
bash: (a) => `Bash: ${a.command || ""}`,
```

In interaction/timeline helpers, keep `bash` as command category. Remove `run_command` special handling unless tests still require reading historical transcripts; this project does not need public compatibility, so prefer deletion.

- [ ] **Step 5: Run context and frontend tests**

Run:

```bash
uv run pytest tests/test_context_config.py -v
```

If frontend JavaScript tests are configured locally, also run the existing frontend test command used by the repo; otherwise record that frontend JS tests were not run.

---

### Task 8: Synchronize Durable Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/mode-schema.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/agent-harness-v2.md`

- [ ] **Step 1: Search old vocabulary**

Run:

```bash
rg -n "run_build|run_command|list_compilers|configure_build_env" README.md AGENTS.md docs src tests
```

Expected before docs update: active docs still mention old public tools.

- [ ] **Step 2: Update official vocabulary**

Apply these durable wording changes:

- Core primitive command tool is `bash`.
- `run_build` is removed from the public model-visible contract.
- C/C++ build/test commands run through `bash` unless a ready recipe is available.
- `list_recipes` and `run_recipe` are workflow package tools with readiness metadata.
- `list_compilers` and `configure_build_env` are not default model-visible workflow tools.
- Command output is bytes-first decoded with Windows code page fallback.
- Offline runtime contract includes bundled Bash.

- [ ] **Step 3: Keep archive references archived**

Do not rewrite `docs/archive/` unless a test explicitly checks it. Historical references may keep old vocabulary.

- [ ] **Step 4: Verify active docs**

Run:

```bash
rg -n "run_build|run_command|list_compilers|configure_build_env" README.md AGENTS.md docs --glob "!docs/archive/**" --glob "!docs/superpowers/**"
```

Expected: no active source-of-truth document describes these as public/default model-visible tools. `design-change-log.md` may mention removal as a dated change.

---

### Task 9: Final Verification And Cleanup

**Files:**
- Inspect: all touched files

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_tools_package.py tests/test_context_config.py tests/test_workflow_package_manifest.py -v
```

Expected: pass.

- [ ] **Step 2: Run fast test subset**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run --locked python scripts/lint.py
```

Expected: pass.

- [ ] **Step 4: Search removed public tool**

Run:

```bash
rg -n "run_build|run_command" src tests README.md AGENTS.md docs --glob "!docs/archive/**" --glob "!docs/superpowers/**"
```

Expected: no live public-contract references. Any remaining references must be internal migration notes or deleted.

- [ ] **Step 5: Review git diff**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; only intentional files changed.
