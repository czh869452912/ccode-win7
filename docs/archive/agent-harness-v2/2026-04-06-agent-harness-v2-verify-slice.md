# Agent Harness V2 Verify Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Agent Harness V2 落地 `verify` 垂直切片：提供只读验证轨道、verify tool pack、最小质量门上下文与薄集成桥接。

**Architecture:** 本切片继续沿用新的 `harness/`、`tooling/`、`tools_v2/` 结构。`verify` 的 phase、pack 和上下文逻辑都放在这些新包里，旧 `QueryEngine` / `InProcessAdapter` 只接收最小投影字段与 system context 注入。verify 不直接修改源码，不向旧 `permissions.py` 注入新规则。

**Tech Stack:** Python 3.8, unittest, existing `ToolContext`, recipe helpers, current `Session` / `QueryEngine` / `InProcessAdapter`

---

## Scope

本计划只实现：

- `verify` mode 的最小可运行垂直切片
- verify phases：`select_recipe -> execute -> summarize`
- verify tool pack
- verify 的最小 summary / quality context
- adapter snapshot 中的 verify activity 可见字段

本计划不实现：

- 真实 `report_quality` 的 V2 重构
- 更细粒度的 coverage/report artifact graph
- 前端大改

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/embedagent/tooling/packs.py` | Modify | 新增 `VERIFY_PACK` |
| `src/embedagent/tools_v2/recipe_ops.py` | Modify | 最小 `report_quality_v2` 入口 |
| `src/embedagent/tools_v2/runtime.py` | Modify | pack-aware schema 暴露 verify |
| `src/embedagent/harness/runner.py` | Modify | verify mode 的 units 构建 |
| `src/embedagent/query_engine.py` | Modify | `_run_harness_mode()` 薄接入 verify |
| `src/embedagent/inprocess_adapter.py` | Modify | `create_session("verify")` 与 snapshot activity |
| `tests/test_tools_v2_runtime.py` | Modify | verify pack 断言 |
| `tests/test_harness_runner_verify.py` | Create | verify units 断言 |
| `tests/test_query_engine_verify_slice.py` | Create | verify 集成断言 |

### Boundary Rules

- 不在旧 `build_ops.py` / `report_quality` 上叠 V2 逻辑。
- 不在 `query_engine.py` 中实现 verify phase 状态机。
- 不让 verify 切片修改任何写入边界和旧 permission 主线。

---

## Task 1: 定义 verify pack

**Files:**
- Modify: `src/embedagent/tooling/packs.py`
- Modify: `tests/test_tools_v2_runtime.py`

- [ ] **Step 1: 写失败测试**

```python
def test_verify_pack_exposes_run_recipe_and_list_recipes(self):
    from embedagent.tools_v2.runtime import ToolRuntimeV2
    runtime = ToolRuntimeV2(self.workspace)
    names = [item["function"]["name"] for item in runtime.schemas_for_pack("verify")]
    self.assertIn("run_recipe", names)
    self.assertIn("list_recipes", names)
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 在 `packs.py` 增加 `VERIFY_PACK`**

建议包含：

- `list_recipes`
- `run_recipe`
- `task_status`
- `ask_user`

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 2: 为 V2 runtime 增加最小质量门工具入口

**Files:**
- Modify: `src/embedagent/tools_v2/recipe_ops.py`
- Modify: `src/embedagent/tools_v2/runtime.py`
- Create: `tests/test_verify_quality_v2.py`

- [ ] **Step 1: 写失败测试**

```python
def test_report_quality_v2_returns_structured_summary(self):
    from embedagent.tools_v2.runtime import ToolRuntimeV2
    runtime = ToolRuntimeV2(self.workspace)
    result = runtime.execute(
        "report_quality_v2",
        {"error_count": 0, "warning_count": 1, "test_failures": 0},
    )
    self.assertTrue(result.success)
    self.assertIn("passed", result.data)
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 在 `recipe_ops.py` 增加 `report_quality_v2`**

最小返回结构：

```python
{
    "passed": bool,
    "error_count": int,
    "warning_count": int,
    "test_failures": int,
}
```

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 3: 扩展 runner，让 verify 也能生成稳定 mode context

**Files:**
- Modify: `src/embedagent/harness/runner.py`
- Create: `tests/test_harness_runner_verify.py`

- [ ] **Step 1: 写失败测试**

```python
def test_runner_builds_verify_units(self):
    from embedagent.harness.runner import HarnessRunner
    runner = HarnessRunner()
    units = runner.build_mode_units("verify", [])
    self.assertTrue(any("Mode: verify" in item for item in units))
    self.assertTrue(any("select_recipe" in item for item in units))
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 在 runner 中为 verify 选择 `verify` pack**

- [ ] **Step 4: 重新运行测试，确认通过**

---

## Task 4: 薄接入 QueryEngine / Adapter

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Create: `tests/test_query_engine_verify_slice.py`

- [ ] **Step 1: 写失败测试**

```python
def test_verify_mode_submit_turn_adds_verify_context(self):
    engine = QueryEngine(
        client=DoneClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    result = engine.submit_turn(
        user_text="开始 verify",
        stream=False,
        initial_mode="verify",
    )
    system_messages = [message.content for message in result.session.messages if message.role == "system"]
    self.assertTrue(any("Mode: verify" in content for content in system_messages))

def test_adapter_snapshot_exposes_verify_activity(self):
    adapter = InProcessAdapter(
        client=DoneClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    snapshot = adapter.create_session("verify")
    self.assertEqual(snapshot["current_mode"], "verify")
    self.assertTrue(snapshot["current_activity"])
```

- [ ] **Step 2: 运行测试，确认失败**

- [ ] **Step 3: 在 `_run_harness_mode()` 中接 verify**

- [ ] **Step 4: 在 adapter create_session 里补 verify 的 `current_phase / discipline_profile / current_activity`**

- [ ] **Step 5: 重新运行测试，确认通过**

---

## Task 5: 组合验证

**Files:** none

- [ ] **Step 1: 运行 verify 新切片测试**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_tools_v2_runtime tests.test_verify_quality_v2 tests.test_harness_runner_verify tests.test_query_engine_verify_slice -v`

- [ ] **Step 2: 运行既有 Harness V2 测试**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_harness_contracts tests.test_phase_engine tests.test_task_graph_v2 tests.test_harness_runner_taskgraph tests.test_query_engine_build_lite tests.test_query_engine_debug_lite tests.test_query_engine_build_full_spec -v`

- [ ] **Step 3: 运行定向旧回归**

Run:

`D:\Claude-project\ccode-win7\.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor tests.test_permissions tests.test_tool_execution tests.test_tool_commit -v`

- [ ] **Step 4: 更新 tracker / change log**

- [ ] **Step 5: Commit**

```bash
git add docs/development-tracker.md docs/design-change-log.md docs/superpowers/plans/2026-04-06-agent-harness-v2-verify-slice.md src/embedagent/harness src/embedagent/tooling src/embedagent/tools_v2 src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests
git commit -m "feat: add agent harness v2 verify slice"
```
