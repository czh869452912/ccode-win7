# EmbedAgent Mode Schema

> 更新日期：2026-03-29
> 适用阶段：Phase 3 模式系统 v2（配置驱动）

---

## 1. 文档目标

记录当前模式注册表的结构、默认模式集及其职责边界，作为 Harness 扩展和项目定制的基线。

本版本描述 Phase 3 v2 已落地的实现：内置 Python dict + JSON 配置文件覆盖层。

---

## 2. 实现位置

- 内置模式定义：`src/embedagent/modes.py`（`_BUILTIN_MODES`）
- 配置加载函数：`src/embedagent/modes.py`（`initialize_modes(workspace)`）
- 提示词框架模板（可选覆盖）：`~/.embedagent/prompt_frame.txt`

---

## 3. 注册表结构

每个模式条目包含：

```python
{
    "slug": str,           # 模式唯一标识，与 key 保持一致
    "system_prompt": str,  # 模式专属行为约束，在进入模式时追加为 system message
    "allowed_tools": list, # 当前模式可见工具名列表（包含 ask_user、manage_todos）
    "writable_globs": list, # write_file / edit_file 的路径白名单（扩展名通配，不绑定目录）
}
```

---

## 4. 默认模式

- 默认模式：`explore`

原因：
- 用户在开始一个 session 时往往没有明确的任务类型（探索、讨论、阅读代码）
- `explore` 提供全读权限，不写文件，适合模糊入口
- 当用户明确了任务，通过 `/mode <name>` 或 `ask_user` 选项切换到具体模式

---

## 5. 当前模式清单

| 模式 | 职责 | 允许工具 | 可写范围 |
|------|------|----------|----------|
| `explore` | 探索代码库、解释逻辑、讨论设计、模糊 session 入口 | `read_file`, `list_files`, `search_text`, `manage_todos`, `ask_user` | 只读 |
| `spec` | 需求整理、验收标准、文档维护 | `read_file`, `list_files`, `search_text`, `write_file`, `manage_todos`, `ask_user` | `**/*.md`, `**/*.rst`, `**/*.txt` |
| `code` | C 语言实现、构建系统改动 | `read_file`, `list_files`, `write_file`, `edit_file`, `search_text`, `compile_project`, `manage_todos`, `ask_user` | 常见源码/构建配置类型（不绑定目录） |
| `debug` | 问题复现、根因定位、最小修复 | `read_file`, `list_files`, `search_text`, `write_file`, `edit_file`, `run_command`, `manage_todos`, `ask_user` | 同 `code` |
| `verify` | 构建、测试、静态检查、质量门（只读） | `compile_project`, `run_tests`, `run_clang_tidy`, `report_quality`, `manage_todos`, `ask_user` | 只读 |

> **注意**：`switch_mode` 工具已移除。模式切换只能由用户发起（`/mode <name>` 或 `ask_user` 选项）。

---

## 6. `code` 模式可写类型（完整列表）

```
**/*.c  **/*.cc  **/*.cpp  **/*.cxx
**/*.h  **/*.hh  **/*.hpp  **/*.hxx
**/*.py  **/*.pyi  **/*.ps1  **/*.bat
**/*.toml  **/*.cfg  **/*.ini
**/*.json  **/*.yaml  **/*.yml
**/*.cmake  **/CMakeLists.txt
**/Makefile  **/makefile  **/meson.build
```

通配符基于扩展名，不绑定 `src/` 等固定目录，兼容任意工程结构。

---

## 7. 配置文件覆盖

### 7.1 加载顺序

```
内置 _BUILTIN_MODES
  ↓ 用户级覆盖（~/.embedagent/modes.json）
  ↓ 项目级覆盖（<workspace>/.embedagent/modes.json）
```

每级对对应模式的定义**完整替换**（非字段级合并）。未出现的模式保留内置值。

### 7.2 配置文件格式

```json
{
  "modes": {
    "code": {
      "system_prompt": "针对本项目的自定义 code 提示词...",
      "allowed_tools": ["read_file", "list_files", "write_file", "edit_file",
                        "search_text", "compile_project", "manage_todos", "ask_user"],
      "writable_globs": ["**/*.c", "**/*.h", "firmware/**"]
    },
    "driver_review": {
      "system_prompt": "只读审查驱动层代码，禁止修改。",
      "allowed_tools": ["read_file", "list_files", "search_text", "ask_user"],
      "writable_globs": []
    }
  }
}
```

新增自定义模式（如 `driver_review`）后，`/mode driver_review` 即可使用，无需改代码。

### 7.3 提示词框架模板覆盖

所有模式的系统提示词通过一个通用框架拼装，可在 `~/.embedagent/prompt_frame.txt` 覆盖。

可用占位符（`str.format()` 语法）：

| 占位符 | 含义 |
|--------|------|
| `{mode_name}` | 模式 slug |
| `{mode_description}` | 模式的 `system_prompt` 字段文本 |
| `{ask_rule}` | 使用 ask_user 的指引（自动生成） |
| `{allowed_tools}` | 逗号分隔的工具列表 |
| `{writable_globs}` | 逗号分隔的可写 glob，或 `只读` |

---

## 8. 模式切换机制

```text
触发方式 1：用户输入 /mode <name>
  → parse_mode_command() 解析目标模式
  → require_mode() 验证（未知模式回落到 explore，不崩溃）
  → 追加新模式 system prompt，继续会话

触发方式 2：LLM 调用 ask_user，用户选择含 option_N_mode 的选项
  → _handle_ask_user() 解析用户选择
  → 若 selected_mode 有效：追加新模式 system prompt，更新 current_mode
  → 继续会话

LLM 不能主动切换模式（无 switch_mode 工具）
```

---

## 9. 已删除的模式

以下模式在 v2 中移除：

| 模式 | 移除原因 |
|------|----------|
| `ask` | 功能完全被 `explore` 覆盖（重命名） |
| `orchestra` | 参考项目经验证明"切换提示词"式编排效果差；LLM 主动切模式导致体验问题；移除后通过 `explore` + 用户确认替代 |
| `test` | 写测试代码 → `code` 模式；执行测试 → `verify` 模式；独立 `test` 模式无必要 |
| `compact` | 上下文压缩由 `ContextManager` 自动处理，不是用户可见模式 |

旧 session 中保存的已删除模式名（如 `orchestra`）在恢复时会自动回落到 `explore`，不会崩溃。
