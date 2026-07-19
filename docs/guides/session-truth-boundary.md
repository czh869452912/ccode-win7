# Session Truth Boundary

Status: current transcript-backed session-history boundary; synchronized 2026-07-19.

This guide records the current durable session-history boundary after the
Phase 5 session projection and reducer work. It is an ownership contract, not
a new runtime API.

## Official Truth

| Concern | Owner | Durable status |
| --- | --- | --- |
| Session log entries | `SessionLogPort`; hosted `TranscriptStore` adapter | `transcript.jsonl` is durable input |
| Live Core state | `embedagent_core.Session` during an active turn | live structured working projection; durable history remains the transcript log |
| Restore | `SessionRestorer` | reduces a trusted transcript prefix and exposes operation/compaction/recovery read models |
| GUI/TUI history | `SessionHistoryAssembler` through session bootstrap | projection of `Session`/transcript restore, not a separate ledger |
| GUI activation | `GET /api/sessions/{id}/bootstrap` | one bootstrap payload containing snapshot, history, plan, permissions, and capabilities |
| Live event delivery | session event/WebSocket transport | ephemeral transport only |
| Timeline UI | TUI/GUI presentation modules | view vocabulary, not durable state |

## Current Evidence

- `packages/embedagent-host/src/embedagent_host/runtime/transcript_store.py`
  is the hosted durable transcript adapter.
- `packages/embedagent-host/src/embedagent_host/runtime/session_history.py`
  builds `turns` and `activities` from the session read model and carries
  transcript restore integrity metadata.
- `packages/embedagent-host/src/embedagent_host/runtime/session_bootstrap_service.py`
  composes history through an injected `history_loader`; it has no timeline
  store or replay loader.
- `src/embedagent/frontend/tui/services/timeline.py` reads the `history` field
  from session bootstrap and does not call a timeline endpoint.
- `src/embedagent/frontend/gui/backend/protocol_payloads.py` serializes
  session `history` and does not expose a durable replay/timeline payload.
- There is no active `timeline_store.py`, `timeline.jsonl`, `get_timeline`, or
  `load_timeline` implementation in Core, Host, or GUI backend source.

The regression contract is implemented in
`tests/test_session_truth_boundaries.py` and complements the existing session
restore, GUI bootstrap, and no-timeline API tests.

## Deletion Rules

Future changes must not:

- add a durable timeline file or timeline-specific session ledger;
- add a `/timeline` or `get_timeline` history endpoint;
- add a `replay`/`timeline` field to the GUI session bootstrap contract;
- make review, history, diagnostics, or restore depend on an ephemeral event
  stream;
- recreate compatibility serializers for pre-release timeline shapes.

If a live stream is needed, it remains a transport cache or a transcript-
derived replay channel and must not become a second source of session truth.

## Closed Follow-Up

The Phase 5 session projection and reducer work is closed for the current
pre-release architecture. Session remains the live structured state for an
active turn, while transcript.jsonl is the only durable session-history
ledger. Future changes must preserve this split and must not introduce a second
timeline or replay store.
