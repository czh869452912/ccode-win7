# Pi-Style Local Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workspace-local skills first-class, Pi-inspired resources with safe metadata, model-visible listings, explicit `/skill:name` invocation, and authoring templates.

**Architecture:** Keep skills as offline workspace file resources under `.embedagent/skills`; do not execute skill code or load dependencies. Add a small `embedagent.skills` module for frontmatter parsing, discovery metadata, prompt formatting, and explicit invocation expansion, then wire it through existing resource discovery, system prompt creation, and slash command dispatch.

**Tech Stack:** Python 3.8 standard library, existing `ToolRuntime`, `InProcessAdapter`, `QueryEngine`, and `Session` boundaries.

---

### Task 1: First-Class Skill Resource Metadata

**Files:**
- Create: `src/embedagent/skills.py`
- Modify: `src/embedagent/local_resources.py`
- Test: `tests/test_local_resources.py`

- [ ] **Step 1: Write the failing tests**

Add tests that create `.embedagent/skills/review/SKILL.md` with Agent Skills frontmatter and assert discovery returns `name`, `description`, `base_dir`, `disable_model_invocation`, and `prompt_visible`. Add a second hidden skill with `disable-model-invocation: true` and assert it remains a resource but is omitted by `format_skills_for_prompt`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_local_resources.py::TestLocalResources::test_discovers_pi_style_skill_frontmatter -v`

Expected: FAIL because `embedagent.skills` does not exist or discovered skills lack metadata.

- [ ] **Step 3: Implement minimal parser and formatter**

Create `embedagent.skills` with:
- `parse_skill_document(text)` returning `(metadata, body)`.
- `discover_skill_resources(workspace, roots, diagnostics)` scanning Pi-style `SKILL.md` directories plus legacy `.md`/`.txt` files.
- `format_skills_for_prompt(skills)` listing only prompt-visible skills in XML-like blocks.

- [ ] **Step 4: Wire discovery**

Update `discover_local_resources` to use `discover_skill_resources` for skills while preserving existing counts and legacy file support.

- [ ] **Step 5: Run tests to verify green**

Run: `uv run pytest tests/test_local_resources.py::TestLocalResources::test_discovers_pi_style_skill_frontmatter tests/test_local_resources.py::TestLocalResources::test_discovers_default_skill_prompt_and_recipe_files -v`

Expected: PASS.

### Task 2: Skill Authoring Template

**Files:**
- Modify: `src/embedagent/self_extension_authoring.py`
- Test: `tests/test_self_extension_authoring.py`

- [ ] **Step 1: Write the failing test**

Extend authoring tests to assert generated skill files start with Agent Skills frontmatter including `name`, `description`, and `disable-model-invocation: false`, and that resource reload sees the description.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_self_extension_authoring.py::test_authors_skill_prompt_recipe_and_disabled_extension -v`

Expected: FAIL because the generated skill currently has no frontmatter.

- [ ] **Step 3: Implement template update**

Change `_write_skill` to emit frontmatter before the existing Markdown body. Keep paths and overwrite semantics unchanged.

- [ ] **Step 4: Run test to verify green**

Run: `uv run pytest tests/test_self_extension_authoring.py::test_authors_skill_prompt_recipe_and_disabled_extension -v`

Expected: PASS.

### Task 3: Explicit `/skill:name` Invocation

**Files:**
- Modify: `src/embedagent/skills.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_local_resources.py`

- [ ] **Step 1: Write the failing tests**

Add a pure function test that expands `/skill:review focus on ownership` into a `<skill name="review" location="...">` block containing the skill body plus the user arguments. Add an adapter test that submits `/skill:review focus on ownership` and verifies the model receives a user message containing the skill block rather than a command error.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_local_resources.py::TestLocalResources::test_expand_skill_invocation_includes_body_and_arguments tests/test_local_resources.py::TestLocalResources::test_slash_skill_command_continues_as_user_turn -v`

Expected: FAIL because expansion and adapter routing are missing.

- [ ] **Step 3: Implement expansion**

Add `expand_skill_invocation(text, resources, workspace)` to `embedagent.skills`. It should support names from `/skill:<name>`, read only workspace-bound skill files, strip frontmatter, and return `(expanded_text, error_message)`.

- [ ] **Step 4: Wire adapter routing**

In `InProcessAdapter._dispatch_input`, recognize parsed names starting with `skill:` before static command lookup. On success, return `{"handled": True, "continue_with_text": expanded_text}`. On failure, emit a `command_result` for the skill command and stop.

- [ ] **Step 5: Run tests to verify green**

Run: `uv run pytest tests/test_local_resources.py::TestLocalResources::test_expand_skill_invocation_includes_body_and_arguments tests/test_local_resources.py::TestLocalResources::test_slash_skill_command_continues_as_user_turn -v`

Expected: PASS.

### Task 4: Prompt Listing Injection

**Files:**
- Modify: `src/embedagent/modes.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/session_store.py`
- Test: `tests/test_local_resources.py`

- [ ] **Step 1: Write the failing tests**

Add a QueryEngine test that initializes a session with one visible and one hidden skill and asserts the system prompt includes `<available_skills>` plus the visible skill name/description/location, and excludes the hidden skill.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_local_resources.py::TestLocalResources::test_query_engine_system_prompt_lists_visible_skills -v`

Expected: FAIL because system prompts do not include local skills.

- [ ] **Step 3: Implement prompt extension**

Add optional `local_resources=None` to `build_system_prompt` and append `format_skills_for_prompt(local_resources["skills"])` when present. Add a QueryEngine helper that passes `self.tools.local_resources()` to `build_system_prompt` at session init and mode-switch points.

- [ ] **Step 4: Run focused tests to verify green**

Run: `uv run pytest tests/test_local_resources.py -v`

Expected: PASS.

### Task 5: Regression Verification

**Files:**
- No additional implementation files.

- [ ] **Step 1: Run focused behavior tests**

Run: `uv run pytest tests/test_local_resources.py tests/test_self_extension_authoring.py tests/test_capability_registry.py -v`

Expected: PASS.

- [ ] **Step 2: Run fast subset**

Run: `uv run pytest tests/ -m "not slow and not gui" -v`

Expected: PASS or report existing unrelated failures with exact failing tests.
