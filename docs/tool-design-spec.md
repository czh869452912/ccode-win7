# EmbedAgent 工具设计规范

> 更新日期：2026-03-29
> 适用范围：所有 Agent 工具的设计、实现与 function calling schema 编写

---

## 1. 为什么工具设计是一等公民

本项目使用的内网模型（GLM5 int4 量化版、Qwen3.5 全量版）在 function calling 上的表现对工具集设计极为敏感：

- 工具集越小、越聚焦，调用成功率越高
- 工具描述越清晰、越具体，参数填写错误率越低
- 量化模型对歧义、嵌套、否定表达的容忍度明显低于非量化模型

因此，工具设计质量直接决定系统能否稳定工作，必须和架构设计同等对待。

---

## 2. 每个模式的工具数量上限

**每个模式严格控制在 5 个工具以内，目标 3-4 个。**

超过 5 个工具时，量化模型在工具选择上的准确率会明显下降——不是不调用，而是调用错工具或混淆参数。

### 各模式工具分配基线

| 模式 | 工具集 | 数量 |
|------|--------|------|
| `ask` | read_file, list_files, search_text, ask_user | 4 |
| `spec` | read_file, search_text, list_files, write_file, ask_user | 5 |
| `code` | read_file, write_file, edit_file, search_text, compile_project | 5 |
| `test` | read_file, write_file, edit_file, run_tests, search_text | 5 |
| `verify` | compile_project, run_tests, run_clang_tidy, report_quality | 4 |
| `debug` | read_file, search_text, run_command, write_file, edit_file | 5 |

仅 `orchestra` 额外提供：`switch_mode`（模式切换）

> **例外说明**：`manage_todos` 是协调工具，在 `orchestra` 和 `code` 模式中使用。
> `code` / `orchestra` 模式因此会超出目标数量上限，属于明确例外——
> `manage_todos` 以任务状态跟踪为主，不影响模型对领域工具的选择判断。

---

## 3. 工具命名规范

- 全英文，`snake_case`
- 格式：`动词_名词`，如 `read_file`、`run_tests`、`list_files`
- 不使用缩写，不使用复合动词
- 同一语义的参数在所有工具中必须使用同一命名（统一用 `path`，不混用 `file_path` / `filepath`）

---

## 4. 工具描述模板

每个工具的 `description` 必须按以下结构编写（固定顺序）：

1. **一句话定义**：动词开头，说明工具做什么，≤20 字
2. **补充说明**：精确补充适用场景，≤30 字
3. **约束提示**（可省略）：说明使用限制，≤20 字

**语言**：中文描述，英文命名。GLM5 / Qwen3.5 在中文描述下语义理解更稳定。

### 完整示例

```python
{
    "name": "edit_file",
    "description": "修改文件中的指定内容。用于替换、插入或删除文件某段文本。仅在当前模式的可写范围内使用。",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要修改的文件路径，相对于项目根目录。示例：src/main.c"
            },
            "old_text": {
                "type": "string",
                "description": "要被替换的原始文本，必须与文件中的内容完全一致，包括缩进和换行。"
            },
            "new_text": {
                "type": "string",
                "description": "替换后的新文本。如果要删除内容，传入空字符串。"
            }
        },
        "required": ["path", "old_text", "new_text"]
    }
}
```

### 参数描述格式

每个参数的 `description` 必须包含：

1. 语义说明（这个参数是什么）
2. 格式或约束（如"相对路径"、"必须完全一致"）
3. **一个具体示例**（示例：xxx）

字符数限制：工具名 + description + 所有参数描述合计不超过 300 token。

---

## 5. 禁止的工具设计模式

以下设计模式会导致量化模型调用失败，**项目中禁止使用**：

| 反模式 | 具体表现 | 后果 |
|--------|----------|------|
| **多功能合并工具** | `file_op(op: "read/write/delete")` 用枚举控制行为 | 量化模型乱填枚举值 |
| **参数命名不一致** | 同一概念在不同工具中叫 `path`、`file_path`、`filepath` | 跨工具调用时混淆参数名 |
| **可选参数过多** | 一个工具有超过 3 个可选参数 | 漏填或错填关键可选参数 |
| **功能重叠的工具** | `search_text` 和 `grep_code` 都能搜索内容 | 模型随机选择，行为不可预测 |
| **枚举值写在 description** | 把枚举值列在描述里而不是 `enum` 字段 | 模型忽略，产生无效值 |
| **嵌套对象参数** | `options: { format: string, encoding: string }` | 量化模型展平或省略嵌套层 |
| **否定限定描述** | "不要用于大文件"、"不应在 debug 模式使用" | 量化模型对否定限定遵守率极低 |
| **语义上必填但标注 optional** | 逻辑上必须提供却没有写进 `required` | 模型以为可以省略，产生无效调用 |

---

## 6. 参数设计规则

- 参数数量不超过 5 个（必填 + 可选合计）
- 超过 5 个参数时，考虑拆分为两个工具
- 所有参数展平为顶层字段，不使用嵌套对象
- 枚举值必须写在 `enum` 字段，不能只写在 description
- `required` 字段必须准确，不允许"逻辑必填但代码 optional"

---

## 7. 工具返回值规范（Observation 结构）

工具执行后必须返回结构化 Observation，不允许只返回原始终端文本。

### 通用字段

```python
{
    "success": bool,          # 工具是否成功执行
    "error": str | None,      # 失败时的错误信息（一句话，中文）
    "data": dict | str        # 实际返回内容
}
```

### 编译类工具的扩展字段

```python
{
    "success": bool,
    "exit_code": int,
    "command": str,
    "stdout": str,
    "stderr": str,
    "error_count": int,
    "diagnostics": [
        {
            "file": str,
            "line": int,
            "column": int,
            "level": "error" | "warning" | "note",
            "message": str
        }
    ],
    "duration_ms": int
}
```

结构化 Observation 有两个作用：
1. Agent 可以基于字段做精确决策（如判断 error_count）
2. 前端可以渲染为格式化展示，而不是原始终端文本

---

## 8. 工具审查清单

新增工具前，逐项确认：

- [ ] 工具名是 `动词_名词` 格式，全英文 `snake_case`
- [ ] 工具所属模式的工具总数 ≤ 5 个
- [ ] description 符合三段结构，总 token ≤ 300
- [ ] 每个参数有语义说明 + 格式说明 + 示例
- [ ] `required` 字段准确，无逻辑必填但标注 optional 的参数
- [ ] 无嵌套对象参数
- [ ] 枚举值写在 `enum` 字段
- [ ] 参数总数 ≤ 5 个
- [ ] 与现有工具无功能重叠
- [ ] 所有工具中同一语义的参数名一致
- [ ] 无否定限定描述
- [ ] 返回值是结构化 Observation，非原始文本

---

## 9. 工具模块组织（tools/ 包结构）

工具按职责拆分到独立模块，禁止将所有工具堆放在单一文件中：

```
src/embedagent/tools/
├── __init__.py      # 仅导出 ToolRuntime, ToolDefinition（保持外部 API 稳定）
├── _base.py         # ToolDefinition、ToolContext（共享 helper）、常量
├── file_ops.py      # read_file, list_files, search_text, write_file, edit_file
├── shell_ops.py     # run_command
├── git_ops.py       # git_status, git_diff, git_log
├── build_ops.py     # compile_project, run_tests, clang-tidy, clang-analyzer, coverage, report_quality
├── todo_ops.py      # manage_todos
└── runtime.py       # ToolRuntime（组装所有模块，提供 schemas() 和 execute()）
```

### 新增工具的标准流程

1. **选择或新建 ops 模块**：功能归属明确时加入已有模块（≤6 个工具），否则新建 `xxx_ops.py`。
2. **在 `build_tools(ctx)` 函数中**定义 handler 闭包和 ToolDefinition，加入返回列表。
3. **在 `runtime.py` 的 `__init__` 中**引入新模块并加入工具列表。
4. **在 `context.py` 的 `ReducerRegistry`** 中注册对应的 `_reduce_xxx` 方法。
5. **在 `modes.py`** 的对应模式 `allowed_tools` 中添加工具名。

### ToolContext 说明

`ToolContext`（`_base.py`）封装了所有工具共享的 helper：路径解析、文本读写、
子进程执行、诊断解析、输出压缩等。各 ops 模块通过 `ctx` 参数获得这些能力，
**不直接操作文件系统或子进程**，保持模块间解耦。
