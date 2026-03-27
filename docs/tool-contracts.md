# EmbedAgent 工具接口契约（Phase 2）

> 更新日期：2026-03-27
> 适用阶段：Phase 2 工具集 v1

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

## 4. 命令类工具 Observation

`run_command`、`git_status`、`git_diff`、`git_log` 都复用同一组基础字段：

```python
{
    "command": str,
    "cwd": str,
    "exit_code": int,
    "stdout": str,
    "stderr": str,
    "stdout_truncated": bool,
    "stderr_truncated": bool,
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
    ]
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
    "diff": str,
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
    ]
}
```

---

## 6. 当前结论

Phase 2 的工具集 v1 已经具备：

- 文件查看与精确编辑
- 命令执行与超时终止
- Git 状态、差异、日志查询
- 面向模型和前端的结构化结果返回

下一步应在此基础上进入模式系统 v1，而不是继续扩充无约束工具数量。
