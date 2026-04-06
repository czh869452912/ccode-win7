# EmbedAgent Agent Harness V2 设计

> 更新日期：2026-04-06
> 状态：已确认的重构设计基线，尚未实现
> 适用范围：mode / harness / tool contract / permission / failure recovery 整体重构

---

## 1. 设计背景

当前系统的核心问题，不是单个工具或单段 prompt 写得不好，而是以下几层机制没有形成闭环：

- mode 承担了过多职责：任务聚焦、工具过滤、写入边界、自动化控制几乎都绑在 mode 上
- tool schema、tool prompt、参数校验、失败反馈、结果预算和权限解释彼此分离，模型拿不到完整行为契约
- 文件列表、搜索结果、诊断输出等高体积结果仍会直接回灌上下文，导致弱模型更容易失控
- `manage_todos` 等流程工具主要依赖 prompt 提醒，而不是由 harness 主动驱动
- allowlist / permission 只有规则匹配，没有足够强的“为什么被拦、如何放行、记忆到什么范围”的解释能力

这使得系统同时落入两类问题：

- 如果 mode 限制太强，系统在真实项目中频繁切换模式、频繁触发奇怪拒绝，自动化几乎无法形成闭环
- 如果 mode 放松过多，工具和提示词又会迅速膨胀，弱模型的工具调用成功率明显下降

本设计的目标，就是把这组矛盾重新拆开。

---

## 2. 设计目标

Agent Harness V2 必须同时满足以下目标：

1. 保留用户可见的 mode，继续利用任务聚焦降低弱模型的自由度。
2. 消除“mode = 硬工具围栏”的耦合，让真实任务不再因为模式切换成本过高而变得难用。
3. 深度融合 spec-driven development 与 TDD，但允许在低风险简单任务里自动降级为轻量流程。
4. 对标 `reference/claude-code` 中成熟的工具契约、结果预算、权限解释和失败恢复思路。
5. 保持离线、Windows 7、C 工程全生命周期、自包含交付这些硬约束不变。

非目标：

- 不追求照搬 Claude Code 的全部交互形态
- 不引入需要强模型才能稳定工作的“全工具自由暴露”模式
- 不为兼容旧 session、旧 mode、旧权限格式保留历史包袱

---

## 3. 设计原则

### 3.1 用户看到的是 mode，内核运行的是 phase

用户仍然看到少量稳定的工作模式；真正决定“当前该做什么”的，是 mode 内部的 execution phase。

### 3.2 聚焦不靠硬切断，靠按阶段装载最小工具集

不再用 mode 直接绑定完整工具全集和写入边界，而是由 harness 根据 phase 选择 tool pack。

### 3.3 工程纪律由系统驱动，不依赖模型自觉

spec、验收标准、失败测试、实现、验证、回归不再只是 prompt 口号，而是 phase engine 的默认轨道。

### 3.4 工具是完整契约，不只是 function schema

每个工具都必须同时定义“何时该用、如何校验、如何失败、失败后怎么修、结果多大时如何预算”。

### 3.5 权限解释和失败解释必须是可行动的

系统返回给模型和用户的不是“失败了”，而是“失败在什么阶段、为什么失败、下一步该怎么修正”。

### 3.6 优先吸收 Claude Code 的强项，但不复制其强模型假设

要借鉴其工具级 prompt、结果持久化、参数错误格式化、权限解释、延迟装载思想；不直接复制其大工具面和宽松自由度。

---

## 4. 参考项目综合结论

本方案不是简单模仿单一参考项目，而是有意做一层综合：

- Roo Code 的优点：用户可感知的 mode 能显著缩小任务面，弱模型更稳定
- Claude Code 的优点：tool contract 完整、失败可恢复、结果预算成熟、权限系统解释性强
- EmbedAgent 的目标约束：离线、Win7、C 工程、弱模型适配、自包含交付

因此推荐的方向是：

- 保留 Roo 风格的“用户可见工作模式”
- 引入 Claude Code 风格的“工具完整契约、结果预算、权限解释、错误格式化”
- 用新的 `phase harness` 把二者结合起来

这意味着：

- 不再把 mode 直接当成硬权限系统
- 不再把所有行为都塞进单一系统提示词
- 不再让模型自己临场决定完整开发方法学

---

## 5. 核心架构

Agent Harness V2 的核心对象如下：

### 5.1 WorkMode

用户可见的工作模式，用来表达当前任务的大类语义。

建议内置模式：

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

其中 `build` 取代当前 `code`，因为它不再只表示“写代码”，而是表示“完成一个带规格、测试、实现与自检的开发闭环”。

### 5.2 ExecutionPhase

mode 内部自动流转的阶段，负责真正调度工具和纪律。

ExecutionPhase 对用户可见，但不是用户必须频繁手动切换的主入口。

建议 UI 呈现为：

- `Mode: build`
- `Phase: implement`

而不是要求用户在 `spec -> code -> verify` 之间反复手动切。

### 5.3 DisciplineProfile

描述本次任务采用的工程纪律强度：

- `full_spec_tdd`
- `lite_spec_tdd`

切换规则：

- 新功能、行为变更、明确缺陷修复、核心模块修改：默认 `full_spec_tdd`
- 机械修改、小型修复、探索性调整：允许降级为 `lite_spec_tdd`
- 降级必须记录原因，不能静默绕过

### 5.4 ToolPack

按 phase 装载的最小工具子集。

ToolPack 取代“mode 直接暴露全部工具”的设计。

### 5.5 RiskProfile

工具声明自己的风险类型，供 permission engine 和 UI 统一消费。

### 5.6 RecoveryDecision

失败后由 harness 做出的恢复决策：

- 返回结构化失败结果，要求模型或用户修正
- 请求 phase handoff 或 discipline 降级
- 请求权限
- 请求用户确认
- 触发确定性的系统兜底逻辑
- 停止并汇报

---

## 6. Mode 2.0 设计

### 6.1 `explore`

职责：

- 阅读代码与文档
- 理解结构、定位范围、比较方案
- 形成后续 spec/build/debug 的入口上下文

特点：

- 默认不改源码
- 可产出只读分析结论和任务拆解建议
- 内部 phase 主要是 `survey -> focus -> evidence`

### 6.2 `spec`

职责：

- 需求收敛
- 边界条件与验收标准定义
- 测试点设计
- 规格文档维护

特点：

- 允许写文档，不允许写业务源码
- 内部 phase 主要是 `intake -> constraints -> acceptance -> handoff`

### 6.3 `build`

职责：

- 默认开发模式
- 在单一 mode 内完成“理解 -> 规格轻收敛 -> 测试设计 -> 实现 -> 自检 -> 修复”

特点：

- 用户停留在同一个 visible mode
- 内部自动 phase 切换，不要求用户在 `spec/code/verify` 之间频繁切换

推荐内部 phase：

- `understand`
- `contract`
- `test_design`
- `implement`
- `check`
- `repair`
- `handoff`

### 6.4 `debug`

职责：

- 缺陷复现
- 根因定位
- 最小修复
- 回归确认

推荐内部 phase：

- `reproduce`
- `isolate`
- `failing_check`
- `patch`
- `regression_check`
- `handoff`

### 6.5 `verify`

职责：

- 独立运行编译、测试、静态分析、覆盖率与质量门
- 汇总结论，不修改源码

推荐内部 phase：

- `select_recipe`
- `execute`
- `summarize`

### 6.6 为什么这样能减少模式切换

当前系统的问题是把大量“本应在同一任务里自动切换的子阶段”提升成了用户必须手动切换的 mode。

Mode 2.0 的核心变化是：

- 用户只切换任务的大类语义
- 系统自动切换任务内部子阶段

因此真实开发路径会从：

`explore -> spec -> code -> verify -> debug -> code -> verify`

收敛成更稳定的：

- 新功能：`build(mode)` 内部完成 `understand -> contract -> test_design -> implement -> check -> repair`
- 缺陷修复：`debug(mode)` 内部完成 `reproduce -> isolate -> failing_check -> patch -> regression_check`

### 6.7 复杂度与纪律映射

phase 的完整粒度保留，但不是所有任务都启用完整轨道。

建议映射：

| 任务复杂度 | Discipline | 默认轨道 |
|-----------|------------|----------|
| 复杂：新功能、行为变更、核心模块修改 | `full_spec_tdd` | `understand -> contract -> test_design -> implement -> check -> repair -> handoff` |
| 中等：局部重构、补测试、非核心逻辑增强 | `lite_spec_tdd` | `understand -> contract -> implement -> check -> handoff` |
| 简单：rename、typo、文档修正、机械替换 | `lite_spec_tdd` 或 direct fast path | `implement -> check` |

设计要求：

- phase 数量多不是问题，前提是复杂任务才启用完整轨道
- 所有降级都必须被记录
- phase 可见性与任务复杂度联动，避免简单任务 UI 过度跳动

---

## 7. Phase Harness

### 7.1 自动流转边界

推荐规则：

- 同一 visible mode 内的 phase，允许自动切换
- visible mode 之间默认不静默切换，只允许“建议切换”
- 后续可增加 session 级选项启用 `auto_handoff_between_modes`

这能兼顾灵活性与可解释性：

- 自动化发生在用户感知成本较低的 phase 层
- mode 仍然是稳定的心智模型

### 7.2 自动流转由 artifact 检测触发

自动切换的依据不是“模型似乎想做下一步”，而是系统能观察到的 artifact 变化。

推荐触发原则：

- `phase` 前进由文件、工具结果、结构化工件出现来触发
- `tool failure` 本身不直接触发 phase 切换
- `command_exit_nonzero` 只产生高信息量失败结果，不直接把当前 phase 推到 `repair`

推荐触发表：

| 当前 Phase | 进入下一 Phase 的条件 |
|-----------|----------------------|
| `understand` | 产出 `context_summary`、`spec_ref`、或被 harness 标记为“理解完成”的结构化摘要 |
| `contract` | 检测到 `spec.md`、验收标准工件，或结构化 `acceptance_criteria` 已记录 |
| `test_design` | 检测到测试文件新增/修改，或结构化 `failing_evidence` 已记录 |
| `implement` | 检测到生产代码修改，且最近一次 `check` 结果已形成 |
| `check` | 检测到 recipe/test/quality gate 的结构化结果 |
| `repair` | 在同一问题链上检测到代码修复并重新验证通过 |

### 7.3 Build Mode 的默认纪律

`build` 模式的默认轨道：

1. `understand`
2. `contract`
3. `test_design`
4. `implement`
5. `check`
6. `repair`
7. `handoff`

约束：

- 没有明确规格时，不直接跳到大规模实现
- 没有测试点或失败样例时，不直接声称“已完成修复”
- `check` 失败时，系统优先返回结构化失败结果；只有在后续检测到修复工件后才推进状态

### 7.4 Debug Mode 的默认纪律

`debug` 模式的默认轨道：

1. `reproduce`
2. `isolate`
3. `failing_check`
4. `patch`
5. `regression_check`
6. `handoff`

约束：

- 未复现时，不进入 patch
- 未形成最小失败证据时，不标记完成
- 回归失败时，保持在当前问题链条内修复，而不是直接触发跨 phase 抖动

### 7.5 Phase Gate 是可绕过的护栏，不是绝对硬围栏

phase gate 默认拦截明显越级的动作，但允许受控绕过：

- 系统先阻止越级动作并解释原因
- 若模型或用户坚持跳过，系统允许降级进入更轻的 discipline
- 所有绕过必须被记录到 `discipline_decisions`

例如：

- 当前在 `contract`
- 模型尝试直接修改 `.c` 文件
- 系统返回：
  - 当前处于 `contract`
  - 建议先完成 spec
  - 若需求已足够明确，可请求降级到 `lite_spec_tdd`

### 7.6 Lite Spec / TDD 降级

允许降级，但必须满足：

- 任务范围小
- 风险低
- 不涉及核心行为重构
- 系统记录降级原因

降级后可走：

- `understand -> implement -> check`
- `reproduce -> patch -> regression_check`

### 7.7 Phase 可见性应按任务复杂度调整

建议 UI 规则：

- 复杂任务：显示完整 discipline checklist 和当前 phase
- 中等任务：显示 mode 与精简 checklist
- 简单任务：只显示 mode 和当前活动描述，不强调 phase 标签跳动

---

## 8. Prompt Stack 设计

当前问题之一，是系统提示词同时承担了人格、模式、工作流、工具使用指南、权限纪律、错误修复指引等过多职责。

V2 保留“概念上分层”的设计，但物理注入应压缩为 3 个单元，避免弱模型被层级结构淹没。

### 8.1 概念分层

概念上仍分为：

1. `Base Frame`
2. `Project Constitution`
3. `Mode Context`
4. `Discipline Checklist`
5. `Tool Guidance`
6. `Runtime Nudges`

### 8.2 物理注入单元

真正注入给模型的只有 3 类：

1. `Base System Prompt`
   角色、离线约束、Win7 约束、C 生命周期目标、全局工程纪律
2. `Mode Context`
   当前 mode、当前 discipline、phase/checklist 状态、当前 tool pack 摘要
3. `Runtime Nudges`
   仅在需要时注入的 1 到 2 条短提醒，例如最近一次 recipe 失败、权限等待、重复失败提示

### 8.3 Tool Guidance 注入原则

- 常驻核心工具集保持稳定顺序和稳定提示位置
- 非核心工具按需装载，但尽量避免高频 phase 切换导致提示顺序反复变化
- `when_to_use / when_not_to_use` 优先写入 tool prompt，而不是拆成单独 system frame

---

## 9. Tool Contract V2

### 9.1 最小必填集与增强字段集

为避免工具字段爆炸，V2 将工具契约分为两层。

最小必填集：

- `name`
- `description`
- `prompt`
- `input_schema`
- `call`
- `validate_input`
- `check_permissions`
- `map_result`
- `result_budget_policy`

增强字段集：

- `tags`
- `examples`
- `phase_affinity`
- `search_hint`
- `is_read_only`
- `is_concurrency_safe`

设计要求：

- 首期落地只强制最小必填集
- `when_to_use / when_not_to_use` 合并进 `prompt`
- `success_schema / failure_schema` 不要求每个工具单独重复声明，由统一 observation envelope 承担

### 9.2 Tool Prompt 设计原则

工具 prompt 必须明确告诉模型：

- 该工具解决什么问题
- 与相近工具相比优先何时选它
- 哪些常见 shell 替代方式不推荐
- 参数如何填写
- 常见错误如何避免

### 9.3 常见失败模式必须写进工具 prompt

对于弱模型，只有统一失败分类还不够。工具 prompt 还必须显式提示常见失败方式，例如：

- 路径必须是工作区内路径
- 参数为空会失败
- 结果过大时应改用更具体的过滤条件
- 编辑前必须先读取目标文件

### 9.4 参数校验错误必须可纠正

参数校验失败统一返回：

```json
{
  "success": false,
  "error": "grep_text 缺少 pattern 参数。",
  "data": {
    "error_kind": "schema_missing_required",
    "error_stage": "validation",
    "retryable": true,
    "suggested_fix": "补充必填参数 pattern。",
    "missing_fields": ["pattern"]
  }
}
```

不能再只返回“工具参数必须是对象”或“工具参数不是有效 JSON”这类过于粗糙的失败。

### 9.5 结果预算必须是基础设施，不只是工具字段

所有工具都要声明结果预算策略：

- `inline_full`
- `inline_preview`
- `preview_plus_ref`
- `summary_plus_ref`
- `never_inline`

列表、搜索、诊断、diff、stdout/stderr、coverage 都必须走统一预算机制。

除此之外，还必须有消息级 aggregate budget：

- 同一轮多个工具结果总量超过阈值时，系统自动替换旧结果为 preview/ref
- 这一步由底层基础设施统一处理，而不是每个工具各自决定

### 9.6 文件与搜索工具重做

建议废弃当前的递归型 `list_files`，改为：

- `list_dir(path, limit, offset, include_hidden)`
- `glob_files(pattern, path, limit, offset, sort_by)`
- `grep_text(pattern, path, glob, output_mode, limit, offset)`
- `read_file(path, start_line, max_lines)`

统一结果形态：

```json
{
  "success": true,
  "data": {
    "preview": [],
    "returned_count": 20,
    "total_count": 138,
    "has_more": true,
    "next_offset": 20,
    "result_ref": ".embedagent/memory/sessions/.../tool-results/..."
  }
}
```

这样既保留探索能力，又不会把大列表直接灌回上下文。

### 9.7 构建与验证工具重做

建议把当前多工具的 build/verify 面重构为 recipe 中心：

- `list_recipes`
- `run_recipe`
- `read_diagnostics`
- `report_quality`

而不是长期维持：

- `compile_project`
- `run_tests`
- `run_clang_tidy`
- `run_clang_analyzer`
- `collect_coverage`

原因：

- recipe 已经是现有系统的真实工程入口
- 对弱模型来说，`run_recipe` 比多个近义工具更稳定
- verify mode 可以把工具数压到更可控的范围

### 9.8 任务系统重做

当前 `manage_todos` 主要依赖模型主动调用，不适合弱模型。

建议改为：

- 内核维护 `TaskGraph`
- phase engine 自动更新当前任务状态
- 模型只在需要补充/拆分/纠偏时通过轻量工具参与

推荐暴露两个轻量接口：

- `task_status`
- `task_update`

其中：

- `task_status` 只读，返回当前任务图压缩视图
- `task_update` 用于显式补充任务拆解或状态修正

这意味着 todo 价值不再依赖模型“记得去用”，而是由 harness 主导。

设计补充：

- `TaskGraph` 以内核状态为真相源
- 常规任务推进由 phase 和 artifact 自动同步
- 模型侧的 `task_update` 只用于显式纠偏、拆分和补充
- 不以解析任意自由文本作为主真相源，避免离线弱模型场景下产生额外歧义

### 9.9 Shell 不是默认隐藏，而是受严格约束的稳定 fallback

Shell 仍然需要存在，但不应成为主要工作流。

建议规则：

- 核心专用工具不足时，允许使用 shell
- shell 的 prompt 必须明确写出“何时不能替代专用工具”
- shell validator 在可判定时直接返回 `suggested_fix: 改用专用工具`
- 不把 shell 的可见性完全交给 phase engine 隐藏/显示，以避免弱模型在失败后突然失去最后的可执行出口

---

## 10. Tool Pack 设计

建议预定义以下 pack。

### 10.0 常驻核心工具集

为保证弱模型提示稳定性，以下核心工具应在多数编程 mode 中保持稳定可见：

- `read_file`
- `list_dir`
- `grep_text`
- `edit_file`
- `write_file`
- `run_recipe`
- `ask_user`
- `task_status`

其余 pack 在此基础上按需附加。

### 10.1 Common Pack

- `task_status`
- `task_update`
- `ask_user`

### 10.2 Discover Pack

- `list_dir`
- `glob_files`
- `grep_text`
- `read_file`
- `symbol_summary`

### 10.3 Doc Pack

- `read_file`
- `write_file`
- `edit_file`

仅在文档可写路径内暴露。

### 10.4 Edit Pack

- `read_file`
- `edit_file`
- `write_file`
- `git_diff`

### 10.5 Recipe Pack

- `list_recipes`
- `run_recipe`
- `read_diagnostics`
- `report_quality`

### 10.6 Repo Read Pack

- `git_status`
- `git_diff`
- `git_log`

### 10.7 Shell Fallback Pack

- `shell_command`

默认作为受严格 prompt 和 validator 约束的 fallback。

---

## 11. Permission / Allowlist V2

### 11.1 权限不再依赖 mode 直接决策

mode 只负责工作语义，不再直接承担权限主判断。

权限系统基于：

- `policy`
- `risk_profile`
- `rule_dsl`

### 11.2 风险类型

建议统一风险分类：

- `read_only`
- `doc_write`
- `code_write`
- `build_exec`
- `repo_read`
- `repo_write`
- `shell_readonly`
- `shell_mutating`
- `destructive`

### 11.3 首期不引入自定义 DSL，先做 Rule Schema V1

首期建议采用 TOML/JSON 规则列表，而不是自定义文本 DSL。

示例：

```json
[
  { "tool": "Edit", "path": "src/**/*.c", "decision": "allow" },
  { "tool": "Edit", "path": "**/README.md", "decision": "deny" },
  { "tool": "Shell", "command_prefix": "git push", "decision": "ask" }
]
```

设计要求：

- 规则可读、可写、可解释
- 支持 tool / path / recipe / command pattern
- 支持 `once / session / project` 记忆范围
- 若未来需要 DSL，只作为 Rule Schema 的语法糖层，而不是首期实现前置条件

### 11.4 权限请求解释必须走统一模板

每次权限请求都必须给出：

- 触发工具
- 风险类别
- 触发原因
- 命中规则来源
- 涉及路径或命令
- 可记忆范围

这个能力要借鉴 Claude Code 的 permission explanation 思路，但为了离线稳定和弱模型适配，默认采用确定性模板生成，而不是额外发一个解释型 LLM 请求。

建议统一模板：

```text
[请求] {tool_name}({args_summary})
[风险] {risk_category}
[原因] {trigger_reason}
[规则] {rule_source_or_default}
[范围] {path_or_command}
[记忆] once / session / project
```

### 11.5 判定顺序

建议顺序：

1. product hard policy
2. explicit deny
3. explicit ask
4. explicit allow
5. low-risk auto allow
6. request confirmation

---

## 12. Failure Model V2

### 12.1 统一失败分类

建议统一 `error_kind`：

- `schema_missing_required`
- `schema_unexpected_param`
- `schema_type_mismatch`
- `phase_mismatch`
- `permission_blocked`
- `path_outside_workspace`
- `path_not_found`
- `file_missing`
- `no_match`
- `ambiguous_match`
- `command_exit_nonzero`
- `command_timeout`
- `tool_unavailable`
- `runtime_internal_error`

### 12.2 统一失败字段

所有失败 Observation 至少带：

- `error_kind`
- `error_stage`
- `retryable`
- `likely_cause`
- `suggested_fix`
- `blocked_by`
- `recommended_phase`
- `user_action_required`

### 12.3 恢复矩阵

建议 harness 内置恢复规则：

- `schema_*`
  返回高信息量失败结果，由模型在下一轮修正；系统不直接启发式自动补参
- `phase_mismatch`
  返回当前 phase 期望与建议去向；是否切换由 harness 或用户确认
- `permission_blocked`
  发起权限请求
- `no_match`
  返回替代搜索建议，并尽量附带辅助恢复信息
- `ambiguous_match`
  返回相近片段、近似命中或建议追加上下文
- `command_exit_nonzero`
  解析 diagnostics，返回结构化失败；不直接触发 phase 切换
- `runtime_internal_error`
  停止并生成内部错误 artifact

### 12.4 重复失败提示

如果同一工具在同一问题链上连续失败超过阈值：

- 不自动盲重试
- 系统注入一个短 nudge，提醒常见错误模式
- 必要时请求用户确认是否继续该路径

---

## 13. 风险封堵机制

### 13.1 Phase Thrash Guard

同一任务若在多个 phase 之间来回切换超过阈值，停止自动流转，请求用户确认。

### 13.2 Tool Thrash Guard

同类工具连续失败超过阈值后，不再盲重试，转入恢复分支。

### 13.3 Result Budget Guard

所有大结果走统一 preview/ref 机制；再叠加消息级 aggregate budget，避免同一轮多个工具结果叠加失控。

### 13.4 Discipline Erosion Guard

如果任务从 `full_spec_tdd` 降级到 `lite_spec_tdd`，必须显式记录原因。

### 13.5 Verify Purity Guard

`verify` mode 保持真正只读，不允许修改源码。

### 13.6 Shell Drift Guard

一旦存在专用工具满足任务，系统默认不装载 shell fallback。

---

## 14. 实施建议

本轮按 clean-slate 重构推进，但不采用纯瀑布式切片。必须正视大爆炸集成风险。

### 14.1 重构治理前提

- 进入实现期后，旧 mode/tool/permission 逻辑进入冻结维护状态
- 前后端协议在重构窗口内按单版本锁步演进
- 旧 session / 旧权限格式直接废弃，不做兼容
- 预留独立的端到端验证窗口

### 14.2 推荐切片顺序

#### Program A：基础设施先行

- `WorkMode / ExecutionPhase / DisciplineProfile / ToolPack`
- 统一 observation envelope
- 结果预算基础设施
- Permission explanation builder

#### Program B：Build Lite 垂直切片

- 跑通 `build + lite_spec_tdd`
- 重做最关键工具：`read/search/edit/run_recipe/ask_user/task_status`
- 这是第一条可用主线

#### Program C：Debug Lite 垂直切片

- 跑通 `debug + lite_spec_tdd`
- 验证复现、定位、修复、回归闭环

#### Program D：Full Discipline 与 TaskGraph

- 引入 `full_spec_tdd`
- 增加 contract/test_design/failing_evidence 等 artifact gate
- 强化 TaskGraph 自动同步

#### Program E：Verify / UI / Rule Schema

- 完成 verify mode
- 前端展示 `mode + discipline + current activity`
- 上线 Rule Schema V1

#### Program F：旧体系切断

- 移除旧 mode 工具过滤主线
- 移除旧 permission-rules JSON 主线
- 移除旧 `list_files` 递归输出模型

### 14.3 大爆炸集成风险控制

- 在最终切断旧体系前预留 2 周端到端验证窗口
- 前端、recipe、permission、context budget 必须按真实工作流回归
- 所有旧格式直接拒绝加载，而不是做半兼容迁移

---

## 15. 预期收益

如果按本方案落地，系统会获得以下改善：

- 用户仍然能通过少量 mode 理解当前工作类型
- mode 不再成为频繁切换和奇怪拒绝的主要来源
- spec/TDD 从提示词口号变成系统默认纪律
- 弱模型每一步只面对少量最相关工具，工具调用成功率会明显高于当前实现
- 大结果不再污染上下文
- 权限与失败反馈都具备足够解释性和可恢复性
- 系统整体更接近 Claude Code 的成熟执行内核，但保持更适合弱模型和离线场景的约束设计

---

## 16. 当前建议结论

本轮不建议继续围绕“修 prompt、补一点 tool description、再调一下 allowlist”做局部优化。

建议直接确立以下新基线：

- 用户可见 mode 保留，但改为工作模式而不是硬工具围栏
- mode 内部引入自动 phase harness
- spec/TDD 作为默认优先纪律，并允许受控降级
- 工具升级为完整契约
- 权限系统升级为风险驱动 + DSL + 可解释
- 大结果和失败恢复采用 Claude Code 风格的成熟机制，但按弱模型约束做本地化调整

这条路线本质上是：

**以 Claude Code 的执行内核质量为目标，以更强的任务聚焦和更小的工具暴露面来适配弱模型。**
