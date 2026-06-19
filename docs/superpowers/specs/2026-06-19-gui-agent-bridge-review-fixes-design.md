# GUI Agent Bridge Review Fixes Design

## Goal

Close the GUI-to-Agent bridge issues found in the review without expanding GUI authority into Agent Core.

## Scope

- Preserve Agent Core as the owner of session truth, transcript history, workflow state, tool execution, and permission policy.
- Keep GUI app-shell state display-only unless a route is explicitly documented as app-shell owned.
- Fix only the reviewed bridge gaps:
  - GUI session snapshot serialization drops protocol diagnostic fields.
  - Direct GUI file write endpoint exposes workspace mutation before an editor/manual-edit contract exists.
  - Legacy WebSocket permission response can remember a permission category against the wrong active session.

## Design

### Snapshot Serialization

`GUIBackend._serialize_session_snapshot()` should forward the diagnostic/read-model fields already present on `SessionSnapshot` and produced by `AgentCoreAdapter`: context diagnostics, transition diagnostics, operation/runtime reducer projections, compaction state, recovery state, and timeline restore counts. The frontend may display or normalize these fields, but must not use them as execution policy.

### Direct File Write Endpoint

The current React app reads files through `GET /api/files/{path}` and does not use `POST /api/files/{path}`. Until a T3-style file editor mutation slice defines a manual edit contract, the write route should reject requests with HTTP 405. This keeps direct GUI mutation out of the product surface while preserving read-only preview behavior.

### Legacy WebSocket Permission Memory

The unified HTTP interaction response remains the primary permission/user-input path. The legacy WebSocket `permission_response` handler may still resolve a pending waiter, but it should only persist remembered categories when the payload includes a `session_id` that matches the backend's current session id. Missing or mismatched session ids must not mutate remembered permission state.

## Testing

- Add GUI backend tests that fail before implementation:
  - session bootstrap preserves diagnostic snapshot fields through the backend serializer;
  - direct file write route returns 405 and does not call core write;
  - legacy WebSocket permission response does not remember without a matching session id, and does remember with a matching session id.
- Run focused GUI backend/runtime tests plus frontend helper tests.

## Boundaries

No changes to Agent Core execution, `PermissionPolicy`, transcript reducers, workflow packages, provider configuration, source-control mutation, terminal persistence, extension loading, or offline runtime dependencies.
