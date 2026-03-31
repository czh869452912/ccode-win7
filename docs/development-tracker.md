# EmbedAgent 开发进度跟踪

> 更新日期：2026-03-31（DC-034 修订）
> 用途：持续跟踪当前阶段、下一步任务、里程碑进度、风险与阻塞

---

## 1. 使用规则

本文件用于回答四个问题：

1. 当前做到哪一步了？
2. 下一步最应该做什么？
3. 哪些任务已经完成，哪些仍在阻塞？
4. 当前有哪些风险需要被持续关注？

更新规则：

- 每完成一个里程碑或子里程碑，更新本文件
- 每次重要设计变更，同时检查是否需要同步本文件
- 当前只保留“近期最重要”的 5-10 项任务，不把它写成无限 backlog

---

## 2. 当前阶段

### 总阶段

- 当前阶段：`Phase 4 真实工程验证 + Phase 6 GUI / Win7 收口`
- 总体状态：`进行中`
- 当前重点：`Phase 4 默认 recipe/真实工程/Win7 验证，Phase 6 GUI 新壳层与 Win7 Chromium 基线收口，Phase 7 继续推进 site-packages 精简与 Win7 bundle 验收`

### 当前判断

项目已经完成：

- 范围和目标收敛
- 参考项目分析
- 总体方案设计
- 实施路线与文档治理基线
- 项目级 `AGENTS.md`
- Python 3.8 / `uv` / `conda` 版本策略落盘
- 工具设计规范 `docs/tool-design-spec.md`（DC-004）
- 实施分期重组（DC-005）：关键路径前移，Phase 1 = 最小可工作 Loop
- Phase 1 最小原型代码骨架（`src/embedagent/`）
- 本地闭环自测：工具调用、Observation 回注、CLI 启动、语法编译
- Python 3.8.10 `uv` 环境验证通过（`.venv`）
- Moonshot `kimi-k2.5` 真实联调已跑通最小工具闭环（需使用 `/v1`，并保留 `reasoning_content`）
- `docs/llm-adapter.md` 已建立，记录已验证 provider 兼容点
- Phase 2 工具核心实现已落地：`run_command`、`git_status`、`git_diff`、`git_log`
- `docs/tool-contracts.md` 已建立，记录当前工具接口契约
- Phase 2 Loop 烟雾验证通过：`run_command` 与 `git_status` 已通过主循环消费验证
- Phase 3 模式系统 v2 已落地：5 模式配置驱动（`explore`/`spec`/`code`/`debug`/`verify`）、`initialize_modes`、工具过滤、`/mode`；`switch_mode` LLM 工具已移除
- `docs/mode-schema.md` 与 `docs/harness-state-machine.md` 已建立
- Phase 3 验证通过：模式切换、违规工具拦截、写入范围拦截均已完成本地验证
- Phase 4 工具第一版已落地：`compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
- `docs/clang-integration-plan.md` 已建立
- Phase 4 解析验证通过：编译诊断、测试汇总、覆盖率提取、质量门评估均已完成本地验证
- 项目内闭环 Clang 工具链已落地到 `toolchains/llvm/current`
- 已完成真实本地 smoke test：编译、analyze、clang-tidy、profdata、llvm-cov report
- Phase 5 最小权限模型已落地：CLI 可对写入和命令执行做确认
- Doom Loop Guard 已落地：连续失败和重复失败动作会触发防护
- `docs/permission-model.md` 已建立
- `docs/context-management-design.md` 已建立
- Phase 5 第一版上下文管理已落地：旧 turn 摘要化、Observation 遮蔽化、最近 turn 保真化
- Phase 5A 上下文预算器已接入：按 mode 分配预算并为输出/推理预留空间
- Phase 5A ReducerRegistry 已落地：不同工具按类型裁剪 Observation，并返回 ContextStats / BudgetEstimate
- Phase 5B Artifact Store 已落地：长输出与大列表会落盘为 `.embedagent/memory/artifacts/...` 并回写 `artifact_ref`
- Phase 5C Session Summary Store 已落地：会话关键状态会持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
- Phase 5D Project Memory Store 已落地：项目级 profile / recipe / known issue 已可落盘并注入上下文
- Phase 5E Resume Entry 已落地：CLI 已支持 `--list-sessions` 与 `--resume <session_id|latest|summary.json>`
- Phase 5F Memory Maintenance 已落地：artifact / session / project memory 已具备基础 cleanup 与索引收口能力
- Phase 5 长任务稳定性验证已完成：`scripts/validate-phase5.py` 已在修复根目录文件写入边界后重新跑通
- Phase 5 权限细化已完成：已支持规则文件、allow / ask / deny、路径与命令模式匹配
- Phase 7 设计基线已建立：`docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md`
- Phase 7 初始脚本骨架已落地：`scripts/prepare-offline.ps1` 已可生成 `build/offline-staging/EmbedAgent/`、launcher、模板配置和 manifest/checksum 草案，并已通过 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证
- Phase 7 build 脚本骨架已落地：`scripts/build-offline-bundle.ps1` 已可把 staging bundle 复制到 `build/offline-dist/`、重写 manifest、重算 checksum，并生成 zip
- Phase 7 validate 脚本骨架已落地：`scripts/validate-offline-bundle.ps1` 已在 skeleton bundle 上验证通过，且 `-RequireComplete` 会按预期对缺失资产返回失败
- Phase 7 真实资产接入已打通第一段：`scripts/offline-assets.json` 已固定 `python_embedded_x64` 与 `mingit_x64`，`prepare/build/validate` 已完成真实 zip、SHA256、sources seed、license notice 与 launcher 校验
- Phase 7 真实资产接入已继续扩展到 `ripgrep_x64` 与 `universal_ctags_x64`，当前 `prepare/build/validate -RequireComplete` 已在四类核心资产上通过
- GUI 状态语义已收口：session status 现在以 `session_snapshot` 为权威，补齐了 `session_status`、`reasoning_delta`、`thinking_state`、稳定 `tool_call_id` 与 GUI 专用懒加载文件树接口
- todo 已切换为 session-scoped：真实会话默认使用 `.embedagent/memory/sessions/<session_id>/todos.json`，新建会话不再继承旧会话 todo
- 新 GUI webapp 已建立：`src/embedagent/frontend/gui/webapp/` 使用 React + Vite 构建，产物已写回 `src/embedagent/frontend/gui/static/`
- `scripts/validate-gui-smoke.py` 已升级：当前源码路径 smoke 可覆盖 tool / permission / ask_user / session todo 隔离与 renderer 报告
- unified input / slash command / workflow 第一版已落地：`submit_user_message` 已统一分发普通消息与 `/help` `/mode` `/sessions` `/resume` `/workspace` `/clear` `/plan` `/review` `/diff` `/permissions` `/todos` `/artifacts`
- 协议层已扩展 `CommandResult`、`PlanSnapshot`、`TurnRecord`、`TimelineItem` 与增强版 `SessionSnapshot`；GUI 已接入 command result、plan pane、command cards 与 slash command hint
- `/review` 已升级为结构化 findings 输出；GUI 工具卡片开始使用 Core 下发的 `tool_label` / `progress_renderer_key` / `result_renderer_key` 做分支渲染
- GUI 已新增独立 review inspector；后端已暴露 tool catalog API，前端开始用 Core 的工具目录为旧 timeline / fallback 展示补足 label 与 renderer

项目下一步：继续推进 Phase 4 真实工程验证，在 Win7 bundle 中验证 Fixed Version WebView2 109 路径，并把 Phase 7 的 site-packages 精简和 Win7 bundle 验收接上。

---

## 3. 下一步优先级

### P0：立刻要做（当前关键路径）

1. 推进 Phase 4 的真实 C 工程与 Win7 验证
2. 在 Win7 bundle 中完成 GUI Chromium 基线实机验证并记录结果
3. 为当前 bundle 评估并收敛 `site-packages` 的精简导出方案

实现备注：

- Phase 1 已按当前可用条件验收完成；`GLM5 int4` / `Qwen3.5` 因环境不具备暂不纳入阻塞项。
- 当前原型已收敛到 `src/embedagent/` 包结构，打包入口与导入路径已同步更新。
- Phase 2 里程碑已满足：文件读写、命令执行、Git 状态/差异/日志均已具备并完成 3.8 本地验证。
- Phase 3 v2 里程碑已满足：5 模式（explore/spec/code/debug/verify）、配置驱动、工具过滤、用户主导切换均已完成 3.8 本地验证。
- Phase 4 已具备项目内闭环工具链，但默认 recipe、真实 C 工程和 Win7 验证仍需补齐。
- Phase 5 脚本验证已重新跑通，当前已从“实现完成”推进到“脚本复验通过”。
- Phase 6 自动化验证已通过，当前缺口已收敛到 Win7 Chromium 路径与真实交互体验。
- Phase 7 现已完成设计基线、ADR、`prepare/build/validate` 三段脚本骨架，以及 Python / MinGit / rg / ctags 的真实资产接入；下一步应转向 site-packages 精简与完整 bundle 验收。

### P1：紧随其后

1. 收敛 Clang bundle 的版本组合与默认命令 recipe
2. 决定是否将 memory browse / inspect 作为 Phase 6 收口项
3. 评估终端前端稳定后是否推进 stdio JSON-RPC adapter
4. 决定是否从 `.venv\Lib\site-packages` 继续直拷，还是切到更精简的运行时导出策略
5. 在 Win7 虚拟机上对当前四类核心资产 bundle 做一次真实验收

---

## 4. 近期任务板

| 编号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| T-001 | 建立最小 `pyproject.toml` + 代码骨架 | `completed` | 已收敛为 `src/embedagent/` 包结构 |
| T-002 | 实现 `OpenAI-compatible LLM Adapter` | `completed` | 同步+流式，Python 标准库，无厂商 SDK |
| T-003 | 实现第一批工具（read/list/search/edit） | `completed` | 已按 `docs/tool-design-spec.md` 规范落地 |
| T-004 | 实现最小主循环 + CLI 入口 | `completed` | 本地假模型闭环已跑通 |
| T-005 | Phase 1 里程碑验证（GLM5 + Qwen3.5） | `completed` | 目标模型环境不具备，按 Moonshot + Python 3.8 验证口径验收 |
| T-006 | 实现 Phase 2 工具（run_command / git） | `completed` | 已补齐工具契约与 Loop 烟雾验证 |
| T-007 | 实现模式系统 v1（dict + 工具过滤） | `completed` | 已补齐文档与本地验证 |
| T-008 | 实现 Phase 4 Clang 工具链第一版封装 | `in_progress` | 已有本地闭环工具链，待真实工程验证与版本收敛 |
| T-009 | 实现 Phase 5 最小权限与防循环保护 | `completed` | 权限模型、Doom Loop Guard、ContextManager、mode-aware budget、Artifact Store、SessionSummaryStore、ProjectMemoryStore、Resume Entry、MemoryMaintenance 已落地；`scripts/validate-phase5.py` 已在 2026-03-29 复验通过 |
| T-010 | 完成 Phase 6 前端协议与 TUI IA 设计 | `completed` | `frontend-protocol.md` 与 `tui-information-architecture.md` 已建立 |
| T-011 | 实现 Phase 6A InProcessAdapter | `completed` | CLI 已改为通过 adapter 驱动 Core，并完成最小行为验证 |
| T-012 | 落地模块化终端前端 | `completed` | 已完成 `src/embedagent/frontend/tui/` 模块化拆包，`src/embedagent/frontend/tui/` 已按新架构迁移，接入 timeline / workspace / artifact / todo 浏览接口，保留 `embedagent.tui` 兼容入口；下一步是继续做真实控制台 / Win7 手工验证与交互细化 |
| T-013 | 建立 Phase 6 验证入口 | `completed` | `scripts/validate-phase6.py` 与 `docs/phase6-validation.md` 已建立，Phase 6 已进入脚本可跟踪状态 |
| T-014 | 建立 Phase 7 离线打包设计基线 | `completed` | 已新增 `docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md` |
| T-015 | 实现 Phase 7A prepare-offline 骨架 | `completed` | 已新增 `scripts/prepare-offline.ps1`，可生成 `build/offline-staging/EmbedAgent/`、launcher、模板配置、manifest 与 checksum 草案，并支持 `-SkipBuild` |
| T-016 | 实现 Phase 7B build-offline-bundle 骨架 | `completed` | 已新增 `scripts/build-offline-bundle.ps1`，可消费 staging bundle，生成 `build/offline-dist/<artifact>/` 与 zip，并重写 dist manifest/checksum |
| T-017 | 实现 Phase 7C validate-offline-bundle 骨架 | `completed` | 已新增 `scripts/validate-offline-bundle.ps1`，可校验 skeleton bundle，并支持 `-RequireComplete` 切换到严格门禁 |
| T-018 | 接入 Python embeddable 与 MinGit 真实资产 | `completed` | 已新增 `scripts/offline-assets.json`，并完成真实 zip 下载、SHA256 固定、staging 解压、sources seed、license notice 与 `-RequireComplete` 验收 |
| T-019 | 接入 ripgrep 与 Universal Ctags 真实资产 | `completed` | 已扩展 `scripts/offline-assets.json` 与 `prepare/build/validate`，完成真实 zip 下载、SHA256 固定、sources seed、license notice 与 `-RequireComplete` 验收 |
| T-020 | 实现新架构协议层（protocol/core/frontend） | `completed` | 已新增 `protocol/` 层定义 CoreInterface/FrontendCallbacks，`core/` 层实现 AgentCoreAdapter，`frontend/gui/` 实现 PyWebView 前端，架构测试 17 项全通过 |
| T-021 | GUI 前端与后端功能联动 | `in_progress` | 已完成 session-scoped todo、权威 session snapshot 状态事件、稳定 tool_call_id、reasoning/thinking 事件、GUI 懒加载文件树、新 React/Vite webapp 构建、slash command / plan pane / command cards、structured review command、review inspector 与 tool catalog fallback；剩余缺口是更完整的 workflow 深化与 Win7 实机验证 |
| T-026 | unified input / slash command / workflow 第一版 | `completed` | 已打通 `submit_user_message -> slash command dispatcher -> command_result / plan_updated -> GUI/TUI` 闭环，并补齐协议类型、计划存储、权限上下文与 focused tests |
| T-022 | 零依赖打包：Python 依赖完整导出 | `completed` | 已新增 `scripts/export-dependencies.py`，确保所有 Python 依赖（含传递依赖）完整导出到 site-packages |
| T-023 | 零依赖打包：依赖完整性验证 | `completed` | 已新增 `scripts/check-bundle-dependencies.py`，验证 bundle 包含所有必需依赖 |
| T-024 | 零依赖打包：内网部署文档 | `completed` | 已新增 `docs/intranet-deployment.md` 和 `docs/offline-packaging-guide.md`，提供完整内网部署指南 |
| T-025 | 零依赖打包：内网配置模板 | `completed` | 已新增 `config/config.json.template`，预配置内网大模型服务示例 |

---

## 5. 里程碑进度

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| Phase 0 | 仓库基线与工作约束 | `completed` | 已完成文档、版本策略、治理基线、工具规范 |
| Phase 1 | 最小可工作 Loop | `completed` | 已完成 Python 3.8 与真实 OpenAI-compatible 工具闭环验证 |
| Phase 2 | 工具集 v1 | `completed` | 已实现 run_command / git 工具，并完成 3.8 本地验证 |
| Phase 3 | 模式系统 v2 | `completed` | 5 模式配置驱动（explore/spec/code/debug/verify）、initialize_modes、工具过滤、/mode 已完成；switch_mode LLM 工具已移除 |
| Phase 4 | Clang 工具链 | `in_progress` | 已有项目内闭环工具链，待真实工程与 Win7 验证 |
| Phase 5 | 质量保障层 | `completed` | 权限、上下文、记忆、恢复与 cleanup 已落地；修复根目录文件写入边界后，专项验证脚本已复验通过 |
| Phase 6 | CLI / TUI / GUI | `in_progress` | InProcessAdapter 已扩展 workspace / timeline / artifact / todo 前端接口；终端前端已拆为 `frontend/tui` 子模块；GUI 已切换到 React/Vite webapp + PyWebView 宿主，当前环境 smoke 已覆盖 tool / permission / ask_user / todo 隔离；待 Win7 Chromium 实机验证与 diff/编辑闭环细化 |
| Phase 7 | 打包与离线交付 | `in_progress` | 设计基线、ADR、`prepare/build/validate` 三段脚本骨架已完成；Python/MinGit/rg/ctags 真实资产接入已完成；GUI 依赖与 bundle-local smoke 已进入交付物，`validate-offline-bundle -RequireComplete`、`check-bundle-dependencies.py` 与 bundle 级 windowed GUI smoke 已通过；待 Win7 bundle 实机验收 |

---

## 6. 当前风险与关注点

| 编号 | 风险 | 当前判断 | 应对方式 |
|------|------|----------|----------|
| R-001 | Python 版本上滑 | 高 | 强制保持 `>=3.8,<3.9`，文档与配置双锁定 |
| R-002 | 过早做 UI 导致核心失焦 | 高 | Phase 6 才做 TUI，Phase 1 只做最简 CLI |
| R-003 | 内网模型 function calling 格式不标准 | 高 | Phase 1 里程碑强制在真实模型上验证，发现问题立即在 LLM Adapter 层补充兼容处理 |
| R-004 | 工具集设计退化（工具增多、描述变复杂） | 中 | `docs/tool-design-spec.md` 有审查清单，每次新增工具前必须过清单 |
| R-005 | 文档和实现脱节 | 高 | 每轮关键变更必须同步更新 tracker / change log / roadmap |
| R-006 | Clang bundle 包大小过大 | 低 | 静态链接验证已通过，打包细节推到 Phase 7 处理 |
| R-007 | provider 兼容差异未系统沉淀 | 中 | 已确认 Moonshot `kimi-k2.5` 需要 `/v1` 和 `reasoning_content`，后续整理到适配文档 |
| R-008 | 当前仓库缺少真实 C 构建入口 | 中 | 已完成本地 smoke test，后续仍需接默认命令和真实工程 |
| R-009 | 当前闭环工具链存在跨版本组合 | 中 | 现状已通过本地 smoke test，后续需要继续收敛到同版本或自建包 |
| R-010 | 当前上下文压缩仍较弱 | 中 | 已有 mode-aware budget、reducer registry、Artifact Store、SessionSummaryStore、ProjectMemoryStore 与 Resume Entry，后续继续补生命周期清理与可选 LLM condenser |
| R-011 | Python embeddable distribution 的 CRT / UCRT 本地部署复杂 | 中 | 用 Phase 7 preflight 清单和本地 DLL bundling 策略收口 |
| R-012 | 第三方二进制来源、License 和 checksum 追溯不足 | 中 | 用 bundle manifest 记录 version/source/license/checksum，并纳入构建产物 |
| R-013 | prepare 阶段与最终 build/validate 阶段契约不清晰，后续脚本容易返工 | 中 | 先把 `prepare/build/validate` 的输入输出边界写清，再继续实现 |
| R-014 | 当前 build 已验证四类核心资产可启动，但 `site-packages` 仍是直拷 `.venv`，离最终 bundle 仍有优化空间 | 中 | 下一步收敛更精简的运行时包导出方案 |
| R-015 | validate 默认允许 skeleton bundle 以告警通过，若无人切到 `-RequireComplete` 可能误判“已可交付” | 中 | 在正式验收和 CI 入口中强制使用 `-RequireComplete` |
| R-016 | 直接拷贝 `.venv\Lib\site-packages` 可能带来过大的 bundle 体积 | 中 | 评估更精简的运行时导出方案，再决定是否替换当前实现 |

---

## 7. 最近更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-03-27 | 建立进度跟踪文件，明确当前阶段与下一步优先级 |
| 2026-03-27 | DC-004/DC-005：工具设计规范建立，实施分期重组，Phase 1 改为最小可工作 Loop |
| 2026-03-27 | 已落地 Phase 1 最小原型代码，并完成本地语法检查、工具自测与假模型闭环验证 |
| 2026-03-27 | Moonshot `kimi-k2.5` 真实联调通过，补齐了温度参数与 `reasoning_content` 兼容处理 |
| 2026-03-27 | 代码骨架迁移到 `src/embedagent/`，并通过 `uv` 创建的 Python 3.8.10 环境验证 |
| 2026-03-27 | 按当前可用条件完成 Phase 1 验收，并切换到 Phase 2 工具集实现 |
| 2026-03-27 | Phase 2 核心工具已实现，并通过 Python 3.8 本地自测 |
| 2026-03-28 | Phase 2 工具契约与 Loop 烟雾验证完成，阶段状态切换到 Phase 3 准备中 |
| 2026-03-28 | Phase 3 模式系统 v1 已完成，并补齐模式结构与状态机文档 |
| 2026-03-28 | Phase 4 第一版工具封装与解析验证完成，并建立 Clang 集成计划文档 |
| 2026-03-28 | 已下载、组装并验证项目内闭环 Clang 工具链，完成编译/分析/tidy/coverage smoke test |
| 2026-03-28 | Phase 5 最小权限模型与 Doom Loop Guard 已落地，并清理了工具链临时产物 |
| 2026-03-28 | Phase 5 第一版 ContextManager 已落地，并完成本地压缩/回归验证 |
| 2026-03-28 | Phase 5A mode-aware budget、ReducerRegistry 与 ContextStats 已落地，并完成本地行为验证 |
| 2026-03-28 | Phase 5B Artifact Store 已落地，并完成大输出脱敏/落盘/回灌验证 |
| 2026-03-28 | Phase 5C Session Summary Store 已落地，并完成状态落盘/回归验证 |
| 2026-03-28 | Phase 5D Project Memory Store 已落地，并完成 recipe / known issue / context 注入验证 |
| 2026-03-28 | Phase 5E Resume Entry 已落地，并完成 list / load / resume 验证 |
| 2026-03-28 | Phase 5F Memory Maintenance 已落地，并完成 cleanup / index 验证 |
| 2026-03-28 | Phase 6B 交互深化已完成：TUI 新增会话列表浏览、权限确认/错误/上下文状态展示，并修复 --tui 空启动路径 |
| 2026-03-28 | Phase 6B 依赖与运行验证已推进：`prompt_toolkit` / `rich` 已接入，非控制台宿主会优雅报错，并完成 headless 真实事件循环验证 |
| 2026-03-28 | Phase 6 验证入口已建立：新增 scripts/validate-phase6.py 和 docs/phase6-validation.md，阶段状态已可脚本跟踪 |
| 2026-03-29 | Phase 6 终端前端已模块化：新增 src/embedagent/frontend/tui/ 包、timeline store 和 adapter 浏览接口，保留 embedagent.tui 兼容入口，并通过 headless 与单元测试 |
| 2026-03-29 | 修复 `**/*.md` 等模式对根目录文件不匹配的问题，补充 `test_modes.py` 回归，并重新跑通 `scripts/validate-phase5.py` |
| 2026-03-29 | README、路线图、进度跟踪与变更日志已按当前能力和阶段状态完成一轮对齐 |
| 2026-03-29 | 建立 Phase 7 离线打包设计基线：新增 `docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md` |
| 2026-03-29 | 建立 `scripts/prepare-offline.ps1`：已可生成 staging bundle 骨架、launcher、模板配置、`bundle-manifest.json` 与 `checksums.txt`，并通过 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证 |
| 2026-03-29 | 建立 `scripts/build-offline-bundle.ps1`：已可把 staging bundle 复制到 `build/offline-dist/`、生成 zip、重写 dist manifest 并重算 checksum |
| 2026-03-29 | 建立 `scripts/validate-offline-bundle.ps1`：默认模式可校验 skeleton bundle 并告警通过，`-RequireComplete` 下会对缺失资产返回失败 |
| 2026-03-29 | 建立 `scripts/offline-assets.json`，正式接入 `python_embedded_x64` 与 `mingit_x64`，并完成真实 prepare/build/validate 验收 |
| 2026-03-30 | 零依赖打包方案落地：新增 `scripts/export-dependencies.py` 导出完整 Python 依赖（含传递依赖），新增 `scripts/check-bundle-dependencies.py` 验证 bundle 完整性，新增 `docs/intranet-deployment.md` 内网部署指南，新增 `docs/offline-packaging-guide.md` 完整打包指南，配置模板已预置内网大模型服务示例 |
| 2026-03-30 | 当前环境 GUI 验证已补齐：已安装 `pywebview` / `fastapi` / `uvicorn` / `websockets`，新增 `scripts/validate-gui-smoke.py`，源码路径与 bundle 路径的 headless GUI smoke 均已通过 |
| 2026-03-30 | 离线 bundle GUI 集成已补齐：`prepare/build/validate` 与 `check-bundle-dependencies.py` 已纳入 GUI launcher / static files / 文档 / site-packages 检查，当前环境完整 bundle 验证通过 |
| 2026-03-30 | Win7 GUI 实机验证入口已准备：GUI launcher 新增 renderer report 与 auto-close 参数，bundle 已内置 `validate-gui-smoke.cmd` 和 `docs/win7-gui-validation.md`，当前 Windows 10 环境 windowed smoke 返回 `renderer=edgechromium` |
| 2026-03-30 | GUI 新壳层已落地：新增 `frontend/gui/webapp/` React + Vite 工程，产物写回 `frontend/gui/static/`；同时完成 session-scoped todo、权威 `session_status`/`thinking_state`/`reasoning_delta`、稳定 `tool_call_id`、GUI 懒加载文件树与增强版 smoke 校验 |





