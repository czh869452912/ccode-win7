# Transcript-Truth Tool Result Persistence Cutover

> Date: 2026-04-05
> Status: Approved design baseline
> Scope: Query/Context persistence cutover, tool-result storage, projection storage redesign

## 1. Goal

EmbedAgent will replace the current "artifact-index + mutable JSON projections" path with a transcript-truth architecture that is safe under parallel tool execution and stable under resume.

The target outcome is:

- `transcript.jsonl` becomes the only session truth source
- large tool-result payloads are persisted as session-local files keyed by `tool_call_id`
- SQLite becomes the canonical projection store for fast listing, browsing, cleanup, and project-memory read models
- `summary.json`, artifact-style listings, and project-memory exports become disposable projections
- old session formats are not migrated or resumed

This is a hard cutover design. The implementation target is the final architecture, not a long-lived compatibility bridge.

## 2. Current Problem

The current design has a structural mismatch between tool execution and persistence:

- tools such as `read_file` are classified as `read_only` and `concurrency_safe`
- the execution path later calls `shrink_observation()`, which writes large fields to `.embedagent/memory/artifacts/...`
- those writes update a shared mutable `artifacts/index.json`
- the shared index is maintained through read-modify-write plus fixed-name temp-file replacement

This produces three design-level failures:

1. "read-only" tools are not actually side-effect-free at runtime
2. parallel execution shares a single mutable file hotspot
3. projection failure can incorrectly fail a tool whose primary work already succeeded

The observed Windows errors are symptoms of this mismatch, not the root problem.

## 3. Design Decisions

The cutover is based on the following explicit decisions:

- session truth remains append-only transcript events
- old session files are discarded; no importer and no resume compatibility layer
- large tool-result persistence is file-based and session-local
- projection metadata is stored in SQLite, not in mutable JSON index files
- parallelism is allowed only in the execution layer
- all shared-state writes happen in a single-writer commit layer
- projection failure must not downgrade primary tool success

## 4. Design Principles

- Windows 7 compatibility remains mandatory
- Python 3.8 compatibility remains mandatory
- append-only truth is preferred over mutable shared state
- session truth must be durable without depending on projections
- projections must be rebuildable from transcript plus persisted tool-result files
- the system must not require cross-thread locking around mutable JSON files
- user-visible labels may continue to say "artifacts", but the runtime model must not depend on the legacy `ArtifactStore` contract

## 5. Target Model

### 5.1 Truth Layer

The truth layer consists of:

- `.embedagent/memory/sessions/<session_id>/transcript.jsonl`
- `.embedagent/memory/sessions/<session_id>/tool-results/<tool_call_id>/<field>.txt|json`

Truth-layer properties:

- append-only transcript events are authoritative
- tool-result files are immutable after first successful write
- a session remains resumable even if all projections are deleted

### 5.2 Projection Layer

The projection layer consists of:

- `.embedagent/memory/projections.sqlite3`
- optional human-readable exports such as `summary.json`
- optional UI-oriented cached listings

Projection-layer properties:

- SQLite is the canonical fast-read index for derived state
- JSON exports are best-effort views only
- runtime restore does not require any projection file

### 5.3 Session-Local Tool Result Storage

Each large externalized field is stored under the current session and tool call:

```text
.embedagent/
  memory/
    sessions/
      <session_id>/
        transcript.jsonl
        tool-results/
          <tool_call_id>/
            content.txt
            stdout.txt
            stderr.txt
            diagnostics.json
```

This removes the current workspace-wide shared artifact directory hotspot and makes file paths deterministic and collision-free.

## 6. Storage Contract

### 6.1 Transcript Events

The transcript keeps the existing event-driven session truth and adds first-class tool-result replacement records.

Required event families for this cutover:

- `message`
- `tool_call`
- `tool_result`
- `content_replacement`
- `compact_boundary`
- `pending_interaction`
- `pending_resolution`
- `context_snapshot`

The key rule is:

- transcript stores what the model actually saw
- transcript does not depend on later code to re-derive those same strings

### 6.2 Tool Result Files

Tool-result files are written once and then treated as immutable content-addressed-by-identity storage.

For this design, identity is:

- `session_id`
- `tool_call_id`
- `field_name`

Write behavior:

- create session-local directory with recursive mkdir
- write target file only if absent
- never rewrite the same materialized field during later turns
- use direct exclusive create/write in the target path, not shared temp-file rename
- treat "already exists" as "already materialized for this tool call", not as an error

Because `session_id + tool_call_id + field_name` is unique, the final design does not need a shared temp-file naming scheme for tool-result persistence.

### 6.3 SQLite Projection Database

SQLite is introduced as a projection store, not a truth source.

Recommended path:

- `.embedagent/memory/projections.sqlite3`

Recommended schema baseline:

```sql
CREATE TABLE schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE session_projection (
  session_id TEXT PRIMARY KEY,
  updated_at TEXT NOT NULL,
  current_mode TEXT NOT NULL,
  turn_count INTEGER NOT NULL,
  message_count INTEGER NOT NULL,
  last_transition_reason TEXT,
  last_transition_message TEXT,
  summary_text TEXT
);

CREATE TABLE tool_result_projection (
  session_id TEXT NOT NULL,
  tool_call_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  field_name TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  preview_text TEXT NOT NULL,
  byte_count INTEGER NOT NULL,
  line_count INTEGER,
  content_kind TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (session_id, tool_call_id, field_name)
);

CREATE TABLE project_memory_recipe (
  key TEXT PRIMARY KEY,
  tool_name TEXT NOT NULL,
  command TEXT NOT NULL,
  cwd TEXT NOT NULL,
  last_mode TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_success_at TEXT NOT NULL,
  success_count INTEGER NOT NULL
);

CREATE TABLE project_memory_issue (
  key TEXT PRIMARY KEY,
  tool_name TEXT NOT NULL,
  mode_name TEXT NOT NULL,
  path TEXT,
  command TEXT,
  summary TEXT NOT NULL,
  status TEXT NOT NULL,
  count INTEGER NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  stored_refs_json TEXT NOT NULL
);
```

Notes:

- `content_replacement` remains transcript truth, not a SQLite truth table
- SQLite caches the latest browse/search view of materialized outputs
- project-memory tables replace the current mutable JSON projection files as canonical derived storage

## 7. Runtime Data Flow

### 7.1 Execution Layer

The execution layer does only tool work.

It returns `RawObservation`:

- primary tool outcome
- raw structured fields
- no materialized file paths
- no projection writes
- no summary/project-memory refresh

Parallel tool execution remains allowed here.

### 7.2 Commit Layer

The commit layer is the only shared-state writer.

It receives:

- `Action`
- `RawObservation`
- current `Session`
- current `ContextAssemblyResult`

It performs, in order:

1. sanitize raw payload
2. decide which fields stay inline and which become stored files
3. materialize large fields to session-local `tool-results/`
4. build exact replacement text shown to the model
5. append transcript `tool_result`
6. append transcript `content_replacement` when applicable
7. update in-memory `Session`
8. schedule or apply projection refresh

Only this layer is allowed to write:

- transcript
- tool-result files
- SQLite projections

Operational rule:

- the commit layer is protected by one process-local single-writer lock
- transcript append, tool-result materialization, in-memory session mutation, and SQLite projection refresh all happen under that writer boundary
- SQLite must not be relied on as a cross-thread locking primitive

### 7.3 Projection Refresh

Projection refresh runs after truth is committed.

Projection refresh updates:

- `session_projection`
- `tool_result_projection`
- project-memory read models
- optional `summary.json` export

Projection refresh is best-effort:

- log failure
- keep committed truth
- do not convert tool success into tool failure

## 8. Replacement Semantics

### 8.1 Why Replacement Text Must Be Persisted

Stored file paths alone are not enough.

Replacement output depends on:

- preview formatting
- preview size
- path rendering
- wording around truncation or storage

If these are re-derived on resume, prompt bytes can drift and behavior can change.

Therefore transcript must record the exact replacement string the model saw.

### 8.2 Replacement Event Shape

Recommended payload:

```json
{
  "type": "content_replacement",
  "payload": {
    "message_id": "m-123",
    "tool_call_id": "call-123",
    "tool_name": "read_file",
    "replacements": [
      {
        "field_name": "content",
        "replacement_text": "Tool result replaced: read_file src/demo.c -> .embedagent/memory/sessions/abc/tool-results/call-123/content.txt",
        "stored_path": ".embedagent/memory/sessions/abc/tool-results/call-123/content.txt"
      }
    ]
  }
}
```

Resume and context assembly use this payload directly instead of regenerating replacement text.

### 8.3 Context Assembly Rule

`ContextManager` must consume persisted `content_replacement` records as authoritative replacement text.

It must not:

- regenerate replacement strings from `stored_path`
- infer replacement text from current preview rules
- rely on suffix scans such as `*_artifact_ref` to reconstruct what the model saw

Committed observation fields such as `content_stored_path` are for browse/readback and diagnostics. They are not the prompt-truth source.

## 9. Concurrency Model

### 9.1 New Meaning Of Concurrency Safety

Current `read_only + concurrency_safe` is too weak because it ignores commit-time side effects.

The new model distinguishes:

- `execution_safe_for_parallelism`
- `requires_serial_commit`

In practice:

- many tools remain execution-parallel
- all committed observations are still serialized through one writer

### 9.2 No Shared Mutable JSON Files

The final architecture must remove runtime dependence on:

- `artifacts/index.json`
- fixed-name shared temp files such as `index.json.tmp`
- cross-thread read-modify-write JSON index updates

This is the same class of design choice that Claude Code uses: append-only transcript plus per-result unique file persistence, instead of a shared mutable artifact index.

## 10. SQLite Responsibilities

SQLite is responsible for:

- fast artifact-style listing for UI
- recent session listing
- cleanup candidate discovery
- project-memory recipes and issues
- projection rebuild checkpoints if needed later

SQLite is not responsible for:

- truth-layer session replay
- primary tool success semantics
- storing the only copy of large tool outputs

## 11. Cleanup Model

Cleanup uses SQLite as the current projection index and transcript as fallback truth.

Rules:

- delete only session-local tool-result files that are no longer referenced by current transcript-derived replacement state
- prefer whole-session cleanup over per-file garbage collection when a session is fully aged out
- projection rebuild must be able to repopulate SQLite from transcript plus surviving session files

Because old sessions are discarded, there is no need for a mixed-format cleanup policy.

## 12. Hard Cutover Scope

This design explicitly removes the following runtime contracts:

- `ArtifactStore.index.json` as a truth-bearing structure
- tool-time artifact writes from `ToolContext.shrink_observation()`
- summary-based resume fallback
- old `*_artifact_ref` semantics as the long-term truth contract

Replacement fields should move to new names such as:

- `content_stored_path`
- `stdout_stored_path`
- `stderr_stored_path`
- `diagnostics_stored_path`

The user-facing "Artifacts" inspector label may remain unchanged if desired, but its backend source must come from SQLite projection data, not the legacy store.

## 13. Files And Components To Change

New components:

- `src/embedagent/tool_commit.py`
- `src/embedagent/tool_result_store.py`
- `src/embedagent/projection_db.py`
- `src/embedagent/persistence_sanitize.py`

Primary changed components:

- [`src/embedagent/query_engine.py`](/D:/Claude-project/ccode-win7/src/embedagent/query_engine.py)
- [`src/embedagent/tools/_base.py`](/D:/Claude-project/ccode-win7/src/embedagent/tools/_base.py)
- [`src/embedagent/session.py`](/D:/Claude-project/ccode-win7/src/embedagent/session.py)
- [`src/embedagent/transcript_store.py`](/D:/Claude-project/ccode-win7/src/embedagent/transcript_store.py)
- [`src/embedagent/session_restore.py`](/D:/Claude-project/ccode-win7/src/embedagent/session_restore.py)
- [`src/embedagent/session_store.py`](/D:/Claude-project/ccode-win7/src/embedagent/session_store.py)
- [`src/embedagent/project_memory.py`](/D:/Claude-project/ccode-win7/src/embedagent/project_memory.py)
- [`src/embedagent/memory_maintenance.py`](/D:/Claude-project/ccode-win7/src/embedagent/memory_maintenance.py)
- [`src/embedagent/inprocess_adapter.py`](/D:/Claude-project/ccode-win7/src/embedagent/inprocess_adapter.py)

Additional explicit requirements for changed components:

- `src/embedagent/inprocess_adapter.py`
  - `list_artifacts()` and `read_artifact()` must switch to SQLite-backed projections
  - user-facing response shape may stay stable, but backend truth must not depend on `ArtifactStore`
  - transcript-missing resume must be a hard error; no summary-based degraded replay remains

- `src/embedagent/context.py`
  - all prompt-facing replacement semantics must move to transcript-persisted `content_replacement`
  - suffix-based legacy artifact scanning must be removed from the merged final state

- `src/embedagent/project_memory.py` and `src/embedagent/session_store.py`
  - become projection writers/readers over SQLite plus optional exported JSON
  - no longer own canonical mutable JSON indexes in the runtime hot path

Legacy runtime path to delete:

- [`src/embedagent/artifacts.py`](/D:/Claude-project/ccode-win7/src/embedagent/artifacts.py)

The file may be removed entirely or reduced to a narrow compatibility shim during branch-local development, but the merged final state must not keep it as a live truth dependency.

## 14. Implementation Strategy

This is not a staged compatibility rollout.

The implementation strategy is:

- develop the new path on a dedicated cutover branch
- keep the old path only as branch-local scaffolding while the new path is incomplete
- remove old runtime entry points before merge
- merge only when the final architecture is end-to-end functional

Main branch must not carry both truth models at once.

## 15. Tests

Required regression coverage:

1. parallel `read_file` and `search_text` no longer race on shared storage
2. tool success survives projection DB failure
3. replacement text is replay-stable across resume
4. deleting SQLite and rebuilding projections from transcript succeeds
5. deleting `summary.json` does not affect resume
6. cleanup does not remove live stored tool-result files
7. multiple large fields from the same tool call are materialized deterministically
8. Windows directory creation and first-write semantics remain race-safe

Existing test targets to extend:

- [`tests/test_query_engine_refactor.py`](/D:/Claude-project/ccode-win7/tests/test_query_engine_refactor.py)
- [`tests/test_inprocess_adapter_frontend_api.py`](/D:/Claude-project/ccode-win7/tests/test_inprocess_adapter_frontend_api.py)

New focused tests expected:

- `tests/test_tool_commit.py`
- `tests/test_projection_db.py`
- `tests/test_tool_result_store.py`

## 16. Acceptance Criteria

This cutover is complete when all of the following are true:

- parallel tool execution no longer depends on a shared mutable artifact index
- transcript plus session-local tool-result files are sufficient to resume
- exact replacement text is restored from transcript without recomputation drift
- SQLite can be deleted and rebuilt from truth data
- projection failure does not cause primary tool failure
- old session resume paths are gone
- old-format sessions are explicitly rejected instead of degraded into a synthetic empty resume
- old artifact-index hot path is gone

## 17. Non-Goals

This cutover does not include:

- migration of existing old-format sessions
- remote transcript unification
- full multi-agent persistence redesign
- replacing transcript storage with SQLite

Transcript remains append-only JSONL truth. SQLite is projection-only.

## 18. Decision

EmbedAgent will perform a hard architectural cutover to transcript-truth tool-result persistence.

The final design uses:

- append-only transcript truth
- session-local immutable tool-result files
- single-writer commit semantics
- SQLite-backed projection metadata
- no old session compatibility
