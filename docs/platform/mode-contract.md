# Mode Contract

## Metadata

> 状态：`active`
> 类型：`platform contract`
> 负责人：`Agent platform maintainers`
> 最后同步日期：`2026-08-01`
> 对应代码范围：`src/embedagent/modes.py`, `packages/embedagent-core/src/embedagent_core/profile.py`

## 1. Official Modes

平台公开模式集为：

- `explore`；
- `spec`；
- `build`；
- `debug`；
- `verify`。

`code` 不是有效模式。模式是用户可见的意图、工具焦点和可写范围契约，不是上层应用的完整状态机。

## 2. Responsibilities

| Mode | Responsibility | Platform Tool Focus | Write Policy |
|---|---|---|---|
| `explore` | 阅读、解释、影响分析 | read/search, `ask_user` | read-only |
| `spec` | 需求、约束、验收和文档 | read/search, `write_file`, `ask_user` | documentation/text writes |
| `build` | 实现与迭代 | read/search/edit, `bash`, `ask_user` | implementation writes |
| `debug` | 复现、隔离、最小修复 | read/search/edit, `bash`, `ask_user` | implementation writes |
| `verify` | 构建、测试和静态检查汇总 | read/search, `bash`, `ask_user` | no source edits |

实际名称集由 `src/embedagent/modes.py` 的 registry 给出。代码使用 `get_mode_registry()` 和 `initialize_modes()` 访问或初始化 registry，不建立代理别名。

## 3. Switching

- 模式切换由用户驱动；
- model 可以提出 `propose_mode_switch` 交互，但只在用户确认后改变 mode；
- `/mode <name>` 和纯自然语言切换请求在 provider call 前处理；
- `/mode <name> <message>` 先切换，再提交 message；
- 未知名称必须失败，不隐式 fallback。

交互恢复重新进入 `AgentToolActionService`，不创建第二条 mode mutation 路径。

## 4. Tools And Applications

mode 中的 allowed tools 只定义平台基础工具焦点和写入契约。上层应用可根据 mode 和自己的 workflow state 返回 active tool names，`AgentExtensionHost` 将它们与 mode contract 合并，再以显式名称请求 `ToolRuntime.schemas_for(...)`。

application manifest、runtime config、compaction state 和 recovery state 仅是读模型，不能更改 mode contract 或激活工具。

## 5. Writable Scope

mode 可进一步限制可写 glob，但不授权。`PermissionPolicy` 决定 allow/ask/deny，独立写路径策略决定目标路径是否可写。两者任一拒绝，写操作都不得执行。

## 6. Verification

- `tests/test_modes.py`
- `tests/test_agent_profiles.py`
- `tests/test_tools_v2_runtime.py`
- `tests/test_current_architecture_boundaries.py`

## 7. Related Documents

- `docs/platform/tools-and-extensions.md`
- `docs/platform/permission-model.md`
- `docs/applications/README.md`
