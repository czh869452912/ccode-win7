# EmbedAgent Win7 Release Evidence Runbook

Run this procedure on a clean Windows 7 SP1 x64 machine after extracting the
release bundle. Do not use a system Python, Clang, WebView2 runtime, or PATH
fallback as release evidence.

1. Run `validate-cpp-smoke.cmd` and retain its JSON output.
2. Run `validate-gui-smoke.cmd --require-fixed-webview2` and retain its JSON output.
3. Run `validate-gui-smoke.cmd --windowed --auto-close-seconds 8 --require-fixed-webview2`.
4. Combine the machine, GUI, and C smoke results into `win7-evidence.json`.
5. Copy `manifests/release-identity.json` and the evidence report to the build
   machine without editing either file.
6. Run the bundled `validate-release-evidence.py` with the release identity and
   report. Only an `ACCEPTED` result is a Win7 delivery claim.

The report must identify Windows 7 SP1 AMD64, renderer `edgechromium`, Fixed
Version WebView2 109 from the bundle, bundle C smoke, and an empty
`blocking_errors` list. A local or Windows 10 run can diagnose problems but
cannot replace this target-machine evidence.

## Phase 7R local versus target evidence

`package.ps1 release -Reproducible` runs two isolated child releases and compares
credential-free bundle records. A passing local run may report `TARGET_READY`
only after both child reports are release-eligible and
`artifact_reproducibility` is `pass`; the comparison report records excluded
operational paths and normalized bundle hashes.

This local state is not a Windows 7 claim. `ACCEPTED` is reserved for the
bundle-local `validate-release-evidence.py` result produced from a clean Windows
7 SP1 x64 machine. Do not copy a local report into the target evidence path or
substitute Windows 10/WebView2 results for the target report.

The validator reads the bundled msedgewebview2.exe file version on Windows and
requires fixed_webview2.runtime_major=109; do not fill runtime_major by hand.
If the major version is missing or differs from 109, the GUI evidence is not
acceptable.