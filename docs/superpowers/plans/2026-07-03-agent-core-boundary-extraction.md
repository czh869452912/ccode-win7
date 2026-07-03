# Agent Core Boundary Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `embedagent_core` import-clean, product-neutral, and ready to become an independently publishable Agent Core package.

**Architecture:** This stage removes reverse dependencies from Core into the product package instead of keeping shims. Core owns durable agent data types, loop/kernel services, permission/event/reducer contracts, and abstract ports; Host owns concrete stores, context assembly, tool implementations, provider clients, workspace policy, and workflow package composition. Old import paths and tests that only protect old paths are deleted in the same slice that removes the old code.

**Tech Stack:** Python 3.8-only dataclasses and typing protocols, existing pytest suite, existing package layout under `src/`, no new runtime dependencies, no compatibility aliases.

---

## Execution Covenant

- No backward compatibility shims, aliases, re-export modules, or dual import paths.
- Delete tests that assert obsolete import locations; rewrite tests that assert product behavior against the new boundary.
- Keep `src/embedagent_core` free of `embedagent.*`, `embedagent_host.*`, GUI, TUI, and workflow package imports.
- Keep C/C++ workflow behavior in `src/embedagent/workflow_packages/c_cpp` and host composition in `src/embedagent_host`.
- Keep Python syntax valid for `>=3.8,<3.9`: no `match`, no `:=`, no `dict | dict`, no built-in generic aliases.
- Do not add dependencies to `pyproject.toml`.
- Each task ends with a small commit. If a task deletes obsolete tests, the commit message must say so.

## Non-Goals For This Stage

- Do not redesign the T3 GUI in this stage.
- Do not extract the physical repo in this stage.
- Do not add Python/HTML/general workflow packages in this stage.
- Do not change the default C/C++ user workflow except where imports must follow the new boundary.

## File Structure Map

### Core-Owned Modules

- Create or promote `src/embedagent_core/session.py`
  - Owns `Action`, `Observation`, `AssistantReply`, `TranscriptMessage`, `Turn`, `Session`, `QueryTurnResult`, pending interaction records, and transcript message constants.
- Create or promote `src/embedagent_core/compacted_history.py`
  - Owns compacted-history checkpoint and reducer data structures used by core reducers.
- Create or promote `src/embedagent_core/interaction.py`
  - Owns `UserInputRequest`, `UserInputResponse`, `UserInputOption`, and generic interactive tool schemas.
- Create or promote `src/embedagent_core/model.py`
  - Owns `ModelClientError` and a `ModelClient` protocol with `generate()` and `stream()`.
- Create or promote `src/embedagent_core/tool_execution.py`
  - Owns `StreamingToolExecutor`, `ToolBatch`, `ToolExecutionUpdate`, and `partition_tool_actions`.
- Create or promote `src/embedagent_core/guard.py`
  - Owns `ProgressGuard`.
- Create `src/embedagent_core/tool_contracts.py`
  - Owns `ToolError`, `ToolDefinition`, `ToolRuntimePort`, tool catalog dataclasses, and workspace path resolver protocol.
- Create `src/embedagent_core/ports.py`
  - Owns host-provided protocols for context assembly, transcript persistence, memory maintenance, prompt assembly, workspace profile messages, tracing, and tool commit coordination.
- Modify existing `src/embedagent_core/*.py`
  - Replace every `embedagent.*` import with `embedagent_core.*` or a port.

### Host/Product-Owned Modules

- Keep concrete `ToolRuntime` in `src/embedagent/tools/runtime.py`
  - It implements `ToolRuntimePort`; it may import `embedagent_core`, but Core must not import it.
- Keep concrete tool implementations in `src/embedagent/tools/`.
- Move concrete OpenAI-compatible provider code from `src/embedagent/llm.py` into `src/embedagent_host/providers/openai_compatible.py`.
- Keep context, memory, stores, prompt assembly, workspace intelligence, and workspace profile implementations in product/host until a separate host plan moves them.
- Modify `src/embedagent_host/inprocess_adapter.py`
  - It constructs all concrete dependencies and passes them into `QueryEngine`.

### Deleted Old Paths

- Delete `src/embedagent/session.py` after all imports use `embedagent_core.session`.
- Delete `src/embedagent/interaction.py` after all imports use `embedagent_core.interaction`.
- Delete `src/embedagent/guard.py` after all imports use `embedagent_core.guard`.
- Delete `src/embedagent/tool_execution.py` after all imports use `embedagent_core.tool_execution`.
- Delete `src/embedagent/compacted_history.py` after all imports use `embedagent_core.compacted_history`.
- Delete `src/embedagent/llm.py` after provider imports use `embedagent_host.providers.openai_compatible` and Core imports use `embedagent_core.model`.
- Do not replace deleted files with compatibility re-export stubs.

---

## Task 1: Add The Hard Core Import Boundary Gate

**Files:**
- Modify: `tests/test_core_package_imports.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] **Step 1: Replace the existing weak import test with a hard boundary test**

Edit `tests/test_core_package_imports.py` so the complete file is:

```python
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class CorePackageImportTests(unittest.TestCase):
    def _core_python_files(self):
        root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent_core")
        self.assertTrue(os.path.isdir(root))
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if filename.endswith(".py"):
                    yield root, os.path.join(dirpath, filename)

    def _imports_from_file(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                yield node.module or ""
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name

    def test_embedagent_core_imports_no_product_host_gui_or_workflow_packages(self):
        forbidden_roots = (
            "embedagent",
            "embedagent_host",
        )
        offenders = []
        for root, path in self._core_python_files():
            for module in self._imports_from_file(path):
                if module == "embedagent_core" or module.startswith("embedagent_core."):
                    continue
                if module == "embedagent_host" or module.startswith("embedagent_host."):
                    offenders.append((os.path.relpath(path, root), module))
                    continue
                if module == "embedagent" or module.startswith("embedagent."):
                    offenders.append((os.path.relpath(path, root), module))
                    continue
                if any(module == item for item in forbidden_roots):
                    offenders.append((os.path.relpath(path, root), module))
        self.assertEqual(offenders, [])

    def test_deleted_core_type_paths_do_not_exist_in_product_package(self):
        root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent")
        deleted = (
            "session.py",
            "interaction.py",
            "guard.py",
            "tool_execution.py",
            "compacted_history.py",
            "llm.py",
        )
        existing = [
            name
            for name in deleted
            if os.path.exists(os.path.join(root, name))
        ]
        self.assertEqual(existing, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Add a deletion-first policy assertion to the architecture boundary test**

Append this test to `tests/test_current_architecture_boundaries.py`:

```python
def test_no_compatibility_reexports_for_core_extraction():
    deleted_paths = [
        ROOT / "src/embedagent/session.py",
        ROOT / "src/embedagent/interaction.py",
        ROOT / "src/embedagent/guard.py",
        ROOT / "src/embedagent/tool_execution.py",
        ROOT / "src/embedagent/compacted_history.py",
        ROOT / "src/embedagent/llm.py",
    ]
    existing = [_relative(path) for path in deleted_paths if path.exists()]
    assert existing == []

    forbidden_reexport_text = (
        "from embedagent_core.session import",
        "from embedagent_core.interaction import",
        "from embedagent_core.guard import",
        "from embedagent_core.tool_execution import",
        "from embedagent_core.compacted_history import",
        "from embedagent_core.model import",
    )
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        text = _read(path)
        rel = _relative(path)
        if rel.startswith("src/embedagent/workflow_packages/c_cpp/"):
            continue
        for token in forbidden_reexport_text:
            if token in text and path.name in (
                "session.py",
                "interaction.py",
                "guard.py",
                "tool_execution.py",
                "compacted_history.py",
                "llm.py",
            ):
                offenders.append("%s reexports %s" % (rel, token))
    assert offenders == []
```

- [ ] **Step 3: Run the new gate and confirm it fails on current imports**

Run:

```bash
uv run pytest tests/test_core_package_imports.py tests/test_current_architecture_boundaries.py::test_no_compatibility_reexports_for_core_extraction -v
```

Expected: FAIL. The failure must list current `embedagent_core` imports from `embedagent.*` and the still-existing product files.

- [ ] **Step 4: Commit the failing architecture gate**

Run:

```bash
git add tests/test_core_package_imports.py tests/test_current_architecture_boundaries.py
git commit -m "test: add hard agent core import boundary gate"
```

---

## Task 2: Promote Core Session And Compaction Data Types

**Files:**
- Move: `src/embedagent/session.py` to `src/embedagent_core/session.py`
- Move: `src/embedagent/compacted_history.py` to `src/embedagent_core/compacted_history.py`
- Modify: `src/embedagent_core/session.py`
- Modify: `src/embedagent_core/compaction_state.py`
- Modify: `src/embedagent_core/compaction_journal.py`
- Modify: all source and test files importing `embedagent.session` or `embedagent.compacted_history`

- [ ] **Step 1: Move the files without leaving stubs**

Run:

```bash
git mv src/embedagent/session.py src/embedagent_core/session.py
git mv src/embedagent/compacted_history.py src/embedagent_core/compacted_history.py
```

- [ ] **Step 2: Fix the promoted session import**

In `src/embedagent_core/session.py`, replace:

```python
from embedagent.compacted_history import CompactedHistoryCheckpoint
```

with:

```python
from embedagent_core.compacted_history import CompactedHistoryCheckpoint
```

- [ ] **Step 3: Replace all session and compacted-history imports**

Run:

```bash
rg -l "embedagent\\.session|embedagent\\.compacted_history" src tests
```

For every returned Python file, replace imports with:

```python
from embedagent_core.session import Action, Observation
from embedagent_core.compacted_history import CompactedHistoryReducer
```

Use the exact imported names that each file already uses; do not import unused names.

- [ ] **Step 4: Delete obsolete import-path tests**

In test files that only assert `from embedagent.session import ...` or `from embedagent.compacted_history import ...` still works, delete those assertions. Keep tests that validate behavior by changing the import to `embedagent_core.session` or `embedagent_core.compacted_history`.

- [ ] **Step 5: Run the focused tests**

Run:

```bash
uv run pytest tests/test_core_package_imports.py tests/test_compacted_history.py tests/test_compaction_state.py tests/test_session_integration.py -v
```

Expected: `test_core_package_imports.py` still fails because other core imports remain; compaction and session behavior tests pass after import updates.

- [ ] **Step 6: Commit the session data promotion**

Run:

```bash
git add src tests
git commit -m "refactor: promote session data types into agent core"
```

---

## Task 3: Promote Interaction, Guard, And Tool Execution Primitives

**Files:**
- Move: `src/embedagent/interaction.py` to `src/embedagent_core/interaction.py`
- Move: `src/embedagent/guard.py` to `src/embedagent_core/guard.py`
- Move: `src/embedagent/tool_execution.py` to `src/embedagent_core/tool_execution.py`
- Modify: `src/embedagent_core/agent_extension_host.py`
- Modify: `src/embedagent_core/agent_loop.py`
- Modify: `src/embedagent_core/agent_tool_action_service.py`
- Modify: all source and test files importing the moved modules

- [ ] **Step 1: Move the files without leaving stubs**

Run:

```bash
git mv src/embedagent/interaction.py src/embedagent_core/interaction.py
git mv src/embedagent/guard.py src/embedagent_core/guard.py
git mv src/embedagent/tool_execution.py src/embedagent_core/tool_execution.py
```

- [ ] **Step 2: Update imports inside promoted files**

In `src/embedagent_core/guard.py`, replace:

```python
from embedagent.session import Action, Observation
```

with:

```python
from embedagent_core.session import Action, Observation
```

In `src/embedagent_core/tool_execution.py`, replace:

```python
from embedagent.session import Action, Observation
```

with:

```python
from embedagent_core.session import Action, Observation
```

- [ ] **Step 3: Replace all imports of the moved modules**

Run:

```bash
rg -l "embedagent\\.(interaction|guard|tool_execution)" src tests
```

Replace those imports with `embedagent_core.interaction`, `embedagent_core.guard`, or `embedagent_core.tool_execution`. Delete tests whose only assertion is that the old product import path still works.

- [ ] **Step 4: Run the focused tests**

Run:

```bash
uv run pytest tests/test_guard.py tests/test_tool_execution.py tests/test_agent_loop_continuation.py tests/test_core_package_imports.py -v
```

Expected: guard, tool execution, and loop continuation tests pass; the core import gate still fails until tool, mode, provider, context, and store dependencies are removed.

- [ ] **Step 5: Commit the primitive promotion**

Run:

```bash
git add src tests
git commit -m "refactor: move interaction and loop primitives into agent core"
```

---

## Task 4: Split Model Provider Contracts From The Concrete Provider

**Files:**
- Create: `src/embedagent_core/model.py`
- Create: `src/embedagent_host/providers/__init__.py`
- Move provider implementation from `src/embedagent/llm.py` to `src/embedagent_host/providers/openai_compatible.py`
- Modify: `src/embedagent_core/agent_loop.py`
- Modify: `src/embedagent_core/query_engine.py`
- Modify: host, CLI, TUI, GUI, and tests importing `OpenAICompatibleClient`

- [ ] **Step 1: Create the core model protocol**

Create `src/embedagent_core/model.py`:

```python
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Protocol

from embedagent_core.session import AssistantReply


class ModelClientError(Exception):
    pass


class ModelClient(Protocol):
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AssistantReply:
        raise NotImplementedError

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
    ) -> AssistantReply:
        raise NotImplementedError
```

- [ ] **Step 2: Move the concrete provider**

Run:

```bash
New-Item -ItemType Directory -Path src\\embedagent_host\\providers
New-Item -ItemType File -Path src\\embedagent_host\\providers\\__init__.py
git mv src/embedagent/llm.py src/embedagent_host/providers/openai_compatible.py
```

- [ ] **Step 3: Update provider implementation imports**

In `src/embedagent_host/providers/openai_compatible.py`, replace:

```python
from embedagent.session import Action, AssistantReply
```

with:

```python
from embedagent_core.model import ModelClientError
from embedagent_core.session import Action, AssistantReply
```

Delete the local `class ModelClientError(Exception):` definition from the provider file.

- [ ] **Step 4: Update core imports**

In `src/embedagent_core/agent_loop.py` and `src/embedagent_core/query_engine.py`, import `ModelClientError` and `ModelClient` from `embedagent_core.model`.

The `QueryEngine.__init__` client argument annotation becomes:

```python
from embedagent_core.model import ModelClient, ModelClientError


def __init__(
    self,
    client: ModelClient,
    tools: ToolRuntimePort,
    ...
) -> None:
```

- [ ] **Step 5: Update product imports for the concrete client**

Run:

```bash
rg -l "embedagent\\.llm|OpenAICompatibleClient" src tests
```

For concrete client construction or test mocks, import:

```python
from embedagent_host.providers.openai_compatible import OpenAICompatibleClient
```

For core error handling, import:

```python
from embedagent_core.model import ModelClientError
```

- [ ] **Step 6: Run the focused provider tests**

Run:

```bash
uv run pytest tests/test_llm_resilience.py tests/test_cli_hosted_entrypoint.py tests/test_hosted_runtime.py tests/test_core_package_imports.py -v
```

Expected: provider behavior tests pass; the core import gate still fails until tool, mode, context, and store dependencies are removed.

- [ ] **Step 7: Commit the model contract split**

Run:

```bash
git add src tests
git commit -m "refactor: split model provider contract from host provider"
```

---

## Task 5: Move Tool Contracts Into Core And Keep ToolRuntime In Product

**Files:**
- Create: `src/embedagent_core/tool_contracts.py`
- Modify: `src/embedagent/tools/_base.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent_core/agent_extension_host.py`
- Modify: `src/embedagent_core/agent_tool_action_service.py`
- Modify: tests importing `ToolDefinition`, `ToolError`, or tool catalog dataclasses

- [ ] **Step 1: Create core tool contracts**

Create `src/embedagent_core/tool_contracts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from embedagent_core.session import Observation


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


def diagnostic_tool_error(
    message: str, error_kind: str, suggested_next_step: str = ""
) -> ToolError:
    return ToolError(
        message,
        error_kind=error_kind,
        retryable=False,
        outcome_class="diagnostic_failure",
        suggested_next_step=suggested_next_step,
    )


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Observation]
    metadata: Dict[str, Any] = field(default_factory=dict)
    read_only: bool = False
    concurrency_safe: bool = False
    interrupt_behavior: str = "block"
    result_budget_policy: str = "default"
    activity_kind: str = "tool"
    context_priority: int = 50

    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolExecutionSpec:
    read_only: bool
    concurrency_safe: bool
    interrupt_behavior: str
    result_budget_policy: str


@dataclass
class ToolPresentation:
    user_label: str
    progress_renderer_key: str
    result_renderer_key: str
    supports_diff_preview: bool


@dataclass
class ToolContextPolicy:
    context_reducer_key: str
    activity_kind: str
    context_priority: int
    read_model_invalidations: List[str]


@dataclass
class ToolCatalogEntry:
    name: str
    description: str
    permission_category: str
    mode_visibility: List[str]
    workflow_visibility: List[str]
    execution: ToolExecutionSpec
    presentation: ToolPresentation
    context_policy: ToolContextPolicy
    source_type: str
    source_id: str

    @property
    def read_only(self) -> bool:
        return self.execution.read_only

    @property
    def concurrency_safe(self) -> bool:
        return self.execution.concurrency_safe

    @property
    def interrupt_behavior(self) -> str:
        return self.execution.interrupt_behavior

    @property
    def result_budget_policy(self) -> str:
        return self.execution.result_budget_policy

    @property
    def read_model_invalidations(self) -> List[str]:
        return list(self.context_policy.read_model_invalidations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permission_category": self.permission_category,
            "mode_visibility": list(self.mode_visibility),
            "workflow_visibility": list(self.workflow_visibility),
            "user_label": self.presentation.user_label,
            "progress_renderer_key": self.presentation.progress_renderer_key,
            "result_renderer_key": self.presentation.result_renderer_key,
            "supports_diff_preview": self.presentation.supports_diff_preview,
            "context_reducer_key": self.context_policy.context_reducer_key,
            "read_only": self.read_only,
            "concurrency_safe": self.concurrency_safe,
            "interrupt_behavior": self.interrupt_behavior,
            "result_budget_policy": self.result_budget_policy,
            "activity_kind": self.context_policy.activity_kind,
            "context_priority": self.context_policy.context_priority,
            "read_model_invalidations": self.read_model_invalidations,
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


class WorkspacePathResolver(Protocol):
    def resolve_path(self, path: str, allow_missing: bool = False) -> str:
        raise NotImplementedError


class ToolRuntimePort(Protocol):
    workspace: str
    tool_result_store: Any
    projection_db: Any

    def schemas_for(
        self,
        mode: str,
        workflow_state: Optional[Dict[str, Any]] = None,
        tool_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def execute_with_interrupt(
        self,
        name: str,
        arguments: Dict[str, Any],
        stop_event: Any,
    ) -> Observation:
        raise NotImplementedError

    def catalog_entry(self, tool_name: str) -> Optional[ToolCatalogEntry]:
        raise NotImplementedError

    def path_resolver(self) -> WorkspacePathResolver:
        raise NotImplementedError
```

- [ ] **Step 2: Make product tool base import core contracts**

In `src/embedagent/tools/_base.py`, delete the local `ToolError`, `diagnostic_tool_error`, and `ToolDefinition` definitions. Import them instead:

```python
from embedagent_core.tool_contracts import (
    ToolDefinition,
    ToolError,
    diagnostic_tool_error,
)
```

Keep `ToolContext`, command decoding, diagnostics, and filesystem helpers in `src/embedagent/tools/_base.py`.

- [ ] **Step 3: Make ToolRuntime implement the port**

In `src/embedagent/tools/runtime.py`, import catalog dataclasses from core:

```python
from embedagent_core.tool_contracts import (
    ToolCatalogEntry,
    ToolContextPolicy,
    ToolExecutionSpec,
    ToolPresentation,
    ToolRuntimePort,
)
```

Remove duplicate dataclass definitions from `runtime.py`.

Add this method to `ToolRuntime`:

```python
def path_resolver(self):
    return self._ctx
```

- [ ] **Step 4: Update Core to use the port**

In `src/embedagent_core/agent_extension_host.py` and `src/embedagent_core/agent_tool_action_service.py`, replace:

```python
from embedagent.tools import ToolRuntime
from embedagent.tools._base import ToolError
```

with:

```python
from embedagent_core.tool_contracts import ToolError, ToolRuntimePort
```

Change constructor annotations from `ToolRuntime` to `ToolRuntimePort`.

- [ ] **Step 5: Remove private ToolRuntime context access from Core**

In `src/embedagent_core/agent_tool_action_service.py`, replace:

```python
resolved_path = self.tools._ctx.resolve_path(normalized, allow_missing=True)
```

with:

```python
resolved_path = self.tools.path_resolver().resolve_path(normalized, allow_missing=True)
```

- [ ] **Step 6: Run focused tool tests**

Run:

```bash
uv run pytest tests/test_tools_v2_runtime.py tests/test_dynamic_tool_registration.py tests/test_tool_execution.py tests/test_core_package_imports.py -v
```

Expected: tool runtime tests pass; the core import gate still fails until mode and host service dependencies are removed.

- [ ] **Step 7: Commit the tool contract split**

Run:

```bash
git add src tests
git commit -m "refactor: move tool contracts into agent core"
```

---

## Task 6: Replace Core Mode Imports With Host-Provided Policies

**Files:**
- Create: `src/embedagent_core/policies.py`
- Modify: `src/embedagent_core/agent_extension_host.py`
- Modify: `src/embedagent_core/agent_tool_action_service.py`
- Modify: `src/embedagent_core/query_engine.py`
- Modify: `src/embedagent_host/inprocess_adapter.py`
- Modify: tests constructing `QueryEngine` directly

- [ ] **Step 1: Create core policy protocols**

Create `src/embedagent_core/policies.py`:

```python
from __future__ import annotations

from typing import Any, Dict, List, Protocol


class ModeToolPolicy(Protocol):
    def allowed_tools_for(
        self,
        mode_name: str,
        workflow_state: Dict[str, Any],
    ) -> List[str]:
        raise NotImplementedError


class WritePathPolicy(Protocol):
    def is_path_writable(
        self,
        mode_name: str,
        normalized_path: str,
        app_config: Any,
    ) -> bool:
        raise NotImplementedError
```

- [ ] **Step 2: Add product policy adapters in host composition**

In `src/embedagent_host/inprocess_adapter.py`, add these classes near the other private host helpers:

```python
class _ProductModeToolPolicy(object):
    def allowed_tools_for(self, mode_name, workflow_state):
        from embedagent.modes import allowed_tools_for

        return allowed_tools_for(mode_name)


class _ProductWritePathPolicy(object):
    def is_path_writable(self, mode_name, normalized_path, app_config):
        from embedagent.modes import is_path_writable

        return is_path_writable(mode_name, normalized_path, app_config)
```

Pass instances into every `QueryEngine(...)` construction:

```python
mode_tool_policy=_ProductModeToolPolicy(),
write_path_policy=_ProductWritePathPolicy(),
```

- [ ] **Step 3: Update AgentExtensionHost**

In `src/embedagent_core/agent_extension_host.py`, remove:

```python
from embedagent.modes import allowed_tools_for
```

Add:

```python
from embedagent_core.policies import ModeToolPolicy
```

Change the constructor to accept `mode_tool_policy: ModeToolPolicy`, store it, and replace direct calls to `allowed_tools_for(current_mode)` with:

```python
base_allowed = self.mode_tool_policy.allowed_tools_for(
    current_mode,
    workflow_state if isinstance(workflow_state, dict) else {},
)
```

- [ ] **Step 4: Update AgentToolActionService**

In `src/embedagent_core/agent_tool_action_service.py`, remove:

```python
from embedagent.modes import is_path_writable
```

Add:

```python
from embedagent_core.policies import WritePathPolicy
```

Accept `write_path_policy: WritePathPolicy` in the constructor and replace:

```python
if not is_path_writable(current_mode, normalized, self._app_config_provider()):
```

with:

```python
if not self.write_path_policy.is_path_writable(
    current_mode,
    normalized,
    self._app_config_provider(),
):
```

- [ ] **Step 5: Update direct QueryEngine tests**

For tests that instantiate `QueryEngine` directly, add tiny test policies:

```python
class AllowAllModeToolPolicy(object):
    def allowed_tools_for(self, mode_name, workflow_state):
        return ["read_file", "list_dir", "glob_files", "grep_text", "ask_user"]


class AllowWorkspaceWritePathPolicy(object):
    def is_path_writable(self, mode_name, normalized_path, app_config):
        return True
```

Pass them into `QueryEngine`.

- [ ] **Step 6: Run focused policy tests**

Run:

```bash
uv run pytest tests/test_current_architecture_boundaries.py::test_query_engine_does_not_own_extension_dispatch_boundary tests/test_modes.py tests/test_query_engine_build_lite.py tests/test_core_package_imports.py -v
```

Expected: mode tests pass in product package; QueryEngine tests pass with explicit policies; the core import gate still fails until context, store, prompt, tracing, and workspace dependencies are removed.

- [ ] **Step 7: Commit policy injection**

Run:

```bash
git add src tests
git commit -m "refactor: inject mode and path policies into agent core"
```

---

## Task 7: Introduce Core Ports For Host Services

**Files:**
- Create: `src/embedagent_core/ports.py`
- Modify: `src/embedagent_core/query_engine.py`
- Modify: `src/embedagent_host/inprocess_adapter.py`
- Modify: tests constructing `QueryEngine` directly

- [ ] **Step 1: Create host service protocols**

Create `src/embedagent_core/ports.py`:

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from embedagent_core.session import ContextAssemblyResult, Session


class ContextAssemblerPort(Protocol):
    def assemble(
        self,
        session: Session,
        current_mode: str,
        workflow_state: Dict[str, Any],
        max_tokens: Optional[int] = None,
    ) -> ContextAssemblyResult:
        raise NotImplementedError


class PromptAssemblyPort(Protocol):
    def build_messages(
        self,
        session: Session,
        context: ContextAssemblyResult,
        current_mode: str,
        workflow_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError


class TranscriptStorePort(Protocol):
    def append_event(self, session_id: str, event: Dict[str, Any]) -> None:
        raise NotImplementedError

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class SessionSummaryStorePort(Protocol):
    def save_summary(self, session: Session) -> None:
        raise NotImplementedError


class ProjectMemoryStorePort(Protocol):
    def load(self) -> Dict[str, Any]:
        raise NotImplementedError

    def save(self, data: Dict[str, Any]) -> None:
        raise NotImplementedError


class MemoryMaintenancePort(Protocol):
    def run(self, session: Session) -> None:
        raise NotImplementedError


class ToolCommitCoordinatorPort(Protocol):
    def before_tool(self, session: Session, tool_name: str, arguments: Dict[str, Any]) -> None:
        raise NotImplementedError

    def after_tool(self, session: Session, tool_name: str, observation: Any) -> None:
        raise NotImplementedError


class WorkspaceProfilePort(Protocol):
    def build_message(self, workspace: str, session_id: str) -> str:
        raise NotImplementedError


class WorkspaceIntelligencePort(Protocol):
    def refresh(self, workspace: str) -> Dict[str, Any]:
        raise NotImplementedError


class ExecutionTracerPort(Protocol):
    def record(self, event_type: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError
```

- [ ] **Step 2: Replace QueryEngine direct imports with ports**

In `src/embedagent_core/query_engine.py`, remove imports of:

```python
from embedagent.context import ContextManager
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.prompt_assembly_service import PromptAssemblyService
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session_store import SessionSummaryStore
from embedagent.tool_commit import ToolCommitCoordinator
from embedagent.transcript_store import TranscriptStore
from embedagent.workspace_intelligence import WorkspaceIntelligenceBroker
from embedagent.workspace_profile import build_workspace_profile_message
from embedagent.strategies.execution_tracer import ExecutionTracer, TraceEventType
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper
```

Import the port types from `embedagent_core.ports`. QueryEngine must receive concrete instances through its constructor. It must not create product-layer defaults.

- [ ] **Step 3: Move QueryEngine default construction into the host**

In `src/embedagent_host/inprocess_adapter.py`, construct the concrete objects currently created by `QueryEngine.__init__`:

```python
from embedagent.context import ContextManager
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.prompt_assembly_service import PromptAssemblyService
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session_store import SessionSummaryStore
from embedagent.tool_commit import ToolCommitCoordinator
from embedagent.transcript_store import TranscriptStore
from embedagent.workspace_intelligence import WorkspaceIntelligenceBroker
from embedagent.workspace_profile import build_workspace_profile_message
```

Pass those objects into `QueryEngine(...)`. For workspace profile, wrap the function:

```python
class _WorkspaceProfilePort(object):
    def build_message(self, workspace, session_id):
        from embedagent.workspace_profile import build_workspace_profile_message

        return build_workspace_profile_message(workspace, session_id)
```

- [ ] **Step 4: Replace retry wrapper dependency**

Core must not import the product strategy wrapper. Either pass a client already wrapped by host or create a core-local retry port. For this stage, wrap the client in host before passing it into QueryEngine:

```python
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper

client_for_engine = LLMClientRetryWrapper(client)
```

Then remove retry-wrapper construction from QueryEngine.

- [ ] **Step 5: Update direct QueryEngine tests**

For tests that instantiate `QueryEngine` directly, use fake ports that record calls in memory. Add this fixture pattern to the relevant test file:

```python
class FakeTranscriptStore(object):
    def __init__(self):
        self.events = []

    def append_event(self, session_id, event):
        self.events.append((session_id, dict(event)))

    def load_events(self, session_id):
        return [dict(event) for _session_id, event in self.events if _session_id == session_id]


class FakeWorkspaceProfile(object):
    def build_message(self, workspace, session_id):
        return ""
```

Do not add default construction back into QueryEngine to keep old tests short.

- [ ] **Step 6: Run focused QueryEngine tests**

Run:

```bash
uv run pytest tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py tests/test_inprocess_adapter_frontend_api.py tests/test_core_package_imports.py -v
```

Expected: QueryEngine and adapter tests pass with explicit host-provided dependencies; the core import gate still fails only on any remaining direct product imports.

- [ ] **Step 7: Commit host service port injection**

Run:

```bash
git add src tests
git commit -m "refactor: inject host service ports into query engine"
```

---

## Task 8: Remove Remaining Product Imports From Core

**Files:**
- Modify: every file under `src/embedagent_core/` still reported by the boundary test
- Modify: product/host files that need to import the new core modules
- Modify: obsolete tests that only assert old imports

- [ ] **Step 1: Print the remaining offenders**

Run:

```bash
uv run pytest tests/test_core_package_imports.py -v
```

Expected: FAIL if any `embedagent_core` file still imports `embedagent.*` or `embedagent_host.*`.

- [ ] **Step 2: For each remaining offender, apply the boundary rule**

Use this rule for every remaining import:

```text
If the imported type is durable agent state or a core reducer contract, move it into embedagent_core.
If the imported object touches workspace files, process execution, HTTP, GUI, TUI, configuration, memory stores, project extensions, workflow packages, or concrete model clients, replace it with a port and inject the concrete implementation from embedagent_host.
If a test only asserts the old product import path, delete the assertion or the test file.
```

- [ ] **Step 3: Verify no old import paths remain in tests**

Run:

```bash
rg -n "from embedagent\\.(session|interaction|guard|tool_execution|compacted_history|llm)|import embedagent\\.(session|interaction|guard|tool_execution|compacted_history|llm)" tests src
```

Expected: no output.

- [ ] **Step 4: Verify the core boundary passes**

Run:

```bash
uv run pytest tests/test_core_package_imports.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit remaining boundary cleanup**

Run:

```bash
git add src tests
git commit -m "refactor: remove product imports from agent core"
```

---

## Task 9: Make Package Metadata Reflect The New Boundary

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`

- [ ] **Step 1: Update package metadata without adding dependencies**

In `pyproject.toml`, keep one installable distribution for this stage, but make the package split explicit:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["embedagent*", "embedagent_core*", "embedagent_host*"]
```

Keep dependencies unchanged. Do not add new extras in this stage.

- [ ] **Step 2: Document the current extraction status in README**

Add this paragraph to the architecture section of `README.md`:

```markdown
`embedagent_core` is the generic Agent Core package boundary. It does not import
the product package, host package, GUI, TUI, or workflow packages. Concrete
provider clients, workspace tools, stores, context assembly, and default
workflow composition live outside Core and are injected by `embedagent_host`.
```

- [ ] **Step 3: Update architecture docs**

In `docs/overall-solution-architecture.md`, update the Agent Core section to state:

```markdown
Agent Core is dependency-inverted: it owns turn state, transcript records,
reducers, permission contracts, extension dispatch, loop control, and abstract
ports. Host/product layers implement the ports. C/C++ workflow behavior is a
workflow package, not a Core dependency.
```

- [ ] **Step 4: Update roadmap**

In `docs/implementation-roadmap.md`, add the completed stage entry:

```markdown
### Agent Core Boundary Extraction

- `embedagent_core` no longer imports `embedagent`, `embedagent_host`, GUI/TUI,
  or workflow package modules.
- Product-owned concrete services are injected through Core ports.
- Deleted product-level compatibility paths are intentionally absent.
```

- [ ] **Step 5: Run docs and architecture verification**

Run:

```bash
uv run pytest tests/test_core_package_imports.py tests/test_current_architecture_boundaries.py tests/test_pre_release_architecture_guards.py -v
uv run --locked python scripts/lint.py
```

Expected: PASS.

- [ ] **Step 6: Commit docs and metadata**

Run:

```bash
git add pyproject.toml README.md docs/overall-solution-architecture.md docs/implementation-roadmap.md
git commit -m "docs: record agent core boundary extraction"
```

---

## Task 10: Run The Stage Gate

**Files:**
- No source edits unless a verification failure identifies a boundary violation.

- [ ] **Step 1: Run the pre-merge architecture gate**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_core_package_imports.py -v
```

Expected: PASS.

- [ ] **Step 2: Run the fast backend suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run --locked python scripts/lint.py
```

Expected: PASS.

- [ ] **Step 4: Inspect deleted-path evidence**

Run:

```bash
git status --short
rg -n "embedagent\\.(session|interaction|guard|tool_execution|compacted_history|llm)" src tests
rg -n "from embedagent import (session|interaction|guard|tool_execution|compacted_history|llm)" src tests
```

Expected: `git status --short` shows only intentional changes. The two `rg` commands produce no output.

- [ ] **Step 5: Commit final verification adjustments**

If no edits were needed after Task 9, skip this commit. If verification fixes were needed, run:

```bash
git add src tests README.md docs pyproject.toml
git commit -m "test: verify agent core boundary extraction"
```

---

## Follow-Up Plan Handoff

After this plan passes, write the next staged plan:

- `2026-07-03-workflow-package-contract-extraction.md`

That plan should remove product-level mode/tool activation assumptions from `embedagent.modes` and `embedagent.tools.runtime`, make workflow package manifests the only source for scenario-specific mode/tool metadata, and keep C/C++ behavior inside `src/embedagent/workflow_packages/c_cpp`.

## Self-Review

- Spec coverage: This plan covers the approved no-backward-compatibility rule, hard deletion of obsolete paths, Core independence, host dependency injection, and architecture/test gates.
- Placeholder scan: The plan contains no intentionally deferred implementation slots. Each task has exact files, exact commands, and concrete code blocks for new tests or new interfaces.
- Type consistency: `Action`, `Observation`, `AssistantReply`, and session records live in `embedagent_core.session`; model contracts live in `embedagent_core.model`; tool contracts live in `embedagent_core.tool_contracts`; host service protocols live in `embedagent_core.ports`; mode/path policies live in `embedagent_core.policies`.
