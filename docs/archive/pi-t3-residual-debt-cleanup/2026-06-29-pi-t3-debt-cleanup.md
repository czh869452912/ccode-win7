# Pi/T3 Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the remaining Pi/T3 architecture debt around search failures, backend-owned slash commands, usage-aware compaction, and stale compaction strategy exports.

**Architecture:** Keep Agent Core decisions inside existing reducer/service boundaries: tools return structured observations, the loop guard only stops genuine no-progress behavior, session bootstrap carries safe capability read models, and context usage is a focused read model consumed by `ContextManager`. Keep the GUI composer as a T3-style presentation/search layer that consumes backend command capabilities rather than owning product slash command truth.

**Tech Stack:** Python 3.8, pytest, existing `ToolRuntime`/`QueryEngine`/`InProcessAdapter` services, React/Vite webapp helper tests through `npm test`, no new runtime dependencies.

---

## Scope Notes

This plan intentionally spans six coupled slices because each removes one part of the same architectural divergence. The slices should be implemented in order and committed independently. Do not introduce compatibility shims for obsolete session logs or frontend command lists.

Keep these constraints throughout:

- Use Python 3.8 syntax only.
- Do not add dependencies to `pyproject.toml`.
- Do not manually edit `uv.lock`.
- Do not commit `config/config.json`.
- If webapp source changes, run `npm test` and `npm run build` from `src/embedagent/frontend/gui/webapp` and include generated static GUI assets when the build changes them.

## File Structure

Expected files to create:

- `src/embedagent/context_usage.py` - focused usage-aware context token read model.
- `src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js` - GUI normalization of backend command descriptors into composer command objects.
- `src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs` - frontend command capability tests.

Expected files to modify:

- `src/embedagent/tools/_base.py` - structured `ToolError`, search traversal helpers, and managed ripgrep helper use.
- `src/embedagent/tools/discovery_ops.py` - `grep_text` file roots, regex/literal behavior, diagnostics.
- `src/embedagent/tools/runtime.py` - tool error metadata conversion and catalog enrichment for failures.
- `src/embedagent/constants.py` - shared skip policy for agent-owned memory.
- `src/embedagent/services/workspace_file_service.py` - consume shared skip helper instead of raw name-only skip where needed.
- `src/embedagent/guard.py` - no behavior change expected; add tests only unless diagnostics expose a gap.
- `src/embedagent/session.py` - persist assistant usage in message metadata.
- `src/embedagent/session_restore.py` - restore assistant usage metadata.
- `src/embedagent/query_engine.py` - transcript message payload carries assistant usage metadata.
- `src/embedagent/context.py` - consume usage-aware context read model for budgets and auto-compact gating.
- `src/embedagent/session_projector.py` and `src/embedagent/frontend/gui/backend/protocol_payloads.py` - expose context usage diagnostics in snapshots.
- `src/embedagent/session_bootstrap_service.py`, `src/embedagent/inprocess_adapter.py`, `src/embedagent/core/adapter.py`, `src/embedagent/frontend/gui/backend/routes_sessions.py` - add safe command capabilities to session bootstrap.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js` - pass bootstrap capabilities through activation.
- `src/embedagent/frontend/gui/webapp/src/state-helpers.js` and `src/embedagent/frontend/gui/webapp/src/store.js` - store session command capabilities.
- `src/embedagent/frontend/gui/webapp/src/App.jsx` - use backend command capabilities for composer slash menu, not static hints/workbench commands.
- `src/embedagent/strategies/context_compaction_engine.py`, `src/embedagent/strategies/llm_retry_wrapper.py`, `src/embedagent/strategies/__init__.py` - remove legacy wrapper-level compaction.
- Tests listed in each task.

---

### Task 1: Structured Tool Errors And `grep_text` Contract

**Files:**
- Modify: `src/embedagent/tools/_base.py`
- Modify: `src/embedagent/tools/discovery_ops.py`
- Modify: `src/embedagent/tools/runtime.py`
- Test: `tests/test_tools_package.py`
- Test: `tests/test_harness_guard_safety.py`

- [ ] **Step 1: Write failing `grep_text` tests for file roots, regex, literal search, and diagnostic failures**

Add these tests to `tests/test_tools_package.py` inside `TestToolRuntimeExecute` after `test_grep_text_continues_with_replacement_decoded_files`:

```python
    def test_grep_text_accepts_single_file_path(self):
        with open(os.path.join(self.workspace, "hal_uart.h"), "w", encoding="utf-8") as handle:
            handle.write("class HAL_UART {\npublic:\n  void init();\n};\n")

        obs = self.rt.execute(
            "grep_text",
            {"pattern": "class HAL_UART", "path": "hal_uart.h"},
        )

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["returned_count"], 1)
        self.assertEqual(obs.data["total_count"], 1)
        self.assertIn("hal_uart.h:1:class HAL_UART", obs.data["preview"][0])

    def test_grep_text_supports_regex_and_literal_mode(self):
        with open(os.path.join(self.workspace, "hal_uart.h"), "w", encoding="utf-8") as handle:
            handle.write("class HAL_UART {\npublic:\n  void init();\n};\n")

        regex_obs = self.rt.execute(
            "grep_text",
            {"pattern": "HAL_UART|public:|void ", "path": "hal_uart.h"},
        )
        literal_obs = self.rt.execute(
            "grep_text",
            {"pattern": "HAL_UART|public:", "path": "hal_uart.h", "literal": True},
        )

        self.assertTrue(regex_obs.success)
        self.assertEqual(regex_obs.data["returned_count"], 3)
        self.assertTrue(literal_obs.success)
        self.assertEqual(literal_obs.data["returned_count"], 0)
        self.assertEqual(literal_obs.data["total_count"], 0)

    def test_grep_text_invalid_regex_is_diagnostic_failure_with_catalog_metadata(self):
        with open(os.path.join(self.workspace, "demo.c"), "w", encoding="utf-8") as handle:
            handle.write("int main(void) { return 0; }\n")

        obs = self.rt.execute("grep_text", {"pattern": "[", "path": "."})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "invalid_pattern")
        self.assertEqual(obs.data["outcome_class"], "diagnostic_failure")
        self.assertFalse(obs.data["retryable"])
        self.assertEqual(obs.data["tool_label"], "Grep Text")
        self.assertEqual(obs.data["permission_category"], "read")

    def test_grep_text_missing_path_is_diagnostic_failure(self):
        obs = self.rt.execute("grep_text", {"pattern": "needle", "path": "missing"})

        self.assertFalse(obs.success)
        self.assertEqual(obs.data["error_kind"], "path_not_found")
        self.assertEqual(obs.data["outcome_class"], "diagnostic_failure")
        self.assertFalse(obs.data["retryable"])
```

- [ ] **Step 2: Write failing guard test showing diagnostic grep failures do not hard-stop**

Add this test to `tests/test_harness_guard_safety.py` after `test_diagnostic_command_failures_do_not_hard_stop`:

```python
    def test_diagnostic_grep_failures_do_not_hard_stop(self):
        action = Action(name="grep_text", arguments={"path": "missing", "pattern": "x"}, call_id="c1")
        fail_obs = Observation(
            tool_name="grep_text",
            success=False,
            error="路径不存在：missing",
            data={
                "error_kind": "path_not_found",
                "outcome_class": "diagnostic_failure",
                "retryable": False,
            },
        )

        self.guard.record(action, fail_obs)
        self.guard.record(action, fail_obs)

        self.assertFalse(self.guard.should_stop())
        self.assertFalse(self.guard.should_block(action))
```

- [ ] **Step 3: Run the new backend tests and confirm the expected failures**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_accepts_single_file_path tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_supports_regex_and_literal_mode tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_invalid_regex_is_diagnostic_failure_with_catalog_metadata tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_missing_path_is_diagnostic_failure tests/test_harness_guard_safety.py::TestLoopGuard::test_diagnostic_grep_failures_do_not_hard_stop -v
```

Expected: at least the file path, regex, and diagnostic metadata tests fail before implementation.

- [ ] **Step 4: Extend `ToolError` with structured metadata**

In `src/embedagent/tools/_base.py`, replace the empty `ToolError` class with a Python 3.8-compatible class:

```python
class ToolError(Exception):
    def __init__(
        self,
        message: str,
        error_kind: str = "tool_error",
        retryable: bool = True,
        outcome_class: str = "",
        suggested_next_step: str = "",
    ) -> None:
        super(ToolError, self).__init__(message)
        self.error_kind = str(error_kind or "tool_error")
        self.retryable = bool(retryable)
        self.outcome_class = str(outcome_class or "")
        self.suggested_next_step = str(suggested_next_step or "")

    def to_observation_data(self) -> Dict[str, Any]:
        data = {
            "error_kind": self.error_kind,
            "retryable": self.retryable,
        }
        if self.outcome_class:
            data["outcome_class"] = self.outcome_class
        if self.suggested_next_step:
            data["suggested_next_step"] = self.suggested_next_step
        return data
```

Keep existing `raise ToolError("...")` call sites valid by preserving defaults.

- [ ] **Step 5: Add search-root and regex helpers**

In `src/embedagent/tools/discovery_ops.py`, import `re` and add helpers near the top:

```python
import re
```

```python
def _diagnostic_tool_error(message: str, error_kind: str, suggested_next_step: str = "") -> ToolError:
    return ToolError(
        message,
        error_kind=error_kind,
        retryable=False,
        outcome_class="diagnostic_failure",
        suggested_next_step=suggested_next_step,
    )


def _resolve_search_root(ctx, raw_path: str) -> str:
    try:
        return ctx.resolve_path(raw_path)
    except ToolError as exc:
        text = str(exc)
        if "路径不存在" in text:
            raise _diagnostic_tool_error(
                text,
                "path_not_found",
                "Use list_dir or glob_files to find the correct search root.",
            )
        if "路径超出当前工作区" in text:
            raise _diagnostic_tool_error(
                text,
                "path_outside_workspace",
                "Search only paths inside the current workspace.",
            )
        raise


def _compile_pattern(pattern: str, literal: bool):
    if literal:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise _diagnostic_tool_error(
            "搜索模式不是有效正则表达式：%s" % exc,
            "invalid_pattern",
            "Set literal=true for fixed-string search or provide a valid regular expression.",
        )


def _line_matches(line_text: str, lowered_pattern: str, compiled_pattern, literal: bool) -> bool:
    if not lowered_pattern:
        return True
    if literal:
        return lowered_pattern in line_text.lower()
    return compiled_pattern.search(line_text) is not None
```

- [ ] **Step 6: Update `grep_text` to accept files and regex/literal mode**

In `_grep_text()` in `src/embedagent/tools/discovery_ops.py`, replace:

```python
        path = ctx.resolve_directory(str(arguments.get("path") or "."))
```

with:

```python
        path = _resolve_search_root(ctx, str(arguments.get("path") or "."))
```

Then add:

```python
        literal = bool(arguments.get("literal", False))
        compiled_pattern = _compile_pattern(pattern, literal)
```

Change the line match condition from substring-only:

```python
                if lowered and lowered not in line_text.lower():
                    continue
```

to:

```python
                if not _line_matches(line_text, lowered, compiled_pattern, literal):
                    continue
```

Update the `grep_text` schema properties to include:

```python
                    "literal": {
                        "type": "boolean",
                        "description": "为 true 时按固定字符串搜索；默认为 false，按正则表达式搜索。",
                    },
```

- [ ] **Step 7: Enrich failed observations with structured error data and catalog metadata**

In `src/embedagent/tools/runtime.py`, add a private helper on `ToolRuntime` near `execute_with_interrupt()`:

```python
    def _enrich_observation(self, name: str, observation: Observation) -> Observation:
        observation.tool_name = name
        if isinstance(observation.data, dict):
            entry = self._catalog.get(name)
            if entry is not None:
                data = dict(observation.data)
                data.setdefault("tool_label", entry.presentation.user_label)
                data.setdefault("permission_category", entry.permission_category)
                data.setdefault(
                    "supports_diff_preview",
                    entry.presentation.supports_diff_preview,
                )
                data.setdefault("progress_renderer_key", entry.presentation.progress_renderer_key)
                data.setdefault("result_renderer_key", entry.presentation.result_renderer_key)
                data.setdefault(
                    "read_model_invalidations",
                    list(entry.context_policy.read_model_invalidations),
                )
                data.setdefault("source_type", entry.source_type)
                data.setdefault("source_id", entry.source_id)
                observation.data = data
        return observation
```

In `execute_with_interrupt()`, change the `ToolError` except block to:

```python
        except ToolError as exc:
            data = exc.to_observation_data() if hasattr(exc, "to_observation_data") else {
                "error_kind": "tool_error",
                "retryable": True,
            }
            return self._enrich_observation(
                name,
                Observation(tool_name=name, success=False, error=str(exc), data=data),
            )
```

Change the generic exception block to return `_enrich_observation(...)` too.

Replace the duplicated success enrichment block at the end of `execute_with_interrupt()` with:

```python
        return self._enrich_observation(name, observation)
```

- [ ] **Step 8: Run targeted tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_continues_with_replacement_decoded_files tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_accepts_single_file_path tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_supports_regex_and_literal_mode tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_invalid_regex_is_diagnostic_failure_with_catalog_metadata tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_missing_path_is_diagnostic_failure tests/test_harness_guard_safety.py -v
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit Task 1**

Run:

```bash
git add src/embedagent/tools/_base.py src/embedagent/tools/discovery_ops.py src/embedagent/tools/runtime.py tests/test_tools_package.py tests/test_harness_guard_safety.py
git commit -m "fix: classify grep diagnostics"
```

---

### Task 2: Skip Agent-Owned Memory During Workspace Search

**Files:**
- Modify: `src/embedagent/constants.py`
- Modify: `src/embedagent/tools/_base.py`
- Modify: `src/embedagent/services/workspace_file_service.py`
- Test: `tests/test_tools_package.py`

- [ ] **Step 1: Write failing search pollution test**

Add this test to `tests/test_tools_package.py` inside `TestToolRuntimeExecute` after the grep tests from Task 1:

```python
    def test_grep_text_skips_embedagent_memory_by_default(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent", "memory", "sessions", "s1"))
        with open(os.path.join(self.workspace, "src.txt"), "w", encoding="utf-8") as handle:
            handle.write("needle in source\n")
        with open(
            os.path.join(self.workspace, ".embedagent", "memory", "sessions", "s1", "transcript.jsonl"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write("needle in agent memory\n")

        obs = self.rt.execute("grep_text", {"pattern": "needle", "path": "."})

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["returned_count"], 1)
        self.assertIn("src.txt:1:needle in source", obs.data["preview"][0])
        self.assertNotIn(".embedagent/memory", "\n".join(obs.data["preview"]))
```

- [ ] **Step 2: Run the new test and confirm failure**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_skips_embedagent_memory_by_default -v
```

Expected: FAIL because `.embedagent/memory` is currently traversed.

- [ ] **Step 3: Add shared traversal skip helpers**

In `src/embedagent/constants.py`, replace the current constants with:

```python
"""Shared constants used across embedagent packages."""

from __future__ import annotations

SKIP_DIR_NAMES = frozenset({".git", ".hg", ".svn", "__pycache__"})
SKIP_RELATIVE_DIRS = frozenset({".embedagent/memory"})
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "cp936")


def normalize_relative_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip("/")


def should_skip_directory(name: str, relative_path: str = "") -> bool:
    if name in SKIP_DIR_NAMES:
        return True
    normalized = normalize_relative_path(relative_path)
    return normalized in SKIP_RELATIVE_DIRS
```

- [ ] **Step 4: Use shared skip helpers in `ToolContext.iter_files()`**

In `src/embedagent/tools/_base.py`, import the shared helper:

```python
from embedagent.constants import should_skip_directory
```

Replace the local `SKIP_DIR_NAMES` set usage inside `iter_files()`:

```python
            dir_names[:] = [name for name in dir_names if name not in SKIP_DIR_NAMES]
```

with:

```python
            visible_dirs = []
            for name in dir_names:
                absolute_dir = os.path.join(current_root, name)
                if should_skip_directory(name, self.relative_path(absolute_dir)):
                    continue
                visible_dirs.append(name)
            dir_names[:] = visible_dirs
```

Keep the existing local `SKIP_DIR_NAMES` definition only if other `_base.py` code still reads it; otherwise import `SKIP_DIR_NAMES` from constants for compatibility inside this module.

- [ ] **Step 5: Use shared skip helper in workspace file service**

In `src/embedagent/services/workspace_file_service.py`, update the import:

```python
from embedagent.constants import SKIP_DIR_NAMES, TEXT_ENCODINGS, should_skip_directory
```

For each directory skip check that has an absolute path available, replace `name in SKIP_DIR_NAMES` with:

```python
should_skip_directory(name, self.relative_path(absolute))
```

For `count_items()`, replace:

```python
            dir_names[:] = [name for name in dir_names if name not in SKIP_DIR_NAMES]
```

with:

```python
            visible_dirs = []
            for name in dir_names:
                absolute = os.path.join(current_root, name)
                if should_skip_directory(name, self.relative_path(absolute)):
                    continue
                visible_dirs.append(name)
            dir_names[:] = visible_dirs
```

- [ ] **Step 6: Run targeted traversal tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_skips_embedagent_memory_by_default tests/test_tools_package.py::TestToolRuntimeExecute::test_grep_text_continues_with_replacement_decoded_files -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add src/embedagent/constants.py src/embedagent/tools/_base.py src/embedagent/services/workspace_file_service.py tests/test_tools_package.py
git commit -m "fix: skip agent memory in search"
```

---

### Task 3: Backend-Owned Command Capabilities In Session Bootstrap

**Files:**
- Modify: `src/embedagent/session_bootstrap_service.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Test: `tests/test_local_resources.py`
- Test: `tests/test_capability_registry.py`

- [ ] **Step 1: Add a safe command capability projection helper**

In `src/embedagent/capabilities.py`, add this function after `command_capability_descriptors()`:

```python
def command_capability_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    commands = []
    for item in list((snapshot or {}).get("descriptors") or []):
        if not isinstance(item, dict) or item.get("kind") != "command":
            continue
        metadata = dict(item.get("metadata") or {})
        usage = str(metadata.get("usage") or "").strip()
        name = _clean_text(item.get("name"))
        if not name or not usage:
            continue
        commands.append(
            {
                "name": name,
                "usage": usage,
                "summary": str(metadata.get("summary") or ""),
                "source_type": _clean_text(item.get("source_type"), "builtin"),
                "source_id": _clean_text(item.get("source_id"), "slash_commands"),
                "active": bool(item.get("active")),
            }
        )
    commands.sort(key=lambda item: item["usage"])
    return {"commands": commands}
```

- [ ] **Step 2: Write command projection test**

Add this test to `tests/test_capability_registry.py` after `test_resource_command_specs_project_visible_skills_and_prompts`:

```python
def test_command_capability_payload_projects_safe_command_menu_items():
    from embedagent.capabilities import command_capability_payload

    descriptors = command_capability_descriptors(
        SlashCommandRegistry(),
        extra_specs=resource_command_specs(
            {
                "skills": [
                    {
                        "name": "code-review",
                        "description": "Review local C changes.",
                        "path": ".embedagent/skills/review/SKILL.md",
                        "prompt_visible": True,
                    }
                ],
                "prompts": [{"name": "triage", "path": ".embedagent/prompts/triage.md"}],
            }
        ),
    )
    registry = CapabilityRegistry(descriptors)

    payload = command_capability_payload(registry.snapshot().to_dict())
    usages = [item["usage"] for item in payload["commands"]]

    assert "/help" in usages
    assert "/resources reload" in usages
    assert "/skill:code-review [args]" in usages
    assert "/prompt:triage [args]" in usages
    assert all("api_key" not in json.dumps(item) for item in payload["commands"])
```

- [ ] **Step 3: Run command projection test**

Run:

```bash
uv run pytest tests/test_capability_registry.py::test_command_capability_payload_projects_safe_command_menu_items -v
```

Expected: FAIL until the helper is imported/implemented correctly.

- [ ] **Step 4: Extend `SessionBootstrapService` with capability loader**

Modify `src/embedagent/session_bootstrap_service.py` constructor:

```python
        capability_loader: Callable[[str], Dict[str, Any]] = None,
```

Store it:

```python
        self._capability_loader = capability_loader
```

In `build()`, include:

```python
            "capabilities": (
                self._capability_loader(safe_session_id)
                if callable(self._capability_loader)
                else {}
            ),
```

- [ ] **Step 5: Wire capabilities from `InProcessAdapter`**

In `src/embedagent/inprocess_adapter.py`, import:

```python
from embedagent.capabilities import command_capability_payload
```

When constructing `SessionBootstrapService`, add:

```python
            capability_loader=self.get_session_capabilities,
```

Add method near `capability_snapshot()`:

```python
    def get_session_capabilities(self, session_id: str = "") -> Dict[str, Any]:
        del session_id
        self._ensure_extension_tools_registered(reason="capabilities")
        return command_capability_payload(self.capability_snapshot())
```

- [ ] **Step 6: Pass capabilities through core adapter and GUI route**

In `src/embedagent/core/adapter.py`, `get_session_bootstrap()` already copies the adapter payload. No shape conversion is needed if the payload is a dict, but ensure it does not drop `"capabilities"`.

In `src/embedagent/frontend/gui/backend/routes_sessions.py`, add to the bootstrap response:

```python
            "capabilities": serialize_session_capabilities(payload.get("capabilities")),
```

In `src/embedagent/frontend/gui/backend/protocol_payloads.py`, add:

```python
def serialize_session_capabilities(payload: Any) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    commands = []
    for item in list(data.get("commands") or []):
        if not isinstance(item, dict):
            continue
        usage = str(item.get("usage") or "").strip()
        name = str(item.get("name") or "").strip()
        if not usage or not name:
            continue
        commands.append(
            {
                "name": name,
                "usage": usage,
                "summary": str(item.get("summary") or ""),
                "source_type": str(item.get("source_type") or ""),
                "source_id": str(item.get("source_id") or ""),
                "active": bool(item.get("active")),
            }
        )
    return {"commands": commands}
```

Import this function in `routes_sessions.py`.

- [ ] **Step 7: Add integration test for dynamic resource commands in bootstrap**

Add this test to `tests/test_local_resources.py` inside `TestLocalResources`:

```python
    def test_session_bootstrap_includes_dynamic_resource_commands(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Review\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage\n",
        )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve=True),
        )
        snapshot = adapter.create_session(mode="explore")
        session_id = snapshot["session_id"]
        adapter.reload_resources(session_id=session_id, reason="test")

        bootstrap = adapter.get_session_bootstrap(session_id)
        commands = bootstrap["capabilities"]["commands"]
        usages = [item["usage"] for item in commands]

        self.assertIn("/resources reload", usages)
        self.assertIn("/skill:code-review [args]", usages)
        self.assertIn("/prompt:triage [args]", usages)
```

- [ ] **Step 8: Run backend capability tests**

Run:

```bash
uv run pytest tests/test_capability_registry.py::test_command_capability_payload_projects_safe_command_menu_items tests/test_local_resources.py::TestLocalResources::test_session_bootstrap_includes_dynamic_resource_commands -v
```

Expected: PASS.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add src/embedagent/capabilities.py src/embedagent/session_bootstrap_service.py src/embedagent/inprocess_adapter.py src/embedagent/core/adapter.py src/embedagent/frontend/gui/backend/routes_sessions.py src/embedagent/frontend/gui/backend/protocol_payloads.py tests/test_capability_registry.py tests/test_local_resources.py
git commit -m "feat: expose command capabilities in bootstrap"
```

---

### Task 4: GUI Composer Uses Backend Command Capabilities

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js`
- Create: `src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Test: `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/composer-command-search.test.mjs`

- [ ] **Step 1: Create command capability normalization tests**

Create `src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  buildComposerCommandsFromCapabilities,
  normalizeCommandCapabilities,
} from "../src/session-runtime/command-capabilities.js";

export function runCommandCapabilitiesTests() {
  const capabilities = normalizeCommandCapabilities({
    commands: [
      {
        name: "resources",
        usage: "/resources reload",
        summary: "Reload resources",
        source_type: "builtin",
        source_id: "slash_commands",
        active: true,
      },
      {
        name: "skill:code-review",
        usage: "/skill:code-review [args]",
        summary: "Review local C changes",
        source_type: "builtin",
        source_id: "slash_commands",
        active: true,
      },
      {
        name: "hidden",
        usage: "/hidden",
        summary: "Inactive",
        active: false,
      },
      {
        name: "",
        usage: "/bad",
        active: true,
      },
    ],
  });

  assert.deepEqual(
    capabilities.commands.map((item) => item.usage),
    ["/resources reload", "/skill:code-review [args]"],
  );

  const commands = buildComposerCommandsFromCapabilities(capabilities);
  assert.deepEqual(
    commands.map((item) => item.slash),
    ["/resources reload", "/skill:code-review [args]"],
  );
  assert.equal(commands[0].id, "backend-command:resources");
  assert.equal(commands[0].group, "command");
  assert.equal(commands[0].label, "/resources reload");
  assert.deepEqual(commands[1].keywords, ["skill:code-review", "Review local C changes"]);
}
```

Register it in `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runCommandCapabilitiesTests } from "./command-capabilities.test.mjs";
```

Then call `runCommandCapabilitiesTests();` near the other composer/session-runtime tests.

- [ ] **Step 2: Run frontend tests and confirm missing module failure**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test -- command-capabilities
```

Expected: FAIL because `command-capabilities.js` does not exist.

- [ ] **Step 3: Implement command capability normalization module**

Create `src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js`:

```javascript
function text(value) {
  return String(value || "").trim();
}

export function normalizeCommandCapabilities(input = {}) {
  const commands = [];
  const seen = new Set();
  for (const item of Array.isArray(input?.commands) ? input.commands : []) {
    const name = text(item?.name);
    const usage = text(item?.usage);
    if (!name || !usage || item?.active === false) continue;
    const key = usage.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    commands.push({
      name,
      usage,
      summary: text(item?.summary),
      sourceType: text(item?.source_type || item?.sourceType),
      sourceId: text(item?.source_id || item?.sourceId),
      active: true,
    });
  }
  return { commands };
}

export function buildComposerCommandsFromCapabilities(capabilities = {}) {
  return normalizeCommandCapabilities(capabilities).commands.map((item) => ({
    id: `backend-command:${item.name}`,
    group: "command",
    label: item.usage,
    slash: item.usage,
    visibleWhen: "always",
    keywords: [item.name, item.summary].filter(Boolean),
  }));
}
```

- [ ] **Step 4: Pass bootstrap capabilities through session activation**

In `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`, import:

```javascript
import { normalizeCommandCapabilities } from "../session-runtime/command-capabilities.js";
```

In `deriveSessionActivation()`, add:

```javascript
    capabilities: normalizeCommandCapabilities(safePayload.capabilities || {}),
```

Update `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs` in the activation fixture to include:

```javascript
      capabilities: {
        commands: [
          {
            name: "resources",
            usage: "/resources reload",
            summary: "Reload resources",
            active: true,
          },
        ],
      },
```

Then assert:

```javascript
  assert.equal(activation.capabilities.commands[0].usage, "/resources reload");
```

- [ ] **Step 5: Store session command capabilities**

In `src/embedagent/frontend/gui/webapp/src/store.js`, add a top-level state field if one does not exist:

```javascript
  sessionCapabilities: { commands: [] },
```

In the `session_activated` reducer branch, set:

```javascript
      sessionCapabilities: action.capabilities || { commands: [] },
```

When resetting workspace/session state, reset to `{ commands: [] }`.

Update the dispatch in `src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js`:

```javascript
      capabilities: activation.capabilities,
```

- [ ] **Step 6: Use backend command capabilities in `App.jsx` composer**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, import:

```javascript
import { buildComposerCommandsFromCapabilities } from "./session-runtime/command-capabilities.js";
```

Remove the `SLASH_COMMAND_HINTS` constant.

Replace:

```javascript
  const composerCommands = paletteCommands;
```

with:

```javascript
  const composerCommands = useMemo(
    () => buildComposerCommandsFromCapabilities(state.sessionCapabilities || {}),
    [state.sessionCapabilities],
  );
```

In the `<Composer />` props, replace:

```jsx
              commandHints={SLASH_COMMAND_HINTS}
              commands={composerCommands}
```

with:

```jsx
              commandHints={[]}
              commands={composerCommands}
```

Keep `paletteCommands` for the command palette.

- [ ] **Step 7: Add source test preventing static slash truth from returning**

Add these assertions to the source-test area in `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` after `const composerSource = ...` or `const appSource = ...` if present:

```javascript
  const appSource = fs.readFileSync(webappSourcePath("App.jsx"), "utf8");
  assert.equal(appSource.includes("SLASH_COMMAND_HINTS"), false);
  assert.equal(appSource.includes("buildComposerCommandsFromCapabilities"), true);
  assert.equal(appSource.includes("const composerCommands = paletteCommands"), false);
```

- [ ] **Step 8: Run frontend tests**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 9: Build GUI assets**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm run build
```

Expected: build succeeds. Include generated static assets under `src/embedagent/frontend/gui/static/` if they changed.

- [ ] **Step 10: Commit Task 4**

Run from repo root:

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/static
git commit -m "feat: drive composer commands from capabilities"
```

---

### Task 5: Usage-Aware Context Accounting And Compaction Gating

**Files:**
- Create: `src/embedagent/context_usage.py`
- Modify: `src/embedagent/session.py`
- Modify: `src/embedagent/session_restore.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/context.py`
- Modify: `src/embedagent/session_projector.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Test: `tests/test_context_usage.py`
- Test: `tests/test_context_config.py`
- Test: `tests/test_session_restore.py`

- [ ] **Step 1: Create failing context usage tests**

Create `tests/test_context_usage.py`:

```python
from embedagent.context_usage import ContextUsageEstimator
from embedagent.session import AssistantReply, Session


def _session_with_usage():
    session = Session(session_id="sess-usage")
    session.add_user_message("hello")
    session.add_assistant_reply(
        AssistantReply(
            content="world",
            actions=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )
    )
    return session


def test_context_usage_prefers_valid_assistant_usage_and_estimates_trailing_messages():
    session = _session_with_usage()
    session.add_user_message("tail " * 20)

    estimate = ContextUsageEstimator(chars_per_token=4.0).estimate_session(
        session,
        context_window=1000,
        reserve_tokens=100,
    )

    assert estimate.tokens > 120
    assert estimate.usage_tokens == 120
    assert estimate.trailing_estimate_tokens > 0
    assert estimate.source == "provider_usage_plus_estimate"
    assert estimate.threshold_tokens == 900
    assert estimate.percent is not None


def test_context_usage_ignores_stale_usage_before_latest_compaction():
    session = _session_with_usage()
    session.add_compact_boundary("summary", 1, "build", {})

    estimate = ContextUsageEstimator(chars_per_token=4.0).estimate_session(
        session,
        context_window=1000,
        reserve_tokens=100,
    )

    assert estimate.tokens is None
    assert estimate.source == "unknown_after_compaction"
    assert estimate.percent is None


def test_context_usage_estimates_when_no_provider_usage_exists():
    session = Session(session_id="sess-estimate")
    session.add_user_message("hello " * 50)

    estimate = ContextUsageEstimator(chars_per_token=4.0).estimate_session(
        session,
        context_window=1000,
        reserve_tokens=100,
    )

    assert estimate.tokens > 0
    assert estimate.usage_tokens == 0
    assert estimate.source == "estimate"
```

- [ ] **Step 2: Run new tests and confirm missing module failure**

Run:

```bash
uv run pytest tests/test_context_usage.py -v
```

Expected: FAIL because `embedagent.context_usage` does not exist.

- [ ] **Step 3: Persist assistant usage into transcript message metadata**

In `src/embedagent/session.py`, in `add_assistant_reply()`, before appending `TranscriptMessage`, build metadata:

```python
        metadata = {}
        if isinstance(reply.usage, dict) and reply.usage:
            metadata["usage"] = {
                "prompt_tokens": int(reply.usage.get("prompt_tokens") or 0),
                "completion_tokens": int(reply.usage.get("completion_tokens") or 0),
                "total_tokens": int(reply.usage.get("total_tokens") or 0),
            }
```

Pass `metadata=metadata` to the assistant `TranscriptMessage`.

In `src/embedagent/session_restore.py`, when constructing `AssistantReply` for role `"assistant"`, pass:

```python
                usage=dict((payload.get("metadata") or {}).get("usage") or {}),
```

- [ ] **Step 4: Add transcript payload support for assistant usage metadata**

`QueryEngine._message_event_payload()` already includes `metadata`, so no extra event field is needed. Add a regression test to `tests/test_session_restore.py` near other message restore tests:

```python
    def test_restore_preserves_assistant_usage_metadata(self):
        events = [
            {
                "type": "message",
                "payload": {
                    "role": "user",
                    "content": "hello",
                    "message_id": "m-user",
                    "turn_id": "t-1",
                },
            },
            {
                "type": "step_started",
                "payload": {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
            },
            {
                "type": "message",
                "payload": {
                    "role": "assistant",
                    "content": "world",
                    "message_id": "m-assistant",
                    "parent_message_id": "m-user",
                    "turn_id": "t-1",
                    "step_id": "s-1",
                    "metadata": {
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 20,
                            "total_tokens": 120,
                        }
                    },
                },
            },
        ]

        result = self.restorer.restore(events)
        assistant = [m for m in result.session.messages if m.role == "assistant"][0]

        self.assertEqual(assistant.metadata["usage"]["total_tokens"], 120)
```

Adjust `self.restorer` to the local fixture name used in `tests/test_session_restore.py`; if the file uses direct `SessionRestorer()`, instantiate it directly.

- [ ] **Step 5: Implement `ContextUsageEstimator`**

Create `src/embedagent/context_usage.py`:

```python
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ContextUsageEstimate:
    tokens: Optional[int]
    source: str
    usage_tokens: int = 0
    trailing_estimate_tokens: int = 0
    last_usage_message_id: str = ""
    context_window: int = 0
    threshold_tokens: int = 0
    percent: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": self.tokens,
            "source": self.source,
            "usage_tokens": self.usage_tokens,
            "trailing_estimate_tokens": self.trailing_estimate_tokens,
            "last_usage_message_id": self.last_usage_message_id,
            "context_window": self.context_window,
            "threshold_tokens": self.threshold_tokens,
            "percent": self.percent,
        }


class ContextUsageEstimator(object):
    def __init__(self, chars_per_token: float = 3.0) -> None:
        self.chars_per_token = chars_per_token if chars_per_token > 0 else 1.0

    def estimate_session(
        self,
        session: Any,
        context_window: int = 0,
        reserve_tokens: int = 0,
    ) -> ContextUsageEstimate:
        messages = list(getattr(session, "messages", []) or [])
        threshold = max(0, int(context_window or 0) - int(reserve_tokens or 0))
        boundary = session.latest_compact_boundary() if hasattr(session, "latest_compact_boundary") else None
        first_allowed_index = self._first_allowed_usage_index(messages, boundary)
        latest_usage_index = -1
        latest_usage_tokens = 0
        latest_usage_message_id = ""

        for index in range(len(messages) - 1, -1, -1):
            if index < first_allowed_index:
                break
            message = messages[index]
            if getattr(message, "role", "") != "assistant":
                continue
            usage = dict(getattr(message, "metadata", {}) or {}).get("usage") or {}
            usage_tokens = self._usage_tokens(usage)
            if usage_tokens <= 0:
                continue
            latest_usage_index = index
            latest_usage_tokens = usage_tokens
            latest_usage_message_id = str(getattr(message, "message_id", "") or "")
            break

        if latest_usage_index < 0:
            if boundary is not None:
                return ContextUsageEstimate(
                    tokens=None,
                    source="unknown_after_compaction",
                    context_window=int(context_window or 0),
                    threshold_tokens=threshold,
                    percent=None,
                )
            estimated = self._estimate_messages(messages)
            return ContextUsageEstimate(
                tokens=estimated,
                source="estimate",
                usage_tokens=0,
                trailing_estimate_tokens=estimated,
                context_window=int(context_window or 0),
                threshold_tokens=threshold,
                percent=self._percent(estimated, context_window),
            )

        trailing = self._estimate_messages(messages[latest_usage_index + 1 :])
        total = latest_usage_tokens + trailing
        return ContextUsageEstimate(
            tokens=total,
            source="provider_usage" if trailing == 0 else "provider_usage_plus_estimate",
            usage_tokens=latest_usage_tokens,
            trailing_estimate_tokens=trailing,
            last_usage_message_id=latest_usage_message_id,
            context_window=int(context_window or 0),
            threshold_tokens=threshold,
            percent=self._percent(total, context_window),
        )

    def _usage_tokens(self, usage: Dict[str, Any]) -> int:
        total = int(usage.get("total_tokens") or 0)
        if total > 0:
            return total
        return int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)

    def _first_allowed_usage_index(self, messages: Any, boundary: Any) -> int:
        if boundary is None:
            return 0
        tail_id = str(getattr(boundary, "preserved_tail_message_id", "") or "")
        if tail_id:
            for index, message in enumerate(messages):
                if str(getattr(message, "message_id", "") or "") == tail_id:
                    return index + 1
        return len(messages)

    def _estimate_messages(self, messages: Any) -> int:
        chars = 0
        for message in list(messages or []):
            payload = message.to_api_dict() if hasattr(message, "to_api_dict") else message
            chars += len(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return int(math.ceil(float(chars) / self.chars_per_token))

    def _percent(self, tokens: int, context_window: int) -> Optional[float]:
        window = int(context_window or 0)
        if window <= 0:
            return None
        return (float(tokens) / float(window)) * 100.0
```

- [ ] **Step 6: Wire usage estimate into `ContextManager`**

In `src/embedagent/context.py`, import:

```python
from embedagent.context_usage import ContextUsageEstimator
```

In `ContextBuildResult`, add:

```python
    context_usage: Any = None
```

In `ContextManager.__init__()`, initialize:

```python
        self.context_usage_estimator = ContextUsageEstimator(self.config.estimated_chars_per_token)
```

When building a `ContextBuildResult`, compute:

```python
        usage_estimate = self.context_usage_estimator.estimate_session(
            session,
            context_window=policy.max_context_tokens,
            reserve_tokens=policy.reserve_output_tokens + policy.reserve_reasoning_tokens,
        )
```

Pass `context_usage=usage_estimate` to returned results.

In `_should_auto_compact()`, prefer `candidate.context_usage.tokens` when available:

```python
        usage = getattr(candidate, "context_usage", None)
        usage_tokens = getattr(usage, "tokens", None)
        if usage_tokens is None and getattr(usage, "source", "") == "unknown_after_compaction":
            return False
        input_tokens = int(usage_tokens if usage_tokens is not None else getattr(candidate.budget, "input_tokens", 0) or 0)
```

Keep existing fallback for tests and offline behavior.

- [ ] **Step 7: Add compaction gating regression test**

Add this test to `tests/test_context_config.py` after `test_near_full_window_uses_compact_policy_before_provider`:

```python
    def test_auto_compact_does_not_use_stale_usage_after_compaction(self):
        cfg = ContextConfig(auto_compact_threshold_ratio=0.01)
        cfg.mode_overrides["build"].update(
            {
                "max_context_tokens": 1000,
                "reserve_output_tokens": 0,
                "reserve_reasoning_tokens": 0,
                "max_recent_turns": 4,
            }
        )
        manager = ContextManager(config=cfg)
        session = Session(session_id="sess-stale-usage")
        session.add_user_message("before compact")
        session.add_assistant_reply(
            AssistantReply(
                content="large response",
                actions=[],
                finish_reason="stop",
                usage={"prompt_tokens": 950, "completion_tokens": 10, "total_tokens": 960},
            )
        )
        boundary = session.add_compact_boundary("summary", 1, "build", {})
        boundary.preserved_tail_message_id = session.messages[-1].message_id

        result = manager.build_messages(session, mode_name="build")

        self.assertNotIn("auto_compact_threshold", result.pipeline_steps)
        self.assertEqual(result.context_usage.source, "unknown_after_compaction")
```

- [ ] **Step 8: Attach context usage diagnostics to context analysis and snapshots**

In every `ContextBuildResult(...)` return site in `src/embedagent/context.py`, include the usage read model in `analysis` by replacing `analysis=self._analyze_context(session)` with:

```python
                    analysis=self._analysis_with_context_usage(session, usage_estimate),
```

Add this helper to `ContextManager` near `_analyze_context()`:

```python
    def _analysis_with_context_usage(self, session: Session, usage_estimate: Any) -> Dict[str, Any]:
        analysis = self._analyze_context(session)
        if hasattr(usage_estimate, "to_dict"):
            analysis["context_usage"] = usage_estimate.to_dict()
        return analysis
```

In `src/embedagent/session_projector.py`, derive `context_usage` from existing `context_analysis`:

```python
        context_analysis = dict(summary_payload.get("context_analysis") or {})
        context_usage = dict(context_analysis.get("context_usage") or {})
```

Use `context_analysis` for the existing `"context_analysis"` field and add:

```python
            "context_usage": context_usage,
```

In `src/embedagent/frontend/gui/backend/protocol_payloads.py`, add to `serialize_session_snapshot()`:

```python
        "context_usage": dict(read_value(snapshot, "context_usage", {}) or {}),
```

- [ ] **Step 9: Run context and restore tests**

Run:

```bash
uv run pytest tests/test_context_usage.py tests/test_context_config.py::TestContextConfig::test_auto_compact_does_not_use_stale_usage_after_compaction tests/test_session_restore.py::TestSessionRestore::test_restore_preserves_assistant_usage_metadata -v
```

Expected: PASS. Adjust the exact `TestSessionRestore` class/test selector to match the file's class names.

- [ ] **Step 10: Commit Task 5**

Run:

```bash
git add src/embedagent/context_usage.py src/embedagent/session.py src/embedagent/session_restore.py src/embedagent/query_engine.py src/embedagent/context.py src/embedagent/session_projector.py src/embedagent/frontend/gui/backend/protocol_payloads.py tests/test_context_usage.py tests/test_context_config.py tests/test_session_restore.py
git commit -m "feat: use provider usage for context accounting"
```

---

### Task 6: Remove Legacy Wrapper-Level Compaction Strategy

**Files:**
- Modify: `src/embedagent/strategies/__init__.py`
- Delete: `src/embedagent/strategies/context_compaction_engine.py`
- Modify: `src/embedagent/strategies/llm_retry_wrapper.py`
- Modify: `tests/test_strategies.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `docs/overall-solution-architecture.md` if it mentions the old strategy as active

- [ ] **Step 1: Write architecture boundary change first**

In `tests/test_current_architecture_boundaries.py`, replace `test_import_strategies()` with:

```python
    def test_import_strategies(self):
        from embedagent.strategies import LLMClientRetryWrapper

        assert LLMClientRetryWrapper is not None

    def test_legacy_context_compaction_strategy_removed(self):
        import embedagent.strategies as strategies

        assert not hasattr(strategies, "ContextCompactionEngine")
```

- [ ] **Step 2: Update strategy tests to stop preserving old compaction engine**

In `tests/test_strategies.py`, remove `TestContextCompactionEngine` and remove the import:

```python
from embedagent.strategies.context_compaction_engine import ContextCompactionEngine
```

In `TestLLMClientRetryWrapper`, remove `test_context_compaction_triggered` because wrapper-level compaction is no longer an active behavior.

Add this test:

```python
    def test_context_length_error_raises_without_wrapper_level_compaction(self):
        client = MagicMock()
        client.generate.side_effect = ModelClientError("context length exceeded")

        wrapper = self._make_wrapper(client=client, base_delay=0.0)

        with self.assertRaises(ModelClientError):
            wrapper.call_with_retry(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                stream=False,
            )
        client.generate.assert_called_once()
```

- [ ] **Step 3: Run tests and confirm failures**

Run:

```bash
uv run pytest tests/test_current_architecture_boundaries.py::TestPublicImports::test_legacy_context_compaction_strategy_removed tests/test_strategies.py::TestLLMClientRetryWrapper::test_context_length_error_raises_without_wrapper_level_compaction -v
```

Expected: FAIL until exports and wrapper are changed.

- [ ] **Step 4: Remove legacy compaction export and file**

In `src/embedagent/strategies/__init__.py`, remove:

```python
from embedagent.strategies.context_compaction_engine import ContextCompactionEngine
```

and remove `"ContextCompactionEngine"` from `__all__`.

Delete `src/embedagent/strategies/context_compaction_engine.py`.

- [ ] **Step 5: Remove wrapper-level compaction branch**

In `src/embedagent/strategies/llm_retry_wrapper.py`, remove the `compaction_engine` constructor argument and instance field:

```python
        compaction_engine: Optional[Any] = None,
```

Remove:

```python
        self.compaction_engine = compaction_engine
```

Remove `compact_retry_used = False` and the context-length compaction branch:

```python
                if (
                    self._is_context_length_error(error_text)
                    and not compact_retry_used
                    and self.compaction_engine is not None
                ):
                    _LOG.warning("LLM context-length error detected; compacting and retrying")
                    current_messages = self.compaction_engine.compact(current_messages)
                    compact_retry_used = True
                    continue
```

Keep `_is_context_length_error()` only if another active caller uses it. If no caller remains, remove `_COMPACT_RETRY_ERROR_MARKERS` and `_is_context_length_error()`.

Update test helper `_make_wrapper()` in `tests/test_strategies.py` to remove the `compaction_engine` parameter.

- [ ] **Step 6: Run strategy and architecture tests**

Run:

```bash
uv run pytest tests/test_strategies.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 6**

Run:

```bash
git add src/embedagent/strategies/__init__.py src/embedagent/strategies/llm_retry_wrapper.py tests/test_strategies.py tests/test_current_architecture_boundaries.py docs/overall-solution-architecture.md
git rm src/embedagent/strategies/context_compaction_engine.py
git commit -m "refactor: remove legacy compaction strategy"
```

---

## Final Verification

- [ ] **Step 1: Run backend targeted suite**

Run:

```bash
uv run pytest tests/test_tools_package.py tests/test_harness_guard_safety.py tests/test_context_usage.py tests/test_context_config.py tests/test_capability_registry.py tests/test_local_resources.py tests/test_strategies.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 2: Run architecture gate**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 3: Run fast suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [ ] **Step 4: Run lint**

Run:

```bash
uv run --locked python scripts/lint.py
```

Expected: PASS.

- [ ] **Step 5: Run GUI tests and build**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test
npm run build
```

Expected: both commands pass. Commit generated static assets if `npm run build` changes files under `src/embedagent/frontend/gui/static/`.

- [ ] **Step 6: Inspect final diff for accidental debt**

Run:

```bash
git status --short
rg -n "SLASH_COMMAND_HINTS|ContextCompactionEngine|timelineFromTurns|timelineFromEvents|SessionTimelineStore|MODE_REGISTRY|get_default_sanitizer|_DEFAULT_SANITIZER" src tests docs -g "*.py" -g "*.js" -g "*.jsx" -g "*.md"
```

Expected: no reintroduced stale symbols. `git status --short` should show only intended files or be clean after final commit.
