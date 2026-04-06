# Agent Harness V2

## 1. Status

This document is now the official architecture baseline, not a future design draft.

Agent Harness is the promoted execution model for EmbedAgent.

## 2. Core Ideas

Harness exists to balance:

- task focus for weaker/offline models
- enough flexibility for real project work
- explicit workflow discipline
- deterministic tool access

It does that by separating three concerns:

- user-visible `mode`
- internal `discipline_profile`
- internal `execution_phase`

## 3. Official Modes

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

## 4. Discipline Profiles

Current harness supports:

- `lite_spec_tdd`
- `full_spec_tdd`

`build` and `debug` may operate in either profile depending on workflow state and harness context.

## 5. Phase Model

Representative phase tracks:

### Build

- `understand`
- `contract`
- `implement`
- `check`
- `handoff`

Full profile may insert:

- `test_design`
- `repair`

### Debug

- `reproduce`
- `isolate`
- `patch`
- `regression_check`
- `handoff`

### Verify

- `select_recipe`
- `execute`
- `summarize`

## 6. Task Truth

The official task system is:

- `TaskGraph`
- projected into `task_status`
- persisted as session task snapshots

Frontends consume:

- `task_summary`
- `task_items`

The old prompt-only todo flow is no longer the architecture baseline.

## 7. Tool Packs

Harness exposes focused packs instead of an undifferentiated tool wall.

Main pack families:

- discovery/file tools
- recipe/build/verify tools
- task/interaction tools

This keeps model tool selection tight without hard mode walls becoming unusable.

## 8. Prompting Model

Prompt construction is layered through harness prompt units, not only through monolithic mode prompts.

The important result is:

- modes stay understandable
- tool focus stays narrow
- task state is surfaced explicitly

## 9. Permission / Context Relationship

Harness does not replace permission or context systems.

- Harness decides workflow focus
- Permission decides whether an action is allowed/ask/deny
- Context decides what prior information is preserved and surfaced

These are cooperating subsystems, not one overloaded prompt.

## 10. Frontend Projection

The official frontend vocabulary for harness state is:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

GUI and TUI should treat these as the stable shell-facing summary of harness state.

## 11. Design Rule

Do not reintroduce long-lived parallel V1/V2 paths.

When harness changes:

- promote the new path into the official runtime/frontends
- then delete the old path or archive its documentation
