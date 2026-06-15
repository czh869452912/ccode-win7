# T3code-Inspired Pi-Bounded Workbench Design

## Purpose

Redesign EmbedAgent's GUI and TUI as a long-term Agent-native workbench. The
target experience should lean heavily toward T3code's product shape while
preserving Pi's small-core, decoupled, extensible architecture philosophy and
EmbedAgent's hard Windows 7, offline, Python 3.8, and default C/C++ workflow
constraints.

The design is intentionally frontend-focused. It does not change Agent Core
workflow truth, tool activation, permission policy, transcript ownership, or
the bundled C/C++ workflow package semantics.

## Goals

- Make the GUI feel like a T3code-style Agent workbench: project/thread
  sidebar, central Agent timeline, rich composer, thread-scoped right-panel
  surfaces, and optional bottom drawer.
- Make the TUI an isomorphic keyboard-first shell rather than a reduced GUI:
  same mental model, same command IDs, same surface concepts, different
  rendering.
- Adopt T3code's maintainable frontend architecture ideas where they fit:
  surface registry, persisted UI state, command palette, keybinding rules, and
  composable chat/timeline/composer boundaries.
- Preserve Pi-style decoupling: frontends consume read models and issue
  commands through protocol boundaries; they do not own workflow, permission,
  tool, extension, or history policy.
- Keep Windows 7 and offline deployment as release gates.

## Design Principles

### T3code For The Shell

T3code provides the target product shape for frontend interaction:

- a persistent thread/project sidebar
- a central chat/timeline column
- a strong composer that owns everyday interaction
- thread-scoped right-panel surfaces
- optional terminal/run drawer
- command palette and keybinding-driven workflows
- local UI state persisted per thread where useful

EmbedAgent should copy the experience and frontend architecture model, not
T3code's cloud, relay, remote environment, Electron, or multi-provider control
plane.

### Pi For The Core Boundary

Pi provides the architectural discipline:

- keep Agent Core small and workflow-neutral
- expose capability and runtime state through read models
- keep durable state reducer-backed
- keep UI shell state out of session history
- let replaceable shells and workflow packages evolve independently

The GUI and TUI may become richer, but they must remain shells.

### Windows 7 Is Not Optional

The GUI build target remains bundled WebView2 Fixed Version 109, aligned with
the current `chrome109` build target. The TUI remains usable in raw console and
ConEmu-style hosts, with ASCII-safe and low-color fallbacks.

## Current Baseline

The repository already has the right high-level separation:

- GUI lives under `src/embedagent/frontend/gui/` and uses React, FastAPI,
  WebSocket, and pywebview.
- TUI lives under `src/embedagent/frontend/tui/` and uses `prompt_toolkit`,
  pure state, reducers, controllers, services, and view modules.
- Frontend protocol truth is documented in `docs/frontend-protocol.md`.
- Session history truth is `transcript.jsonl -> Session -> bootstrap/history`.
- Workflow semantics flow through Agent Core and the default C/C++ workflow
  extension, not through frontends.

The current GUI is already a three-area shell, but its inspector is still a
tabbed side panel rather than a thread-scoped surface system. The current TUI is
modular, but it needs a stronger overlay, command palette, keybinding, and
surface model to match the long-term workbench shape.

## Target Information Architecture

Both GUI and TUI share this product model:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Header: session title | mode | phase | runtime health | commands     │
├──────────────┬───────────────────────────────────────┬──────────────┤
│ Sidebar      │ Agent Timeline                         │ Right Panel  │
│              │                                       │ Surfaces     │
│ Sessions     │ User / assistant messages              │              │
│ Project      │ Turn groups                            │ Plan         │
│ Resources    │ Agent steps                            │ Diff         │
│ Files        │ Tool activity                          │ Preview      │
│ Skills       │ Inline plans / diffs / interactions    │ Runtime      │
│ Recipes      │                                       │ Diagnostics  │
│ Artifacts    │ Composer                               │              │
├──────────────┴───────────────────────────────────────┴──────────────┤
│ Optional bottom drawer: terminal / run output / long logs            │
└─────────────────────────────────────────────────────────────────────┘
```

The central Agent timeline is the spine. Other surfaces orbit the active
session/thread and active turn.

## GUI Design

### Layout

The GUI should move from the current `Sidebar + Timeline + Inspector` shape to
a T3code-style workbench:

- left `ThreadSidebar`
  - current session/thread list
  - new session entry point
  - project/resource groups: files, local skills, prompts, recipes, artifacts
- center `ChatColumn`
  - `ChatHeader`
  - `MessagesTimeline`
  - `ChatComposer`
  - optional `Branch/Mode/Runtime` footer strip where relevant
- right `RightPanelTabs`
  - thread-scoped surface registry
  - active surface rendering
  - responsive inline/sheet behavior
- bottom `WorkbenchDrawer`
  - terminal-like run logs, long tool output, future local terminal surfaces

### Messages Timeline

The timeline should group runtime activity by turn and step:

- user message
- leading system/context notices
- agent step header
- tool activity group
- reasoning summary where available
- assistant result
- inline cards for permission, user input, plan, diff, compaction, recovery, and
  runtime warnings

The GUI can reuse the existing `session-runtime/projector.js` direction, but it
should converge toward a `MessagesTimeline` component boundary similar to
T3code's.

### Composer

The composer becomes the primary interaction surface:

- slash command suggestions
- `@file` and resource mentions
- mode chip
- optional model/runtime metadata chip when safe and configured
- pending permission and user-input actions
- plan follow-up actions
- send/stop behavior
- keyboard-first operation

The composer must call backend-owned commands and interaction endpoints. It
must not resolve permissions, activate tools, or mutate workflow state locally.

### Right Panel Surfaces

Replace the current inspector-tab mental model with thread-scoped surfaces:

- `plan`
- `diff`
- `preview`
- `runtime`
- `diagnostics`
- `artifacts`
- future `terminal`

Each session remembers:

- whether the right panel is open
- ordered surface list
- active surface id
- surface-local UI state where harmless, such as scroll position or selected
  preview

This state is UI state only. It should persist in frontend settings/local
storage or an equivalent shell settings file, never in `transcript.jsonl`.

### Command Palette

GUI buttons, menus, slash commands, and shortcuts should converge on stable
command IDs:

- `session.new`
- `session.resume`
- `session.cancel`
- `mode.set.explore`
- `mode.set.spec`
- `mode.set.build`
- `mode.set.debug`
- `mode.set.verify`
- `surface.toggle.plan`
- `surface.toggle.diff`
- `surface.toggle.preview`
- `surface.toggle.runtime`
- `surface.toggle.diagnostics`
- `resources.reload`
- `composer.send`
- `composer.stop`

Command implementations must remain frontend adapters over protocol calls or
local UI state updates.

## TUI Design

The TUI should share the same workbench model while using terminal-native
interaction patterns.

### Layout Modes

- Wide terminal: sidebar, timeline, and active surface can appear together.
- Medium terminal: timeline plus one auxiliary surface.
- Narrow terminal: timeline/composer main view with overlays for sidebar,
  surfaces, command palette, permissions, and selectors.

### Pi-Inspired Interaction Patterns

Adopt Pi's TUI ideas without porting its TypeScript runtime:

- overlay-based dialogs and selectors
- command palette
- status/footer line with session, mode, runtime, follow, and dirty indicators
- keyboard-first navigation
- width-safe truncation and wrapping
- paste-friendly multiline composer behavior
- selector-based permission and user-input handling
- diff and tool output rendering that is stable and compact

The existing `prompt_toolkit` package structure remains valid. The likely
additions are:

- `SurfaceState`
- `CommandPaletteState`
- `KeybindingContext`
- `FooterStatus`
- overlay view builders
- selector components

### TUI State Ownership

The TUI reducer may own:

- active surface
- surface stack
- explorer selection
- command palette filter
- layout mode
- composer draft
- footer status projection

It must not own:

- workflow phase truth
- task truth
- permission decisions
- tool activation
- extension loading
- session history truth

## Shared Shell Model

Introduce a frontend workbench model as a shell-level contract. It can be
implemented separately in JS and Python at first, but the concepts and fixtures
should match.

### Workbench UI State

Suggested state families:

- `ThreadSidebarState`
  - session list projection
  - selected session
  - selected resource group
- `SurfaceState`
  - open surfaces by session
  - active surface
  - surface-local harmless UI state
- `ComposerState`
  - draft text
  - mention candidates
  - slash command candidates
  - pending interaction rendering state
- `CommandPaletteState`
  - command list
  - filter
  - active command
  - context
- `KeybindingState`
  - defaults
  - user overrides
  - context predicates
- `LayoutState`
  - sidebar width
  - right panel open/closed
  - bottom drawer state
  - compact layout mode

### Command Registry

The command registry should describe commands, not execute Core behavior
directly. Each command descriptor should include:

- stable id
- label
- category
- default shortcut, if any
- frontend availability predicate
- handler kind: local UI update, protocol request, or message submission

### Keybinding Rules

Borrow T3code's rule shape, but keep implementation small:

```json
{
  "key": "mod+k",
  "command": "commandPalette.toggle",
  "when": "!composerFocus"
}
```

Initial predicate support can be limited to boolean context keys, `!`, `&&`,
and `||`. Unknown context keys evaluate to false. Invalid rules are ignored with
diagnostics.

## Protocol Boundary

The workbench consumes existing and future-safe protocol/read-model data:

- session bootstrap
- session snapshot
- session events
- task projection
- permission context
- tool catalog
- capability snapshot
- runtime configuration
- compaction state
- recovery state
- extension diagnostics
- local resource reload state

Frontend code must not infer policy from these diagnostics. It may display
them, route them into surfaces, and invoke explicit backend endpoints.

## Windows 7 And Offline Constraints

### GUI

- Keep GUI build target at `chrome109`.
- Keep bundled WebView2 Fixed Version 109 as the expected renderer.
- Do not add Electron, Node runtime requirements, online CDNs, remote relay
  dependencies, or browser automation dependencies.
- Avoid JS and CSS features not supported by Chrome 109 unless build tooling
  reliably transpiles them.
- Avoid dependencies that require modern browser APIs beyond WebView2 109.
- Keep static assets self-contained under the existing GUI static bundle.

### TUI

- Support raw console and ConEmu-style hosts.
- Keep all critical paths keyboard-accessible.
- Preserve ASCII and low-color fallbacks.
- Do not depend on terminal image support, mouse input, or advanced ANSI
  behavior for primary workflows.

### Packaging

UI work must not add runtime-invoked external binaries unless
`scripts/offline-runtime-contract.json` is updated in the same implementation
slice. Design and frontend static assets should not add new runtime toolchain
requirements.

## Non-Goals

- Porting T3code's Electron shell.
- Porting T3code's cloud auth, relay, remote environment, or multi-provider
  control plane.
- Making the frontend responsible for workflow policy, permission policy,
  active-tool selection, extension loading, or session-history reconstruction.
- Adding public plugin marketplaces, online installs, or runtime dependency
  installation.
- Turning EmbedAgent into a general browser automation agent or public remote
  coding platform.
- Rebuilding the C/C++ workflow package as part of the frontend redesign.

## Implementation Program

### Slice 1: Workbench Contract

Define the shared frontend workbench concepts before moving UI code:

- surface schema
- command IDs
- keybinding rule shape
- layout state shape
- protocol mapping for each surface
- GUI/TUI test fixtures

Verification:

- pure JS tests for command and surface reducers
- Python tests for TUI command/surface state
- docs updated for frontend protocol and module boundaries

### Slice 2: GUI T3 Shell

Refactor the GUI into T3code-style boundaries:

- `AppSidebarLayout`
- `ThreadSidebar`
- `ChatColumn`
- `MessagesTimeline`
- `ChatComposer`
- `RightPanelTabs`
- `WorkbenchDrawer`

Keep backend APIs unchanged during this slice.

Verification:

- existing GUI webapp tests
- focused tests for session activation, right-panel persistence, and timeline
  rendering
- static rebuild

### Slice 3: GUI Interaction Architecture

Add the richer interaction layer:

- command palette
- keybinding store
- slash command and mention presentation
- pending interaction composer actions
- surface persistence per session

Verification:

- command/keybinding reducer tests
- browser-level smoke for command palette and surface toggles
- GUI backend API tests unchanged or updated only for explicit contract changes

### Slice 4: TUI Pi Interaction Model

Bring the TUI into the same workbench mental model:

- surface stack
- command palette overlay
- selector overlays for permissions and user input
- footer status line
- shared command IDs
- layout degradation for narrow terminals

Verification:

- `tests/test_terminal_frontend.py`
- focused TUI reducer/controller tests
- manual raw console and ConEmu smoke checklist

### Slice 5: Shared Shell Fixtures And Documentation

Unify the GUI/TUI concepts with shared fixtures and docs:

- documented command registry
- documented surface registry
- keybinding defaults for GUI and TUI
- frontend protocol updates for visible read models
- module docs for GUI and TUI

Verification:

- docs/source sync review
- architecture tests that prevent reintroduction of old `todos` or `code`
  vocabulary in frontend contracts

### Slice 6: Compatibility And Polish

Run compatibility hardening after the new shell shape exists:

- Win7 GUI smoke
- WebView2 renderer report
- Chrome 109 feature audit
- bundle size and offline asset check
- TUI raw console/ConEmu smoke
- responsive layout polish

Verification:

- `validate-gui-smoke.cmd` on Win7 bundle when available
- local GUI tests and build
- relevant Python fast tests

## Acceptance Criteria

- GUI presents a T3code-like workbench with thread sidebar, central timeline,
  rich composer, right-panel surfaces, and optional bottom drawer.
- TUI presents the same workbench concepts through keyboard-first overlays,
  selectors, footer state, and surfaces.
- GUI and TUI share command IDs and keybinding concepts.
- Right-panel/surface/layout state is persisted as shell UI state, not session
  history.
- Frontend code consumes Agent Core read models and protocol APIs without
  owning workflow or permission policy.
- GUI static build remains compatible with Chrome/WebView2 109.
- Offline bundle requirements remain intact.
