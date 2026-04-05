# GUI Timeline Event Anchors Design

## Background

The GUI timeline currently mixes several event transport paths:

- live reducer updates from WebSocket callback messages
- session event log replay for active sessions
- structured timeline bootstrap from `/api/sessions/{id}/timeline`
- snapshot-derived pending interaction state

These paths do not share a single event-anchor contract. Several GUI-visible events either lose `turn_id` / `step_id` / `step_index`, or only recover them on one path. As a result:

- `context_compacted` cards stack as detached session-level groups
- slash/workflow `command_result` cards drift or fall back to session-bottom rendering
- `session_error` cards bind to the wrong turn after replay
- permission and user-input interactions show inconsistent context between Timeline, Inspector, and snapshot state

## Goals

1. Establish `turn_id` / `step_id` / `step_index` as a stable end-to-end event-anchor contract.
2. Treat slash/workflow commands as first-class user turns in the timeline model.
3. Make live updates, raw event replay, and structured timeline bootstrap project the same semantics.
4. Eliminate permission/user-input context drift between event log, snapshot, and Inspector.
5. Reduce noisy `context_compacted` cards so compaction notifications represent real compaction.

## Non-Goals

- No redesign of the visible timeline layout.
- No new mode system behavior.
- No broad rewrite of the GUI transport architecture beyond what is required to unify anchors.

## Design

### 1. Unified Event Anchor Contract

The following protocol/dataclass payloads must carry anchor fields directly:

- `CommandResult`
- `PermissionRequest`
- `UserInputRequest`
- GUI `Message` metadata for `ERROR` and `CONTEXT_COMPACTED`
- pending interaction/session snapshot serialization

For interaction requests, `session_id` should also be preserved so snapshot and callback representations remain equivalent.

### 2. Slash/Workflow Commands Become Formal Turns

`submit_user_message()` generates a `turn_id` before slash-command dispatch when the input is a slash/workflow command.

Behavior:

- handled slash command without continuation:
  - emit `turn_start`
  - emit command/tool/interaction events anchored to that `turn_id`
  - emit `turn_end`
- slash command with `continue_with_text`:
  - reuse the pre-generated `turn_id`
  - command-side events and the subsequent agent turn share the same turn anchor
  - `_run_turn_v2()` must accept an injected `turn_id` and skip duplicate `turn_start`

This keeps command output, command-triggered tools, command-triggered permission prompts, and follow-up agent steps inside one turn lifecycle.

### 3. Turn-Level Events Are First-Class

Not all anchored events should be forced into a step.

We explicitly model the following as turn-level events:

- `command_result`
- `context_compacted`
- `session_error`
- command-side `tool_started` / `tool_finished`
- turn-level `permission_required` / `user_input_required`

These events carry `turn_id` and may leave `step_id` empty.

### 4. Structured Timeline Must Preserve Turn-Level Events

`build_structured_timeline()` must preserve both:

- step-level tool/activity data
- turn-level transitions and turn-level tool calls

In step-aware sessions:

- turn-level events must no longer be dropped when `current_step is None`
- `turn.transitions` must include `command_result`, `context_compacted`, `session_error`, `permission_required`, and `user_input_required`
- `turn.tool_calls` must include command-side tool activity with no step anchor

`timelineFromTurns()` must project these turn-level records back into flat timeline items so initial page load matches live rendering.

### 5. Interaction Consistency

Permission and user-input tickets must store:

- `turn_id`
- `step_id`
- `step_index`

This data must be preserved in:

- callback payloads
- pending ticket dictionaries
- `_pending_interaction_payload()`
- session snapshot serialization
- frontend local `interaction.created` append path

The frontend may still merge local interaction events with backend event-log replay, but both paths must now be structurally identical and dedupe by `interaction_id`.

### 6. Real Compaction Only

`ContextBuildResult.compacted` should no longer flip to `True` solely because old turns exist.

The normal summary window is not itself a GUI-worthy compaction event. `context_compacted` should only be emitted when there is actual compaction impact, such as:

- reduced tool-message replacement
- character count reduction
- hard trim / forced compact path

## Implementation Notes

- Keep backward-compatible fallback behavior in reducers where practical, but make backend anchors authoritative.
- Avoid inventing synthetic steps for command results and system cards.
- Prefer small helper changes over ad hoc field injection at every call site.

## Testing Strategy

Add regression coverage for:

1. protocol/dataclass anchor fields
2. callback bridge metadata propagation
3. slash command turn lifecycle and anchored command results
4. anchored command-side tool and permission events
5. raw event replay for `command_result` / `context_compacted` / `session_error`
6. structured timeline projection of turn-level transitions and tool calls
7. frontend reducer preservation of explicit anchors
8. reduced `context_compacted` emission frequency

## Risks And Mitigations

- Risk: command turns emit duplicate user-start records.
  - Mitigation: `_run_turn_v2()` accepts injected `turn_id` and optional `emit_turn_start=False`.

- Risk: live and reload paths still diverge after field propagation.
  - Mitigation: make `timelineFromTurns()` consume `turn.transitions` and `turn.tool_calls`, not only `steps`.

- Risk: permission/user-input snapshot and live event log drift again.
  - Mitigation: store anchor fields inside tickets and serialize them everywhere from the same ticket object.
