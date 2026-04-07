# Overall Solution Architecture

## 1. Scope

EmbedAgent is a native, offline-first Agent IDE core for C/C++ engineering.

The stable architecture assumptions are:

- Windows 7 compatibility
- Python 3.8 runtime target
- Offline bundle delivery
- Agent Core first, UI shells replaceable
- Clang-centered toolchain

## 2. Top-Level Structure

The product is organized around one main execution spine:

`Frontend -> Core Adapter -> InProcessAdapter -> QueryEngine -> Harness -> ToolRuntime -> Permission/Context/Stores`

### Frontend Layer

- `src/embedagent/frontend/tui/`
- `src/embedagent/frontend/gui/`

These are shells only. They do not own workflow semantics.

### Protocol / Core Layer

- `src/embedagent/protocol/`
- `src/embedagent/core/`

This is the stable contract boundary between UI and Agent Core.

### Agent Core Layer

- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/query_engine.py`
- `src/embedagent/session_history.py`
- `src/embedagent/harness/`
- `src/embedagent/tools/`
- `src/embedagent/context.py`
- `src/embedagent/permissions.py`

This is the product core.

## 3. Official Execution Model

The repository now uses one official execution model:

- user-visible `mode`
- internal `discipline_profile`
- internal `execution_phase`
- `TaskGraph` as workflow truth

### Official Modes

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`build` is the only implementation mode.

### Official Task Model

The task system is no longer prompt-only.

Official task truth flows through:

- `TaskGraph`
- `task_status`
- session task snapshots

Session snapshots carry:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

## 4. Tool Architecture

The tool runtime has one official facade:

- `src/embedagent/tools/runtime.py`

Harness selects focused tool packs by mode/phase, but execution still flows through one runtime object.

### Official Tool Families

#### File / Discovery

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`

#### Build / Verify

- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `record_failing_evidence`

#### Workflow / Interaction

- `task_status`
- `ask_user`

#### Supporting Capabilities

- `git_status`
- `git_diff`
- `git_log`
- `run_command` as controlled fallback

## 5. Harness Layer

`src/embedagent/harness/` owns:

- mode registry
- discipline defaults
- phase advancement rules
- prompt unit construction
- task graph construction
- session task snapshot persistence

This keeps workflow structure out of the frontend and out of ad-hoc prompt text.

## 6. Permission Layer

`src/embedagent/permissions.py` is the only official permission engine.

It owns:

- action category mapping
- rule loading
- rule matching
- stable explanation text
- frontend-visible permission context

The frontend should never infer permission policy from mode alone.

## 7. Context Layer

`src/embedagent/context.py` and `src/embedagent/workspace_intelligence.py` own:

- context budgets
- reducer registry
- tool-result replacement
- summary assembly
- workspace intelligence evidence

The context system is aligned to the official harness vocabulary, especially:

- `build`
- `list_dir`
- `glob_files`
- `grep_text`
- `run_recipe`
- `report_quality_v2`
- `task_status`

## 8. Session / Transcript Truth

Session truth is distributed across:

- live `Session`
- transcript events
- `SessionHistoryAssembler` projections
- tool result storage/projections
- summary store
- task snapshots

No frontend should maintain its own workflow truth separate from session snapshots and replayable events.

### Session History Rule

Official session-history ownership is:

- `transcript.jsonl` is the only durable session-history ledger
- `Session` / `session.turns` is the only live structured history state
- `timeline.jsonl` is replay transport only
- GUI activation reads one bootstrap payload that includes snapshot, structured history, plan, permission context, and replay metadata

Historical turns must never be rebuilt from replay-log tails.

## 9. Frontend Contract

The frontend-facing vocabulary is now:

- `build`, not `code`
- `tasks`, not `todos`
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

If a frontend change introduces older terms back into the product shell, that is an architectural regression.

## 10. Bundling Model

The shipped product is expected to be a self-contained offline bundle.

The architecture therefore assumes runtime discovery for bundled tools, not global machine dependencies.

## 11. Design Rule

Do not reintroduce parallel V1/V2 execution paths.

When changing architecture:

- promote the new path to the only official path
- then delete or archive the old path
- keep current docs describing only the official architecture
