# T3-Parity GUI And Visual Debug Design

## Reader And Action

This design is for the engineer implementing the next GUI slice. After reading
it, they should be able to build a Windows 7-compatible EmbedAgent GUI that
closely follows T3 Code's core interaction model for timeline, pending
interaction, and diff review, while also adding a development-only visual
debugging harness that Codex can drive.

## Decision

Use T3 Code as the product interaction reference, not as the runtime base.

The target is a near one-to-one recreation of T3 Code's core coding-agent
experience inside EmbedAgent's existing GUI stack:

- Python-hosted FastAPI backend
- static React webapp
- pywebview / WebView2 109 for packaged GUI
- Chrome 109-compatible frontend bundle
- offline deployment
- Agent Core and C/C++ workflow semantics owned by EmbedAgent

Do not fork T3 Code as the primary product base for this slice.

## Why T3 Code Cannot Be Used Directly

T3 Code is MIT licensed, so its design and selected code ideas can be reused
with attribution where appropriate. It is not a good direct base for
EmbedAgent's product constraints.

The current T3 Code repository assumes:

- Node 24 at the monorepo root, and Node 22+/24 for the server package
- pnpm 10 and Vite Plus
- React 19, Tailwind 4, Vite Plus browser tests, and modern bundling
- Electron desktop packaging
- provider CLIs, auth/pairing, relay, SSH, Tailscale, SQLite, and remote
  environment concepts
- online installation and provider authentication flows

Those assumptions conflict with EmbedAgent's baseline:

- Python 3.8 runtime
- Windows 7 compatibility
- offline bundle startup without Node or Electron at runtime
- bundled WebView2 109 rather than Electron
- Agent Core first, with UI shells as replaceable consumers
- default C/C++ workflow owned by the bundled workflow package
- no required online service, relay, marketplace, provider cloud, Docker, WSL,
  VS Code, or runtime dependency install

Forking T3 Code would require removing or replacing its runtime, packaging,
auth, relay, provider, and orchestration layers. That would be more work and
risk than reproducing the desired GUI behavior in EmbedAgent.

## Reuse Policy

Treat T3 Code as an interaction specification and reference implementation.

Allowed:

- Mirror visible behavior, component boundaries, and state transitions.
- Port small pure helper ideas when they fit EmbedAgent's dependency and
  browser target constraints.
- Keep local notes mapping T3 concepts to EmbedAgent protocol fields.
- Use the local T3 clone as reference during implementation.

Not allowed:

- Add Electron to EmbedAgent.
- Require Node at runtime.
- Require pnpm, Vite Plus, or T3's monorepo tooling for the shipped product.
- Import T3 packages directly into the EmbedAgent GUI.
- Add Clerk, relay, SSH, Tailscale, remote environment, or provider CLI
  assumptions to Agent Core.
- Make the GUI own transcript history, permission decisions, tool activation,
  workflow state, extension loading, or provider behavior.

If code is copied from T3 rather than independently reimplemented, the
implementation must preserve MIT attribution and keep the copied surface small,
auditable, and compatible with EmbedAgent's build target.

## Scope

The first parity slice covers the core experience only:

- messages timeline
- work/tool rows
- turn folding
- pending permission and ask-user interaction
- changed-files summary
- diff panel
- Codex-driven visual debugging for the real development GUI

Out of scope:

- T3 cloud, relay, auth, pairing, SSH, Tailscale, and provider picker flows
- Electron desktop shell
- terminal/browser surfaces
- mobile UI
- checkpoint revert semantics beyond showing safe diff summaries
- changing Agent Core, transcript truth, workflow package ownership, or
  permission policy
- Win7-machine automation. Development automation runs on the current Win10/11
  development environment.

## Product Parity Targets

### Messages Timeline

EmbedAgent's timeline should follow T3 Code's `MessagesTimeline` behavior:

- user messages align as compact user bubbles
- assistant messages render as Markdown responses
- work entries are compact rows between user and assistant messages
- settled turns collapse intermediate work behind a "Worked for ..." style fold
- interrupted turns remain expanded until the next turn
- the latest running turn stays unfolded
- copy and metadata controls are quiet until hover/focus
- long work output opens inline rather than forcing a side panel
- timeline keeps the user's scroll position stable when folds toggle

EmbedAgent-specific projection rules:

- transcript/bootstrap remains the history source
- WebSocket live events and bootstrap history must produce the same row model
- `turn_id`, `step_id`, and `step_index` remain authoritative anchors
- projection badges are useful while the cutover is incomplete, but should be
  hidden or moved to diagnostics once parity is stable

### Work Rows

Work rows should follow T3's compact tool/work presentation:

- one-line row by default
- icon reflects the activity kind: read, write, command, task, diagnostic, or
  user input
- success/failure/neutral indicators live at the right edge
- details expand in place
- file-change rows show changed file count and diff stats when available
- command rows show command preview and raw command only when expanded
- failed rows have a visibly distinct tone without overwhelming the timeline

EmbedAgent maps this from existing tool metadata:

- tool name and catalog label
- permission category
- progress/result renderer keys
- tool arguments after private metadata is stripped
- tool result summaries, diagnostics, and diff previews
- runtime source and resolved tool roots for diagnostics only

### Pending Permission

T3 shows pending approval in the composer area rather than burying it in a
generic inspector. EmbedAgent should do the same.

Target behavior:

- pending permission appears above or inside the composer area
- the panel states the request kind: command, file read, file change, or other
  permission category
- approve/deny actions are immediately reachable
- optional "remember" remains available for permission categories that support
  backend-owned remembered approvals
- the timeline receives a compact interaction row showing that approval was
  requested and then resolved
- stale/expired/conflicting interactions show a non-actionable notice

Backend ownership remains unchanged. The GUI only sends an interaction response
to the existing backend endpoint.

### Pending User Input

T3's pending user input panel should be mirrored:

- active question appears in the composer area
- option cards are keyboard-selectable with number keys
- single-select options can auto-advance after a short delay
- multi-question prompts show progress
- custom answer remains possible when the prompt allows free-form input
- submitting the final answer resolves the backend interaction
- answered prompts leave a compact resolved interaction row in the timeline

EmbedAgent's current `ask_user` shape is simpler than T3's multi-question
model. The first implementation should normalize it into a one-question
internal view. Later slices can extend the backend contract if multi-question
ask-user becomes official.

### Diff And Changed Files

T3's diff experience has two layers:

- a changed-files card attached to the relevant turn
- a right-panel diff surface that can focus a whole turn or a single file

EmbedAgent should reproduce that behavior with its own data:

- file write/edit tool results can create turn-level changed-file summaries
- `/diff` and review evidence can open the diff surface
- the right panel has a first-class `diff` surface, not only a generic preview
- selecting a file in the changed-files card focuses that file in the diff
  panel
- the diff panel can show parseable diffs with file-level sections and fallback
  to raw unified diff when parsing fails

The existing `diff2html` dependency can remain for the first parity pass if it
meets Chrome 109 and offline constraints. A later implementation may replace it
with a smaller local renderer if needed.

## EmbedAgent Data Model Mapping

Introduce a GUI-local row model similar to T3's timeline rows. It is a
frontend projection, not a new session-history source.

Suggested row kinds:

- `message`
- `work`
- `turn_fold`
- `interaction`
- `diff_summary`
- `working`
- `system_notice`

Suggested work entry fields:

- id
- created timestamp when available
- turn id
- step id
- tool name
- label
- request kind
- tone
- command preview
- detail
- changed files
- diff stats
- expandable body
- status

The projection should be produced from:

- bootstrap history turns
- live WebSocket events
- session event log interaction lifecycle events
- session snapshot pending interaction
- tool catalog metadata
- review/diff command results

This projection must be pure and covered by frontend tests.

## Visual Debugging Harness

Add a development-only GUI debugging mechanism that Codex can operate.

The mechanism should:

- start the real GUI backend in source-tree development mode
- use a deterministic fake OpenAI-compatible model server
- seed scenarios for normal reply, tool use, permission, ask-user, file edit,
  diff, review, failure, and compact/recovery notices where possible
- open the GUI in Playwright Chromium
- capture screenshots for desktop and narrow widths
- click composer controls, pending permission actions, pending user-input
  options, turn folds, changed-files entries, right-panel tabs, and diff files
- read DOM assertions for visible state, not only HTTP responses
- store screenshots, traces, console errors, and scenario summaries under a
  generated debug output directory

The harness should not:

- automate the pywebview desktop window in the first version
- require Win7
- require external network
- depend on T3 runtime
- become part of the shipped offline runtime

Implementation can live under scripts and webapp test helpers. Playwright is a
development dependency only.

## Implementation Slices

### Slice 1: T3 Parity Projection

Build the pure frontend projection layer:

- normalize bootstrap and live events into T3-like rows
- derive work rows from tool events
- derive pending/resolved interaction rows
- derive changed-file summaries from tool results and diff command results
- add structural sharing where useful to reduce rerenders

Verification:

- webapp helper tests for row derivation
- live/reload equivalence tests
- no backend protocol change required

### Slice 2: Timeline Parity Components

Replace the current timeline presentation with T3-like row components:

- message rows
- compact work rows
- expandable work details
- turn fold rows
- working indicator
- hidden diagnostics/debug badges by default

Verification:

- webapp tests
- static build
- Playwright screenshot scenario for normal, tool, failed tool, and folded turn

### Slice 3: Composer Pending Interaction

Move pending permission and ask-user handling into the composer area:

- approval panel
- user-input option panel
- number-key option shortcuts
- remember approval option
- stale/expired notice handling
- timeline interaction row parity

Verification:

- reducer/component tests for permission and user-input flows
- Playwright click tests for approve, deny, option select, and custom answer
- existing GUI backend interaction tests remain authoritative for backend
  behavior

### Slice 4: Diff Parity

Promote diff from generic preview into a first-class right-panel surface:

- changed-files card in the timeline
- diff surface state with optional focused file
- parseable diff render and raw fallback
- `/diff`, review evidence, and file-change tool results open the same surface

Verification:

- helper tests for changed-file summary and focused diff state
- Playwright screenshots for multi-file diff, focused file, parse fallback
- static build

### Slice 5: Codex Visual Debug Harness

Add the development harness:

- script to start fake model and GUI backend
- Playwright scenario runner
- screenshot/trace output
- scenario fixtures for timeline, interaction, and diff
- concise JSON summary for agents

Verification:

- harness runs locally on the development machine
- screenshots are created
- console errors fail the run unless explicitly allowlisted
- existing headless GUI smoke remains available for API-level coverage

### Slice 6: TUI Follow-Up

TUI parity is lower priority. After GUI core parity lands, mirror the same
mental model in prompt_toolkit:

- compact work rows
- foldable turns where terminal width allows
- pending interaction overlay
- diff summary and raw diff viewer
- future headless render/debug capture inspired by Pi's TUI tests

## Acceptance Criteria

- GUI core interaction closely matches T3 Code for timeline, work rows,
  pending interaction, and diff review.
- The implementation runs in EmbedAgent's current GUI stack and remains
  compatible with Chrome/WebView2 109.
- No T3 runtime, Electron, online auth, relay, SSH, Tailscale, Node runtime, or
  provider CLI dependency enters EmbedAgent's shipped product.
- Agent Core remains authoritative for workflow state, transcript history,
  permission decisions, tool activation, extension loading, and provider
  behavior.
- Codex can run a local visual debug harness, inspect screenshots, click the
  real GUI, and use DOM assertions to verify UI fixes.
- Existing GUI backend smoke tests continue to cover protocol-level behavior.

## Documentation Follow-Up

When implementation lands, update the active source-of-truth docs that describe
actual product behavior:

- frontend protocol
- GUI module documentation
- TUI module documentation if TUI parity work lands
- implementation roadmap and development tracker
- design change log

Do not update active architecture docs to claim T3 parity is implemented until
the corresponding slices are actually merged.
