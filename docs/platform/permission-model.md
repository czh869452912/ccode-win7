# Permission Model

## Metadata

> 状态：`active`
> 类型：`platform contract`
> 负责人：`Agent platform maintainers`
> 最后同步日期：`2026-08-01`
> 对应代码范围：`packages/embedagent-core/src/embedagent_core/permissions.py`

## 1. Engine And Inputs

`PermissionPolicy` 是通用 Agent 平台的唯一权限决策引擎。Standalone caller 通过 `AgentPorts.permissions` 显式注入；Host 可组装产品规则、session memory 和 runtime catalog category lookup，但不得在 adapter 或 UI 内建第二套决策。

写路径决策与权限决策独立。`PermissionPolicy` 返回 allow/ask/deny；`WritePathPolicy` 判定目标是否可写。两者任一拒绝，action 都不执行。

## 2. Categories

- `read`；
- `workspace_write`；
- `shell_exec`；
- `toolchain_exec`；
- `git_write`；
- `network`；
- `telemetry`；
- `other`。

active `ToolRuntime` catalog metadata 是工具 category 的唯一真相。无有效 category 的工具归为 `other` 并默认 ask，不得用未分类状态绕过高权限检查。

## 3. Rules

规则是从配置文件读取的结构化对象，支持：

- `decision`: `allow`, `ask`, `deny`；
- `category`；
- `tool_names` / `tool`；
- `path_globs` / `path`；
- `cwd_globs`；
- `command_patterns` / `command_prefix`；
- `recipes` / `recipe`；
- `reason`。

匹配采用 last-match-wins。决策返回稳定 explanation，包含 request、risk、reason、rule source、scope 和 memory scope，供 model 和注册前端展示。

## 4. Defaults

无匹配规则时：

- `read` allow；
- `workspace_write` ask，除非明确 auto-approve writes；
- `shell_exec` 与 `toolchain_exec` ask，除非明确 auto-approve commands；
- `git_write` ask，除非明确 auto-approve writes；
- `network`, `telemetry`, `other` ask，除非明确 auto-approve all。

Core 默认 `PermissionPolicy()` 遵循上述规则。默认离线不表示 network action 可隐式允许。

## 5. Interaction And Memory

ask 决策使当前 action 挂起并创建 permission interaction。Host/UI 可在当前 session 记住 category 决策，但 remembered categories 只是 permission context 的输入，不是 mode side effect 或 durable global rule。

用户回应后，action 重新进入 `AgentToolActionService`，再次经 active-tool、hook、permission 和 path checks。Host 不保存 approval token 以直接调用 runtime handler。

## 6. Resource, Extension And Network Rules

resource reload 是发现/读取操作，不授予执行权。`author_local_capability` 是 `workspace_write`，它不启用 manifest、加载 Python code 或安装依赖。project extension 声明的 permission 不能绕过 runtime catalog 和 `PermissionPolicy`。

内网 Git、自定义 service、provider gateway 和 telemetry 使用显式 adapter/tool/sink 边界。network 或 telemetry 副作用不得隐藏在 `read` 中。passive telemetry 只接收经约束的安全结构化事件，不接收 prompt、source content、raw output、credential、approval secret 或 permission payload。

## 7. Frontend Projection

前端 permission context 包含 rules path、active categories、normalized rules、remembered categories 和 auto-approve flags。前端只解释已有决策并收集用户回应，不按工具名重新实现风险等级。

## 8. Verification

- `tests/test_permissions.py`
- `tests/test_agent_core_public_api.py`
- `tests/test_inprocess_adapter_frontend_api.py`
- `tests/test_hosted_interaction_service.py`
- `tests/test_dynamic_tool_registration.py`

## 9. Related Documents

- `docs/platform/permissions-and-context.md`
- `docs/platform/tools-and-extensions.md`
- `docs/platform/tool-contracts.md`
- `docs/platform/mode-contract.md`
