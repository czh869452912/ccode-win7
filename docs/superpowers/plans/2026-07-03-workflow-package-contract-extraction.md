# Workflow Package Contract Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workflow/scenario package contracts the authoritative source for scenario-specific mode, tool, and GUI capability metadata while keeping Agent Core generic.

**Architecture:** This stage introduces a host/product scenario profile boundary that composes base modes, workflow package manifests, and tool activation without C/C++ assumptions in generic runtime paths. `ToolRuntime` remains the concrete product tool registry, but provider-facing schema projection must use explicit active tool names from `AgentExtensionHost`; old implicit mode fallback behavior is deleted rather than preserved. The default C/C++ workflow stays bundled through `src/embedagent_host/default_extensions.py`, and its package-owned `packs.py`, `tool_metadata.py`, and `package_manifest.py` remain the only source for C/C++ workflow-specific tools.

**Tech Stack:** Python 3.8 dataclasses/typing, existing pytest suite, existing JavaScript GUI capability normalizers, no new runtime dependencies, no compatibility aliases.

---

## Execution Covenant

- Do not preserve old implicit fallback paths for `ToolRuntime.schemas_for(...)`.
- Delete or rewrite tests that only assert old mode fallback behavior.
- Keep `src/embedagent_core` free of `embedagent.*`, `embedagent_host.*`, GUI/TUI, or workflow package imports.
- Keep default C/C++ workflow behavior inside `src/embedagent/workflow_packages/c_cpp/`.
- Keep hosted product composition inside `src/embedagent_host/`.
- Keep Python syntax valid for `>=3.8,<3.9`: no `match`, no `:=`, no `dict | dict`, no built-in generic aliases.
- Do not add dependencies to `pyproject.toml`.
- Each task ends with a small commit.

## Non-Goals For This Stage

- Do not physically split `embedagent_core` into a separate repository.
- Do not implement new Python, HTML, embedded-C, or generic workflow packages.
- Do not redesign the T3 GUI timeline or composer interaction lifecycle in this stage.
- Do not change C/C++ harness internals except where activation contracts need to route through the new boundary.

## File Structure Map

### New Profile Contract

- Create `src/embedagent/agent_profiles.py`
  - Owns `AgentModeDescriptor`, `AgentProfile`, `default_c_cpp_agent_profile()`, and helpers for profile mode lookup, write globs, base tools, system prompt text, and protocol metadata.
  - This is product/host composition, not Agent Core.

### Existing Mode Boundary

- Modify `src/embedagent/modes.py`
  - Delegate built-in mode definitions to the default profile.
  - Keep public helpers such as `DEFAULT_MODE`, `mode_names()`, `require_mode()`, `allowed_tools_for()`, `get_writable_globs()`, `is_path_writable()`, and mode parsing.
  - Remove duplicated built-in dictionaries and C/C++-shaped write contracts from this module.

### Tool Runtime Boundary

- Modify `src/embedagent/tools/runtime.py`
  - Remove the import of `embedagent.modes.allowed_tools_for`.
  - Make `schemas_for(..., tool_names=None)` return no schemas when no explicit tool list is provided.
  - Keep `schemas()` as the full registered runtime catalog.

### Extension Host And Manager

- Modify `src/embedagent_core/extensions.py`
  - Rename the semantic fallback parameter in `ExtensionManager.allowed_tool_names(...)` from `fallback` to `base_tool_names`.
  - The method starts from `base_tool_names` and unions extension-provided names.

- Modify `src/embedagent_core/agent_extension_host.py`
  - Pass `base_tool_names=` from the injected `ModeToolPolicy`.
  - Request runtime schemas only with explicit active tool names.

### Hosted Adapter

- Modify `src/embedagent_host/inprocess_adapter.py`
  - Replace direct fallback use of `allowed_tools_for(...)` with a profile-backed `_ProductModeToolPolicy`.
  - Make frontend tool catalog active visibility use the same profile plus extension manager path.
  - Add mode/profile descriptors into session capability payloads if not already present through protocol conversion.

### Protocol / GUI Capability Projection

- Modify `src/embedagent_core/capabilities.py`
  - Add `mode` to `CAPABILITY_KINDS`.
  - Add `mode_capability_descriptors(...)` that projects profile mode descriptors as read-only capability descriptors.
  - Extend `command_capability_payload(...)` or add a focused payload helper so GUI capability payloads include backend-declared modes.

- Modify `src/embedagent_core/runtime_capability_service.py`
  - Accept a `mode_descriptor_loader`.
  - Register mode descriptors alongside model, tool, command, resource, and workflow package descriptors.

- Modify `src/embedagent/protocol/app_protocol.py` only if current capability conversion cannot already preserve modes.
- Modify GUI JS only if tests prove mode catalog still depends on hard-coded values instead of backend capabilities.

### Tests

- Modify `tests/test_modes.py`
- Modify `tests/test_tools_v2_runtime.py`
- Modify `tests/test_tools_package.py`
- Modify `tests/test_workflow_extensions.py`
- Modify `tests/test_dynamic_tool_registration.py`
- Modify `tests/test_capability_registry.py`
- Modify `tests/test_inprocess_adapter_frontend_api.py`
- Modify `tests/test_current_architecture_boundaries.py`
- Add `tests/test_agent_profiles.py`

---

## Task 1: Add Profile Contract Tests

**Files:**
- Create: `tests/test_agent_profiles.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] **Step 1: Write failing tests for the new default profile**

Create `tests/test_agent_profiles.py` with:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class AgentProfileTests(unittest.TestCase):
    def test_default_profile_declares_current_product_modes(self):
        from embedagent.agent_profiles import default_c_cpp_agent_profile

        profile = default_c_cpp_agent_profile()
        self.assertEqual(profile.default_mode, "explore")
        self.assertEqual(
            [item.slug for item in profile.modes],
            ["explore", "spec", "build", "debug", "verify"],
        )

    def test_profile_base_tools_exclude_c_workflow_tools(self):
        from embedagent.agent_profiles import default_c_cpp_agent_profile

        profile = default_c_cpp_agent_profile()
        harness_tools = {
            "list_recipes",
            "run_recipe",
            "report_quality_v2",
            "record_failing_evidence",
            "task_status",
        }
        for mode_name in ("explore", "spec", "build", "debug", "verify"):
            self.assertEqual(set(profile.allowed_tools_for(mode_name)) & harness_tools, set())

    def test_profile_mode_descriptor_payload_is_gui_safe(self):
        from embedagent.agent_profiles import default_c_cpp_agent_profile

        profile = default_c_cpp_agent_profile()
        payload = profile.mode_descriptor_payloads()
        build = [item for item in payload if item["id"] == "build"][0]
        self.assertEqual(build["label"], "Build")
        self.assertEqual(build["dispatch"], {"kind": "mode.set", "mode": "build"})
        self.assertEqual(build["source_type"], "agent_profile")
        self.assertEqual(build["source_id"], profile.profile_id)

    def test_unknown_mode_raises_in_profile_lookup(self):
        from embedagent.agent_profiles import default_c_cpp_agent_profile

        profile = default_c_cpp_agent_profile()
        with self.assertRaises(ValueError):
            profile.require_mode("python-build")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Add an architecture guard for profile ownership**

Append this test to `tests/test_current_architecture_boundaries.py`:

```python
def test_tool_runtime_does_not_import_mode_registry_for_schema_projection():
    runtime_source = _read(ROOT / "src/embedagent/tools/runtime.py")
    assert "from embedagent.modes import allowed_tools_for" not in runtime_source
    assert "allowed_tools_for(mode_name)" not in runtime_source


def test_c_workflow_tools_are_declared_only_by_c_workflow_package_or_tests():
    c_tools = (
        "list_recipes",
        "run_recipe",
        "report_quality_v2",
        "record_failing_evidence",
        "task_status",
    )
    allowed_prefixes = (
        "src/embedagent/workflow_packages/c_cpp/",
        "src/embedagent/tools/recipe_ops.py",
        "src/embedagent/tools/session_ops.py",
    )
    offenders = []
    for path in _source_files_under("src", suffixes=(".py", ".js", ".jsx")):
        rel = _relative(path)
        if rel.startswith(allowed_prefixes):
            continue
        text = _read(path)
        for tool_name in c_tools:
            if '"%s"' % tool_name in text or "'%s'" % tool_name in text:
                offenders.append("%s hard-codes %s" % (rel, tool_name))
    assert offenders == []
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/test_agent_profiles.py tests/test_current_architecture_boundaries.py::test_tool_runtime_does_not_import_mode_registry_for_schema_projection tests/test_current_architecture_boundaries.py::test_c_workflow_tools_are_declared_only_by_c_workflow_package_or_tests -v
```

Expected: FAIL because `embedagent.agent_profiles` does not exist and `ToolRuntime` still imports `allowed_tools_for`.

- [ ] **Step 4: Commit the failing profile contract tests**

Run:

```bash
git add tests/test_agent_profiles.py tests/test_current_architecture_boundaries.py
git commit -m "test: add agent profile contract guards"
```

---

## Task 2: Implement The Default Agent Profile

**Files:**
- Create: `src/embedagent/agent_profiles.py`
- Modify: `src/embedagent/modes.py`
- Test: `tests/test_agent_profiles.py`
- Test: `tests/test_modes.py`

- [ ] **Step 1: Add the profile implementation**

Create `src/embedagent/agent_profiles.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class AgentModeDescriptor(object):
    slug: str
    label: str
    description: str
    system_prompt: str
    allowed_tools: List[str] = field(default_factory=list)
    writable_globs: List[str] = field(default_factory=list)
    icon_key: str = "circle"
    color_token: str = "info"

    def to_mode_definition(self) -> Dict[str, object]:
        return {
            "slug": self.slug,
            "system_prompt": self.system_prompt,
            "allowed_tools": list(self.allowed_tools),
            "writable_globs": list(self.writable_globs),
            "label": self.label,
            "description": self.description,
            "icon_key": self.icon_key,
            "color_token": self.color_token,
        }

    def to_capability_metadata(self, profile_id: str) -> Dict[str, object]:
        return {
            "id": self.slug,
            "label": self.label,
            "description": self.description,
            "icon_key": self.icon_key,
            "color_token": self.color_token,
            "command_id": "mode.%s" % self.slug,
            "dispatch": {"kind": "mode.set", "mode": self.slug},
            "source_type": "agent_profile",
            "source_id": profile_id,
        }


@dataclass(frozen=True)
class AgentProfile(object):
    profile_id: str
    label: str
    default_mode: str
    modes: List[AgentModeDescriptor]

    def mode_registry(self) -> Dict[str, Dict[str, object]]:
        return dict((item.slug, item.to_mode_definition()) for item in self.modes)

    def require_mode(self, mode_name: str) -> AgentModeDescriptor:
        requested = str(mode_name or "").strip()
        for item in self.modes:
            if item.slug == requested:
                return item
        raise ValueError("Unknown mode %r" % (mode_name,))

    def allowed_tools_for(self, mode_name: str) -> List[str]:
        return list(self.require_mode(mode_name).allowed_tools)

    def writable_globs_for(self, mode_name: str) -> List[str]:
        return list(self.require_mode(mode_name).writable_globs)

    def mode_descriptor_payloads(self) -> List[Dict[str, object]]:
        return [item.to_capability_metadata(self.profile_id) for item in self.modes]


BASE_READ_TOOLS = ["read_file", "list_dir", "glob_files", "grep_text"]
BASE_DISCUSSION_TOOLS = BASE_READ_TOOLS + ["git_status", "git_log", "ask_user"]
BASE_WRITE_TOOLS = BASE_READ_TOOLS + [
    "write_file",
    "edit_file",
    "bash",
    "author_local_capability",
    "ask_user",
]
BASE_VERIFY_TOOLS = BASE_READ_TOOLS + ["bash", "ask_user"]

SPEC_WRITABLE_GLOBS = ["**/*.md", "**/*.rst", "**/*.txt"]
DEVELOPMENT_WRITABLE_GLOBS = SPEC_WRITABLE_GLOBS + [
    "**/*.c",
    "**/*.cc",
    "**/*.cpp",
    "**/*.cxx",
    "**/*.h",
    "**/*.hh",
    "**/*.hpp",
    "**/*.hxx",
    "**/*.py",
    "**/*.pyi",
    "**/*.ps1",
    "**/*.bat",
    "**/*.toml",
    "**/*.cfg",
    "**/*.ini",
    "**/*.json",
    "**/*.yaml",
    "**/*.yml",
    "**/*.cmake",
    "CMakeLists.txt",
    "**/CMakeLists.txt",
    "Makefile",
    "**/Makefile",
    "makefile",
    "**/makefile",
    "meson.build",
    "**/meson.build",
]


def default_c_cpp_agent_profile() -> AgentProfile:
    return AgentProfile(
        profile_id="embedagent.default_c_cpp",
        label="Default C/C++ Agent",
        default_mode="explore",
        modes=[
            AgentModeDescriptor(
                slug="explore",
                label="Explore",
                description="Read code and discuss design without writing files.",
                system_prompt=(
                    "你当前处于 explore 模式（默认模式）。"
                    "负责阅读代码、解释逻辑、讨论设计方案，以及帮助用户理清思路。"
                    "当用户需要修改文件时，询问应切换到哪个模式，"
                    "提供 2-4 个选项（如 spec / build / debug），等待用户用 /mode 切换。"
                    "不要擅自写文件。"
                ),
                allowed_tools=list(BASE_DISCUSSION_TOOLS),
                writable_globs=[],
                icon_key="search",
                color_token="info",
            ),
            AgentModeDescriptor(
                slug="spec",
                label="Spec",
                description="Write requirements, boundaries, and design documentation.",
                system_prompt=(
                    "你当前处于 spec 模式，负责整理需求、边界条件、验收标准和文档。"
                    "先用 list_dir / glob_files 探测现有文档目录；若工作区为空或无文档目录，可在 docs/ 下创建。"
                    "不要擅自切到实现模式；若需要实现，告知用户需要切换模式。"
                ),
                allowed_tools=BASE_READ_TOOLS + ["write_file", "ask_user"],
                writable_globs=list(SPEC_WRITABLE_GLOBS),
                icon_key="file-text",
                color_token="accent",
            ),
            AgentModeDescriptor(
                slug="build",
                label="Build",
                description="Implement and refactor within the configured write boundary.",
                system_prompt=(
                    "你当前处于 build 模式，负责完成开发闭环。"
                    "你拥有开发所需的读写边界，但不要因为进入 build 模式而预设任务或固定阶段。"
                    "仅在用户提出明确开发、修复、重构、运行或验证请求时推进相应工作流。"
                    "应复用现有工程结构，不要假设固定目录；如遇关键分歧，请求用户确认。"
                ),
                allowed_tools=list(BASE_WRITE_TOOLS),
                writable_globs=list(DEVELOPMENT_WRITABLE_GLOBS),
                icon_key="hammer",
                color_token="success",
            ),
            AgentModeDescriptor(
                slug="debug",
                label="Debug",
                description="Reproduce, diagnose, and minimally repair failures.",
                system_prompt=(
                    "你当前处于 debug 模式，负责复现问题、定位根因并做最小修复。"
                    "先根据当前工程结构和诊断缩小范围，不要假设固定目录。"
                    "若需要更大范围重构，告知用户建议切换到 build 模式。"
                ),
                allowed_tools=list(BASE_WRITE_TOOLS),
                writable_globs=list(DEVELOPMENT_WRITABLE_GLOBS),
                icon_key="bug",
                color_token="warning",
            ),
            AgentModeDescriptor(
                slug="verify",
                label="Verify",
                description="Run read-only quality gates and report evidence.",
                system_prompt=(
                    "你当前处于 verify 模式，负责执行构建、测试、静态检查并给出质量门结论。"
                    "本模式不改代码；发现问题时只说明证据与建议，并告知用户需要切换到哪个模式修复。"
                ),
                allowed_tools=list(BASE_VERIFY_TOOLS),
                writable_globs=[],
                icon_key="badge-check",
                color_token="verify",
            ),
        ],
    )
```

- [ ] **Step 2: Delegate mode registry initialization to the profile**

In `src/embedagent/modes.py`, import the profile:

```python
from embedagent.agent_profiles import default_c_cpp_agent_profile
```

Replace the existing `_BUILTIN_MODES = {...}` dictionary with:

```python
_DEFAULT_AGENT_PROFILE = default_c_cpp_agent_profile()
_BUILTIN_MODES = _DEFAULT_AGENT_PROFILE.mode_registry()
```

Keep the rest of the public mode API intact.

- [ ] **Step 3: Run profile and mode tests**

Run:

```bash
uv run pytest tests/test_agent_profiles.py tests/test_modes.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit the profile implementation**

Run:

```bash
git add src/embedagent/agent_profiles.py src/embedagent/modes.py tests/test_agent_profiles.py tests/test_modes.py
git commit -m "feat: add agent profile mode contract"
```

---

## Task 3: Make Runtime Schema Projection Explicit

**Files:**
- Modify: `tests/test_tools_v2_runtime.py`
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent_core/extensions.py`
- Modify: `src/embedagent_core/agent_extension_host.py`
- Modify: `src/embedagent_host/inprocess_adapter.py`

- [ ] **Step 1: Rewrite runtime tests for explicit schema requests**

In `tests/test_tools_v2_runtime.py`, replace the three default schema tests with:

```python
    def test_schema_projection_requires_explicit_tool_names(self):
        from embedagent.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [item["function"]["name"] for item in runtime.schemas_for("build")]
        self.assertEqual(names, [])

    def test_explicit_build_tool_names_project_schemas(self):
        from embedagent.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for(
                "build",
                tool_names=["read_file", "list_dir", "write_file", "edit_file"],
            )
        ]
        self.assertEqual(names, ["read_file", "list_dir", "write_file", "edit_file"])

    def test_explicit_verify_tool_names_preserve_workflow_visibility_filter(self):
        from embedagent.tools import ToolRuntime

        runtime = ToolRuntime(self.workspace)
        names = [
            item["function"]["name"]
            for item in runtime.schemas_for(
                "verify",
                workflow_state="chat",
                tool_names=["read_file", "grep_text", "ask_user"],
            )
        ]
        self.assertEqual(names, ["read_file", "grep_text", "ask_user"])
```

- [ ] **Step 2: Rewrite package tests that relied on implicit mode fallback**

In `tests/test_tools_package.py`, update calls such as:

```python
schemas = self.rt.schemas_for("verify", workflow_state="review")
```

to pass explicit base tool names:

```python
schemas = self.rt.schemas_for(
    "verify",
    workflow_state="review",
    tool_names=["read_file", "list_dir", "glob_files", "grep_text", "bash", "ask_user"],
)
```

For build/debug assertions, use:

```python
tool_names=["read_file", "list_dir", "glob_files", "grep_text", "write_file", "edit_file", "bash", "author_local_capability", "ask_user"]
```

Keep assertions that C workflow tools are absent when they are not explicitly active.

- [ ] **Step 3: Rename fallback semantics in extension tests**

In tests that call `allowed_tool_names(..., fallback=...)`, replace `fallback=` with `base_tool_names=`.

Example:

```python
names = manager.allowed_tool_names(
    "build",
    workflow_state="chat",
    base_tool_names={"read_file", "ask_user"},
)
```

- [ ] **Step 4: Verify rewritten tests fail before production changes**

Run:

```bash
uv run pytest tests/test_tools_v2_runtime.py tests/test_tools_package.py tests/test_workflow_extensions.py -v
```

Expected: FAIL because production still uses implicit fallback and `allowed_tool_names` still accepts `fallback=`.

- [ ] **Step 5: Remove implicit mode fallback from ToolRuntime**

In `src/embedagent/tools/runtime.py`, delete:

```python
from embedagent.modes import allowed_tools_for
```

Replace this line inside `schemas_for`:

```python
allowed_by_mode = set(tool_names or allowed_tools_for(mode_name))
```

with:

```python
if tool_names is None:
    return []
allowed_by_mode = set(tool_names)
```

- [ ] **Step 6: Rename ExtensionManager active-tool fallback**

In `src/embedagent_core/extensions.py`, change the `allowed_tool_names` signature to:

```python
    def allowed_tool_names(
        self,
        mode_name: str,
        workflow_state: str = "chat",
        base_tool_names: Optional[Set[str]] = None,
    ) -> Set[str]:
        names = set(base_tool_names or set())
```

Update internal call sites to use `base_tool_names=`.

- [ ] **Step 7: Update AgentExtensionHost**

In `src/embedagent_core/agent_extension_host.py`, change:

```python
                fallback=set(
                    self._mode_tool_policy.allowed_tools_for(
                        mode_name,
                        workflow_state=workflow_state,
                    )
                ),
```

to:

```python
                base_tool_names=set(
                    self._mode_tool_policy.allowed_tools_for(
                        mode_name,
                        workflow_state=workflow_state,
                    )
                ),
```

- [ ] **Step 8: Update hosted adapter active-tool calls**

In `src/embedagent_host/inprocess_adapter.py`, replace `fallback=set(allowed_tools_for(...))` with:

```python
base_tool_names=set(self._mode_tool_policy.allowed_tools_for(state.current_mode))
```

For the tool catalog loop over `mode_names()`, use:

```python
base_tool_names=set(self._mode_tool_policy.allowed_tools_for(mode_name))
```

If `_mode_tool_policy` does not exist as an instance attribute yet, assign it in `__init__` before constructing `QueryEngine` dependencies:

```python
self._mode_tool_policy = _ProductModeToolPolicy()
```

and pass `mode_tool_policy=self._mode_tool_policy` where needed.

- [ ] **Step 9: Run runtime and workflow tests**

Run:

```bash
uv run pytest tests/test_tools_v2_runtime.py tests/test_tools_package.py tests/test_workflow_extensions.py tests/test_dynamic_tool_registration.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit explicit schema projection**

Run:

```bash
git add src/embedagent/tools/runtime.py src/embedagent_core/extensions.py src/embedagent_core/agent_extension_host.py src/embedagent_host/inprocess_adapter.py tests/test_tools_v2_runtime.py tests/test_tools_package.py tests/test_workflow_extensions.py tests/test_dynamic_tool_registration.py
git commit -m "refactor: require explicit active tool schema projection"
```

---

## Task 4: Publish Profile Modes Through Capability Snapshots

**Files:**
- Modify: `tests/test_capability_registry.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `src/embedagent_core/capabilities.py`
- Modify: `src/embedagent_core/runtime_capability_service.py`
- Modify: `src/embedagent_host/inprocess_adapter.py`

- [ ] **Step 1: Add capability tests for mode descriptors**

Append to `tests/test_capability_registry.py`:

```python
def test_mode_capability_descriptors_project_agent_profile_modes():
    from embedagent.agent_profiles import default_c_cpp_agent_profile
    from embedagent_core.capabilities import mode_capability_descriptors

    descriptors = mode_capability_descriptors(default_c_cpp_agent_profile())

    names = [item.name for item in descriptors]
    assert names == ["build", "debug", "explore", "spec", "verify"]
    build = [item for item in descriptors if item.name == "build"][0]
    assert build.kind == "mode"
    assert build.source_type == "agent_profile"
    assert build.metadata["dispatch"] == {"kind": "mode.set", "mode": "build"}
```

Add or update an adapter API test in `tests/test_inprocess_adapter_frontend_api.py`:

```python
    def test_session_capabilities_include_backend_declared_modes(self):
        snapshot = self.adapter.create_session(mode="explore")
        capabilities = self.adapter.get_session_capabilities(snapshot["session_id"])
        modes = capabilities.get("modes") or []
        ids = [item.get("id") for item in modes]
        self.assertEqual(ids, ["build", "debug", "explore", "spec", "verify"])
        build = [item for item in modes if item.get("id") == "build"][0]
        self.assertEqual(build.get("dispatch"), {"kind": "mode.set", "mode": "build"})
```

- [ ] **Step 2: Run the capability tests and verify they fail**

Run:

```bash
uv run pytest tests/test_capability_registry.py::test_mode_capability_descriptors_project_agent_profile_modes tests/test_inprocess_adapter_frontend_api.py::InProcessAdapterFrontendApiTests::test_session_capabilities_include_backend_declared_modes -v
```

Expected: FAIL because mode capability descriptors are not yet projected.

- [ ] **Step 3: Add mode descriptors to capabilities**

In `src/embedagent_core/capabilities.py`, change:

```python
CAPABILITY_KINDS = ("command", "model_profile", "resource", "tool", "workflow_package")
```

to:

```python
CAPABILITY_KINDS = ("command", "mode", "model_profile", "resource", "tool", "workflow_package")
```

Add:

```python
def mode_capability_descriptors(profile: Any) -> List[CapabilityDescriptor]:
    payloads_method = getattr(profile, "mode_descriptor_payloads", None)
    if not callable(payloads_method):
        return []
    descriptors = []
    for item in list(payloads_method() or []):
        if not isinstance(item, dict):
            continue
        mode_id = _clean_text(item.get("id"))
        if not mode_id:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=mode_id,
                kind="mode",
                source_type=_clean_text(item.get("source_type"), "agent_profile"),
                source_id=_clean_text(item.get("source_id"), "agent_profile"),
                metadata=dict(item),
                active=True,
            )
        )
    return sorted(descriptors, key=lambda descriptor: descriptor.name)
```

Add this payload helper:

```python
def app_capability_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    payload = command_capability_payload(snapshot)
    modes = []
    for item in list((snapshot or {}).get("descriptors") or []):
        if not isinstance(item, dict) or item.get("kind") != "mode":
            continue
        metadata = dict(item.get("metadata") or {})
        mode_id = _clean_text(metadata.get("id") or item.get("name"))
        if not mode_id:
            continue
        modes.append(
            {
                "id": mode_id,
                "label": _clean_text(metadata.get("label"), mode_id),
                "description": str(metadata.get("description") or ""),
                "icon_key": _clean_text(metadata.get("icon_key"), "circle"),
                "color_token": _clean_text(metadata.get("color_token"), "info"),
                "command_id": _clean_text(metadata.get("command_id"), "mode.%s" % mode_id),
                "dispatch": dict(metadata.get("dispatch") or {"kind": "mode.set", "mode": mode_id}),
                "source_type": _clean_text(item.get("source_type"), "agent_profile"),
                "source_id": _clean_text(item.get("source_id"), "agent_profile"),
                "active": bool(item.get("active")),
            }
        )
    modes.sort(key=lambda item: item["id"])
    payload["modes"] = modes
    return payload
```

- [ ] **Step 4: Wire RuntimeCapabilityService**

In `src/embedagent_core/runtime_capability_service.py`, add a constructor argument:

```python
        mode_descriptor_loader: Callable[[], List[Any]],
```

Store it as `self._mode_descriptor_loader`. In `snapshot()`, register descriptors from:

```python
        for descriptor in self._mode_descriptor_loader() or []:
            registry.register(descriptor)
```

- [ ] **Step 5: Wire InProcessAdapter**

In `src/embedagent_host/inprocess_adapter.py`, import:

```python
    app_capability_payload,
    mode_capability_descriptors,
```

and:

```python
from embedagent.agent_profiles import default_c_cpp_agent_profile
```

Create `self._agent_profile = default_c_cpp_agent_profile()` in `__init__`, then construct `RuntimeCapabilityService` with:

```python
mode_descriptor_loader=lambda: mode_capability_descriptors(self._agent_profile),
```

Change `get_session_capabilities()` to return:

```python
return app_capability_payload(self.capability_snapshot())
```

- [ ] **Step 6: Run capability tests**

Run:

```bash
uv run pytest tests/test_capability_registry.py tests/test_inprocess_adapter_frontend_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit capability projection**

Run:

```bash
git add src/embedagent_core/capabilities.py src/embedagent_core/runtime_capability_service.py src/embedagent_host/inprocess_adapter.py tests/test_capability_registry.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "feat: project agent profile modes through capabilities"
```

---

## Task 5: Update Documentation And Final Architecture Gates

**Files:**
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/superpowers/plans/2026-07-03-workflow-package-contract-extraction.md`

- [ ] **Step 1: Update active docs**

Add a short current-baseline note to `README.md` and `docs/overall-solution-architecture.md`:

```markdown
- Hosted agent profiles declare scenario mode metadata, base tool policy, and GUI mode capability projection. Workflow packages declare scenario-specific workflow tools, packs, prompts, resources, and manifests. Provider-facing schemas are always projected from explicit active tool names computed by the shared extension boundary.
```

Add a completed-slice bullet to `docs/implementation-roadmap.md`:

```markdown
- Agent profile contracts now own hosted scenario mode/base-tool metadata and GUI mode capability projection, while workflow package contracts own scenario-specific workflow tools and packs; `ToolRuntime.schemas_for(...)` no longer performs implicit mode fallback when active tool names are omitted.
```

- [ ] **Step 2: Run architecture gates**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_core_package_imports.py -v
```

Expected: PASS.

- [ ] **Step 3: Run fast tests**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [ ] **Step 4: Run lint**

Run:

```bash
uv run --locked python scripts/lint.py
```

Expected: PASS.

- [ ] **Step 5: Commit docs and final guard alignment**

Run:

```bash
git add README.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/superpowers/plans/2026-07-03-workflow-package-contract-extraction.md
git commit -m "docs: record workflow package contract extraction"
```

---

## Self-Review

- Spec coverage: The plan covers scenario/profile contracts, explicit active tool schema projection, C/C++ workflow package ownership, GUI mode metadata via backend capabilities, and deletion of old implicit fallback behavior.
- Placeholder scan: No deferred placeholder or compatibility shim steps are present.
- Type consistency: `AgentProfile`, `AgentModeDescriptor`, `mode_capability_descriptors`, `app_capability_payload`, and `base_tool_names` are introduced before use and referenced consistently.
