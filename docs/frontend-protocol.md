# Frontend Protocol

## 1. Purpose

This document describes the current stable contract between Agent Core and frontend shells.

The protocol vocabulary is now:

- `build`, not `code`
- `tasks`, not the retired todo vocabulary
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `agentApplication`
- `agentApplications`

## 2. Core Boundary

The stable contract boundary is:

- `src/embedagent/protocol/__init__.py`
- `src/embedagent/core/adapter.py`

Frontends should only rely on this boundary, not on internal session or query-engine details.

The core adapter boundary uses `get_inprocess_adapter()` internally for hosted
adapter class lookup. Removed private adapter lookup aliases are not frontend
protocol contracts.

### Workbench Shell State

GUI and TUI may keep local workbench shell state for sidebar selection,
right-panel surfaces, bottom drawers, command-palette query, keybindings, and
layout density. This state is not session-history truth and is not an
activation or permission policy.

GUI panel resizing is a local shell concern, but renderer-facing resize entry
points must stay semantic: `App.jsx` wires `startSidebarResize` /
`startRightPanelResize`, while CSS variable names, direction constants, and
document-root style mutation remain inside `panel-resize-controller.js`.

Frontend shell state must not decide tool visibility, execute tools, approve
permissions, change durable modes, infer transcript history, load extensions,
or mutate workflow state. Those decisions remain owned by Agent Core,
ExtensionManager, PermissionPolicy, SessionHistoryAssembler, and the existing
session/bootstrap protocol.

Current pending-interaction responses may render local busy state, but response
submission and response event logging are not shell policy. GUI code must route
that path through `interaction-response-controller.js`; `App.jsx` must not
inject root-level logger callbacks or synthesize a separate interaction
history stream.

### GUI App-Shell State

The GUI may expose a local app-shell read model for desktop-host concerns:
recent workspaces, the active workspace record, safe host/runtime/renderer
diagnostics, app-level command metadata, and GUI-local settings. The canonical
app activation bootstrap route is `GET /api/app/bootstrap`; app workspace
routes return the same envelope after mutations.

GUI backend session, workspace, file, task, and tool-catalog routes
must resolve the active core explicitly through the app host. Backend routes
must not depend on compatibility proxy objects that hide the active-workspace
requirement.

`src/embedagent/frontend/gui/backend/server.py` is the backend composition
root. HTTP route registration is delegated by family to `routes_app.py`,
`routes_sessions.py`, `routes_terminal.py`, `routes_source_control.py`, and
`routes_preview.py`; new route families should follow that pattern instead of
adding broad route ownership back to `server.py`.

This state is owned by the GUI host and frontend shell. It is not session
history, workflow truth, tool activation policy, permission policy, extension
loading policy, provider configuration, or transcript state. It must not
include API keys, prompt bodies, source files, raw tool outputs, permission
payload secrets, or transcript entries.

Current app-shell v1 fields include `app`, `workspaces`,
`active_workspace`, `has_active_workspace`, `diagnostics`, `capabilities`,
`settings`, and `last_error`. Diagnostics are safe read-model fields for host,
runtime, renderer, workspace registry, and active-core presence only.
`capabilities.app_commands`, `capabilities.workspace_commands`,
`capabilities.workbench_commands`, `capabilities.command_palette.groups`,
`capabilities.surfaces.right_panel`,
`capabilities.surfaces.bottom_drawer`, `capabilities.surfaces.chrome`, and
`capabilities.keybindings` are the app-shell entrypoint contract for the
renderer workbench. App/workspace/workbench command entries and surface entries
are descriptor records, not bare ids. Command
descriptors carry `id`, `group`, `label`, ordering metadata, and may also carry
`slash`, `visible_when`, `surface`, `drawer`, `keywords`, `description`, and
safe dispatch metadata. Supported `dispatch.kind` values are renderer-local
handler registry keys; renderers must not reintroduce command-id or
dispatch-kind switch ladders as hidden capability policy. Command-palette
group descriptors carry `id`, `title`,
`description`, and ordering metadata, and may also carry `leading`, `meta`, and
`keywords`; renderer command grouping must consume those descriptors instead of
owning a fixed group title/description table. Command labels are visible
display descriptors: app/workspace/workbench command descriptors that omit
labels do not become visible commands, and dynamic slash-command descriptors
are visible only when they provide explicit `label`, `usage`, or `slash`
metadata. Renderer command lists and command-palette rows must not synthesize
labels or titles from command ids. Commands whose groups are missing from
`capabilities.command_palette.groups`, or whose group descriptors omit `title`,
do not become visible palette rows; renderers must not title-case group ids as
fallback group titles. Missing command row description/meta copy remains empty
instead of falling back to command ids. Surface command row descriptions come
from surface descriptors and are not synthesized from surface or drawer ids.
Session/workspace row leading markers come from command-palette label
descriptors and remain empty when absent. Command-palette group leading markers
come from explicit group descriptors and are not synthesized from group titles.
`capabilities.command_palette`
also carries renderer-facing `labels` for the palette title, search label,
placeholders, empty states, root section titles, current/missing badges,
workspace meta text, and session/workspace fallback labels. Composer
slash-command group labels must reuse `capabilities.command_palette.groups`
through `workbench/command-palette-model.js` `buildCommandGroupLabels(...)`,
while `capabilities.chrome.composer.command_menu` carries the Composer
slash/path menu aria labels, empty states, path group label, item-kind labels,
fallback command group label, and default slash-command group id. Renderer
command normalization must not synthesize missing groups as `"command"`, and
Composer must not keep renderer-local static command hint fallbacks as an
alternate slash-command source.
Composer hint-bar items are ordered descriptor records under
`capabilities.chrome.composer.hints`; the renderer may filter those descriptors
by generic `visible_when`/`visibleWhen` values such as `always`, `running`, and
`interaction`, but it must not own a separate hard-coded hint item list.
Surface descriptors carry `id`,
`title`, and ordering metadata, and may also carry `icon`, `description`, `command`,
`command_label`, `slash`, `visible_when`, `read_only`, `offline`, and
`keywords`. Right-panel surface titles and surface-owned panel headings,
including the Files surface header, must consume those descriptors instead of
renderer-local default copy. Surface descriptors that omit `title` remain
diagnostic capability records only; they do not enter visible launchers or
commands, and renderer helpers must not derive a title from the surface kind or
id. Resource surface helper titles may use only instance data such as file
basenames, preview ids/URLs, and terminal ids; missing preview instance data
does not create a fallback tab. Surface chrome descriptors carry the right-panel aria label,
add-surface label, empty-state title/body, tab action labels, close-label
prefixes, and default icon fallback. Keybinding descriptors carry `key`,
`command_id`, and `when`. The
renderer may keep local metadata for React components, but visible
command-palette entries, right-panel launchers, bottom-drawer tabs, surface
command labels, panel chrome labels, icons, descriptions, and keybinding
targets are filtered or merged from this bootstrap declaration. Renderer-local
workbench command lists must not provide default session, message, view,
palette, or workflow commands when app-shell command descriptors are absent;
the retired duplicate `workflow.diff` GUI command is replaced by the declared
`surface.diff` entrypoint. A
missing `capabilities` object or missing capability descriptor arrays mean no
app-shell entrypoints, not GUI defaults.
Renderer app-shell capability fanout is a local read model:
`webapp/src/app-runtime/app-capability-model.js` owns the normalized accessors
for keybindings, command-palette descriptors, app chrome, surface chrome,
Preview servers, thread lifecycle descriptors, and empty-state copy. `App.jsx`
should consume `buildAppCapabilityModelFromState(...)` /
`buildAppCapabilityModel(...)` rather than reading `state.app.capabilities` or
`stateRef.current.app.capabilities` directly for each surface, controller
getter, or command subsystem.
Header panel toggles, command-palette open/close/query state,
command-palette command/session/workspace selection, and command-id resolution
are renderer action-controller concerns in
`webapp/src/app-runtime/workbench-command-controller.js`; `App.jsx` must not
import `commandById` or inline-dispatch palette/toggle reducer actions as a
second workbench command policy. Command visibility context, including
session/workspace presence, palette-open state, and interruptible-turn status,
is a `webapp/src/workbench/commands.js` read model through
`buildCommandVisibilityContext(...)`; root App composition must pass state
slices to that model instead of hand-building the visibility object, including
the keyboard-shortcut context handed to `workbench-keyboard-controller.js`.
`capabilities.home` carries GUI home/sidebar copy for workspace and thread
sections, including inactive-workspace labels, path placeholder text, open and
recent-workspace labels, missing-path labels, thread empty-state copy, and
thread action aria prefixes. Renderer home/sidebar components should consume
that copy from the app-shell read model instead of hard-coding the default
EmbedAgent wording. This copy remains presentation metadata only and must not
drive session history, workspace activation policy, workflow state, tool
visibility, permissions, or extension loading.
Workspace path input changes are GUI app-shell state updates owned by
`webapp/src/app-runtime/workspace-controller.js`; root App composition wires
`setWorkspacePath` and does not inline `workspace_path_changed` dispatches.
The default GUI shell descriptor set lives in
`src/embedagent/frontend/gui/backend/app_shell_spec.py` and is injected into
`AppShellService`; alternate hosts may provide a smaller or specialized spec
without modifying the service or Agent Core.
Right-panel surface descriptors may also carry safe renderer metadata such as
`body_kind` / `bodyKind` and `panel_kind` / `panelKind`. Unknown right-panel
surface kinds are accepted only as non-executing `surface_panel` bodies with a
safe generic panel kind such as `descriptor`, `diagnostics`, or `plan`; they do
not load frontend code, call backend services, or bypass app capability
filtering.
Generic SurfacePanel actions for diff-file focus, Source Control refresh/file
selection, and app-shell settings patching are renderer action-controller
concerns in `webapp/src/app-runtime/surface-panel-controller.js`; root App
composition must not inline those reducer actions or source-control lambdas.
`webapp/src/app-runtime/surface-panel-props.js` owns the `SurfacePanel` prop
mapping from state, chrome, and controller handles.
Active-workspace read-model refresh is likewise delegated to
`webapp/src/app-runtime/active-workspace-data-loader.js`, with
`sourceControlController.loadStatus` passed directly instead of wrapped by a
root App adapter.
App bootstrap may also include safe `agentApplication`, `agentApplications`,
and `emptyState` projections. Before any workspace is active, those values come
from the backend-selected agent application registry declared by the app host or
launcher; once a workspace has an active core, the active core's safe
capability projection is authoritative. The GUI can use that projection for
app-level empty-state copy and agent-aware shell display without creating a core
or reading session history.
No-workspace shell branding and copy must come from app-shell metadata such as
`app.productName`, `capabilities.home`, and `capabilities.emptyState`; renderer
components and app-shell normalizers must not hard-code the default product or
agent name. A missing backend `productName` remains empty instead of falling
back to the bundled product name.
Workbench-local persisted surface state is re-sanitized after app bootstrap or
workspace switch against the same declaration; stale local `preview`,
`source_control`, `terminal`, or other surfaces must not survive when the
backend no longer declares their parent surface capability.
Persisted workbench surface descriptors are normalized through the
renderer-local surface registry's `persistedSurfaceFrom(...)` helper. The
localStorage UI-state module must not branch on fixed file or terminal surface
kinds to decide resource fields, tab ids, titles, reveal markers, or terminal
pane metadata. Surface instance fields that vary by kind are initialized by the
same renderer-local surface model through `SURFACE_INITIALIZERS[kind]`; new
surface-specific metadata must not be added as branches inside
`makeSurface(...)`. App capability cleanup uses
`persistedSurfaceDefinitions(appCapabilities, placement)`, including
registry-declared `persistedRelatedKinds` such as Files retaining File resource
surfaces and currently declared safe dynamic panels; UI-state code must not
hard-code related persisted kinds such as `files -> file` or treat unknown
surface kinds as globally supported. Right-panel open-time preparation that varies by surface
kind, such as file reveal/deduplication or preview placeholder cleanup, routes
through `SURFACE_OPEN_PREPARERS[surface.kind]` rather than branches in
`openSurface(...)`. Right-panel surface-local pane operations that vary by kind
route through `SURFACE_PANE_HANDLERS[surface.kind]`; terminal pane
split/activate/close metadata must not be added as reducer-level
`surface.kind === "terminal"` branches.
The GUI no longer keeps retired Inspector sidecar state for artifact lists,
review detail panes, permission-rule panes, runtime panes, workspace previews,
or event logs. Review results remain timeline activities, permission and user
input requests remain session interaction state, local file content remains
file-surface state, and app diagnostics remain the app-shell diagnostics
surface. The split GUI artifact refetch facade is retired as well: there is no
GUI `/api/artifacts` route or `artifacts_refresh` WebSocket event.
`capabilities.surfaces.right_panel` may declare descriptors for `files`,
`terminal`, `diff`, `preview`, `plan`, `source_control`, `settings`, and
`diagnostics`; `capabilities.surfaces.bottom_drawer` may declare descriptors
for `terminal`, `run_output`, and `logs`. `capabilities.terminal` describes the GUI
terminal limitations (`enabled`, `pty`, `resize`, `history_persistent`, and
`max_buffer_bytes`). `capabilities.chrome.timeline` describes Timeline log
aria labels, empty/history/termination copy, work-group labels,
activity-row labels/status/timer templates, work-row default heading/icon/status
labels under `work_row`, changed-files card labels, and structured tool-detail
field/section labels under `tool_detail`. Frontend T3 timeline rows may carry
display data such as timestamps, interruption flags, detail field keys, and
detail section kinds, but fallback labels and templates remain app-shell
chrome. Review-result rows are selected from structured review payload fields,
not from slash command names. Command-result row labels must come from
explicit payload labels or app-shell `commandDefaultName`, not from
renderer-synthesized `/${commandName}` strings.
`capabilities.surfaces.chrome.file_preview` describes
File Preview chrome, metadata labels, fallback messages, and language labels
for the read-only file right-panel surface.
`capabilities.surfaces.chrome.diff_panel` describes Diff Panel default titles,
empty-state copy, control titles, file rail labels, collapse labels, and the
source-control diff title template for the already-projected diff display
surface. A `command_result` may open the Diff surface from structured
`data.diff`; renderers must not key that behavior on `command_name`, and
workbench tab titles must come from explicit diff payload titles or the
app-shell surface descriptor rather than a renderer `"diff"` fallback.
`capabilities.source_control`
describes the local
source-control surface: `enabled`, `vcs`, `read_only`, `remote_providers`,
`network`, `checkpoints`, `requires_active_workspace`, and `chrome` copy for
status/diff errors, empty states, counts, group order, groups, providers, file
status badges, runtime labels, panel actions, and the composer Branch Toolbar
under `chrome.branch_toolbar`. Group/provider labels must render only declared
labels or declared fallback labels, not raw protocol ids.
The selected `capabilities.agentApplication.metadata.appShell` profile is a
backend-side filter over the GUI app-shell spec. It can allow specific app
commands, right-panel surfaces, bottom-drawer surfaces, keybinding command
targets, and command-palette groups, and can mark GUI capabilities such as
`preview` or `source_control` disabled. Renderers consume the resulting
filtered capability lists; they must not re-add default C/C++ workbench
entrypoints for a generic or specialized agent that did not declare them.
The renderer may keep a local registry of supported component kinds, but that
registry is not a frontend capability source and must not be exposed as a fixed
surface id list.

The GUI terminal bottom drawer is app-shell hosted and workspace-bound. It is
implemented with Windows 7-compatible Python stdlib subprocess pipes, not a
full PTY. Its buffer and tab state are frontend/backend GUI display state only:
they are not transcript history, workflow truth, telemetry, provider/runtime
configuration, permission policy, source-control checkpoint state, or Agent
Core state.
Frontend terminal, preview, and source-control API helpers must surface
backend `detail`, `error`, or status text only; when those are absent they
leave the error message empty so renderer controllers can use app-shell chrome
fallbacks instead of helper-local request-failure copy.

The GUI File Preview right-panel is app-shell hosted and read-only over
already-loaded workspace file content. The frontend may render breadcrumbs,
language/line metadata, markdown preview mode, reveal markers, and retry/copy
path actions, but those are GUI display affordances only. They are not file
save behavior, transcript history, workflow truth, telemetry, provider/runtime
configuration, permission policy, extension loading policy, source-control
checkpoint state, or Agent Core state.

The GUI Source Control right-panel and composer Branch Toolbar are app-shell
hosted and active-workspace bound. They are read-only and local-only in the
current contract: the GUI backend may invoke bundled/workspace MinGit for local
`status` and `diff` views, and the frontend may display file paths, counts,
toolbar checkout labels, and explicitly requested unified diff text. These
payloads are not app bootstrap diagnostics, transcript history, workflow truth,
telemetry, provider/runtime configuration, permission policy, checkpoint state,
extension loading policy, or Agent Core state. The current contract does not
include remote providers, push/pull, staging, commit, or checkpoint mutation.

GUI thread lifecycle operations are exposed through session lifecycle endpoints
and reflected in session summary/projection metadata for app thread lists.
Visible thread actions must come from
`capabilities.thread_lifecycle.actions` descriptor records, not a renderer-owned
fixed action list. The default app shell currently declares `rename`, `fork`,
and `archive`, but alternate shells may omit or relabel those entries.
Lifecycle action descriptors also carry renderer-facing labels, disabled reason
labels, prompt, confirmation, success, empty-title, and failure copy. Frontends
may display and invoke declared actions with explicit labels, but they must not
hard-code visible rename/fork/archive copy, synthesize missing action labels or
notice copy from action ids, persist their own lifecycle sidecar state, or
treat these metadata fields as transcript history, workflow truth, tool
activation policy, permission policy, extension loading policy, or
source-control checkpoints.

GUI app-shell settings are local shell preferences unless a later documented
backend contract promotes a specific setting into durable runtime
configuration. They must not be interpreted as Agent Core policy.

### GUI Renderer Runtime State

The GUI renderer state is moving toward T3 Code-style focused modules instead
of one large app reducer shape. Thread selection, session summaries, and
history-integrity display state are owned by
`webapp/src/session-runtime/thread-state.js`; composer draft text is owned by
`webapp/src/composer/composer-state.js`; GUI run-output event-log display
state is owned by `webapp/src/session-runtime/run-output-state.js`; active
session transport connection/reload projection is owned by
`webapp/src/session-runtime/session-transport-state.js`; WebSocket lifecycle
control is owned by `webapp/src/app-runtime/session-transport-controller.js`;
raw WebSocket message scheduling, derivation, and effect execution are owned by
`webapp/src/app-runtime/socket-message-controller.js`, which accepts React
transition scheduling as a generic injected callback rather than through a root
App inline wrapper;
session bootstrap activation control is owned by
`webapp/src/app-runtime/session-activation-controller.js`; terminal display
buffers remain under `webapp/src/terminal/`; persisted workbench surfaces
remain under `webapp/src/workbench/`.

`store.js` may dispatch to these focused reducers, but new frontend code must
not reintroduce root-level `sessions`, `currentSessionId`, `composer`, or
`historyIntegrity` fields as parallel state, and must not reintroduce retired
sidebar tab sidecars such as `sidebarTab` or `set_sidebar`. New transport
status code must not reintroduce root-level `connectionState` / `set_connection`; websocket
connection and reload status feed session transport state and
`projectTransportView(...)`. React components and runtime controllers should
consume the focused read models. These renderer modules are GUI-local
display/read-model state only: they do not own session history, workflow
truth, permission policy, tool activation, extension loading, provider
configuration, telemetry, or Agent Core runtime reducers.

Live tool-completion refresh uses backend/tool metadata rather than renderer
tool-name lists. Tool events may carry `read_model_invalidations` values, but
the GUI refreshes only read models it owns, such as workspace files, tasks, and
capabilities. Renderer code must not infer file/task refresh from names like
`write_file`, `edit_file`, or workflow-package tools, and artifact
invalidations no longer map to a GUI sidecar refetch path.

Visual debug scenarios are outside the frontend protocol. The React webapp may
install `window.__EMBEDAGENT_VISUAL_DEBUG__` only when `?visual_debug=1` is
present, and that hook must expand private `dev_fixture_*` descriptors into the
same ordinary reducer actions used by product flows. Product reducers and
frontend protocol docs must not define `visual_*fixture` action contracts.

## 3. Session Snapshot

Important session snapshot fields include:

- `session_id`
- `status`
- `current_mode`
- `workflow_state`
- `pending_interaction`
- `pending_interaction_valid`
- `runtime_source`
- `bundled_tools_ready`
- `runtime_environment.bash_exe`
- `workflow`
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `extensions`
- `extension_diagnostics`
- `runtime_config`
- `compaction_state`
- `recovery_state`
- operation/runtime/compaction/recovery diagnostics

`task_items` is the official frontend task list payload.

GUI session bootstrap serializers and renderer normalizers must not invent a
missing `workflow_state` value. If the backend snapshot omits the state name,
the frontend-visible snapshot keeps it empty; workflow display continues to use
the separate generic `workflow` payload.

`pending_interaction` is the single frontend-visible pending interaction
payload. It carries permission and user-input requests through a `kind` field
instead of parallel permission or user-input snapshot fields. `tool_name` is a
payload field, not a frontend classification fallback; missing user-input tool
names must not be synthesized as `ask_user`.

`max_turns`, where present in snapshots or turn-end events, is a compatibility projection for an explicitly supplied runtime/test loop safety limit. Persistent JSON configuration must not set this value. A missing or null value means the default Pi-style continuation path has no fixed turn-count cutoff. Frontends may display explicit safety-limit values for diagnostics, but they must not treat them as required session budgets or infer loop policy from them.

`extensions.local_resources` may contain the latest file-only resource reload state, including counts and diagnostics for `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes`. Skill resource entries may include Agent Skills-style metadata such as `name`, `description`, `base_dir`, `disable_model_invocation`, and `prompt_visible`.

`extensions.project_extensions` may contain the hosted adapter's latest project extension load state, including counts, manifest entries, and loader diagnostics for `.embedagent/extensions/<name>/extension.json`.

`extensions.local_resources`, `extensions.project_extensions`, and `extension_diagnostics` are frontend-visible health and diagnostics state, not frontend-owned execution policy.

Future intranet/custom-service/provider/telemetry health, if exposed, belongs in diagnostics/read-model fields such as `extensions`, `extension_diagnostics`, `runtime_config`, or capability projections. Frontends may display service availability, last error, buffered telemetry counts, or source metadata, but must not decide network activation, permission policy, retry policy, extension loading, or telemetry redaction.

Permission context and tool catalog payloads may include `network` and `telemetry` permission categories. Frontends may display those categories and remember approvals through the existing backend-owned permission flow, but they must not reinterpret them as `read` or auto-run them from catalog metadata.

Capability projections are also diagnostics/read-model state. `InProcessAdapter.capability_snapshot()` may expose tools, local file resources, slash commands, workflow package manifests, selected agent application metadata, available same-package agent applications, and model profile metadata for future frontend inspection, but frontends must not treat that projection as active-tool policy or permission state.

Session capability payloads expose:

- `agentApplication`: the selected backend-declared application descriptor
- `agentApplications`: the available application descriptors from the same selected application registry
- `modes`, `commands`, `tools`, `workflowPackages`, `resources`, `modelProfiles`, and `emptyState`

Renderer code must consume these backend-declared descriptors. It must not
hard-code the default C/C++ application, mode list, workflow-package labels, or
no-workspace copy when the backend has not provided them.
Mode descriptor `colorToken` values are generic visual tokens such as `info`,
`accent`, `success`, or `warning`; renderer code must not treat concrete mode
names such as `verify` as color-token policy.
Tool descriptors in `tools` carry GUI presentation fields such as `name`,
`label`, `renderer_key`, `permission_category`, `source_type`, `source_id`,
and safe `metadata`. `metadata.preview_arg` is the current display contract
for timeline tool-call previews, and `metadata.changed_path_arg` identifies
the argument that can seed changed-file summaries when no explicit diff or
changed-file list is present. GUI code must consume this descriptor data
instead of deriving preview text, command/file request kind, or changed-file
paths from built-in or workflow tool names.
`workflowPackages` is present as an array; profile-only applications such as
`embedagent.python` or `embedagent.html` may legitimately return an empty
array.

Visible skills and prompt files are projected to frontend-adjacent surfaces as local `resource` descriptors plus explicit slash-command descriptors (`skill:<name>` and `prompt:<name>`). There is no first-class frontend `skill` or `prompt` capability kind yet; frontends should continue treating these files as file-only local resources plus optional commands.

`runtime_config` is reducer-backed diagnostics/read-model state. It may expose credential-free model profile metadata, registered tool names, active model-visible tool names, local resource revision metadata, capability counts, and provider snapshot records. Frontends may display this for restore/debug visibility, but they must not use it as active-tool policy, permission state, resource reload authority, or project extension load state.

`compaction_state` is reducer-backed diagnostics/read-model state. It may expose compact boundary counts, latest boundary metadata, token/message counts, preserved message anchors, trigger/phase/window-generation diagnostics, safe file activity paths, evidence refs, extension-summary flag, and diagnostics. Frontends may display this for restore/debug visibility, but they must not use it as context-selection policy, history truth, extension execution policy, permission state, or a trigger for resource reload.

`recovery_state` is reducer-backed diagnostics/read-model state. It may expose recovery marker counts, latest marker metadata, trusted-prefix counts, stop reasons, skip summaries, operation/compaction/runtime summaries, and diagnostics. Frontends may display this for restore/debug visibility, but they must not use it as restore policy, active mode/tool/context policy, extension execution policy, permission state, or a trigger for resource reload.

`workflow` is the generic workflow projection. For the default C/C++ harness, `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, and `task_items` are compatibility fields projected from `workflow`.

Frontend shells should not read or infer default harness internals such as task graph state. They consume the snapshot fields and, where a richer shape is needed, the `workflow` payload.
The GUI no longer owns a workflow runtime panel display helper. It must not
synthesize C/C++ phase, discipline, or activity rows from compatibility
snapshot fields for non-C applications; workflow package detail belongs in the
generic session snapshot, capability, or activity projections supplied by the
selected backend application.

Session activation additionally depends on one bootstrap payload containing:

- `snapshot`
- `history`
- `plan`
- `permission_context`

`history` is assembled by `SessionHistoryAssembler` from transcript-backed
`Session` state. It contains nested `turns` for structured diagnostics and
`activities` for direct T3-style frontend consumption. `history.activities`
items use the current frontend vocabulary (`user`, `reasoning`, `tool`,
`assistant`) and carry `turn_id`, `step_id`, `step_index`, `status`, and safe
tool presentation metadata where applicable. Frontends must not rebuild this
activity stream from event replay tails or nested `history.turns`.

The React GUI activates sessions by normalizing `history.activities` through
`webapp/src/session-runtime/activity-state.js`. The TUI activates sessions by
formatting the same `history.activities` records into local display lines.
Legacy helpers that rebuilt timeline items from `turns`, transport events, or
TUI-local `items` history streams are not frontend protocol surfaces.

For live GUI updates, interaction activity is also backend-owned. Core turn
events such as `permission_required` and `user_input_required` are forwarded by
`CallbackBridge` to `WebSocketFrontend.on_turn_event(...)`, then normalized as
`session_event` messages whose event kind denotes interaction creation. Raw
`permission_request` and `user_input_request` WebSocket messages remain only
the current blocking interaction UI/response channel; renderer code must not
synthesize interaction-created transport events, history rows, or activity
records from those raw request messages. User-input display remains
`kind`/event-kind driven even when the payload omits `tool_name`.

`history.integrity.status` is the official history health signal:

- `healthy`
- `partial`
- `unavailable`

## 4. HTTP API Surface

Key routes include:

- `GET /api/app/bootstrap`
- `GET /api/app/workspaces`
- `POST /api/app/workspaces`
- `POST /api/app/workspaces/{workspace_id}/activate`
- `DELETE /api/app/workspaces/{workspace_id}`
- `GET /api/app/source-control/status`
- `POST /api/app/source-control/refresh`
- `GET /api/app/source-control/diff?path=<path>&scope=<scope>`
- `GET /api/sessions`
- `GET /api/sessions/capabilities`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions`
- `POST /api/sessions/{session_id}/message`
- `POST /api/sessions/{session_id}/mode`
- `POST /api/sessions/{session_id}/cancel`
- `POST /api/sessions/{session_id}/interactions/{interaction_id}/respond`
- `GET /api/sessions/{session_id}/bootstrap`
- `GET /api/sessions/{session_id}/plan`
- `GET /api/sessions/{session_id}/permissions`
- `POST /api/sessions/{session_id}/resources/reload`
- `GET /api/sessions/{session_id}/terminals`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/open`
- `GET /api/sessions/{session_id}/terminals/{terminal_id}/snapshot`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/write`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/clear`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/restart`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/resize`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/close`
- `GET /api/workspace`
- file read/tree routes

`GET /api/app/bootstrap` is the GUI app activation bootstrap contract. It
reports app-shell state only. Session activation remains exclusively
`GET /api/sessions/{session_id}/bootstrap`, whose payload contains session
snapshot, structured history, plan, and permission context.
When the launcher or host declares a selected agent application,
`GET /api/app/bootstrap` may expose that application's safe
`agentApplication`, `agentApplications`, and `emptyState` descriptors even when
`has_active_workspace` is false. This is app-shell display metadata only; it
does not create a session/core, activate workflow tools, or replace
`GET /api/sessions/{session_id}/bootstrap`.

Frontend task display comes from `snapshot.task_items` in session snapshots and
bootstrap payloads. There is no split task-list refetch endpoint or
`tasks_refresh` WebSocket contract, and `CoreInterface` no longer exposes a
frontend-facing `list_tasks` facade. Workspace recipes are local workflow
resources and tool/command capabilities; the GUI must not treat them as a
renderer-owned `/api/workspace/recipes` feed or depend on a frontend-facing
`list_workspace_recipes` facade.

`GET /api/sessions/capabilities` exposes the active workspace/session command
capability projection used by GUI composer slash-command menus. It is a
read-only capability surface derived from Agent Core capability metadata; it is
not session history, workflow truth, tool activation policy, permission policy,
or an extension loading endpoint. The GUI refreshes this projection through
the app-runtime `createSessionCommandCapabilityLoader(...)` handle rather than
root-level fetch/dispatch lambdas. Its application fields are display/control
metadata only: `agentApplication` identifies the selected scenario application,
and `agentApplications` lists only applications available from the selected
package/registry, so an externally injected Python/HTML/etc. application does
not inherit bundled C/C++ defaults in the GUI. Tool presentation metadata is
consumed from this capability projection's `tools` descriptors and normalized
into the renderer `toolCatalog`; there is no split GUI `/api/tool-catalog`
refetch contract or frontend-facing `CoreInterface.get_tool_catalog` facade.
Right-panel navigation is likewise owned by the app-shell surface capability
projection. Surface body components merge backend-declared descriptor metadata
with locally supported renderer metadata (`bodyKind` and, for generic panels,
`panelKind`) and do not keep a second hard-coded tab registry, `inspectorTab`
adapter, or `onTabChange` navigation contract. Supported right-panel
`bodyKind` values route through a renderer-local body renderer registry rather
than a component switch. Body metadata lookup receives the active app-shell
capabilities; hidden/resource surfaces such as `file` must still be declared by
the backend with visibility metadata instead of relying on renderer-only
fallback. Right-panel surface opening also
uses renderer metadata (`openKind`) so terminal session creation is not inferred
from a fixed surface id in the controller; supported `openKind` values route
through a renderer-local handler registry rather than a controller switch.
App-level resource open flows use semantic right-panel controller methods
(`openFileSurface`, `openPreviewSurface`, and `openFilesSurface`) instead of
dispatching concrete resource surface kinds from App.
Active right-panel surface selection is read through the renderer surface model
selectors `rightPanelSurfacesFrom(...)` and `activeRightPanelSurfaceFrom(...)`;
App must not resolve the active surface with root-level `surfaces.find(...)`
logic.
Right-panel surface-local pane operations route through
`SURFACE_PANE_HANDLERS[surface.kind]`; terminal split/activate/close pane
metadata is no longer reducer-level terminal kind logic.
The terminal controller keeps its terminal-specific right-panel adapter in
`TERMINAL_SURFACE_KIND` and `terminalSurfaceActionInput(...)`; individual
split/activate/close action handlers must not repeat surface-kind checks.
Right-panel tab activation side effects use renderer metadata
(`activationKind`) through the `right-panel-controller.js`
`RIGHT_PANEL_ACTIVATION_HANDLERS[definition.activationKind]` registry; App
delegates to `rightPanelController.activateSurface` and does not inspect
activation metadata or call terminal-session side effects directly.
Right-panel tab lifecycle commands for close, close others, close to right,
close all, add surface, and Files-surface opening are also direct
`right-panel-controller.js` method wiring rather than App-owned reducer
dispatch payloads.
Bottom drawer selection uses the same renderer metadata path: drawer activation
side effects come from bottom surface `activationKind` records, not drawer-kind
conditionals in the terminal controller. Supported activation kinds route
through a renderer-local handler registry rather than a controller switch.
Bottom drawer terminal new/select actions, terminal id generation, and
right-panel active terminal pane new/split/select/close actions remain inside
`terminal-controller.js`; App wires controller methods directly and does not
import terminal id helpers, dispatch `terminal_active_set` inline, or pass
`activeRightPanelSurface` through terminal callback lambdas.
Supported bottom drawer `bodyKind` values route through a renderer-local body
renderer registry rather than a component switch.
The renderer has no root-level `inspectorTab` / `inspectorOpen` navigation
state; opening, activating, and closing right-panel content flows through
workbench surface state.
Active GUI webapp source uses the current right-panel/surface vocabulary for
this area: `surface.*` translation keys, `surface-panel` CSS, the
`--right-panel-w-raw` layout variable, and `right-panel-toggle` tests. Retired
Inspector shell ids and selectors are not active protocol vocabulary.

`POST /api/sessions` without an explicit mode leaves mode selection to the selected backend application/profile. Frontends should not inject `explore` or `build` as an implicit entry mode.
Frontend protocol projection also preserves an empty/missing `current_mode` as
empty diagnostic state instead of filling in the built-in `explore` mode.

`POST /api/sessions/{session_id}/resume` should preserve the restored session mode unless the caller explicitly supplies a mode override.

`POST /api/sessions/{session_id}/resources/reload` refreshes local file resources for the session and returns the backend resource snapshot. It is not a plugin execution endpoint.

Terminal routes require an active GUI workspace and are scoped by
`session_id` plus a client-chosen `terminal_id`. They expose snapshots,
summaries, limited history buffers, and non-PTY lifecycle operations for the
GUI bottom drawer only. `write` sends user text to the GUI-owned subprocess
stdin; it is not a model tool call, permission approval, transcript append, or
workflow action.

Source-control routes require an active GUI workspace. `status` and `refresh`
return a local Git status read model; `diff` returns a read-only unified diff
for a workspace-contained file path and `unstaged` or `staged` scope. These
routes are GUI display routes, not model tool calls, permission approvals,
transcript appends, workflow actions, remote Git providers, or checkpoint
mutations.

`/skill:<name> [args]` and `/prompt:<name-or-path> [args]` are handled through the normal message submission path, not separate HTTP endpoints. On success the backend expands the workspace-bound Markdown/text resource into the user turn; on failure it emits a normal `command_result` for the resource command. Visible resource commands may appear in `/help` output and command capability snapshots as `skill:<name>` or `prompt:<name>`.

## 5. WebSocket Event Types

Important pushed event types include:

- `session_status`
- `stream_delta`
- `reasoning_delta`
- `thinking_state`
- `tool_start`
- `tool_finish`
- `permission_request`
- `user_input_request`
- `command_result`
- `plan_updated`
- `turn_start`
- `turn_end`
- `session_finished`
- `message`
- `session_event`
- `terminal_event`

For `command_result`, GUI follow-up loader effects must be keyed from
structured payload fields. A result carrying `data.switch_session_id` may load
that session regardless of command name; renderers must not bind that behavior
to `/resume`. Optional GUI run-output log entries for command results must
also be declared by payload fields such as `log_label` / `log_detail`; the
renderer must not synthesize `command: /...` labels or ok/error copy from
`command_name` and `success`.

There is no session event replay HTTP route. Transport gaps and reconnects ask
the GUI to reload `GET /api/sessions/{session_id}/bootstrap`; frontend history
bootstrap must come from `history.activities` in that structured bootstrap
payload, and the active GUI timeline is a frontend projection of that activity
read model plus live reducer actions. There is no durable timeline-backed
session-history store; that historical path has been removed and must not be
treated as current frontend history truth.

`terminal_event` carries GUI terminal output/lifecycle deltas for the bottom
drawer. It is intentionally not part of session replay/history and must not be
reduced into `Session`, `SessionHistoryAssembler`, `RuntimeConfigReducer`,
`CompactionStateReducer`, or `RecoveryStateReducer`.

Resource reload may appear in live events as `resource.discovered` and `resource.reloaded` event kinds. Frontends may use those for diagnostics or refresh hints, but session history remains transcript/bootstrap-backed.

Reducer-backed `runtime_config.resource_revision` advances from transcript `resource_reloaded` events. `resource.discovered` events remain diagnostics and should not be treated as a new active resource revision by frontend code.

Reducer-backed `compaction_state` advances from transcript `compact_boundary` events. Frontends should not infer compaction from transport events, summary text alone, or timeline entries.

Reducer-backed `recovery_state` advances from transcript `recovery_marker` events. Frontends should not infer recovery state from transport events, timeline gaps, or session summary fields alone.

All live tool/interaction/command events must preserve the engine-issued execution anchors:

- `turn_id`
- `step_id`
- `step_index`

Frontend shells must treat these as authoritative and must not synthesize replacement step ids.

## 6. Tool Catalog

The frontend-visible tool catalog should represent the official workflow vocabulary used by the product shell.

The UI should not use the catalog to reintroduce deprecated mode/tool naming.

Catalog visibility is computed from workflow-neutral mode contracts plus tools activated by the hosted runtime's shared `ExtensionManager`. This lets the shell display harness tool metadata such as `task_status` while keeping `modes.py` independent from the harness pack design and avoiding a separate frontend-only extension chain.

Catalog entries include display and source metadata:

- `name`
- `label`
- `renderer_key`
- `permission_category`
- `metadata.preview_arg`
- `metadata.changed_path_arg`
- `source_type`
- `source_id`

Frontends may display dynamic tool source metadata for diagnostics or future extension management. Timeline tool-call preview text, command/file request kind, and changed-file path inference must come from this catalog metadata plus backend-projected permission categories, not from renderer-side tool-name tables. Frontends must continue to treat tool permission behavior as backend-owned and derive permission prompts only from backend events.

Extension diagnostics are frontend-visible health information. Frontends may display them, but they must not infer extension execution policy from them.

Project extension loader failures are mirrored into `extension_diagnostics`. Frontends may display the health information and project extension source metadata, but permission prompts and execution policy remain backend-owned.

Provider turn snapshot metadata may appear in operation diagnostics as `snapshot_id`, mode/workflow state, registered tool names, active tool names, credential-free model profile metadata, resource revision metadata, safe prompt units such as `local_skill_listing`, and capability counts. Frontends may display this for debugging, but full prompts, skill bodies, prompt bodies, file contents, raw tool outputs, and API keys are not part of the frontend protocol.

Telemetry and intranet sink status, if later surfaced, is frontend-visible health only. Frontend protocols must not carry prompts, source text, raw tool outputs, API keys, approval secrets, or permission tokens for telemetry export.

Compaction metadata may appear in `compaction_state` as safe counts, message ids, file paths, and stored evidence refs. Frontends may display this for debugging, but full compacted prompts, raw file contents, raw tool outputs, and API keys are not part of the frontend protocol.

Recovery metadata may appear in `recovery_state` as safe counts, stop reasons, reducer summaries, and trusted-prefix metadata. Frontends may display this for debugging, but prompts, messages, raw tool outputs, file contents, and API keys are not part of the frontend protocol.

For `task_status`, the official presentation metadata is:

- `progress_renderer_key = "tasks"`
- `result_renderer_key = "tasks"`
- `activity_kind = "task"`

## 7. TUI / GUI Rule

TUI and GUI may present different interaction surfaces, but they must agree on:

- session snapshot meaning
- task payload meaning
- permission context meaning
- mode names

If the shells disagree on those semantics, the protocol is drifting and must be corrected.
