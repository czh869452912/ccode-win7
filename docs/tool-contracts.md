# EmbedAgent 工具接口契约（Phase 4）

> 更新日期：2026-03-28（Phase 5B 修订）
> 适用阶段：Phase 4-5 工具与验证工具

---

## 1. 文档目标

记录当前已经实现的工具名称、参数和 Observation 结构，作为后续模式系统与前端展示的接口基线。

本文件聚焦已落地实现，不展开未来工具设计。

---

## 2. 当前已实现工具

### 2.1 文件工具

| 工具 | 作用 | 核心参数 |
|------|------|----------|
| `read_file` | 读取单个文本文件 | `path` |
| `list_files` | 列出目录下文件 | `path`, `pattern` |
| `search_text` | 搜索文本内容 | `query`, `path` |
| `edit_file` | 精确替换文件片段 | `path`, `old_text`, `new_text` |

### 2.2 命令与 Git 工具

| 工具 | 作用 | 核心参数 |
|------|------|----------|
| `run_command` | 执行工作区内 shell 命令 | `command`, `cwd`, `timeout_sec` |
| `git_status` | 查看当前仓库状态 | `path` |
| `git_diff` | 查看工作区或暂存区差异 | `path`, `scope` |
| `git_log` | 查看最近提交历史 | `path`, `limit` |

### 2.3 构建与质量工具

| 工具 | 作用 | 核心参数 |
|------|------|----------|
| `compile_project` | 执行编译并解析诊断 | `command`, `cwd`, `timeout_sec` |
| `run_tests` | 执行测试并汇总结果 | `command`, `cwd`, `timeout_sec` |
| `run_clang_tidy` | 执行 clang-tidy 并解析诊断 | `command`, `cwd`, `timeout_sec` |
| `run_clang_analyzer` | 执行 clang 静态分析并解析诊断 | `command`, `cwd`, `timeout_sec` |
| `collect_coverage` | 执行覆盖率命令并提取百分比 | `command`, `cwd`, `timeout_sec` |
| `report_quality` | 根据错误数、失败测试和覆盖率给出质量门结论 | `error_count`, `test_failures`, `warning_count`, `line_coverage`, `min_line_coverage` |

---

## 3. Observation 基线

所有工具统一返回：

```python
{
    "success": bool,
    "error": str | None,
    "data": dict
}
```

---

## 3.1 大输出 Artifact 规则

从 Phase 5B 开始，工具不会再把大体积 `content` / `stdout` / `stderr` / `diff` / `diagnostics` / `files` / `matches` / `entries` 原样长期留在会话里。

当这些字段超过内联阈值时，Observation 会改为：

- 保留脱敏后的预览内容
- 追加 `<field>_artifact_ref`，指向工作区内 `.embedagent/memory/artifacts/...` 的 JSON 文件
- 追加 `<field>_char_count` 或 `<field>_item_count` 之类的元数据

Artifact 文件同样会做基础脱敏，当前至少覆盖：

- `sk-...` 形式 key
- `Bearer ...` token
- `Authorization:` 头
- 常见 `api_key` / `secret` / `password` 赋值片段

模型若需要查看更多上下文，可通过 `read_file` 读取对应 `artifact_ref`。

---

## 4. 命令类工具 Observation

`run_command`、`git_status`、`git_diff`、`git_log`、`compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage` 都复用同一组基础字段：

```python
{
    "command": str,
    "cwd": str,
    "exit_code": int,
    "stdout": str,  # 可能是预览
    "stderr": str,  # 可能是预览
    "stdout_truncated": bool,
    "stderr_truncated": bool,
    "stdout_artifact_ref": str | None,
    "stderr_artifact_ref": str | None,
    "stdout_char_count": int | None,
    "stderr_char_count": int | None,
    "duration_ms": int,
    "timed_out": bool,
}
```

错误判定规则：

- `timed_out == True` -> 失败
- `exit_code != 0` -> 失败
- 否则 -> 成功

---

## 5. Git 工具扩展字段

### 5.1 `git_status`

额外字段：

```python
{
    "path": str,
    "branch": str,
    "entries": [
        {
            "status": str,
            "path": str,
        }
    ],
    "entries_artifact_ref": str | None,
    "entries_item_count": int | None,
}
```

### 5.2 `git_diff`

额外字段：

```python
{
    "path": str,
    "scope": "working" | "staged",
    "file_count": int,
    "line_count": int,
    "diff": str,  # 可能是预览
    "diff_artifact_ref": str | None,
    "diff_char_count": int | None,
}
```

### 5.3 `git_log`

额外字段：

```python
{
    "path": str,
    "limit": int,
    "entries": [
        {
            "commit": str,
            "author": str,
            "date": str,
            "subject": str,
        }
    ],
    "entries_artifact_ref": str | None,
    "entries_item_count": int | None,
}
```

---

## 6. 构建与质量工具扩展字段

### 6.1 `compile_project` / `run_clang_tidy` / `run_clang_analyzer`

额外字段：

```python
{
    "diagnostic_count": int,
    "error_count": int,
    "warning_count": int,
    "note_count": int,
    "diagnostics": [
        {
            "file": str,
            "line": int,
            "column": int,
            "level": "error" | "warning" | "note",
            "message": str,
        }
    ],
    "diagnostics_artifact_ref": str | None,
    "diagnostics_item_count": int | None,
}
```

### 6.2 `run_tests`

除诊断字段外，额外包含：

```python
{
    "test_summary": {
        "passed": int,
        "failed": int,
        "skipped": int,
        "total": int,
    }
}
```

### 6.3 `collect_coverage`

额外字段：

```python
{
    "coverage_summary": {
        "line_coverage": float | None,
        "function_coverage": float | None,
        "branch_coverage": float | None,
        "region_coverage": float | None,
    }
}
```

### 6.4 `report_quality`

返回：

```python
{
    "passed": bool,
    "error_count": int,
    "warning_count": int,
    "test_failures": int,
    "line_coverage": float | None,
    "min_line_coverage": float | None,
    "reasons": list[str],
}
```

说明：

- 该工具的 `success` 字段等同于质量门是否通过
- 若未通过，`error` 返回 `质量门未通过。`

---

## 7. 当前结论

当前工具集已经具备：

- 文件查看与精确编辑
- 命令执行与超时终止
- Git 状态、差异、日志查询
- 编译、测试、静态检查、覆盖率与质量门的第一版封装
- 面向模型和前端的结构化结果返回

下一步应在此基础上接入真实 Clang 构建命令与项目级默认配置，而不是重新退回到通用 `run_command`。
