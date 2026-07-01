# Hosted Runtime Shell Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy CLI/TUI/GUI entrypoint runtime assembly with a single Hosted Runtime boundary, while deleting old shell-owned construction paths and preventing new technical debt.

**Architecture:** Agent Core stays minimal and owns only loop, snapshots, reducers, permission, tool action, and extension host behavior. A new hosted layer owns launch configuration, provider/tool/context/permission assembly, session host operations, and shell-facing event translation. CLI, TUI, and GUI become replaceable shells over that hosted boundary.

**Tech Stack:** Python 3.8, stdlib dataclasses/typing, existing `InProcessAdapter`, existing frontend GUI/TUI modules, pytest, existing architecture guard tests.

---

## File Structure

- Create: `src/embedagent/hosted/__init__.py`
  - Exports the hosted runtime types and factory.
- Create: `src/embedagent/hosted/launch_config.py`
  - Resolves workspace, config file values, environment values, CLI overrides, permission flags, model settings, and max-turn safety fuse.
- Create: `src/embedagent/hosted/runtime.py`
  - Owns `OpenAICompatibleClient`, `ToolRuntime`, `ContextManager`, `PermissionPolicy`, `ProjectMemoryStore`, `SessionSummaryStore`, default extension assembly, and `InProcessAdapter` construction.
- Create: `src/embedagent/hosted/session_host.py`
  - Shell-facing wrapper around `InProcessAdapter`: list/create/resume/bootstrap/submit/respond/reload/capability operations.
- Modify: `src/embedagent/cli.py`
  - Replace inline runtime assembly with hosted runtime calls. Keep CLI-specific output formatting and argparse only.
- Modify: `src/embedagent/frontend/tui/launcher.py`
  - Use hosted launch configuration; stop loading config directly.
- Modify: `src/embedagent/frontend/tui/bootstrap.py`
  - Delete provider/tool/context/permission construction. Accept hosted runtime/session host and create `TerminalApp`.
- Modify: `src/embedagent/frontend/tui/app.py`
  - Accept session host or adapter bridge through a single field. Preserve UI lifecycle.
- Modify: `src/embedagent/frontend/gui/backend/runtime.py`
  - Delegate GUI runtime construction to hosted runtime factory.
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
  - Consume GUI session host service only; do not construct core/runtime dependencies.
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  - Remove session/interaction/composer/workbench feature state that has focused module homes.
- Modify: `src/embedagent/frontend/gui/webapp/src/composer/composer-state.js`
  - Make composer drafts thread/draft-session scoped.
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - Ensure workbench stores descriptors/active surface only, not feature data.
- Modify: `tests/test_pre_release_architecture_guards.py`
  - Add deletion-oriented guards for shell/runtime boundaries.
- Create: `tests/test_hosted_launch_config.py`
  - Tests launch config resolution and no persistent `max_turns` product ceiling.
- Create: `tests/test_hosted_runtime.py`
  - Tests hosted runtime constructs shared dependencies once and exposes a session host.
- Modify: `tests/test_tui_launcher.py`
  - Update tests to patch hosted config/factory instead of old `load_config`/`run_tui` path.
- Create: `tests/test_cli_hosted_entrypoint.py`
  - Tests CLI uses config-backed hosted runtime and does not require env-only model values.
- Modify: `tests/test_gui_runtime.py`
  - Update GUI runtime tests to expect hosted runtime delegation.

## Non-Negotiable Deletions

- Delete CLI direct construction of `OpenAICompatibleClient`, `ToolRuntime`, `ContextManager`, `PermissionPolicy`, and `InProcessAdapter`.
- Delete TUI bootstrap direct construction of those same runtime dependencies.
- Delete per-shell config resolution helpers after hosted launch config lands.
- Do not add compatibility aliases for old CLI/TUI runtime APIs.
- Do not add fallback history/bootstrap/projector paths in GUI.
- Do not move shell concerns into Agent Core or `QueryEngine`.

---

### Task 1: Hosted Launch Configuration

**Files:**
- Create: `src/embedagent/hosted/__init__.py`
- Create: `src/embedagent/hosted/launch_config.py`
- Create: `tests/test_hosted_launch_config.py`

- [ ] **Step 1: Write the failing launch config tests**

```python
import os

from embedagent.config import AppConfig
from embedagent.hosted.launch_config import LaunchOverrides, resolve_launch_config


def test_resolve_launch_config_uses_overrides_before_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
    )
    result = resolve_launch_config(
        workspace=str(tmp_path),
        overrides=LaunchOverrides(
            base_url="http://override/v1",
            api_key="sk-override",
            model="override-model",
            timeout=12,
        ),
    )
    assert result.workspace == os.path.realpath(str(tmp_path))
    assert result.base_url == "http://override/v1"
    assert result.api_key == "sk-override"
    assert result.model == "override-model"
    assert result.timeout == 12


def test_resolve_launch_config_uses_config_when_overrides_are_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
    )
    result = resolve_launch_config(workspace=str(tmp_path), overrides=LaunchOverrides())
    assert result.base_url == "http://configured/v1"
    assert result.api_key == "sk-configured"
    assert result.model == "configured-model"
    assert result.timeout == 45


def test_resolve_launch_config_ignores_persistent_max_turns(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
            max_turns=8,
        ),
    )
    result = resolve_launch_config(workspace=str(tmp_path), overrides=LaunchOverrides())
    assert result.max_turns is None


def test_resolve_launch_config_accepts_explicit_max_turns_safety_fuse(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
            max_turns=8,
        ),
    )
    result = resolve_launch_config(
        workspace=str(tmp_path), overrides=LaunchOverrides(max_turns=3)
    )
    assert result.max_turns == 3


def test_resolve_launch_config_rejects_missing_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent.hosted.launch_config.load_config",
        lambda workspace: AppConfig(base_url="http://configured/v1", api_key="sk-configured"),
    )
    try:
        resolve_launch_config(workspace=str(tmp_path), overrides=LaunchOverrides())
    except ValueError as exc:
        assert "model" in str(exc).lower() or "模型" in str(exc)
    else:
        raise AssertionError("missing model should fail")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hosted_launch_config.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'embedagent.hosted'`.

- [ ] **Step 3: Implement minimal hosted launch config**

```python
# src/embedagent/hosted/launch_config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from embedagent.config import AppConfig, load_config


@dataclass
class LaunchOverrides(object):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[float] = None
    max_turns: Optional[int] = None
    approve_all: bool = False
    approve_writes: bool = False
    approve_commands: bool = False
    permission_rules: str = ""
    max_context_tokens: Optional[int] = None
    reserve_output_tokens: Optional[int] = None
    chars_per_token: Optional[float] = None


@dataclass
class LaunchConfig(object):
    workspace: str
    app_config: AppConfig
    base_url: str
    api_key: str
    model: str
    timeout: float
    max_turns: Optional[int]
    approve_all: bool
    approve_writes: bool
    approve_commands: bool
    permission_rules: str


def _first_non_empty(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        return value
    return None


def resolve_launch_config(workspace: str, overrides: LaunchOverrides) -> LaunchConfig:
    resolved_workspace = os.path.realpath(workspace)
    app_config = load_config(resolved_workspace)
    if overrides.max_context_tokens is not None:
        app_config.max_context_tokens = overrides.max_context_tokens
    if overrides.reserve_output_tokens is not None:
        app_config.reserve_output_tokens = overrides.reserve_output_tokens
    if overrides.chars_per_token is not None:
        app_config.chars_per_token = overrides.chars_per_token

    base_url = str(
        _first_non_empty(
            overrides.base_url,
            getattr(app_config, "base_url", ""),
            os.environ.get("EMBEDAGENT_BASE_URL"),
            "http://127.0.0.1:8000/v1",
        )
    )
    api_key = str(
        _first_non_empty(
            overrides.api_key,
            getattr(app_config, "api_key", ""),
            os.environ.get("EMBEDAGENT_API_KEY"),
            "",
        )
    )
    model = str(
        _first_non_empty(
            overrides.model,
            getattr(app_config, "model", ""),
            os.environ.get("EMBEDAGENT_MODEL"),
            "",
        )
    )
    timeout = float(
        _first_non_empty(
            overrides.timeout,
            getattr(app_config, "timeout", None),
            os.environ.get("EMBEDAGENT_TIMEOUT"),
            120.0,
        )
    )
    if not model:
        raise ValueError("必须通过 --model、环境变量或配置文件提供模型名称。")
    return LaunchConfig(
        workspace=resolved_workspace,
        app_config=app_config,
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
        max_turns=int(overrides.max_turns) if overrides.max_turns is not None else None,
        approve_all=bool(overrides.approve_all),
        approve_writes=bool(overrides.approve_writes),
        approve_commands=bool(overrides.approve_commands),
        permission_rules=overrides.permission_rules or "",
    )
```

```python
# src/embedagent/hosted/__init__.py
from embedagent.hosted.launch_config import LaunchConfig, LaunchOverrides, resolve_launch_config

__all__ = ["LaunchConfig", "LaunchOverrides", "resolve_launch_config"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_hosted_launch_config.py -v`

Expected: PASS.

---

### Task 2: Hosted Runtime and Session Host

**Files:**
- Create: `src/embedagent/hosted/runtime.py`
- Create: `src/embedagent/hosted/session_host.py`
- Modify: `src/embedagent/hosted/__init__.py`
- Create: `tests/test_hosted_runtime.py`

- [ ] **Step 1: Write the failing hosted runtime tests**

```python
from unittest.mock import MagicMock

from embedagent.config import AppConfig
from embedagent.hosted.launch_config import LaunchConfig
from embedagent.hosted.runtime import create_hosted_runtime
from embedagent.hosted.session_host import HostedSessionHost


def _config(tmp_path):
    return LaunchConfig(
        workspace=str(tmp_path),
        app_config=AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
        base_url="http://configured/v1",
        api_key="sk-configured",
        model="configured-model",
        timeout=45,
        max_turns=None,
        approve_all=True,
        approve_writes=False,
        approve_commands=False,
        permission_rules="",
    )


def test_create_hosted_runtime_builds_session_host(tmp_path, monkeypatch):
    client_cls = MagicMock(return_value=MagicMock(name="client"))
    tools_cls = MagicMock(return_value=MagicMock(name="tools"))
    context_cls = MagicMock(return_value=MagicMock(name="context_manager"))
    policy_cls = MagicMock(return_value=MagicMock(name="permission_policy"))
    adapter_cls = MagicMock(return_value=MagicMock(name="adapter"))
    monkeypatch.setattr("embedagent.hosted.runtime.OpenAICompatibleClient", client_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.ToolRuntime", tools_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.ContextManager", context_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.PermissionPolicy", policy_cls)
    monkeypatch.setattr("embedagent.hosted.runtime.InProcessAdapter", adapter_cls)

    runtime = create_hosted_runtime(_config(tmp_path))

    assert isinstance(runtime.session_host, HostedSessionHost)
    client_cls.assert_called_once_with(
        base_url="http://configured/v1",
        api_key="sk-configured",
        model="configured-model",
        timeout=45,
    )
    tools_cls.assert_called_once()
    context_cls.assert_called_once()
    policy_cls.assert_called_once()
    adapter_cls.assert_called_once()


def test_session_host_delegates_session_operations():
    adapter = MagicMock()
    adapter.list_sessions.return_value = [{"session_id": "s1"}]
    adapter.create_session.return_value = {"session_id": "s2"}
    adapter.resume_session.return_value = {"session_id": "s1"}
    adapter.submit_user_message.return_value = None
    host = HostedSessionHost(adapter=adapter)

    assert host.list_sessions(limit=1) == [{"session_id": "s1"}]
    assert host.create_session(mode="build") == {"session_id": "s2"}
    assert host.resume_session(reference="latest", mode="build") == {"session_id": "s1"}
    host.submit_user_message(session_id="s1", text="hello", stream=False, wait=True)

    adapter.list_sessions.assert_called_once_with(limit=1)
    adapter.create_session.assert_called_once_with("build", event_handler=None)
    adapter.resume_session.assert_called_once_with("latest", "build", event_handler=None)
    adapter.submit_user_message.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hosted_runtime.py -v`

Expected: FAIL with missing `embedagent.hosted.runtime` or `HostedSessionHost`.

- [ ] **Step 3: Implement hosted runtime/session host**

```python
# src/embedagent/hosted/session_host.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


EventHandler = Optional[Callable[[str, str, Dict[str, object]], None]]


@dataclass
class HostedSessionHost(object):
    adapter: Any

    def list_sessions(self, limit: int = 10) -> List[Dict[str, object]]:
        return self.adapter.list_sessions(limit=limit)

    def create_session(self, mode: str, event_handler: EventHandler = None) -> Dict[str, object]:
        return self.adapter.create_session(mode, event_handler=event_handler)

    def resume_session(
        self, reference: str, mode: str, event_handler: EventHandler = None
    ) -> Dict[str, object]:
        return self.adapter.resume_session(reference, mode, event_handler=event_handler)

    def submit_user_message(
        self,
        session_id: str,
        text: str,
        stream: bool,
        wait: bool,
        permission_resolver=None,
        user_input_resolver=None,
        event_handler: EventHandler = None,
    ) -> None:
        self.adapter.submit_user_message(
            session_id=session_id,
            text=text,
            stream=stream,
            wait=wait,
            permission_resolver=permission_resolver,
            user_input_resolver=user_input_resolver,
            event_handler=event_handler,
        )
```

```python
# src/embedagent/hosted/runtime.py
from __future__ import annotations

from dataclasses import dataclass

from embedagent.context import ContextManager, make_context_config
from embedagent.hosted.launch_config import LaunchConfig
from embedagent.hosted.session_host import HostedSessionHost
from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.llm import OpenAICompatibleClient
from embedagent.permissions import PermissionPolicy
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session_store import SessionSummaryStore
from embedagent.tools import ToolRuntime


@dataclass
class HostedRuntime(object):
    launch_config: LaunchConfig
    session_host: HostedSessionHost


def create_hosted_runtime(launch_config: LaunchConfig, event_handler=None) -> HostedRuntime:
    client = OpenAICompatibleClient(
        base_url=launch_config.base_url,
        api_key=launch_config.api_key,
        model=launch_config.model,
        timeout=launch_config.timeout,
    )
    tools = ToolRuntime(launch_config.workspace, app_config=launch_config.app_config)
    context_manager = ContextManager(
        config=make_context_config(launch_config.app_config),
        project_memory=ProjectMemoryStore(launch_config.workspace),
    )
    permission_policy = PermissionPolicy(
        auto_approve_all=launch_config.approve_all,
        auto_approve_writes=launch_config.approve_writes,
        auto_approve_commands=launch_config.approve_commands,
        workspace=launch_config.workspace,
        rules_path=launch_config.permission_rules,
    )
    adapter = InProcessAdapter(
        client=client,
        tools=tools,
        max_turns=launch_config.max_turns,
        permission_policy=permission_policy,
        summary_store=SessionSummaryStore(launch_config.workspace),
        context_manager=context_manager,
        event_handler=event_handler,
    )
    return HostedRuntime(
        launch_config=launch_config,
        session_host=HostedSessionHost(adapter=adapter),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hosted_runtime.py -v`

Expected: PASS.

---

### Task 3: CLI Replacement Over Hosted Runtime

**Files:**
- Modify: `src/embedagent/cli.py`
- Create: `tests/test_cli_hosted_entrypoint.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Write failing CLI hosted entrypoint tests**

```python
from unittest.mock import MagicMock

from embedagent import cli
from embedagent.config import AppConfig


def test_cli_uses_hosted_config_model_for_non_tui_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "embedagent.hosted.launch_config.load_config",
        lambda workspace: AppConfig(
            base_url="http://configured/v1",
            api_key="sk-configured",
            model="configured-model",
            timeout=45,
        ),
    )
    runtime = MagicMock()
    runtime.session_host.create_session.return_value = {"session_id": "s1"}
    monkeypatch.setattr("embedagent.cli.create_hosted_runtime", lambda config, event_handler=None: runtime)

    exit_code = cli.main(["--workspace", str(tmp_path), "--no-stream", "hello"])

    assert exit_code == 0
    runtime.session_host.create_session.assert_called_once()
    runtime.session_host.submit_user_message.assert_called_once()


def test_cli_architecture_guard_blocks_direct_runtime_construction():
    text = open("src/embedagent/cli.py", "r", encoding="utf-8").read()
    blocked = [
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
        "InProcessAdapter(",
    ]
    for needle in blocked:
        assert needle not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_hosted_entrypoint.py -v`

Expected: FAIL because CLI still constructs runtime directly.

- [ ] **Step 3: Replace CLI runtime assembly**

Implementation notes:
- Keep `build_parser`, `_read_user_message`, `_format_session_record`, `_parse_initial_message`, event formatting, permission resolver, and user input resolver.
- Import from hosted layer:

```python
from embedagent.hosted.launch_config import LaunchOverrides, resolve_launch_config
from embedagent.hosted.runtime import create_hosted_runtime
```

- Remove imports of `load_config`, `ContextManager`, `InProcessAdapter`, `OpenAICompatibleClient`, `PermissionPolicy`, `ProjectMemoryStore`, and `ToolRuntime`.
- Resolve config once after `initialize_modes(workspace)`:

```python
launch_config = resolve_launch_config(
    workspace,
    LaunchOverrides(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        timeout=args.timeout,
        max_turns=args.max_turns,
        approve_all=args.approve_all,
        approve_writes=args.approve_writes,
        approve_commands=args.approve_commands,
        permission_rules=args.permission_rules,
        max_context_tokens=args.max_context_tokens,
        reserve_output_tokens=args.reserve_output_tokens,
        chars_per_token=args.chars_per_token,
    ),
)
```

- Use `launch_config.app_config.default_mode` for fallback mode.
- Create runtime:

```python
runtime = create_hosted_runtime(launch_config, event_handler=on_event)
host = runtime.session_host
```

- Replace `summary_store.list_summaries` with `host.list_sessions`.
- Replace adapter calls with host calls.

- [ ] **Step 4: Add architecture guard**

Add to `tests/test_pre_release_architecture_guards.py`:

```python
def test_cli_shell_does_not_construct_hosted_runtime_dependencies():
    text = _read(ROOT / "src/embedagent/cli.py")
    blocked = (
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
        "InProcessAdapter(",
    )
    for needle in blocked:
        assert needle not in text
```

- [ ] **Step 5: Run CLI tests and architecture guard**

Run: `uv run pytest tests/test_cli_hosted_entrypoint.py tests/test_pre_release_architecture_guards.py -v`

Expected: PASS.

---

### Task 4: TUI Pi-Style Replacement Over Hosted Runtime

**Files:**
- Modify: `src/embedagent/frontend/tui/launcher.py`
- Modify: `src/embedagent/frontend/tui/bootstrap.py`
- Modify: `tests/test_tui_launcher.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Write failing TUI launcher tests**

```python
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from embedagent.frontend.tui import launcher as tui_launcher


class TestTuiLauncher(unittest.TestCase):
    def test_launch_tui_uses_hosted_runtime_factory(self):
        runtime = MagicMock()
        with tempfile.TemporaryDirectory() as workspace:
            with patch(
                "embedagent.frontend.tui.launcher.resolve_launch_config",
                return_value=MagicMock(workspace=os.path.realpath(workspace)),
            ) as resolve_config, patch(
                "embedagent.frontend.tui.launcher.create_hosted_runtime",
                return_value=runtime,
            ) as create_runtime, patch(
                "embedagent.frontend.tui.launcher.run_tui",
                return_value=0,
            ) as run_tui:
                exit_code = tui_launcher.launch_tui(workspace=workspace, max_turns=3)

        self.assertEqual(exit_code, 0)
        self.assertEqual(resolve_config.call_args.args[0], os.path.realpath(workspace))
        self.assertEqual(resolve_config.call_args.kwargs["overrides"].max_turns, 3)
        create_runtime.assert_called_once()
        self.assertIs(run_tui.call_args.kwargs["session_host"], runtime.session_host)

    def test_tui_bootstrap_architecture_guard_blocks_direct_runtime_construction(self):
        text = open(
            "src/embedagent/frontend/tui/bootstrap.py", "r", encoding="utf-8"
        ).read()
        blocked = [
            "OpenAICompatibleClient(",
            "ToolRuntime(",
            "ContextManager(",
            "PermissionPolicy(",
            "InProcessAdapter(",
            "load_config(",
        ]
        for needle in blocked:
            self.assertNotIn(needle, text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui_launcher.py -v`

Expected: FAIL because launcher/bootstrap still resolve config and construct runtime directly.

- [ ] **Step 3: Replace TUI launcher**

Implementation notes:
- Import `LaunchOverrides`, `resolve_launch_config`, and `create_hosted_runtime`.
- Remove `_resolve_runtime_value`.
- `launch_tui()` resolves launch config, creates runtime, sets headless env, then calls:

```python
return run_tui(
    session_host=runtime.session_host,
    workspace=launch_config.workspace,
    mode=mode,
    resume=resume,
    initial_message=message,
)
```

- [ ] **Step 4: Replace TUI bootstrap**

Implementation notes:
- `run_tui()` signature becomes:

```python
def run_tui(session_host, workspace, mode, resume, initial_message="") -> int:
```

- Keep `load_tui_dependencies()`.
- Construct `TerminalApp(adapter=session_host.adapter, ...)` as a temporary bridge only if `TerminalApp` still expects `adapter`. The bridge lives in TUI bootstrap, but no runtime dependency construction is allowed there.
- Do not preserve old `run_tui(base_url=..., model=...)` signature.

- [ ] **Step 5: Add architecture guard**

Add to `tests/test_pre_release_architecture_guards.py`:

```python
def test_tui_shell_does_not_construct_hosted_runtime_dependencies():
    for rel in (
        "src/embedagent/frontend/tui/launcher.py",
        "src/embedagent/frontend/tui/bootstrap.py",
    ):
        text = _read(ROOT / rel)
        for needle in (
            "OpenAICompatibleClient(",
            "ToolRuntime(",
            "ContextManager(",
            "PermissionPolicy(",
            "InProcessAdapter(",
            "load_config(",
        ):
            assert needle not in text
```

- [ ] **Step 6: Run TUI and guard tests**

Run: `uv run pytest tests/test_tui_launcher.py tests/test_pre_release_architecture_guards.py -v`

Expected: PASS.

---

### Task 5: GUI Backend Hosted Runtime Delegation

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/runtime.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Modify: `tests/test_gui_runtime.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Write failing GUI runtime delegation test**

Add or replace a test in `tests/test_gui_runtime.py`:

```python
from unittest.mock import MagicMock


def test_gui_runtime_delegates_to_hosted_runtime(tmp_path, monkeypatch):
    from embedagent.frontend.gui.backend import runtime as gui_runtime

    hosted_runtime = MagicMock()
    monkeypatch.setattr(
        "embedagent.frontend.gui.backend.runtime.resolve_launch_config",
        MagicMock(return_value=MagicMock(workspace=str(tmp_path))),
    )
    create_hosted_runtime = MagicMock(return_value=hosted_runtime)
    monkeypatch.setattr(
        "embedagent.frontend.gui.backend.runtime.create_hosted_runtime",
        create_hosted_runtime,
    )

    result = gui_runtime.create_gui_runtime(workspace=str(tmp_path), model="configured-model")

    assert result.session_host is hosted_runtime.session_host
    create_hosted_runtime.assert_called_once()
```

- [ ] **Step 2: Run GUI runtime test to verify it fails**

Run: `uv run pytest tests/test_gui_runtime.py -v`

Expected: FAIL because GUI runtime still constructs runtime dependencies directly.

- [ ] **Step 3: Replace GUI backend runtime construction**

Implementation notes:
- GUI backend runtime should create `LaunchOverrides` from GUI launcher options.
- GUI backend runtime should call `resolve_launch_config()` and `create_hosted_runtime()`.
- GUI-specific services should receive `hosted_runtime.session_host` or `hosted_runtime.session_host.adapter` only where existing APIs still require adapter.
- Do not add compatibility factories preserving old construction paths.

- [ ] **Step 4: Add architecture guard**

Add to `tests/test_pre_release_architecture_guards.py`:

```python
def test_gui_backend_runtime_delegates_hosted_dependency_construction():
    text = _read(ROOT / "src/embedagent/frontend/gui/backend/runtime.py")
    for needle in (
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
    ):
        assert needle not in text
```

- [ ] **Step 5: Run GUI backend tests and guard**

Run: `uv run pytest tests/test_gui_runtime.py tests/test_pre_release_architecture_guards.py -v`

Expected: PASS.

---

### Task 6: GUI T3-Style Frontend Runtime Isolation

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/composer/composer-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/thread-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify or create frontend tests under `src/embedagent/frontend/gui/webapp/src`

- [ ] **Step 1: Write failing frontend state boundary tests**

Add JS tests matching the existing frontend test framework:

```javascript
import { describe, expect, it } from "vitest";
import {
  composerInitialState,
  composerReducer,
  draftKeyForSession,
} from "./composer/composer-state.js";

describe("composer state", () => {
  it("keeps drafts scoped by session key", () => {
    let state = composerInitialState();
    state = composerReducer(state, {
      type: "composer/update_draft",
      sessionId: "s1",
      draft: "first",
    });
    state = composerReducer(state, {
      type: "composer/update_draft",
      sessionId: "s2",
      draft: "second",
    });

    expect(state.draftsByKey[draftKeyForSession("s1")].draft).toBe("first");
    expect(state.draftsByKey[draftKeyForSession("s2")].draft).toBe("second");
  });
});
```

Add architecture guard:

```python
def test_gui_root_store_does_not_own_thread_scoped_composer_draft():
    text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    assert "draft:" not in text
    assert "composerInitialState" in text
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run from `src/embedagent/frontend/gui/webapp`: `npm test -- --run`

Expected: FAIL because composer is still global draft state.

- [ ] **Step 3: Implement thread-scoped composer state**

Implementation notes:
- `composerInitialState()` returns:

```javascript
{
  draftsByKey: {},
  activeDraftKey: null,
}
```

- `draftKeyForSession(sessionId)` returns `session:${sessionId || "new"}`.
- `composerReducer` updates only the targeted key.
- Sending a local user message clears only the active draft key.

- [ ] **Step 4: Slim root store**

Implementation notes:
- Keep root reducer as composition only.
- Feature state updates must delegate to focused reducers.
- Remove root-owned `composer: { draft: "" }`.
- Move `TOOL_LABELS` to presentation helper if it is still in store.

- [ ] **Step 5: Align workbench surfaces with T3 descriptor-only state**

Implementation notes:
- Ensure `workbench/surfaces.js` stores surface identity, kind, title, target, and active id.
- Feature data such as preview content, diff content, terminal buffer, file tree, and review markdown stays in feature modules.

- [ ] **Step 6: Run GUI frontend tests and build**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test -- --run
npm run build
```

Expected: PASS. Commit updated generated static assets if build changes them.

---

### Task 7: Full Architecture Gate

**Files:**
- All modified files.

- [ ] **Step 1: Run Python architecture gate**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 2: Run fast Python tests**

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

- [ ] **Step 4: Run GUI gate if webapp source changed**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 5: Manual ignored-path CLI smoke**

Run:

```bash
uv run embedagent --workspace .agents/cli-smoke --no-stream --max-turns 1 "只回答 OK，不要调用工具。"
```

Expected: prints `OK` using config-backed model settings without requiring model env vars.

---

## Self-Review

- Spec coverage: The plan creates a hosted boundary, removes CLI/TUI/GUI direct runtime assembly, preserves Agent Core minimality, and adds architecture guards against regression.
- Placeholder scan: No `TBD`, `TODO`, or undefined future tasks are required to execute the plan.
- Type consistency: `LaunchOverrides`, `LaunchConfig`, `HostedRuntime`, and `HostedSessionHost` are introduced before dependent tasks use them.
- Python version: All Python snippets use Python 3.8-compatible dataclasses and typing; no walrus, `match`, or `dict | dict`.
