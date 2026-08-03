# Shared Shell Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile one product-owned shell descriptor that drives GUI and TUI commands, surfaces, keybindings, tool presentation, and application contributions.

**Architecture:** Protocol owns immutable JSON-safe descriptor DTOs, while the `embedagent` product owns registration records, validation, deterministic compilation, and default composition. Host application records stop carrying shell allow-lists. GUI and TUI receive the compiled descriptor through constructor injection and never supplement it with local catalogs.

**Tech Stack:** Python 3.8 dataclasses, `embedagent-protocol`, EmbedAgent product composition, React 18 JavaScript, prompt_toolkit, pytest, Node test runner.

---

## Preconditions And File Responsibilities

This is Stage 3 of the frontend convergence design. Start only after `2026-08-03-strict-frontend-protocol-authority.md` is merged and both shell runtimes consume the strict current DTOs.

- `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`: descriptor DTOs only; no defaults or compiler behavior.
- `src/embedagent/frontend/shell/registration.py`: product-level immutable contribution records and registry lookup.
- `src/embedagent/frontend/shell/compiler.py`: duplicate checks, renderer/dispatch validation, availability merge, deterministic ordering.
- `src/embedagent/frontend/shell/defaults.py`: minimal generic shell and product-owned optional registrations.
- `src/embedagent/product_catalog.py`: binds application ids to workflow/application and shell registrations.
- `src/embedagent/frontend/gui/backend/app_shell.py`: attaches injected compiled descriptors to app bootstrap.
- `src/embedagent/frontend/tui/runtime.py`: exposes the injected descriptor and dispatches registered commands.
- `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`: consumes complete descriptors; no fallback labels, commands, surfaces, or keybindings.
- `src/embedagent/frontend/tui/workbench.py`: presentation state derived from the injected descriptor; no fixed catalogs.

The compiler input may contain records from the generic product shell and the selected application only. Workspace extensions may select a declared generic renderer key but cannot add executable JavaScript or replace a built-in command id.

### Task 1: Lock The Protocol Descriptor Cross-Field Contract

**Files:**
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `tests/test_agent_app_protocol.py`

- [ ] **Step 1: Write failing descriptor validation tests**

Add exact round-trip tests:

```python
def test_shell_descriptor_is_json_safe_and_workflow_neutral():
    descriptor = ShellDescriptor(
        schema_version=1,
        commands=[
            CommandDescriptor(
                id="session.new",
                label="New Session",
                group="session",
                dispatch={"kind": "session.create"},
            )
        ],
        surfaces=[
            SurfaceDescriptor(
                id="session.command_palette",
                label="Commands",
                placement="overlay",
                renderer_key="command_palette",
            )
        ],
        keybindings=[KeybindingDescriptor(command_id="session.new", keys="ctrl+n")],
    )

    payload = descriptor.to_dict()
    json.dumps(payload)
    assert payload["commands"][0]["dispatch"] == {"kind": "session.create"}
    assert "task_graph" not in json.dumps(payload).lower()
```

Add failures for duplicate ids within a descriptor, a keybinding that references an absent command, unsupported placement, blank renderer key, and a dispatch record without `kind`.

- [ ] **Step 2: Run protocol tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_agent_app_protocol.py`

Expected: FAIL because Stage 2 structural validation does not yet reject duplicate ids or dangling keybindings inside one descriptor.

- [ ] **Step 3: Add cross-field validation without product policy**

Extend `ShellDescriptor.__post_init__` with deterministic structural checks:

```python
command_ids = _unique_ids("shell_command", self.commands)
_unique_ids("shell_surface", self.surfaces)
for keybinding in self.keybindings:
    if keybinding.command_id not in command_ids:
        raise ValueError("unknown_keybinding_command:%s" % keybinding.command_id)
```

The DTO still does not know product defaults, application ids, supported renderer sets, supported dispatch-kind sets, command handlers, or layouts.

- [ ] **Step 4: Regenerate the strict descriptor fixtures**

Run: `uv run python scripts/export-frontend-protocol-fixtures.py --output-dir tests/fixtures/frontend_protocol`

Expected: `app_bootstrap.json` still contains the Stage 2 `shell` slot with no wire-shape change, and fixture generation is deterministic.

- [ ] **Step 5: Run protocol tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_agent_app_protocol.py tests/test_protocol_versions.py`

Expected: PASS.

- [ ] **Step 6: Commit descriptor vocabulary**

```bash
git add packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py packages/embedagent-protocol/src/embedagent_protocol/__init__.py tests/test_agent_app_protocol.py tests/test_protocol_versions.py tests/fixtures/frontend_protocol
git commit -m "feat: define shared shell descriptors"
```

### Task 2: Build The Product Registration Compiler

**Files:**
- Create: `src/embedagent/frontend/shell/__init__.py`
- Create: `src/embedagent/frontend/shell/registration.py`
- Create: `src/embedagent/frontend/shell/compiler.py`
- Create: `tests/test_shell_registration.py`

- [ ] **Step 1: Write failing deterministic compiler tests**

Cover generic plus selected-application merge, stable ordering, and rejection paths:

```python
def test_compiler_merges_generic_and_selected_application_records():
    registry = ShellContributionRegistry(
        generic=ShellContribution(
            commands=(command("session.new", "session.create", order=10),),
            surfaces=(surface("session.commands", "overlay", "command_palette", order=10),),
        ),
        applications={
            "embedagent.default_c_cpp": ShellContribution(
                commands=(command("workflow.verify", "session.command", order=50),)
            )
        },
    )

    descriptor = compile_shell_descriptor(
        registry,
        application_id="embedagent.default_c_cpp",
        session_capabilities={"commands": [{"id": "workflow.verify", "active": True}]},
    )

    assert [item.id for item in descriptor.commands] == ["session.new", "workflow.verify"]
```

Add separate tests that reject duplicate command/surface ids, unknown renderer keys, unknown dispatch kinds, keybindings to unavailable commands, duplicate ordering keys, and application ids absent from the registry.

- [ ] **Step 2: Run the compiler tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_shell_registration.py`

Expected: FAIL because the shell package does not exist.

- [ ] **Step 3: Define immutable registration input records**

Use frozen product-local dataclasses:

```python
@dataclass(frozen=True)
class CommandContribution:
    descriptor: CommandDescriptor
    order: int


@dataclass(frozen=True)
class SurfaceContribution:
    descriptor: SurfaceDescriptor
    order: int


@dataclass(frozen=True)
class ShellContribution:
    commands: Tuple[CommandContribution, ...] = ()
    surfaces: Tuple[SurfaceContribution, ...] = ()
    keybindings: Tuple[KeybindingDescriptor, ...] = ()
    tool_presentations: Tuple[ToolPresentation, ...] = ()
    timeline_items: Tuple[TimelineItemDescriptor, ...] = ()
    interactions: Tuple[InteractionDescriptor, ...] = ()
```

`ShellContributionRegistry` stores one generic contribution plus an explicit application map and returns no implicit fallback for an unknown non-empty id.

- [ ] **Step 4: Implement deterministic compilation**

The compiler accepts explicit allow sets:

```python
SUPPORTED_RENDERERS = frozenset(
    (
        "command_palette",
        "interaction",
        "generic_timeline",
        "tool",
        "workflow_summary",
        "file_reference",
        "inline_diff",
        "terminal",
        "source_control",
        "preview",
    )
)
SUPPORTED_DISPATCH_KINDS = frozenset(
    (
        "session.create",
        "session.cancel",
        "session.mode",
        "session.command",
        "session.select",
        "workspace.open",
        "shell.surface",
    )
)
```

Merge generic then selected application records, validate all references, filter session-dynamic command availability without adding records, sort by `(order, id)`, and return a validated `ShellDescriptor` built from immutable registration inputs. Never read GUI/TUI files or Host private state.

- [ ] **Step 5: Run compiler tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_shell_registration.py`

Expected: PASS.

- [ ] **Step 6: Commit the product compiler**

```bash
git add src/embedagent/frontend/shell tests/test_shell_registration.py
git commit -m "feat: compile product shell registration"
```

### Task 3: Move Default And Application Contributions Into Product Composition

**Files:**
- Create: `src/embedagent/frontend/shell/defaults.py`
- Modify: `src/embedagent/product_catalog.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`
- Modify: `tests/test_product_host_composition.py`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_non_c_workflow_capabilities.py`

- [ ] **Step 1: Write failing ownership tests**

Assert Host records no longer expose UI metadata and product compilation selects only the chosen application:

```python
def test_host_application_record_has_no_shell_metadata():
    record = BUILTIN_AGENT_APPLICATION_RECORDS[0]
    assert not hasattr(record, "app_shell")
    assert "appShell" not in json.dumps(record.descriptor().metadata)


def test_generic_product_shell_has_no_cpp_contribution():
    descriptor = product_shell_registry().compile(
        application_id=GENERIC_AGENT_APPLICATION_ID,
        session_capabilities={},
    )
    ids = {item.id for item in descriptor.commands}
    assert "workflow.verify" not in ids
```

- [ ] **Step 2: Run ownership tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_product_host_composition.py tests/test_agent_app_protocol.py tests/test_non_c_workflow_capabilities.py`

Expected: FAIL because `AgentApplicationRecord.app_shell` and Host shell constants still exist.

- [ ] **Step 3: Define the minimal generic product contribution**

`minimal_shell_contribution()` contains only:

- commands: new/select/rename/archive/fork session, cancel, mode selection, command palette, permission/user-input response;
- overlays: command palette and interaction;
- timeline renderers: message, reasoning, tool, error, workflow summary, file reference, inline diff;
- core keybindings: focus composer, open commands, new session, cancel;
- no terminal, source control, task panel, plan inspector, preview, editor, or C/C++ command.

Use descriptor constructors in `defaults.py`; do not copy dictionaries from the deleted GUI spec.

- [ ] **Step 4: Define explicit optional and application contributions**

Create named factory functions `desktop_file_contribution()`, `terminal_contribution()`, `source_control_contribution()`, `preview_contribution()`, and `cpp_workflow_contribution()`. The C/C++ contribution selects generic `workflow_summary` and `inline_diff` renderers and adds only commands declared active by session capabilities.

`product_shell_registry()` composes the minimal generic records plus product-enabled optional contributions and a mapping keyed by official application ids.

- [ ] **Step 5: Delete Host shell ownership**

Remove `app_shell` from `AgentApplicationRecord`, remove its `appShell` metadata serialization, and delete `_BASE_APP_SHELL`, `_CODE_APP_SHELL`, `_WEB_APP_SHELL`. Remove `_DEFAULT_C_CPP_APP_SHELL` and `_c_cpp_app_shell()` from `product_catalog.py`; product shell registration replaces them.

- [ ] **Step 6: Run ownership tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_product_host_composition.py tests/test_agent_app_protocol.py tests/test_non_c_workflow_capabilities.py tests/test_shell_registration.py`

Expected: PASS with no Host-owned shell catalog.

- [ ] **Step 7: Commit product-owned registrations**

```bash
git add src/embedagent/frontend/shell/defaults.py src/embedagent/product_catalog.py packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py tests/test_product_host_composition.py tests/test_agent_app_protocol.py tests/test_non_c_workflow_capabilities.py tests/test_shell_registration.py
git commit -m "refactor: move shell defaults into product composition"
```

### Task 4: Inject The Compiled Descriptor Into GUI Bootstrap

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/app_shell.py`
- Delete: `src/embedagent/frontend/gui/backend/app_shell_spec.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/launcher.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `tests/test_gui_app_shell.py`
- Modify: `tests/test_gui_backend_api.py`
- Modify: `tests/test_gui_launcher_app_mode.py`

- [ ] **Step 1: Rewrite GUI tests around injected compilation**

Construct `AppShellService` with `shell_compiler` and assert exact selected output:

```python
service = AppShellService(
    app_host,
    shell_compiler=lambda application_id, capabilities: descriptor,
)
payload = service.bootstrap()

self.assertEqual(payload["shell"], descriptor.to_dict())
self.assertEqual(compiler_calls[0][0], "tests.python")
```

Add a failure test where duplicate ids from a bad registry cause bootstrap to raise `ValueError("duplicate_shell_command:...")`; GUI must not silently fall back to defaults.

- [ ] **Step 2: Run GUI backend tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_gui_app_shell.py tests/test_gui_backend_api.py tests/test_gui_launcher_app_mode.py`

Expected: FAIL because GUI still owns `AppShellSpec` and filters application allow-lists locally.

- [ ] **Step 3: Replace GUI shell spec with compiler injection**

`AppShellService.__init__` receives:

```python
shell_compiler: Callable[[str, Dict[str, Any]], ShellDescriptor]
```

During bootstrap, read the selected `agent_application.id` from strict capability data, call the compiler once, and pass `descriptor.to_dict()` to `AppBootstrap`. Delete `_selected_app_shell_profile`, record filters, local keybinding filters, and every default command/surface definition.

`GUIBackend` requires the compiler; `gui/launcher.py` injects `product_shell_compiler()`. Tests use an explicit minimal compiler fixture. Delete `app_shell_spec.py` in the same commit.

- [ ] **Step 4: Run GUI backend tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_gui_app_shell.py tests/test_gui_backend_api.py tests/test_gui_launcher_app_mode.py`

Expected: PASS.

- [ ] **Step 5: Commit GUI descriptor injection**

```bash
git add src/embedagent/frontend/gui/backend/app_shell.py src/embedagent/frontend/gui/backend/app_shell_spec.py src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/launcher.py src/embedagent/frontend/gui/backend/protocol_payloads.py tests/test_gui_app_shell.py tests/test_gui_backend_api.py tests/test_gui_launcher_app_mode.py
git commit -m "refactor: inject compiled shell into gui"
```

### Task 5: Remove GUI Fallback Catalogs

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`

- [ ] **Step 1: Add failing no-fallback tests**

Assert an empty descriptor produces an empty optional registry and malformed records fail:

```javascript
const model = normalizeAppBootstrap(appBootstrap({ shell: emptyShell() }));
assert.deepEqual(model.shell.commands, []);
assert.deepEqual(model.shell.surfaces, []);
assert.deepEqual(model.shell.keybindings, []);
assert.throws(() => normalizeAppBootstrap(appBootstrap({ shell: { commands: [{}] } })));
```

Assert command palette, surface selection, and keybinding installation use only ids present in `model.shell`.

- [ ] **Step 2: Run webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because local modules still supply default records or labels.

- [ ] **Step 3: Convert workbench modules into descriptor selectors**

`commands.js` exports lookup/filter functions over a passed descriptor. `keybindings.js` binds passed records. `surfaces.js` selects passed surface descriptors. None exports a static catalog. `app-shell/model.js` validates the complete strict payload and does not synthesize ids, labels, dispatch records, placements, renderer keys, or keybindings.

- [ ] **Step 4: Run webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with empty-shell and invalid-descriptor cases.

- [ ] **Step 5: Commit GUI catalog deletion**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-shell/model.js src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js src/embedagent/frontend/gui/webapp/test
git commit -m "refactor: derive gui workbench from shell descriptor"
```

### Task 6: Inject The Same Descriptor Into TUI

**Files:**
- Modify: `src/embedagent/frontend/tui/launcher.py`
- Modify: `src/embedagent/frontend/tui/bootstrap.py`
- Modify: `src/embedagent/frontend/tui/app.py`
- Modify: `src/embedagent/frontend/tui/runtime.py`
- Modify: `src/embedagent/frontend/tui/workbench.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/tui/views.py`
- Modify: `tests/test_tui_runtime.py`
- Modify: `tests/test_terminal_frontend.py`
- Modify: `tests/test_tui_launcher.py`

- [ ] **Step 1: Add failing descriptor-driven TUI tests**

Use a descriptor containing one custom command and one optional surface:

```python
runtime = TerminalRuntime(
    host,
    shell_descriptor=shell_descriptor(
        commands=[command("tests.custom", "session.command")],
        surfaces=[surface("tests.details", "secondary", "workflow_summary")],
    ),
    dispatch=actions.append,
)

assert [item.id for item in runtime.commands()] == ["tests.custom"]
runtime.execute_command("tests.custom", ["arg"])
assert host.command_calls == [("s-1", "tests.custom", ["arg"])]
```

Assert no command or surface absent from the descriptor appears in palette/help/layout state.

- [ ] **Step 2: Run TUI tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_tui_runtime.py tests/test_terminal_frontend.py tests/test_tui_launcher.py`

Expected: FAIL because TUI uses `WORKBENCH_COMMANDS`, `RIGHT_PANEL_SURFACES`, and `BOTTOM_DRAWER_SURFACES`.

- [ ] **Step 3: Inject the product compiler at launch**

`launch_tui()` resolves the selected application id from `LaunchConfig`, compiles the descriptor through `product_shell_compiler()`, and passes it through `run_tui()` to `TerminalRuntime` and `TerminalApp`. No TUI module imports `product_catalog.py` directly.

- [ ] **Step 4: Replace fixed TUI catalogs and command branches**

Delete the three module constants. `WorkbenchState` stores descriptor-derived command/surface tuples. `command_by_id`, palette filtering, help rendering, and surface opening accept the state registry.

`TerminalController.handle_command()` parses the slash name, resolves a descriptor, and calls `TerminalRuntime.execute_command()`. Delete the complete hard-coded branch table for `help`, `new`, `resume`, `sessions`, `snapshot`, `mode`, `plan`, `review`, `diff`, `permissions`, `workspace`, `tasks`, `open`, `edit`, `save`, `explorer`, `inspector`, and `follow`. Renderer-specific behavior is selected by the registered dispatch/renderer keys.

- [ ] **Step 5: Run TUI tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_tui_runtime.py tests/test_terminal_frontend.py tests/test_tui_launcher.py`

Expected: PASS with the custom descriptor and empty descriptor cases.

- [ ] **Step 6: Commit TUI descriptor injection**

```bash
git add src/embedagent/frontend/tui/launcher.py src/embedagent/frontend/tui/bootstrap.py src/embedagent/frontend/tui/app.py src/embedagent/frontend/tui/runtime.py src/embedagent/frontend/tui/workbench.py src/embedagent/frontend/tui/controller.py src/embedagent/frontend/tui/views.py tests/test_tui_runtime.py tests/test_terminal_frontend.py tests/test_tui_launcher.py
git commit -m "refactor: derive tui workbench from shell descriptor"
```

### Task 7: Prove GUI And TUI Consume One Registration Truth

**Files:**
- Create: `tests/test_frontend_shell_parity.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `docs/product/composition.md`
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/platform/frontend-gui.md`
- Modify: `docs/platform/frontend-tui.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Generated: `src/embedagent/frontend/gui/static/*`

- [ ] **Step 1: Add a cross-shell parity test**

Compile once, serialize once, then feed the same data into GUI bootstrap and TUI runtime fixtures:

```python
descriptor = product_shell_compiler()(application_id, capabilities)
gui_payload = app_shell_service(descriptor).bootstrap()["shell"]
tui_runtime = TerminalRuntime(host, shell_descriptor=descriptor, dispatch=lambda action: None)

assert [item["id"] for item in gui_payload["commands"]] == [
    item.id for item in tui_runtime.commands()
]
assert [item["id"] for item in gui_payload["surfaces"]] == [
    item.id for item in tui_runtime.surfaces()
]
```

Run: `uv run python scripts/test-suite.py tdd tests/test_frontend_shell_parity.py`

Expected before final wiring: FAIL; after Tasks 4-6: PASS.

- [ ] **Step 2: Add architecture source guards**

Forbid `app_shell`/`appShell` on Host application records, forbid `WORKBENCH_COMMANDS`, `RIGHT_PANEL_SURFACES`, `BOTTOM_DRAWER_SURFACES`, and forbid `default_app_shell_spec`. Assert the only product default registration module is `src/embedagent/frontend/shell/defaults.py`.

- [ ] **Step 3: Run architecture guards**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`

Expected: PASS.

- [ ] **Step 4: Update owning documents**

Document product compiler ownership, descriptor injection, supported contribution kinds, and fail-closed validation. Update the code/doc matrix for the new `frontend/shell` package. Replace Stage 3 status with the Stage 4 minimal-workbench blocker.

- [ ] **Step 5: Run webapp tests and build committed assets**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm run build`

Expected: exit code 0 and refreshed static assets.

- [ ] **Step 6: Run complete Python and lint gates**

Run: `uv run python scripts/test-suite.py full`

Expected: PASS.

Run: `uv run --locked python scripts/lint.py`

Expected: PASS.

- [ ] **Step 7: Verify retired catalogs are absent**

Run: `rg -n "WORKBENCH_COMMANDS|RIGHT_PANEL_SURFACES|BOTTOM_DRAWER_SURFACES|default_app_shell_spec|_BASE_APP_SHELL|_CODE_APP_SHELL|_WEB_APP_SHELL|appShell" src packages tests`

Expected: no production matches; fixture assertions may contain a retired token only when explicitly proving rejection.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 8: Commit Stage 3 gates, docs, and assets**

```bash
git add tests/test_frontend_shell_parity.py tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py docs/product/composition.md docs/platform/frontend-protocol.md docs/platform/frontend-gui.md docs/platform/frontend-tui.md docs/references/code-doc-matrix.md docs/current-status.md docs/implementation-roadmap.md src/embedagent/frontend/gui/static
git commit -m "docs: establish shared shell registration"
```

## Stage Exit Criteria

- One product compiler emits the complete descriptor consumed by both GUI and TUI.
- Protocol owns descriptor shape but no default records or compiler behavior.
- Host application records contain no shell profile, allow-list, or UI metadata.
- GUI backend and TUI launcher require explicit compiler/descriptor injection.
- GUI and TUI contain no fallback command, surface, keybinding, tool, workflow, or application catalog.
- Duplicate ids, unknown renderers, unknown dispatch kinds, and dangling keybindings fail closed.
- Cross-shell parity, architecture guards, full Python tests, lint, webapp tests, and webapp build pass.
