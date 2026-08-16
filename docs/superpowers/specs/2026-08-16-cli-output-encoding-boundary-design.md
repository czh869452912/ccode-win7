# CLI Output Encoding Boundary Design

> Status: approved design awaiting written review
> Type: temporary implementation specification
> Date: 2026-08-16

## 1. Problem

The packaged CLI release smoke passes on the local UTF-8 Windows development
environment but fails consistently on the English GitHub-hosted Windows runner.
The failing scenario is `chat_permission`, which exits with code 4 and is
reported as `protocol_error`.

The failure has a deterministic local reproduction:

- with the default UTF-8 standard streams, the exact release test passes;
- with `PYTHONIOENCODING=cp1252`, the exact release test fails with
  `chat_permission_exit_4_protocol_error`, matching hosted CI.

The first non-ASCII output in that scenario is the Core-owned permission reason
`该操作会修改工作区文件。`. The CLI renderer writes the reason to stdout. A
strict `cp1252` stream raises `UnicodeEncodeError`; because that exception is a
`ValueError`, the shared session client runtime classifies the failed action
delivery as `protocol_error`.

This is not a Linux/Windows behavioral split. Linux jobs and both frontend
matrix jobs pass. It is an undefined CLI text-output boundary exposed by an
English Windows redirected stream.

## 2. Goals

- Make the packaged CLI safe when stdout or stderr cannot encode localized
  product text.
- Preserve UTF-8 output unchanged when the stream supports it.
- Exercise a constrained English Windows code page in the real staged-launcher
  release smoke on every machine.
- Report launcher failures with stable structured fields sufficient to identify
  the scenario, process exit code, and CLI failure category.
- Keep prompts, source, raw tool output, credentials, and permission payloads
  out of reports.
- Keep encoding policy in the product CLI; do not move presentation concerns
  into Core, Protocol, Host, or `SessionClientRuntime`.

## 3. Non-Goals

- Do not translate or remove the Chinese permission reason.
- Do not force Core or Host payloads to ASCII.
- Do not make CI pass only by setting a UTF-8 environment variable in the
  workflow.
- Do not change event ordering, bootstrap, recovery, or action-publication
  semantics.
- Do not add compatibility aliases or preserve obsolete failure-report shapes.
- Do not claim Windows 7 acceptance from hosted CI.

## 4. Considered Approaches

### 4.1 Force UTF-8 only in GitHub Actions

Rejected. This would hide the product defect while a packaged CLI launched from
an English Windows 7 console or redirected process could still fail.

### 4.2 Replace localized permission text with ASCII

Rejected. Permission semantics belong to Core and are valid Unicode data.
Changing one string would leave every other localized output path vulnerable.

### 4.3 Own encoding tolerance at the CLI process boundary

Selected. The CLI entry point configures its standard output streams once,
preserving their selected encoding while changing unencodable-character
handling from strict failure to replacement. This keeps the policy at the
presentation boundary, covers every CLI command, and avoids per-renderer write
wrappers.

## 5. Architecture

### 5.1 CLI Standard Streams

A focused CLI text-output module owns standard-stream preparation. At CLI
startup it examines `sys.stdout` and `sys.stderr`; when a stream exposes Python
3.8's `reconfigure(...)`, it preserves the current encoding and sets
`errors="replace"`. Streams without `reconfigure(...)` are left untouched, so
embedded callers and test-owned `StringIO` objects retain their existing
contracts.

The CLI `main(...)` entry point invokes this preparation before parsing options
or constructing runtime objects. Renderers continue to write normal Unicode
text. UTF-8 streams emit the original text; constrained streams emit their
codec's replacement representation rather than raising.

No encoding policy is added to `SessionClientRuntime`. A runtime action sink
that genuinely raises remains a failed delivery and is still not committed.

### 5.2 Release Smoke Environment

`validate-cli-smoke.py` remains stdlib-only and continues to invoke only the
staged `embedagent.cmd`. Its isolated child environment explicitly sets
`PYTHONIOENCODING=cp1252`, making the release gate deterministic and modeling an
English Windows redirected CLI. This is a test condition, not a production
launcher override.

The same nine scenarios continue to run for `minimal-cli` and `cpp-desktop`.
`chat_permission` proves that a localized permission prompt is delivered, the
scripted approval is consumed as an interaction response, and the requested
file is written.

### 5.3 Safe Failure Diagnostics

Launcher process failures use a dedicated internal exception carrying only:

- scenario identifier;
- observed process exit code;
- stable CLI failure category parsed from the existing `error: <code>` line.

The schema-version-2 failure report projects those values as separate fields in
addition to the high-level failure stage. It does not store stdout, stderr,
prompts, source content, tool output, credentials, or permission details.

## 6. Error Handling

- Standard streams that support reconfiguration use replacement on encoding
  failure.
- Custom or embedded streams are not mutated by global CLI preparation.
- A launcher exit mismatch is reported as a structured smoke failure rather
  than a composite opaque string.
- Unexpected validator exceptions continue to report only their exception type
  and stage.
- Runtime sink exceptions unrelated to text encoding retain current
  delivered-before-committed failure semantics.

## 7. Verification Strategy

TDD proceeds in three slices:

1. A CLI standard-stream unit test constructs strict `cp1252` text streams,
   verifies localized output fails before preparation, then requires preparation
   to preserve the encoding and make the write safe.
2. The real staged-launcher release test runs with validator-owned `cp1252` and
   must initially reproduce `chat_permission_exit_4_protocol_error`; after the
   CLI boundary change it must pass for both flavors.
3. Failure-report tests require separate scenario, exit-code, and CLI-category
   fields and verify that raw child output is absent.

Required final gates are the focused CLI and packaging tests, architecture
guards, the complete regular Python partition, the Windows release partition,
and locked lint. No frontend source changes are planned.

## 8. Documentation And Closure

The durable output-encoding and release-smoke contracts belong in
`docs/product/packaging-and-deployment.md`. When all acceptance conditions are
closed, this specification and its implementation plan move together into an
indexed `docs/archive/cli-output-encoding-boundary/` package, and
`docs/superpowers/README.md` no longer lists the slice.
