# EmbedAgent 配置指南

EmbedAgent 通过分层配置管理 LLM 连接参数、上下文窗口设置和模式行为，
无需修改源码即可适配不同模型和项目布局。

---

## 配置优先级

优先级从低到高：

```
代码内置默认值
  ↑
用户级配置  (~/.embedagent/config.json)
  ↑
项目级配置  (<workspace>/.embedagent/config.json)
  ↑
环境变量    (EMBEDAGENT_*)
  ↑
CLI 参数    (--max-context-tokens 等)
```

后者覆盖前者，CLI 参数始终优先。

---

## 配置文件位置

| 级别 | 路径 | 作用域 |
|------|------|--------|
| 用户级 | `~/.embedagent/config.json` | 对该用户所有项目生效 |
| 项目级 | `<workspace>/.embedagent/config.json` | 仅对当前项目生效 |

配置文件在 `embedagent` 启动时自动加载，**无需重启**即可修改（每次调用重新读取）。

---

## 完整 JSON Schema

```json
{
  "base_url": "string",
  "api_key": "string",
  "model": "string",
  "timeout": 120,
  "max_context_tokens": 18000,
  "reserve_output_tokens": 2000,
  "chars_per_token": 3.0,
  "max_recent_turns": 4,
  "max_turns": 8,
  "default_mode": "explore",
  "mode_writable_globs": {
    "<mode_name>": ["glob_pattern", "..."]
  },
  "mode_extra_writable_globs": {
    "<mode_name>": ["glob_pattern", "..."]
  }
}
```

所有字段均为可选，未设置的字段使用代码内置默认值。

---

## 字段说明

### LLM 连接

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `base_url` | string | `http://127.0.0.1:8000/v1` | 模型服务根地址 |
| `api_key` | string | `""` | API Key |
| `model` | string | `""` | 模型名称，**必须设置** |
| `timeout` | number | `120` | 请求超时秒数 |

环境变量等效：`EMBEDAGENT_BASE_URL`、`EMBEDAGENT_API_KEY`、`EMBEDAGENT_MODEL`、`EMBEDAGENT_TIMEOUT`。

### 上下文窗口

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_context_tokens` | integer | `18000` | 总上下文 token 预算 |
| `reserve_output_tokens` | integer | `2000` | 为模型输出预留的 token |
| `chars_per_token` | number | `3.0` | 字符/token 估算比率 |
| `max_recent_turns` | integer | `4` | 保留为完整历史的最近轮数 |

> **提示**：使用支持 32k/128k 上下文的模型时，将 `max_context_tokens` 调大可显著
> 减少上下文压缩频率，从而提高大文件分析的准确性。

### 循环控制

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_turns` | integer | `8` | 单次会话允许的最大工具调用轮数 |
| `default_mode` | string | `"explore"` | 启动时的默认模式 |

### 模式可写路径覆盖

`mode_writable_globs` 允许按模式自定义可写文件的 glob 匹配规则，**完全替换**该模式的内置默认值。

```json
{
  "mode_writable_globs": {
    "code": ["**/*.py", "**/*.toml", "**/*.cfg"],
    "spec": ["**/*.md", "**/*.rst", "docs/**/*.txt"]
  }
}
```

- **glob 语法**：使用 Python `fnmatch` 规则，`*` 匹配任意字符（含 `/`），`?` 匹配单字符。
- **只覆盖指定模式**：未指定的模式继续使用内置默认值。
- **空列表 = 只读**：`"code": []` 将使 code 模式无法写入任何文件。

`mode_extra_writable_globs` 用于在保留内置默认值的前提下，**增量追加**额外可写 glob。

```json
{
  "mode_extra_writable_globs": {
    "code": ["**/*.cmake", "CMakeLists.txt"],
    "spec": ["**/*.adoc"]
  }
}
```

- **不会替换默认值**：它只在已有默认范围上追加。
- **适合项目异构结构**：例如只想给 code 模式增加 `cmake/` 文件，而不想整份重写默认规则。

---

## 内置默认可写路径

| 模式 | 默认可写扩展名/文件 |
|------|------------------|
| `explore` | （只读） |
| `spec` | `**/*.md`、`**/*.rst`、`**/*.txt` |
| `code` | 常见源码、脚本、JSON/YAML、TOML/INI/CFG、CMake/Makefile 类文件 |
| `debug` | 常见源码、脚本、JSON/YAML、TOML/INI/CFG、CMake/Makefile 类文件 |
| `verify` | （只读） |

---

## 常用场景示例

### 场景 1：大上下文模型（32k token）

`~/.embedagent/config.json`:
```json
{
  "base_url": "http://127.0.0.1:8000/v1",
  "model": "qwen3.5-72b-coder",
  "max_context_tokens": 32000,
  "reserve_output_tokens": 4000,
  "max_recent_turns": 8
}
```

### 场景 2：非标准项目目录结构（增量追加）

项目根目录的 `.embedagent/config.json`:
```json
{
  "mode_extra_writable_globs": {
    "code": ["**/*.cmake", "CMakeLists.txt", "cmake/**/*.txt"],
    "spec": ["**/*.adoc"]
  }
}
```

### 场景 3：只允许修改特定子目录

```json
{
  "mode_writable_globs": {
    "code": ["src/mymodule/**/*.py"],
    "test": ["tests/unit/**/*.py", "tests/integration/**/*.py"]
  }
}
```

---

## CLI 参数快速参考

以下 CLI 参数会覆盖配置文件中的对应值：

```
--max-context-tokens INT    上下文 token 总量
--reserve-output-tokens INT 输出预留 token
--chars-per-token FLOAT     字符/token 比率
--max-turns INT             最大循环轮数
--mode STR                  初始模式
```

---

## manage_todos 工具使用指引

`manage_todos` 工具用于在多步任务中维护显式任务清单。

当前默认语义已经改为**会话级隔离**：

- 真实会话运行时，数据持久化到
  `<workspace>/.embedagent/memory/sessions/<session_id>/todos.json`
- 只有脱离会话上下文、直接调用工具运行时时，才会退回旧的
  `<workspace>/.embedagent/todos.json`

### 使用场景

- **explore 模式**：探索代码库后用 `add` 记录发现的问题或改进点，方便后续切换到具体模式处理；
- **code 模式**：长实现序列中用 `complete` 标记已完成项，避免遗漏；
- **会话恢复**：恢复会话后 `list` 查看该 session 未完成项，快速回到上下文。

### 操作示例

```
# 列出当前会话的所有任务
manage_todos(action="list")

# 添加任务
manage_todos(action="add", content="实现 UserService.login 方法")
manage_todos(action="add", content="为 login 编写单元测试")
manage_todos(action="add", content="更新 API 文档")

# 完成任务 (id=1)
manage_todos(action="complete", item_id=1)

# 删除任务 (id=3)
manage_todos(action="remove", item_id=3)
```

### 注意事项

- `todos.json` 是项目级持久化文件，可随项目 git 提交（或加入 `.gitignore`）；
- `remove` 操作会重新编号剩余条目（从 1 开始），建议在完成前不要依赖固定 id；
- 若前端 / Runtime 已注入 `session_id`，`manage_todos` 默认只读写当前会话的 todo 文件，不会污染其他会话；
- 工具在所有模式下均可用；`mode_writable_globs` 仅影响 `write_file` / `edit_file` 的路径白名单，不影响 `manage_todos`。
