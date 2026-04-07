# Agent Harness V2 设计方案审查报告

> 日期：2026-04-06
> 审查对象：`docs/agent-harness-v2.md`
> 参考依据：`reference/claude-code` 源码、`docs/mode-schema.md`、`docs/tool-contracts.md`、`docs/overall-solution-architecture.md`

---

## 1. 执行摘要

`agent-harness-v2.md` 是一方向正确的顶层重构宣言，它准确诊断了当前系统的核心病症：
- mode 与硬权限过度耦合；
- 工具契约不完整、失败不可恢复；
- 大结果回灌上下文；
- 工程纪律依赖模型自觉而非系统驱动。

但该方案作为“可直接落地的设计基线”存在显著不足。其主要风险在于：
1. **Phase 自动流转的判定逻辑缺失**，仅靠列表面 phase 无法自愈；
2. **Tool Contract V2 的字段爆炸**（11 个必填字段）与实现节奏不匹配；
3. **Prompt Stack 7 层拆分过于理想化**，未考虑弱模型对层级指示的跟随能力；
4. **Permission DSL 设计超前**，但缺少与 Phase/ToolPack 的联动删除策略；
5. **Failure Model 的"自动恢复"假设过强**，对弱模型的重试引导不足；
6. **实施切片（Slice 1-6）是瀑布式顺序**，缺少 clean-slate 重构必须正视的大爆炸集成风险。

本报告将逐层展开分析，并给出基于 `reference/claude-code` 实践的修正建议。

---

## 2. 核心问题映射：从用户痛点到设计缺陷

| 用户痛点 | V2 方案中的对应设计 | 审查结论 |
|---------|-------------------|---------|
| `list_files` 结果传回上下文导致污染 | 9.5 节结果预算 + `preview_plus_ref` | 方向对，但缺少**聚合预算（aggregate budget）**的硬约束机制 |
| todo 等流程工具不被使用 | 9.7 节 `TaskGraph` + `task_status/task_update` | 从"模型主动"转向"系统主导"是对的，但 `task_update` 仍依赖模型调用，未根本解决 |
| 失败时模型不知何以修正 | 12 节统一失败分类 + `suggested_fix` | 分类合理，但**未要求每个工具在 prompt 中显式声明常见失败模式** |
| 权限拒绝体验差 | 11 节 Permission DSL | DSL 可读，但**缺少运行期 explainability 的确定性模板规范** |
| mode 频繁切换、自动化受限 | 6 节 Mode 2.0 + Phase Harness | **Phase 自动流转的判定逻辑缺失**，仅靠列表面 phase 无法自愈 |

---

## 3. Mode / Phase 设计的问题与修正建议

### 3.1 Phase 数量本身不是问题，问题在于“谁来驱动、什么时候启用”

V2 为 `build` 定义了 7 个 phase：`understand → contract → test_design → implement → check → repair → handoff`；`debug` 定义了 6 个。

若将 Phase 仅视为内部状态机，数量多确实会增加弱模型的认知负担。但若 Phase 的设计目标是**类似 Superpower 的强制轨道**，把 Spec / TDD 固化为不可绕过的系统纪律，则数量多并非核心问题。**真正需要解决的是：复杂任务才启用完整轨道，简单任务自动轻量降级，所有降级必须被记录，phase 切换由 artifact 客观检测触发。**

建议的任务复杂度映射：

| 任务复杂度 | 启用的 Discipline | Phase 轨道 |
|-----------|------------------|-----------|
| 复杂（新功能、行为变更、核心模块修改） | `full_spec_tdd` | `understand → contract → test_design → implement → check → repair → handoff` |
| 中等（局部重构、新增测试覆盖） | `lite_spec_tdd` | `understand → contract → implement → check → handoff` |
| 简单（typo、rename、文档修正） | `lite_spec_tdd` 或 `direct_implement` | `implement → check`（或只有 `implement`） |

### 3.2 Phase 的 UI 可见性应随任务复杂度动态调整

3.1 节提出 `"Mode: build / Phase: implement"` 的 UI 呈现，但未回答标签跳动造成的焦虑问题。

建议：
- **复杂任务**：UI 应显示完整的 discipline checklist（如进度条或步骤列表），让用户和模型都清楚当前处于哪个检查点。
- **简单任务**：UI 只显示 `"Mode: build"` 和一个轻量的活动描述（如 `"Editing src/foo.c"`），不暴露 phase 细节。
- **Phase 信息不通过独立的 system message 注入**，而是作为 Mode Context 中的一个 `discipline_checklist` 段落，随回合自然演进。

例如，复杂任务中的系统提示片段：
```text
当前纪律：full_spec_tdd
进度：[✓] understand → [✓] contract → [→] test_design → [ ] implement → [ ] check
当前阶段目标：基于已确认的 spec.md，设计测试点和初始失败测试。在产出 tests/ 下的测试代码前，不要大规模实现生产代码。
```

### 3.3 Phase Gate 是可绕过的护栏，但绕过必须留下痕迹

Phase harness 不应做成绝对强制的硬围栏，而应是可记录、可审计的护栏：

- **默认 Gate**：在 `full_spec_tdd` 下，如果模型在 `contract` 阶段就调用 `edit_file` 修改 `.c` 文件，系统应拦截并提示：
  > "当前处于 contract 阶段，建议先完成 spec。如果你确认需求足够明确，可以请求进入 implement 阶段。"
- **降级出口**：如果模型坚持（或用户通过 `ask_user` 选项选择了“跳过，直接实现”），系统允许进入，但必须：
  1. 自动把 `discipline_profile` 降级为 `lite_spec_tdd`；
  2. 在 `discipline_decisions` 中记录：`"Skipped contract phase at turn 5: model argued that requirements were clear from user input."`
  3. 在后续系统提示中固定显示一个简短的降级标记：`[lite_spec_tdd] skipped: contract`

这与 V2 文档 7.4 节的精神一致，但把降级从“模型请求 → 系统批准”变成了“系统拦截 → 模型/用户申诉 → 自动记录”，更主动、更透明。

### 3.4 自动 Phase 切换应由 artifact 检测触发，而不是模型意图推断

V2 文档列出了大量 phase，但未给出自动流转的具体判定逻辑。这是当前设计最危险的缺口。

建议自动切换由严格的 artifact 检测触发：

| 当前 Phase | 自动进入下一 Phase 的条件 |
|-----------|------------------------|
| `understand` | harness 检测到模型产出了 `context_summary` 或 `spec.md` 文件 |
| `contract` | 检测到 `spec.md` 存在且模型在最近 2 轮内引用过它 |
| `test_design` | 检测到 `tests/` 目录下有新增或修改的测试文件 |
| `implement` | 检测到 `src/` 下有代码修改，且最近一次 `run_recipe` 的 `exit_code == 0` |
| `check` | 检测到 `run_recipe` 的测试/质量门结果 |
| `repair` | `check` 失败后，模型调用了 `edit_file` 或 `run_recipe` 且结果通过，则自动进入 `handoff` |

**关键点**：
- 自动切换不是“AI 理解模型意图”，而是**文件系统/工具结果的客观变化**。
- 如果条件不满足，系统不催促、不强制，只是稳定重复当前 phase 的 checklist。
- 如果连续 2-3 轮条件都未满足，系统触发 `ask_user`："当前在 contract 阶段，但我没有看到 spec 产出。你是要继续在此阶段工作，还是降级为轻量模式？"

### 3.5 `command_exit_nonzero` 直接切到 `repair` phase 过于粗暴

12.3 节恢复矩阵建议 `command_exit_nonzero` → 解析 diagnostics，转入 `repair` 或 `reproduce`。

`exit_nonzero` 的原因千奇百怪：编译错误、测试失败、命令参数错误、环境缺失。如果每次编译失败都触发 phase 切换，会导致 phase thrash（即使 13.1 节有 Thrash Guard，guard 被触发本身也意味着体验受损）。

建议：
- 取消 `command_exit_nonzero` 与 phase 切换的硬绑定。
- 系统解析 exit code、stdout/stderr、diagnostics 后，**在同一 phase 内将解析结果返回给模型**，由模型决定是继续在当前 phase 修复（通常是 `implement` 或 `verify`），还是请求用户帮助。
- Phase 切换应该是 **artifact 满足条件的变化**，而不是工具执行失败的直接后果。
- 只有当 `check` 阶段发现问题，且模型已经产出修复代码并再次调用 `run_recipe` 验证通过时，才自动从 `repair` 进入 `handoff`。

---

## 4. Tool Contract V2 的问题

### 4.1 11 个必填字段的契约负担过重

9.1 节要求每个工具必须具备 `name, description, when_to_use, when_not_to_use, examples, input_schema, validator, success_schema, failure_schema, result_budget_policy, permission_profile, phase_affinity`。

这对于一个小团队维护的工具集来说负担过重：
- `phase_affinity` 的语义不清。如果工具在多个 phase 都可用，是否意味着 phase 边界被稀释？
- `examples` 的维护成本被低估。Claude Code 并没有为每个工具都在 schema 层面维护 `examples`，而是把最佳实践写在 tool prompt 里（如 `BashTool/prompt.ts` 中长达数百行的 git/PR 操作指引）。

**Claude Code 的参照：**
`Tool.ts` 中的 `ToolDef` 接口很精简：
- `name, description, call, inputSchema, outputSchema, prompt, checkPermissions, mapToolResultToToolResultBlockParam`
- 其余全部是可选的（`isEnabled, isConcurrencySafe, isReadOnly, validateInput, renderToolResultMessage` 等）。

Claude Code 的提示词注入不依赖 `when_to_use` 这种独立字段，而是把 "何时用、何时不用" 直接写进 `prompt()` 返回的字符串。

**建议：**
- Tool Contract V2 应区分**最小必填集**和**增强字段集**。最小集只保留：
  1. `name`
  2. `description`
  3. `input_schema`
  4. `call`
  5. `checkPermissions`
  6. `mapToolResultToToolResultBlockParam`
- `when_to_use / when_not_to_use` 合并进 `prompt` 内容，由开发者在 prompt 文本中自由编排，而不是作为独立 schema 字段。
- `phase_affinity` 改为可选，初期只用一个简单的 `tags: string[]` 进行过滤。

### 4.2 结果预算缺少"工具间 aggregate budget"硬约束

9.4 节定义了 `inline_full, inline_preview, preview_plus_ref, summary_plus_ref, never_inline` 五种策略。

这是**单工具级别**的预算，未考虑同一轮次中多个工具结果叠加的总量。一个弱模型可能在同一轮并行调用 `list_dir` + `grep_text` + `read_file`，三个工具各自在预算内，但加起来仍可能灌爆上下文。

9.5 节的统一结果形态只声明了 `returned_count, total_count, has_more`，但缺少当模型连续翻页时 harness 主动截断或建议换策略的干预逻辑。

**Claude Code 的参照：**
- `Tool.ts` 中每个工具有 `maxResultSizeChars`，超过则持久化到文件（`contentReplacementState`）。
- 在 `query.ts` 中有 **aggregate tool result budget**：单轮所有工具结果总和超过阈值时，自动将非关键结果替换为摘要或持久化引用。
- `FileReadTool` 的 `maxResultSizeChars` 甚至被设为 `Infinity`，因为它自带 `maxTokens / maxSizeBytes` 限制，避免"持久化-再读取"的循环。

**建议：**
- 必须引入**消息级 aggregate budget**，作为 Tool Contract 的底层基础设施，而不是可选策略。
- 对于 `list_dir / grep_text` 等高体积工具，当单轮结果总量超过阈值时，harness 应：
  1. 自动将旧结果替换为 `X results omitted. See <ref>`；
  2. 在当前 turn 的系统提示中追加一条 `budget_hint`："Multiple search results were large; prefer using more specific patterns or read_file for targeted context."

### 4.3 Shell Fallback Pack 的设计有自废武功的风险

9.8 节提出 "Shell 不应再承担主要工作流"，并建议"默认隐藏，仅在 phase engine 判定需要时装载"。

`phase engine 判定需要` 的判定标准是什么？如果标准依赖关键词匹配或模型调用失败次数，那么弱模型在专用工具失败一次后，系统给它的选项就只剩下 shell——这**会训练模型在遇到阻力时退化为 shell 调用**，反而加剧工具调用失败。

对于 C 工程，大量操作（如 `make`, `cmake`, `ninja`）本质上仍是命令执行。recipe 中心确实可以封装常用命令，但首次配置 recipe 时仍离不开 shell 探索。

**Claude Code 的参照：**
BashTool 是所有工具中 **prompt 最详尽、场景覆盖最周密的工具**（仅 `bashCommandHelpers.ts` 和 `prompt.ts` 就超过 800 行）。Claude Code 并未削弱 BashTool，而是**通过极其详细的 prompt 来约束它何时被使用、何时不该使用**。

Claude Code 甚至把 "有专用工具时优先用专用工具" 写在 **BashTool 自己的 prompt 里面**，让模型在每次想用 Bash 时都自我检查。

**建议：**
- 不要"默认隐藏 shell"，而是**给 shell 一个极其严格的 prompt**，明确要求：
  - `read/search/list/edit` 有专用工具时不得使用 shell；
  - 调用前必须在 reasoning 中说明"为什么专用工具不够"。
- 如果模型仍然误用 shell，**通过 `validateInput` 拦截并返回 `suggested_fix: "改用 edit_file"`**，而不是直接移除 shell 选项导致模型走投无路。

---

## 5. Prompt Stack 的问题

### 5.1 7 层 prompt stack 对弱模型可能过于复杂

8 节 Prompt Stack：Base Frame → Project Constitution → Mode Frame → Phase Frame → Discipline Frame → Active Tool Prompts → Runtime Guidance。

分层本身是工程上清晰的结构，但对于**上下文理解能力有限**的模型，过多的层级反而会让它抓不住重点。弱模型往往只能有效响应**最近一次 system message 注入**或**最显眼的指令块**。

此外，文档没有定义各层之间的**优先级冲突解决规则**。如果 Base Frame 说"保持简洁"，而 Discipline Frame 说"先写 spec 再写测试"，模型应该听谁的？

**Claude Code 的参照：**
Claude Code 的 system prompt 打法是**"一条主 prompt + 少量动态追加"**。工具 prompt 不是通过独立 frame 注入，而是**直接作为每个 tool 的 `prompt()` 返回内容，在工具被装载时拼入 system message**。

不存在显式的 "Phase Frame"，phases 的状态转换是通过**工具结果 + 少量 loop 级别的状态提示**来隐式驱动的。

**建议：**
- 将 7 层压缩为 **3 个物理注入单元**：
  1. **Base System Prompt**（角色、工程方法学、全局约束）
  2. **Mode Context**（当前任务类型、tool pack、以及 `discipline_checklist` 进度表）
  3. **Runtime Nudges**（仅当需要时注入的 1-2 句话提醒，如 "Last compile failed, fix before proceeding.")
- `Phase Frame` 和 `Discipline Frame` 不要作为独立 system message 注入，而是**作为 Mode Context 中的子段落**，一次性拼入。

### 5.2 Active Tool Prompts 的装载时机未明确

6 节和 10 节的 ToolPack 设计意味着每次 phase 切换都要重新计算可见工具集和对应 prompt。

如果 phase 切换频繁（如 `implement → check → repair → implement` 循环），**prompt 中的 tool descriptions 会在每次切换时被重新排序或截断**，这会破坏弱模型对工具位置的记忆（一些弱模型对 prompt 开头/结尾的内容更敏感）。

Claude Code 采用了一种更稳定的做法：**核心工具（Read, Edit, Bash, Glob, Grep）始终可见**，其余工具才按需延迟加载（`shouldDefer: true`）。

**建议：**
- 定义一个 **"常驻核心工具集（Core Pack）"**，包含 `read_file, edit_file, write_file, list_dir, grep_text, run_recipe, ask_user, task_status`，这些工具在任何 phase 都稳定可见。
- 其他工具才按 phase 延迟加载。这样可以给弱模型一个稳定的"肌肉记忆"基础。

---

## 6. Permission / Allowlist V2 的问题

### 6.1 Rule DSL 的编译与调试成本被低估

11.3 节给出示例：
```text
allow Read(**)
allow Edit(src/**/*.c)
ask Shell(prefix:git push)
deny Shell(pattern:rm -rf *)
```

这本质上是一个小型 DSL，需要 parser、AST、evaluator。对于目标约束（Win7、离线、Python 3.8 嵌入式）来说，引入 DSL parser 的维护成本不低。

`ask Shell(prefix:git push)` 中的 `prefix` 与 `pattern` 语义差异对非技术用户不直观。文档中也没有说明**规则冲突时的解决策略**（例如一条 `allow Edit(**)` 和一条 `deny Edit(secret.c)` 同时命中时怎么办）。11.5 节的判定顺序提到了 explicit deny → explicit ask → explicit allow，但没有说明同一工具在同一路径上的多规则合并逻辑。

**Claude Code 的参照：**
Claude Code 的权限规则采用**更简单的通配符匹配**（`matchWildcardPattern`），配置格式是 settings.json 中的 JSON 数组（`GlobalToolPermissionRule`）。

没有自定义 DSL，而是通过**工具自带的 `preparePermissionMatcher` + 通配符**实现匹配。这降低了配置面复杂度，用户通过学习 JSON/hooks 即可掌握。

**建议：**
- **首期不要自定义 DSL**。直接采用 TOML/JSON 配置格式，规则条目形如：
  ```json
  { "tool": "Edit", "path": "src/**/*.c", "decision": "allow" }
  ```
- 如果未来确实需要 DSL，那也应该在 JSON 规则稳定运行至少一个版本后再做语法糖层，而不是在重构基线就引入。

### 6.2 权限解释层缺乏"确定性模板规范"

11.4 节要求每次权限请求给出：触发工具、风险类别、触发原因、命中规则来源、涉及路径、可记忆范围。

"为了离线稳定和弱模型适配，默认采用确定性模板生成"——这个设计意图正确，但文档没有给出**模板的具体结构**。如果模板生成逻辑散落在各个 permission 处理函数中，那么不同工具返回的解释风格会不一致，模型仍难以理解。

**建议：**
- 在阶段 1 就实现一个 `PermissionExplanationBuilder` 类，强制所有权限请求通过它生成解释文本。输出结构固定为：
  ```text
  [请求] {tool_name}({args_summary})
  [风险] {risk_category}
  [原因] {trigger_reason}
  [规则] {rule_source_or_default}
  [范围] {path_or_command}
  [记忆] 本次允许 / 本次会话 / 永久 (once/session/project)
  ```
- 对于弱模型，解释文本应尽量控制在一句话以内（如 `"Edit(src/main.c) is blocked: file is outside the current mode's writable range. Consider switching to build mode or adding an allow rule."`）。

---

## 7. Failure Model / Recovery 的问题

### 7.1 自动修正参数并重试一次（`schema_*`）的可行性存疑

12.3 节恢复矩阵建议：`schema_*` → 自动修正参数后重试一次。

哪些参数错误是可以"自动修正"的？`schema_missing_required` 的情况下系统怎么知道 missing field 应该填什么值？如果系统真能自动修正，那说明 schema 本身设计得不够好，或者默认值缺失。

对于弱模型，**自动重试一次如果仍然失败，会迅速耗尽 turn 的 tool call 预算**，导致模型没有机会向用户解释发生了什么。

**Claude Code 的参照：**
Claude Code 并不自动重试参数错误的 tool call。它在 `validateInput` 失败时返回 `{ result: false, message, errorCode }`，把这个 message 作为 tool result 直接返回给模型，**由模型在下一轮生成修正后的参数**。

这种设计基于一个事实：LLM 的自我修正能力（即使是弱模型）在得到明确错误信息后，往往比系统的启发式修正更可靠。

**建议：**
- 取消 "自动修正参数后重试"，改为：
  1. `schema_*` 错误 → 返回高信息量的失败结果（`error_kind`, `missing_fields`, `suggested_fix`）；
  2. **由模型在下一次迭代中自行修正**；
  3. harness 只在**同一轮内、同一工具已连续失败 2 次**时，才追加一个系统提示 nudge（`"You have failed to call X twice. Common mistake: Y. Please check your parameters."`）。

### 7.2 `no_match / ambiguous_match` 的恢复建议流于表面

12.3 节：`no_match` → 自动建议改用 `glob_files / grep_text / read_file`；`ambiguous_match` → 提示缩小片段或读取更多上下文。

"自动建议改用某某工具" 不等于 "模型会成功改用"。弱模型在收到 `no_match` 后，可能陷入循环：先用 `grep_text`，找不到；再用 `list_dir`，找不到；再用 `read_file` 乱猜。文档没有定义**当建议被模型忽略时的兜底策略**。

**建议：**
- 对于 `no_match` 和 `ambiguous_match`，harness 不应只是"建议"，而应**主动向模型提供替代信息**。例如：
  - `edit_file` 的 `old_string` 未匹配 → 在失败结果中附加 `actualSnippet: "相近文本为 ..."`（参考 Claude Code `FileEditTool` 的 `findActualString` 逻辑）；
  - `grep_text` 的 pattern 未匹配 → 调用内部 `glob_files` 扫描目录，把 "该目录下有哪些文件" 作为失败结果的一部分返回。
- 这本质上是在**把恢复成本从模型侧转移到系统侧**。

---

## 8. Task / Todo 重做的盲区

### 8.1 `TaskGraph` 系统主导但 `task_update` 仍依赖模型调用

9.7 节提出内核维护 `TaskGraph`，phase engine 自动更新当前任务状态，模型只在需要补充/拆分/纠偏时通过 `task_update` 参与。

这个设计的关键假设是 "phase engine 能自动知道任务进度"，但实际上 phase engine 只能根据工具调用的**副作用**推断进度（如编译通过 = make 阶段完成）。它无法知道模型是否已经"理解了需求"或"完成了根因定位"。

如果 `task_update` 仍是一个可选工具，弱模型可能仍然不使用它，导致 `TaskGraph` 与真实工作流脱节。

**Claude Code 的参照：**
Claude Code 的 `TodoWriteTool` 是一个**延迟加载（`shouldDefer: true`）的工具**，模型需要通过 `ToolSearch` 才能发现它。这设计上的意图就是**不把 todo 当成核心工作流强制项**。

Claude Code 并没有一个独立的 `TaskGraph` 内核来驱动任务，而是**把当前进行中的活动直接显示在状态栏（status line）**，并在某些技能（skills）中通过结构化 prompt 要求模型维护 checklist。

**建议：**
- 如果 TODO/任务跟踪确实对当前场景非常重要，不要把 `task_update` 做成可选工具。
- 更可行的方案是：
  1. 把任务列表作为 **system prompt 的固定段落**，每次 turn 都携带；
  2. 模型对任务的更新不是通过 `task_update` 工具，而是**在每次 assistant message 的 reasoning 中被 parse 出来**，由 harness 自动同步到任务列表。
  3. 这样即使弱模型不主动调用工具，只要它在文本中说 `"Next, I will fix the buffer overflow in line 42"`，harness 就能提取并更新任务状态。

---

## 9. 实施路径的风险

### 9.1 Clean-slate 重构必须正视大爆炸集成风险

14 节的实施建议：
1. Harness 核心对象重构
2. Tool Contract V2
3. Build/Debug 工作流
4. Permission DSL
5. Verify 与 UI 可视化
6. 清理旧体系

Slice 1-6 是一个典型的大瀑布顺序。既然项目明确选择 **clean-slate 重构**，不保留旧 mode、旧权限、旧 session 的兼容逻辑，也不做新老并行，那么必须正视以下风险：

- **开发冻结期**：在 Slice 1-4 完成之前，旧功能的需求迭代必须冻结，否则重构代码会不断追赶新提交的旧模式逻辑。
- **大爆炸集成窗口**：Slice 6 "清理旧体系" 需要一次性的开关翻转。必须预留足够的端到端测试窗口（建议至少 2 周），在此期间所有核心路径（build、debug、verify）必须被重新验证。
- **旧 session 直接废弃**：clean-slate 意味着旧会话不可恢复，前端直接拒绝加载旧格式即可。
- **Frontend 协议同步**：不并行意味着 frontend 只需维护一套 protocol adapter。但必须确保重构期间，frontend 团队与 core 团队的协议版本严格对齐，避免"core 已经切换到新 event 格式，frontend 还在解析旧格式"的断层。

---

## 10. 总结与关键修正建议

### 10.1 总体评价

`agent-harness-v2.md` 的诊断非常精准，但**治疗方案的剂量偏大**。它试图在一个重构周期内同时解决：
- 模式系统（Mode → Phase）
- 工具契约（11 个必填字段）
- 权限 DSL（自定义语言）
- 失败恢复矩阵（自动重试 + phase 切换）
- Prompt Stack（7 层）
- 结果预算（多级别策略）

对于一个小团队维护的、面向弱模型的、Win7 离线环境的系统来说，**同时推进这么多重设计极易导致实现半贴子化**（每样都做了，每样都不扎实）。

### 10.2 最关键的 6 条修正建议

1. **保留完整 Phase 粒度，但只在复杂任务启用**。`build` 的 `full_spec_tdd` 轨道保留 7 个 phase，`lite_spec_tdd` 自动压缩到 `understand → contract → implement → check → handoff`，简单任务可进一步降级。
2. **Phase 切换由 artifact 检测触发，不是失败回退**。`command_exit_nonzero` 不直接切 phase，只在 `edit + rerun passed` 时才从 `repair` 进入 `handoff`。
3. **Tool Contract 先只做最小集**：去掉 `phase_affinity / examples / success_schema / failure_schema` 的必填要求，把 `when_to_use` 写进 prompt 文本。
4. **权限首期不做自定义 DSL**，先用 TOML/JSON 的规则列表 + 确定性解释模板跑通。
5. ** failure recovery 取消"自动修正参数"和"自动切换 phase"**，改为向模型返回高信息量的错误结果 + `suggested_fix`，由模型自行修正。
6. **实施路径接受 clean-slate 重构**，但需正视大爆炸集成风险：开发冻结期、2 周端到端验证窗口、旧格式直接废弃无需兼容。

### 10.3 从 Claude Code 最值得吸收的三点

1. **Tool Prompt 的详尽程度决定工具调用成功率**。Claude Code 的 `BashTool/prompt.ts` 不是简单的功能描述，而是**数百行的场景操作手册**。 Prompt 工程应该是重构的首要和最高优先级工作。
2. **结果预算不是 schema 字段，而是底层基础设施**。Claude Code 的 `contentReplacementState` 和 `maxResultSizeChars` 是自动生效的，不需要每个工具自己决定策略。应该先做基础设施，再让工具接入。
3. **权限匹配保持简单**。Claude Code 没有复杂的 DSL，就是通配符 + JSON 配置 + `preparePermissionMatcher`。对于目标约束来说，简单意味着可靠。

---

*本报告已记录于 `docs/issues/agent-harness-v2-design-review.md`，建议在进入 Harness V2 实现切片前召开设计 review，确认上述修正方向。*
