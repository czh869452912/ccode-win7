# Phase 6: GUI Experience - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Redesign conversation UI for inline tool display, inline diff preview, real-time streaming, and conversation-first layout. Transform user experience to match industry-leading agent coding tools.

</domain>

<decisions>
## Implementation Decisions

### the agent's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints:
- Python 3.8.x strictly — no walrus operator, no match, no dict | dict
- Offline deployment mandatory — no external CDN dependencies
- Windows 7 compatibility mandatory

</decisions>

<code_context>
## Existing Code Insights

The project has a TUI (Terminal UI) frontend under src/embedagent/frontend/tui/ with:
- Timeline view (views/timeline.py) — nested step panels
- Inspector view (views/inspector.py) — auxiliary panel
- Composer (views/composer.py) — input area
- Frontend adapter (frontend_adapter.py) — bridges backend to frontend

There's also a GUI launcher at src/embedagent/frontend/gui/ with a basic static HTML file.

The new flat timeline (build_flat_timeline from Phase 5) provides items[] array consumable by frontend.

</code_context>

<specifics>
## Specific Ideas

1. Use flat items[] from Phase 5 as the primary data model for GUI rendering
2. Implement inline tool cards showing: tool_name, status (started/completed/failed), arguments, result
3. Implement diff viewer with: line numbers, gutter markers (+/-), syntax highlighting, dark/light theme
4. Implement real-time streaming: item.updated events append output chunks to command execution items
5. Layout: main chat area 70% width, auxiliary panels collapsible to 30%

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
