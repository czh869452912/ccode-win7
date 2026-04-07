# Agent Harness V2 Debug-Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持新架构边界清晰的前提下，为 Agent Harness V2 落地第二条可运行主线：`debug` mode + `lite_spec_tdd`，覆盖复现、定位、最小修复、回归确认的第一版执行闭环。

**Architecture:** 本计划承接 `build-lite` 基础切片，继续扩展 `harness/`、`tools_v2/`、`permissions_v2/`，但不把 V2 细节重新塞回 `query_engine.py`、`modes.py` 或旧 `tools/runtime.py`。实现重点是新增 debug 的 phase 轨道、最小 failing-evidence artifact gate、面向调试的工具 pack，以及 QueryEngine 的薄委托桥接。

**Tech Stack:** Python 3.8, dataclasses, unittest, existing `ToolContext`, current `Session` / `QueryEngine` / transcript infrastructure

---

## Scope

本计划只覆盖：

- `debug` visible mode 的 `lite_spec_tdd`
- debug phase 轨道：`reproduce -> isolate -> patch -> regression_check -> handoff`
- 第一批调试专用 pack
- 最小 failing-evidence artifact state
- debug mode 的 snapshot 可见字段

本计划不覆盖：

- `full_spec_tdd` 的 debug 轨道
- verify mode 的独立重构
- 旧 mode / 旧 permission 主线清理
- UI 大改

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/embedagent/harness/contracts.py` | Modify | 新增 debug 相关 phase/状态字段（若需要） |
| `src/embedagent/harness/registry.py` | Modify | 新增 `debug` mode 的 lite/full 轨道 |
| `src/embedagent/harness/phase_engine.py` | Modify | 增加 debug artifact 驱动推进逻辑 |
| `src/embedagent/harness/runner.py` | Modify | 新增 debug mode 的 context/builders |
| `src/embedagent/tooling/packs.py` | Modify | 新增 `debug_lite` pack |
| `src/embedagent/tools_v2/session_ops.py` | Modify | 新增最小 `record_failing_evidence` 或等价结构化入口 |
| `src/embedagent/tools_v2/runtime.py` | Modify | 暴露 `debug_lite` pack schemas |
| `src/embedagent/query_engine.py` | Modify | 仅增加 debug mode 的薄委托和最小上下文注入 |
| `src/embedagent/inprocess_adapter.py` | Modify | snapshot 中的 debug activity 字段同步 |
| `tests/test_harness_contracts.py` | Modify | 增加 debug mode 注册表断言 |
| `tests/test_phase_engine.py` | Modify | 增加 debug phase 推进断言 |
| `tests/test_tools_v2_runtime.py` | Modify | 增加 debug_lite pack 暴露断言 |
| `tests/test_query_engine_debug_lite.py` | Create | debug mode 薄集成测试 |

### Boundary Rules

- 不在 `query_engine.py` 中实现 debug phase 推进细节。
- 不在旧 `permissions.py` 中叠加 debug-specific 规则。
- 不新增“万能调试工具”；仍优先复用 V2 通用工具与现有 recipe/runtime。

---

## Task 1: 扩展 Harness registry，让 debug 成为正式的 V2 轨道

**Files:**
- Modify: `src/embedagent/harness/registry.py`
- Modify: `tests/test_harness_contracts.py`

- [ ] **Step 1: 先写失败测试**

```python
def test_debug_mode_defaults_to_lite_spec_tdd(self):
    from embedagent.harness.registry import build_default_registry
    registry = build_default_registry()
    self.assertEqual(
        registry["debug"].default_discipline.value,
        "lite_spec_tdd",
    )

def test_debug_mode_has_expected_lite_track(self):
    from embedagent.harness.registry import build_default_registry
    registry = build_default_registry()
    self.assertEqual(
        [phase.value for phase in registry["debug"].lite_track],
        ["reproduce", "isolate", "patch", "regression_check", "handoff"],
    )
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_harness_contracts -v`

Expected: `KeyError: 'debug'`

- [ ] **Step 3: 在 `registry.py` 增加 debug mode**

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 2: 扩展 phase engine，改为支持 debug 的 artifact 驱动推进

**Files:**
- Modify: `src/embedagent/harness/phase_engine.py`
- Modify: `tests/test_phase_engine.py`

- [ ] **Step 1: 写失败测试**

```python
def test_reproduce_advances_when_failing_evidence_exists(self):
    from embedagent.harness.contracts import ExecutionPhase
    from embedagent.harness.phase_engine import advance_phase
    next_phase = advance_phase(
        ExecutionPhase.REPRODUCE,
        {"failing_evidence_ready": True},
        "lite_spec_tdd",
    )
    self.assertEqual(next_phase.value, "isolate")

def test_patch_advances_when_regression_result_ready(self):
    from embedagent.harness.contracts import ExecutionPhase
    from embedagent.harness.phase_engine import advance_phase
    next_phase = advance_phase(
        ExecutionPhase.PATCH,
        {"regression_result_ready": True},
        "lite_spec_tdd",
    )
    self.assertEqual(next_phase.value, "regression_check")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_phase_engine -v`

Expected: assertions fail because debug transitions do not exist yet

- [ ] **Step 3: 在 `phase_engine.py` 追加 debug 分支**

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 3: 新增 debug_lite tool pack，不重新发明大而全调试工具

**Files:**
- Modify: `src/embedagent/tooling/packs.py`
- Modify: `src/embedagent/tools_v2/runtime.py`
- Modify: `tests/test_tools_v2_runtime.py`

- [ ] **Step 1: 写失败测试**

```python
def test_debug_lite_pack_exposes_read_edit_and_run_recipe(self):
    from embedagent.tools_v2.runtime import ToolRuntimeV2
    runtime = ToolRuntimeV2(self.workspace)
    names = [item["function"]["name"] for item in runtime.schemas_for_pack("debug_lite")]
    self.assertIn("read_file", names)
    self.assertIn("edit_file", names)
    self.assertIn("run_recipe", names)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_tools_v2_runtime -v`

Expected: assertion failure because `debug_lite` not defined

- [ ] **Step 3: 在 `packs.py` 增加 `DEBUG_LITE_PACK`**

建议组合：

- `read_file`
- `list_dir`
- `grep_text`
- `edit_file`
- `write_file`
- `run_recipe`
- `ask_user`
- `task_status`
- `glob_files`
- `list_recipes`

- [ ] **Step 4: 在 `runtime.py` 支持 `debug_lite`**

- [ ] **Step 5: 重新运行测试，确认通过**

---

## Task 4: 为 debug-lite 增加最小 failing-evidence 入口

**Files:**
- Modify: `src/embedagent/tools_v2/session_ops.py`
- Create: `tests/test_debug_evidence_v2.py`

- [ ] **Step 1: 写失败测试**

```python
def test_record_failing_evidence_returns_structured_payload(self):
    from embedagent.tools_v2.runtime import ToolRuntimeV2
    runtime = ToolRuntimeV2(self.workspace)
    result = runtime.execute(
        "record_failing_evidence",
        {"summary": "reproduced failure in src/demo.c"},
    )
    self.assertTrue(result.success)
    self.assertEqual(result.data.get("summary"), "reproduced failure in src/demo.c")
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 在 `session_ops.py` 增加 `record_failing_evidence`**

返回结构：

```python
{
    "summary": "...",
    "failing_evidence_ready": True,
}
```

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 5: 让 harness runner 能生成 debug-lite 上下文

**Files:**
- Modify: `src/embedagent/harness/runner.py`
- Create: `tests/test_harness_runner_debug.py`

- [ ] **Step 1: 写失败测试**

```python
def test_runner_builds_debug_mode_units(self):
    from embedagent.harness.runner import HarnessRunner
    runner = HarnessRunner()
    units = runner.build_mode_units("debug", [])
    self.assertTrue(any("Mode: debug" in item for item in units))
    self.assertTrue(any("lite_spec_tdd" in item for item in units))
```

- [ ] **Step 2: 运行测试，确认失败**

Expected: no debug units yet

- [ ] **Step 3: 扩展 `runner.py`，支持 debug**

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 6: 薄接入 QueryEngine / InProcessAdapter

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Create: `tests/test_query_engine_debug_lite.py`

- [ ] **Step 1: 写失败测试**

```python
def test_debug_mode_submit_turn_adds_harness_context(self):
    engine = QueryEngine(
        client=DoneClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    result = engine.submit_turn(
        user_text="开始 debug-lite",
        stream=False,
        initial_mode="debug",
    )
    system_messages = [message.content for message in result.session.messages if message.role == "system"]
    self.assertTrue(any("Mode: debug" in content for content in system_messages))
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 仅在 `_run_harness_mode()` 里接入 debug**

- [ ] **Step 4: adapter snapshot 同步 `debug` 的 `current_phase / discipline_profile / current_activity`**

- [ ] **Step 5: 重新运行测试，确认通过**

---

## Task 7: 运行第二条垂直切片的组合验证

**Files:** none

- [ ] **Step 1: 运行新切片测试**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_harness_contracts tests.test_phase_engine tests.test_tools_v2_runtime tests.test_debug_evidence_v2 tests.test_harness_runner_debug tests.test_query_engine_debug_lite -v`

- [ ] **Step 2: 运行定向旧回归**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor tests.test_permissions tests.test_tool_execution tests.test_tool_commit -v`

- [ ] **Step 3: 更新 tracker / change log**

- [ ] **Step 4: Commit**

```bash
git add docs/development-tracker.md docs/design-change-log.md src/embedagent/harness src/embedagent/tooling src/embedagent/tools_v2 src/embedagent/inprocess_adapter.py src/embedagent/query_engine.py tests
git commit -m "feat: add agent harness v2 debug-lite slice"
```
