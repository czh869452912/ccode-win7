# GUI Bundle Launcher Exe Design

## Goal

Improve the offline GUI startup experience by adding a native Windows launcher
executable to the existing one-folder portable bundle.

The launcher should let users double-click `EmbedAgent.exe` or
`embedagent-gui.exe` from the bundle root to start the GUI, while preserving the
current offline bundle architecture, Windows 7 target, Python 3.8 runtime, and
WebView2 Fixed Version 109 renderer requirement.

## Current Baseline

The current release shape is a self-contained portable directory:

```text
EmbedAgent/
├── embedagent.cmd
├── embedagent-tui.cmd
├── embedagent-gui.cmd
├── runtime/
│   ├── python/
│   ├── site-packages/
│   └── webview2-fixed-runtime/
├── app/embedagent/
├── bin/git/
├── bin/rg/
├── bin/ctags/
├── bin/llvm/
├── config/
├── docs/
└── manifests/
```

`embedagent-gui.cmd` currently owns the GUI startup environment:

- `EMBEDAGENT_BUNDLE_ROOT`
- `PYTHONHOME`
- `PYTHONPATH`
- `PYTHONNOUSERSITE`
- bundled `PATH` entries for MinGit, ripgrep, Universal Ctags, and LLVM/Clang
- checks for bundled Python and WebView2 Fixed Version runtime
- launch of `app\embedagent\frontend\gui\launcher.py`

This is already aligned with the accepted portable bundle baseline, but it gives
users a script-like entry point instead of a native app entry point.

## Design Principles

1. The one-folder portable bundle remains the product delivery baseline.
2. The launcher executable is a thin startup shim, not a frozen Agent Core.
3. The existing `.cmd` launchers stay available for diagnostics and fallback.
4. No runtime dependency on Docker, WSL, VS Code, Electron, runtime Node, online
   services, system Python, system Git, system LLVM, or system WebView2 is added.
5. Windows 7 compatibility remains mandatory.
6. WebView2 must continue to use the bundled Fixed Version 109 runtime.
7. Agent Core, GUI backend, GUI frontend, session history, permissions,
   workflow state, and runtime reducers are unchanged.

## Recommended Approach

Add a small native Win32 GUI launcher executable to the bundle root.

The recommended implementation language is C or C++ using Win32 APIs. This
keeps the launcher independent of .NET, Python, Node, or installer frameworks
and gives the project direct control over path handling, environment setup, and
subprocess creation.

The launcher should be built as a GUI subsystem executable so double-clicking it
does not leave a console window behind. It may show blocking startup errors with
`MessageBoxA` or `MessageBoxW`, while returning non-zero process exit codes for
scripted validation.

### Why Not A One-File Exe

One-file packaging is intentionally out of scope for this slice. Freezing the
entire Python GUI would make the bundle harder to inspect, validate, checksum,
license, and repair. It would also make external runtime tools such as
LLVM/Clang, MinGit, ripgrep, Universal Ctags, and WebView2 harder to reason
about.

The product needs a native entry point, not a different deployment model.

## Launcher Behavior

The launcher should:

1. Resolve its own executable directory as `BUNDLE_ROOT`.
2. Set `EMBEDAGENT_BUNDLE_ROOT=%BUNDLE_ROOT%`.
3. Set `PYTHONHOME=%BUNDLE_ROOT%\runtime\python`.
4. Set `PYTHONPATH=%BUNDLE_ROOT%\app;%BUNDLE_ROOT%\runtime\site-packages`.
5. Set `PYTHONNOUSERSITE=1`.
6. Prepend these paths to `PATH`:
   - `%BUNDLE_ROOT%\bin\git\cmd`
   - `%BUNDLE_ROOT%\bin\git\bin`
   - `%BUNDLE_ROOT%\bin\rg`
   - `%BUNDLE_ROOT%\bin\ctags`
   - `%BUNDLE_ROOT%\bin\llvm\bin`
   - `%BUNDLE_ROOT%\bin\llvm\libexec`
7. Validate that `%BUNDLE_ROOT%\runtime\python\python.exe` exists.
8. Validate that
   `%BUNDLE_ROOT%\runtime\webview2-fixed-runtime\msedgewebview2.exe` exists.
9. Forward all command-line arguments to:

```text
%BUNDLE_ROOT%\runtime\python\python.exe
%BUNDLE_ROOT%\app\embedagent\frontend\gui\launcher.py
```

10. Wait for the Python GUI process to exit and return its exit code.

Argument quoting must preserve spaces in workspace paths and user-provided
options. The launcher should use `CreateProcessW` and construct a quoted command
line rather than relying on shell execution.

## Bundle Shape

The bundle root should contain:

```text
EmbedAgent.exe
embedagent-gui.exe
embedagent-gui.cmd
```

`EmbedAgent.exe` may be the user-facing display name and `embedagent-gui.exe`
may be a stable script-friendly alias. If maintaining two binaries is
unnecessary, `embedagent-gui.exe` can be a copied artifact of the same launcher
binary.

The existing `embedagent-gui.cmd` stays in place and continues to be validated.
It remains useful when a support engineer wants to see console output or compare
launcher behavior.

## Packaging Changes

### Source Layout

Add launcher source under a packaging-owned path, for example:

```text
scripts/launcher/embedagent_gui_launcher.cpp
```

The source should avoid dependencies outside the Windows SDK and C/C++ runtime
available to the build toolchain.

### Build Stage

The packaging control plane should gain an internal launcher build step before
bundle assembly validates launcher artifacts.

The build step should:

- compile the launcher executable on the build machine
- emit it under a build cache/artifact directory
- stage it into the bundle root during `prepare-offline.ps1`
- fail release packaging if the executable cannot be produced or staged

The build machine may use an installed compiler or a configured project
toolchain. The runtime bundle must not require that compiler after packaging.

### Staging

`prepare-offline.ps1` should stage the generated launcher executable into:

- `EmbedAgent.exe`
- `embedagent-gui.exe`

It should continue generating `embedagent-gui.cmd`.

The bundle manifest should include a `gui_launcher_exe` component so validation
and release reports can explain whether the native launcher is present.

### Validation

`validate-offline-bundle.ps1` should add static checks for:

- `EmbedAgent.exe`
- `embedagent-gui.exe`
- existing `embedagent-gui.cmd`

Dynamic checks should include:

```cmd
EmbedAgent.exe --help
embedagent-gui.exe --help
embedagent-gui.cmd --help
```

`validate-gui-smoke.py` should prefer the native launcher when `--bundle-root`
is provided, while retaining an explicit fallback path for `.cmd` diagnostics if
needed by tests or support workflows.

The Win7 GUI validation guide should update its suggested commands to include:

```cmd
EmbedAgent.exe --help
embedagent-gui.exe --help
validate-gui-smoke.cmd
validate-gui-smoke.cmd --windowed --auto-close-seconds 8
```

## User Experience

For normal users:

- unzip the bundle
- double-click `EmbedAgent.exe`
- choose or activate a workspace inside the GUI

For command-line users and support:

- `embedagent-gui.exe --workspace D:\Project`
- `embedagent-gui.cmd --workspace D:\Project`
- `validate-gui-smoke.cmd --windowed --auto-close-seconds 8`

Startup errors should be direct and repair-oriented:

- missing Python runtime
- missing WebView2 Fixed Version runtime
- missing GUI launcher script
- failure to create the Python GUI process

## Error Handling

The native launcher should fail before starting Python if required bundle files
are missing. It should report:

- the missing file path
- the expected bundle root
- a hint to repair or rebuild the offline bundle

Subprocess creation failures should report the Windows error code. If Python
starts and exits with a non-zero code, the native launcher should return that
code without hiding it.

If `--help` is passed, the launcher should still run the Python GUI parser so
the help output remains owned by `launcher.py`.

## Testing Strategy

### Unit / Static Tests

Add tests or script checks for:

- launcher source exists
- launcher artifact staging is represented in the bundle manifest
- validator requires both native GUI launcher names
- `.cmd` launcher remains present

### Packaging Verification

Run:

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 assemble -Profile dev
pwsh -File scripts/package.ps1 verify -Profile dev
```

For release readiness:

```powershell
pwsh -File scripts/package.ps1 release -Profile release
```

### Dynamic Checks

From the bundle root:

```cmd
EmbedAgent.exe --help
embedagent-gui.exe --help
embedagent-gui.cmd --help
validate-gui-smoke.cmd
```

On a real Windows 7 target, also run:

```cmd
validate-gui-smoke.cmd --windowed --auto-close-seconds 8
```

The windowed check must still confirm:

- renderer is `edgechromium`
- runtime source is `bundle`
- WebView2 Fixed Version 109 is used from the bundle

## Documentation Updates

Durable docs should be updated in the implementation slice:

- `README.md`
- `AGENTS.md` if governance wording changes
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/modules/packaging-and-deployment.md`
- `docs/guides/win7-gui-validation.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

If the implementation creates a lasting decision about launcher technology, add
an ADR or update the packaging control-plane ADR with the native launcher
decision.

## Risks And Mitigations

### Risk: The Launcher Becomes A Second Runtime

Mitigation: keep it limited to environment setup, preflight checks, argument
forwarding, process creation, and exit-code propagation. All GUI behavior stays
in `launcher.py` and the existing backend/frontend.

### Risk: Win7 Build Compatibility Is Assumed But Not Proven

Mitigation: compile with conservative Win32 APIs, avoid modern CRT assumptions
where possible, and keep real Windows 7 smoke validation as the release proof.

### Risk: Path Quoting Breaks Workspace Arguments

Mitigation: use wide-character Windows APIs, quote each path and forwarded
argument deterministically, and add validation for paths containing spaces.

### Risk: Native Launcher Hides Useful Diagnostics

Mitigation: preserve `embedagent-gui.cmd` as the visible-console fallback and
ensure native launcher errors include the failed path and Windows error code.

### Risk: Packaging Adds A Build-Time Tool Requirement

Mitigation: treat the compiler as build-time only. The produced bundle remains
self-contained and never requires a compiler to start the GUI.

## Success Criteria

1. The offline bundle includes `EmbedAgent.exe`, `embedagent-gui.exe`, and
   `embedagent-gui.cmd`.
2. Double-clicking `EmbedAgent.exe` starts the GUI from the bundle root.
3. `EmbedAgent.exe --help` and `embedagent-gui.exe --help` return exit code `0`.
4. `embedagent-gui.cmd --help` still returns exit code `0`.
5. `validate-offline-bundle.ps1` treats missing native GUI launcher artifacts as
   release-blocking.
6. `validate-gui-smoke.py --bundle-root <bundle>` can launch through the native
   launcher.
7. Win7 windowed smoke still reports bundled `edgechromium`.
8. No Agent Core, permission, workflow, transcript, reducer, or backend protocol
   semantics change.
9. The product remains a one-folder offline portable bundle, not a one-file exe.
