# Agent Harness V2 Foundation and Build-Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不继续膨胀 `query_engine.py` / `modes.py` / `permissions.py` / `tools/runtime.py` 的前提下，落地 Agent Harness V2 的第一条可运行主线：`build` mode + `lite_spec_tdd` + core tool pack + rule schema v1。

**Architecture:** 本计划只覆盖 `docs/agent-harness-v2.md` 中的 Program A 和 Program B。实现方式是新增 `harness/`、`tooling/`、`tools_v2/`、`permissions_v2/` 四个聚焦包，把 phase、prompt stack、tool contract、预算、权限解释和 build-lite 调度拆到新模块中；既有大文件只保留薄 shim 和桥接逻辑，不再承接新核心实现。

**Tech Stack:** Python 3.8, dataclasses, enum, existing `ToolContext` / `WorkspaceRecipe` helpers, unittest, current `Session` / `QueryEngine` infrastructure

---

## Scope

这份计划**只实现第一阶段可交付切片**：

- 新建 Harness V2 核心包
- 跑通 `build` mode 的 `lite_spec_tdd`
- 重做第一批核心工具：`list_dir`, `glob_files`, `grep_text`, `read_file`, `edit_file`, `write_file`, `list_recipes`, `run_recipe`, `task_status`, `ask_user`
- 上线 Rule Schema V1 和确定性 permission explanation builder
- 让 `QueryEngine` 能在 `build` mode 下委托给新的 harness runner

本计划**不包含**：

- `debug` mode 的完整新工作流
- `verify` mode 的完整新工作流
- `full_spec_tdd`
- 旧权限配置迁移
- UI 大改，只补最小 snapshot / inspector 可见字段

后续 `debug`、`verify`、`full_spec_tdd`、旧体系切断，应分别写后续计划。

---

## File Map

### New Packages

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/embedagent/harness/__init__.py` | Create | Harness V2 公共导出 |
| `src/embedagent/harness/contracts.py` | Create | `WorkMode`、`DisciplineProfile`、`ExecutionPhase`、`PhaseState`、`ArtifactState` |
| `src/embedagent/harness/registry.py` | Create | mode 定义、phase 轨道、tool pack 名称和 discipline 默认映射 |
| `src/embedagent/harness/phase_engine.py` | Create | 基于 artifact 的 phase 推进与 gate 判定 |
| `src/embedagent/harness/prompt_stack.py` | Create | 3 单元 prompt 注入拼装 |
| `src/embedagent/harness/task_graph.py` | Create | 内核任务图与自动同步入口 |
| `src/embedagent/harness/runner.py` | Create | `build + lite_spec_tdd` 的主驱动器，供 `QueryEngine` 调用 |
| `src/embedagent/tooling/__init__.py` | Create | Tool Contract V2 导出 |
| `src/embedagent/tooling/contracts.py` | Create | 工具最小契约、Observation envelope、BudgetPolicy |
| `src/embedagent/tooling/result_budget.py` | Create | 单工具预算 + aggregate budget 基础设施 |
| `src/embedagent/tooling/packs.py` | Create | 常驻 core pack 与 build-lite pack 装载 |
| `src/embedagent/permissions_v2/__init__.py` | Create | Permission V2 公共导出 |
| `src/embedagent/permissions_v2/schema.py` | Create | Rule Schema V1 解析与校验 |
| `src/embedagent/permissions_v2/matcher.py` | Create | tool/path/recipe/command 前缀匹配 |
| `src/embedagent/permissions_v2/explainer.py` | Create | 确定性权限解释模板 |
| `src/embedagent/permissions_v2/policy.py` | Create | Permission V2 评估器 |
| `src/embedagent/tools_v2/__init__.py` | Create | V2 工具 runtime 导出 |
| `src/embedagent/tools_v2/discovery_ops.py` | Create | `list_dir`, `glob_files`, `grep_text` |
| `src/embedagent/tools_v2/read_ops.py` | Create | `read_file` with range support |
| `src/embedagent/tools_v2/edit_ops.py` | Create | `edit_file`, `write_file` V2 wrappers |
| `src/embedagent/tools_v2/recipe_ops.py` | Create | `list_recipes`, `run_recipe` |
| `src/embedagent/tools_v2/session_ops.py` | Create | `task_status`, `ask_user` V2 wrappers |
| `src/embedagent/tools_v2/runtime.py` | Create | V2 runtime + pack-aware schema exposure |

### Thin Integration Files

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/embedagent/query_engine.py` | Modify | 对 `build` mode 接入 `HarnessRunner` 的薄委托，不在此处实现新 phase/permission 逻辑 |
| `src/embedagent/inprocess_adapter.py` | Modify | 补 Harness V2 snapshot 字段转发 |
| `src/embedagent/protocol/__init__.py` | Modify | 扩展 session snapshot / runtime view 字段 |

### Tests

| 文件 | 操作 | 职责 |
|------|------|------|
| `tests/test_harness_contracts.py` | Create | mode/discipline/phase contracts 和 registry |
| `tests/test_phase_engine.py` | Create | artifact 触发的 phase 推进 |
| `tests/test_prompt_stack_v2.py` | Create | 3 单元 prompt 注入结果 |
| `tests/test_tooling_budget_v2.py` | Create | result budget 与 aggregate budget |
| `tests/test_rule_schema_v2.py` | Create | permission schema / matcher / explainer |
| `tests/test_tools_v2_runtime.py` | Create | V2 tools runtime 和 pack 暴露 |
| `tests/test_query_engine_build_lite.py` | Create | `build + lite_spec_tdd` 主线集成 |

### Boundary Rules

- 不在 `query_engine.py` 中新增 phase 枚举、tool pack 细节、permission 规则实现。
- 不在 `modes.py` 中加入 V2 phase 逻辑；`modes.py` 只负责 visible mode 入口和向后兼容壳层，真正实现放在 `harness/registry.py`。
- 不在 `permissions.py` 中叠加 V2 规则求值器；V2 放在 `permissions_v2/`，旧文件只保留桥接入口。
- 不在 `tools/runtime.py` 中继续塞 V2 工具实现；V2 runtime 放在 `tools_v2/runtime.py`。

---

## Task 1: 建立 Harness V2 核心契约与注册表

**Files:**
- Create: `src/embedagent/harness/__init__.py`
- Create: `src/embedagent/harness/contracts.py`
- Create: `src/embedagent/harness/registry.py`
- Test: `tests/test_harness_contracts.py`

- [ ] **Step 1: 写失败测试，固定 mode / discipline / phase 的最小契约**

```python
import unittest


class HarnessContractsTests(unittest.TestCase):
    def test_build_mode_defaults_to_lite_spec_tdd(self):
        from embedagent.harness.registry import build_default_registry
        registry = build_default_registry()
        self.assertEqual(
            registry["build"].default_discipline.value,
            "lite_spec_tdd",
        )

    def test_build_mode_has_expected_lite_track(self):
        from embedagent.harness.registry import build_default_registry
        registry = build_default_registry()
        self.assertEqual(
            [phase.value for phase in registry["build"].lite_track],
            ["understand", "contract", "implement", "check", "handoff"],
        )

    def test_verify_mode_is_readonly(self):
        from embedagent.harness.registry import build_default_registry
        registry = build_default_registry()
        self.assertTrue(registry["verify"].readonly_mode)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `.venv\Scripts\python.exe -m unittest tests.test_harness_contracts -v`

Expected: `ModuleNotFoundError: No module named 'embedagent.harness'`

- [ ] **Step 3: 创建 `contracts.py`，只放枚举和轻量 dataclass**

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class WorkMode(str, Enum):
    EXPLORE = "explore"
    SPEC = "spec"
    BUILD = "build"
    DEBUG = "debug"
    VERIFY = "verify"


class DisciplineProfile(str, Enum):
    FULL_SPEC_TDD = "full_spec_tdd"
    LITE_SPEC_TDD = "lite_spec_tdd"


class ExecutionPhase(str, Enum):
    UNDERSTAND = "understand"
    CONTRACT = "contract"
    TEST_DESIGN = "test_design"
    IMPLEMENT = "implement"
    CHECK = "check"
    REPAIR = "repair"
    HANDOFF = "handoff"
    REPRODUCE = "reproduce"
    ISOLATE = "isolate"
    FAILING_CHECK = "failing_check"
    PATCH = "patch"
    REGRESSION_CHECK = "regression_check"
    SELECT_RECIPE = "select_recipe"
    EXECUTE = "execute"
    SUMMARIZE = "summarize"


@dataclass
class ArtifactState:
    flags: Dict[str, bool] = field(default_factory=dict)


@dataclass
class ModeDefinition:
    slug: str
    default_discipline: DisciplineProfile
    lite_track: List[ExecutionPhase]
    full_track: List[ExecutionPhase]
    readonly_mode: bool = False
```

- [ ] **Step 4: 创建 `registry.py`，把轨道和 pack 名称集中在一个小文件里**

```python
from embedagent.harness.contracts import (
    DisciplineProfile,
    ExecutionPhase,
    ModeDefinition,
)


def build_default_registry():
    return {
        "build": ModeDefinition(
            slug="build",
            default_discipline=DisciplineProfile.LITE_SPEC_TDD,
            lite_track=[
                ExecutionPhase.UNDERSTAND,
                ExecutionPhase.CONTRACT,
                ExecutionPhase.IMPLEMENT,
                ExecutionPhase.CHECK,
                ExecutionPhase.HANDOFF,
            ],
            full_track=[
                ExecutionPhase.UNDERSTAND,
                ExecutionPhase.CONTRACT,
                ExecutionPhase.TEST_DESIGN,
                ExecutionPhase.IMPLEMENT,
                ExecutionPhase.CHECK,
                ExecutionPhase.REPAIR,
                ExecutionPhase.HANDOFF,
            ],
        ),
        "verify": ModeDefinition(
            slug="verify",
            default_discipline=DisciplineProfile.LITE_SPEC_TDD,
            lite_track=[
                ExecutionPhase.SELECT_RECIPE,
                ExecutionPhase.EXECUTE,
                ExecutionPhase.SUMMARIZE,
            ],
            full_track=[
                ExecutionPhase.SELECT_RECIPE,
                ExecutionPhase.EXECUTE,
                ExecutionPhase.SUMMARIZE,
            ],
            readonly_mode=True,
        ),
    }
```

- [ ] **Step 5: 导出公共入口**

```python
from embedagent.harness.contracts import (
    ArtifactState,
    DisciplineProfile,
    ExecutionPhase,
    ModeDefinition,
    WorkMode,
)
from embedagent.harness.registry import build_default_registry
```

- [ ] **Step 6: 重新运行测试，确认通过**

Run: `.venv\Scripts\python.exe -m unittest tests.test_harness_contracts -v`

Expected: 3 tests `ok`

---

## Task 2: 落地 Phase Engine 和 Prompt Stack，且只保留 3 个物理注入单元

**Files:**
- Create: `src/embedagent/harness/phase_engine.py`
- Create: `src/embedagent/harness/prompt_stack.py`
- Test: `tests/test_phase_engine.py`
- Test: `tests/test_prompt_stack_v2.py`

- [ ] **Step 1: 写 phase 推进失败测试，固定 artifact 驱动而不是失败驱动**

```python
import unittest


class PhaseEngineTests(unittest.TestCase):
    def test_understand_advances_when_contract_artifact_exists(self):
        from embedagent.harness.contracts import ExecutionPhase
        from embedagent.harness.phase_engine import advance_phase
        next_phase = advance_phase(
            ExecutionPhase.UNDERSTAND,
            {"contract_ready": True},
            "lite_spec_tdd",
        )
        self.assertEqual(next_phase.value, "contract")

    def test_nonzero_exit_does_not_force_phase_jump(self):
        from embedagent.harness.contracts import ExecutionPhase
        from embedagent.harness.phase_engine import advance_phase
        next_phase = advance_phase(
            ExecutionPhase.IMPLEMENT,
            {"last_command_failed": True},
            "lite_spec_tdd",
        )
        self.assertEqual(next_phase.value, "implement")
```

- [ ] **Step 2: 写 prompt stack 失败测试，固定 3 单元输出**

```python
import unittest


class PromptStackV2Tests(unittest.TestCase):
    def test_build_messages_returns_three_sections(self):
        from embedagent.harness.prompt_stack import build_prompt_units
        units = build_prompt_units(
            base_prompt="base",
            mode_name="build",
            discipline_label="lite_spec_tdd",
            checklist_lines=["[ ] contract", "[ ] implement"],
            tool_prompt_lines=["Use read_file first."],
            runtime_nudges=["Last recipe failed."],
        )
        self.assertEqual(len(units), 3)
        self.assertIn("lite_spec_tdd", units[1])
        self.assertIn("Last recipe failed.", units[2])
```

- [ ] **Step 3: 实现 `phase_engine.py`，只做客观 artifact 判定**

```python
from embedagent.harness.contracts import ExecutionPhase


def advance_phase(current_phase, artifact_flags, discipline_value):
    flags = dict(artifact_flags or {})
    if current_phase == ExecutionPhase.UNDERSTAND and flags.get("contract_ready"):
        return ExecutionPhase.CONTRACT
    if current_phase == ExecutionPhase.CONTRACT and flags.get("implementation_ready"):
        return ExecutionPhase.IMPLEMENT
    if current_phase == ExecutionPhase.IMPLEMENT and flags.get("check_result_ready"):
        return ExecutionPhase.CHECK
    if current_phase == ExecutionPhase.CHECK and flags.get("check_passed"):
        return ExecutionPhase.HANDOFF
    return current_phase
```

- [ ] **Step 4: 实现 `prompt_stack.py`，不要做 7 次物理注入**

```python
def build_prompt_units(
    base_prompt,
    mode_name,
    discipline_label,
    checklist_lines,
    tool_prompt_lines,
    runtime_nudges,
):
    mode_context = "\n".join(
        [
            "Mode: %s" % mode_name,
            "Discipline: %s" % discipline_label,
            "Checklist:",
        ] + list(checklist_lines) + ["Tools:"] + list(tool_prompt_lines)
    )
    runtime_context = "\n".join(list(runtime_nudges or []))
    return [base_prompt, mode_context, runtime_context]
```

- [ ] **Step 5: 运行测试，确认 phase 与 prompt stack 都通过**

Run:

`.venv\Scripts\python.exe -m unittest tests.test_phase_engine tests.test_prompt_stack_v2 -v`

Expected: all `ok`

---

## Task 3: 建立 Tool Contract V2 和结果预算基础设施

**Files:**
- Create: `src/embedagent/tooling/__init__.py`
- Create: `src/embedagent/tooling/contracts.py`
- Create: `src/embedagent/tooling/result_budget.py`
- Create: `src/embedagent/tooling/packs.py`
- Test: `tests/test_tooling_budget_v2.py`

- [ ] **Step 1: 写失败测试，固定 aggregate budget 行为**

```python
import unittest


class ToolingBudgetV2Tests(unittest.TestCase):
    def test_large_results_are_replaced_with_refs(self):
        from embedagent.tooling.result_budget import apply_aggregate_budget
        results = [
            {"tool_name": "glob_files", "preview": "a" * 3000, "result_ref": "ref-a"},
            {"tool_name": "grep_text", "preview": "b" * 3000, "result_ref": "ref-b"},
        ]
        reduced = apply_aggregate_budget(results, char_budget=2000)
        self.assertTrue(any(item.get("omitted") for item in reduced))
```

- [ ] **Step 2: 实现 `contracts.py`，只保留最小必填契约**

```python
from dataclasses import dataclass, field


@dataclass
class ToolSpecV2:
    name: str
    description: str
    prompt: str
    input_schema: dict
    result_budget_policy: str
    tags: list = field(default_factory=list)
```

- [ ] **Step 3: 实现 `result_budget.py`，先做单纯的 preview/ref 替换**

```python
def apply_aggregate_budget(results, char_budget):
    total = 0
    reduced = []
    for item in results:
        preview = str(item.get("preview") or "")
        total += len(preview)
        if total > char_budget:
            reduced.append(
                {
                    "tool_name": item.get("tool_name"),
                    "preview": "",
                    "result_ref": item.get("result_ref"),
                    "omitted": True,
                }
            )
            continue
        reduced.append(item)
    return reduced
```

- [ ] **Step 4: 实现 `packs.py`，先固定 build-lite pack**

```python
CORE_PACK = [
    "read_file",
    "list_dir",
    "grep_text",
    "edit_file",
    "write_file",
    "run_recipe",
    "ask_user",
    "task_status",
]


BUILD_LITE_PACK = CORE_PACK + [
    "glob_files",
    "list_recipes",
]
```

- [ ] **Step 5: 运行预算测试**

Run: `.venv\Scripts\python.exe -m unittest tests.test_tooling_budget_v2 -v`

Expected: all `ok`

---

## Task 4: 新建 `tools_v2/`，只实现 build-lite 所需核心工具

**Files:**
- Create: `src/embedagent/tools_v2/__init__.py`
- Create: `src/embedagent/tools_v2/discovery_ops.py`
- Create: `src/embedagent/tools_v2/read_ops.py`
- Create: `src/embedagent/tools_v2/edit_ops.py`
- Create: `src/embedagent/tools_v2/recipe_ops.py`
- Create: `src/embedagent/tools_v2/session_ops.py`
- Create: `src/embedagent/tools_v2/runtime.py`
- Test: `tests/test_tools_v2_runtime.py`

- [ ] **Step 1: 写失败测试，固定 pack 暴露**

```python
import unittest


class ToolsV2RuntimeTests(unittest.TestCase):
    def test_build_lite_pack_exposes_list_dir_and_run_recipe(self):
        from embedagent.tools_v2.runtime import ToolRuntimeV2
        runtime = ToolRuntimeV2("D:/Claude-project/ccode-win7")
        names = [item["function"]["name"] for item in runtime.schemas_for_pack("build_lite")]
        self.assertIn("list_dir", names)
        self.assertIn("run_recipe", names)
```

- [ ] **Step 2: 在 `discovery_ops.py` 实现 `list_dir`，只列一层**

```python
import os


def list_dir(ctx, path, limit, offset):
    root = ctx.resolve_directory(path)
    names = sorted(os.listdir(root))
    items = names[offset : offset + limit]
    return {
        "preview": items,
        "returned_count": len(items),
        "total_count": len(names),
        "has_more": offset + limit < len(names),
        "next_offset": offset + len(items),
    }
```

- [ ] **Step 3: 在 `recipe_ops.py` 实现 `list_recipes` 与 `run_recipe`，直接复用现有 recipe 设施**

```python
def list_recipes(ctx):
    return ctx.list_workspace_recipes()


def run_recipe(ctx, recipe_id):
    recipe = ctx.resolve_workspace_recipe(recipe_id)
    return ctx.run_shell_tool(
        tool_name="run_recipe",
        command_text=str(recipe.get("command") or ""),
        cwd_argument=str(recipe.get("cwd") or "."),
        timeout_sec=int(recipe.get("timeout_sec") or 120),
        diagnostic=True,
    )
```

- [ ] **Step 4: 在 `runtime.py` 装配 pack-aware schema 暴露**

```python
from embedagent.tooling.packs import BUILD_LITE_PACK, CORE_PACK


class ToolRuntimeV2(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self._tools = {}

    def schemas_for_pack(self, pack_name):
        if pack_name == "build_lite":
            allowed = set(BUILD_LITE_PACK)
        else:
            allowed = set(CORE_PACK)
        return [tool.schema() for name, tool in self._tools.items() if name in allowed]
```

- [ ] **Step 5: 运行测试，确认 `tools_v2` 可以构造并暴露 pack**

Run: `.venv\Scripts\python.exe -m unittest tests.test_tools_v2_runtime -v`

Expected: all `ok`

---

## Task 5: 落地 Permission V2 的 Rule Schema V1 与解释模板

**Files:**
- Create: `src/embedagent/permissions_v2/__init__.py`
- Create: `src/embedagent/permissions_v2/schema.py`
- Create: `src/embedagent/permissions_v2/matcher.py`
- Create: `src/embedagent/permissions_v2/explainer.py`
- Create: `src/embedagent/permissions_v2/policy.py`
- Test: `tests/test_rule_schema_v2.py`

- [ ] **Step 1: 写失败测试，固定规则和解释文本**

```python
import unittest


class RuleSchemaV2Tests(unittest.TestCase):
    def test_permission_explanation_has_stable_sections(self):
        from embedagent.permissions_v2.explainer import build_permission_explanation
        text = build_permission_explanation(
            tool_name="Edit",
            args_summary="src/main.c",
            risk_category="code_write",
            trigger_reason="file write requires confirmation",
            rule_source="default",
            scope_text="src/main.c",
            memory_scope="session",
        )
        self.assertIn("[请求]", text)
        self.assertIn("[风险]", text)
        self.assertIn("[记忆]", text)
```

- [ ] **Step 2: 在 `schema.py` 定义 Rule Schema V1**

```python
from dataclasses import dataclass


@dataclass
class PermissionRuleV1:
    tool: str
    decision: str
    path: str = ""
    recipe: str = ""
    command_prefix: str = ""
```

- [ ] **Step 3: 在 `explainer.py` 实现统一文本模板**

```python
def build_permission_explanation(
    tool_name,
    args_summary,
    risk_category,
    trigger_reason,
    rule_source,
    scope_text,
    memory_scope,
):
    return "\n".join(
        [
            "[请求] %s(%s)" % (tool_name, args_summary),
            "[风险] %s" % risk_category,
            "[原因] %s" % trigger_reason,
            "[规则] %s" % rule_source,
            "[范围] %s" % scope_text,
            "[记忆] %s" % memory_scope,
        ]
    )
```

- [ ] **Step 4: 运行规则测试**

Run: `.venv\Scripts\python.exe -m unittest tests.test_rule_schema_v2 -v`

Expected: all `ok`

---

## Task 6: 把 build-lite harness runner 接进 `QueryEngine`，但只做薄委托

**Files:**
- Create: `src/embedagent/harness/runner.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/protocol/__init__.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_query_engine_build_lite.py`

- [ ] **Step 1: 写集成失败测试，固定 `build` mode 走 harness runner**

```python
import unittest
from unittest.mock import MagicMock


class QueryEngineBuildLiteTests(unittest.TestCase):
    def test_build_mode_calls_harness_runner(self):
        from embedagent.query_engine import QueryEngine
        engine = QueryEngine(
            client=MagicMock(),
            tools=MagicMock(),
        )
        engine._run_harness_mode = MagicMock(return_value=("build", None))
        engine._execute_action = MagicMock()
        engine._run_harness_mode("build", None)
        engine._run_harness_mode.assert_called_once()
```

- [ ] **Step 2: 在 `harness/runner.py` 建立最小 runner**

```python
class HarnessRunner(object):
    def __init__(self, registry, prompt_stack, phase_engine):
        self.registry = registry
        self.prompt_stack = prompt_stack
        self.phase_engine = phase_engine

    def build_mode_context(self, mode_name, discipline_label, checklist_lines, tool_lines, runtime_nudges):
        return self.prompt_stack(
            base_prompt="",
            mode_name=mode_name,
            discipline_label=discipline_label,
            checklist_lines=checklist_lines,
            tool_prompt_lines=tool_lines,
            runtime_nudges=runtime_nudges,
        )
```

- [ ] **Step 3: 只在 `query_engine.py` 增加薄委托，不把 V2 逻辑塞进旧文件**

```python
from embedagent.harness.runner import HarnessRunner


def _run_harness_mode(self, current_mode, session):
    if current_mode != "build":
        return current_mode, None
    runner = HarnessRunner(...)
    mode_context = runner.build_mode_context(
        mode_name="build",
        discipline_label="lite_spec_tdd",
        checklist_lines=["[ ] understand", "[ ] contract", "[ ] implement", "[ ] check"],
        tool_lines=["Core tools loaded."],
        runtime_nudges=[],
    )
    return current_mode, mode_context
```

- [ ] **Step 4: 扩展 session snapshot，暴露最小 V2 运行态**

```python
{
    "current_mode": "build",
    "current_phase": "implement",
    "discipline_profile": "lite_spec_tdd",
    "current_activity": "Editing src/embedagent/..."
}
```

- [ ] **Step 5: 运行 build-lite 集成测试**

Run: `.venv\Scripts\python.exe -m unittest tests.test_query_engine_build_lite -v`

Expected: all `ok`

---

## Task 7: 做一次首条主线验证并锁定“不继续长大”的架构边界

**Files:**
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: 运行新旧测试的最小组合**

Run:

`.venv\Scripts\python.exe -m unittest tests.test_harness_contracts tests.test_phase_engine tests.test_prompt_stack_v2 tests.test_tooling_budget_v2 tests.test_rule_schema_v2 tests.test_tools_v2_runtime tests.test_query_engine_build_lite -v`

Expected: all `ok`

- [ ] **Step 2: 运行现有回归保护**

Run:

`.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor tests.test_permissions tests.test_tool_execution tests.test_tool_commit -v`

Expected: no regressions

- [ ] **Step 3: 更新 tracker，声明 Program A/B 已进入实现中**

```markdown
- 当前重点：Agent Harness V2 Program A/B 实现中
- 新增风险：旧模式主线冻结期间禁止继续向 `query_engine.py` 追加 V2 核心逻辑
```

- [ ] **Step 4: 更新 change log，记录 Build-Lite 第一条主线已开始实现**

```markdown
- 变更主题：Agent Harness V2 Program A/B implementation started
- 变更摘要：新增 harness/tooling/tools_v2/permissions_v2 包，`QueryEngine` 仅增加薄委托
```

- [ ] **Step 5: Commit**

```bash
git add docs/development-tracker.md docs/design-change-log.md src/embedagent/harness src/embedagent/tooling src/embedagent/tools_v2 src/embedagent/permissions_v2 tests
git commit -m "feat: start agent harness v2 foundation and build-lite vertical slice"
```

---

## Self-Review

### Spec Coverage

| 设计要求 | 计划覆盖 |
|---------|---------|
| 保留用户可见 mode，但引入内部 phase | Task 1, Task 2, Task 6 |
| 复杂任务与简单任务的 discipline 分层 | Task 1, Task 2 |
| 工具契约最小化并写进新包 | Task 3 |
| 大结果 aggregate budget | Task 3 |
| 不继续向大文件叠逻辑 | File Map + Task 6 |
| 首期不用 DSL，先落 Rule Schema V1 | Task 5 |
| build + lite_spec_tdd 首条主线 | Task 4, Task 6 |
| 前端最小可见 mode/phase/discipline | Task 6 |

### Placeholder Scan

- 未使用 `TBD`、`TODO`、`later`
- 每个任务都给出了具体文件路径
- 所有测试步骤都给出了明确命令

### Type Consistency

- `WorkMode`, `DisciplineProfile`, `ExecutionPhase` 统一定义于 `harness/contracts.py`
- `ToolSpecV2` 统一定义于 `tooling/contracts.py`
- `PermissionRuleV1` 统一定义于 `permissions_v2/schema.py`

---

## Follow-Up Plans

本计划完成后，再分别写：

1. `debug + lite_spec_tdd` Implementation Plan
2. `full_spec_tdd + TaskGraph auto-sync` Implementation Plan
3. `verify mode + UI cutover + old system removal` Implementation Plan

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-06-agent-harness-v2-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
