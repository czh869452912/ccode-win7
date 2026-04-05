# Transcript-Truth Tool Result Cutover 代码审阅结论

> 审阅日期：2026-04-05
> 审阅范围：`docs/superpowers/plans/2026-04-05-transcript-truth-tool-result-cutover.md` 及对应代码变更
> 状态：核心竞争问题已解决，存在若干后续跟进项

---

## 1. 原始问题根因与本轮修复对照

### 1.1 用户报告的故障现象

在一个 turn 的一个 step 中触发多个工具调用时，出现**一个成功，后续全部失败**的情况。典型错误日志：

```text
Read File src/input.c              done
Read File src/render.c             error: WinError 2  系统找不到指定的文件。: '...artifacts\index.json.tmp' -> '...artifacts\index.json'
Read File src/utils.c              error: WinError 32 另一个程序正在使用此文件，进程无法访问。: '...artifacts\index.json.tmp' -> '...artifacts\index.json'
```

### 1.2 旧架构的根因分析

旧架构中，`ToolRuntime.execute()` 在工具执行阶段直接调用 `ToolContext.shrink_observation()`，后者会：

1. 将大字段写入 workspace-wide 的共享目录 `.embedagent/memory/artifacts/`
2. 通过 `read-modify-write` 更新共享的 `artifacts/index.json`
3. 使用固定名称的 temp 文件（`index.json.tmp`）进行替换

这导致被标记为 `read_only` 和 `concurrency_safe` 的工具，在**执行阶段仍然有共享文件写入的副作用**。多个线程并行执行时，`index.json.tmp` 成为单一可变热点，Windows 下极易触发 `WinError 2/32`。

### 1.3 本轮重构的关键修复（已验证通过）

| 设计目标 | 实现状态 | 关键代码位置 |
|---------|---------|-------------|
| **删除 `ArtifactStore` 运行时热路径** | `src/embedagent/artifacts.py` 已删除；`ToolRuntime` 不再导入 `ArtifactStore` | `src/embedagent/tools/runtime.py` |
| **工具执行层只返回原始结果，不做持久化** | `ToolContext` 已移除 `shrink_observation`、`shrink_text_field` 等辅助函数 | `src/embedagent/tools/_base.py` |
| **所有共享状态写入串行化** | `ToolCommitCoordinator.commit()` 内部持有 `threading.Lock()` | `src/embedagent/tool_commit.py:11-16, 62` |
| **大字段写入会话本地文件，永不覆盖** | `ToolResultStore._write_if_absent()` 使用 `io.open(path, "x", ...)`；`FileExistsError` 被静默忽略 | `src/embedagent/tool_result_store.py:63-69` |
| **投影元数据从共享 JSON 迁移到 SQLite** | `ProjectionDb` 替代 `artifacts/index.json`，自带实例级锁 | `src/embedagent/projection_db.py` |
| **Resume 不再降级到 summary-only** | `session_restore.py` 对空或异常 transcript 直接抛错；`inprocess_adapter.py` 不再合成空会话 | `src/embedagent/session_restore.py` / `src/embedagent/inprocess_adapter.py:255-262` |
| **Context 使用 transcript 记录的 replacement text** | `context.py` 从 `session.content_replacements` 直接读取 `replacement_text` 作为 prompt truth | `src/embedagent/context.py:678-690` |

### 1.4 新运行时的并发数据流

```
并行执行阶段（安全并发）
    └─> StreamingToolExecutor 并发跑工具
        └─> 只产生原始 Observation，不写任何共享文件

串行提交阶段（单写锁保护）
    └─> QueryEngine._record_tool_observation()
        └─> ToolCommitCoordinator.commit() [threading.Lock]
            ├─> Materialize 大字段到 sessions/<sid>/tool-results/<call_id>/<field>.txt
            ├─> 追加 tool_result / content_replacement 到 transcript.jsonl
            ├─> 更新 Session 内存状态
            └─> 刷新 SQLite 投影（最佳努力，失败被吞掉）
```

**结论**：由于并行执行层和共享文件写入已完全解耦，原始 `index.json.tmp` 的竞争场景已不可能再发生。

---

## 2. 未完全消除的潜在风险

核心问题虽已解决，但代码库中仍存在以下值得关注的残留或新引入的风险点。

### 2.1 `session_store.py` 仍保留一个共享可变 JSON 索引

`SessionSummaryStore._update_index()` 仍在用 `_atomic_write_json()` 写 `.embedagent/memory/sessions/index.json`：

- 虽然它已不在工具执行热路径中，由 `_persist_summary()` 在主线程串行调用
- 但本质上仍是**共享可变 JSON 文件**
- 若未来出现多 Session 并发写同一工作区，仍可能在 `os.replace` 步骤遇到竞争

**建议**：后续将会话列表索引完全迁移到 `ProjectionDb` 的 `session_projection` 表，彻底消除 JSON 索引残留。

### 2.2 `project_memory.py` 直接写 JSON 且无文件级锁

`ProjectMemoryStore.refresh()` 和 `cleanup()` 会直接覆盖以下文件：
- `project-profile.json`
- `command-recipes.json`
- `known-issues.json`
- `memory-index.json`

存在两个问题：
1. 写操作**未使用 temp/rename 原子写**
2. 实例级**没有 threading lock**

当前它只在 `QueryEngine._persist_summary()` 的串行流程中被调用，风险较低；但如果 CLI 命令或外部脚本并发触发 `refresh`，文件损坏风险将暴露。不过这与本次**并行工具执行**的问题无关。

**建议**：将 `project_memory` 的 recipes 和 issues 迁移到 `ProjectionDb`（设计文档中已有 `project_memory_recipe` / `project_memory_issue` 表定义），同时删除 JSON 文件投影。

### 2.3 前端 API 中残留旧字段名

`src/embedagent/inprocess_adapter.py:1592` 仍有：

```python
"diff_artifact_ref": str(diff_data.get("diff_artifact_ref") or ""),
```

这是旧 `ArtifactStore` 命名约定的残留。底层值实际来源于 `diff_stored_path`，因此**不影响运行时的存储竞争**。但这是一个命名债务，长期可能导致维护者误解数据链路。

**建议**：统一替换为 `diff_stored_path`，并同步更新前端 GUI/TUI 的引用点。

### 2.4 `ToolResultStore` 的 "write-if-absent" 语义假设

`_write_if_absent()` 在并发时只保证一个线程成功创建文件，另一个遇到 `FileExistsError` 后忽略。这里有一个隐含假设：

> **同一个 `(session_id, tool_call_id, field_name)` 对应的内容永远相同。**

如果未来同一个 `call_id` 被重复提交且内容不同，第二次的变更会被**静默丢弃**。当前架构下该假设成立（`call_id` 是 `uuid` 生成），但如果 retry/replay 逻辑设计不当，可能成为隐蔽 bug。

**建议**：在 `tool_commit.py` 的 commit 日志或 debug 输出中，为 `FileExistsError` 场景添加一条 trace 级别的日志，以便在异常调查时快速识别重复 materialization。

### 2.5 `tool_commit.py` 的单写锁可能成为新的性能瓶颈

所有工具提交（transcript 追加、文件 IO、SQLite upsert）都在同一把 `threading.Lock()` 下：

- 这是设计方案的意图（正确性优先于极致并行度）
- 但如果 SQLite 投影写入因磁盘繁忙或 `SQLITE_BUSY` 变慢，会阻塞后续所有工具结果的提交

**建议**：若后续在高并发场景下观察到明显感觉，可考虑将 **projection refresh** 从锁内拆出为锁外 best-effort 异步刷新（设计文档 §7.3 也允许此做法），仅保持 transcript + tool-result files 在锁内。

---

## 3. 验证结果

### 3.1 单元测试

```text
tests.test_tool_result_store                    OK
tests.test_projection_db                        OK
tests.test_tool_commit                          OK
tests.test_query_engine_refactor                OK
tests.test_inprocess_adapter_frontend_api       OK
────────────────────────────────────────────────
Ran 83 tests in 15.426s
OK
```

### 3.2 集成验证脚本

```text
.venv/Scripts/python.exe scripts/validate-phase5.py   PASS (exit 0)
.venv/Scripts/python.exe scripts/validate-phase6.py   PASS (exit 0)
```

---

## 4. 总结与建议

1. **核心问题已解决**：并行工具调用不再竞争任何共享可变文件。原始的 `artifacts/index.json.tmp` 路径已彻底从运行时热路径中移除。
2. **架构方向正确**：执行层纯化 + 单写协调器 + 会话本地存储 + SQLite 投影，符合 `transcript-truth-tool-result-cutover` 设计文档的核心决策。
3. **建议后续跟进**：
   - 将会话索引和 project-memory 的 JSON 投影完全迁移到 SQLite
   - 清理前端 API 中残留的 `*_artifact_ref` 字段名
   - 评估是否需要将 projection refresh 从单写锁中拆出，以优化高并发性能
