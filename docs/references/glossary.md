# Glossary

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-06-17`
> 对应代码范围：`README.md`, `AGENTS.md`, `docs/`, `src/embedagent/`

## 1. Official Product Vocabulary

| 术语 | 含义 | 备注 |
|---|---|---|
| `explore` | 默认入口模式，用于探索、理解与收集上下文 | 正式 mode |
| `spec` | 需求、方案和规格收敛模式 | 正式 mode |
| `build` | 唯一的一等实现模式 | 正式 mode |
| `debug` | 面向问题定位与修复的模式 | 正式 mode |
| `verify` | 只读的质量门与验证模式 | 正式 mode |
| `TaskGraph` | 官方任务真相结构 | 不使用 prompt-only todo flow |
| `task_status` | 官方任务观察与投影接口 | 前端与模型都围绕该语义 |
| `discipline_profile` | Harness 内部执行纪律档位 | 与 `mode`、`execution_phase` 配套 |
| `execution_phase` | Harness 内部执行阶段 | 与 `mode`、`discipline_profile` 配套 |
| `transcript.jsonl` | 唯一 durable session-history ledger | 历史真相源 |
| `SessionHistoryAssembler` | GUI 历史序列化器 | 不由 replay-log 直接生成历史 |

## 2. Official Document Vocabulary

| 术语 | 含义 | 备注 |
|---|---|---|
| `superpowers process docs` | 当前切片说明书 | 位于 `docs/superpowers/` |
| `global project docs` | 长期 `source-of-truth` | 位于 `README.md`、`AGENTS.md` 与 `docs/` 活动文档 |
| `archive docs` | 历史留痕 | 位于 `docs/archive/` |
| `module docs` | 模块级长期说明 | 位于 `docs/modules/` |
| `workflow docs` | 可执行流程说明 | 位于 `docs/workflows/` |
| `reference docs` | 术语、映射与图表约定 | 位于 `docs/references/` |

## 3. Historical Terms And Their Status

| 历史术语 | 当前状态 | 替代词汇 / 说明 |
|---|---|---|
| `code` 作为 first-class mode | 禁止在活动文档中作为正式词汇使用 | 使用 `build` |
| retired todo vocabulary | 禁止作为前端正式词汇使用 | 使用 `tasks` |
| retired todo-management tool name | 禁止作为官方任务工作流语义使用 | 使用 `TaskGraph`、`task_status` |
| `timeline.jsonl` 作为历史数据库或 transport ledger | 禁止 | 当前契约无 durable timeline transport；GUI history 只走 transcript/bootstrap |
| 完成切片 plan/spec 停留在 `docs/superpowers/` | 禁止 | 回写长期文档后归档到 `docs/archive/<topic>/` |
| 历史阶段说明停留在 docs 根目录 | 禁止 | 迁入合适的 `docs/archive/<topic>/` |

## 4. Usage Rules

- 活动文档优先使用本文件中的正式术语。
- 历史术语只允许出现在“历史说明”或“兼容说明”中。
- 如果正式术语变化，先更新本文件，再更新根文档和模块文档。
