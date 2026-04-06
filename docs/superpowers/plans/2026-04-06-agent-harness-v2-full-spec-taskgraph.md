# Agent Harness V2 Full-Spec TDD and TaskGraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Agent Harness V2 落地第三条垂直切片：`build` mode 的 `full_spec_tdd` 轨道，以及以 `TaskGraph` 为真相源的最小自动同步机制。

**Architecture:** 本切片只扩展已经存在的 `harness/` 新包，不把任务图、discipline 决策、artifact gate 细节塞回旧 `query_engine.py` / `modes.py`。`TaskGraph` 作为内核真相源放在 `harness/task_graph.py`，`full_spec_tdd` 的轨道、artifact gate 和 discipline 决策放在 `harness/registry.py`、`phase_engine.py`、`runner.py`；旧主线只接受“当前 phase / 当前 activity / 当前 task summary”这类投影字段。

**Tech Stack:** Python 3.8, dataclasses, unittest, current `Session` / `QueryEngine` / `InProcessAdapter`, existing recipe/tool execution infrastructure

---

## Scope

本计划只实现：

- `build` mode 的 `full_spec_tdd` 轨道注册
- `TaskGraph` 最小真相源
- 最小 artifact gate：
  - `contract_ready`
  - `failing_evidence_ready`
  - `implementation_ready`
  - `check_result_ready`
  - `check_passed`
- `TaskGraph` 自动同步的第一版
- snapshot / runner 暴露 `task_summary`

本计划不实现：

- debug mode 的 `full_spec_tdd`
- 多任务依赖图和复杂 owner/blockedBy
- 从自由文本解析任务
- 前端大改

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/embedagent/harness/task_graph.py` | Create | `TaskGraph` 真相源、任务状态推进、摘要输出 |
| `src/embedagent/harness/contracts.py` | Modify | 增加 task/discpline decision 相关 dataclass（若确有必要） |
| `src/embedagent/harness/registry.py` | Modify | 为 `build` 增加 `full_track` 的真实约束语义 |
| `src/embedagent/harness/phase_engine.py` | Modify | 基于 artifact gate 的 full_spec_tdd 推进 |
| `src/embedagent/harness/runner.py` | Modify | 挂接 TaskGraph、生成 `task_summary`、生成 `full_spec_tdd` checklist |
| `src/embedagent/query_engine.py` | Modify | 仅接受 runner 产出的 context 投影 |
| `src/embedagent/inprocess_adapter.py` | Modify | snapshot 暴露 `task_summary` |
| `src/embedagent/protocol/__init__.py` | Modify | snapshot dataclass 补 `task_summary` |
| `tests/test_task_graph_v2.py` | Create | TaskGraph 真相源和自动同步 |
| `tests/test_harness_contracts.py` | Modify | full_spec_tdd track 断言 |
| `tests/test_phase_engine.py` | Modify | build full-spec artifact gate 断言 |
| `tests/test_harness_runner_taskgraph.py` | Create | runner 输出 `task_summary` 和 full checklist |
| `tests/test_query_engine_build_full_spec.py` | Create | build + full_spec_tdd 薄集成 |

### Boundary Rules

- 不在旧 `todos.py` / `manage_todos` 上叠加 TaskGraph 真相逻辑。
- 不在 `query_engine.py` 内实现 TaskGraph 规则和 phase 推进。
- 不引入大而全的任务 orchestrator；首期只做单任务主线的自动同步。

---

## Task 1: 建立 TaskGraph 最小真相源

**Files:**
- Create: `src/embedagent/harness/task_graph.py`
- Create: `tests/test_task_graph_v2.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest


class TaskGraphV2Tests(unittest.TestCase):
    def test_new_graph_starts_with_single_active_task(self):
        from embedagent.harness.task_graph import TaskGraph
        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        self.assertEqual(len(graph.tasks), 1)
        self.assertEqual(graph.tasks[0].status, "in_progress")

    def test_graph_can_advance_task_status(self):
        from embedagent.harness.task_graph import TaskGraph
        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        graph.complete_current("contract ready")
        self.assertEqual(graph.tasks[0].status, "completed")

    def test_graph_summary_is_stable_text(self):
        from embedagent.harness.task_graph import TaskGraph
        graph = TaskGraph.for_mode("build", "full_spec_tdd")
        summary = graph.render_summary()
        self.assertIn("in_progress", summary)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_task_graph_v2 -v`

Expected: `ModuleNotFoundError: No module named 'embedagent.harness.task_graph'`

- [ ] **Step 3: 实现 `task_graph.py` 最小版本**

要求：

- `TaskNode(id, title, status, note)`
- `TaskGraph.for_mode(mode_name, discipline)`
- `current_task()`
- `complete_current(note)`
- `start_next(title)`
- `render_summary()`

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 2: 让 `build` 的 `full_spec_tdd` 轨道成为真实注册表语义

**Files:**
- Modify: `src/embedagent/harness/registry.py`
- Modify: `tests/test_harness_contracts.py`

- [ ] **Step 1: 写失败测试**

```python
def test_build_mode_full_track_has_test_design_and_repair(self):
    from embedagent.harness.registry import build_default_registry
    registry = build_default_registry()
    self.assertEqual(
        [phase.value for phase in registry["build"].full_track],
        ["understand", "contract", "test_design", "implement", "check", "repair", "handoff"],
    )
```

- [ ] **Step 2: 运行测试，确认通过或补到现有定义**

- [ ] **Step 3: 若有缺口，修正 `registry.py`**

- [ ] **Step 4: 重新运行测试**

---

## Task 3: 扩展 phase engine，支持 build full-spec 的 artifact gate

**Files:**
- Modify: `src/embedagent/harness/phase_engine.py`
- Modify: `tests/test_phase_engine.py`

- [ ] **Step 1: 写失败测试**

```python
def test_contract_advances_to_test_design_when_failing_evidence_is_ready(self):
    from embedagent.harness.contracts import ExecutionPhase
    from embedagent.harness.phase_engine import advance_phase
    next_phase = advance_phase(
        ExecutionPhase.CONTRACT,
        {"failing_evidence_ready": True},
        "full_spec_tdd",
    )
    self.assertEqual(next_phase.value, "test_design")

def test_check_advances_to_repair_when_check_failed(self):
    from embedagent.harness.contracts import ExecutionPhase
    from embedagent.harness.phase_engine import advance_phase
    next_phase = advance_phase(
        ExecutionPhase.CHECK,
        {"check_result_ready": True, "check_passed": False},
        "full_spec_tdd",
    )
    self.assertEqual(next_phase.value, "repair")
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 扩展 `advance_phase()`，按 discipline 区分 lite/full**

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 4: 把 TaskGraph 和 full-spec checklist 挂进 runner

**Files:**
- Modify: `src/embedagent/harness/runner.py`
- Create: `tests/test_harness_runner_taskgraph.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest


class HarnessRunnerTaskGraphTests(unittest.TestCase):
    def test_runner_builds_full_spec_units_with_task_summary(self):
        from embedagent.harness.runner import HarnessRunner
        runner = HarnessRunner()
        units = runner.build_mode_units("build", [], discipline_override="full_spec_tdd")
        self.assertTrue(any("full_spec_tdd" in item for item in units))
        self.assertTrue(any("Tasks:" in item for item in units))
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 在 runner 中新增**

- TaskGraph 初始化
- `discipline_override`
- `task_summary`
- full-spec checklist 输出

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 5: 薄接入 QueryEngine / Adapter / Protocol

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/protocol/__init__.py`
- Create: `tests/test_query_engine_build_full_spec.py`

- [ ] **Step 1: 写失败测试**

```python
def test_build_mode_full_spec_adds_full_harness_context(self):
    engine = QueryEngine(
        client=DoneClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    result = engine.submit_turn(
        user_text="开始 full spec",
        stream=False,
        initial_mode="build",
        workflow_state="plan",
    )
    system_messages = [message.content for message in result.session.messages if message.role == "system"]
    self.assertTrue(any("full_spec_tdd" in content for content in system_messages))

def test_adapter_snapshot_exposes_task_summary(self):
    adapter = InProcessAdapter(
        client=DoneClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    snapshot = adapter.create_session("build")
    self.assertIn("task_summary", snapshot)
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 在薄桥接层加 `task_summary` 字段**

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 6: 组合验证

**Files:** none

- [ ] **Step 1: 运行新切片测试**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_task_graph_v2 tests.test_harness_contracts tests.test_phase_engine tests.test_harness_runner_taskgraph tests.test_query_engine_build_full_spec -v`

- [ ] **Step 2: 运行已有 Harness V2 测试**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_prompt_stack_v2 tests.test_tooling_budget_v2 tests.test_rule_schema_v2 tests.test_tools_v2_runtime tests.test_query_engine_build_lite tests.test_query_engine_debug_lite tests.test_debug_evidence_v2 tests.test_harness_runner_debug -v`

- [ ] **Step 3: 运行定向旧回归**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor tests.test_permissions tests.test_tool_execution tests.test_tool_commit -v`

- [ ] **Step 4: 更新 tracker / change log**

- [ ] **Step 5: Commit**

```bash
git add docs/development-tracker.md docs/design-change-log.md docs/superpowers/plans/2026-04-06-agent-harness-v2-full-spec-taskgraph.md src/embedagent/harness src/embedagent/inprocess_adapter.py src/embedagent/query_engine.py src/embedagent/protocol/__init__.py tests
git commit -m "feat: add agent harness v2 full-spec task graph slice"
```
