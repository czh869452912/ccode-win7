# Phase G Turn Snapshot Capability Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase G foundation: explicit frozen provider-request turn snapshots plus a small non-executing capability registry for tools, resources, commands, and model profiles.

**Architecture:** Add two focused core modules: `capabilities.py` owns a JSON-serializable read model, and `turn_snapshot.py` owns immutable provider-request inputs. Keep `ToolRuntime` execution, `ExtensionManager` activation, and `AgentLoop` orchestration intact; integrate snapshots inside `QueryEngine._call_provider_operation` so the provider consumes `snapshot.messages` and `snapshot.tool_schemas`.

**Tech Stack:** Python 3.8 dataclasses and standard library only, existing pytest/unittest suite, no new dependencies, no online runtime behavior.

---

## Source Spec

Read this first:

- `docs/superpowers/specs/2026-06-14-phase-g-turn-snapshot-capability-registry-design.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`

## File Structure

Create:

- `src/embedagent/capabilities.py`  
  Owns `CapabilityDescriptor`, `CapabilitySnapshot`, `CapabilityRegistry`, plus helper functions that project existing runtime, resource, slash-command, and model state into descriptors. It must not execute tools, load code, or choose active tools.

- `src/embedagent/turn_snapshot.py`  
  Owns `TurnSnapshot` and `TurnSnapshotBuilder`. It deep-copies provider request messages, tool schemas, runtime environment, capability projection, and context stats.

- `tests/test_capability_registry.py`  
  Unit tests for descriptor normalization, duplicate handling, serialization, and projections from `ToolRuntime`, local resources, slash commands, and a model profile.

- `tests/test_turn_snapshot.py`  
  Unit tests for snapshot copy semantics, deterministic active tool names, JSON serialization, and provider-safe payload fields.

Modify:

- `src/embedagent/query_engine.py`  
  Build a `CapabilityRegistry` projection and a `TurnSnapshot` before provider calls. Provider calls must consume the snapshot payload, and provider operation metadata/result should record only safe snapshot metadata.

- `src/embedagent/tools/runtime.py`  
  Add a read-only `capability_descriptors()` projection from the existing tool catalog and local resources. Do not change execution or schema filtering.

- `src/embedagent/slash_commands.py`  
  Add a read-only `capability_descriptors()` projection for slash commands.

- `src/embedagent/inprocess_adapter.py`  
  Add an adapter-owned capability snapshot helper that combines runtime tools/resources, slash commands, project extension summary, and model profile. Keep existing GUI bootstrap unchanged unless tests reveal a safe diagnostic-only field is useful.

- `tests/test_query_engine_refactor.py`  
  Add a narrow integration test that proves provider request operation metadata includes snapshot id/capability counts and that the client receives copied snapshot messages and schemas.

- `tests/test_inprocess_adapter_frontend_api.py` or `tests/test_local_resources.py`  
  Add a narrow adapter/runtime projection test if unit tests do not fully cover integrated command/resource/model projections.

- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/tool-contracts.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`
- `AGENTS.md` only if the final implemented vocabulary changes from the current constitution.

Do not modify:

- `uv.lock`
- `config/config.json`
- built GUI bundle files under `src/embedagent/frontend/gui/static/assets/` unless the source frontend changes, which Phase G should avoid.

## Task 1: Capability Registry Core

**Files:**

- Create: `tests/test_capability_registry.py`
- Create: `src/embedagent/capabilities.py`

- [ ] **Step 1: Write failing tests for descriptor registration, duplicate replacement, filtering, and serialization**

Create `tests/test_capability_registry.py` with this initial content:

```python
import json

from embedagent.capabilities import (
    CapabilityDescriptor,
    CapabilityRegistry,
)


def test_registry_registers_descriptors_and_serializes_snapshot():
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDescriptor(
            name="read_file",
            kind="tool",
            source_type="builtin",
            source_id="embedagent.core",
            metadata={"permission_category": "read"},
            active=True,
        )
    )
    registry.register(
        CapabilityDescriptor(
            name="review",
            kind="command",
            source_type="builtin",
            source_id="slash_commands",
            metadata={"usage": "/review"},
            active=False,
        )
    )

    snapshot = registry.snapshot()
    payload = snapshot.to_dict()

    assert payload["counts"] == {
        "command": 1,
        "model_profile": 0,
        "resource": 0,
        "tool": 1,
    }
    assert payload["active_names_by_kind"]["tool"] == ["read_file"]
    assert payload["active_names_by_kind"]["command"] == []
    assert payload["descriptors"][0]["kind"] == "command"
    assert payload["descriptors"][1]["kind"] == "tool"
    json.dumps(payload, sort_keys=True)


def test_registry_duplicate_key_replaces_descriptor_without_duplicate_row():
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDescriptor(
            name="read_file",
            kind="tool",
            source_type="builtin",
            source_id="embedagent.core",
            metadata={"version": 1},
            active=False,
        )
    )
    registry.register(
        CapabilityDescriptor(
            name="read_file",
            kind="tool",
            source_type="builtin",
            source_id="embedagent.core",
            metadata={"version": 2},
            active=True,
        )
    )

    payload = registry.snapshot().to_dict()

    assert len(payload["descriptors"]) == 1
    assert payload["descriptors"][0]["metadata"]["version"] == 2
    assert payload["descriptors"][0]["active"] is True


def test_registry_filters_by_kind_and_returns_copies():
    registry = CapabilityRegistry()
    registry.register(CapabilityDescriptor(name="read_file", kind="tool"))
    registry.register(CapabilityDescriptor(name="help", kind="command"))

    tools = registry.descriptors(kind="tool")
    tools[0].metadata["mutated"] = True

    assert [item.name for item in tools] == ["read_file"]
    assert "mutated" not in registry.descriptors(kind="tool")[0].metadata


def test_descriptor_normalizes_empty_source_and_metadata():
    descriptor = CapabilityDescriptor(
        name="  read_file  ",
        kind="  tool ",
        source_type="",
        source_id="",
        metadata=None,
        active=True,
    )

    assert descriptor.name == "read_file"
    assert descriptor.kind == "tool"
    assert descriptor.source_type == "runtime"
    assert descriptor.source_id == "runtime"
    assert descriptor.metadata == {}
```

- [ ] **Step 2: Run tests and verify the module is missing**

Run:

```bash
uv run pytest tests/test_capability_registry.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'embedagent.capabilities'
```

- [ ] **Step 3: Implement minimal registry core**

Create `src/embedagent/capabilities.py`:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

CAPABILITY_KINDS = ("command", "model_profile", "resource", "tool")


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return deepcopy(metadata)


@dataclass
class CapabilityDescriptor:
    name: str
    kind: str
    source_type: str = "runtime"
    source_id: str = "runtime"
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    active: bool = False

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name)
        self.kind = _clean_text(self.kind)
        self.source_type = _clean_text(self.source_type, "runtime")
        self.source_id = _clean_text(self.source_id, self.source_type)
        self.metadata = _safe_metadata(self.metadata)
        self.active = bool(self.active)
        if not self.name:
            raise ValueError("capability descriptor name is required")
        if not self.kind:
            raise ValueError("capability descriptor kind is required")

    def key(self) -> Tuple[str, str, str, str]:
        return (self.kind, self.name, self.source_type, self.source_id)

    def copy(self) -> "CapabilityDescriptor":
        return CapabilityDescriptor(
            name=self.name,
            kind=self.kind,
            source_type=self.source_type,
            source_id=self.source_id,
            metadata=deepcopy(self.metadata or {}),
            active=self.active,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "metadata": deepcopy(self.metadata or {}),
            "active": bool(self.active),
        }


@dataclass
class CapabilitySnapshot:
    descriptors: List[CapabilityDescriptor]

    def descriptors_for_kind(self, kind: str) -> List[CapabilityDescriptor]:
        normalized = _clean_text(kind)
        return [item.copy() for item in self.descriptors if item.kind == normalized]

    def counts(self) -> Dict[str, int]:
        payload = dict((kind, 0) for kind in CAPABILITY_KINDS)
        for item in self.descriptors:
            payload[item.kind] = int(payload.get(item.kind, 0)) + 1
        return payload

    def active_names_by_kind(self) -> Dict[str, List[str]]:
        payload = dict((kind, []) for kind in CAPABILITY_KINDS)
        for item in self.descriptors:
            if item.active:
                payload.setdefault(item.kind, []).append(item.name)
        for names in payload.values():
            names.sort()
        return payload

    def to_dict(self) -> Dict[str, Any]:
        ordered = sorted(
            [item.copy() for item in self.descriptors],
            key=lambda item: item.key(),
        )
        return {
            "descriptors": [item.to_dict() for item in ordered],
            "counts": self.counts(),
            "active_names_by_kind": self.active_names_by_kind(),
        }


class CapabilityRegistry(object):
    def __init__(self, descriptors: Optional[Iterable[CapabilityDescriptor]] = None) -> None:
        self._descriptors = {}  # type: Dict[Tuple[str, str, str, str], CapabilityDescriptor]
        for descriptor in list(descriptors or []):
            self.register(descriptor)

    def register(self, descriptor: CapabilityDescriptor) -> None:
        if not isinstance(descriptor, CapabilityDescriptor):
            raise ValueError("capability descriptor is required")
        self._descriptors[descriptor.key()] = descriptor.copy()

    def extend(self, descriptors: Iterable[CapabilityDescriptor]) -> None:
        for descriptor in list(descriptors or []):
            self.register(descriptor)

    def descriptors(self, kind: Optional[str] = None) -> List[CapabilityDescriptor]:
        normalized_kind = _clean_text(kind) if kind is not None else ""
        items = [item.copy() for item in self._descriptors.values()]
        if normalized_kind:
            items = [item for item in items if item.kind == normalized_kind]
        return sorted(items, key=lambda item: item.key())

    def snapshot(self) -> CapabilitySnapshot:
        return CapabilitySnapshot(self.descriptors())
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
uv run pytest tests/test_capability_registry.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/capabilities.py tests/test_capability_registry.py
git commit -m "feat: add capability registry core"
```

## Task 2: Capability Projections From Runtime, Resources, Commands, And Model Profile

**Files:**

- Modify: `tests/test_capability_registry.py`
- Modify: `src/embedagent/capabilities.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/slash_commands.py`
- Modify: `src/embedagent/inprocess_adapter.py`

- [ ] **Step 1: Add failing tests for projection helpers**

Append to `tests/test_capability_registry.py`:

```python
import os

from embedagent.capabilities import (
    command_capability_descriptors,
    model_profile_capability_descriptor,
    resource_capability_descriptors,
    runtime_tool_capability_descriptors,
)
from embedagent.slash_commands import SlashCommandRegistry
from embedagent.tools import ToolRuntime


def test_runtime_tool_capability_descriptors_project_tool_catalog(tmp_path):
    runtime = ToolRuntime(str(tmp_path))

    descriptors = runtime_tool_capability_descriptors(runtime)
    by_name = dict((item.name, item) for item in descriptors)

    assert "read_file" in by_name
    assert by_name["read_file"].kind == "tool"
    assert by_name["read_file"].source_type == "builtin"
    assert by_name["read_file"].source_id == "embedagent.core"
    assert by_name["read_file"].metadata["permission_category"] == "read"


def test_resource_capability_descriptors_project_local_resources(tmp_path):
    skill_dir = tmp_path / ".embedagent" / "skills"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "review.md"
    skill_path.write_text("# Review\n", encoding="utf-8")

    runtime = ToolRuntime(str(tmp_path))
    resources = runtime.reload_resources(reason="test")

    descriptors = resource_capability_descriptors(resources)

    assert [item.name for item in descriptors] == [".embedagent/skills/review.md"]
    assert descriptors[0].kind == "resource"
    assert descriptors[0].source_type == "local_resource"
    assert descriptors[0].source_id == "skill"
    assert descriptors[0].metadata["path"] == ".embedagent/skills/review.md"


def test_command_and_model_profile_descriptors_are_serializable():
    commands = command_capability_descriptors(SlashCommandRegistry())
    model = model_profile_capability_descriptor(
        {
            "model": "local-qwen",
            "base_url": "http://localhost:11434/v1",
            "api_key": "secret-value",
        }
    )
    registry = CapabilityRegistry(commands + [model])
    payload = registry.snapshot().to_dict()

    command_names = [item["name"] for item in payload["descriptors"] if item["kind"] == "command"]
    model_items = [item for item in payload["descriptors"] if item["kind"] == "model_profile"]

    assert "help" in command_names
    assert model_items[0]["name"] == "local-qwen"
    assert model_items[0]["metadata"]["base_url"] == "http://localhost:11434/v1"
    assert "api_key" not in model_items[0]["metadata"]
    json.dumps(payload, sort_keys=True)
```

- [ ] **Step 2: Run tests and verify helper imports fail**

Run:

```bash
uv run pytest tests/test_capability_registry.py -v
```

Expected:

```text
ImportError: cannot import name 'command_capability_descriptors'
```

- [ ] **Step 3: Implement projection helpers in `capabilities.py`**

Append these functions to `src/embedagent/capabilities.py`:

```python
def runtime_tool_capability_descriptors(runtime: Any) -> List[CapabilityDescriptor]:
    catalog = []
    catalog_method = getattr(runtime, "catalog_entries", None)
    if callable(catalog_method):
        catalog = list(catalog_method() or [])
    descriptors = []
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        name = _clean_text(entry.get("name"))
        if not name:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=name,
                kind="tool",
                source_type=_clean_text(entry.get("source_type"), "runtime"),
                source_id=_clean_text(entry.get("source_id"), "runtime"),
                metadata=dict(entry),
                active=False,
            )
        )
    return descriptors


def resource_capability_descriptors(resources: Dict[str, Any]) -> List[CapabilityDescriptor]:
    descriptors = []
    if not isinstance(resources, dict):
        return descriptors
    resource_groups = (
        ("skills", "skill", "path"),
        ("prompts", "prompt", "path"),
        ("recipes", "recipe", "id"),
    )
    for group_name, source_id, name_key in resource_groups:
        for item in list(resources.get(group_name) or []):
            if not isinstance(item, dict):
                continue
            name = _clean_text(item.get(name_key))
            if not name:
                continue
            metadata = dict(item)
            metadata["resource_group"] = group_name
            descriptors.append(
                CapabilityDescriptor(
                    name=name,
                    kind="resource",
                    source_type=_clean_text(item.get("source"), "local_resource"),
                    source_id=source_id,
                    metadata=metadata,
                    active=True,
                )
            )
    return sorted(descriptors, key=lambda item: item.key())


def command_capability_descriptors(command_registry: Any) -> List[CapabilityDescriptor]:
    specs_method = getattr(command_registry, "specs", None)
    specs = list(specs_method() or []) if callable(specs_method) else []
    descriptors = []
    for spec in specs:
        name = _clean_text(getattr(spec, "name", ""))
        if not name:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=name,
                kind="command",
                source_type="builtin",
                source_id="slash_commands",
                metadata={
                    "usage": str(getattr(spec, "usage", "") or ""),
                    "summary": str(getattr(spec, "summary", "") or ""),
                },
                active=True,
            )
        )
    return descriptors


def model_profile_capability_descriptor(config_or_client: Any) -> CapabilityDescriptor:
    model = ""
    base_url = ""
    if isinstance(config_or_client, dict):
        model = _clean_text(config_or_client.get("model"))
        base_url = _clean_text(config_or_client.get("base_url"))
    else:
        model = _clean_text(getattr(config_or_client, "model", ""))
        base_url = _clean_text(getattr(config_or_client, "base_url", ""))
    metadata = {}
    if base_url:
        metadata["base_url"] = base_url
    return CapabilityDescriptor(
        name=model or "default-model",
        kind="model_profile",
        source_type="configured",
        source_id="llm",
        metadata=metadata,
        active=True,
    )
```

- [ ] **Step 4: Add convenience methods to existing owners**

In `src/embedagent/tools/runtime.py`, add import:

```python
from embedagent.capabilities import (
    resource_capability_descriptors,
    runtime_tool_capability_descriptors,
)
```

Add methods after `local_resources()`:

```python
    def capability_descriptors(self) -> List[Any]:
        descriptors = runtime_tool_capability_descriptors(self)
        descriptors.extend(resource_capability_descriptors(self.local_resources()))
        return descriptors
```

In `src/embedagent/slash_commands.py`, add import:

```python
from embedagent.capabilities import command_capability_descriptors
```

Add method to `SlashCommandRegistry`:

```python
    def capability_descriptors(self):
        return command_capability_descriptors(self)
```

In `src/embedagent/inprocess_adapter.py`, import:

```python
from embedagent.capabilities import (
    CapabilityRegistry,
    command_capability_descriptors,
    model_profile_capability_descriptor,
)
```

Add this method after `_build_engine()`:

```python
    def capability_snapshot(self) -> Dict[str, Any]:
        registry = CapabilityRegistry()
        runtime_capabilities = getattr(self.tools, "capability_descriptors", None)
        if callable(runtime_capabilities):
            registry.extend(runtime_capabilities())
        registry.extend(command_capability_descriptors(self.command_registry))
        registry.register(model_profile_capability_descriptor(self.client))
        return registry.snapshot().to_dict()
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_capability_registry.py -v
```

Expected:

```text
7 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/capabilities.py src/embedagent/tools/runtime.py src/embedagent/slash_commands.py src/embedagent/inprocess_adapter.py tests/test_capability_registry.py
git commit -m "feat: project runtime capabilities"
```

## Task 3: Turn Snapshot Core

**Files:**

- Create: `tests/test_turn_snapshot.py`
- Create: `src/embedagent/turn_snapshot.py`

- [ ] **Step 1: Write failing snapshot tests**

Create `tests/test_turn_snapshot.py`:

```python
import json

from embedagent.turn_snapshot import TurnSnapshotBuilder


def test_turn_snapshot_builder_copies_provider_inputs_and_sorts_active_tools():
    messages = [{"role": "user", "content": "hello", "nested": {"x": 1}}]
    tool_schemas = [{"type": "function", "function": {"name": "write_file"}}]
    capabilities = {"counts": {"tool": 1}, "descriptors": []}

    snapshot = TurnSnapshotBuilder().build(
        session_id="sess-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="build",
        workflow_state="chat",
        messages=messages,
        tool_schemas=tool_schemas,
        active_tool_names=["write_file", "read_file", "read_file"],
        model_profile={"name": "local-qwen"},
        runtime_environment={"python": "3.8"},
        capabilities=capabilities,
        context_stats={"approx_tokens": 42},
    )

    messages[0]["nested"]["x"] = 99
    tool_schemas[0]["function"]["name"] = "mutated"
    capabilities["counts"]["tool"] = 99

    assert snapshot.snapshot_id.startswith("ts-")
    assert snapshot.messages[0]["nested"]["x"] == 1
    assert snapshot.tool_schemas[0]["function"]["name"] == "write_file"
    assert snapshot.active_tool_names == ["read_file", "write_file"]
    assert snapshot.capabilities["counts"]["tool"] == 1
    assert snapshot.context_stats["approx_tokens"] == 42


def test_turn_snapshot_to_dict_is_json_serializable_and_provider_safe():
    snapshot = TurnSnapshotBuilder().build(
        session_id="sess-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="verify",
        workflow_state="review",
        messages=[{"role": "system", "content": "safe"}],
        tool_schemas=[],
        active_tool_names=[],
        model_profile={"name": "default-model"},
        runtime_environment={},
        capabilities={"counts": {}, "descriptors": []},
        context_stats={},
    )

    payload = snapshot.to_dict()
    json.dumps(payload, sort_keys=True)

    assert payload["session_id"] == "sess-1"
    assert payload["mode_name"] == "verify"
    assert payload["workflow_state"] == "review"
    assert payload["messages"] == [{"role": "system", "content": "safe"}]
    assert payload["tool_schemas"] == []
    assert payload["model_profile"] == {"name": "default-model"}
```

- [ ] **Step 2: Run tests and verify module is missing**

Run:

```bash
uv run pytest tests/test_turn_snapshot.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'embedagent.turn_snapshot'
```

- [ ] **Step 3: Implement `TurnSnapshot` and builder**

Create `src/embedagent/turn_snapshot.py`:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _copy_dict(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _copy_list(value: Optional[List[Any]]) -> List[Any]:
    if not isinstance(value, list):
        return []
    return deepcopy(value)


def _stable_names(names: Optional[List[str]]) -> List[str]:
    seen = set()
    result = []
    for name in list(names or []):
        text = str(name or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return sorted(result)


@dataclass
class TurnSnapshot:
    snapshot_id: str
    session_id: str
    turn_id: str
    step_id: str
    mode_name: str
    workflow_state: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_schemas: List[Dict[str, Any]] = field(default_factory=list)
    active_tool_names: List[str] = field(default_factory=list)
    model_profile: Dict[str, Any] = field(default_factory=dict)
    runtime_environment: Dict[str, Any] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    context_stats: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        self.snapshot_id = str(self.snapshot_id or "").strip() or ("ts-" + uuid.uuid4().hex[:12])
        self.session_id = str(self.session_id or "").strip()
        self.turn_id = str(self.turn_id or "").strip()
        self.step_id = str(self.step_id or "").strip()
        self.mode_name = str(self.mode_name or "").strip()
        self.workflow_state = str(self.workflow_state or "").strip() or "chat"
        self.messages = _copy_list(self.messages)
        self.tool_schemas = _copy_list(self.tool_schemas)
        self.active_tool_names = _stable_names(self.active_tool_names)
        self.model_profile = _copy_dict(self.model_profile)
        self.runtime_environment = _copy_dict(self.runtime_environment)
        self.capabilities = _copy_dict(self.capabilities)
        self.context_stats = _copy_dict(self.context_stats)
        self.created_at = str(self.created_at or "").strip() or _utc_now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "mode_name": self.mode_name,
            "workflow_state": self.workflow_state,
            "messages": deepcopy(self.messages),
            "tool_schemas": deepcopy(self.tool_schemas),
            "active_tool_names": list(self.active_tool_names),
            "model_profile": deepcopy(self.model_profile),
            "runtime_environment": deepcopy(self.runtime_environment),
            "capabilities": deepcopy(self.capabilities),
            "context_stats": deepcopy(self.context_stats),
            "created_at": self.created_at,
        }


class TurnSnapshotBuilder(object):
    def build(
        self,
        session_id: str,
        turn_id: str,
        step_id: str,
        mode_name: str,
        workflow_state: str,
        messages: List[Dict[str, Any]],
        tool_schemas: List[Dict[str, Any]],
        active_tool_names: Optional[List[str]] = None,
        model_profile: Optional[Dict[str, Any]] = None,
        runtime_environment: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        context_stats: Optional[Dict[str, Any]] = None,
    ) -> TurnSnapshot:
        return TurnSnapshot(
            snapshot_id="ts-" + uuid.uuid4().hex[:12],
            session_id=session_id,
            turn_id=turn_id,
            step_id=step_id,
            mode_name=mode_name,
            workflow_state=workflow_state,
            messages=messages,
            tool_schemas=tool_schemas,
            active_tool_names=active_tool_names or [],
            model_profile=model_profile or {},
            runtime_environment=runtime_environment or {},
            capabilities=capabilities or {},
            context_stats=context_stats or {},
        )
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
uv run pytest tests/test_turn_snapshot.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/turn_snapshot.py tests/test_turn_snapshot.py
git commit -m "feat: add turn snapshot core"
```

## Task 4: Provider Request Consumes TurnSnapshot

**Files:**

- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Add failing integration test**

Append this client and test near existing provider operation lifecycle tests in `tests/test_query_engine_refactor.py`:

```python
class SnapshotInspectingClient(object):
    def __init__(self):
        self.messages = []
        self.tools = []

    def generate(self, messages, tools=None):
        self.messages.append(messages)
        self.tools.append(tools or [])
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        return reply


    def test_provider_request_consumes_turn_snapshot_and_records_safe_metadata(self):
        transcript_store = TranscriptStore(self.workspace)
        client = SnapshotInspectingClient()
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
            transcript_store=transcript_store,
            max_turns=1,
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="检查项目",
            stream=False,
            initial_mode="build",
            session=session,
        )

        snapshot = engine.last_turn_snapshot()
        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(len(client.messages), 1)
        self.assertIsNotNone(snapshot)
        self.assertEqual(client.messages[0], snapshot.messages)
        self.assertEqual(client.tools[0], snapshot.tool_schemas)
        self.assertIn("read_file", snapshot.active_tool_names)

        events = transcript_store.load_events(session.session_id)
        started = [
            item["payload"]
            for item in events
            if item["type"] == "operation_started"
            and item["payload"].get("kind") == "provider_request"
        ]
        finished = [
            item["payload"]
            for item in events
            if item["type"] == "operation_finished"
            and item["payload"].get("kind") == "provider_request"
        ]

        metadata = started[0]["metadata"]
        result_payload = finished[0]["result"]

        self.assertTrue(metadata["turn_snapshot"]["snapshot_id"].startswith("ts-"))
        self.assertEqual(
            metadata["turn_snapshot"]["active_tool_names"],
            sorted(snapshot.active_tool_names),
        )
        self.assertIn("capability_counts", metadata["turn_snapshot"])
        self.assertEqual(
            result_payload["turn_snapshot"]["snapshot_id"],
            metadata["turn_snapshot"]["snapshot_id"],
        )
        self.assertNotIn("messages", metadata["turn_snapshot"])
        self.assertNotIn("tool_schemas", metadata["turn_snapshot"])
```

- [ ] **Step 2: Run the single failing test**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py -k "turn_snapshot" -v
```

Expected:

```text
AttributeError: 'QueryEngine' object has no attribute 'last_turn_snapshot'
```

- [ ] **Step 3: Import snapshot and capability helpers**

In `src/embedagent/query_engine.py`, add imports:

```python
from embedagent.capabilities import (
    CapabilityRegistry,
    model_profile_capability_descriptor,
    resource_capability_descriptors,
    runtime_tool_capability_descriptors,
)
from embedagent.turn_snapshot import TurnSnapshot, TurnSnapshotBuilder
```

- [ ] **Step 4: Initialize snapshot builder and storage**

In `QueryEngine.__init__`, after `self._llm_wrapper = ...`, add:

```python
        self._turn_snapshot_builder = TurnSnapshotBuilder()
        self._last_turn_snapshot = None  # type: Optional[TurnSnapshot]
```

Add public diagnostic accessor after `stop()`:

```python
    def last_turn_snapshot(self) -> Optional[TurnSnapshot]:
        return self._last_turn_snapshot
```

- [ ] **Step 5: Add helper methods in `QueryEngine`**

Add these methods before `_call_provider_operation`:

```python
    def _active_tool_names_from_schemas(self, tool_schemas: list) -> list:
        names = []
        for schema in list(tool_schemas or []):
            if not isinstance(schema, dict):
                continue
            function = schema.get("function")
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "").strip()
            if name:
                names.append(name)
        return sorted(set(names))

    def _capability_snapshot_for_provider(self, active_tool_names: list) -> Dict[str, Any]:
        registry = CapabilityRegistry()
        registry.extend(runtime_tool_capability_descriptors(self.tools))
        local_resources = {}
        local_resources_method = getattr(self.tools, "local_resources", None)
        if callable(local_resources_method):
            local_resources = local_resources_method()
        registry.extend(resource_capability_descriptors(local_resources))
        registry.register(model_profile_capability_descriptor(self.client))

        active_set = set(active_tool_names or [])
        for descriptor in registry.descriptors(kind="tool"):
            descriptor.active = descriptor.name in active_set
            registry.register(descriptor)
        return registry.snapshot().to_dict()

    def _model_profile_snapshot(self) -> Dict[str, Any]:
        descriptor = model_profile_capability_descriptor(self.client)
        return {
            "name": descriptor.name,
            "source_type": descriptor.source_type,
            "source_id": descriptor.source_id,
            "metadata": dict(descriptor.metadata or {}),
        }

    def _context_stats_for_snapshot(self, messages: list) -> Dict[str, Any]:
        return {
            "message_count": len(messages or []),
        }

    def _turn_snapshot_metadata(self, snapshot: TurnSnapshot) -> Dict[str, Any]:
        capabilities = dict(snapshot.capabilities or {})
        return {
            "snapshot_id": snapshot.snapshot_id,
            "mode_name": snapshot.mode_name,
            "workflow_state": snapshot.workflow_state,
            "active_tool_names": list(snapshot.active_tool_names),
            "model_profile": dict(snapshot.model_profile or {}),
            "capability_counts": dict(capabilities.get("counts") or {}),
        }
```

- [ ] **Step 6: Build snapshot before operation metadata and call provider through it**

At the start of `_call_provider_operation`, before `_emit_operation_started(...)`, add:

```python
        active_tool_names = self._active_tool_names_from_schemas(tool_schemas)
        capabilities = self._capability_snapshot_for_provider(active_tool_names)
        snapshot = self._turn_snapshot_builder.build(
            session_id=session.session_id,
            turn_id=turn_id,
            step_id=step_id,
            mode_name=current_mode,
            workflow_state=workflow_state,
            messages=messages,
            tool_schemas=tool_schemas,
            active_tool_names=active_tool_names,
            model_profile=self._model_profile_snapshot(),
            runtime_environment=self.tools.runtime_environment_snapshot(),
            capabilities=capabilities,
            context_stats=self._context_stats_for_snapshot(messages),
        )
        self._last_turn_snapshot = snapshot
        snapshot_metadata = self._turn_snapshot_metadata(snapshot)
```

Update provider operation metadata fields:

```python
                "message_count": len(snapshot.messages),
                "tool_schema_count": len(snapshot.tool_schemas),
                "stream": bool(stream),
                "turn_snapshot": snapshot_metadata,
```

Update the provider call:

```python
            reply = self._call_llm_with_retry(
                snapshot.messages,
                snapshot.tool_schemas,
                stream,
                on_text_delta,
                on_reasoning_delta,
            )
```

Update successful operation result:

```python
            result=dict(
                self._provider_operation_result(reply),
                turn_snapshot=snapshot_metadata,
            ),
```

- [ ] **Step 7: Run the single integration test**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py -k "turn_snapshot" -v
```

Expected:

```text
1 passed
```

- [ ] **Step 8: Run related focused suites**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py tests/test_dynamic_tool_registration.py tests/test_workflow_extensions.py -v
```

Expected:

```text
passed
```

- [ ] **Step 9: Commit**

```bash
git add src/embedagent/query_engine.py tests/test_query_engine_refactor.py
git commit -m "feat: route provider requests through turn snapshots"
```

## Task 5: Adapter Capability Snapshot And Resource Integration

**Files:**

- Modify: `tests/test_local_resources.py`
- Modify: `src/embedagent/inprocess_adapter.py` if Task 2 did not already add the method

- [ ] **Step 1: Add failing adapter capability snapshot test**

Append to `tests/test_local_resources.py`:

```python
    def test_adapter_capability_snapshot_combines_tools_resources_commands_and_model(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage\n",
        )
        client = FakeClient()
        client.model = "local-test-model"
        client.base_url = "http://localhost:11434/v1"
        adapter = InProcessAdapter(
            client=client,
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
        )
        adapter.reload_resources(reason="test")

        payload = adapter.capability_snapshot()
        by_kind = {}
        for item in payload["descriptors"]:
            by_kind.setdefault(item["kind"], []).append(item)

        self.assertTrue(any(item["name"] == "read_file" for item in by_kind["tool"]))
        self.assertTrue(any(item["name"] == ".embedagent/prompts/triage.md" for item in by_kind["resource"]))
        self.assertTrue(any(item["name"] == "help" for item in by_kind["command"]))
        self.assertEqual(by_kind["model_profile"][0]["name"], "local-test-model")
        self.assertIn("tool", payload["counts"])
        self.assertIn("resource", payload["counts"])
```

- [ ] **Step 2: Run the test and verify failure if method is missing or resource projection is incomplete**

Run:

```bash
uv run pytest tests/test_local_resources.py -k "capability_snapshot" -v
```

Expected before implementation:

```text
AttributeError: 'InProcessAdapter' object has no attribute 'capability_snapshot'
```

If Task 2 already added `capability_snapshot`, expected failure may instead be an assertion about missing prompt resources. Fix only the failing projection path.

- [ ] **Step 3: Ensure adapter method uses loaded local resources**

If Task 2 did not add it, add to `src/embedagent/inprocess_adapter.py` after `_build_engine()`:

```python
    def capability_snapshot(self) -> Dict[str, Any]:
        registry = CapabilityRegistry()
        runtime_capabilities = getattr(self.tools, "capability_descriptors", None)
        if callable(runtime_capabilities):
            registry.extend(runtime_capabilities())
        registry.extend(command_capability_descriptors(self.command_registry))
        registry.register(model_profile_capability_descriptor(self.client))
        return registry.snapshot().to_dict()
```

If the test fails because resources are stale, ensure `ToolRuntime.capability_descriptors()` calls `self.local_resources()` rather than reading a cached external payload:

```python
    def capability_descriptors(self) -> List[Any]:
        descriptors = runtime_tool_capability_descriptors(self)
        descriptors.extend(resource_capability_descriptors(self.local_resources()))
        return descriptors
```

- [ ] **Step 4: Run resource and registry tests**

Run:

```bash
uv run pytest tests/test_capability_registry.py tests/test_local_resources.py -v
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/inprocess_adapter.py src/embedagent/tools/runtime.py tests/test_local_resources.py tests/test_capability_registry.py
git commit -m "feat: expose adapter capability snapshot"
```

## Task 6: Documentation Closeout

**Files:**

- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `AGENTS.md` only if terms require synchronization
- Move: `docs/superpowers/specs/2026-06-14-phase-g-turn-snapshot-capability-registry-design.md`
- Move: `docs/superpowers/plans/2026-06-14-phase-g-turn-snapshot-capability-registry.md`

- [ ] **Step 1: Update source-of-truth docs with final Phase G shape**

Use these exact statements as the durable wording base, adapted to each document's existing section style:

```markdown
Phase G adds two Agent Core read-model foundations:

- `TurnSnapshot` is the explicit frozen provider-request input. `QueryEngine` builds it after context assembly and active tool schema projection; the provider request consumes `snapshot.messages` and `snapshot.tool_schemas`.
- `CapabilityRegistry` is a non-executing read model for tools, local file resources, slash commands, and model profiles. Registration records provenance and metadata, but activation still belongs to `ExtensionManager`/`AgentExtensionHost`, and execution still belongs to `ToolRuntime`/`AgentToolActionService`.

Snapshot diagnostics may record `snapshot_id`, mode/workflow state, active tool names, model profile metadata without credentials, and capability counts. They must not record full prompt bodies, file contents, raw tool outputs, or API keys.
```

In `docs/implementation-roadmap.md`, mark Phase G complete and add the next phase candidate:

```markdown
Next candidate: durable runtime configuration reducer for active capability state, model profile selection, and local resource revision metadata.
```

In `docs/design-change-log.md`, add a dated entry:

```markdown
## 2026-06-14 - Phase G Turn Snapshot And Capability Registry

- Added explicit turn snapshots as the provider-request boundary.
- Added a minimal capability registry read model for tools, resources, slash commands, and model profiles.
- Preserved offline/Windows 7 constraints and kept activation/execution ownership unchanged.
```

- [ ] **Step 2: Archive completed slice docs**

Create archive directory:

```bash
mkdir -p docs/archive/phase-g-turn-snapshot-capability-registry
```

Move files:

```bash
git mv docs/superpowers/specs/2026-06-14-phase-g-turn-snapshot-capability-registry-design.md docs/archive/phase-g-turn-snapshot-capability-registry/
git mv docs/superpowers/plans/2026-06-14-phase-g-turn-snapshot-capability-registry.md docs/archive/phase-g-turn-snapshot-capability-registry/
```

On PowerShell, use:

```powershell
New-Item -ItemType Directory -Force docs\archive\phase-g-turn-snapshot-capability-registry
git mv docs\superpowers\specs\2026-06-14-phase-g-turn-snapshot-capability-registry-design.md docs\archive\phase-g-turn-snapshot-capability-registry\
git mv docs\superpowers\plans\2026-06-14-phase-g-turn-snapshot-capability-registry.md docs\archive\phase-g-turn-snapshot-capability-registry\
```

- [ ] **Step 3: Run documentation grep checks**

Run:

```bash
rg -n "TurnSnapshot|CapabilityRegistry|turn snapshot|capability registry" AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md docs/tool-contracts.md docs/frontend-protocol.md docs/agent-harness-v2.md
```

Expected:

```text
matches in active source-of-truth docs
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md docs/tool-contracts.md docs/frontend-protocol.md docs/agent-harness-v2.md docs/archive/phase-g-turn-snapshot-capability-registry
git commit -m "docs: close phase g architecture notes"
```

## Task 7: Final Verification

**Files:**

- No source edits unless verification finds a real defect.

- [ ] **Step 1: Run focused Phase G tests**

Run:

```bash
uv run pytest tests/test_capability_registry.py tests/test_turn_snapshot.py tests/test_query_engine_refactor.py tests/test_dynamic_tool_registration.py tests/test_workflow_extensions.py tests/test_local_resources.py -v
```

Expected:

```text
passed
```

- [ ] **Step 2: Run harness component tests**

Run:

```bash
uv run pytest tests/ -m harness -v
```

Expected:

```text
passed
```

- [ ] **Step 3: Run fast suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected:

```text
passed
```

- [ ] **Step 4: Run lint checks**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
```

Expected:

```text
All checks passed!
All done! ... files would be left unchanged.
```

- [ ] **Step 5: Inspect git status and history**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected:

```text
## codex/phase-g-turn-snapshot-capability-registry
```

with only intentional Phase G commits in the recent history.

## Self-Review

Spec coverage:

- Explicit `TurnSnapshot`: Task 3.
- Provider request consumes snapshot: Task 4.
- Minimal `CapabilityRegistry`: Task 1.
- Tools/resources/commands/model profile read model: Tasks 2 and 5.
- Activation remains ExtensionManager/AgentExtensionHost: Task 4 records active schema results only and does not select tools in `TurnSnapshot`.
- Execution remains ToolRuntime/AgentToolActionService: Tasks 1-5 add read projections only.
- Offline, Windows 7, Python 3.8: all code uses standard library, no new dependencies, no Python 3.9+ syntax.
- Safe diagnostics only: Task 4 metadata records ids/counts/names, not full prompts or credentials.
- Docs synchronized and slice docs archived: Task 6.

Placeholder scan:

- No placeholder markers or vague edge-case steps.
- All code-changing steps include concrete code blocks.
- Commands include expected outcomes.

Type consistency:

- `CapabilityDescriptor`, `CapabilitySnapshot`, `CapabilityRegistry`, `TurnSnapshot`, and `TurnSnapshotBuilder` names match across tests and implementation steps.
- Helper names are consistent: `runtime_tool_capability_descriptors`, `resource_capability_descriptors`, `command_capability_descriptors`, `model_profile_capability_descriptor`.
- `QueryEngine.last_turn_snapshot()` returns `Optional[TurnSnapshot]`.
