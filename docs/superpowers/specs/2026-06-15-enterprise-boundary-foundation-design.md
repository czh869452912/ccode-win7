# Enterprise Boundary Foundation Design

## Purpose

Implement the first code-level guardrails for the Pi-style enterprise/intranet
boundary without adding real network integrations. The goal is to make future
intranet Git, custom service, provider, catalog, and telemetry work visible to
the same permission and metadata pipeline instead of hiding it behind `read`,
`other`, or ad hoc diagnostics.

## Scope

- Add explicit `network` and `telemetry` permission categories.
- Allow dynamic extension tools and project extension manifests to declare those
  categories.
- Keep the default policy conservative: both categories ask unless a matching
  rule or auto-approve-all allows them.
- Add a local-only telemetry envelope helper that keeps safe operational fields
  and redacts or summarizes sensitive values.
- Do not open sockets, upload telemetry, install dependencies, or introduce a
  telemetry service.

## Architecture

Permission category truth should be shared from `embedagent.permissions` so
runtime tool registration, self-extension authoring, and project extension
manifest validation do not drift. `ToolRuntime` remains the catalog and schema
projection boundary; the new categories only affect metadata and permission
decisions.

`embedagent.telemetry` is a small utility module, not a sink framework. It builds
safe event envelopes for future adapters by copying only scalar operational
metadata, summarizing lists and dictionaries, and redacting sensitive keys such
as prompts, source text, raw tool outputs, API keys, tokens, secrets, and
permission payloads.

## Testing

Use TDD with focused tests:

- permission policy asks for dynamic tools categorized as `network` or
  `telemetry`
- permission context exposes the new categories
- dynamic tool registration accepts `network` and `telemetry` metadata
- project extension manifests and authoring accept the new categories
- telemetry envelopes redact sensitive fields and keep safe fields

## Non-Goals

- Real intranet Git/custom service implementations
- Remote catalog loading
- Telemetry upload or buffering
- New runtime dependencies
- Public extension marketplace behavior
