# EmbedAgent Win7 Release Evidence Runbook

Run this procedure on a clean Windows 7 SP1 x64 machine after extracting one
release flavor. Do not use a system Python, Clang, WebView2 runtime, or PATH
fallback as release evidence. Read `manifests/release-identity.json` first and
verify its `flavor_id`, `bundle_plan_sha256`, and exact `gate_ids`.

1. Run `validate-cli-smoke.cmd --json-report cli-smoke.json` for either release flavor.
2. For `cpp-desktop` only, run `validate-cpp-smoke.cmd` and retain its JSON output.
3. For `cpp-desktop` only, run `validate-gui-smoke.cmd --require-fixed-webview2`.
4. For `cpp-desktop` only, run `validate-gui-smoke.cmd --windowed --auto-close-seconds 8 --require-fixed-webview2`.
5. Combine machine data and exactly the plan-selected gate results into `win7-evidence.json`. Include GUI/C++ objects only when their gate IDs are selected.
6. Copy `manifests/release-identity.json` and the evidence report to the build
   machine without editing either file.
7. Run the bundled `validate-release-evidence.py` with the release identity and
   report. Only an `ACCEPTED` result is a Win7 delivery claim.

The report must identify Windows 7 SP1 AMD64, match the identity flavor/target/plan hash, contain the exact gate set and an empty `blocking_errors` list. `minimal-cli` requires `runtime_contract` and bundle-local `win7_cli_smoke`; GUI/C++ evidence is neither required nor accepted as an extra gate. `cpp-desktop` additionally requires renderer `edgechromium`, Fixed Version WebView2 109 from the bundle, GUI headless/windowed smokes and bundle-local C smoke. A local or Windows 10 run can diagnose problems but cannot replace this target-machine evidence.

## Local Versus Target Evidence

`package.ps1 release -Reproducible` runs two isolated child releases and compares
credential-free bundle records. A passing local run may report `TARGET_READY`
only after both child reports are release-eligible and
`artifact_reproducibility` is `pass`; the comparison report records excluded
operational paths and normalized bundle hashes.

This local state is not a Windows 7 claim. `ACCEPTED` is reserved for the
bundle-local `validate-release-evidence.py` result produced from a clean Windows
7 SP1 x64 machine. Do not copy a local report into the target evidence path or
substitute Windows 10/WebView2 results for the target report.

For `cpp-desktop`, the validator reads the bundled msedgewebview2.exe file version on Windows and requires fixed_webview2.runtime_major=109; do not fill runtime_major by hand. If the major version is missing or differs from 109, the desktop GUI evidence is not acceptable. This check does not apply to `minimal-cli`, which contains no GUI or WebView2 runtime.
