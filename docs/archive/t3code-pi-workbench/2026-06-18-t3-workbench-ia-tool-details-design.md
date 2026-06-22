# T3 Workbench IA And Tool Details Design

## Goal

Move the GUI closer to T3 Code by making the workbench information architecture clearer and replacing raw timeline tool JSON with readable, tool-aware detail views.

## Scope

- GUI webapp only.
- No Agent Core, protocol, permission, workflow package, or transcript ledger changes.
- Left sidebar owns workspace/thread navigation.
- Right panel Files surface owns file-tree browsing.
- Timeline work rows expose structured details for common tool calls instead of raw JSON.
- Primary scroll regions remain usable and test-covered.

## Architecture

The timeline projector remains the normalization boundary. It will add a stable `detailModel` to work rows while preserving existing primitive fields such as `args`, `changedFiles`, `commandPreview`, and `detail` for compatibility. React rendering stays in timeline components and consumes the structured model without importing backend, runtime, or Core modules.

The sidebar change is an information-architecture cleanup. `Sidebar` stops receiving file-tree props and no longer renders the Files tab; existing file-tree state and loading remain shared app-shell state consumed by the right-panel `FilesSurface`.

Scroll fixes stay in CSS and visual/test assertions. The change should make timeline, thread list, right-panel body, file tree, and file preview behave as explicit scroll containers without making the app shell or Agent Core aware of GUI display state.

## User Experience

Tool rows still collapse into a compact T3-style summary. When expanded, a user sees a concise detail surface with:

- a tool-specific title/status;
- path, pattern, command, or recipe metadata as compact fields;
- result summary, stdout/stderr, preview, diff, and changed files where available;
- no default raw JSON dump for normal tool data.

The left sidebar should feel like a navigation rail for the active project and threads. File browsing moves to the right panel where it can sit beside timeline/editor surfaces.

## Testing

- Unit tests cover tool detail projection for representative read/search/write/command data.
- Component/source tests assert work rows render structured details without raw JSON fallback.
- Sidebar tests assert the left Files tab is absent and right Files surface remains available.
- Visual/debug harness covers timeline tool detail expansion, scrollability, and left/right file-tree ownership.

## Non-Goals

- No new file editor.
- No source-control mutation.
- No Agent Core hook, reducer, capability, permission, or workflow changes.
- No online dependency or runtime Node dependency.
