# T3 GUI Parity Ledger

This ledger records the current T3 Code reference and the intentionally
limited subset ported into the offline EmbedAgent GUI. It is a comparison
record, not a runtime dependency declaration.

## Reference Baseline

| Field | Value |
| --- | --- |
| Checkout | reference/t3code |
| Commit | 2318e00270203780b72efbbcffce92e907312027 |
| Date | 2026-07-18 |
| Subject | fix(web): avoid duplicate mention text on paste |

## Relevant Surface Map

| Surface | T3 reference | EmbedAgent target | Classification | Status |
| --- | --- | --- | --- | --- |
| Sidebar and thread list | apps/web/src/components/Sidebar.tsx | src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx | UX + client runtime | existing parity slice |
| App shell and navigation | apps/web/src/components/AppSidebarLayout.tsx | src/embedagent/frontend/gui/webapp/src/components/workbench/AppSidebarLayout.jsx | UX + client runtime | existing parity slice |
| Chat and timeline | apps/web/src/components/ChatView.tsx and components/chat | src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx and session-runtime/t3-timeline.js | UX + projection | existing parity slice |
| Composer | apps/web/src/components/chat/ChatComposer.tsx | src/embedagent/frontend/gui/webapp/src/components/Composer.jsx and composer/ | UX + interaction | existing parity slice |
| Right panel | apps/web/src/components/RightPanelTabs.tsx and file/diff components | src/embedagent/frontend/gui/webapp/src/components/workbench/ and components/diff/ | UX + surface state | existing parity slice |
| Terminal | apps/web/src/components/ThreadTerminalDrawer.tsx | src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx and terminal/ | UX + service adapter | existing parity slice |
| Source control | apps/web/src/components/GitActionsControl.tsx | src/embedagent/frontend/gui/webapp/src/components/source-control/ | UX + service adapter | existing parity slice |
| Thread state | packages/client-runtime/src/state/threadState.ts and threadReducer.ts | src/embedagent/frontend/gui/webapp/src/session-runtime/thread-state.js | client runtime | partial convergence |
| Shell state | packages/client-runtime/src/state/shell.ts and shellReducer.ts | src/embedagent/frontend/gui/webapp/src/app-shell/ and workbench/ | client runtime | partial convergence |
| App/session contract | packages/contracts/src/server.ts and rpc.ts | src/embedagent/frontend/gui/backend/protocol_payloads.py and webapp runtime | protocol | partial convergence |

## Explicit Exclusions

The following T3 areas are excluded infrastructure for the Win7/offline
product and must not be silently reimplemented as a different GUI behavior:

- cloud authentication, Clerk, and account pairing;
- Relay, remote environments, SSH, Tailscale, and hosted connections;
- mobile clients and mobile-specific routes;
- Electron desktop APIs and automatic updates;
- provider marketplace and online model/service discovery.

When an excluded feature changes in T3, record the new reference path and
leave the row classified as excluded infrastructure.

## Re-Baselining Procedure

Run these commands from the repository root when reference/t3code changes:

~~~powershell
git -C reference/t3code log -1 --date=iso --format="%H%n%ad%n%s"
rg --files reference/t3code/apps/web/src reference/t3code/packages/client-runtime/src reference/t3code/packages/contracts/src
~~~

Record the new commit, date, and subject before porting a change. Diff only
the three relevant T3 path groups, classify each change as UX, client runtime,
protocol, or excluded infrastructure, then run the GUI and architecture gates.
