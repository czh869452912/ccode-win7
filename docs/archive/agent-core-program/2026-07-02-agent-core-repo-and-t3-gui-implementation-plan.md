# Agent Core Repository Split And T3 GUI Implementation Plan

> **Superseded:** This broad plan is superseded by the staged plans starting with
> `docs/superpowers/plans/2026-07-03-agent-core-boundary-extraction.md`.
> The older document reflects an earlier repository shape and must not be used
> as the execution checklist for current work.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current C/C++-shaped product internals with a generic Agent Core, explicit host/workflow package assembly, and a T3 Code-style GUI contract that is driven by backend capabilities and durable activities.

**Architecture:** Build the new contract first, then make interaction state activity-ledger based, then remove GUI hardcoding, then move the C/C++ harness into a first-party workflow package boundary. The promoted path becomes the only supported path; obsolete reducers, compatibility shims, stale tests, misleading filenames, and raw transport-driven GUI behavior are deleted instead of patched.

**Tech Stack:** Python 3.8-only standard-library typing/dataclasses, existing FastAPI backend routes, existing JavaScript module tests under the Vite webapp, existing pytest suite, existing npm build pipeline, no new runtime dependencies.

---

## Execution Covenant

- Do not preserve old internal contracts.
- Do not add compatibility aliases, feature flags, dual reducers, or fallback bootstrap formats.
- When a test asserts an obsolete path, delete that test case or replace the file with a new contract test in the same commit that removes the code path.
- Keep Python syntax valid for Python 3.8: no `match`, no `:=`, no `dict | dict`, no built-in generic aliases.
- Keep offline and Windows 7 requirements intact: no Docker, WSL, VS Code, online services, runtime dependency installation, or new runtime dependency unless it is already in `pyproject.toml`.
- Generated GUI static assets under `src/embedagent/frontend/gui/static/` must be rebuilt and committed whenever webapp source changes.
- Each task ends with a small commit. Do not batch unrelated phases into one commit.

## Source References

- Design spec: `docs/superpowers/specs/2026-07-02-agent-core-repo-and-t3-gui-design.md`
- Product constitution: `AGENTS.md`
- Current architecture: `docs/overall-solution-architecture.md`
- Current roadmap: `docs/implementation-roadmap.md`
- Pi reference: `reference/pi/packages/agent/`
- T3 Code reference: `reference/t3code/`

## File Structure Map

### New Protocol Modules

- Create `src/embedagent/protocol/app_protocol.py`
  - Sole Python source for Agent App Protocol v1 dataclasses and normalizers.
  - Owns app bootstrap, capability, thread shell, thread detail, activity, command, and stream item shapes.
- Modify `src/embedagent/protocol/__init__.py`
  - Re-export only promoted protocol types.
  - Do not re-export GUI backend serializer helpers.
- Create `tests/test_agent_app_protocol.py`
  - Verifies protocol normalization, no legacy timeline fields, no C/C++ assumptions, and JSON-safe payloads.

### Backend Projection

- Modify `src/embedagent/frontend/gui/backend/protocol_payloads.py`
  - Replace ad hoc serializers with calls into `embedagent.protocol.app_protocol`.
  - Keep this file as GUI backend route glue only.
- Modify `src/embedagent/frontend/gui/backend/routes_app.py`
  - Return app-shell bootstrap only.
  - Add capability metadata for app surfaces and empty-state copy.
- Modify `src/embedagent/frontend/gui/backend/routes_sessions.py`
  - Return protocol-shaped thread detail bootstrap.
  - Keep `GET /api/sessions/{id}/bootstrap` as session activation truth.
- Modify `tests/test_gui_backend_api.py`
  - Replace assertions for legacy snapshot fields with protocol-shaped assertions.
  - Delete cases that expect response snapshots to be enough to close GUI interactions.

### Interaction Ledger

- Modify `src/embedagent/frontend/gui/backend/session_events.py`
  - Map Core events to canonical activity kinds:
    - `approval.requested`
    - `approval.resolved`
    - `approval.response.failed`
    - `user-input.requested`
    - `user-input.resolved`
    - `user-input.response.failed`
- Modify `src/embedagent/agent_lifecycle.py`
  - Ensure pending interaction lifecycle events contain enough safe payload for protocol activities.
- Modify `src/embedagent/agent_kernel.py`
  - Keep pending interaction creation/resolution as Core boundary.
  - Do not expose GUI-specific payloads from Core.
- Modify `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - Remove renderer effects for raw `permission_request` and `user_input_request`.
  - Accept only backend-owned `session_event` messages for timeline/composer state.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js`
  - Add reducer actions for canonical interaction activities.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
  - Derive the current composer interaction from open activity records.
- Modify `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
  - Delete raw request reload assertions.
  - Add canonical activity event tests.
- Modify `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`
  - Replace snapshot-pending interaction input tests with activity-ledger input tests.

### Dynamic GUI Capabilities

- Create `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`
  - Converts backend protocol payloads into camelCase client runtime state.
- Create `src/embedagent/frontend/gui/webapp/src/session-runtime/tool-presentation.js`
  - Resolves tool labels/icons/renderers from backend tool metadata with generic fallback.
- Modify `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - Remove hardcoded mode list.
  - Build commands from backend capability metadata.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js`
  - Normalize backend commands, modes, and workflow commands from one capability payload.
- Modify `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`
  - Use protocol-provided empty-state copy and scenario label.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - Use `tool-presentation.js` metadata before any generic fallback.
  - Remove direct C/C++ workflow tool labels.
- Modify `src/embedagent/frontend/gui/webapp/src/store.js`
  - Remove hardcoded C/C++ tool title map.
  - Keep only reducer state plumbing that consumes normalized capability data.
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Replace `.mode-explore`, `.mode-spec`, `.mode-build`, `.mode-debug`, `.mode-verify` color rules with data-driven CSS variables applied by components.
- Create `src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs`
  - Verifies a fake Python/HTML workflow package can drive modes, commands, tool labels, and empty-state text.
- Modify `src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs`
  - Add capability-driven mode command tests.
- Modify `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - Replace C-specific tool label expectations with metadata and fallback expectations.

### Workflow Package Boundary

- Create package directory `src/embedagent/workflow_packages/`
- Create `src/embedagent/workflow_packages/__init__.py`
- Create `src/embedagent/workflow_packages/c_cpp/`
- Move `src/embedagent/harness/*.py` into `src/embedagent/workflow_packages/c_cpp/`
- Delete `src/embedagent/harness/`
  - Do not leave re-export files or import aliases.
- Modify `src/embedagent/default_extensions.py`
  - Move C/C++ default assembly into host/product composition.
  - Keep generic Core free of direct C/C++ imports.
- Modify tests importing `embedagent.harness.*`
  - Replace with `embedagent.workflow_packages.c_cpp.*` where the test is still a C/C++ workflow package test.
  - Delete tests that only asserted old harness import locations or compatibility paths.
- Modify `tests/test_current_architecture_boundaries.py`
  - Add import guards preventing Core from importing `embedagent.workflow_packages.c_cpp`, GUI backend, or webapp modules.

### Package Split Preparation

- Create `src/embedagent_core/` only after protocol, GUI, and workflow package boundaries pass.
- Create `src/embedagent_host/` only after `embedagent_core` imports are clean.
- Move generic runtime modules from `src/embedagent/` into `src/embedagent_core/`.
- Move hosted app/session/server composition modules into `src/embedagent_host/`.
- Leave `src/embedagent/` as the product entry package only if it contains no compatibility re-exports; product entry modules may import core, host, GUI, and workflow packages explicitly.
- Modify `pyproject.toml`
  - Change product description away from C/C++-only framing.
  - Keep Python `>=3.8,<3.9`.
  - Do not add dependencies.

---

## Task 1: Add Agent App Protocol V1

**Files:**
- Create: `src/embedagent/protocol/app_protocol.py`
- Modify: `src/embedagent/protocol/__init__.py`
- Create: `tests/test_agent_app_protocol.py`

- [ ] **Step 1: Write failing protocol tests**

Add `tests/test_agent_app_protocol.py`:

```python
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.protocol import (
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    InteractionActivity,
    ModeDescriptor,
    ThreadDetailSnapshot,
    ThreadShell,
    ToolPresentation,
    WorkflowPackageDescriptor,
)


class AgentAppProtocolTests(unittest.TestCase):
    def test_capability_snapshot_is_json_safe_and_backend_declared(self):
        snapshot = CapabilitySnapshot(
            modes=[
                ModeDescriptor(
                    id="python-build",
                    label="Python Build",
                    description="Implement Python changes",
                    icon_key="hammer",
                    color_token="success",
                    command_id="mode.python-build",
                )
            ],
            commands=[
                CommandDescriptor(
                    id="mode.python-build",
                    label="Python Build",
                    group="mode",
                    dispatch={"kind": "mode.set", "mode": "python-build"},
                )
            ],
            tools=[
                ToolPresentation(
                    name="pytest",
                    label="Pytest",
                    icon_key="test-tube",
                    renderer_key="command",
                    permission_category="command",
                )
            ],
            workflow_packages=[
                WorkflowPackageDescriptor(
                    id="workflow-python",
                    label="Python",
                    active=True,
                    state={"phase": "test"},
                )
            ],
            resources=[],
            model_profiles=[],
            empty_state={
                "scenario_label": "Python workspace",
                "primary": "Choose a local workspace",
                "secondary": "The selected scenario defines tools and modes.",
            },
        )

        payload = snapshot.to_dict()

        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["modes"][0]["id"], "python-build")
        self.assertEqual(payload["tools"][0]["label"], "Pytest")
        self.assertNotIn("todos", json.dumps(payload))
        self.assertNotIn("harness", json.dumps(payload).lower())
        json.dumps(payload)

    def test_thread_detail_contains_activities_not_timeline_replay(self):
        detail = ThreadDetailSnapshot(
            thread=ThreadShell(
                id="sess-1",
                title="Parser repair",
                archived=False,
                current_mode="python-build",
                status="waiting_permission",
                updated_at="2026-07-02T10:00:00Z",
                pending_interaction=True,
            ),
            snapshot={"session_id": "sess-1", "status": "waiting_permission"},
            activities=[
                InteractionActivity(
                    id="act-1",
                    kind="approval.requested",
                    request_id="perm-1",
                    turn_id="turn-1",
                    created_at="2026-07-02T10:00:00Z",
                    payload={
                        "requestKind": "file-change",
                        "toolName": "edit_file",
                        "summary": "Edit src/parser.py",
                    },
                )
            ],
            capabilities=CapabilitySnapshot(),
            workflow={"package_id": "workflow-python"},
            integrity={"status": "healthy"},
        )

        payload = detail.to_dict()

        self.assertEqual(payload["history"]["activities"][0]["kind"], "approval.requested")
        self.assertNotIn("timeline", payload)
        self.assertNotIn("turns", payload["history"])
        json.dumps(payload)

    def test_app_bootstrap_does_not_include_session_history(self):
        bootstrap = AppBootstrap(
            app={"name": "EmbedAgent"},
            workspaces=[],
            commands=[CommandDescriptor(id="app.open", label="Open", group="app")],
            surfaces=[{"id": "chat", "label": "Chat"}],
            diagnostics={"offline": True},
        )

        payload = bootstrap.to_dict()

        self.assertIn("app", payload)
        self.assertNotIn("history", payload)
        self.assertNotIn("snapshot", payload)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run:

```bash
uv run pytest tests/test_agent_app_protocol.py -v
```

Expected: FAIL because `AppBootstrap`, `CapabilitySnapshot`, and related protocol types are not exported.

- [ ] **Step 3: Create the protocol dataclasses**

Create `src/embedagent/protocol/app_protocol.py` with these public types and helpers:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


@dataclass
class ModeDescriptor:
    id: str
    label: str
    description: str = ""
    icon_key: str = ""
    color_token: str = ""
    command_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "iconKey": self.icon_key,
            "colorToken": self.color_token,
            "commandId": self.command_id,
        }


@dataclass
class CommandDescriptor:
    id: str
    label: str
    group: str
    dispatch: Dict[str, Any] = field(default_factory=dict)
    shortcut: str = ""
    availability: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "group": self.group,
            "dispatch": _dict(self.dispatch),
            "shortcut": self.shortcut,
            "availability": _dict(self.availability),
        }


@dataclass
class ToolPresentation:
    name: str
    label: str
    icon_key: str = ""
    renderer_key: str = "generic"
    permission_category: str = "other"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "iconKey": self.icon_key,
            "rendererKey": self.renderer_key,
            "permissionCategory": self.permission_category,
            "metadata": _dict(self.metadata),
        }


@dataclass
class WorkflowPackageDescriptor:
    id: str
    label: str
    active: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "active": bool(self.active),
            "state": _dict(self.state),
            "metadata": _dict(self.metadata),
        }


@dataclass
class CapabilitySnapshot:
    version: int = 1
    modes: List[ModeDescriptor] = field(default_factory=list)
    commands: List[CommandDescriptor] = field(default_factory=list)
    tools: List[ToolPresentation] = field(default_factory=list)
    workflow_packages: List[WorkflowPackageDescriptor] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    model_profiles: List[Dict[str, Any]] = field(default_factory=list)
    empty_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": int(self.version),
            "modes": [item.to_dict() for item in self.modes],
            "commands": [item.to_dict() for item in self.commands],
            "tools": [item.to_dict() for item in self.tools],
            "workflowPackages": [item.to_dict() for item in self.workflow_packages],
            "resources": [_dict(item) for item in self.resources],
            "modelProfiles": [_dict(item) for item in self.model_profiles],
            "emptyState": _dict(self.empty_state),
        }


@dataclass
class ThreadShell:
    id: str
    title: str
    archived: bool
    current_mode: str
    status: str
    updated_at: str
    pending_interaction: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "archived": bool(self.archived),
            "currentMode": self.current_mode,
            "status": self.status,
            "updatedAt": self.updated_at,
            "pendingInteraction": bool(self.pending_interaction),
        }


@dataclass
class InteractionActivity:
    id: str
    kind: str
    request_id: str
    turn_id: str
    created_at: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "requestId": self.request_id,
            "turnId": self.turn_id,
            "createdAt": self.created_at,
            "payload": _dict(self.payload),
        }


@dataclass
class ThreadDetailSnapshot:
    thread: ThreadShell
    snapshot: Dict[str, Any]
    activities: List[Any]
    capabilities: CapabilitySnapshot
    workflow: Dict[str, Any] = field(default_factory=dict)
    integrity: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        activity_payloads = []
        for item in self.activities:
            activity_payloads.append(item.to_dict() if hasattr(item, "to_dict") else _dict(item))
        return {
            "thread": self.thread.to_dict(),
            "snapshot": _dict(self.snapshot),
            "history": {
                "activities": activity_payloads,
                "integrity": _dict(self.integrity),
            },
            "capabilities": self.capabilities.to_dict(),
            "workflow": _dict(self.workflow),
        }


@dataclass
class AppBootstrap:
    app: Dict[str, Any]
    workspaces: List[Dict[str, Any]]
    commands: List[CommandDescriptor]
    surfaces: List[Dict[str, Any]]
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app": _dict(self.app),
            "workspaces": [_dict(item) for item in self.workspaces],
            "commands": [item.to_dict() for item in self.commands],
            "surfaces": [_dict(item) for item in self.surfaces],
            "diagnostics": _dict(self.diagnostics),
        }
```

- [ ] **Step 4: Export the protocol types**

Modify `src/embedagent/protocol/__init__.py` to include:

```python
from embedagent.protocol.app_protocol import (
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    InteractionActivity,
    ModeDescriptor,
    ThreadDetailSnapshot,
    ThreadShell,
    ToolPresentation,
    WorkflowPackageDescriptor,
)
```

Keep any existing exports that are still promoted contracts. Do not export old GUI serializer helpers.

- [ ] **Step 5: Run protocol tests**

Run:

```bash
uv run pytest tests/test_agent_app_protocol.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/protocol/app_protocol.py src/embedagent/protocol/__init__.py tests/test_agent_app_protocol.py
git commit -m "feat: add agent app protocol contracts"
```

---

## Task 2: Project Backend Bootstrap Through The Protocol

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_app.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Modify: `tests/test_gui_backend_api.py`
- Create: `tests/test_gui_protocol_projection.py`

- [ ] **Step 1: Add failing backend projection tests**

Create `tests/test_gui_protocol_projection.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.protocol_payloads import (
    serialize_app_bootstrap,
    serialize_session_bootstrap,
)


class GuiProtocolProjectionTests(unittest.TestCase):
    def test_session_bootstrap_uses_protocol_history_activities_only(self):
        payload = serialize_session_bootstrap(
            {
                "snapshot": {"session_id": "sess-1", "status": "idle", "current_mode": "python"},
                "history": {
                    "activities": [{"id": "a1", "kind": "user", "content": "hi"}],
                    "turns": [{"id": "legacy-turn"}],
                },
                "capabilities": {
                    "modes": [{"id": "python", "label": "Python", "commandId": "mode.python"}],
                    "commands": [{"id": "mode.python", "label": "Python", "group": "mode"}],
                    "tools": [{"name": "pytest", "label": "Pytest"}],
                    "emptyState": {"scenario_label": "Python workspace"},
                },
            }
        )

        self.assertEqual(payload["thread"]["id"], "sess-1")
        self.assertEqual(payload["history"]["activities"][0]["kind"], "user")
        self.assertNotIn("turns", payload["history"])
        self.assertNotIn("timeline", payload)
        self.assertEqual(payload["capabilities"]["modes"][0]["id"], "python")

    def test_app_bootstrap_is_app_shell_only(self):
        payload = serialize_app_bootstrap(
            {
                "app": {"name": "EmbedAgent"},
                "workspaces": [{"id": "ws-1", "label": "demo"}],
                "commands": [{"id": "app.open", "label": "Open", "group": "app"}],
                "surfaces": [{"id": "chat", "label": "Chat"}],
                "diagnostics": {"offline": True},
                "history": {"activities": []},
            }
        )

        self.assertEqual(payload["app"]["name"], "EmbedAgent")
        self.assertNotIn("history", payload)
        self.assertNotIn("snapshot", payload)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new projection tests and confirm they fail**

Run:

```bash
uv run pytest tests/test_gui_protocol_projection.py -v
```

Expected: FAIL because `serialize_app_bootstrap` and `serialize_session_bootstrap` do not exist.

- [ ] **Step 3: Implement route-level protocol serializers**

Modify `src/embedagent/frontend/gui/backend/protocol_payloads.py`:

```python
from embedagent.protocol import (
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    ModeDescriptor,
    ThreadDetailSnapshot,
    ThreadShell,
    ToolPresentation,
    WorkflowPackageDescriptor,
)
```

Add helper functions:

```python
def _capability_snapshot(data):
    data = data if isinstance(data, dict) else {}
    return CapabilitySnapshot(
        modes=[
            ModeDescriptor(
                id=str(item.get("id") or item.get("name") or ""),
                label=str(item.get("label") or item.get("name") or ""),
                description=str(item.get("description") or ""),
                icon_key=str(item.get("iconKey") or item.get("icon_key") or ""),
                color_token=str(item.get("colorToken") or item.get("color_token") or ""),
                command_id=str(item.get("commandId") or item.get("command_id") or ""),
            )
            for item in list(data.get("modes") or [])
            if isinstance(item, dict) and (item.get("id") or item.get("name"))
        ],
        commands=[
            CommandDescriptor(
                id=str(item.get("id") or item.get("name") or ""),
                label=str(item.get("label") or item.get("usage") or item.get("name") or ""),
                group=str(item.get("group") or item.get("source_type") or "command"),
                dispatch=dict(item.get("dispatch") or {}),
                shortcut=str(item.get("shortcut") or ""),
                availability=dict(item.get("availability") or {}),
            )
            for item in list(data.get("commands") or [])
            if isinstance(item, dict) and (item.get("id") or item.get("name"))
        ],
        tools=[
            ToolPresentation(
                name=str(item.get("name") or ""),
                label=str(item.get("label") or item.get("name") or ""),
                icon_key=str(item.get("iconKey") or item.get("icon_key") or ""),
                renderer_key=str(item.get("rendererKey") or item.get("renderer_key") or "generic"),
                permission_category=str(
                    item.get("permissionCategory") or item.get("permission_category") or "other"
                ),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in list(data.get("tools") or [])
            if isinstance(item, dict) and item.get("name")
        ],
        workflow_packages=[
            WorkflowPackageDescriptor(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or item.get("id") or ""),
                active=bool(item.get("active")),
                state=dict(item.get("state") or {}),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in list(data.get("workflowPackages") or data.get("workflow_packages") or [])
            if isinstance(item, dict) and item.get("id")
        ],
        resources=list(data.get("resources") or []),
        model_profiles=list(data.get("modelProfiles") or data.get("model_profiles") or []),
        empty_state=dict(data.get("emptyState") or data.get("empty_state") or {}),
    )
```

Add promoted serializers:

```python
def serialize_app_bootstrap(payload):
    data = payload if isinstance(payload, dict) else {}
    bootstrap = AppBootstrap(
        app=dict(data.get("app") or {}),
        workspaces=list(data.get("workspaces") or []),
        commands=[
            CommandDescriptor(
                id=str(item.get("id") or item.get("name") or ""),
                label=str(item.get("label") or item.get("usage") or item.get("name") or ""),
                group=str(item.get("group") or "app"),
                dispatch=dict(item.get("dispatch") or {}),
            )
            for item in list(data.get("commands") or [])
            if isinstance(item, dict) and (item.get("id") or item.get("name"))
        ],
        surfaces=list(data.get("surfaces") or []),
        diagnostics=dict(data.get("diagnostics") or {}),
    )
    return bootstrap.to_dict()


def serialize_session_bootstrap(payload):
    data = payload if isinstance(payload, dict) else {}
    snapshot = dict(data.get("snapshot") or {})
    session_id = str(snapshot.get("session_id") or data.get("session_id") or "")
    thread_data = data.get("thread") if isinstance(data.get("thread"), dict) else {}
    history = data.get("history") if isinstance(data.get("history"), dict) else {}
    detail = ThreadDetailSnapshot(
        thread=ThreadShell(
            id=session_id,
            title=str(thread_data.get("title") or snapshot.get("title") or session_id),
            archived=bool(thread_data.get("archived")),
            current_mode=str(snapshot.get("current_mode") or ""),
            status=str(snapshot.get("status") or ""),
            updated_at=str(snapshot.get("updated_at") or snapshot.get("created_at") or ""),
            pending_interaction=bool(snapshot.get("pending_interaction_valid")),
        ),
        snapshot=snapshot,
        activities=list(history.get("activities") or []),
        capabilities=_capability_snapshot(data.get("capabilities") or {}),
        workflow=dict(snapshot.get("workflow_state") or data.get("workflow") or {}),
        integrity=dict(history.get("integrity") or {}),
    )
    return detail.to_dict()
```

- [ ] **Step 4: Wire routes to the promoted serializers**

In `src/embedagent/frontend/gui/backend/routes_app.py`, pass the existing app-shell payload through `serialize_app_bootstrap`.

In `src/embedagent/frontend/gui/backend/routes_sessions.py`, pass the session bootstrap payload through `serialize_session_bootstrap`.

Delete route logic that re-adds `history.turns`, flat timeline fields, or event-list replay fields.

- [ ] **Step 5: Update backend API tests**

In `tests/test_gui_backend_api.py`:

- Replace `self.assertIn("snapshot", payload)` for the bootstrap route with `self.assertIn("thread", payload)` and `self.assertIn("history", payload)`.
- Assert `payload["history"]` contains `activities` and does not contain `turns`.
- Delete `test_post_interaction_response_emits_backend_owned_resolved_event` because response routes must not be tested by observing absent broadcast side effects; interaction closure is covered by canonical activity events in Task 3.

- [ ] **Step 6: Run backend projection tests**

Run:

```bash
uv run pytest tests/test_gui_protocol_projection.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/embedagent/frontend/gui/backend/protocol_payloads.py src/embedagent/frontend/gui/backend/routes_app.py src/embedagent/frontend/gui/backend/routes_sessions.py tests/test_gui_protocol_projection.py tests/test_gui_backend_api.py
git commit -m "feat: project gui bootstrap through app protocol"
```

---

## Task 3: Promote Interaction Activities As The Only GUI Truth

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/session_events.py`
- Modify: `src/embedagent/agent_lifecycle.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/activity-state.test.mjs`
- Modify: `tests/test_agent_lifecycle.py`

- [ ] **Step 1: Replace raw request tests with canonical activity event tests**

In `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`, delete the current `permission_request` and `user_input_request` cases that expect `LOAD_SESSION`.

Add these cases:

```javascript
  const approvalRequested = derive("session_event", {
    event_id: "evt-approval",
    seq: 7,
    event_kind: "approval.requested",
    payload: {
      request_id: "perm-1",
      interaction_id: "perm-1",
      turn_id: "turn-1",
      tool_name: "edit_file",
      request_kind: "file-change",
      summary: "Edit src/demo.c",
      details: { path: "src/demo.c" },
    },
  });
  assert.equal(approvalRequested.actions[0].type, "interaction_requested");
  assert.equal(approvalRequested.actions[0].kind, "approval.requested");
  assert.equal(approvalRequested.actions[0].requestId, "perm-1");
  assert.equal(approvalRequested.actions[0].payload.toolName, "edit_file");
  assert.deepEqual(approvalRequested.loaderRequests, []);

  const userInputRequested = derive("session_event", {
    event_id: "evt-user-input",
    seq: 8,
    event_kind: "user-input.requested",
    payload: {
      request_id: "ask-1",
      interaction_id: "ask-1",
      turn_id: "turn-1",
      questions: [{ id: "answer", question: "Continue?", options: [{ index: 1, label: "Yes" }] }],
    },
  });
  assert.equal(userInputRequested.actions[0].type, "interaction_requested");
  assert.equal(userInputRequested.actions[0].kind, "user-input.requested");
  assert.equal(userInputRequested.actions[0].requestId, "ask-1");
  assert.deepEqual(userInputRequested.loaderRequests, []);

  const rawPermissionIgnored = derive("permission_request", {
    permission_id: "perm-raw",
    reason: "Transport-only request",
  });
  assert.deepEqual(rawPermissionIgnored.actions, []);
  assert.deepEqual(rawPermissionIgnored.transportEvents, []);
  assert.deepEqual(rawPermissionIgnored.loaderRequests, []);
```

- [ ] **Step 2: Add reducer tests for open and resolved interaction activities**

In `src/embedagent/frontend/gui/webapp/test/activity-state.test.mjs`, add:

```javascript
  let state = reduceActivityState(createActivityState(), {
    type: "interaction_requested",
    id: "evt-approval",
    kind: "approval.requested",
    requestId: "perm-1",
    turnId: "turn-1",
    createdAt: "2026-07-02T10:00:00.000Z",
    payload: { summary: "Edit src/demo.c", toolName: "edit_file" },
  });
  assert.equal(state.activities[0].kind, "interaction");
  assert.equal(state.activities[0].sourceActivityKind, "approval.requested");
  assert.equal(state.activities[0].requestId, "perm-1");
  assert.equal(state.activities[0].status, "pending");

  state = reduceActivityState(state, {
    type: "interaction_resolved",
    id: "evt-approval-resolved",
    kind: "approval.resolved",
    requestId: "perm-1",
    turnId: "turn-1",
    createdAt: "2026-07-02T10:01:00.000Z",
    payload: { decision: "accept" },
  });
  assert.equal(state.activities[0].status, "resolved");
  assert.equal(state.activities[0].resolvedAt, "2026-07-02T10:01:00.000Z");
```

- [ ] **Step 3: Run frontend tests and confirm they fail**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- --run socket-message-effects activity-state
```

Expected: FAIL because the socket effect and reducer actions do not exist.

- [ ] **Step 4: Map backend event kinds**

Modify `_GUI_EVENT_KIND_MAP` in `src/embedagent/frontend/gui/backend/session_events.py`:

```python
_GUI_EVENT_KIND_MAP = {
    "turn_start": "turn.started",
    "turn_end": "transition.recorded",
    "step_start": "step.started",
    "step_end": "step.finished",
    "tool_started": "tool.started",
    "tool_finished": "tool.finished",
    "permission_required": "approval.requested",
    "permission_resolved": "approval.resolved",
    "permission_response_failed": "approval.response.failed",
    "user_input_required": "user-input.requested",
    "user_input_resolved": "user-input.resolved",
    "user_input_response_failed": "user-input.response.failed",
    "session_finished": "session.finished",
    "session_error": "session.error",
}
```

Normalize payload keys in `build_session_event` before returning:

```python
def _interaction_payload(event_name, payload):
    if event_name not in (
        "permission_required",
        "permission_resolved",
        "permission_response_failed",
        "user_input_required",
        "user_input_resolved",
        "user_input_response_failed",
    ):
        return dict(payload)
    data = dict(payload)
    request_id = (
        data.get("request_id")
        or data.get("permission_id")
        or data.get("interaction_id")
        or ""
    )
    data["request_id"] = str(request_id)
    data["interaction_id"] = str(data.get("interaction_id") or request_id)
    data["turn_id"] = str(data.get("turn_id") or "")
    return data
```

Use `_interaction_payload(event_name, event_payload)` as the returned `payload`.

- [ ] **Step 5: Remove raw request renderer effects**

In `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`, delete the branches for:

```javascript
if (type === "permission_request") { ... }
if (type === "user_input_request") { ... }
```

Add session event handling:

```javascript
if (eventKind === "approval.requested" || eventKind === "user-input.requested") {
  actions.push({
    type: "interaction_requested",
    id: eventId,
    kind: eventKind,
    requestId: String(payload?.request_id || payload?.interaction_id || ""),
    turnId: String(payload?.turn_id || ""),
    createdAt,
    payload: normalizeInteractionPayload(payload),
  });
}
if (
  eventKind === "approval.resolved" ||
  eventKind === "approval.response.failed" ||
  eventKind === "user-input.resolved" ||
  eventKind === "user-input.response.failed"
) {
  actions.push({
    type: "interaction_resolved",
    id: eventId,
    kind: eventKind,
    requestId: String(payload?.request_id || payload?.interaction_id || ""),
    turnId: String(payload?.turn_id || ""),
    createdAt,
    payload: normalizeInteractionPayload(payload),
  });
}
```

Add helper:

```javascript
function normalizeInteractionPayload(payload = {}) {
  return {
    requestKind: text(payload.request_kind || payload.requestKind),
    toolName: text(payload.tool_name || payload.toolName),
    summary: text(payload.summary || payload.reason || payload.question),
    reason: text(payload.reason),
    details: payload.details && typeof payload.details === "object" ? payload.details : {},
    questions: Array.isArray(payload.questions) ? payload.questions : [],
    decision: text(payload.decision),
    answer: text(payload.answer || payload.selected_option_text),
    error: text(payload.error || payload.detail),
  };
}
```

- [ ] **Step 6: Add reducer support**

In `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js`, add cases:

```javascript
    case "interaction_requested":
      return {
        ...state,
        activities: upsertActivityItem(
          state.activities,
          {
            id: action.id || makeEventId("interaction"),
            kind: "interaction",
            sourceActivityKind: action.kind,
            requestId: action.requestId || "",
            status: "pending",
            content: action.payload?.summary || "",
            turnId: action.turnId || state.activeTurnId,
            createdAt: action.createdAt || "",
            payload: action.payload || {},
            ...liveProjectionMeta(),
          },
          (item) => item.kind === "interaction" && item.requestId === action.requestId,
        ),
      };
    case "interaction_resolved":
      return {
        ...state,
        activities: upsertActivityItem(
          state.activities,
          {
            id: action.id || makeEventId("interaction"),
            kind: "interaction",
            sourceActivityKind: action.kind,
            requestId: action.requestId || "",
            status: action.kind && action.kind.indexOf("failed") >= 0 ? "error" : "resolved",
            content: action.payload?.summary || action.payload?.error || "",
            turnId: action.turnId || state.activeTurnId,
            resolvedAt: action.createdAt || "",
            payload: action.payload || {},
            ...liveProjectionMeta(),
          },
          (item) => item.kind === "interaction" && item.requestId === action.requestId,
        ),
      };
```

Add both action types to `ACTIVITY_ACTION_TYPES`.

- [ ] **Step 7: Run focused frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- --run socket-message-effects activity-state
```

Expected: PASS.

- [ ] **Step 8: Run backend interaction tests**

Run:

```bash
uv run pytest tests/test_agent_lifecycle.py tests/test_gui_backend_api.py -v
```

Expected: PASS after updating expectations from `interaction.created` to canonical activity kinds.

- [ ] **Step 9: Commit**

```bash
git add src/embedagent/frontend/gui/backend/session_events.py src/embedagent/agent_lifecycle.py src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs src/embedagent/frontend/gui/webapp/test/activity-state.test.mjs tests/test_agent_lifecycle.py tests/test_gui_backend_api.py
git commit -m "feat: make gui interactions activity-ledger driven"
```

---

## Task 4: Derive Composer Pending State From Activities

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/composer-interaction-model.test.mjs`

- [ ] **Step 1: Write failing activity-derived interaction tests**

In `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`, replace the direct snapshot input setup with:

```javascript
  const activities = [
    {
      id: "act-approval",
      kind: "interaction",
      sourceActivityKind: "approval.requested",
      requestId: "perm-1",
      status: "pending",
      turnId: "turn-1",
      payload: {
        requestKind: "file-change",
        toolName: "edit_file",
        summary: "File-change approval requested",
        reason: "Edit src/demo.c",
        details: { path: "src/demo.c" },
      },
    },
  ];
  const permission = currentInteractionFromActivities(activities);
  assert.equal(permission.kind, "permission");
  assert.equal(permission.interactionId, "perm-1");
  assert.equal(permission.summary, "File-change approval requested");
```

Add a resolution test:

```javascript
  const closed = currentInteractionFromActivities([
    activities[0],
    {
      id: "act-approval-resolved",
      kind: "interaction",
      sourceActivityKind: "approval.resolved",
      requestId: "perm-1",
      status: "resolved",
      payload: { decision: "accept" },
    },
  ]);
  assert.equal(closed, null);
```

- [ ] **Step 2: Run focused tests and confirm they fail**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- --run interaction-model composer-interaction-model
```

Expected: FAIL because `currentInteractionFromActivities` does not exist.

- [ ] **Step 3: Implement activity-derived selector**

In `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`, add:

```javascript
export function currentInteractionFromActivities(activities = []) {
  const records = Array.isArray(activities) ? activities : [];
  const resolved = new Set();
  for (const item of records) {
    if (
      item?.kind === "interaction" &&
      item?.requestId &&
      (item.status === "resolved" || item.status === "error" || String(item.sourceActivityKind || "").endsWith(".resolved"))
    ) {
      resolved.add(item.requestId);
    }
  }
  for (let index = records.length - 1; index >= 0; index -= 1) {
    const item = records[index];
    if (!item || item.kind !== "interaction" || item.status !== "pending") continue;
    if (!item.requestId || resolved.has(item.requestId)) continue;
    const sourceKind = String(item.sourceActivityKind || "");
    if (sourceKind === "approval.requested") {
      return normalizeComposerInteraction({
        interaction_id: item.requestId,
        kind: "permission",
        tool_name: item.payload?.toolName,
        category: item.payload?.permissionCategory,
        reason: item.payload?.reason || item.payload?.summary,
        details: item.payload?.details || {},
        request_kind: item.payload?.requestKind,
      });
    }
    if (sourceKind === "user-input.requested") {
      return normalizeComposerInteraction({
        interaction_id: item.requestId,
        kind: "user_input",
        tool_name: item.payload?.toolName || "ask_user",
        questions: Array.isArray(item.payload?.questions) ? item.payload.questions : [],
      });
    }
  }
  return null;
}
```

- [ ] **Step 4: Remove snapshot-pending interaction as composer truth**

Where composer state currently passes `snapshot.pending_interaction` into `normalizeComposerInteraction`, replace it with `currentInteractionFromActivities(state.activities)`.

Keep backend snapshots carrying `pending_interaction_valid` only as diagnostics and thread-list status; do not use it to render composer cards.

- [ ] **Step 5: Run frontend interaction tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- --run interaction-model composer-interaction-model composer-state
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs src/embedagent/frontend/gui/webapp/test/composer-interaction-model.test.mjs src/embedagent/frontend/gui/webapp/test/composer-state.test.mjs
git commit -m "feat: derive composer interactions from activities"
```

---

## Task 5: Make GUI Modes, Commands, Tools, And Empty State Backend-Declared

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/tool-presentation.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Create: `src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`

- [ ] **Step 1: Add fake non-C capability tests**

Create `src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs`:

```javascript
import assert from "node:assert/strict";

import { normalizeProtocolCapabilities } from "../src/session-runtime/protocol-normalizer.js";
import { toolPresentationFor } from "../src/session-runtime/tool-presentation.js";

export function runProtocolNormalizerTests() {
  const capabilities = normalizeProtocolCapabilities({
    modes: [
      {
        id: "html-build",
        label: "HTML Build",
        description: "Create frontend pages",
        iconKey: "layout-template",
        colorToken: "success",
        commandId: "mode.html-build",
      },
    ],
    commands: [
      {
        id: "mode.html-build",
        label: "HTML Build",
        group: "mode",
        dispatch: { kind: "mode.set", mode: "html-build" },
      },
    ],
    tools: [
      {
        name: "open_preview",
        label: "Open Preview",
        iconKey: "monitor",
        rendererKey: "preview",
        permissionCategory: "network",
      },
    ],
    emptyState: {
      scenario_label: "HTML workspace",
      primary: "Choose a local frontend workspace",
      secondary: "Modes and tools come from the selected backend package.",
    },
  });

  assert.equal(capabilities.modes[0].id, "html-build");
  assert.equal(capabilities.commands[0].dispatch.mode, "html-build");
  assert.equal(capabilities.emptyState.scenarioLabel, "HTML workspace");

  const preview = toolPresentationFor("open_preview", capabilities.toolCatalog);
  assert.equal(preview.label, "Open Preview");
  assert.equal(preview.rendererKey, "preview");

  const fallback = toolPresentationFor("unknown_tool", capabilities.toolCatalog);
  assert.equal(fallback.label, "unknown_tool");
  assert.equal(fallback.rendererKey, "generic");
}
```

- [ ] **Step 2: Register the new webapp test runner export**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, import and run `runProtocolNormalizerTests`.

- [ ] **Step 3: Run the new test and confirm it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- --run protocol-normalizer
```

Expected: FAIL because the new modules do not exist.

- [ ] **Step 4: Implement capability normalization**

Create `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`:

```javascript
function text(value) {
  return String(value || "").trim();
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function normalizeProtocolCapabilities(input = {}) {
  const modes = Array.isArray(input.modes)
    ? input.modes.map((item) => ({
        id: text(item.id),
        label: text(item.label || item.id),
        description: text(item.description),
        iconKey: text(item.iconKey),
        colorToken: text(item.colorToken),
        commandId: text(item.commandId),
      })).filter((item) => item.id)
    : [];
  const commands = Array.isArray(input.commands)
    ? input.commands.map((item) => ({
        id: text(item.id || item.name),
        label: text(item.label || item.usage || item.name),
        group: text(item.group || "command"),
        dispatch: object(item.dispatch),
        shortcut: text(item.shortcut),
        availability: object(item.availability),
      })).filter((item) => item.id)
    : [];
  const tools = Array.isArray(input.tools)
    ? input.tools.map((item) => ({
        name: text(item.name),
        label: text(item.label || item.name),
        iconKey: text(item.iconKey),
        rendererKey: text(item.rendererKey || "generic"),
        permissionCategory: text(item.permissionCategory || "other"),
        metadata: object(item.metadata),
      })).filter((item) => item.name)
    : [];
  const toolCatalog = {};
  for (const tool of tools) toolCatalog[tool.name] = tool;
  const emptyStateInput = object(input.emptyState);
  return {
    modes,
    commands,
    tools,
    toolCatalog,
    workflowPackages: Array.isArray(input.workflowPackages) ? input.workflowPackages : [],
    emptyState: {
      scenarioLabel: text(emptyStateInput.scenario_label || emptyStateInput.scenarioLabel),
      primary: text(emptyStateInput.primary),
      secondary: text(emptyStateInput.secondary),
    },
  };
}
```

Create `src/embedagent/frontend/gui/webapp/src/session-runtime/tool-presentation.js`:

```javascript
function text(value) {
  return String(value || "").trim();
}

export function toolPresentationFor(toolName, catalog = {}) {
  const name = text(toolName);
  const item = catalog && typeof catalog === "object" ? catalog[name] : null;
  if (item) {
    return {
      name,
      label: text(item.label || name),
      iconKey: text(item.iconKey),
      rendererKey: text(item.rendererKey || "generic"),
      permissionCategory: text(item.permissionCategory || "other"),
      metadata: item.metadata && typeof item.metadata === "object" ? item.metadata : {},
    };
  }
  return {
    name,
    label: name,
    iconKey: "",
    rendererKey: "generic",
    permissionCategory: "other",
    metadata: {},
  };
}
```

- [ ] **Step 5: Replace hardcoded workbench modes**

In `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`, delete the static mode list and expose a builder:

```javascript
export function buildModeCommandsFromCapabilities(capabilities = {}) {
  const modes = Array.isArray(capabilities.modes) ? capabilities.modes : [];
  return modes.map((mode) => ({
    id: mode.commandId || `mode:${mode.id}`,
    group: "mode",
    label: mode.label,
    description: mode.description,
    iconKey: mode.iconKey,
    dispatch: { kind: "mode.set", mode: mode.id },
    visibleWhen: "hasSession",
  }));
}
```

Call this builder from the existing command palette assembly instead of the hardcoded five-mode array.

- [ ] **Step 6: Replace C/C++ tool label maps**

In `src/embedagent/frontend/gui/webapp/src/store.js`, delete the hardcoded label map for `run_recipe`, `report_quality_v2`, `task_status`, and `record_failing_evidence`.

In `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`, call `toolPresentationFor(item.toolName, toolCatalog)` before deriving display labels. Keep generic file, shell, and diff renderers only when chosen by metadata or by safe generic fallback.

- [ ] **Step 7: Make empty state copy dynamic**

In `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`, replace hardcoded C/C++ text with props:

```javascript
const scenarioLabel = emptyState?.scenarioLabel || "workspace";
const primary = emptyState?.primary || "Choose a local workspace";
const secondary = emptyState?.secondary || "The selected backend package defines modes, tools, and workflow behavior.";
```

Render `primary`, `secondary`, and `scenarioLabel`. Do not include C/C++ wording in this component.

- [ ] **Step 8: Replace mode CSS classes with CSS variables**

In `src/embedagent/frontend/gui/webapp/src/styles.css`, delete:

```css
.mode-badge.mode-explore { ... }
.mode-badge.mode-spec { ... }
.mode-badge.mode-build { ... }
.mode-badge.mode-debug { ... }
.mode-badge.mode-verify { ... }
```

Use:

```css
.mode-badge {
  color: var(--mode-color, var(--text-secondary));
  background: var(--mode-bg, rgba(255,255,255,.06));
  border-color: var(--mode-border, var(--border-default));
}
```

Set the CSS variables from the mode descriptor in the component that renders the badge.

- [ ] **Step 9: Run focused GUI capability tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- --run protocol-normalizer command-capabilities t3-timeline
```

Expected: PASS.

- [ ] **Step 10: Build static GUI assets**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: build succeeds and updates `src/embedagent/frontend/gui/static/`.

- [ ] **Step 11: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js src/embedagent/frontend/gui/webapp/src/session-runtime/tool-presentation.js src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static
git commit -m "feat: drive gui capabilities from backend metadata"
```

---

## Task 6: Move C/C++ Harness Into A Workflow Package

**Files:**
- Create: `src/embedagent/workflow_packages/__init__.py`
- Create: `src/embedagent/workflow_packages/c_cpp/`
- Move: `src/embedagent/harness/*.py` to `src/embedagent/workflow_packages/c_cpp/`
- Delete: `src/embedagent/harness/`
- Modify: `src/embedagent/default_extensions.py`
- Modify: `tests/test_workflow_package_manifest.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify: `tests/test_harness_*.py`
- Modify: `tests/test_task_graph_v2.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] **Step 1: Add failing import-boundary tests**

In `tests/test_current_architecture_boundaries.py`, add:

```python
def test_core_does_not_import_c_cpp_workflow_package():
    import ast
    import os

    root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent")
    forbidden = (
        "embedagent.workflow_packages.c_cpp",
        "embedagent.harness",
    )
    core_files = (
        "agent_kernel.py",
        "agent_loop.py",
        "agent_tool_action_service.py",
        "agent_extension_host.py",
        "agent_lifecycle.py",
        "turn_snapshot.py",
    )
    offenders = []
    for filename in core_files:
        path = os.path.join(root, filename)
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=filename)
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = ",".join(alias.name for alias in node.names)
            if any(item in module for item in forbidden):
                offenders.append((filename, module))
    assert offenders == []
```

Add:

```python
def test_obsolete_harness_package_path_is_removed():
    import importlib

    try:
        importlib.import_module("embedagent.harness")
    except ImportError:
        return
    raise AssertionError("embedagent.harness must be deleted, not kept as a compatibility alias")
```

- [ ] **Step 2: Run boundary tests and confirm they fail**

Run:

```bash
uv run pytest tests/test_current_architecture_boundaries.py -v
```

Expected: FAIL while `embedagent.harness` still exists.

- [ ] **Step 3: Move the package files**

Move all files from `src/embedagent/harness/` to `src/embedagent/workflow_packages/c_cpp/`.

Update internal imports:

```python
from embedagent.workflow_packages.c_cpp.task_graph import TaskGraph
from embedagent.workflow_packages.c_cpp.extension import CHarnessWorkflowExtension
from embedagent.workflow_packages.c_cpp.package_manifest import C_CPP_WORKFLOW_PACKAGE_ID
```

Delete `src/embedagent/harness/` entirely after imports are updated. Do not leave `__init__.py`, alias modules, or re-export stubs.

- [ ] **Step 4: Rename tests that still validate the C/C++ package**

For tests that validate the still-supported C/C++ workflow behavior, rename files from `test_harness_*.py` to `test_c_cpp_workflow_*.py`.

Examples:

```bash
git mv tests/test_harness_contracts.py tests/test_c_cpp_workflow_contracts.py
git mv tests/test_harness_mode_contract.py tests/test_c_cpp_workflow_mode_contract.py
git mv tests/test_harness_runner_taskgraph.py tests/test_c_cpp_workflow_runner_taskgraph.py
git mv tests/test_harness_task_projection.py tests/test_c_cpp_workflow_task_projection.py
```

Inside each renamed test, replace `embedagent.harness` imports with `embedagent.workflow_packages.c_cpp`.

Delete tests that only assert old package paths, old compatibility re-exports, or legacy `harness_prompt` naming.

- [ ] **Step 5: Move default C/C++ assembly out of Core-shaped modules**

Modify `src/embedagent/default_extensions.py` so it is clearly host/product assembly. If a generic Core package is introduced in Task 8, this file moves to `src/embedagent_host/default_extensions.py`.

Allowed import in host/product assembly:

```python
from embedagent.workflow_packages.c_cpp.extension import CHarnessWorkflowExtension
```

Forbidden import in Core modules:

```python
from embedagent.workflow_packages.c_cpp.extension import CHarnessWorkflowExtension
```

- [ ] **Step 6: Run workflow package tests**

Run:

```bash
uv run pytest tests/test_c_cpp_workflow_*.py tests/test_workflow_package_manifest.py tests/test_workflow_extensions.py tests/test_task_graph_v2.py -v
```

Expected: PASS after renames and import updates.

- [ ] **Step 7: Run architecture guard**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/embedagent/workflow_packages src/embedagent/default_extensions.py tests
git add -u src/embedagent/harness
git commit -m "refactor: move c cpp harness into workflow package"
```

---

## Task 7: Add Fake Non-C Workflow Package Coverage

**Files:**
- Create: `tests/fixtures/workflow_packages/python_demo.py`
- Create: `tests/test_non_c_workflow_capabilities.py`
- Modify: `src/embedagent/protocol/app_protocol.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`

- [ ] **Step 1: Add fake workflow package fixture**

Create `tests/fixtures/workflow_packages/python_demo.py`:

```python
class PythonDemoWorkflowPackage(object):
    package_id = "workflow-python-demo"
    label = "Python Demo"

    def package_manifest(self):
        return {
            "id": self.package_id,
            "label": self.label,
            "supported_modes": ["python-explore", "python-build"],
            "tools": [
                {
                    "name": "pytest",
                    "label": "Pytest",
                    "renderer_key": "command",
                    "permission_category": "command",
                }
            ],
        }

    def capability_metadata(self):
        return {
            "modes": [
                {
                    "id": "python-explore",
                    "label": "Python Explore",
                    "description": "Inspect Python code",
                    "iconKey": "search",
                    "colorToken": "info",
                    "commandId": "mode.python-explore",
                },
                {
                    "id": "python-build",
                    "label": "Python Build",
                    "description": "Implement Python code",
                    "iconKey": "hammer",
                    "colorToken": "success",
                    "commandId": "mode.python-build",
                },
            ],
            "commands": [
                {
                    "id": "mode.python-build",
                    "label": "Python Build",
                    "group": "mode",
                    "dispatch": {"kind": "mode.set", "mode": "python-build"},
                }
            ],
            "tools": [
                {
                    "name": "pytest",
                    "label": "Pytest",
                    "iconKey": "test-tube",
                    "rendererKey": "command",
                    "permissionCategory": "command",
                }
            ],
            "emptyState": {
                "scenario_label": "Python workspace",
                "primary": "Choose a local Python workspace",
                "secondary": "Python workflow metadata drives this shell.",
            },
        }
```

- [ ] **Step 2: Add non-C capability test**

Create `tests/test_non_c_workflow_capabilities.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures", "workflow_packages"))

from embedagent.frontend.gui.backend.protocol_payloads import serialize_session_bootstrap
from python_demo import PythonDemoWorkflowPackage


class NonCWorkflowCapabilityTests(unittest.TestCase):
    def test_python_workflow_package_projects_without_gui_code_changes(self):
        package = PythonDemoWorkflowPackage()
        payload = serialize_session_bootstrap(
            {
                "snapshot": {
                    "session_id": "sess-python",
                    "status": "idle",
                    "current_mode": "python-build",
                    "workflow_state": {"package_id": package.package_id},
                },
                "history": {"activities": []},
                "capabilities": package.capability_metadata(),
            }
        )

        self.assertEqual(payload["thread"]["currentMode"], "python-build")
        self.assertEqual(payload["capabilities"]["modes"][0]["id"], "python-explore")
        self.assertEqual(payload["capabilities"]["tools"][0]["label"], "Pytest")
        self.assertEqual(
            payload["capabilities"]["emptyState"]["scenario_label"],
            "Python workspace",
        )
        self.assertNotIn("C/C++", str(payload))
        self.assertNotIn("run_recipe", str(payload))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the test and confirm it passes**

Run:

```bash
uv run pytest tests/test_non_c_workflow_capabilities.py -v
```

Expected: PASS. If it fails because protocol keys are camelCase only, update `CapabilitySnapshot.to_dict()` to include the exact key shape consumed by the GUI and keep the test expectation aligned with that promoted shape.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/workflow_packages/python_demo.py tests/test_non_c_workflow_capabilities.py src/embedagent/protocol/app_protocol.py src/embedagent/frontend/gui/backend/protocol_payloads.py
git commit -m "test: prove gui capability contract supports non c workflows"
```

---

## Task 8: Split Core And Host Packages Inside The Monorepo

**Files:**
- Create: `src/embedagent_core/`
- Create: `src/embedagent_host/`
- Move generic Core modules from `src/embedagent/` to `src/embedagent_core/`
- Move hosted runtime and app composition modules from `src/embedagent/` to `src/embedagent_host/`
- Modify: `pyproject.toml`
- Modify: `tests/test_current_architecture_boundaries.py`
- Create: `tests/test_core_package_imports.py`
- Create: `tests/test_host_package_composition.py`

- [ ] **Step 1: Add import purity tests**

Create `tests/test_core_package_imports.py`:

```python
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class CorePackageImportTests(unittest.TestCase):
    def test_embedagent_core_imports_no_gui_host_or_workflow_package(self):
        root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent_core")
        forbidden = (
            "embedagent.frontend",
            "embedagent_host",
            "embedagent.workflow_packages",
            "embedagent.workflow_packages.c_cpp",
        )
        offenders = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, "r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    module = ""
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                    elif isinstance(node, ast.Import):
                        module = ",".join(alias.name for alias in node.names)
                    if any(item in module for item in forbidden):
                        offenders.append((os.path.relpath(path, root), module))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
```

Expected initial result: FAIL because `src/embedagent_core` does not exist.

- [ ] **Step 2: Create package directories**

Create:

```text
src/embedagent_core/__init__.py
src/embedagent_host/__init__.py
```

`src/embedagent_core/__init__.py` exports only generic Core version and selected public package identifiers. It must not import workflow packages or GUI modules.

- [ ] **Step 3: Move generic Core modules**

Move generic runtime modules into `src/embedagent_core/`:

```text
agent_kernel.py
agent_loop.py
agent_lifecycle.py
agent_tool_action_service.py
agent_extension_host.py
agent_event_bus.py
turn_snapshot.py
runtime_config.py
compaction_state.py
recovery_state.py
turn_experience.py
permissions.py
tool_runtime.py
extension_manager.py
capability_registry.py
```

Update imports to `embedagent_core.*`.

Delete old files from `src/embedagent/` after imports are updated. Do not leave forwarding modules.

- [ ] **Step 4: Move host composition modules**

Move hosted product composition into `src/embedagent_host/`:

```text
default_extensions.py
hosted_command_service.py
hosted_interaction_service.py
inprocess_adapter.py
session_lifecycle.py
workspace_registry.py
```

Update GUI backend imports to use `embedagent_host.*` where they need hosted behavior.

- [ ] **Step 5: Keep product entry package explicit**

`src/embedagent/` may keep CLI/product entry modules only when they are true composition entrypoints. Product entry modules may import:

```python
import embedagent_core
import embedagent_host
from embedagent.workflow_packages.c_cpp.extension import CHarnessWorkflowExtension
```

They must not provide old module aliases such as `embedagent.agent_loop` or `embedagent.harness`.

- [ ] **Step 6: Update package metadata**

Modify `pyproject.toml`:

- Change the description away from embedded C-only wording.
- Keep `requires-python = ">=3.8,<3.9"`.
- Do not add dependencies.
- Ensure package discovery includes `embedagent_core`, `embedagent_host`, `embedagent`, and workflow packages.

- [ ] **Step 7: Run core and host import tests**

Run:

```bash
uv run pytest tests/test_core_package_imports.py tests/test_host_package_composition.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/embedagent_core src/embedagent_host src/embedagent pyproject.toml tests/test_core_package_imports.py tests/test_host_package_composition.py tests/test_current_architecture_boundaries.py
git add -u src/embedagent
git commit -m "refactor: split core and host packages in monorepo"
```

---

## Task 9: Delete Misleading Timeline And Compatibility Test Names

**Files:**
- Delete or rename: `tests/test_gui_timeline_flat.py`
- Create: `tests/test_tui_activity_timeline.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `src/embedagent/frontend/tui/views/timeline.py`

- [ ] **Step 1: Rename the TUI activity timeline test**

Run:

```bash
git mv tests/test_gui_timeline_flat.py tests/test_tui_activity_timeline.py
```

The existing assertions validate TUI activity formatting, not a GUI flat timeline contract. Keep the behavior, remove the misleading old name.

- [ ] **Step 2: Add a guard against flat timeline resurrection**

In `tests/test_pre_release_architecture_guards.py`, add:

```python
def test_no_flat_timeline_view_or_builder_paths():
    import os

    root = os.path.join(os.path.dirname(__file__), "..", "src")
    forbidden_names = (
        "FlatTimelineView",
        "build_flat_history",
        "timelineFromTurns",
        "timelineFromEvents",
        "session-runtime/projector.js",
    )
    offenders = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith((".py", ".js", ".jsx")):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            for name in forbidden_names:
                if name in text:
                    offenders.append((os.path.relpath(path, root), name))
    assert offenders == []
```

- [ ] **Step 3: Run timeline guard tests**

Run:

```bash
uv run pytest tests/test_tui_activity_timeline.py tests/test_pre_release_architecture_guards.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tui_activity_timeline.py tests/test_pre_release_architecture_guards.py
git add -u tests/test_gui_timeline_flat.py
git commit -m "test: remove misleading flat timeline test path"
```

---

## Task 10: Update Long-Lived Architecture Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Create or modify: `docs/frontend-protocol.md`
- Create or modify: `docs/tool-contracts.md`
- Create or modify: `docs/agent-harness-v2.md`

- [x] **Step 1: Update documentation only after code tasks pass**

Edit the docs so the active architecture states:

```text
Agent Core is generic and imports no workflow package, GUI backend, or product host.
The hosted product explicitly assembles Core, selected workflow packages, and UI shells.
The C/C++ workflow package is first-party but not Core.
The GUI consumes Agent App Protocol snapshots/events and backend-declared capabilities.
Interactions are durable activity records; raw transport requests do not create GUI state.
```

Delete statements that describe old harness paths, flat timeline history, raw interaction request GUI state, or hardcoded C/C++ GUI behavior as active contracts.

- [x] **Step 2: Run doc terminology scan**

Run:

```bash
rg -n -P "embedagent\\.harness|src/embedagent/harness|MODE_REGISTRY|_DEFAULT_SANITIZER|get_default_sanitizer|(?<![A-Za-z0-9])_inprocess_adapter|_get_adapter_class|SessionTimelineStore|build_flat_history|FlatTimelineView|timelineFromTurns|timelineFromEvents|harness_prompt|interaction\\.created|manage_todos|/api/todos|todos\\.json|\\btodos\\b" README.md AGENTS.md docs src tests --glob "!docs/archive/**" --glob "!docs/superpowers/**" --glob "!docs/development-tracker.md" --glob "!docs/design-change-log.md" --glob "!src/embedagent/frontend/gui/static/**"
```

Expected: no active-contract hits. Historical tracker/change-log files and
generated static assets are not active contracts.

- [x] **Step 3: Commit**

```bash
git add README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/pi-inspired-agent-core-blueprint.md docs/frontend-protocol.md docs/tool-contracts.md docs/agent-harness-v2.md
git commit -m "docs: describe generic core and t3 gui contract"
```

---

## Task 11: Run Product Gates And Remove Dead Compatibility Code

**Files:**
- Modify only files surfaced by the scans and failing tests.
- Do not add compatibility modules to make obsolete imports pass.

- [x] **Step 1: Run architecture gate**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [x] **Step 2: Run fast backend suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS. If failures are from obsolete old path assertions, delete or replace those tests in the same commit that deletes the code path. If failures are from active behavior, fix the promoted path.

- [x] **Step 3: Run lint**

Run:

```bash
uv run --locked python scripts/lint.py
```

Expected: PASS.

- [x] **Step 4: Run GUI gate**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: PASS and static assets are current.

- [x] **Step 5: Scan for obsolete import paths and compatibility language**

Run:

```bash
rg -n -P "embedagent\\.harness|src/embedagent/harness|MODE_REGISTRY|_DEFAULT_SANITIZER|get_default_sanitizer|(?<![A-Za-z0-9])_inprocess_adapter|_get_adapter_class|SessionTimelineStore|build_flat_history|FlatTimelineView|timelineFromTurns|timelineFromEvents|harness_prompt|interaction\\.created|manage_todos|/api/todos|todos\\.json|\\btodos\\b" README.md AGENTS.md docs src tests --glob "!docs/archive/**" --glob "!docs/superpowers/**" --glob "!docs/development-tracker.md" --glob "!docs/design-change-log.md" --glob "!src/embedagent/frontend/gui/static/**"
```

Expected: no active hits outside historical docs/reference material. Delete active hits; do not suppress the scan.

- [x] **Step 6: Commit final cleanup**

```bash
git add src tests README.md AGENTS.md docs src/embedagent/frontend/gui/static
git commit -m "chore: remove obsolete compatibility paths"
```

---

## Physical Repository Split Checklist

Run this only after Tasks 1 through 11 pass in the monorepo.

- [ ] `agent-core` repository contains `embedagent_core`, `embedagent.protocol`, Core tests, and no C/C++ workflow package or GUI code.
- [ ] `agent-host` repository contains hosted session lifecycle, app/bootstrap/server adapters, command service, interaction service, workspace registry, and offline bundle contract integration.
- [ ] `workflow-c-cpp` repository contains the moved `workflow_packages/c_cpp` package and C/C++ workflow tests.
- [ ] `agent-gui` repository contains the webapp, static build pipeline, GUI contract tests, and no scenario-specific source code.
- [ ] Product bundle repository or product package assembles `agent-core`, `agent-host`, `agent-gui`, `workflow-c-cpp`, Python 3.8 embeddable runtime, MinGit, ripgrep, Universal Ctags, Clang, and every runtime-invoked binary listed in `scripts/offline-runtime-contract.json`.
- [ ] Clean Windows 7/WebView2 smoke evidence is recorded before any release claim.

## Self-Review

- Spec coverage: Tasks 1 and 2 implement the Agent App Protocol; Tasks 3 and 4 implement activity-ledger interactions; Task 5 removes GUI hardcoding; Tasks 6 through 8 create workflow/Core/Host package boundaries; Task 9 deletes misleading old timeline paths; Task 10 updates docs; Task 11 runs gates and removes dead compatibility code.
- Placeholder scan: this plan contains concrete file paths, test snippets, commands, and expected outcomes. It intentionally avoids placeholder labels, deferred implementation markers, and compatibility-preserving escape hatches.
- Type consistency: protocol names use Python snake_case constructor fields and JSON camelCase output; frontend normalizers consume camelCase and tolerate snake_case only at the boundary where Python still produces existing payload fragments.
