# Remaining Pi Architecture Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Pi-inspired architecture gaps without weakening the offline, Windows 7, Python 3.8, or default C/C++ workflow constraints.

**Architecture:** Treat each gap as an independently testable slice. Keep Agent Core generic, keep the bundled C/C++ workflow behind the extension/package boundary, keep skills as file resources rather than executable code, and move durable/prompt-visible state toward reducer-backed read models.

**Tech Stack:** Python 3.8 standard library, existing `QueryEngine`, `InProcessAdapter`, `ExtensionManager`, `ToolRuntime`, transcript reducers, and pytest/ruff verification.

---

## Scope Check

This is not one implementation task. It is a four-slice architecture program:

1. Workflow-neutral core naming and prompt-message boundary.
2. Pi-compatible local skill discovery ignore semantics.
3. Internal skill read model to unify prompt listing, command projection, and explicit invocation.
4. Prompt-unit snapshot discipline and reducer-safe diagnostics.

Each slice should be implemented and committed separately. The first three slices are near-term; the fourth is architectural hardening and can follow after the system is stable.

## Slice 1: Workflow-Neutral Core Prompt Boundary

**Purpose:** Remove remaining harness-shaped names from Agent Core internals while preserving hosted C/C++ behavior and legacy transcript compatibility.

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/design-change-log.md`

**Current Gap:**
- `QueryEngine._should_inject_harness`
- `QueryEngine._append_harness_messages`
- local variables such as `harness_prompt`
- system message kind `harness_prompt`

These names make the generic core still look harness-owned even though behavior already flows through `AgentExtensionHost`.

**Target Shape:**
- Rename private core helpers to workflow-neutral names:
  - `_should_inject_workflow_prompt`
  - `_append_workflow_prompt_messages`
- New prompt messages use `kind="workflow_prompt"`.
- Dedupe remains compatible with existing `kind="harness_prompt"` transcript/session messages.
- Metadata should include a generic package/source identity when available, for example `package_id` or `source_id`, while preserving existing C/C++ metadata fields.

**TDD Tasks:**

- [ ] **Step 1: Write failing tests for new workflow prompt kind**

Add to `tests/test_workflow_extensions.py`:

```python
def test_c_harness_extension_uses_generic_workflow_prompt_kind(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.extensions import ExtensionManager
    from embedagent.query_engine import QueryEngine
    from embedagent.session import AssistantReply
    from embedagent.tools import ToolRuntime

    class Client(object):
        def generate(self, messages, tools=None):
            return AssistantReply(content="ok", actions=[], finish_reason="stop")
        def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
            reply = self.generate(messages, tools=tools)
            if on_text_delta is not None:
                on_text_delta(reply.content)
            return reply

    manager = ExtensionManager()
    for extension in build_default_extension_set(str(tmp_path)):
        manager.register(extension)
    engine = QueryEngine(Client(), ToolRuntime(str(tmp_path)), extension_manager=manager)
    result = engine.submit_user_turn("build it", stream=False, initial_mode="build")

    prompt_kinds = [message.kind for message in result.session.messages if message.role == "system"]
    assert "workflow_prompt" in prompt_kinds
    assert "harness_prompt" not in prompt_kinds
```

- [ ] **Step 2: Write failing compatibility test for legacy dedupe**

Add to `tests/test_query_engine_refactor.py`:

```python
def test_workflow_prompt_dedupe_accepts_legacy_harness_prompt_kind(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.extensions import ExtensionManager
    from embedagent.query_engine import QueryEngine
    from embedagent.session import AssistantReply, Session
    from embedagent.tools import ToolRuntime

    class Client(object):
        def generate(self, messages, tools=None):
            return AssistantReply(content="ok", actions=[], finish_reason="stop")
        def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
            return self.generate(messages, tools=tools)

    manager = ExtensionManager()
    for extension in build_default_extension_set(str(tmp_path)):
        manager.register(extension)
    session = Session()
    session.add_system_message(
        "legacy prompt",
        kind="harness_prompt",
        metadata={"mode_name": "build", "discipline_label": "lite_spec_tdd"},
    )

    engine = QueryEngine(Client(), ToolRuntime(str(tmp_path)), extension_manager=manager)
    engine.submit_user_turn("build it", stream=False, initial_mode="build", session=session)

    prompt_messages = [
        message for message in session.messages
        if message.kind in ("harness_prompt", "workflow_prompt")
    ]
    assert len(prompt_messages) == 1
```

- [ ] **Step 3: Run red tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_c_harness_extension_uses_generic_workflow_prompt_kind tests/test_query_engine_refactor.py::test_workflow_prompt_dedupe_accepts_legacy_harness_prompt_kind -v --basetemp build/pytest-tmp
```

Expected: first test fails because messages still use `harness_prompt`.

- [ ] **Step 4: Implement generic prompt boundary**

In `src/embedagent/query_engine.py`:
- Rename private helper methods and local variables.
- Use `kind="workflow_prompt"` for newly appended workflow prompt messages.
- Dedupe over both `workflow_prompt` and legacy `harness_prompt`.
- Keep C/C++ prompt content and activation unchanged.

- [ ] **Step 5: Update docs and tests**

Update docs to state that `harness_prompt` is legacy transcript compatibility and `workflow_prompt` is the current internal message kind.

- [ ] **Step 6: Verify slice**

Run:

```bash
uv run ruff check src/embedagent/query_engine.py tests/test_query_engine_refactor.py tests/test_workflow_extensions.py
uv run pytest tests/test_query_engine_refactor.py tests/test_workflow_extensions.py -q --basetemp build/pytest-tmp
```

Expected: all selected tests pass.

## Slice 2: Pi-Compatible Skill Discovery Ignore Rules

**Purpose:** Bring local skill discovery closer to Pi while staying offline and dependency-free.

**Files:**
- Modify: `src/embedagent/skills.py`
- Modify: `tests/test_local_resources.py`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/design-change-log.md`

**Current Gap:**
- Skill discovery does not honor `.gitignore`, `.ignore`, or `.fdignore`.

**Target Shape:**
- Honor ignore files while scanning `.embedagent/skills`.
- Support a minimal standard-library ignore subset:
  - blank lines and `#` comments
  - exact relative path rules
  - directory rules ending in `/`
  - glob rules using `fnmatch`
  - negation rules beginning with `!`
- Keep workspace-bound path checks.
- Do not add dependencies.

**TDD Tasks:**

- [ ] **Step 1: Write failing ignore tests**

Add to `tests/test_local_resources.py`:

```python
def test_skill_discovery_honors_ignore_files(self):
    from embedagent.local_resources import discover_local_resources

    _write_text(os.path.join(self.workspace, ".embedagent", "skills", ".gitignore"), "ignored/\n*.tmp.md\n")
    _write_text(
        os.path.join(self.workspace, ".embedagent", "skills", "visible", "SKILL.md"),
        "---\nname: visible-skill\ndescription: Visible skill.\n---\n# Visible\n",
    )
    _write_text(
        os.path.join(self.workspace, ".embedagent", "skills", "ignored", "SKILL.md"),
        "---\nname: ignored-skill\ndescription: Ignored skill.\n---\n# Ignored\n",
    )
    _write_text(
        os.path.join(self.workspace, ".embedagent", "skills", "draft.tmp.md"),
        "---\nname: draft-skill\ndescription: Draft skill.\n---\n# Draft\n",
    )

    payload = discover_local_resources(self.workspace)
    names = [item["name"] for item in payload["skills"]]

    assert names == ["visible-skill"]
```

Add a negation test:

```python
def test_skill_discovery_ignore_negation_can_reinclude_file(self):
    from embedagent.local_resources import discover_local_resources

    _write_text(os.path.join(self.workspace, ".embedagent", "skills", ".ignore"), "*.md\n!keep.md\n")
    _write_text(
        os.path.join(self.workspace, ".embedagent", "skills", "keep.md"),
        "---\nname: keep-skill\ndescription: Keep skill.\n---\n# Keep\n",
    )
    _write_text(
        os.path.join(self.workspace, ".embedagent", "skills", "drop.md"),
        "---\nname: drop-skill\ndescription: Drop skill.\n---\n# Drop\n",
    )

    payload = discover_local_resources(self.workspace)

    assert [item["name"] for item in payload["skills"]] == ["keep-skill"]
```

- [ ] **Step 2: Run red tests**

Run:

```bash
uv run pytest tests/test_local_resources.py::TestLocalResources::test_skill_discovery_honors_ignore_files tests/test_local_resources.py::TestLocalResources::test_skill_discovery_ignore_negation_can_reinclude_file -v --basetemp build/pytest-tmp
```

Expected: tests fail because ignored files are still discovered.

- [ ] **Step 3: Implement ignore matcher**

In `src/embedagent/skills.py`:
- Add `_load_ignore_rules(root)`.
- Add `_is_ignored(relative_path, is_dir, rules)`.
- Apply ignore rules during `os.walk`.
- Normalize paths to forward slashes.
- Keep `.git` and `__pycache__` exclusions.

- [ ] **Step 4: Verify slice**

Run:

```bash
uv run ruff check src/embedagent/skills.py tests/test_local_resources.py
uv run pytest tests/test_local_resources.py -q --basetemp build/pytest-tmp
```

Expected: all local resource tests pass.

## Slice 3: Internal Skill Read Model

**Purpose:** Stop scattering skill-specific projections across prompt formatting, adapter help, capability snapshots, and invocation lookup.

**Files:**
- Create: `src/embedagent/skill_index.py`
- Modify: `src/embedagent/skills.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/modes.py`
- Modify: `tests/test_local_resources.py`
- Modify: `tests/test_capability_registry.py`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/frontend-protocol.md`

**Current Gap:**
- Skill data is carried as generic resource dicts.
- Prompt listing, dynamic command listing, and explicit invocation each inspect resource dicts independently.
- This makes future behavior such as diagnostics, revision metadata, and frontend skill inspection harder to reason about.

**Target Shape:**
- Add a non-executing internal read model:
  - `SkillIndex`
  - `SkillRecord`
  - `build_skill_index(resources)`
- It exposes:
  - `visible_records()`
  - `record_by_name(name)`
  - `prompt_text()`
  - `command_specs()`
  - `safe_summary()`
- It does not execute code, reload resources, decide permissions, or activate tools.
- Keep public capability kind as `resource` for now; do not introduce a new frontend `skill` kind until a UI inspector requires it.

**TDD Tasks:**

- [ ] **Step 1: Write failing pure read-model tests**

Add to `tests/test_local_resources.py`:

```python
def test_skill_index_projects_prompt_commands_and_lookup(self):
    from embedagent.local_resources import discover_local_resources
    from embedagent.skill_index import build_skill_index

    _write_text(
        os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
        "---\nname: code-review\ndescription: Review local C changes.\n---\n# Review\n",
    )
    _write_text(
        os.path.join(self.workspace, ".embedagent", "skills", "private", "SKILL.md"),
        "---\nname: private-audit\ndescription: Hidden.\ndisable-model-invocation: true\n---\n# Private\n",
    )

    index = build_skill_index(discover_local_resources(self.workspace))

    assert [item.name for item in index.visible_records()] == ["code-review"]
    assert index.record_by_name("code-review").base_dir == ".embedagent/skills/review"
    assert index.record_by_name("private-audit").prompt_visible is False
    assert "<name>code-review</name>" in index.prompt_text()
    assert [spec.name for spec in index.command_specs()] == ["skill:code-review"]
```

- [ ] **Step 2: Run red test**

Run:

```bash
uv run pytest tests/test_local_resources.py::TestLocalResources::test_skill_index_projects_prompt_commands_and_lookup -v --basetemp build/pytest-tmp
```

Expected: fails because `embedagent.skill_index` does not exist.

- [ ] **Step 3: Implement `SkillIndex`**

Create `src/embedagent/skill_index.py` using dataclasses and plain dict inputs. Keep it Python 3.8 compatible.

- [ ] **Step 4: Refactor call sites**

Use `build_skill_index(...)` in:
- `modes.build_system_prompt`
- `InProcessAdapter._skill_command_specs`
- `InProcessAdapter._refresh_local_skills_prompt_locked`
- `skills.expand_skill_invocation`

Keep existing public helper functions as thin wrappers if needed.

- [ ] **Step 5: Verify slice**

Run:

```bash
uv run ruff check src/embedagent/skill_index.py src/embedagent/skills.py src/embedagent/inprocess_adapter.py src/embedagent/modes.py tests/test_local_resources.py
uv run pytest tests/test_local_resources.py tests/test_capability_registry.py -q --basetemp build/pytest-tmp
```

Expected: all selected tests pass.

## Slice 4: Prompt-Unit Snapshot Discipline

**Purpose:** Move local skills from ad hoc prompt text toward explicit prompt units and safe snapshot diagnostics.

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/turn_snapshot.py`
- Modify: `src/embedagent/runtime_config.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_runtime_config.py`
- Modify: `tests/test_local_resources.py`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/design-change-log.md`

**Current Gap:**
- Visible skills are injected as system prompt text.
- Provider snapshot diagnostics do not explicitly record safe prompt-unit/resource information.
- Resource reload mutates future session context, but there is no explicit prompt-unit read model in the turn snapshot metadata.

**Target Shape:**
- `TurnSnapshot` metadata records safe prompt-unit metadata:
  - prompt unit kind: `local_skill_listing`
  - resource revision if available
  - visible skill count
  - visible skill names
- It must not record full skill bodies, full prompt text, raw file contents, API keys, or tool outputs.
- In-flight provider requests continue consuming the already-built snapshot; reload affects subsequent provider requests only.

**TDD Tasks:**

- [ ] **Step 1: Write failing safe metadata test**

Add to `tests/test_query_engine_refactor.py`:

```python
def test_turn_snapshot_records_safe_local_skill_prompt_unit_metadata(tmp_path):
    from embedagent.query_engine import QueryEngine
    from embedagent.session import AssistantReply
    from embedagent.tools import ToolRuntime

    class Client(object):
        def __init__(self):
            self.messages = []
        def generate(self, messages, tools=None):
            self.messages.append(messages)
            return AssistantReply(content="ok", actions=[], finish_reason="stop")
        def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
            return self.generate(messages, tools=tools)

    skill_dir = tmp_path / ".embedagent" / "skills" / "review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: code-review\ndescription: Review local C changes.\n---\n# Secret Body\n",
        encoding="utf-8",
    )
    runtime = ToolRuntime(str(tmp_path))
    runtime.reload_resources(reason="test")
    engine = QueryEngine(Client(), runtime)
    result = engine.submit_user_turn("inspect", stream=False, initial_mode="build")

    snapshot_events = [
        event for event in engine.transcript_store.load_events(result.session.session_id)
        if event["type"] == "operation_started"
        and (event.get("payload") or {}).get("kind") == "provider_request"
    ]
    metadata = (snapshot_events[0].get("payload") or {}).get("metadata") or {}
    prompt_units = metadata["turn_snapshot"]["prompt_units"]

    assert prompt_units == [{"kind": "local_skill_listing", "visible_skill_names": ["code-review"], "visible_skill_count": 1}]
    assert "Secret Body" not in str(metadata)
```

- [ ] **Step 2: Run red test**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::test_turn_snapshot_records_safe_local_skill_prompt_unit_metadata -v --basetemp build/pytest-tmp
```

Expected: fails because snapshot metadata has no prompt unit metadata.

- [ ] **Step 3: Implement safe prompt-unit metadata**

Add a safe metadata builder close to the existing turn snapshot construction. Prefer deriving from the skill read model introduced in Slice 3.

- [ ] **Step 4: Add reload/save-point behavior test**

Add a test proving that a reload after one turn changes only the next provider request metadata and not prior provider request records.

- [ ] **Step 5: Verify slice**

Run:

```bash
uv run ruff check src/embedagent/query_engine.py src/embedagent/turn_snapshot.py src/embedagent/runtime_config.py tests/test_query_engine_refactor.py tests/test_runtime_config.py
uv run pytest tests/test_query_engine_refactor.py tests/test_runtime_config.py tests/test_local_resources.py -q --basetemp build/pytest-tmp
```

Expected: all selected tests pass.

## Recommended Order

1. **Slice 1 first** because it removes misleading core/harness vocabulary before more prompt work lands.
2. **Slice 2 next** because it is isolated, user-visible, and keeps skill discovery compatible with Pi.
3. **Slice 3 next** because it reduces duplication introduced by the first skill slice and makes future prompt-unit work cleaner.
4. **Slice 4 last** because it touches provider snapshot diagnostics and should build on the `SkillIndex`.

## Deferred Items

These should not be included in the above slices:

- Online skill/plugin registries.
- Dependency installation.
- Marketplace metadata.
- Built-in tool replacement.
- General multi-agent orchestration.
- Remote web search or browser automation.

They remain outside the product baseline because of offline deployment, Windows 7, and focused C/C++ engineering constraints.

## Verification Baseline

Each completed slice should at least run:

```bash
uv run ruff check src/ tests/
uv run pytest tests/ -m "not slow and not gui" -q --ignore=tests/test_hygn_03_warning_cleanup.py --basetemp build/pytest-tmp
```

The `test_hygn_03_warning_cleanup.py` exclusion is currently needed on this machine because that test starts a nested pytest process which does not inherit the repository-local `--basetemp`, and the default user Temp pytest directory is permission-blocked.
