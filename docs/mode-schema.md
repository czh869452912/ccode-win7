# EmbedAgent Mode Schema（Phase 3）

> 更新日期：2026-03-28
> 适用阶段：Phase 3 模式系统 v1

---

## 1. 文档目标

记录当前 `MODE_REGISTRY` 的最小字段、默认模式和各模式职责边界，作为后续 Harness 扩展的基线。

本版本只描述 Phase 3 已落地的 Python dict 结构，不涉及 TOML 加载。

---

## 2. 当前结构

当前实现位于：

- `src/embedagent/modes.py`

`MODE_REGISTRY` 采用：

```python
{
    "mode_name": {
        "slug": str,
        "system_prompt": str,
        "allowed_tools": list[str],
        "writable_globs": list[str],
    }
}
```

---

## 3. 字段说明

### 3.1 `slug`

- 模式唯一标识
- 当前实现中与字典 key 保持一致

### 3.2 `system_prompt`

- 当前模式的专属行为约束
- 在进入模式时追加到会话中，作为新的 system message

### 3.3 `allowed_tools`

- 当前模式可见的真实工具名列表
- `switch_mode` 不写入该字段，而是由系统自动附加

### 3.4 `writable_globs`

- 当前模式允许 `edit_file` 写入的路径范围
- 空列表表示当前模式只读

---

## 4. 当前默认模式

- 默认模式：`code`

原因：

- 当前仓库的主任务仍是实现核心代码
- `code` 模式具备 `read_file`、`edit_file`、`search_text`、`run_command`
- 若任务需要 Git 或更强约束，模型或用户可显式切换模式

---

## 5. 当前模式清单

| 模式 | 当前职责 | 允许工具 | 可写范围 |
|------|----------|----------|----------|
| `ask` | 澄清信息缺口 | `read_file`, `list_files`, `search_text` | 只读 |
| `orchestra` | 拆解任务与路由模式 | `read_file`, `list_files`, `search_text`, `git_status` | 只读 |
| `spec` | 规格与文档整理 | `read_file`, `list_files`, `search_text`, `edit_file` | `docs/**/*.md`, `README.md` |
| `code` | 最小实现生产代码 | `read_file`, `edit_file`, `search_text`, `run_command` | `src/**/*.py`, `pyproject.toml` |
| `test` | 测试与复现路径 | `read_file`, `edit_file`, `search_text`, `run_command` | `tests/**/*.py`, `src/**/*.py` |
| `verify` | 检查命令与 Git 结果 | `run_command`, `git_status`, `git_diff`, `git_log` | 只读 |
| `debug` | 复现、定位、最小修复 | `read_file`, `search_text`, `edit_file`, `run_command` | `src/**/*.py`, `tests/**/*.py` |
| `compact` | 上下文压缩与整理 | `read_file`, `list_files`, `search_text` | 只读 |

---

## 6. 当前结论

Phase 3 的 Mode Schema 已满足：

- 模式注册表存在且可枚举
- 每个模式有独立 system prompt
- 工具集按模式过滤
- `edit_file` 按 `writable_globs` 执行约束

下一阶段应在此基础上实现更完整的 Harness，而不是回退到单一大 prompt。
