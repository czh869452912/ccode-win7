# ADR 0005: GUI Native Launcher In Portable Bundle

## Status

Accepted

## Context

EmbedAgent's release baseline is a one-folder portable Windows 7 x64 offline
bundle. The GUI currently starts through `embedagent-gui.cmd`, which correctly
sets the bundled Python, site-packages, WebView2 Fixed Version 109, and tool
`PATH` environment.

That script entry point is useful for diagnostics, but normal users expect a
native application entry point they can double-click from the bundle root.

## Decision

Add a native Win32 GUI launcher executable to the existing portable bundle:

- `EmbedAgent.exe` for user-facing double-click startup
- `embedagent-gui.exe` for script-friendly GUI startup
- `embedagent-gui.cmd` remains as a diagnostic fallback

The launcher is a thin startup shim only. It resolves the bundle root, sets the
same environment as `embedagent-gui.cmd`, checks bundled Python and WebView2,
forwards arguments to `app/embedagent/frontend/gui/launcher.py`, waits for the
Python process, and returns its exit code.

The product remains a one-folder portable bundle. This ADR does not adopt
PyInstaller, Nuitka, Electron, an installer-first strategy, or a one-file exe
deployment model.

## Consequences

Positive:

- users get a native GUI entry point
- support still has `.cmd` launchers for visible console diagnostics
- the bundle remains inspectable and contract-validated
- Agent Core and GUI runtime architecture remain unchanged

Trade-offs:

- release packaging now has a build-time compiler requirement for the launcher
- validators must check both native exe launchers and `.cmd` launchers
- real Windows 7 smoke remains required to prove the launcher binary is portable

## Follow-Up

1. Keep `validate-offline-bundle.ps1` and `check-bundle-dependencies.py` aligned
   with the launcher set.
2. Keep `validate-gui-smoke.py` preferring `embedagent-gui.exe` for bundle
   tests.
3. Do not replace the portable bundle with one-file freezing unless a separate
   ADR supersedes ADR 0001 and this decision.
