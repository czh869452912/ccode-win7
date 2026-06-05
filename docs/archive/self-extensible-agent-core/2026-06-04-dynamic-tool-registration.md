# Dynamic Tool Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build Slice 2 of the self-extensible Agent Core by making tools dynamically registerable through in-process extensions while preserving active-tool gating, catalog projection, and permission enforcement.

**Architecture:** `ToolRuntime` becomes a source-aware registry that can accept `ToolDefinition` objects after construction. `ExtensionManager` gains a registration hook that asks injected extensions for tools and registers them into the shared runtime. `QueryEngine` and `InProcessAdapter` synchronize registered tools before schema/catalog/execution boundaries, while `PermissionPolicy` classifies dynamic tools through catalog metadata.

**Tech Stack:** Python 3.8, dataclasses, existing `ToolDefinition`, `ToolRuntime`, `ExtensionManager`, `QueryEngine`, `InProcessAdapter`, `PermissionPolicy`, pytest.

---

## Scope

This plan implements Slice 2 from:

- `docs/superpowers/specs/2026-06-04-self-extensible-agent-core-design.md`
- `docs/superpowers/specs/2026-06-04-dynamic-tool-registration-design.md`

Included:

- dynamic `ToolRuntime.register_tool()`
- catalog source metadata (`source_type`, `source_id`)
- extension `register_tools` hook and diagnostics
- active-tool visibility through existing `allowed_tool_names`
- permission category lookup through runtime catalog metadata
- QueryEngine and InProcessAdapter registration synchronization
- source-of-truth documentation updates

Excluded:

- project-local `.embedagent/extensions/<name>/extension.py` loading
- `.embedagent/skills`, `.embedagent/prompts`, `.embedagent/recipes` discovery
- reload command/API
- custom command, shortcut, provider, renderer, or UI APIs
- built-in tool replacement by extensions

## File Structure

- `src/embedagent/tools/runtime.py`
  Owns the dynamic tool registry, source-aware catalog metadata, registration validation, and execution from the shared tool map.

- `src/embedagent/extensions.py`
  Owns the in-process extension registration event/result contract and diagnostic recording for extension tool registration failures.

- `src/embedagent/permissions.py`
  Owns official permission categories and the optional metadata category lookup used for dynamic tools.

- `src/embedagent/query_engine.py`
  Synchronizes extension tool registrations before agent turns/command turns and wires `PermissionPolicy` to the tool catalog.

- `src/embedagent/inprocess_adapter.py`
  Synchronizes extension tool registrations before frontend catalog projection and wires hosted `PermissionPolicy` to the tool catalog.

- `tests/test_dynamic_tool_registration.py`
  New focused tests for runtime registration, extension registration, QueryEngine execution, adapter catalog projection, and permission gating.

- `tests/test_permissions.py`
  Adds focused permission metadata lookup tests.

- Documentation:
  `README.md`, `AGENTS.md`, `docs/overall-solution-architecture.md`,
  `docs/tool-contracts.md`, `docs/permission-model.md`,
  `docs/frontend-protocol.md`, `docs/development-tracker.md`,
  `docs/design-change-log.md`.

---

### Task 1: Source-Aware ToolRuntime Registration

**Files:**
- Create: `tests/test_dynamic_tool_registration.py`
- Modify: `src/embedagent/tools/runtime.py`

- [x] **Step 1: Write failing runtime registration tests**

Create `tests/test_dynamic_tool_registration.py` with this content:

```python
from __future__ import annotations

import pytest

from embedagent.session import Observation
from embedagent.tools import ToolDefinition, ToolRuntime


def dynamic_tool_metadata(permission_category="read", read_only=True):
    return {
        "permission_category": permission_category,
        "mode_visibility": ["build"],
        "workflow_visibility": ["chat"],
        "user_label": "Dynamic Echo",
        "progress_renderer_key": "default",
        "result_renderer_key": "default",
        "supports_diff_preview": False,
        "context_reducer_key": "dynamic_echo",
        "read_only": read_only,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "tool",
        "context_priority": 50,
    }


def make_dynamic_tool(name="dynamic_echo", permission_category="read", read_only=True):
    def handler(arguments):
        return Observation(
            name,
            True,
            None,
            {"echo": str(arguments.get("message") or "")},
        )

    return ToolDefinition(
        name=name,
        description="Echo a message from a dynamically registered tool.",
        parameters={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        handler=handler,
        metadata=dynamic_tool_metadata(permission_category, read_only=read_only),
        read_only=read_only,
        concurrency_safe=True,
        interrupt_behavior="block",
        result_budget_policy="compact-preview",
        activity_kind="tool",
        context_priority=50,
    )


def schema_names(schemas):
    return [item["function"]["name"] for item in schemas]


def test_register_tool_adds_schema_catalog_and_execution_metadata(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    runtime.register_tool(
        make_dynamic_tool(),
        source_id="test.extension",
        source_type="extension",
    )

    schemas = runtime.schemas_for("build", workflow_state="chat", tool_names=["dynamic_echo"])
    entry = runtime.tool_catalog_entry("dynamic_echo")
    observation = runtime.execute("dynamic_echo", {"message": "hello"})

    assert schema_names(schemas) == ["dynamic_echo"]
    assert entry["name"] == "dynamic_echo"
    assert entry["permission_category"] == "read"
    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "test.extension"
    assert observation.success is True
    assert observation.data["echo"] == "hello"
    assert observation.data["tool_label"] == "Dynamic Echo"
    assert observation.data["permission_category"] == "read"


def test_register_tool_rejects_builtin_name_from_extension_source(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    tool = make_dynamic_tool(name="read_file")

    with pytest.raises(ValueError) as exc:
        runtime.register_tool(tool, source_id="test.extension", source_type="extension")

    assert "already registered" in str(exc.value)
    assert runtime.tool_catalog_entry("read_file")["source_type"] == "builtin"


def test_register_tool_is_idempotent_for_same_source(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    runtime.register_tool(
        make_dynamic_tool(),
        source_id="test.extension",
        source_type="extension",
    )
    runtime.register_tool(
        make_dynamic_tool(),
        source_id="test.extension",
        source_type="extension",
    )

    entries = [
        item
        for item in runtime.catalog_entries()
        if item.get("name") == "dynamic_echo"
    ]

    assert len(entries) == 1
    assert entries[0]["source_id"] == "test.extension"


def test_builtin_and_harness_tools_have_source_metadata(tmp_path):
    runtime = ToolRuntime(str(tmp_path))

    assert runtime.tool_catalog_entry("read_file")["source_type"] == "builtin"
    assert runtime.tool_catalog_entry("read_file")["source_id"] == "embedagent.core"
    assert runtime.tool_catalog_entry("run_recipe")["source_type"] == "harness"
    assert runtime.tool_catalog_entry("run_recipe")["source_id"] == "embedagent.harness"
```

- [x] **Step 2: Run runtime registration tests and verify they fail**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py::test_register_tool_adds_schema_catalog_and_execution_metadata tests/test_dynamic_tool_registration.py::test_register_tool_rejects_builtin_name_from_extension_source tests/test_dynamic_tool_registration.py::test_register_tool_is_idempotent_for_same_source tests/test_dynamic_tool_registration.py::test_builtin_and_harness_tools_have_source_metadata -v
```

Expected: FAIL because `ToolRuntime.register_tool()` and catalog source fields do not exist.

- [x] **Step 3: Add source fields and registration helpers**

Modify imports at the top of `src/embedagent/tools/runtime.py`:

```python
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
```

Change the `_base` import to include `ToolDefinition`:

```python
from embedagent.tools._base import ToolContext, ToolDefinition, ToolError
```

Add these constants after the harness imports:

```python
_VALID_TOOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REGISTERABLE_PERMISSION_CATEGORIES = set(
    ["read", "workspace_write", "shell_exec", "toolchain_exec", "git_write"]
)
_EXTENSION_REQUIRED_METADATA = (
    "permission_category",
    "mode_visibility",
    "workflow_visibility",
    "user_label",
    "read_only",
    "concurrency_safe",
    "interrupt_behavior",
    "result_budget_policy",
)
```

Add fields to `ToolCatalogEntry`:

```python
    source_type: str
    source_id: str
```

Add these fields to `ToolCatalogEntry.to_dict()`:

```python
            "source_type": self.source_type,
            "source_id": self.source_id,
```

- [x] **Step 4: Refactor ToolRuntime initialization through register_tool**

Replace the construction of `official_tools`, `harness_tools`, `_catalog`, and `_tools` inside `ToolRuntime.__init__` with this block:

```python
        self._mode_runtime = OfficialRuntimeModes()
        core_tools = (
            file_ops.build_tools(self._ctx)
            + shell_ops.build_tools(self._ctx)
            + git_ops.build_tools(self._ctx)
            + compile_ops.build_tools(self._ctx)
        )
        harness_tools = build_harness_tools(self._ctx)
        self._catalog = {}  # type: Dict[str, ToolCatalogEntry]
        self._tools = {}  # type: Dict[str, ToolDefinition]
        for tool in core_tools:
            self.register_tool(
                tool,
                source_id="embedagent.core",
                source_type="builtin",
            )
        for tool in harness_tools:
            if tool.name in self._tools:
                continue
            self.register_tool(
                tool,
                source_id="embedagent.harness",
                source_type="harness",
            )
```

- [x] **Step 5: Add register_tool and catalog entry creation**

Add these methods to `ToolRuntime` before `schemas()`:

```python
    def register_tool(
        self,
        tool: ToolDefinition,
        source_id: str = "",
        source_type: str = "extension",
        replace: bool = False,
    ) -> None:
        source_type = str(source_type or "extension").strip()
        source_id = str(source_id or source_type or "runtime").strip()
        if replace:
            raise ValueError("tool replacement is not enabled in this slice")
        self._validate_tool_definition(tool, source_type)
        existing = self._catalog.get(tool.name)
        if existing is not None:
            if existing.source_type == source_type and existing.source_id == source_id:
                pass
            else:
                raise ValueError("tool already registered: %s" % tool.name)
        metadata = self._metadata_for_tool(tool, source_type)
        tool.metadata = metadata
        tool.read_only = bool(metadata.get("read_only"))
        tool.concurrency_safe = bool(metadata.get("concurrency_safe"))
        tool.interrupt_behavior = str(metadata.get("interrupt_behavior") or "block")
        tool.result_budget_policy = str(metadata.get("result_budget_policy") or "default")
        tool.activity_kind = str(metadata.get("activity_kind") or "tool")
        tool.context_priority = int(metadata.get("context_priority") or 50)
        self._tools[tool.name] = tool
        self._catalog[tool.name] = self._catalog_entry_for_tool(
            tool,
            metadata,
            source_type=source_type,
            source_id=source_id,
        )

    def _validate_tool_definition(self, tool: ToolDefinition, source_type: str) -> None:
        if not isinstance(tool, ToolDefinition):
            raise ValueError("registered tool must be a ToolDefinition")
        name = str(getattr(tool, "name", "") or "").strip()
        if not name or not _VALID_TOOL_NAME_RE.match(name):
            raise ValueError("invalid tool name: %s" % (name or "<empty>"))
        if not callable(getattr(tool, "handler", None)):
            raise ValueError("tool %s is missing a callable handler" % name)
        if not isinstance(getattr(tool, "parameters", None), dict):
            raise ValueError("tool %s parameters must be an object schema" % name)
        if source_type == "extension":
            raw_metadata = dict(getattr(tool, "metadata", {}) or {})
            missing = []
            for key in _EXTENSION_REQUIRED_METADATA:
                if key not in raw_metadata:
                    missing.append(key)
            if missing:
                raise ValueError(
                    "tool %s missing metadata: %s" % (name, ", ".join(sorted(missing)))
                )

    def _metadata_for_tool(self, tool: ToolDefinition, source_type: str) -> Dict[str, Any]:
        raw_metadata = dict(getattr(tool, "metadata", {}) or {})
        metadata = self._build_default_metadata(tool.name)
        metadata.update(raw_metadata)
        category = str(metadata.get("permission_category") or "").strip()
        if category not in _REGISTERABLE_PERMISSION_CATEGORIES:
            raise ValueError(
                "tool %s has unsupported permission category: %s"
                % (tool.name, category or "<empty>")
            )
        return metadata

    def _catalog_entry_for_tool(
        self,
        tool: ToolDefinition,
        metadata: Dict[str, Any],
        source_type: str,
        source_id: str,
    ) -> ToolCatalogEntry:
        return ToolCatalogEntry(
            name=tool.name,
            description=tool.description,
            permission_category=str(metadata.get("permission_category") or "read"),
            mode_visibility=list(metadata.get("mode_visibility") or []),
            workflow_visibility=list(metadata.get("workflow_visibility") or []),
            user_label=str(metadata.get("user_label") or tool.name),
            progress_renderer_key=str(metadata.get("progress_renderer_key") or "default"),
            result_renderer_key=str(metadata.get("result_renderer_key") or "default"),
            supports_diff_preview=bool(metadata.get("supports_diff_preview")),
            context_reducer_key=str(metadata.get("context_reducer_key") or tool.name),
            read_only=bool(metadata.get("read_only")),
            concurrency_safe=bool(metadata.get("concurrency_safe")),
            interrupt_behavior=str(metadata.get("interrupt_behavior") or "block"),
            result_budget_policy=str(metadata.get("result_budget_policy") or "default"),
            activity_kind=str(metadata.get("activity_kind") or "tool"),
            context_priority=int(metadata.get("context_priority") or 50),
            source_type=source_type,
            source_id=source_id,
        )
```

- [x] **Step 6: Include source metadata in observations**

In `ToolRuntime.execute_with_interrupt`, inside the existing block that adds catalog metadata to `observation.data`, add:

```python
                data.setdefault("source_type", entry.source_type)
                data.setdefault("source_id", entry.source_id)
```

The final block should include `tool_label`, `permission_category`, renderer keys, and source keys.

- [x] **Step 7: Run runtime registration tests**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py::test_register_tool_adds_schema_catalog_and_execution_metadata tests/test_dynamic_tool_registration.py::test_register_tool_rejects_builtin_name_from_extension_source tests/test_dynamic_tool_registration.py::test_register_tool_is_idempotent_for_same_source tests/test_dynamic_tool_registration.py::test_builtin_and_harness_tools_have_source_metadata -v
```

Expected: PASS.

- [x] **Step 8: Run existing tool runtime tests**

Run:

```bash
uv run pytest tests/test_tools_package.py -v
```

Expected: PASS. Existing tool count remains 20 and legacy aliases stay absent.

- [x] **Step 9: Commit Task 1**

```bash
git add src/embedagent/tools/runtime.py tests/test_dynamic_tool_registration.py
git commit -m "feat: add dynamic tool runtime registry"
```

---

### Task 2: Permission Category Lookup For Dynamic Tools

**Files:**
- Modify: `src/embedagent/permissions.py`
- Modify: `tests/test_permissions.py`

- [x] **Step 1: Write failing metadata permission tests**

Append these tests to `tests/test_permissions.py` inside `TestPermissionPolicy`:

```python
    def test_metadata_category_lookup_controls_dynamic_tool_permission(self):
        policy = PermissionPolicy(
            auto_approve_all=False,
            workspace="D:\\workspace",
            category_lookup=lambda name: "shell_exec" if name == "dynamic_shell" else "",
        )

        decision = policy.evaluate(
            Action("dynamic_shell", {"command": "echo hello"}, "call-shell")
        )

        self.assertEqual(decision.outcome, "ask")
        self.assertEqual(decision.request.category, "shell_exec")
        self.assertEqual(decision.details.get("category"), "shell_exec")

    def test_set_category_lookup_supports_late_tool_runtime_binding(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")
        policy.set_category_lookup(
            lambda name: "workspace_write" if name == "dynamic_write" else ""
        )

        decision = policy.evaluate(
            Action("dynamic_write", {"path": "generated.txt"}, "call-write")
        )

        self.assertEqual(decision.outcome, "ask")
        self.assertEqual(decision.request.category, "workspace_write")
        self.assertEqual(decision.details.get("path"), "generated.txt")

    def test_invalid_metadata_category_falls_back_to_other(self):
        policy = PermissionPolicy(
            auto_approve_all=False,
            workspace="D:\\workspace",
            category_lookup=lambda name: "not_real",
        )

        decision = policy.evaluate(Action("dynamic_unknown", {}, "call-unknown"))

        self.assertEqual(decision.outcome, "allow")
        self.assertEqual(decision.details.get("category"), "other")
```

- [x] **Step 2: Run permission tests and verify they fail**

Run:

```bash
uv run pytest tests/test_permissions.py::TestPermissionPolicy::test_metadata_category_lookup_controls_dynamic_tool_permission tests/test_permissions.py::TestPermissionPolicy::test_set_category_lookup_supports_late_tool_runtime_binding tests/test_permissions.py::TestPermissionPolicy::test_invalid_metadata_category_falls_back_to_other -v
```

Expected: FAIL because `PermissionPolicy.__init__` does not accept `category_lookup` and `set_category_lookup()` does not exist.

- [x] **Step 3: Add official permission categories and lookup plumbing**

Modify imports in `src/embedagent/permissions.py`:

```python
from typing import Any, Callable, Dict, List, Optional
```

Add this constant after the interaction tool sets:

```python
OFFICIAL_PERMISSION_CATEGORIES = set(
    ["read", "workspace_write", "shell_exec", "toolchain_exec", "git_write"]
)
```

Update `PermissionPolicy.__init__` signature:

```python
        rules_path: str = "",
        category_lookup: Optional[Callable[[str], str]] = None,
```

Inside `__init__`, after `self.auto_approve_commands = auto_approve_commands`, add:

```python
        self._category_lookup = category_lookup
```

Add this public setter after `build_request()`:

```python
    def set_category_lookup(self, category_lookup: Optional[Callable[[str], str]]) -> None:
        self._category_lookup = category_lookup
```

- [x] **Step 4: Use metadata lookup before static tool sets**

Add this helper above `_category_for_action()`:

```python
    def _metadata_category_for_action(self, action: Action) -> str:
        lookup = getattr(self, "_category_lookup", None)
        if not callable(lookup):
            return ""
        try:
            category = str(lookup(action.name) or "").strip()
        except (RuntimeError, ValueError, TypeError, OSError):
            return ""
        if category in OFFICIAL_PERMISSION_CATEGORIES:
            return category
        return ""
```

Update `_category_for_action()` so the first lines are:

```python
    def _category_for_action(self, action: Action) -> str:
        metadata_category = self._metadata_category_for_action(action)
        if metadata_category:
            return metadata_category
```

Keep the existing static set fallback after those lines.

- [x] **Step 5: Run permission tests**

Run:

```bash
uv run pytest tests/test_permissions.py -v
```

Expected: PASS.

- [x] **Step 6: Commit Task 2**

```bash
git add src/embedagent/permissions.py tests/test_permissions.py
git commit -m "feat: classify dynamic tool permissions"
```

---

### Task 3: Extension Tool Registration Hook

**Files:**
- Modify: `src/embedagent/extensions.py`
- Modify: `tests/test_dynamic_tool_registration.py`

- [x] **Step 1: Write failing extension registration tests**

Append this code to `tests/test_dynamic_tool_registration.py`:

```python
from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    ToolRegistrationEvent,
    ToolRegistrationResult,
)


class DynamicToolExtension(object):
    extension_id = "dynamic_tools"
    builtin_extension = False

    def __init__(self, active=True, tool_name="dynamic_echo"):
        self.active = active
        self.tool_name = tool_name

    def register_tools(self, event, context):
        assert event.reason in ("session_start", "catalog", "test")
        assert context.tool_registry is not None
        return ToolRegistrationResult(
            tools=[make_dynamic_tool(name=self.tool_name)],
            source_id=self.extension_id,
        )

    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        if self.active and mode_name == "build" and workflow_state == "chat":
            return {self.tool_name}
        return set()


class InvalidToolExtension(object):
    extension_id = "invalid_tool"
    builtin_extension = False

    def register_tools(self, event, context):
        del event, context
        return ToolRegistrationResult(tools=[object()], source_id=self.extension_id)


def test_extension_manager_registers_tools_into_runtime(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    manager = ExtensionManager([DynamicToolExtension()])

    manager.register_tools(
        ToolRegistrationEvent(current_mode="build", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )

    entry = runtime.tool_catalog_entry("dynamic_echo")
    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "dynamic_tools"
    assert manager.diagnostics() == []


def test_extension_tool_registration_failure_records_diagnostic(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    manager = ExtensionManager([InvalidToolExtension()])

    manager.register_tools(
        ToolRegistrationEvent(current_mode="build", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )

    diagnostics = manager.diagnostics()
    assert diagnostics
    assert diagnostics[0]["extension_id"] == "invalid_tool"
    assert diagnostics[0]["event"] == "register_tools"
    assert diagnostics[0]["metadata"]["source_id"] == "invalid_tool"
    assert diagnostics[0]["metadata"]["reason"] == "test"
```

- [x] **Step 2: Run extension registration tests and verify they fail**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py::test_extension_manager_registers_tools_into_runtime tests/test_dynamic_tool_registration.py::test_extension_tool_registration_failure_records_diagnostic -v
```

Expected: FAIL because `ToolRegistrationEvent`, `ToolRegistrationResult`, and `ExtensionManager.register_tools()` do not exist.

- [x] **Step 3: Add registration dataclasses**

In `src/embedagent/extensions.py`, add these dataclasses after `ResourcesDiscoverResult`:

```python
@dataclass
class ToolRegistrationEvent:
    current_mode: str = ""
    workflow_state_name: str = "chat"
    reason: str = "startup"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolRegistrationResult:
    tools: List[Any] = field(default_factory=list)
    source_id: str = ""
    source_type: str = "extension"
    metadata: Dict[str, Any] = field(default_factory=dict)
```

- [x] **Step 4: Add structured diagnostic helper**

In `ExtensionManager`, replace `_record_hook_error()` with:

```python
    def _record_diagnostic(
        self,
        extension: Any,
        event_name: str,
        error: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._diagnostics.append(
            ExtensionDiagnostic(
                extension_id=self._extension_id(extension),
                event=event_name,
                error=str(error or ""),
                severity="error",
                source="builtin" if self._is_builtin_extension(extension) else "project",
                metadata=dict(metadata or {}),
            )
        )

    def _record_hook_error(self, extension: Any, event_name: str, exc: Exception) -> None:
        self._record_diagnostic(extension, event_name, str(exc))
```

Existing diagnostics tests should continue to pass because `to_dict()` output keeps the same top-level keys.

- [x] **Step 5: Add ExtensionManager.register_tools()**

Add this method to `ExtensionManager` after `discover_resources()`:

```python
    def register_tools(
        self,
        event: ToolRegistrationEvent,
        context: ExtensionContext,
    ) -> None:
        registry = getattr(context, "tool_registry", None)
        register_tool = getattr(registry, "register_tool", None)
        if not callable(register_tool):
            return
        for extension in list(self._extensions):
            result = self._call_hook(extension, "register_tools", event, context)
            if result is None:
                continue
            tools = list(getattr(result, "tools", []) or [])
            source_id = str(getattr(result, "source_id", "") or self._extension_id(extension))
            source_type = str(getattr(result, "source_type", "") or "extension")
            for tool in tools:
                tool_name = str(getattr(tool, "name", "") or "")
                try:
                    register_tool(
                        tool,
                        source_id=source_id,
                        source_type=source_type,
                    )
                except (RuntimeError, ValueError, TypeError, OSError) as exc:
                    self._record_diagnostic(
                        extension,
                        "register_tools",
                        str(exc),
                        metadata={
                            "tool_name": tool_name,
                            "source_id": source_id,
                            "source_type": source_type,
                            "reason": str(event.reason or ""),
                        },
                    )
                    if self._is_builtin_extension(extension):
                        raise
```

- [x] **Step 6: Run extension registration tests**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py::test_extension_manager_registers_tools_into_runtime tests/test_dynamic_tool_registration.py::test_extension_tool_registration_failure_records_diagnostic -v
```

Expected: PASS.

- [x] **Step 7: Run Slice 1 capability extension tests**

Run:

```bash
uv run pytest tests/test_capability_extensions.py tests/test_workflow_extensions.py -v
```

Expected: PASS.

- [x] **Step 8: Commit Task 3**

```bash
git add src/embedagent/extensions.py tests/test_dynamic_tool_registration.py
git commit -m "feat: add extension tool registration hook"
```

---

### Task 4: QueryEngine And Adapter Integration

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_dynamic_tool_registration.py`

- [x] **Step 1: Write failing QueryEngine and adapter tests**

Append this code to `tests/test_dynamic_tool_registration.py`:

```python
from embedagent.session import Action, AssistantReply


class ToolCallingClient(object):
    def __init__(self, action):
        self.action = action
        self.seen_tool_names = []

    def generate(self, messages, tools=None):
        del messages
        self.seen_tool_names = [
            item["function"]["name"]
            for item in list(tools or [])
            if item.get("type") == "function"
        ]
        return AssistantReply(
            content="using dynamic tool",
            actions=[self.action],
            finish_reason="tool_calls",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None:
            on_reasoning_delta(reply.reasoning_content)
        return reply


def test_query_engine_dynamic_tool_schema_requires_activation(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    runtime = ToolRuntime(str(tmp_path))
    session = __import__("embedagent.session", fromlist=["Session"]).Session()
    inactive = DynamicToolExtension(active=False)
    engine = QueryEngine(
        client=ToolCallingClient(Action("dynamic_echo", {"message": "hi"}, "call-1")),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=ExtensionManager([inactive]),
    )

    engine.initialize_session(session, "build", workflow_state="chat", user_text="hello")
    inactive_names = schema_names(engine._schemas_for_active_tools("build", "chat"))
    inactive.active = True
    active_names = schema_names(engine._schemas_for_active_tools("build", "chat"))

    assert "dynamic_echo" not in inactive_names
    assert "dynamic_echo" in active_names


def test_query_engine_executes_active_extension_tool(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    action = Action("dynamic_echo", {"message": "hello"}, "call-dynamic")
    client = ToolCallingClient(action)
    engine = QueryEngine(
        client=client,
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=ExtensionManager([DynamicToolExtension(active=True)]),
        max_turns=1,
    )

    result = engine.submit_user_turn("use dynamic", stream=False, initial_mode="build")
    observation = result.session.turns[-1].observations[-1]

    assert "dynamic_echo" in client.seen_tool_names
    assert observation.success is True
    assert observation.tool_name == "dynamic_echo"
    assert observation.data["echo"] == "hello"


class DynamicShellExtension(DynamicToolExtension):
    extension_id = "dynamic_shell"

    def register_tools(self, event, context):
        del event, context
        return ToolRegistrationResult(
            tools=[
                make_dynamic_tool(
                    name="dynamic_shell",
                    permission_category="shell_exec",
                    read_only=False,
                )
            ],
            source_id=self.extension_id,
        )


def test_query_engine_dynamic_shell_tool_waits_for_permission(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    action = Action("dynamic_shell", {"message": "hello"}, "call-shell")
    engine = QueryEngine(
        client=ToolCallingClient(action),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=False, workspace=str(tmp_path)),
        extension_manager=ExtensionManager([DynamicShellExtension(active=True, tool_name="dynamic_shell")]),
        max_turns=1,
    )

    result = engine.submit_user_turn("use dynamic shell", stream=False, initial_mode="build")
    observation = result.session.turns[-1].observations[-1]

    assert result.transition.reason == "permission_wait"
    assert observation.success is False
    assert observation.data["pending"] is True


def test_inprocess_adapter_catalog_includes_active_extension_tool(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.extension_manager.register(DynamicToolExtension(active=True))

    catalog = adapter.get_tool_catalog()
    entry = [item for item in catalog if item.get("name") == "dynamic_echo"][0]

    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "dynamic_tools"
    assert entry["permission_category"] == "read"
```

- [x] **Step 2: Run integration tests and verify they fail**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py::test_query_engine_dynamic_tool_schema_requires_activation tests/test_dynamic_tool_registration.py::test_query_engine_executes_active_extension_tool tests/test_dynamic_tool_registration.py::test_query_engine_dynamic_shell_tool_waits_for_permission tests/test_dynamic_tool_registration.py::test_inprocess_adapter_catalog_includes_active_extension_tool -v
```

Expected: FAIL because QueryEngine and InProcessAdapter do not synchronize extension tool registrations and `PermissionPolicy` is not wired to tool catalog metadata.

- [x] **Step 3: Wire QueryEngine permission category lookup**

Modify the extension import in `src/embedagent/query_engine.py`:

```python
from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    SessionView,
    ToolRegistrationEvent,
    WorkflowEvent,
)
```

In `QueryEngine.__init__`, after `self.extension_manager = extension_manager or ExtensionManager()`, add:

```python
        category_setter = getattr(self.permission_policy, "set_category_lookup", None)
        if callable(category_setter):
            category_setter(self._tool_permission_category)
```

Add this helper near `_extension_context()`:

```python
    def _tool_permission_category(self, tool_name: str) -> str:
        lookup = getattr(self.tools, "tool_catalog_entry", None)
        if not callable(lookup):
            return ""
        entry = lookup(tool_name) or {}
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("permission_category") or "")
```

- [x] **Step 4: Add QueryEngine extension tool synchronization**

Add this method after `_workflow_event()`:

```python
    def _ensure_extension_tools_registered(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        reason: str = "turn",
    ) -> None:
        self.extension_manager.register_tools(
            ToolRegistrationEvent(
                current_mode=current_mode,
                workflow_state_name=workflow_state,
                reason=reason,
                metadata={"session_id": session.session_id},
            ),
            self._extension_context(session),
        )
```

In `initialize_session()`, after `current_mode = require_mode(initial_mode)["slug"]`, add:

```python
        self._ensure_extension_tools_registered(
            session,
            current_mode,
            workflow_state,
            reason="session_start",
        )
```

This ensures schema projection and direct command execution see extension tools before the model/tool loop starts.

- [x] **Step 5: Wire InProcessAdapter permission lookup and catalog synchronization**

Modify imports in `src/embedagent/inprocess_adapter.py`:

```python
from embedagent.extensions import ExtensionContext, ToolRegistrationEvent
```

In `InProcessAdapter.__init__`, after `self.extension_manager = default_extensions.manager`, add:

```python
        category_setter = getattr(self.permission_policy, "set_category_lookup", None)
        if callable(category_setter):
            category_setter(self._tool_permission_category)
```

Add these methods near `_build_engine()`:

```python
    def _tool_permission_category(self, tool_name: str) -> str:
        lookup = getattr(self.tools, "tool_catalog_entry", None)
        if not callable(lookup):
            return ""
        entry = lookup(tool_name) or {}
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("permission_category") or "")

    def _ensure_extension_tools_registered(
        self,
        reason: str = "catalog",
        mode_name: str = "",
        workflow_state: str = "chat",
    ) -> None:
        runtime_snapshot = {}
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        if callable(runtime_lookup):
            runtime_snapshot = runtime_lookup()
        self.extension_manager.register_tools(
            ToolRegistrationEvent(
                current_mode=str(mode_name or ""),
                workflow_state_name=str(workflow_state or "chat"),
                reason=str(reason or "catalog"),
            ),
            ExtensionContext(
                workspace=str(getattr(self.tools, "workspace", "") or ""),
                runtime_environment=dict(runtime_snapshot or {}),
                tool_registry=self.tools,
                permission_policy=self.permission_policy,
            ),
        )
```

At the start of `get_tool_catalog()`, add:

```python
        self._ensure_extension_tools_registered(reason="catalog")
```

- [x] **Step 6: Include source metadata in adapter tool events**

In `InProcessAdapter._tool_event_metadata()`, add these keys to the returned dictionary:

```python
            "source_type": entry.get("source_type") or "",
            "source_id": entry.get("source_id") or "",
```

Keep existing keys unchanged.

- [x] **Step 7: Run dynamic integration tests**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py -v
```

Expected: PASS.

- [x] **Step 8: Run focused QueryEngine and adapter regression tests**

Run:

```bash
uv run pytest tests/test_capability_extensions.py tests/test_workflow_extensions.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [x] **Step 9: Commit Task 4**

```bash
git add src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests/test_dynamic_tool_registration.py
git commit -m "feat: wire extension tools into agent runtime"
```

---

### Task 5: Source-Of-Truth Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [x] **Step 1: Update README runtime direction**

In `README.md`, update the extension-runtime bullet near the top to mention dynamic tool registration:

```markdown
- Official extension runtime direction: `ExtensionManager` is the shared in-process capability boundary for workflow defaults, prompt/context hooks, tool-call/tool-result hooks, resource discovery contracts, dynamic in-process tool registration, and extension diagnostics; project-local Python code loading remains deferred
```

- [x] **Step 2: Update AGENTS.md architecture vocabulary**

In `AGENTS.md`, update the `ExtensionManager` paragraph under Harness:

```markdown
`ExtensionManager` is also the shared in-process capability boundary for prompt/context hooks, tool-call and tool-result hooks, resource discovery contracts, dynamic in-process tool registration, and extension diagnostics. This does not enable project-local Python extension loading; that remains a separate, explicitly guarded follow-up.
```

In the Tooling section, add this paragraph after the `ToolRuntime.schemas_for(mode, workflow_state, tool_names=active_tool_names)` paragraph:

```markdown
Dynamic in-process extension tools are registered into the shared `ToolRuntime` with source metadata and explicit permission categories. A registered extension tool is model-visible only when active through the shared `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` path and remains subject to `PermissionPolicy`.
```

- [x] **Step 3: Update overall architecture**

In `docs/overall-solution-architecture.md`, add a short paragraph to the Agent Core Layer section:

```markdown
Slice 2 makes the tool runtime source-aware and dynamically extensible. In-process extensions can register `ToolDefinition` objects into the shared `ToolRuntime`; source metadata is projected through the existing catalog, and active-tool visibility still flows through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)`.
```

- [x] **Step 4: Update tool contracts**

In `docs/tool-contracts.md`, add this section after the extension tool hooks section:

```markdown
## Dynamic Extension Tool Registration

In-process extensions may register tools into the shared `ToolRuntime` through the extension manager. Registered tools must provide:

- `ToolDefinition`
- `permission_category`
- mode and workflow visibility metadata
- read-only and concurrency metadata
- source metadata supplied by the extension runtime

Registration does not make a tool active by itself. A dynamic tool appears in model schemas and frontend catalog views only when its name is active through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)`. Extensions cannot replace built-in tools in this slice.
```

- [x] **Step 5: Update permission model**

In `docs/permission-model.md`, add this paragraph to the tool categories section:

```markdown
Dynamic extension tools are classified through `ToolRuntime` catalog metadata. `PermissionPolicy` may receive a category lookup bound to the active runtime; if a registered extension tool declares `workspace_write`, `shell_exec`, `toolchain_exec`, or `git_write`, the same approval and rule paths apply as for built-in tools. Unknown tools without valid metadata remain `other` and should not be used as a shortcut for privileged behavior.
```

- [x] **Step 6: Update frontend protocol**

In `docs/frontend-protocol.md`, update the tool catalog item documentation to include:

```markdown
- `source_type`
- `source_id`
```

Add:

```markdown
Frontends may display dynamic tool source metadata for diagnostics or future extension management. They must continue to treat tool permission behavior as backend-owned and derive permission prompts only from backend events.
```

- [x] **Step 7: Update tracker and changelog**

Append this section to `docs/development-tracker.md`:

```markdown
## 2026-06-04 Dynamic Tool Registration

- Added the Slice 2 plan for dynamic in-process tool registration through the shared extension manager and tool runtime.
- Dynamic tools remain inactive until selected by the extension active-tool path and remain permission-gated through catalog metadata.
- Project-local extension loading, resource discovery, and reload commands remain follow-up slices.
```

Append this section to `docs/design-change-log.md`:

```markdown
## 2026-06-04 Dynamic Tool Registration

Accepted dynamic in-process tool registration as the second self-extensible Agent Core slice. Tool registration is source-aware, active-tool gated, and permission-classified through runtime catalog metadata. Built-in tool replacement, project-local Python loading, and resource reload remain deferred.
```

- [x] **Step 8: Run documentation vocabulary check**

Run:

```bash
rg -n "manage_todos| code mode|code mode|Session.task_graph" README.md AGENTS.md docs/overall-solution-architecture.md docs/tool-contracts.md docs/permission-model.md docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md
```

Expected: no matches for reintroduced deprecated vocabulary in the edited sections.

- [x] **Step 9: Commit Task 5**

```bash
git add README.md AGENTS.md docs/overall-solution-architecture.md docs/tool-contracts.md docs/permission-model.md docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: document dynamic tool registration"
```

---

### Task 6: Final Verification

**Files:**
- Verify only; no planned source edits.

- [x] **Step 1: Run dynamic and extension-focused tests**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py tests/test_workflow_extensions.py -v
```

Expected: PASS.

- [x] **Step 2: Run permission and tool runtime tests**

Run:

```bash
uv run pytest tests/test_permissions.py tests/test_tools_package.py -v
```

Expected: PASS.

- [x] **Step 3: Run QueryEngine and frontend adapter regression tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py tests/test_inprocess_adapter_frontend_api.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [x] **Step 4: Run fast suite with workspace temp directory**

Run:

```bash
$tmp = Join-Path (Get-Location) '.pytest-envtmp'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null; $env:TMP=$tmp; $env:TEMP=$tmp; uv run pytest tests/ -m "not slow and not gui" -v --basetemp .pytest-tmp-dynamic-tools
```

Expected: PASS. The `TMP` and `TEMP` override avoids known ACL problems with the default user temp pytest directory on this machine.

- [x] **Step 5: Run focused lint**

Run:

```bash
uv run ruff check src/embedagent/tools/runtime.py src/embedagent/extensions.py src/embedagent/permissions.py src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests/test_dynamic_tool_registration.py tests/test_permissions.py
```

Expected: PASS.

- [x] **Step 6: Inspect final git state**

Run:

```bash
git status --short
git log --oneline -n 10
```

Expected: implementation and documentation changes are committed. Pre-existing unrelated local files may still appear:

```text
 M .agents/plugins/superpowers
 M .claude/settings.local.json
?? .superpowers/brainstorm/1383-1775611182/
?? analysis/embedagent_vs_claude_code_architecture_review.md
?? docs/superpowers/specs/2026-05-26-workflow-extension-boundary-design.md
```

Do not stage or revert those unrelated files.
