# Overall Solution Architecture

## 1. Scope

EmbedAgent is a native, offline-first Agent IDE core for C/C++ engineering.

The stable architecture assumptions are:

- Windows 7 compatibility
- Python 3.8 runtime target
- Offline bundle delivery
- Agent Core first, UI shells replaceable
- Clang-centered toolchain

## 2. Top-Level Structure

The product is organized around one main execution spine:

`Frontend -> Agent App Protocol / Core Adapter -> Hosted Runtime -> InProcessAdapter -> Session Runtime -> QueryEngine -> AgentKernel -> AgentLoop / AgentLifecycleJournal -> AgentToolActionService -> AgentExtensionHost / ToolRuntime / PermissionPolicy -> Context/Stores`

### Frontend Layer

- `src/embedagent/frontend/tui/`
- `src/embedagent/frontend/gui/`

These are shells only. They do not own workflow semantics.

The GUI shell has a replaceable app-shell boundary for desktop-host state:
`src/embedagent/frontend/gui/backend/app_shell.py` wraps the GUI app host and
projects recent workspaces, active workspace metadata, safe host/runtime/
renderer diagnostics, app-level command metadata, and GUI-local settings. The
matching frontend model lives under
`src/embedagent/frontend/gui/webapp/src/app-shell/`. This boundary is not Agent
Core: it must not own sessions, transcript history, workflow state, mode/tool
policy, permission decisions, extension loading, provider configuration, or
runtime reducers.

The React GUI renderer uses focused T3-style local state modules for workbench
surfaces, thread/session selection, composer drafts, terminal display buffers,
source-control display state, and preview display state. In particular,
`webapp/src/session-runtime/thread-state.js` owns the active thread id, session
summary list, and history-integrity display read model, and
`webapp/src/composer/composer-state.js` owns draft text. The retired
`sidebarTab` / `set_sidebar` sidecar is not part of this renderer state model.
These modules are
renderer read models only and must not become session history, workflow truth,
tool policy, permission policy, extension loading policy, provider
configuration, telemetry, or Agent Core runtime reducers.
Workbench command visibility, right-panel launchers, bottom-drawer tabs, and
keybinding targets are filtered from GUI app-shell capabilities returned by
`GET /api/app/bootstrap`. App-shell app/workspace/workbench commands, surfaces,
and keybindings are backend-declared descriptor records rather than bare string ids;
command-palette group titles/descriptions/order and palette labels/placeholders
are also app-shell descriptors. Right-panel chrome copy, tab action labels,
aria labels, empty-state text, and default surface icon fallback come from
`capabilities.surfaces.chrome`; File Preview breadcrumb aria text and markdown
mode glyphs are part of the same app-shell chrome contract.
Workbench command labels are visible descriptors too: app/workspace/workbench
commands without explicit labels are omitted from visible command entrypoints,
dynamic slash commands must provide explicit `label`, `usage`, or `slash`
metadata, and command-palette rows must not fall back to command ids for
titles. Built-in GUI shell command execution is also descriptor-owned through
`dispatch.kind`; renderer controllers do not switch on fixed command ids to
infer actions, and supported dispatch kinds are routed through an explicit
renderer-local handler registry rather than a dispatch-kind switch.
Bottom-drawer surface commands may carry the same
dispatch descriptors; the Terminal drawer opens through
`terminal.ensure_open`, not through a renderer branch on the drawer kind.
Bottom-drawer body mounting is renderer-local `bodyKind` metadata on supported
surface definitions, and the default shell does not expose drawer surfaces
without an implemented body. Supported body kinds route through
`BOTTOM_DRAWER_BODY_RENDERERS`, not a component switch.
Bottom-drawer activation side effects use renderer-local `activationKind`
metadata, so selecting the terminal drawer is not inferred from a fixed drawer
kind in the terminal controller. Supported bottom-drawer activation kinds route
through an explicit renderer-local handler registry rather than a controller
switch.
Terminal-controller right-panel surface validation and terminal pane action
payload assembly are centralized in `TERMINAL_SURFACE_KIND` and
`terminalSurfaceActionInput(...)`, not repeated per-action surface-kind
checks.
Right-panel body mounting uses the same renderer-local metadata path scoped by
active app-shell capabilities; app-shell surface ids select visibility and
labels, while renderer registry records select the concrete body component.
Hidden resource surfaces such as `file` are backend-declared with
`launcher=False` / `command=False` rather than renderer-only body fallback.
Supported body kinds route through `RIGHT_PANEL_BODY_RENDERERS`, not a
component switch.
Generic `SurfacePanel` bodies are selected by renderer-local `panelKind`
metadata, so Plan, Diff, Source Control, Settings, and Diagnostics panels do
not require branches on app-shell surface ids.
Commands in undeclared or untitled palette groups remain hidden
rather than using title-cased group ids, and missing command row description/meta copy
remains empty instead of falling back to command ids. Surface command row
descriptions come from surface descriptors rather than surface/drawer ids.
Session/workspace palette row leading markers also come from command-palette
label descriptors and remain empty when absent. Command-palette group leading
markers come from explicit group descriptors and are not synthesized from group
titles. Command-palette shortcut labels and separators are app-shell label
descriptors rather than renderer-local platform defaults.
Labels, descriptions, icon keys, command/slash metadata, ordering, visibility,
and read-only/offline hints come from the app shell. Surface-owned panel
headings, including the right-panel Files surface header, use the active
surface descriptor title rather than renderer-local defaults. Opening a
right-panel surface also uses the declared surface title instead of parsing
command labels such as `Open ...`. Right-panel surface open behavior uses
renderer-local `openKind` metadata, so terminal session creation is not
inferred from a fixed surface id in the controller; supported `openKind`
values are routed through an explicit renderer-local handler registry rather
than a controller switch. App-level preview and Files-browser open flows call
semantic right-panel controller methods instead of dispatching concrete
resource surface kinds directly, while file-preview opening and workspace-file
content loading are delegated to `file-preview-controller.js`. Those semantic
open methods still require the active app shell to declare the target
right-panel surface; hidden capabilities such as Generic Agent without Preview
or a specialized agent without File Preview do not reopen the local renderer's
supported bodies through direct controller calls. Those semantic open methods
return whether a surface was actually opened, and the file-preview controller
stops loading when File Preview is not declared so unsupported agents do not
fetch preview content behind a hidden UI. Preview session
open/refresh/external-open orchestration is delegated to
`preview-controller.js`, which preflights the same semantic Preview capability
before invoking backend preview routes.
Source Control status refresh and file-diff requests likewise require the
active app shell's Source Control capability before invoking backend
source-control routes.
Timeline/manual Diff surface opening is delegated to `diff-surface-controller.js`,
so `App.jsx` does not construct diff surface state or dispatch
`diff_surface_opened` directly.
Terminal service calls require the active app shell's Terminal capability
before opening, listing, writing, clearing, restarting, closing, or attaching
terminal panes, even when stale terminal UI state still exists locally.
Right-panel terminal surface creation follows the same rule
and refuses to start a terminal session when the active app shell omits the
right-panel Terminal surface. Right-panel activation side effects use
renderer-local `activationKind` metadata through the
`right-panel-controller.js` `RIGHT_PANEL_ACTIVATION_HANDLERS` registry, not
inline App checks for terminal surface ids or direct terminal-session calls.
Surface
capability records without explicit app-shell titles remain diagnostics only;
they do not become visible launchers or surface commands, and the renderer does
not derive titles from surface kind/id strings. Resource surface helper titles
use only instance data such as file basenames, preview ids/URLs, and terminal
ids; missing preview instance data does not create a fallback tab.
GUI home/sidebar copy for workspace and thread sections is also app-shell
declared through `capabilities.home`; renderer components consume that read
model instead of owning the default workspace/thread wording.
Renderer-local surface registries describe only how a known
surface renderer is mounted and are exposed through derived helpers rather than
fixed surface id lists; they do not grant app-shell entrypoints when the backend
declaration omits the `capabilities` object or the relevant command, surface,
or keybinding descriptor arrays. Persisted workbench surface state is re-sanitized after app
bootstrap or workspace switch against the same declaration, so stale local UI
state cannot reopen surfaces that the active app shell does not expose.
Live workbench surface-open actions use the same app-shell declaration gate:
payload-driven Diff intents, direct `workbench_surface_opened` actions, and
other reducer-level opens must not create right-panel or bottom-drawer surfaces
that the active app shell does not declare.
Shallow persisted surface descriptors are normalized by the renderer-local
surface registry through `persistedSurfaceFrom(...)`; the browser localStorage
state module must not own fixed file/terminal surface field rules. Per-kind
surface instance metadata is initialized through `SURFACE_INITIALIZERS[kind]`
inside that same renderer-local model, not by branches in `makeSurface(...)`.
App capability cleanup reads `persistedSurfaceDefinitions(appCapabilities,
placement)` and registry-declared `persistedRelatedKinds`, so hidden/resource
surfaces such as File under Files are not hard-coded in UI-state sanitization.
Right-panel open-time preparation also routes through
`SURFACE_OPEN_PREPARERS[surface.kind]`; `openSurface(...)` must not own
file/preview preparation branches. Right-panel surface-local pane operations
also route through `SURFACE_PANE_HANDLERS[surface.kind]`; terminal
split/activate/close metadata must not live as generic reducer terminal-kind
branches.
The default GUI app-shell descriptor set is an injected `AppShellSpec` from
`src/embedagent/frontend/gui/backend/app_shell_spec.py`; `AppShellService`
composes that spec with safe active-core projections instead of owning inline
surface, command, or keybinding lists.
App bootstrap also projects a safe selected-agent application registry and
empty-state read model into app-shell capabilities. Before workspace activation
that projection comes from the backend-selected application registry declared
by the app host or launcher; after workspace activation the active Core's
capability projection is authoritative. The GUI can adapt labels/copy for
generic or specialized agents without creating a core or making app bootstrap a
session-history source. Selected agent application manifests may also declare
`metadata.appShell` allow-lists for app commands, right-panel surfaces,
bottom-drawer surfaces, keybinding command targets, command-palette groups,
and disabled GUI capability ids. `AppShellService` applies that profile to the
injected `AppShellSpec` before returning capabilities, so a generic base agent
does not inherit Preview, Diff, or Source Control entrypoints from the default
C/C++ application. Surface capabilities may additionally declare safe dynamic
right-panel descriptor surfaces: unknown surface kinds are retained only when
they map to a non-executing `surface_panel` body with a safe generic panel kind,
so specialized agents can add read-only GUI affordances without frontend plugin
execution or new service calls. Renderer app-shell normalizers preserve a missing
backend product name as empty rather than inventing the bundled product name;
untitled thread fallback prefixes come from `home.threads` descriptors rather
than renderer-local English copy.
Retired Inspector sidecar state for artifacts, review panes, permission-rule
panes, runtime panes, workspace previews, and event logs has been removed; those
concerns now appear only through active surfaces, session activities,
interaction state, or app-shell diagnostics.
The old `Inspector.jsx` component and `inspectorTab` / `inspectorKind` dispatch
path are retired. Right-panel fallback content is rendered by `SurfacePanel`
from renderer-local `panelKind` metadata.
The GUI artifact refetch facade has also been removed: GUI routes no longer
expose `/api/artifacts`, and WebSocket/frontend callback contracts no longer
carry `artifacts_refresh`.
The hosted `/artifacts` slash command and TUI artifact browser surface are also
retired. Tool-result stored paths may remain in transcript/session metadata for
evidence and cleanup, but frontends no longer get a standalone artifact browse
API.
The old GUI workflow-runtime display helper is also removed; renderer workflow
detail must come from backend-declared session snapshot, capability, or
activity projections instead of synthesized C/C++ phase rows.
Frontend protocol adapters preserve backend-declared mode state. They must not
import the built-in mode default or inject `explore` when a selected
application/profile leaves `current_mode` empty.

GUI thread lifecycle operations are exposed through the session lifecycle facade
and consumed by the GUI app shell through
`capabilities.thread_lifecycle.actions` descriptor records rather than a
renderer-owned fixed action list. The default app shell currently declares
`rename`, `fork`, and `archive`; alternate shells may omit or relabel those
entries. Action labels, disabled reason labels, prompt, confirmation, success,
empty-title, and failure copy also live on those descriptors rather than in the
renderer lifecycle controller. Missing action labels keep actions out of the
visible rail, and missing notice copy remains absent rather than being
synthesized from action ids or labels. Lifecycle actions update session
summary/projection metadata used by app thread lists; they do not rewrite
transcript history, own workflow state, activate tools, decide permissions,
load extensions, or create source-control checkpoints.
Native prompt/confirm access for those renderer-initiated lifecycle prompts is
isolated in `app-runtime/browser-dialog-service.js`; `App.jsx` injects that
service into the lifecycle controller rather than calling browser dialog APIs
directly.

GUI session list loading is owned by the renderer
`app-runtime/session-list-controller.js`. The controller is the only webapp
module that fetches `/api/sessions` for the thread list and dispatches
`sessions_loaded`; `App.jsx` composes the controller but does not own the
session-list API/action pair.

GUI JSON request/error handling is owned by
`app-runtime/http-client.js`. `App.jsx` imports the shared `fetchJson` helper
and passes it into focused controllers; it does not define its own HTTP client
or call browser `fetch` directly.

GUI active-workspace read-model refresh is owned by
`app-runtime/active-workspace-data-loader.js`. After workspace activation, that
loader coordinates session list refresh, session command capability refresh,
workspace file tree refresh, and local status-surface refresh from injected
dependencies. `App.jsx` wires the dependencies but does not inline the refresh
fanout.

GUI panel resize pointer handling is owned by
`app-runtime/panel-resize-controller.js`. The controller clamps panel widths,
tracks pointer drag state, and mutates the CSS variables on the document root;
`App.jsx` only wires sidebar and right-panel resize callbacks.

GUI WebSocket payload handling is split between pure effect derivation and
effect execution. `app-runtime/socket-message-effects.js` derives transport
events, reducer actions, and loader requests from backend messages, while
`app-runtime/socket-effect-executor.js` applies those effects by updating the
active session transport read model, dispatching reducer actions, invoking
loader requests, and triggering reload recovery. `App.jsx` stays the
composition root and does not own transport append/recovery loops.

The GUI terminal bottom drawer is also app-shell hosted. `GUIBackend` owns an
in-memory terminal service bound to the active workspace and exposes
thread-scoped terminal HTTP routes plus `terminal_event` WebSocket messages.
GUIBackend resolves workspace-bound Agent Core access explicitly through the
app host; it does not carry a compatibility core proxy as route state.
The service uses Python stdlib subprocess pipes for Windows 7 compatibility and
offline deployment; it is not a full PTY and does not introduce ConPTY,
`node-pty`, `pywinpty`, `pexpect`, runtime Node, Electron, Docker, WSL, VS Code,
or online-service dependencies. Terminal buffers are GUI-local display state
only and must not become transcript history, workflow state, telemetry,
permission policy, runtime reducer truth, source-control checkpoints, or Agent
Core behavior. The Terminal drawer command is an app-shell surface descriptor
with `dispatch.kind: terminal.ensure_open`; drawer kind alone has no
terminal-specific execution semantics. The default bottom drawer exposes only
implemented Run Output and Terminal bodies; stale declarations without a
renderer body are deleted rather than shown through a fallback.

The GUI Source Control right-panel is another app-shell hosted surface.
`GUIBackend` owns an active-workspace-bound `SourceControlService` that invokes
only read-only local Git status/diff commands through bundled or workspace
MinGit. The React source-control model displays local changes and opens the
existing Diff surface for selected files. Diff workbench tab titles come from
explicit diff payload titles or the app-shell surface descriptor rather than a
renderer `"diff"` fallback. Source-control group order and file status badge
labels come from `capabilities.source_control.chrome` instead of renderer
fixed group arrays, status-initial inference, or raw group/provider id fallback.
This slice does not stage, commit,
push, pull, contact remote providers, create checkpoints, or write transcript
history, workflow state, telemetry, permission policy, runtime reducer truth,
provider configuration, extension loading state, or Agent Core behavior.
Frontend source-control, terminal, and preview API helpers do not contain
helper-local request-failure copy; when backend error payloads omit detail,
controllers fall through to the app-shell chrome fallback declared for the
surface.

The GUI Preview right-panel is app-shell hosted as well. `GUIBackend` owns a
workspace-bound `PreviewService` that accepts local loopback HTTP URLs only,
probes them through Python stdlib networking, and may open the same local URL
in the system browser. It does not embed an online browser service, execute
browser automation, contact remote hosts, mutate source control, write
transcript history, workflow state, telemetry, permission policy, runtime
reducer truth, provider configuration, extension loading state, or Agent Core
behavior.

### Protocol / Core Layer

- `src/embedagent/protocol/`
- `src/embedagent/core/`

This is the stable contract boundary between UI shells and Agent Core. The GUI
consumes Agent App Protocol snapshots/events and backend-declared capability
metadata instead of hard-coding scenario-specific modes, tools, or workflow
packages.

### Agent Core Layer

- `src/embedagent_core/`
- `src/embedagent_core/query_engine.py`
- `src/embedagent_core/agent_lifecycle.py`
- `src/embedagent_core/agent_kernel.py`
- `src/embedagent_core/agent_loop.py`
- `src/embedagent_core/agent_tool_action_service.py`
- `src/embedagent_core/agent_extension_host.py`
- `src/embedagent_core/agent_event_bus.py`
- `src/embedagent_core/session.py`
- `src/embedagent_core/interaction.py`
- `src/embedagent_core/model.py`
- `src/embedagent_core/tool_contracts.py`
- `src/embedagent_core/ports.py`
- `src/embedagent_core/policies.py`
- `src/embedagent_core/guard.py`
- `src/embedagent_core/prompt_assembly_service.py`
- `src/embedagent_core/compactor.py`
- `src/embedagent_core/context_window.py`
- `src/embedagent_core/turn_snapshot.py`
- `src/embedagent_core/capabilities.py`
- `src/embedagent_core/runtime_config.py`
- `src/embedagent_core/compaction_state.py`
- `src/embedagent_core/recovery_state.py`
- `src/embedagent_core/workflow_package_manifest.py`
- `src/embedagent_core/extensions.py`
- `src/embedagent_core/permissions.py`

This is the generic Agent Core package. Agent Core is dependency-inverted: it
owns turn state, transcript records, reducers, permission contracts, extension
dispatch, loop control, and abstract ports. Host/product layers implement the
ports. C/C++ workflow behavior is a workflow package, not a Core dependency.
Core must not import the product package, host package, GUI, TUI, or workflow
packages.

### Host And Product Composition Layer

- `src/embedagent_host/inprocess_adapter.py`
- `src/embedagent_host/hosted_command_service.py`
- `src/embedagent_host/hosted_interaction_service.py`
- `src/embedagent_host/hosted/`
- `src/embedagent/agent_applications.py`
- `src/embedagent/session_runtime.py`
- `src/embedagent/session_projector.py`
- `src/embedagent/session_history.py`
- `src/embedagent/tools/`
- `src/embedagent/context.py`
- `src/embedagent/project_extensions.py`
- `src/embedagent/slash_commands.py`

This layer assembles Agent Core, selected agent applications, workflow packages, local resources,
project-local extensions, product session hosting, CLI/TUI/GUI bridges, and
offline bundle integration. It is replaceable product composition, not generic
Core.

Hosted `AgentApplication` records declare scenario identity, manifest metadata,
profile, mode policy, extension manager, and workflow refreshers. The hosted
application registry stores built-in applications as `AgentApplicationRecord`
data. Profile-only applications build directly from profile records; workflow
backed specialized applications declare a `builder_path` that resolves to the
package-owned application factory, so the generic loader does not contain C/C++
workflow branches. Profile-only records stay in the base registry and can be
built without importing the bundled C/C++ workflow package. Workflow-backed
built-ins, including the default C/C++ product application, are added only by the
hosted product registry in `src/embedagent_host/agent_application_registry.py`.
The default C/C++ application record and app-shell overlay live in
`src/embedagent/workflow_packages/c_cpp/application_record.py`; the base
registry does not import that package. The selected registry exposes safe
`AgentApplicationManifest` records for GUI capability projection. Agent profiles
declare scenario mode metadata, base tool policy, and GUI mode capability
projection.
Built-in application records also carry `metadata.appShell` GUI allow-lists,
so the hosted GUI can derive a smaller base shell or a specialized workflow
shell from the selected application manifest rather than assuming the default
C/C++ workbench surface set.
The legacy/global `src/embedagent/modes.py` facade is intentionally backed by
the generic base agent profile; hosted runtime paths use the selected
`AgentApplication.profile` for specialized writable globs, prompt copy, mode
descriptors, and active-tool base policy through
`src/embedagent/agent_profile_runtime.py`. `InProcessAdapter` composes those
shared profile runtime policies and must not inline product prompt rendering,
write-glob evaluation, or mode-switch parsing. The default C/C++ profile is
loaded only from `src/embedagent/workflow_packages/c_cpp/agent_profile.py` by
the default C/C++ application, not by the global mode facade or generic
application loader.
Workflow packages declare scenario-specific
workflow tools, packs, prompts, resources, manifests, workspace-profile
detectors, and package-owned tool names. Provider-facing schemas are always
projected from explicit active tool names computed by the shared extension
boundary.

The base application registry exposes profile-only `embedagent.generic`,
`embedagent.python`, and `embedagent.html` applications. The hosted product
registry composes those base records with `embedagent.default_c_cpp` as the
packaged default specialized application. The non-C applications share the same
Agent Core, hosted runtime, protocol, and GUI shell while carrying no C/C++
workflow package manifest or harness refresh path, and constructing them through
the base registry does not import `embedagent.workflow_packages.c_cpp`. Base
configuration and bundled config templates do not pin the default C/C++
application id; when `agent_application_id` is omitted, hosted product
selection falls through to the product registry default.

### Default C/C++ Workflow Package

- `src/embedagent/workflow_packages/c_cpp/`
- `src/embedagent/workflow_packages/c_cpp/extension.py`
- `src/embedagent/workflow_packages/c_cpp/workflow_projection.py`
- `src/embedagent/workflow_packages/c_cpp/packs.py`
- `src/embedagent/workflow_packages/c_cpp/tool_registry.py`
- `src/embedagent/workflow_packages/c_cpp/tool_metadata.py`

The first-party C/C++ workflow package owns C/C++ discipline, phase, task graph,
tool registration, metadata, packs, workspace-profile detector, context
reducers, session task snapshots, and workflow projection. It is bundled by the
hosted product but is not part of the generic Agent Core.

The default C/C++ harness is now entered through the in-process workflow extension boundary. Harness internals remain bundled and enabled by default, but `QueryEngine` must not import concrete harness task classes directly.

`InProcessAdapter` owns the hosted runtime's `ExtensionManager` and passes that same manager to each session-scoped `QueryEngine`. Frontend tool catalog visibility is computed from the same manager, so model-facing tools and shell metadata share one extension chain.

Hosted adapter behavior that is not Agent Core lives in focused hosted
services. `HostedCommandService` owns slash-command dispatch, command-result
recording/emission, and hosted command tool execution such as `/run`; it uses
`ReviewCommandService` for `/review` evidence synthesis. `HostedInteractionService`
owns permission/user-input approve, reject, reply, respond, and pending ticket
glue while actual turn resume continues through the existing action pipeline.
`InProcessAdapter` remains the session/runtime bridge and must not grow a
parallel command or interaction subsystem.

Hosted review, project-memory, and workspace-intelligence services classify
tool results through the workflow-neutral `tool_evidence` payload schema:
`recipe_action`, test summaries, coverage summaries, diagnostics, and quality
gate fields. They must not import default C/C++ workflow tool constants; a
specialized workflow can produce the same safe fields with its own tool names.

`ExtensionManager` is now the shared in-process capability boundary. The current default C/C++ harness remains the bundled workflow extension, while the same boundary also carries generic prompt/context hooks, tool-call and tool-result interception, resource discovery contracts, dynamic in-process tool registration, workflow-owned workspace recipe projection, extension diagnostics, and manifest-gated project-local Python extensions. Extension objects are discovered only through `extension_capabilities()` and must return explicit `ExtensionCapability` records for each hook, manifest provider, context reducer registrar, recipe projector, or extension-owned tool handler they expose; method-name hooks are not compatibility contracts. Capability dispatch internals flow through `AgentEventBus`, the source-aware observer/reducer bus introduced and closed out in Phase B. Event-specific reducer semantics cover merge, union, first-result, first-block-wins, sequential argument rewrite, and trusted fail-closed diagnostics. Workspace-local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are official discoverable resources. Visible skills are summarized through one lightweight local skill listing prompt unit, while skill and prompt bodies enter context only through explicit `/skill:<name> [args]` and `/prompt:<name-or-path> [args]` commands. These resources are Markdown/text context, not executable extension code.

`AgentExtensionHost` is the session-engine side of that boundary. It builds extension contexts and workflow events, initializes workflow state, applies prompt/context hooks, registers dynamic tools, computes extension-aware active tool names, requests explicit tool schemas, applies tool-call/tool-result hooks, and handles extension-owned tool calls. `QueryEngine` keeps a compatibility `extension_manager` reference, but extension hook dispatch is centralized in `AgentExtensionHost`.

Tool-result workflow patches expose only the current generic `workflow` read
model plus safe `metadata`; old extension projection fields are not part of
the extension boundary.

Workflow-package prompt units are described by the generic `WorkflowPrompt` descriptor and appended as generic `workflow_prompt` system messages. `PromptAssemblyService` owns workflow-prompt append/dedupe mechanics. The old harness-specific prompt kind is no longer active; new Agent Core prompt injection and deduplication use only the generic workflow naming.

`AgentLifecycleJournal` owns durable lifecycle writes for schema v2 operation events, transition save points, pending interaction lifecycle events, context operation payload helpers, and workflow-patch persistence helpers. `AgentKernel` owns turn frames and pending interaction create/resolve boundaries. `AgentToolActionService` owns non-LLM tool action execution: active-tool checks, extension pre/post hooks, permission evaluation, pending permission/user-input action handling, mode-switch proposals, path write guards, runtime dispatch, extension-owned tool calls, resumed action execution, and workflow-patch capture after tool-result hooks. `AgentLoop` owns Pi-style open turn-loop continuation: agent step lifecycle, context/provider attempts, active schema requests through `AgentExtensionHost`, compact retry, tool batch interruption, guard-stop, abort, and explicit loop safety-limit compatibility transitions. Ordinary command/build/test failures are diagnostic tool results for the next model turn, not automatic hard-stop conditions; guard-stop is reserved for provider/protocol no-progress and true runaway protection. The optional safety fuse remains available only as an explicit runtime/test parameter; persistent JSON configuration must not set a product loop ceiling, and hosted defaults do not stop merely because eight model/tool cycles were used. `QueryEngine` remains the public session facade and keeps ownership of transcript-backed session mutation compatibility; it must not grow private loop or completion forwarding wrappers.

`ProgressGuard` owns the turn-loop no-progress/runaway safety check. It fingerprints action intent together with observation evidence, so distinct files, commands, diagnostic outputs, and successful writes are treated as progress even when they use the same tool name. It replaces repeated-tool-name stopping with evidence-aware stopping and remains a guard only; it does not decide validation success, tool activation, permissions, or workflow state.

Explicit user mode-switch requests are routed by `QueryEngine` before provider calls. `/mode <name>` and pure natural-language mode switches become local mode changes with closed lifecycle operations; `/mode <name> <message>` switches first and submits the remainder under the target mode. Model-initiated mode changes remain non-LLM tool actions mediated by `AgentToolActionService` and user confirmation, not autonomous provider policy.

`TurnSnapshot` is the explicit frozen input for one provider request. `TurnSnapshotService` builds it after context assembly and active tool schema projection, including credential-free model profile, runtime configuration, resource revision, capability, prompt-unit, and context-stat metadata. `QueryEngine` then calls the provider with `snapshot.messages` and `snapshot.tool_schemas`. Snapshot diagnostics may record safe metadata such as `snapshot_id`, mode/workflow state, registered tool names, active tool names, credential-free model profile metadata, safe prompt-unit metadata, and capability counts; they must not record prompt bodies, file contents, raw tool outputs, or credentials.

`WorkflowPackageManifest` is a non-executing read model for workflow package identity, supported modes and workflow states, declared tools, packs, resource scopes, and diagnostics. The bundled C/C++ package exposes its manifest through the extension boundary and derives it from the same package-owned constants that drive tool metadata and pack definitions. Manifest projection is diagnostic/control-plane state only; it does not activate tools, grant permissions, execute tools, or load packages.

`CapabilityRegistry` is a non-executing read model for runtime tools, modes, local file resources, slash commands, model profiles, and workflow packages. It records provenance and metadata for diagnostics and future reducer work. It does not decide active tools, execute tools, reload resources, load extensions, or replace permission checks; those responsibilities remain with `AgentExtensionHost` / `ExtensionManager`, `ToolRuntime` / `AgentToolActionService`, resource reload paths, project extension loading, and `PermissionPolicy`.

`RuntimeConfigReducer` is the replayable runtime configuration read model. It reduces safe transcript events into credential-free model profile metadata, registered tool names, model-visible active tool names, local resource revision metadata, capability counts, and provider snapshot records. It feeds `ManagedSession.runtime_config`, session snapshots, and provider `TurnSnapshot` resource revision/model metadata when available. It remains diagnostic/replay state and must not become an active-tool selector, resource loader, extension loader, tool executor, or permission engine.

`ContextManager` owns deterministic context assembly. Core context reducers are workflow-neutral; C/C++ workflow reducers for recipe results, build diagnostics, quality reports, and task status are registered by the bundled workflow extension from harness-owned modules. In addition to reactive compact retry after provider context-limit errors, `ContextManager` may pre-provider rebuild with the internal compact policy when the assembled input approaches `auto_compact_threshold_ratio` and there is older turn history to summarize. That trigger is expressed as a context pipeline step and compact-boundary diagnostic metadata, not as a new public extension API. `ContextWindowState` is a small internal value object that derives safe trigger/phase/window-generation diagnostics from context pipeline steps; it is not a durable history source or policy engine.

`ContextPlan` is the explicit read model for one provider request's assembled context. The current implementation records safe selected-message counts, recent/summarized turn counts, pipeline steps, token/character summaries, preserved message ids when present, and replacement refs; compact-boundary metadata can reuse that plan instead of re-inferring basic counts. `CompactionJournal` builds the safe `compact_boundary` and `compacted_history` transcript payloads from the context assembly, boundary, and window diagnostics. `compacted_history` transcript events record a safe compacted-history checkpoint with summary text, first-kept anchor, replacement messages, trigger/phase metadata, token/message counts, file activity refs, and evidence refs. `SessionRestorer` validates checkpoint ids, anchors, and replacement-message shape before replaying them into live `Session.compacted_history`; `ContextManager` can rebuild provider history from the latest valid replacement checkpoint plus the newer transcript suffix. The transcript remains the audit log. `CompactionStateReducer` includes compacted-history projection for diagnostics, but it remains a replay/read model and must not become the planner, summary generator, extension executor, permission engine, or second session-history source.

`CompactionStateReducer` is the replayable structured compaction read model. It reduces `compact_boundary` transcript events into safe boundary records with preserved message anchors, token/message counts, trigger/phase/window-generation diagnostics, file activity paths, evidence refs, extension-summary flags, and duplicate/malformed diagnostics. It also projects compacted-history checkpoints as diagnostic state. It feeds restore results, `ManagedSession.compaction_state`, protocol snapshots, and session snapshots. It remains diagnostic/replay state and must not become a context selector, summary generator, extension executor, permission engine, or second session-history source.

`RecoveryStateReducer` is the replayable hosted recovery read model. It reduces `recovery_marker` transcript events into safe recovery records with trusted-prefix counts, stop reasons, skip summaries, operation/compaction/runtime summaries, and duplicate/malformed diagnostics. It feeds restore results, `ManagedSession.recovery_state`, protocol snapshots, and session snapshots. It remains diagnostic/replay state and must not change restore validation, retry tool calls, select modes, activate tools, load extensions, bypass permissions, or become frontend-owned policy.

`TurnExperienceReducer` is the replayable turn-experience read model. It reduces safe `tool_result` and `loop_transition` transcript events into completed work, unverified changes, validation failures, blockers, last failure, and suggested next steps. It feeds `ManagedSession.turn_experience`, protocol snapshots, session snapshots, `session_finished` payloads, CLI diagnostics, the TUI inspector, and GUI T3 system notices. It remains display/replay state and must not drive loop continuation, validation policy, active-tool selection, permission decisions, restore rules, extension loading, or session-history truth.

Default bundled workflow assembly is outside `QueryEngine` through `AgentApplication`. A bare `QueryEngine` receives an empty `ExtensionManager`; hosted product paths install the selected application extension manager before constructing session engines. The default C/C++ product application lives in `src/embedagent/workflow_packages/c_cpp/application.py` and is reached through the application record's lazy builder path, while `InProcessAdapter` depends only on the application boundary, selected application id, and injected mode/profile policies. Hosted capability payloads expose the selected application as `agentApplication` and available applications from the same selected registry as `agentApplications`; built-in agent applications share the central `agent_application_capability_payload(...)` projection used by both hosted session capabilities and no-workspace GUI app bootstrap. An injected external application must not leak the bundled C/C++ application into its GUI capability list. Hosted product paths may additionally load project-local extensions from `.embedagent/extensions/<name>/extension.json` when the manifest is explicitly enabled and declares permissions. Loaded project extensions receive `api.ExtensionCapability` and must explicitly declare every active hook from `extension_capabilities()`. Public remote registries, plugin marketplaces, runtime dependency installation, built-in tool replacement, and multi-agent orchestration remain out of scope.

Optional enterprise/intranet integrations are hosted capabilities, not Agent Core responsibilities. Intranet Git adapters, custom service providers, model gateways, organization-local catalogs, and telemetry sinks must be explicitly configured, trusted, disableable, and failure-tolerant. They attach through provider, extension, workflow-package, or passive sink boundaries with source metadata and normal permission checks; they must not make startup, default C/C++ workflows, restore, resource reload, or session history depend on network availability.

The foundation for that boundary is implemented as metadata and policy, not as network behavior. `ToolRuntime` catalog metadata is the source of truth for permission category, and `PermissionPolicy` asks by default for `other` when a tool lacks valid metadata. `network` and `telemetry` are official permission categories recognized by `PermissionPolicy`, dynamic tool registration, project extension manifests, self-extension authoring, frontend permission context, and tool catalogs. `src/embedagent/telemetry.py` builds local safe envelopes for future sinks by redacting or summarizing prompt/source/output/credential metadata; it does not upload data or create a telemetry service.

Managed-session workflow refresh in the product adapter path goes through `AgentApplication.refresh_managed_session()`, which delegates to the selected application's workflow refreshers. The bundled C/C++ application uses `CHarnessWorkflowExtension.refresh_managed_session()` internally; the old `HarnessStateSynchronizer` service facade has been removed rather than kept as a parallel compatibility path.

### Session Runtime Ownership

- `ManagedSession` hosts thread/lock/status and durable `Session` references
- one session-scoped `QueryEngine` is the facade and transcript/session mutation owner; `AgentKernel`, `AgentLifecycleJournal`, `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost` own lifecycle, journal, loop, action, active schema, and extension dispatch internals
- `InProcessAdapter` is a host/bridge layer and must not mint duplicate workflow identities or own slash-command business rules that can live in hosted services such as `ReviewCommandService`
- `SessionSnapshotProjector` and `SessionHistoryAssembler` are projections, not workflow truth
- `SessionHistoryAssembler` emits both nested `turns` and direct T3-style `activities` from the same transcript-backed `Session` state
- the React GUI consumes `history.activities` through `session-runtime/activity-state.js`; the TUI formats the same activities into local display lines; nested `history.turns` is diagnostic structure and must not be reprojected into a second frontend history source
- `SessionHistoryAssembler.build()` is the only active history serializer; deleted flat item serializers and TUI `items` history views must not be reintroduced
- GUI live interaction activity is backend-owned: Core `permission_required`
  and `user_input_required` turn events flow through `CallbackBridge` into
  `WebSocketFrontend.on_turn_event(...)` and then into `session_event`
  envelopes. Raw `permission_request` / `user_input_request` WebSocket
  messages drive only the current blocking interaction UI and must not become
  renderer-synthesized activity/history streams.
- GUI/TUI read-model refresh after tool completion is metadata-driven. Tool
  catalog entries may declare `read_model_invalidations`; hosted adapters and
  frontend shells use those hints only for safe projections they own, such as
  workspace files, tasks, or capabilities, instead of maintaining parallel
  tool-name refresh lists. GUI artifact invalidations no longer create a
  sidecar refetch event.
- `SessionSnapshotProjector` reads the generic workflow projection, not default harness internals
- `runtime_config` in session snapshots is reducer-backed diagnostic state, not frontend-owned policy
- `compaction_state` in session snapshots is reducer-backed diagnostic state, not frontend-owned context policy
- `recovery_state` in session snapshots is reducer-backed diagnostic state, not frontend-owned recovery policy
- `turn_experience` in session snapshots is reducer-backed display state; CLI, TUI, and GUI may render it but must not infer their own completion, validation, blocker, or next-step policy from history or tool names
- no durable timeline-backed session-history store exists; GUI activation and
  `/review` consume transcript/session projections, and transport recovery reloads
  session bootstrap instead of calling a session event replay route
- hosted adapter session bootstrap assembly lives in `SessionBootstrapService`,
  runtime/capability projections live in `RuntimeCapabilityService`, slash
  command dispatch and command-result emission live in `HostedCommandService`,
  and permission/user-input response glue lives in `HostedInteractionService`;
  `InProcessAdapter` stays a host facade over those services instead of
  accumulating command/bootstrap/interaction business rules
- GUI command-result follow-up behavior is payload-driven: session switching
  uses `switch_session_id`, Diff opening uses structured diff payloads, and
  run-output log copy uses optional `log_label` / `log_detail` fields rather
  than renderer-derived slash-command names; timeline command-result labels
  likewise come from explicit payload labels or app-shell `commandDefaultName`,
  not synthesized `/${commandName}` strings
- GUI composer slash-command default grouping is app-shell declared:
  `capabilities.chrome.composer.command_menu.default_command_group_id` is the
  only fallback group id for backend slash commands, and protocol/session
  command normalization does not synthesize missing groups as `"command"`
- GUI composer slash-command items come only from command capability
  projection; renderer-local static `commandHints` fallbacks are removed and
  must not be used as an alternate command source
- GUI composer hint-bar entries are app-shell descriptors under
  `capabilities.chrome.composer.hints`; renderer code filters them by generic
  visibility state instead of owning a fixed hint id/order list
- provider request snapshots and workflow prompt append decisions live behind
  `TurnSnapshotService` and `PromptAssemblyService`; compact payload assembly
  lives in `CompactionJournal`, keeping `QueryEngine` focused on session
  mutation and loop orchestration
- `/review` session evidence extraction, finding synthesis, git-diff evidence
  shaping, and markdown rendering live in `ReviewCommandService`; review
  classification consumes structured evidence payload fields rather than
  default C/C++ tool-name constants
- project memory and workspace intelligence consume the same structured
  evidence payload helpers, so runnable recipe history, diagnostic summaries,
  and quality-gate summaries are not tied to the bundled C/C++ workflow tool
  names
- `InProcessAdapter` only invokes hosted services and emits the command result

## 3. Official Execution Model

The repository now uses one default C/C++ workflow model:

- user-visible `mode`
- internal `discipline_profile`
- internal `execution_phase`
- `TaskGraph` as default harness workflow truth
- `Session.workflow_state` as the generic workflow-state carrier

### Official Modes

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`build` is the only implementation mode.

### Official Task Model

The default task system is no longer prompt-only.

Official task truth flows through:

- `TaskGraph`
- `task_status`
- session task snapshots

`Session.task_graph` has been removed. The default C/C++ harness keeps `TaskGraph` ownership behind `CHarnessWorkflowExtension` and a harness-owned session graph state adapter, while the core/frontend boundary carries only `Session.workflow_state["workflow"]`. Importing or instantiating `embedagent_core.session.Session` must not load harness task graph internals.

Frontend-facing task projection now comes from `Session.workflow_state["workflow"]`. The default C/C++ harness extension is responsible for keeping that projection synchronized with its internal task graph and persisted session task snapshots. The payload assembly itself is centralized in `src/embedagent/workflow_packages/c_cpp/workflow_projection.py`, which is the adapter from C harness internals to generic workflow state.

Workflow-neutral strategies, projectors, and frontend task APIs read task state from that generic workflow projection rather than from harness task graph internals.

Session snapshots carry:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `extensions`
- `extension_diagnostics`
- `turn_experience`

## 4. Tool Architecture

The tool runtime has one official facade:

- `src/embedagent/tools/runtime.py`

Harness selects focused tool packs by mode/phase, but execution still flows through one runtime object.

Hosted agent profile allowed-tool lists are workflow-neutral permission/write contracts. Default C/C++ workflow tools are activated by the harness extension and packs, then passed to runtime schema projection as explicit active tool names.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it returns no provider-facing schemas; it must not be used to activate base mode tools or the default harness pack implicitly.

The tool runtime is source-aware and dynamically extensible. A bare `ToolRuntime` registers workflow-neutral built-ins only. In-process extensions can register `ToolDefinition` objects into the shared runtime; the bundled C/C++ workflow package uses this same boundary for compiler/build helpers, recipe execution, quality reporting, evidence capture, and task-status tools. Source metadata is projected through the existing catalog, and active-tool visibility still flows through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)`.

C/C++ workflow pack definitions live only in `src/embedagent/workflow_packages/c_cpp/packs.py`. The obsolete `src/embedagent/tooling/packs.py` re-export and package-root pack aliases have been removed so Agent Core no longer carries a second pack import surface.

Local self-extension authoring is a workflow-neutral write capability. `SelfExtensionAuthoringService` writes workspace-bound `.embedagent` skills, prompts, recipes, and disabled-by-default project extension skeletons. The `author_local_capability` tool exposes that service in build/debug mode with `workspace_write` permission. Authoring does not refresh resource caches and does not import or enable generated Python extensions; resource reload and project extension loading remain separate operations.

The tool runtime also owns a file-only local resource cache. `ToolRuntime.reload_resources()` refreshes workspace-bound `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` resources. Root-level `workspace_recipes` is a workflow-neutral read model over explicit project/local/history recipe resources: it does not detect CMake/Make/Ninja projects and does not assign the default C/C++ `run_recipe` tool name. The bundled C/C++ workflow package owns CMake/Make/Ninja recipe detection, `run_recipe` normalization, and recipe resolution through its explicit `workspace_recipes` extension capability. Skill and prompt bodies are expanded only through explicit slash commands.

Project-local Python extensions are loaded by hosted adapters through `src/embedagent/project_extensions.py`, not by resource reload. The loader validates `extension.json`, keeps entrypoints inside the extension directory, passes a narrow workspace-bound API object, registers loaded objects into the shared `ExtensionManager`, and projects load state under `Session.workflow_state["extensions"]["project_extensions"]`. Hook participation still requires explicit `extension_capabilities()` records; defining a method with a recognized hook name does nothing unless it is declared.

Runtime-invoked external binaries are part of the tool architecture even when they are not model-visible tools. `scripts/offline-runtime-contract.json` is the repo-side contract for bundled Python, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executables. Packaging validators consume this contract so the runtime, bundle gate, and dependency checker share one external-tool truth.

Capability projections are read-only. `ToolRuntime.capability_descriptors()` projects registered tools and cached local file resources; `ExtensionManager.package_manifests()` collects workflow package manifests from registered extensions; `InProcessAdapter.capability_snapshot()` combines runtime capabilities, slash commands, workflow packages, and the active model profile. These projections are not active-tool policy and must not be used to bypass `AgentExtensionHost`, `ExtensionManager`, or `PermissionPolicy`.

Runtime configuration projections are also read-only. `runtime_configured`, `resource_reloaded`, and provider-request snapshot metadata are reduced by `RuntimeConfigReducer` so restore and frontend diagnostics can explain model profile metadata, registered tool names, active model-visible tool names, local resource revision, and capability counts. `resource_discovered` remains discovery/replay diagnostics only and does not advance runtime resource revision state.

### Official Tool Families

#### File / Discovery

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`

#### Build / Verify

- `bash`
- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `record_failing_evidence`

#### Workflow / Interaction

- `task_status`
- `ask_user`

#### Supporting Capabilities

- `git_status`
- `git_diff`
- `git_log`

`bash` is the official command execution primitive. Recipes are higher-level declarative entry points and must expose readiness and suggested next steps instead of acting like an opaque shell wrapper.

## 5. Workflow Extension And Harness Layer

`src/embedagent_core/extensions.py` owns the local in-process capability extension contract.

The default C/C++ workflow package extension in `src/embedagent/workflow_packages/c_cpp/extension.py` owns:

- mode registry
- discipline defaults
- phase advancement rules
- prompt unit construction
- task graph construction
- session task snapshot persistence
- workspace recipe projection and resolution for `list_recipes` / `run_recipe`

This keeps workflow structure out of the frontend, out of ad-hoc prompt text, and out of the workflow-neutral parts of Agent Core.

## 6. Permission Layer

`src/embedagent_core/permissions.py` is the only official permission engine.

It owns:

- action category mapping
- rule loading
- rule matching
- stable explanation text
- frontend-visible permission context

The frontend should never infer permission policy from mode alone.

## 7. Context Layer

`src/embedagent/context.py` and `src/embedagent/workspace_intelligence.py` own:

- context budgets
- workflow-neutral reducer registry
- tool-result replacement
- summary assembly
- workspace intelligence evidence

`src/embedagent/tool_evidence.py` is the generic evidence-shape classifier for
hosted services. It recognizes recipe, test, coverage, diagnostic, and quality
gate payloads without importing workflow-package tool-name constants.

The default C/C++ workflow extension registers harness-owned context reducers for:

- `run_recipe`
- `report_quality_v2`
- `task_status`
- `record_failing_evidence`

The workflow-neutral reducer registry owns `bash` command summaries, including output decoding metadata, tail truncation, full-output refs, and structured failure guidance.

## 8. Session / Transcript Truth

Session truth is distributed across:

- live `Session`
- transcript events
- `SessionHistoryAssembler` projections
- tool result storage/projections
- summary store
- task snapshots

No frontend should maintain its own workflow truth separate from session
snapshots and backend-owned live events.

Additional ownership rules:

- engine-issued `turn_id` / `step_id` / `step_index` are the only official execution anchors
- resumed permission and user-input interactions must re-enter the same `AgentToolActionService` action pipeline used by first execution; `QueryEngine` must not keep separate `ask_user` or mode-switch execution branches
- snapshot/bootstrap payloads are projected from session truth and do not own side effects

### Session History Rule

Official session-history ownership is:

- `transcript.jsonl` is the only durable session-history ledger
- `Session` / `session.turns` is the only live structured history state
- there is no durable timeline transport in the current product contract
- GUI activation reads one bootstrap payload that includes snapshot, structured history, plan, and permission context

Historical turns must never be rebuilt from replay-log tails.

### Durable Operation State Rule

Durable runtime operation state is projected from explicit schema v2 lifecycle events:

- `operation_started`
- `operation_finished`
- `operation_interrupted`

`OperationLogReducer` consumes the validated transcript prefix and must not infer operation state from legacy replay/history events such as `step_started`, `tool_call`, `tool_result`, or `loop_transition`. Those events still rebuild structured session history and tool topology. Operation lifecycle events explain runtime execution units such as turns, agent steps, context assembly, context snapshots, provider requests, tool calls, pending interactions, workflow patches, and save points. Restore-time projections close unfinished operations as interrupted, while live snapshot projections preserve unfinished operations as active. Diagnostics such as `operation_diagnostics` are reducer projections over this operation state and must not become a second session-history source.

### Runtime Configuration State Rule

Replayable runtime configuration is projected from safe schema v2 events:

- `runtime_configured`
- `resource_reloaded`
- provider-request `operation_started` metadata containing safe `turn_snapshot` fields

`RuntimeConfigReducer` consumes the validated transcript prefix and must not infer runtime configuration from frontend replay, `resource_discovered`, prompts, raw tool outputs, or local extension code. Session snapshots may expose `runtime_config` for diagnostics and restore visibility; that projection does not activate tools, execute tools, reload resources, load project extensions, or bypass permissions.

### Structured Compaction State Rule

Replayable compaction state is projected from compact boundary events:

- `compact_boundary`
- `compacted_history`

`CompactionStateReducer` consumes the validated transcript prefix and must not infer compaction state from `timeline.jsonl`, prompts, raw tool outputs, or local extension code. Session snapshots may expose `compaction_state` for diagnostics and restore visibility; that projection does not select active context, rewrite summaries, load extensions, execute tools, or bypass permissions. `Session.compact_boundaries` remains live context compatibility state, and `Session.compacted_history` is restored live context state derived from validated transcript events; neither is a second durable truth.

### Recovery State Rule

Replayable hosted recovery state is projected from recovery marker events:

- `recovery_marker`

`RecoveryStateReducer` consumes the validated transcript prefix and must not infer recovery state from `timeline.jsonl`, prompts, raw tool outputs, or local extension code. Hosted resume may append safe recovery markers after restoring a trusted prefix. Session snapshots may expose `recovery_state` for diagnostics and restore visibility; that projection does not change restore validation, retry tool calls, select modes, activate tools, select context, load extensions, or bypass permissions.

### Turn Experience State Rule

User-facing turn experience is projected from safe transcript events:

- `tool_result`
- `loop_transition`

`TurnExperienceReducer` consumes the validated transcript prefix and must not infer experience state from frontend replay, `timeline.jsonl`, prompts, local extension code, renderer state, or command-name heuristics. Validation failures are projected only from explicit tool-result metadata supplied by the owning workflow/tool. Session snapshots may expose `turn_experience` for CLI/TUI/GUI display and resume visibility; that projection does not decide whether the agent continues, whether validation is sufficient, which tools are active, what permissions apply, or what session history means.

## 9. Frontend Contract

The frontend-facing vocabulary is now:

- `build`, not `code`
- `tasks`, not the retired todo vocabulary
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `agentApplication` and `agentApplications` for backend-declared scenario
  application identity, profile id, workflow package ids, and activation state

If a frontend change introduces older terms back into the product shell, that is an architectural regression.
GUI no-workspace copy, mode catalogs, command lists, tool presentation,
workflow package/application identity, and runtime workflow summary rows must
come from backend capability/snapshot payloads rather than renderer-side C/C++
defaults. The no-workspace selected-agent display projection comes from the app
host/launcher and is superseded by active-core capabilities after workspace
activation. Tool labels, icon keys, renderer keys, permission categories, and
preview arguments come from the frontend-visible tool catalog, with only a
generic unknown-tool fallback to the tool id. Runtime workflow rows are declared
by the selected workflow
projection under `workflow.metadata.display_rows`; the renderer must not
synthesize default C/C++ phase, discipline, or activity rows from legacy
snapshot fields. GUI session creation without an explicit mode leaves mode
selection to the selected backend application/profile instead of injecting a
renderer or route-level default.

GUI task display is a session snapshot/bootstrap projection. The renderer must
not call a split `/api/tasks` endpoint, listen for `tasks_refresh`, or maintain a
separate `tasks_loaded` action path; `CoreInterface` likewise no longer exposes
a frontend-facing `list_tasks` facade. Workspace recipes are workflow resources
and tool capabilities, not a GUI-owned `/api/workspace/recipes` panel feed or
frontend-facing `list_workspace_recipes` facade; workflow-specific quick actions
must be declared through backend capability or command metadata rather than a
renderer-owned recipe list.
Tool presentation metadata for timeline/tool rows is also part of session
capability/bootstrap projection. The GUI must not call a split
`/api/tool-catalog` endpoint, keep a root `toolCatalog` fallback state, or
depend on a frontend-facing `CoreInterface.get_tool_catalog` facade.
Right-panel navigation is app-shell surface capability driven end to end.
Surface panel components render whichever supported surface is active, but they
must merge backend-declared descriptor metadata with locally supported renderers
instead of keeping their own hard-coded surface tab registry, `inspectorTab`
adapter, or `onTabChange` navigation path that bypasses app capabilities.
Right-panel chrome copy and surface command labels are also backend-declared
surface capability metadata rather than renderer string concatenation.
Session/message/view/palette command entries are backend-declared
`workbench_commands`; the renderer no longer owns a local default command list,
and the old duplicate `workflow.diff` entrypoint is not part of the default GUI
shell.
The renderer must not keep parallel root-level `inspectorTab` / `inspectorOpen`
navigation fields; the right-panel workbench surface state is the single live
navigation state for this area.
The active GUI webapp source also follows this vocabulary directly:
`surface.*` translation keys, `surface-panel` CSS, `right-panel-toggle` tests,
and the `--right-panel-w-raw` layout variable. Old Inspector shell selectors,
i18n keys, and toggle ids are historical only.

## 10. Bundling Model

The shipped product is expected to be a self-contained offline bundle.

The architecture therefore assumes runtime discovery for bundled tools, not global machine dependencies.

The GUI bundle includes a thin native Win32 launcher (`EmbedAgent.exe` / `embedagent-gui.exe`) for double-click startup, while Python, WebView2, LLVM/Clang, MinGit, ripgrep, and Universal Ctags remain explicit files in the portable bundle.

`scripts/offline-runtime-contract.json` enumerates the bundled external tools that runtime flows may invoke and the release gates that prove the bundle is usable. The release bundle validation gate and dependency checker must consume this contract rather than maintaining independent hard-coded lists. Repo-side release validation now includes a bundled C smoke workspace compiled by bundle-local Clang via `validate-cpp-smoke.py`; clean Windows 7 unpack-and-run smoke remains the final release proof that the contract-backed bundle is actually portable.

Offline-first does not forbid explicitly configured intranet use. It means network services are optional adapters with timeouts, local fallback/disable paths, and safe diagnostics. Telemetry, when present, is a passive sink over safe structured lifecycle/capability/diagnostic events and must not export prompts, source text, raw tool outputs, API keys, permission payloads, tokens, or approval secrets. The current code has only the permission/category and safe-envelope foundation for those future adapters; it does not ship a network uploader.

## 11. Design Rule

Do not reintroduce parallel V1/V2 execution paths.

When changing architecture:

- promote the new path to the only official path
- then delete or archive the old path
- keep current docs describing only the official architecture

The project is pre-release. Compatibility with old internal session state,
timeline projections, GUI reducer shapes, and extension-hook compatibility
surfaces is not a product goal. `pre-release-architecture-debt-audit.md`
records the closed debt baseline for deleting or replacing those layers while
preserving Windows 7, offline deployment, Python 3.8, and the default C/C++
workflow target.

## 12. Next Architecture Direction

The current official architecture remains the baseline described above. The next architecture program is defined by `pi-inspired-agent-core-blueprint.md`.

That program keeps learning from Pi at two levels:

- functional design: extensions, resources, durable sessions, compaction, command surfaces, model capability metadata, observability, and self-extension workflows
- architecture philosophy: a smaller core, capability registration, event reducers, turn snapshots, save points, and replaceable workflow packages

The Pi lesson for enterprise capabilities is structural rather than permissive: keep Core small, expose stable capability/event/provider boundaries, and let optional adapters carry environment-specific behavior. EmbedAgent keeps the stricter offline and Windows 7 baseline, so intranet integrations must stay outside Core and must degrade cleanly when absent.

The intended long-term direction is that Agent Core can be described without C/C++ workflow vocabulary. The bundled C/C++ harness remains the default product workflow, but it should continue moving toward a first-party workflow package loaded through the same capability boundary as other local extensions.

This is a gradual direction, not a statement that the target state is fully implemented. Phase A durable operation reducers, Phase B extension hook bus dispatch, Phase C AgentKernel lifecycle extraction, Phase D default C/C++ workflow package ownership, Phase E local self-extension authoring, Phase F repo-side offline bundle validation, Phase G turn snapshot / capability registry foundation, Phase H runtime configuration reducer, Phase I workflow package manifest/read model, Phase J structured compaction state, Phase K recovery state, Phase L pack compatibility cleanup, and Phase M core alias cleanup are complete. The 2026-06-25 pre-release debt cleanup slice program is closed, and the release-gate slice adds contract-backed C smoke validation plus explicit Win7 GUI gate metadata. Future changes should prefer deletion-oriented replacement of stale internal paths over preserving hosted compatibility, while keeping the default C/C++ workflow runnable and recording clean Win7/WebView2 bundle smoke evidence before release claims.

Phase M removed the remaining core-level global/proxy compatibility aliases for
mode registry access, command sanitizer access, and hosted adapter class lookup.
Current code should use `get_mode_registry()`, `get_command_sanitizer()`, and
`get_inprocess_adapter()` directly instead of compatibility names.
